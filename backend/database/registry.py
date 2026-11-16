"""Read model metadata without loading weights or activating a deployment."""
import psycopg
from psycopg.rows import dict_row

LATEST_MODEL_SQL = """
    SELECT id, model_name, model_version, s3_bucket, s3_key, sha256,
           trained_at, training_duration_seconds, status, is_active, created_at
    FROM model_registry.models
    WHERE model_name = %s AND status = 'ready'
    ORDER BY trained_at DESC, id DESC
    LIMIT 1
"""


class RegistryUnavailable(Exception):
    """The registry is unconfigured or cannot be read."""


class ModelRegistry:
    def __init__(self, connection_params, connect=None):
        self.connection_params = dict(connection_params or {})
        self.connect = connect or psycopg.connect

    def latest(self, model_name):
        params = self.connection_params.copy()
        if any(params.get(key) in (None, "") for key in ("host", "port", "dbname", "user", "password")):
            raise RegistryUnavailable('Database is not configured')
        try:
            params["port"] = int(params["port"])
            if not 1 <= params["port"] <= 65535:
                raise ValueError
        except (TypeError, ValueError):
            raise RegistryUnavailable('Database port is invalid') from None
        try:
            with self.connect(**params, row_factory=dict_row,
                              connect_timeout=5, options='-c statement_timeout=5000') as conn:
                conn.read_only = True
                row = conn.execute(LATEST_MODEL_SQL, (model_name,)).fetchone()
        except psycopg.Error:
            # Driver errors may contain connection details; do not expose them.
            raise RegistryUnavailable('Model registry is unavailable') from None
        if row is None:
            return None
        model = dict(row)
        for field in ('trained_at', 'created_at'):
            model[field] = model[field].isoformat()
        return model
