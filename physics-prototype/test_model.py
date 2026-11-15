import copy
import unittest
from model import example, simulate, validate, ensemble

class PhysicsTests(unittest.TestCase):
    def test_energy_balance(self):
        r=simulate(example());d=r['diagnostics'];self.assertAlmostEqual(d['balance_residual_j'],0,places=5)
        self.assertLessEqual(d['captured_j'],d['combustion_j']*.8)
    def test_equilibrium(self):
        s=example();s['source_w']=0;r=simulate(s)
        self.assertTrue(all(t==s['ambient_k'] for t in r['frames'][-1]['temperature_k']))
    def test_heat_without_losses(self):
        s=example();s['patches']=s['patches'][:1];s['source_index']=0;s['duration']=2;s['h']=0;p=s['patches'][0];p.update(emissivity=0,conductivity=0,fuel=False)
        r=simulate(s);c=p['area']*p['thickness']*p['density']*p['cp'];self.assertAlmostEqual(r['frames'][-1]['temperature_k'][0],s['ambient_k']+800/c,places=6)
    def test_oxygen_cutoff(self):
        s=example();s['oxygen_percent']=0;r=simulate(s);self.assertTrue(all(t is None for t in r['ignition_seconds']))
    def test_finite_fuel(self):
        s=example();s['patches']=s['patches'][:1];s['source_index']=0;s['patches'][0]['heat_combustion']=1e6;r=simulate(s)
        self.assertGreaterEqual(min(r['remaining_fuel_kg']),0);self.assertAlmostEqual(r['remaining_fuel_kg'][0],0)
    def test_convergence(self):
        s=example();a=simulate(s);s['dt']=.025;b=simulate(s)
        self.assertLess(max(abs(x-y) for x,y in zip(a['frames'][-1]['temperature_k'],b['frames'][-1]['temperature_k'])),2)
    def test_invalid(self):
        for field,value in [('h',float('nan')),('source_index',999),('oxygen_percent',-1)]:
            s=example();s[field]=value
            with self.assertRaises(ValueError):validate(s)
    def test_material_sensitivity(self):
        s=example();a=simulate(s);s['patches'][10]['cp']*=2;b=simulate(s)
        self.assertGreater(b['ignition_seconds'][10],a['ignition_seconds'][10])
    def test_ensemble(self):
        r=ensemble(example());self.assertLess(r['cases']['high']['ignition_seconds'][10],r['cases']['low']['ignition_seconds'][10])
    def test_adaptive_step_budget(self):
        s=example();s.update(duration=600,dt=.1,h=50,source_w=0,source_seconds=0,capture_fraction=0)
        s['patches']=[dict(s['patches'][0],x=x,y=y,area=.001,thickness=.0001,density=50,cp=100,
            conductivity=0,emissivity=0,fuel=False) for y in range(6) for x in range(10)]
        s['source_index']=0
        with self.assertRaisesRegex(ValueError,'computation budget'):
            simulate(s)
if __name__=='__main__':unittest.main()
