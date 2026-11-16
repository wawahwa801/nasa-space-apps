"""Registry/S3 inference boundaries; all AWS access is injected in unit tests."""
import hashlib
import io
import json
from pathlib import Path
import zipfile

from botocore.exceptions import ClientError
from flask import Flask, jsonify, request
import pytest

import app as app_module
from hybrid_artifacts import (ArtifactUnavailable, FILES, FORMAT, S3ArtifactCache,
                              extract_bundle, sha256)
from hybrid_service import HybridService, ModelNotReady


def archive_bytes():
    contents = {name: ('test-' + name).encode() for name in FILES}
    contents['bundle.json'] = json.dumps(dict(format=FORMAT, files={
        name:dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest()) for name,data in contents.items()
    })).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        for name,data in contents.items():archive.writestr(name,data)
    return output.getvalue()


@pytest.fixture
def artifact(tmp_path):
    raw = archive_bytes()
    row = dict(id=1,model_name='flex2-hybrid',model_version='v1',s3_bucket='private',
               s3_key='models/flex2-hybrid/v1/bundle.zip',sha256=hashlib.sha256(raw).hexdigest())
    class S3:
        calls = 0
        def get_object(self, **kwargs):
            self.calls += 1
            return dict(ContentLength=len(raw),Body=io.BytesIO(raw))
    s3 = S3()
    return row,S3ArtifactCache(tmp_path, 'private',client=s3),s3


def test_download_verify_and_reuse_disk_cache(artifact):
    row,cache,s3 = artifact
    root = cache.prepare(row)
    assert (root/'geometry/training/final.pt').is_file()
    assert cache.prepare(row) == root
    assert s3.calls == 1
    (root/'baseline/selected.pt').write_bytes(b'tampered')
    with pytest.raises(ArtifactUnavailable):cache.prepare(row)


def test_checksum_and_bucket_fail_closed(artifact):
    row,cache,s3 = artifact
    with pytest.raises(ArtifactUnavailable):cache.prepare(dict(row,s3_bucket='foreign'))
    assert s3.calls == 0
    with pytest.raises(ArtifactUnavailable):cache.prepare(dict(row,sha256='0'*64))
    assert not (cache.root/('0'*64)).exists()
    with pytest.raises(ArtifactUnavailable):cache.prepare(dict(row,sha256=None))


@pytest.mark.parametrize('entry',['../escape','/absolute','geometry/../../escape'])
def test_archive_traversal_rejected(tmp_path,entry):
    path = tmp_path/'bad.zip'
    with zipfile.ZipFile(path,'w') as archive:archive.writestr(entry,b'bad')
    with pytest.raises(ArtifactUnavailable):extract_bundle(path,tmp_path/'out')
    assert not (tmp_path/'escape').exists()


def test_duplicate_entries_rejected(tmp_path):
    path=tmp_path/'duplicate.zip'
    with pytest.warns(UserWarning):
        with zipfile.ZipFile(path,'w') as archive:
            archive.writestr('bundle.json','{}');archive.writestr('bundle.json','{}')
    with pytest.raises(ArtifactUnavailable):extract_bundle(path,tmp_path/'out')


def predictor_factory(bundle):
    app=Flask('stub-predictor')
    @app.get('/api/runs')
    def runs():return jsonify(runs=[dict(id='a',values=dict(n0=100))])
    @app.get('/api/compare')
    def compare():return jsonify(hybrid='generated',conditions=request.args.get('run'))
    @app.post('/api/simulate')
    def simulate():return jsonify(prediction=dict(hybrid='generated'),simulation=dict(received=request.json))
    return app


def test_registry_selection_pins_frames_and_cached_runtime(artifact):
    row,cache,s3=artifact
    other=dict(row,id=2,model_version='v2')
    class Registry:
        def latest(self,name):assert name=='flex2-hybrid';return other
        def by_id(self,name,id_):return {1:row,2:other}.get(id_)
    factories=[]
    def factory(path):factories.append(path);return predictor_factory(path)
    service=HybridService(Registry(),cache,factory)
    first,status=service.handle('runs','GET',[],None)
    assert status==200 and first['model']['id']==2 and first['model']['source']=='s3'
    frame,status=service.handle('compare','GET',[('run','a')],None,1)
    assert status==200 and frame['model']['version']=='v1'
    again,_=service.handle('compare','GET',[('run','a')],None,1)
    assert again['model']['id']==1 and len(factories)==2 and s3.calls==1
    simulation,_=service.handle('simulate','POST',[],dict(controls={'run':'a'}),1)
    assert simulation['prediction']['model']['id']==1
    with pytest.raises(ModelNotReady):service.handle('compare','GET',[],None,999)


def test_api_forwards_pinned_id_and_sanitizes_errors(monkeypatch):
    monkeypatch.setattr(app_module,'load_dotenv',lambda *args:None)
    monkeypatch.setenv('LLM_PROVIDER','mock')
    calls=[]
    class Service:
        fail=False
        def handle(self,*args):
            calls.append(args)
            if self.fail:raise ClientError({'Error':{'Code':'AccessDenied','Message':'private-secret'}},'GetObject')
            return {'hybrid':'image','model':{'id':12,'source':'s3'}},200
    service=Service()
    client=app_module.create_app(hybrid_service=service).test_client()
    response=client.get('/api/hybrid/compare?run=a&n0=1',headers={'X-Model-ID':'12'})
    assert response.status_code==200 and calls[-1][-1]==12
    assert response.headers['Cache-Control']=='no-store'
    for value in ['-1','0','abc','1'*5000]:
        assert client.get('/api/hybrid/compare',headers={'X-Model-ID':value}).status_code==400
    service.fail=True
    response=client.get('/api/hybrid/runs')
    assert response.status_code==503 and b'private-secret' not in response.data
    assert client.get('/api/health').status_code==200


def test_no_config_is_not_local_fallback(monkeypatch):
    monkeypatch.setattr(app_module,'load_dotenv',lambda *args:None)
    monkeypatch.setenv('LLM_PROVIDER','mock')
    class Registry:
        def latest(self,name):return None
    client=app_module.create_app(model_registry=Registry()).test_client()
    assert client.get('/api/hybrid/runs').status_code==503
