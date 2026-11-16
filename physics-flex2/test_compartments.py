import copy
import unittest
from compartments import default_environment, simulate_dimensioned, dimensions

class DimensionedTests(unittest.TestCase):
    def pair(self):
        q=default_environment();q['rooms']=q['rooms'][:2];q['source']=0
        q['edges']=[dict(a=0,b=1,open=True,length_m=4,width_m=1.2)]
        q['duration_s']=1800
        return q
    def test_default_no_seconds_scale_cascade(self):
        r=simulate_dimensioned(default_environment())
        times=[t for t in r['ignition_times_s'].values() if t not in (None,0)]
        self.assertTrue(times);self.assertGreater(min(times),60)
        self.assertEqual(len(r['frames']),241)
        self.assertLessEqual(r['diagnostics']['released_energy_kj'],r['diagnostics']['initial_fuel_energy_kj']+1e-6)
        self.assertLessEqual(r['diagnostics']['transferred_energy_kj'],r['diagnostics']['released_energy_kj']+1e-6)
    def test_dimensions_and_length_affect_spread(self):
        q=self.pair();a=simulate_dimensioned(q)['ignition_times_s']['R2'];self.assertIsNotNone(a)
        q['rooms'][1].update(width_m=12,length_m=12,height_m=5)
        b=simulate_dimensioned(q)['ignition_times_s']['R2'];self.assertTrue(b is None or b>a)
        q=self.pair();q['edges'][0]['length_m']=90
        b=simulate_dimensioned(q)['ignition_times_s']['R2'];self.assertTrue(b is None or b>a)
    def test_closed_hall_and_inert_room(self):
        q=self.pair();q['edges'][0]['open']=False
        r=simulate_dimensioned(q);self.assertIsNone(r['ignition_times_s']['R2'])
        self.assertEqual(r['ignition_intervals']['R2']['scenarios_reached'],0)
        q=self.pair();q['rooms'][1]['fuel']=False
        self.assertIsNone(simulate_dimensioned(q)['ignition_times_s']['R2'])
    def test_envelope_and_censoring(self):
        r=simulate_dimensioned(default_environment());self.assertFalse(r['uncertainty']['calibrated']);self.assertIsNone(r['uncertainty']['confidence_level'])
        for f in r['frames']:
            for s in f['rooms']:
                self.assertLessEqual(s['temperature_lower_c'],s['temperature_c']);self.assertLessEqual(s['temperature_c'],s['temperature_upper_c'])
        for interval in r['ignition_intervals'].values():
            if interval['not_reached_in_some_scenarios']:self.assertIsNone(interval['latest_s'])
    def test_droplet_size_and_K_drive_scaled_burn_history(self):
        a=simulate_dimensioned(self.pair(),{'initial_diameter_mm':.8,'k_mm2_s':.8})
        b=simulate_dimensioned(self.pair(),{'initial_diameter_mm':1.6,'k_mm2_s':.8})
        self.assertAlmostEqual(b['diagnostics']['scaled_burn_duration_s']/a['diagnostics']['scaled_burn_duration_s'],4.)
        self.assertNotEqual(a['frames'],b['frames'])
        c=simulate_dimensioned(self.pair(),{'initial_diameter_mm':.8,'k_mm2_s':1.6})
        self.assertAlmostEqual(c['diagnostics']['scaled_burn_duration_s'],a['diagnostics']['scaled_burn_duration_s']/2.)
    def test_validation_and_determinism(self):
        q=self.pair();self.assertEqual(simulate_dimensioned(q),simulate_dimensioned(copy.deepcopy(q)))
        for field,val in [('width_m',0),('length_m',float('nan')),('height_m',7)]:
            q=self.pair();q['rooms'][1][field]=val
            with self.assertRaises(ValueError):dimensions(q)
        q=self.pair();q['edges'][0]['length_m']=-1
        with self.assertRaises(ValueError):dimensions(q)
if __name__=='__main__':unittest.main()
