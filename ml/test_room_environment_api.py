"""Custom-layout API uses real solver and explicitly stubbed CNN responses."""
import base64, copy, importlib.util, io, sys, types, unittest
from pathlib import Path
from unittest.mock import patch
from flask import Flask, jsonify
from PIL import Image

def fake_model(_path, texture=False):
    app=Flask('layout-test');buffer=io.BytesIO()
    Image.new('L',(16,16),255).save(buffer,format='PNG')
    png='data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode()
    @app.get('/api/compare')
    def compare():return jsonify(mask=png,hybrid=png,cnn=png,retrieval=png)
    return app

class EnvironmentApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fake=types.ModuleType('flex2_compare');fake.create_app=fake_model
        with patch.dict(sys.modules,{'flex2_compare':fake}):
            spec=importlib.util.spec_from_file_location('layout_api',Path(__file__).with_name('dashboard_simulation.py'))
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            cls.client=module.build_app().test_client()
        cls.query=dict(controls={},mm_per_pixel=.03,k_mm2_s=.8,source=0,environment=dict(
            rooms=[dict(id='a',name='A',x=0,y=0,fuel=True),dict(id='b',name='B',x=9,y=9,fuel=True)],edges=[dict(a=0,b=1,open=True)]))
    def test_default_environment(self):
        r=self.client.get('/api/environment');self.assertEqual(r.status_code,200);self.assertEqual(len(r.json['rooms']),16)
    def test_custom_layout_and_doors_reach_solver(self):
        r=self.client.post('/api/simulate',json=self.query);self.assertEqual(r.status_code,200)
        self.assertEqual(r.json['simulation']['scenario']['rooms'],self.query['environment']['rooms'])
        self.assertIsNotNone(r.json['simulation']['ignition_times_s']['b'])
        q=copy.deepcopy(self.query);q['environment']['edges'][0]['open']=False
        self.assertIsNone(self.client.post('/api/simulate',json=q).json['simulation']['ignition_times_s']['b'])
    def test_invalid_layouts_rejected(self):
        for mutate in [lambda q:q['environment']['rooms'][1].update(x=0,y=0),lambda q:q['environment']['edges'][0].update(b=12),lambda q:q.update(source=3),lambda q:q['environment']['rooms'][0].update(fuel=False),lambda q:q['environment'].update(duration_s=999),lambda q:q['environment']['rooms'][1].update(x=10)]:
            q=copy.deepcopy(self.query);mutate(q);self.assertEqual(self.client.post('/api/simulate',json=q).status_code,400)
if __name__=='__main__':unittest.main()
