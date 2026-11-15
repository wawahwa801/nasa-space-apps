import csv
import math
from pathlib import Path
import tempfile
import unittest
from model import CONFLICTS, diameter, fit, predict, records, trajectory


class PhysicsTests(unittest.TestCase):
    def test_physical_boundary_and_volume(self):
        frames = trajectory(2, .5, 10, .3)
        self.assertEqual(frames[0]['diameter_mm'], 2)
        self.assertEqual(frames[-1]['diameter_mm'], 0)
        self.assertEqual(frames[-1]['time_s'], 10)
        self.assertTrue(all(a['relative_volume'] >= b['relative_volume'] for a,b in zip(frames, frames[1:])))
        self.assertAlmostEqual(trajectory(2,.5,4,1)[-1]['diameter_mm'], math.sqrt(2))

    def test_calibration_and_numeric_rejection(self):
        obs = dict(diameter_px=100, mm_per_pixel=.03, calibration_source='fixture', image_kind='cnn_estimate')
        self.assertEqual(diameter(obs), 3)
        for value in [True, float('nan'), float('inf'), -1, 0]:
            with self.assertRaises(ValueError):
                diameter(dict(obs, mm_per_pixel=value))
        with self.assertRaises(ValueError):
            diameter(dict(obs, calibration_source=''))
        with self.assertRaises(ValueError):
            trajectory(3,.8,600,.01)

    def test_provenance_and_assumptions(self):
        rs = records()
        self.assertEqual(len(rs),99)
        self.assertNotIn('E183L11', {r['id'] for r in rs})
        run = next(r for r in rs if not r['fuel_conflict'])
        q = dict(run_id=run['id'], observation=dict(diameter_px=100, mm_per_pixel=.03, calibration_source='fixture', image_kind='cnn_estimate'))
        result = predict(q)
        self.assertEqual(result['mode'],'assumed_coefficient')
        self.assertEqual(result['gas_status'],'user_assumed')
        self.assertEqual(result['run']['features'],run['features'])
        with self.assertRaises(ValueError):
            predict(dict(q,run_id=next(iter(CONFLICTS))))

    def fixture(self, folder, source='measured_backlit', oxygen=.22):
        # Synthetic trajectories only: checks fitting/leakage, never experimental accuracy.
        rs=records()
        train=next(r for r in rs if r['split']=='train' and r['fuel']=='Decane')
        test=next(r for r in rs if r['split']=='test' and r['fuel']=='Decane' and r['apparatus']['fiber_usage_flag']==train['apparatus']['fiber_usage_flag'])
        path=Path(folder)/'synthetic.csv'
        with path.open('w',newline='') as f:
            w=csv.writer(f)
            w.writerow(['run_id','time_s','diameter_mm','measurement_source','source_file','calibration_source','oxygen_mole_fraction','nitrogen_mole_fraction'])
            for r,k in [(train,.5),(test,1.)]:
                for t in [0,1,2]:
                    w.writerow([r['id'],t,math.sqrt(9-k*t),source,'synthetic-test-only','synthetic-test-only',oxygen,1-oxygen])
        return path,train,test

    def test_fit_and_held_out_run_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            path,train,test=self.fixture(folder)
            model=fit(path)
            self.assertEqual([r['run_id'] for r in model['training_runs']],[train['id']])
            self.assertAlmostEqual(model['training_runs'][0]['k_mm2_s'],.5)
            self.assertEqual(model['held_out'][0]['reference_run'],train['id'])
            self.assertGreater(model['held_out'][0]['diameter_rmse_mm'],0)
            q=dict(run_id=test['id'], observation=dict(diameter_px=100,mm_per_pixel=.03,calibration_source='synthetic',image_kind='cnn_estimate'))
            self.assertAlmostEqual(predict(q,model)['k_mm2_s'],.5)
            with self.assertRaises(ValueError):
                predict(dict(q,run_id=train['id']),model)  # self reference forbidden

    def test_generated_targets_and_composition_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path,_,_=self.fixture(folder,source='cnn_estimate')
            with self.assertRaises(ValueError): fit(path)
            path,_,_=self.fixture(folder,oxygen=.21)
            with self.assertRaises(ValueError): fit(path)


if __name__=='__main__': unittest.main()
