"""Verify FLEX-2 joins, telemetry timing, trial splits and mode-aware API."""
from io import BytesIO
import base64
import hashlib
import json
import unittest

import numpy as np
from PIL import Image

from flex2_data import ROOT, ART, OFFSETS, stamp, rows, FIELDS
from flex2_model import nearest
from flame_display import centre_flame


class DisplayTests(unittest.TestCase):
    def test_translation_centres_signal_without_resizing_or_recolouring(self):
        import cv2
        image=np.zeros((256,256,3),dtype='uint8')
        cv2.circle(image,(70,85),35,(25,80,170),-1)
        # Smaller peripheral reflection should not determine the centre.
        cv2.circle(image,(210,235),7,(250,250,250),-1)
        result,alignment=centre_flame(image)
        self.assertTrue(alignment['found'])
        x,y,w,h=alignment['source_bounds'];dx,dy=alignment['shift_pixels']
        self.assertLessEqual(abs(x+(w-1)/2+dx-127.5),.5)
        self.assertLessEqual(abs(y+(h-1)/2+dy-127.5),.5)
        before=np.all(image==[25,80,170],axis=2);after=np.all(result==[25,80,170],axis=2)
        self.assertEqual(before.sum(),after.sum())
        # Translation can clip peripheral background, but cannot invent colours.
        self.assertTrue(set(map(tuple,np.unique(result.reshape(-1,3),axis=0)))<=set(map(tuple,np.unique(image.reshape(-1,3),axis=0))))

    def test_empty_signal_is_retained(self):
        image=np.zeros((256,256,3),dtype='uint8');result,alignment=centre_flame(image)
        self.assertFalse(alignment['found']);np.testing.assert_array_equal(result,image)


class RetrievalTests(unittest.TestCase):
    def test_numeric_features_and_fuel_filter(self):
        x=np.array([[100.,20.],[200.,20.],[100.,30.]])
        idx,dist=nearest(x,np.array([0,0,1]),np.array([195.,20.]),0,np.array([100.,10.]),np.arange(3))
        self.assertEqual(idx.tolist(),[1,0]);self.assertLess(dist[0],dist[1])
        with self.assertRaises(ValueError):nearest(x,np.array([0,0,1]),x[0],2,np.ones(2),np.arange(3))


@unittest.skipUnless((ROOT/'prepared.npz').exists(),'FLEX-2 data not prepared')
class DataTests(unittest.TestCase):
    def test_requested_count_and_finite_features(self):
        m=json.loads((ROOT/'manifest.json').read_text())
        if m.get('target_runs') is not None:
            self.assertEqual(len(m['records']),m['target_runs'])
            self.assertTrue((np.load(ROOT/'prepared.npz')['masks'].sum(axis=(1,2))>=400).all())
        self.assertTrue(np.isfinite([r['features'] for r in m['records']]).all())
        self.assertEqual(len({r['run'] for r in m['records']}),len(m['records']))

    @unittest.skipUnless((ROOT/'inventory.json').exists(),'Raw NASA acquisition inventory not downloaded')
    def test_insufficient_runs_does_not_replace_prepared_data(self):
        from flex2_data import prepare
        before=hashlib.sha256((ROOT/'prepared.npz').read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError,'usable independent runs'):
            prepare(1000000)
        self.assertEqual(hashlib.sha256((ROOT/'prepared.npz').read_bytes()).hexdigest(),before)

    @unittest.skipUnless(any(ROOT.glob('*/record.json')),'Raw NASA source members not downloaded')
    def test_join_hashes_preignition_telemetry_and_splits(self):
        d=np.load(ROOT/'prepared.npz');m=json.loads((ROOT/'manifest.json').read_text());groups={}
        self.assertEqual(m['fields'],['pressure_kpa','temperature_c'])
        for i,r in enumerate(m['records']):
            self.assertNotIn(r['run'],groups);groups[r['run']]=r['split']
            self.assertEqual(str(d['groups'][i]),r['run'])
            self.assertEqual(m['fuels'][int(d['fuels'][i])],r['fuel'])
            self.assertTrue(r['category'].endswith(r['fuel']))
            self.assertEqual([v['offset_after_retraction'] for v in r['members']],OFFSETS)
            for member in r['members']:
                raw=(ROOT/r['run']/member['file']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(),member['sha256'])
                self.assertEqual(Image.open(BytesIO(raw)).mode,'RGB')
                self.assertGreater(stamp(member['timestamp']),stamp(r['retraction']))
            from datetime import timedelta
            chamber=next(x for x in r['metadata'] if x['file'].endswith('_Chamber_Readings.txt'))
            path=ROOT/r['run']/chamber['file'];self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),chamber['sha256'])
            before=[x for x in rows(path.read_text()) if stamp(r['ignition'])-timedelta(seconds=5)<=stamp(x['FCU TimeStamp'])<stamp(r['ignition'])]
            self.assertGreaterEqual(len(before),3)
            pressure=np.mean([[float(x[f'FCU_MP_PT{k}(PSIA)']) for k in [16,17,28,29]] for x in before])*6.894757293
            temperature=np.mean([[float(x[f'FCU_MP_TM{k}(Deg C)']) for k in [1,2,3,4]] for x in before])
            np.testing.assert_allclose(d['features'][i],[pressure,temperature],rtol=1e-6)
        self.assertEqual(d['images'].shape[1:],(256,256,3))
        sets=[set(d['groups'][d['splits']==s]) for s in ['train','validation','test']]
        self.assertTrue(all(sets));self.assertFalse(sets[0]&sets[1] or sets[0]&sets[2] or sets[1]&sets[2])


class PublishedArtifactTests(unittest.TestCase):
    def test_published_runtime_pair_integrity_and_consistency(self):
        from verify_flex2_models import verify
        result=verify()
        self.assertEqual(result['runs'],100)
        self.assertEqual(result['files_verified'],4)


@unittest.skipUnless((ART/'selected.pt').exists(),'FLEX-2 checkpoint not trained')
class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from flex2_lab import create_app
        cls.c=create_app().test_client();cls.info=cls.c.get('/flex2/api/info').get_json()

    def test_all_fuels_and_recorded_examples_are_retrievable(self):
        manifest=json.loads((ROOT/'manifest.json').read_text())
        self.assertEqual(len(self.info['library']),len(manifest['records']))
        for sample in self.info['library']:
            response=self.c.get('/flex2/api/predict',query_string=dict(fuel=sample['fuel'],mode='retrieval',**sample['features']))
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.get_json()['reference']['id'],sample['id'])
        for spec in self.info['fuels']:
            values={f['key']:f['default'] for f in spec['fields']}
            response=self.c.get('/flex2/api/predict',query_string=dict(fuel=spec['name'],mode='cnn',**values))
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.get_json()['fuel'],spec['name'])

    def test_modes_and_reference_provenance(self):
        sample=self.info['library'][0];outputs=[]
        for mode in ['cnn','retrieval']:
            r=self.c.get('/flex2/api/predict',query_string=dict(fuel=sample['fuel'],mode=mode,**sample['features']))
            self.assertEqual(r.status_code,200);result=r.get_json();outputs.append(result['image'])
            self.assertEqual(result['source'],'PSI-68');self.assertEqual(result['mode'],mode)
            self.assertIn('display_alignment',result)
            image=Image.open(BytesIO(base64.b64decode(result['image'].split(',')[1])))
            self.assertEqual(image.size,(256,256));self.assertEqual(image.mode,'RGB')
            if mode=='retrieval':self.assertEqual(result['reference']['id'],sample['id'])
        self.assertNotEqual(outputs[0],outputs[1])

    def test_training_only_and_invalid_inputs(self):
        sample=self.info['library'][0]
        result=self.c.get('/flex2/api/predict',query_string=dict(fuel=sample['fuel'],mode='retrieval',library='train',**sample['features'])).get_json()
        self.assertEqual(result['reference']['split'],'train')
        for query in ['fuel=missing','mode=bad','library=test','pressure_kpa=nan','temperature_c=inf','oxygen=21','video_time=1','pressure_kpa=1&pressure_kpa=2']:
            self.assertEqual(self.c.get('/flex2/api/predict?'+query).status_code,400,query)

    def test_pressure_changes_cnn_pixels(self):
        spec=next(f for f in self.info['fuels'] if f['name']=='Decane');params={f['key']:f['default'] for f in spec['fields']}
        pressure=next(f for f in spec['fields'] if f['key']=='pressure_kpa');images=[]
        for value in [pressure['min'],pressure['max']]:
            params['pressure_kpa']=value;r=self.c.get('/flex2/api/predict',query_string=dict(fuel='Decane',**params))
            self.assertEqual(r.status_code,200);images.append(np.array(Image.open(BytesIO(base64.b64decode(r.get_json()['image'].split(',')[1])))).astype(float))
        self.assertGreater(np.abs(images[0]-images[1]).max(),5)


if __name__=='__main__':unittest.main()
