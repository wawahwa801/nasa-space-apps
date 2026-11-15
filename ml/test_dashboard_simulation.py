"""Exercise published hybrid inference through the room-simulation boundary."""
import unittest
from dashboard_simulation import build_app

class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = build_app().test_client()
        run = cls.client.get('/api/runs').get_json()['runs'][0]
        cls.query = dict(controls=dict(run=run['id'], **run['values']),
                         mm_per_pixel=.03, k_mm2_s=.8, source=3)

    def test_real_prediction_reaches_room_solver(self):
        response = self.client.post('/api/simulate', json=self.query)
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        burn = result['simulation']['burn_model']
        self.assertAlmostEqual(burn['initial_diameter_mm'], burn['diameter_px'] * .03)
        self.assertEqual(burn['controls'], self.query['controls'])
        self.assertEqual(result['simulation']['frames'][0]['rooms'][3]['state'], 'burning')
        self.assertGreater(len(result['simulation']['frames']), 1)

    def test_invalid_scale_rejected(self):
        response = self.client.post('/api/simulate', json=dict(self.query, mm_per_pixel=0))
        self.assertEqual(response.status_code, 400)

    def test_unsupported_controls_rejected(self):
        query = dict(self.query, controls=dict(self.query['controls'], unsupported=7))
        self.assertEqual(self.client.post('/api/simulate', json=query).status_code, 400)
