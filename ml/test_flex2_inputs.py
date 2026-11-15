"""Keep unsupported commands, joins and missingness out of physical model labels."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from flex2_inputs import setting_values, reported_gas, EVIDENCE


class InputEvidenceTests(unittest.TestCase):
    def test_corrupted_source_cannot_be_reported_as_verified(self):
        from flex2_inputs import audit
        with TemporaryDirectory() as folder:
            root=Path(folder);(root/'R1').mkdir()
            (root/'manifest.json').write_text(json.dumps(dict(records=[])))
            (root/'R1'/'settings.txt').write_text('corrupted')
            (root/'input-metadata-search.json').write_text(json.dumps([dict(run='R1',file='settings.txt',sha256='0'*64)]))
            with patch('flex2_inputs.ROOT',root):
                with self.assertRaisesRegex(ValueError,'Metadata checksum mismatch'):audit()

    def test_wrong_run_and_placeholder_settings_are_rejected(self):
        text='TEST_POINT_DESIGNATOR(N/A),TP_PARAMETER_FIBER_USAGE_FLAG(N/A),TP_PARAMETER_IGNITER_WATTAGE(Watts),FLOW_NOZZLE_1_SPEED(N/A)\n0,0,0,42\n'
        result=setting_values('E183L11',text)
        self.assertEqual(result['status'],'rejected_run_id')
        self.assertIsNone(result['fiber_usage_flag']);self.assertIsNone(result['igniter_power_setting_w'])

    def test_units_and_command_semantics_are_preserved(self):
        text='TEST_POINT_DESIGNATOR(N/A),TP_PARAMETER_FIBER_USAGE_FLAG(N/A),TP_PARAMETER_IGNITER_WATTAGE(Watts),FLOW_NOZZLE_1_SPEED(N/A)\nA109D04,No,11.98,42\n'
        result=setting_values('A109D04',text)
        self.assertIs(result['fiber_usage_flag'],False)
        self.assertEqual(result['igniter_power_setting_w'],11.98)
        self.assertEqual(result['flow_nozzle_setting'],'42')
        self.assertNotIn('flow_m_s',result)

    def test_publication_join_requires_exact_run_and_consistent_fuel(self):
        evidence=json.loads(EVIDENCE.read_text())
        result=reported_gas(dict(run='E073C02',fuel='Heptane'),evidence)
        self.assertEqual(result['oxygen_mole_fraction'],.21)
        self.assertEqual(result['nitrogen_mole_fraction'],.79)
        self.assertIsNone(result['uncertainty'])
        for record in [dict(run='E073C02',fuel='Decane'),dict(run='E073C02-extra',fuel='Heptane'),dict(run='E135F02',fuel='N_Octane')]:
            self.assertIsNone(reported_gas(record,evidence)['oxygen_mole_fraction'])

    def test_generated_table_preserves_missingness_and_evidence(self):
        path=Path(__file__).parent/'reports'/'flex2-input-coverage.json'
        report=json.loads(path.read_text());records=report['records']
        self.assertEqual(len(records),100)
        self.assertEqual(len({r['run_id'] for r in records}),100)
        self.assertTrue(all(r['flow_m_s'] is None and r['initial_diameter_mm'] is None for r in records))
        self.assertEqual(sum(r['oxygen_mole_fraction'] is not None for r in records),10)
        self.assertEqual(sum(r['fiber_usage_flag'] is not None for r in records),99)
        self.assertTrue(all(r['gas_source'] for r in records if r['oxygen_mole_fraction'] is not None))


if __name__=='__main__':unittest.main()
