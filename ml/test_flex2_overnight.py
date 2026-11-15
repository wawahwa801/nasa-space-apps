"""Leakage and feature-join checks for the monitored overnight runner."""
import unittest
import numpy as np

from flex2_data import ROOT
from flex2_overnight import load_verified


@unittest.skipUnless((ROOT/'prepared.npz').exists(), 'published FLEX-2 library unavailable')
class OvernightInputTests(unittest.TestCase):
    def test_verified_features_and_references_are_run_disjoint(self):
        data,manifest,features,references,_=load_verified()
        self.assertEqual(features.shape,(99,5))
        self.assertEqual(data['excluded_unverified_settings_ids'],['E183L11'])
        train=np.where(data['splits']=='train')[0]
        for i,ref in enumerate(references):
            self.assertIn(ref,train)
            self.assertNotEqual(data['groups'][i],data['groups'][ref])
        self.assertTrue(np.isfinite(features).all())

if __name__=='__main__':unittest.main()
