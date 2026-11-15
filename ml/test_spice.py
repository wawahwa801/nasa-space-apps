"""Checks for the scientific joins/splits and public prototype API."""
import hashlib
from io import BytesIO
import json
import unittest
import zipfile

import numpy as np
from PIL import Image

from spice_data import ROOT, ART, SOURCE, FIELDS
from spice_model import nearest


class RetrievalTests(unittest.TestCase):
    def test_same_fuel_exact_nozzle_then_distance(self):
        x=np.array([[.4,10,20],[.8,10,20],[.4,12,20],[.4,10,20]])
        fuels=np.array([0,0,0,1]);scale=np.array([.4,10,10])
        idx,_=nearest(x,fuels,np.array([.4,10,20]),0,scale,np.array([0,1,2,3]))
        self.assertEqual(idx.tolist(),[0,2])
        idx,_=nearest(x,fuels,x[0],0,scale,np.array([1,2,3]))
        self.assertEqual(idx.tolist(),[2])
        with self.assertRaises(ValueError):nearest(x,fuels,x[0],2,scale,np.arange(4))


@unittest.skipUnless((ROOT/'prepared.npz').exists(),'SPICE data not prepared')
class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=np.load(ROOT/'prepared.npz');cls.m=json.loads((ROOT/'manifest.json').read_text())

    def test_no_group_or_condition_leakage(self):
        groups={};conditions={}
        for r in self.m['records']:
            for mapping,key in [(groups,r['group']),(conditions,(r['fuel'],*map(lambda v:round(v,6),r['features'])))]:
                if key in mapping:self.assertEqual(mapping[key],r['split'])
                mapping[key]=r['split']
        self.assertEqual(set(self.d['splits']),{'train','validation','test'})
        self.assertEqual(self.d['images'].shape[1:],(256,256,3))
        self.assertEqual(FIELDS,['nozzle_mm','fuel_sccm','air_cm_s'])

    def test_original_image_and_condition_joins(self):
        for i,r in enumerate(self.m['records']):
            with zipfile.ZipFile(SOURCE/r['archive']) as z:raw=z.read(r['member'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(),r['image_sha256'])
            self.assertEqual(r['member'].split('/')[-1].split('.')[0].upper(),r['id'])
            np.testing.assert_allclose(self.d['features'][i],[r['original_row'][j] for j in [9,17,20]],rtol=1e-6)
            idx,dist=nearest(self.d['features'],self.d['fuels'],self.d['features'][i],self.d['fuels'][i],np.ones(3),np.arange(len(self.d['images'])))
            self.assertAlmostEqual(float(dist[0]),0.)


@unittest.skipUnless((ART/'selected.pt').exists(),'SPICE checkpoint not trained')
class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from spice_lab import create_app
        cls.client=create_app().test_client();cls.info=cls.client.get('/spice/api/info').get_json()

    def test_prediction_and_training_library(self):
        example=self.info['examples'][0]
        response=self.client.get('/spice/api/predict',query_string=dict(fuel=example['fuel'],library='train',**example['features']))
        self.assertEqual(response.status_code,200);r=response.get_json()
        import base64
        self.assertEqual(Image.open(BytesIO(base64.b64decode(r['prediction'].split(',')[1]))).size,(256,256))
        self.assertTrue(all(m['split']=='train' for m in r['matches']))
        source=self.client.get(r['matches'][0]['original_url'])
        self.assertEqual(source.status_code,200)
        self.assertEqual(Image.open(BytesIO(source.data)).size,(3008,2000))

    def test_invalid_inputs(self):
        for query in ['fuel_sccm=nan','air_cm_s=inf','nozzle_mm=0','fuel=missing','library=test','video_time=1','fuel_sccm=1&fuel_sccm=2']:
            self.assertEqual(self.client.get('/spice/api/predict?'+query).status_code,400,query)
        self.assertEqual(self.client.get('/spice/api/source/missing').status_code,404)

    def test_predictions_depend_on_flow_features(self):
        import base64
        fuel=next(f for f in self.info['fuels'] if f['name']=='Ethylene')
        defaults={f['key']:f['default'] for f in fuel['fields']}
        for field in fuel['fields']:
            if field['key']=='nozzle_mm' or field['min']==field['max']:continue
            images=[]
            for value in [field['min'],field['max']]:
                query=dict(fuel=fuel['name'],**defaults);query[field['key']]=value
                response=self.client.get('/spice/api/predict',query_string=query)
                self.assertEqual(response.status_code,200)
                raw=base64.b64decode(response.get_json()['prediction'].split(',')[1])
                images.append(np.array(Image.open(BytesIO(raw))).astype(float))
            self.assertGreater(np.abs(images[0]-images[1]).max(),5,field['key'])


if __name__=='__main__':unittest.main()
