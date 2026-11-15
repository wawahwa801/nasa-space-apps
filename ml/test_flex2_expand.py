"""Verify expanded targets preserve independent groups and original holdouts."""
import unittest
import numpy as np

from flex2_data import ROOT
from flex2_data import file_tree
from flex2_discovery import DISCOVERY_CATEGORIES

EXPANDED=ROOT.parent/'flex2-expanded'


@unittest.skipUnless((EXPANDED/'prepared.npz').exists(), 'expanded FLEX-2 targets unavailable')
class ExpansionTests(unittest.TestCase):
    def test_discovery_campaigns_exist_in_cached_PSI_inventory(self):
        categories={node.get('subcategory') for node in file_tree()}
        self.assertTrue(set(DISCOVERY_CATEGORIES).issubset(categories))

    def test_40_new_runs_are_training_only_and_holdouts_are_frozen(self):
        base=np.load(ROOT/'prepared.npz');full=np.load(EXPANDED/'prepared.npz')
        old={str(run):str(split) for run,split in zip(base['groups'],base['splits'])}
        new={str(run):str(split) for run,split in zip(full['groups'],full['splits'])}
        self.assertEqual(len(new),140)
        self.assertEqual(len(set(new)),140)
        self.assertEqual(sum(split=='train' for split in new.values()),100)
        self.assertEqual(sum(split=='validation' for split in new.values()),20)
        self.assertEqual(sum(split=='test' for split in new.values()),20)
        self.assertTrue(all(new[run]==split for run,split in old.items()))
        self.assertTrue(all(split=='train' for run,split in new.items() if run not in old))


if __name__=='__main__':unittest.main()
