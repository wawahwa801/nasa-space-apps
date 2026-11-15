import copy
import unittest
from rooms import example, simulate


class RoomGraphTests(unittest.TestCase):
    def test_default_spread_and_finite_budget(self):
        q=example();result=simulate(q)
        times=result['ignition_times_s']
        self.assertEqual(times['R5'],0)
        self.assertTrue(all(t is not None for t in times.values()))
        self.assertGreater(times['R1'],times['R2'])
        self.assertEqual(sum(r['state']=='burning' for r in result['frames'][0]['rooms']),1)
        self.assertTrue(all(r['state']=='burned' for r in result['frames'][-1]['rooms']))
        diagnostics=result['diagnostics']
        self.assertLessEqual(diagnostics['released_proxy'],9+1e-10)
        self.assertLessEqual(diagnostics['transferred_proxy'],q['transfer_fraction']*diagnostics['released_proxy']+1e-10)
        for a,b in zip(result['frames'],result['frames'][1:]):
            self.assertGreater(b['time_s'],a['time_s'])
            self.assertTrue(all(x['remaining_fraction']>=y['remaining_fraction'] for x,y in zip(a['rooms'],b['rooms'])))

    def test_closed_doors_and_zero_coupling_block_spread(self):
        q=example();q['transfer_fraction']=0
        result=simulate(q)
        self.assertEqual(sum(t is not None for t in result['ignition_times_s'].values()),1)
        q=example()
        for edge in q['edges']:edge['open']=False
        result=simulate(q)
        self.assertEqual(sum(t is not None for t in result['ignition_times_s'].values()),1)

    def test_topology_and_inert_barrier(self):
        q=example();q['source']=0
        # Closing all edges across the middle column isolates the far column.
        for room in q['rooms']:
            if room['x']==1:room['fuel']=False
        result=simulate(q)
        self.assertTrue(all(result['ignition_times_s'][r['id']] is None for r in q['rooms'] if r['x']>0))
        self.assertTrue(all(r['state']=='inert' for r in result['frames'][-1]['rooms'] if r['id'] in ['R2','R5','R8']))

    def test_engine_parameter_response_and_determinism(self):
        q=example();first=simulate(q)
        self.assertEqual(first,simulate(copy.deepcopy(q)))
        q['k_mm2_s']=.4
        slower=simulate(q)
        self.assertGreater(slower['ignition_times_s']['R2'],first['ignition_times_s']['R2'])
        self.assertGreater(slower['burn_model']['formal_zero_diameter_time_s'],first['burn_model']['formal_zero_diameter_time_s'])

    def test_input_validation(self):
        for mutate in [lambda q:q.update(source=True),lambda q:q['rooms'][4].update(fuel=False),
                       lambda q:q['edges'].append(dict(q['edges'][0])),lambda q:q.update(transfer_fraction=float('nan')),
                       lambda q:q['rooms'][1].update(x=0,y=0),lambda q:q['edges'][0].update(a=99)]:
            q=example();mutate(q)
            with self.assertRaises(ValueError):simulate(q)


if __name__=='__main__':unittest.main()
