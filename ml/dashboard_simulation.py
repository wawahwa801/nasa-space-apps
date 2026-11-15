"""Hybrid dashboard API: python ml/dashboard_simulation.py (port 5055)."""
import base64
import io
import sys
from pathlib import Path
import numpy as np
from PIL import Image
from flask import request, jsonify
from flex2_compare import create_app
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'physics-flex2'))
from rooms import example, simulate
from model import number


def build_app():
    root = Path(__file__).resolve().parent
    app = create_app(root / 'data/flex2-geometry-model', texture=True)
    @app.post('/api/simulate')
    def run():
        try:
            q = request.get_json()
            controls = q['controls']
            if not isinstance(controls, dict):
                raise ValueError('Expected model controls')
            scale = number(q['mm_per_pixel'], 'Assumed mm/pixel', .0001, .1)
            k = number(q['k_mm2_s'], 'Assumed K', .000001, 10)
            source = q['source']
            # Reuse the exact inference validation and model used by the live demo.
            with app.test_client() as client:
                response = client.get('/api/compare', query_string=controls)
            result = response.get_json()
            if response.status_code != 200:
                return jsonify(result), response.status_code
            mask = np.asarray(Image.open(io.BytesIO(base64.b64decode(result['mask'].split(',')[1]))).convert('L')) / 255.
            area = int(np.count_nonzero(mask >= .5))
            if area == 0:
                raise ValueError('No usable flame mask; simulation cannot start')
            pixels = 2 * (area / np.pi) ** .5
            size = number(pixels * scale, 'Assumed proxy diameter', .01, 10)
            scenario = example()
            scenario.update(source=source, k_mm2_s=k)
            burn = dict(initial_diameter_mm=size, k_mm2_s=k, mode='illustrative_cnn_flame_proxy',
                        controls=controls, diameter_px=pixels, assumed_mm_per_pixel=scale,
                        warning='Flame mask area converted to an assumed room proxy size; no liquid-droplet measurement or calibrated cabin spread.')
            simulation = simulate(scenario, burn_override=burn)
            return jsonify(prediction=result, simulation=simulation)
        except (ValueError, KeyError, TypeError) as exc:
            return jsonify(error=str(exc)), 400
    return app

if __name__ == '__main__':
    build_app().run(host='127.0.0.1', port=5055, debug=False)
