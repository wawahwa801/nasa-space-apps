import copy
import unittest
from rooms import example, simulate


class RoomGraphTests(unittest.TestCase):
    def test_default_spread_and_finite_budget(self):
        q=example();result=simulate(q)
        times=result['ignition_times_s']
        self.assertEqual(times[q['rooms'][q['source']]['id']],0)
        self.assertTrue(all(t is not None for t in times.values()))
        self.assertGreater(times['R1'],times['R2'])
        self.assertEqual(sum(r['state']=='burning' for r in result['frames'][0]['rooms']),1)
        self.assertTrue(all(r['state']=='burned' for r in result['frames'][-1]['rooms']))
        diagnostics=result['diagnostics']
        self.assertLessEqual(diagnostics['released_proxy'],len(q['rooms'])+1e-10)
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
        q=example()
        # The science-wing entry is an articulation edge: isolate its three modules.
        for edge in q['edges']:
            if {edge['a'],edge['b']} == {4,5}:edge['open']=False
        result=simulate(q)
        self.assertTrue(all(result['ignition_times_s'][q['rooms'][i]['id']] is None for i in [5,6,15]))
        q=example();q['rooms'][5]['fuel']=False
        result=simulate(q)
        self.assertEqual(result['frames'][-1]['rooms'][5]['state'],'inert')
        self.assertTrue(all(result['ignition_times_s'][q['rooms'][i]['id']] is None for i in [6,15]))

    def test_branching_loops_and_source_selection(self):
        q=example()
        self.assertEqual(len(q['rooms']),16)
        self.assertEqual(len(q['edges']),17)
        self.assertEqual(len({(r['x'],r['y']) for r in q['rooms']}),16)
        self.assertGreaterEqual(max(sum(i in (e['a'],e['b']) for e in q['edges']) for i in range(16)),4)
        # The crew branch has an alternate route through Command.
        for edge in q['edges']:
            if {edge['a'],edge['b']}=={2,9}:edge['open']=False
        self.assertIsNotNone(simulate(q)['ignition_times_s']['R10'])
        for source in range(16):
            q=example();q['source']=source;result=simulate(q)
            states=result['frames'][0]['rooms']
            self.assertEqual([i for i,r in enumerate(states) if r['state']=='burning'],[source])
            self.assertEqual(result['ignition_times_s'][q['rooms'][source]['id']],0)

    def test_engine_parameter_response_and_determinism(self):
        q=example();first=simulate(q)
        self.assertEqual(first,simulate(copy.deepcopy(q)))
        q['k_mm2_s']=.4
        slower=simulate(q)
        self.assertGreater(slower['ignition_times_s']['R2'],first['ignition_times_s']['R2'])
        self.assertGreater(slower['burn_model']['formal_zero_diameter_time_s'],first['burn_model']['formal_zero_diameter_time_s'])

    def test_input_validation(self):
        for mutate in [lambda q:q.update(source=True),lambda q:q['rooms'][q['source']].update(fuel=False),
                       lambda q:q['edges'].append(dict(q['edges'][0])),lambda q:q.update(transfer_fraction=float('nan')),
                       lambda q:q['rooms'][1].update(x=0,y=2),lambda q:q['edges'][0].update(a=99)]:
            q=example();mutate(q)
            with self.assertRaises(ValueError):simulate(q)


if __name__=='__main__':unittest.main()
