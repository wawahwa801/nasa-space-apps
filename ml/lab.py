"""Local CNN testing UI: python ml/lab.py (http://127.0.0.1:5050)."""
import base64
from io import BytesIO
import json
import math

import numpy as np
from PIL import Image
import torch
from flask import Flask, jsonify, render_template, request

from flame import DATA, OUT, load, model


def png(array):
    buffer = BytesIO()
    Image.fromarray(np.uint8(np.clip(array, 0, 1) * 255)).save(buffer, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()


def create_app(run_id='bass-b1'):
    app = Flask(__name__)
    torch.set_num_threads(2)
    net = model()
    net.load_state_dict(torch.load(OUT / 'tiny.pt', map_location='cpu', weights_only=True))
    net.eval()
    frames = load(run_id)
    provenance = json.loads((DATA / run_id / 'provenance.json').read_text())
    metrics = json.loads((OUT / 'metrics.json').read_text())
    if metrics.get('train_run') != run_id:
        raise ValueError('Checkpoint/run mismatch: train with --run-id ' + run_id)

    @app.get('/')
    def index():
        return render_template('lab.html')

    @app.get('/api/info')
    def info():
        return jsonify(run_id=run_id, frames=len(frames), metrics=metrics,
                       provenance=provenance, max_index=len(frames)-2)

    @app.get('/api/predict')
    def predict():
        def number(name, default, low, high, integer=False):
            value = float(request.args.get(name, default))
            if not math.isfinite(value) or not low <= value <= high or (integer and not value.is_integer()):
                raise ValueError(f'{name} must be between {low} and {high}')
            return int(value) if integer else value
        try:
            frame = number('frame', 0, 0, len(frames)-2, True)
            exposure = number('exposure', 1, .5, 1.5)
            contrast = number('contrast', 1, .5, 1.5)
            steps = number('steps', 1, 1, 8, True)
        except (ValueError, OverflowError) as error:
            return jsonify(error=str(error)), 400
        source = frames[frame]
        adjusted = ((source - .5) * contrast + .5).mul(exposure).clamp(0, 1)
        with torch.inference_mode():
            output = adjusted.unsqueeze(0)
            for _ in range(steps):
                output = net(output)
        result = output[0]
        def image(tensor):
            return png(tensor.permute(1, 2, 0).numpy())
        timestamps = provenance['timestamps_seconds']
        horizon = (timestamps[frame+1] - timestamps[frame]) * steps
        return jsonify(input=image(adjusted), prediction=image(result),
                       actual=image(frames[frame+1]), time_seconds=timestamps[frame],
                       horizon_seconds=horizon,
                       change_mse=torch.mean((result-adjusted)**2).item(),
                       actual_comparable=exposure == 1 and contrast == 1 and steps == 1)

    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=5050, debug=False)
