"""API/error contracts and selection-query regression checks (no live PostgreSQL)."""
from datetime import datetime, timezone
import sqlite3

import psycopg
import pytest

import app as app_module
from database.registry import ModelRegistry


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch):
    monkeypatch.setattr(app_module, 'load_dotenv', lambda *args: None)
    monkeypatch.setenv('LLM_PROVIDER', 'mock')
    for key in ('DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_SSLMODE', 'DB_SSLROOTCERT'):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def registry():
    # Execute the selection SQL on a local SQL engine to check ordering/filtering.
    # This does not stand in for PostgreSQL connectivity or privilege verification.
    db = sqlite3.connect(':memory:')
    db.execute("ATTACH DATABASE ':memory:' AS model_registry")
    db.row_factory = sqlite3.Row
    db.execute('''CREATE TABLE model_registry.models (
        id INTEGER, model_name TEXT, model_version TEXT, s3_bucket TEXT,
        s3_key TEXT, sha256 TEXT, trained_at TEXT, training_duration_seconds INTEGER,
        status TEXT, is_active BOOLEAN, created_at TEXT)''')
    records = [
        (1, 'flex2', 'old', '2025-01-01T00:00:00+00:00', 'ready', True),
        (2, 'flex2', 'new', '2025-02-01T00:00:00+00:00', 'ready', False),
        (3, 'flex2', 'staged', '2025-03-01T00:00:00+00:00', 'staged', False),
        (4, 'other', 'other-new', '2025-04-01T00:00:00+00:00', 'ready', False),
        (5, 'flex2', 'tie-winner', '2025-02-01T00:00:00+00:00', 'ready', False),
    ]
    for id_, name, version, trained, status, active in records:
        db.execute('INSERT INTO model_registry.models VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                   (id_, name, version, 'private-bucket', f'{version}/selected.pt', None,
                    trained, 60, status, active, '2025-05-01T00:00:00+00:00'))

    class Connection:
        read_only = False
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params):
            assert self.read_only
            self.cursor = db.execute(sql.replace('%s', '?'), params)
            return self
        def fetchone(self):
            row = self.cursor.fetchone()
            if row is None: return None
            row = dict(row)
            for key in ('trained_at', 'created_at'):
                row[key] = datetime.fromisoformat(row[key])
            return row

    def connect(**kwargs):
        assert kwargs['connect_timeout'] == 5
        assert 'statement_timeout=5000' in kwargs['options']
        return Connection()

    yield ModelRegistry(dict(host='localhost', port='5432', dbname='pyroclast', user='reader', password='test-only'), connect=connect)
    db.close()


def test_latest_ready_uses_training_time_and_deterministic_tie(registry):
    client = app_module.create_app(model_registry=registry).test_client()
    response = client.get('/api/models/latest')
    assert response.status_code == 200
    model = response.json['model']
    assert model['model_version'] == 'tie-winner'
    assert model['trained_at'] == '2025-02-01T00:00:00+00:00'
    assert response.headers['Cache-Control'] == 'no-store'


def test_model_name_filter_and_missing_model(registry):
    client = app_module.create_app(model_registry=registry).test_client()
    assert client.get('/api/models/latest?model_name=other').json['model']['model_version'] == 'other-new'
    assert client.get('/api/models/latest?model_name=missing').status_code == 404


def test_sql_parameters_are_not_interpolated(registry):
    client = app_module.create_app(model_registry=registry).test_client()
    assert client.get('/api/models/latest', query_string={'model_name': "flex2' OR 1=1--"}).status_code == 404


@pytest.mark.parametrize('query', ['model_name=', 'model_name=a&model_name=b', 'unknown=x', 'model_name='+'a'*101, 'model_name=%00'])
def test_invalid_query_does_not_touch_database(query):
    class ForbiddenRegistry:
        def latest(self, name): raise AssertionError('Database should not be queried')
    client = app_module.create_app(model_registry=ForbiddenRegistry()).test_client()
    assert client.get('/api/models/latest?' + query).status_code == 400


def test_missing_configuration_keeps_health_available():
    client = app_module.create_app().test_client()
    assert client.get('/api/models/latest').status_code == 503
    assert client.get('/api/health').status_code == 200


def test_connection_failure_does_not_expose_credentials():
    def fail(*args, **kwargs):
        raise psycopg.OperationalError('password=secret internal-db.example')
    registry = ModelRegistry(dict(host='localhost', port='5432', dbname='pyroclast', user='reader', password='secret'), connect=fail)
    client = app_module.create_app(model_registry=registry).test_client()
    response = client.get('/api/models/latest')
    assert response.status_code == 503
    assert b'secret' not in response.data and b'internal-db' not in response.data


@pytest.mark.parametrize('port', ['f', '0', '65536', ''])
def test_invalid_port_never_connects(port):
    def forbidden(**kwargs): raise AssertionError('Must not connect')
    from database.registry import RegistryUnavailable
    registry = ModelRegistry(dict(host='localhost', port=port, dbname='pyroclast', user='reader', password='secret'), connect=forbidden)
    with pytest.raises(RegistryUnavailable): registry.latest('flex2')


def test_route_uses_separate_environment_fields_and_raw_password(monkeypatch):
    for key, value in dict(DB_HOST='db.example', DB_PORT='5433', DB_NAME='pyroclast', DB_USER='reader', DB_PASSWORD='p@ss:/?#%word').items():
        monkeypatch.setenv(key, value)
    captured = {}
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, *args): return self
        def fetchone(self): return None
    def connect(**kwargs):
        captured.update(kwargs)
        return Connection()
    monkeypatch.setattr(psycopg, 'connect', connect)
    client = app_module.create_app().test_client()
    assert client.get('/api/models/latest').status_code == 404
    assert captured['host'] == 'db.example'
    assert captured['port'] == 5433
    assert captured['dbname'] == 'pyroclast'
    assert captured['user'] == 'reader'
    assert captured['password'] == 'p@ss:/?#%word'


def test_pinned_ready_version_is_not_replaced_by_latest(registry):
    assert registry.by_id('flex2', 1)['model_version'] == 'old'
    assert registry.by_id('flex2', 3) is None  # staged
    assert registry.by_id('other', 1) is None
