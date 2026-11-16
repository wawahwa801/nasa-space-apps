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
from compartments import default_environment, dimensions, simulate_dimensioned
from model import number


def build_app():
    root = Path(__file__).resolve().parent
    app = create_app(root / 'data/flex2-geometry-model', texture=True)
    app.config['MAX_CONTENT_LENGTH'] = 16000
    @app.get('/api/environment')
    def environment():
        return jsonify(default_environment())

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
            scenario = default_environment()
            if 'environment' in q:
                custom = q['environment']
                if not isinstance(custom, dict) or set(custom) - {'rooms', 'edges', 'duration_s'}:
                    raise ValueError('Environment must contain rooms, edges and optional duration_s')
                scenario.update(rooms=custom['rooms'], edges=custom['edges'], duration_s=custom.get('duration_s',1200))
            scenario.update(source=source, k_mm2_s=k)
            scenario=dimensions(scenario)
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
            size = number(pixels * scale, 'Visual diameter', .000001, 10000)
            burn = dict(initial_diameter_mm=size, legacy_k_mm2_s_ignored=k, mode='visual_mask_provenance',
                        controls=controls, diameter_px=pixels, assumed_mm_per_pixel=scale,
                        warning='Uncalibrated image diameter only; it does not set compartment heat release or ignition timing.')
            simulation = simulate_dimensioned(scenario, image_provenance=burn)
            return jsonify(prediction=result, simulation=simulation)
        except (ValueError, KeyError, TypeError) as exc:
            return jsonify(error=str(exc)), 400
    return app

if __name__ == '__main__':
    build_app().run(host='127.0.0.1', port=5055, debug=False)
