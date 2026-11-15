"""Verify the bounded survey and its distinction between labels and opaque settings."""
import json
import unittest

from flex2_feature_sample import CATEGORIES, REPORTS, select, number


class FeatureSampleTests(unittest.TestCase):
    def test_fixed_cap_and_exclusion_of_existing_library(self):
        nodes=[]
        for j,category in enumerate(CATEGORIES):
            for i in range(6):
                run=f'{chr(65+j)}123A{i:02}'
                nodes.append(dict(key=run+'D.zip',subcategory=category,id=run,restricted=False))
        excluded={f'{chr(65+j)}123A00' for j in range(len(CATEGORIES))}
        result=select(nodes,excluded)
        self.assertEqual(len(result),48)
        self.assertFalse({r['run'] for r in result}&excluded)
        self.assertEqual(len({r['run'] for r in result}),48)
        for category in CATEGORIES:self.assertEqual(sum(r['category']==category for r in result),4)

    def test_nonfinite_and_opaque_values_are_not_physical_numbers(self):
        for value in [None,'nan','inf','N/A','Full Auto','1/4','9dB']:
            self.assertIsNone(number(value))

    def test_report_and_source_joins_preserve_scope(self):
        data=json.loads((REPORTS/'flex2-feature-sample.json').read_text())
        existing={r['run'] for r in json.loads((REPORTS/'flex2-100-data.json').read_text())['records']}
        self.assertEqual(data['sample']['runs'],48)
        self.assertFalse(data['sample']['statistical_significance_tested'])
        self.assertFalse({r['run'] for r in data['records']}&existing)
        self.assertTrue(all('oxygen_mole_fraction' not in r['features'] for r in data['records']))
        for r in data['records']:
            if not r['settings_run_verified']:self.assertNotIn('fiber_usage',r['features'])
            if r['reported_gas_condition']:
                self.assertEqual(r['catalog_fuel'],'Heptane')
                self.assertEqual(r['reported_gas_condition']['oxygen_mole_fraction'],.21)
            self.assertNotIn('flow_m_s',r['features'])
            self.assertNotIn('initial_diameter_mm',r['features'])


if __name__=='__main__':unittest.main()
