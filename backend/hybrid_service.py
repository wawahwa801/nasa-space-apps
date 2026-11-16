"""Serve the existing hybrid predictor from verified registry/S3 artifacts."""
from collections import OrderedDict
import os
from pathlib import Path
import sys
import threading

from hybrid_artifacts import S3ArtifactCache


class ModelNotReady(Exception):
    pass


def model_application(bundle):
    # The code is installed with the application, never included in the artifact.
    ml = Path(__file__).resolve().parents[1] / 'ml'
    if str(ml) not in sys.path:
        sys.path.insert(0, str(ml))
    from dashboard_simulation import build_app
    return build_app(bundle / 'geometry', baseline_data_dir=bundle / 'baseline',
                     baseline_checkpoint=bundle / 'baseline/selected.pt')


class HybridService:
    def __init__(self, registry, artifacts=None, factory=model_application, model_name=None):
        self.registry = registry
        self.artifacts = artifacts if artifacts is not None else S3ArtifactCache(
            os.getenv('MODEL_CACHE_DIR', str(Path(__file__).resolve().parent / '.model-cache')),
            os.getenv('HYBRID_S3_BUCKET'), os.getenv('HYBRID_S3_PREFIX', 'models/flex2-hybrid/'),
            os.getenv('AWS_REGION', 'us-west-2'))
        self.factory = factory
        self.model_name = model_name or os.getenv('HYBRID_MODEL_NAME', 'flex2-hybrid')
        self.loaded = OrderedDict()
        self.lock = threading.Lock()

    def handle(self, action, method, query, payload, model_id=None):
        # Serializes inference and first-load operations per process. A second
        # version can coexist with an already-open, version-pinned animation.
        with self.lock:
            model = self.registry.by_id(self.model_name, model_id) if model_id is not None else self.registry.latest(self.model_name)
            if model is None:
                raise ModelNotReady('No matching ready hybrid version')
            identity = (model['id'], model.get('sha256'))
            if identity not in self.loaded:
                bundle = self.artifacts.prepare(model)
                predictor = self.factory(bundle)
                # Fail closed if inference cannot warm up; do not advertise readiness.
                with predictor.test_client() as client:
                    runs = client.get('/api/runs')
                    if runs.status_code != 200 or not runs.json.get('runs'):
                        raise ModelNotReady('Hybrid warm-up failed')
                    first = runs.json['runs'][0]
                    warmup = client.get('/api/compare', query_string={'run': first['id'], **first['values']})
                    if warmup.status_code != 200 or not warmup.json.get('hybrid'):
                        raise ModelNotReady('Hybrid warm-up failed')
                self.loaded[identity] = predictor
                while len(self.loaded) > 2:
                    self.loaded.popitem(last=False)
            self.loaded.move_to_end(identity)
            predictor = self.loaded[identity]
            with predictor.test_client() as client:
                response = client.open('/api/' + action, method=method, query_string=query, json=payload if method == 'POST' else None)
                data = response.get_json(silent=True)
            if not isinstance(data, dict):
                return {'error': 'Unsupported hybrid endpoint'}, response.status_code
            tag = dict(id=model['id'], name=model['model_name'], version=model['model_version'],
                       sha256=model['sha256'], source='s3')
            if response.status_code == 200:
                data['model'] = tag
                if isinstance(data.get('prediction'), dict):
                    data['prediction']['model'] = tag
            return data, response.status_code
