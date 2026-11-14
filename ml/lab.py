"""Local feature-to-image CNN lab: http://127.0.0.1:5050."""
import base64
from io import BytesIO
import json
import math

import numpy as np
from PIL import Image
import torch
from flask import Flask, jsonify, render_template, request

from flame import DATA
from conditional import load_model


def png(array):
    buffer=BytesIO()
    Image.fromarray(np.uint8(np.clip(array,0,1)*255)).save(buffer,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode()


def create_app():
    app=Flask(__name__);torch.set_num_threads(2)
    net,saved=load_model()
    manifest=json.loads((DATA/'conditional-manifest.json').read_text())
    data=np.load(DATA/'conditional.npz')
    defaults=[round(float(v),6) for v in data['features'][0]]
    specs=[dict(f,min=round(f['min'],6),max=round(f['max'],6)) for f in saved['features']]

    @app.get('/')
    def index():
        return render_template('lab.html')

    @app.get('/api/info')
    def info():
        return jsonify(features=[dict(f,default=defaults[i]) for i,f in enumerate(specs)],
            metrics=saved['metrics'],trials=manifest,
            fixed={'initial_oxygen_percent':22.2,'width_cm':2,'flow_restrictor':2},
            unsupported=['pressure','calibrated airflow (m/s)','gravity variation','temperature','humidity','fuel category'])

    @app.get('/api/predict')
    def predict():
        values=[]
        try:
            for i,f in enumerate(specs):
                value=float(request.args.get(f['key'],defaults[i]))
                if not math.isfinite(value) or not f['min']<=value<=f['max']:
                    raise ValueError(f"{f['label']} must be between {f['min']:g} and {f['max']:g}")
                values.append(value)
        except (ValueError,OverflowError) as error:
            return jsonify(error=str(error)),400
        unknown=set(request.args)-{f['key'] for f in specs}
        if unknown:
            return jsonify(error='Unsupported features: '+', '.join(sorted(unknown))),400
        features=torch.tensor([values],dtype=torch.float32)
        with torch.inference_mode():
            output=net((features-saved['low'])/saved['scale'])[0]
        # Provide source evidence separately; it is not fed into the network.
        distances=(((data['features']-np.array(values))/saved['scale'].numpy())**2).mean(1)
        nearest=int(np.argmin(distances))
        nearest_trial=str(data['groups'][nearest])
        return jsonify(prediction=png(output.permute(1,2,0).numpy()),
            reference=png(data['images'][nearest].astype('float32')/255),
            reference_trial=nearest_trial,reference_features=data['features'][nearest].tolist(),
            normalized_distance=float(np.sqrt(distances[nearest])),
            exact_documented_sample=bool(distances[nearest]<1e-8),
            warning='Illustrative CNN output. Four training trials cannot establish independent physical effects. '
                    'Within-range combinations can still be unsupported. Fan/air values are display readings, not m/s.')

    return app


if __name__=='__main__':
    create_app().run(host='127.0.0.1',port=5050,debug=False)
