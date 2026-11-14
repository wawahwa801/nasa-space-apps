"""Local domain-aware, condition-only multi-source flame CNN lab."""
import base64
from io import BytesIO
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
import torch
from flask import Flask,jsonify,render_template,request
from jinja2 import DictLoader

from flame import DATA
from multi_model import load_model,encode
from multisource_data import FIELDS,SOURCE_IDS

NAMES={'PSI-25':'BASS-II · solid films','PSI-98':'SAFFIRE-I · fabric',
       'PSI-100':'SAFFIRE-III · fabric','PSI-107':'SPICE · gas jet (separate domain)'}


def png(array):
    buffer=BytesIO();Image.fromarray(np.uint8(np.clip(array,0,1)*255)).save(buffer,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode()


def create_app():
    app=Flask(__name__);torch.set_num_threads(2)
    app.jinja_loader=DictLoader({'lab.html':(Path(__file__).resolve().parent/'templates'/'lab.html').read_text()})
    net,saved=load_model()
    manifest=json.loads((DATA/'multi-manifest.json').read_text())
    images=np.load(DATA/'multi-images.npz')['images']
    experiments={e['run']:e for e in manifest['experiments']}
    records=manifest['records']
    specifications={}
    for source in SOURCE_IDS:
        entries=[e for e in experiments.values() if e['source']==source and e['split']=='train']
        specs=[]
        for key,label,unit in FIELDS:
            values=[e['features'][key] for e in entries if e['features'][key] is not None]
            specs.append(dict(key=key,label=label,unit=unit,min=min(values) if values else None,
                              max=max(values) if values else None))
        specifications[source]=specs

    @app.get('/')
    def index():return render_template('lab.html')

    @app.get('/api/info')
    def info():return jsonify(sources=[dict(id=s,label=NAMES[s],features=specifications[s]) for s in SOURCE_IDS],
        experiments=list(experiments.values()),metrics=saved['metrics'],time_is_input=False,
        unsupported=['humidity','temperature','variable gravity','pressure effects outside SPICE'])

    @app.get('/api/predict')
    def predict():
        source=request.args.get('source','PSI-25')
        if source not in SOURCE_IDS:return jsonify(error='Unknown source'),400
        run=request.args.get('run',next(e['run'] for e in experiments.values() if e['source']==source))
        if run not in experiments or experiments[run]['source']!=source:return jsonify(error='Unknown source/trial combination'),400
        allowed={'source','run'}|{f['key'] for f in specifications[source]}
        if set(request.args)-allowed:return jsonify(error='Unsupported input; time and image inputs have been removed'),400
        record=dict(experiments[run]);values=dict(record['features']);warnings=[]
        try:
            for spec in specifications[source]:
                key=spec['key']
                if key not in request.args:continue
                if values[key] is None:raise ValueError(spec['label']+' is undocumented for this trial')
                value=float(request.args[key])
                if not math.isfinite(value) or spec['min'] is None or not spec['min']-1e-7<=value<=spec['max']+1e-7:
                    raise ValueError(spec['label']+' must be within the observed training range for this source')
                values[key]=value
            for low,high in [('oxygen_low','oxygen_high'),('fuel_low','fuel_high')]:
                if values[low] is not None and values[low]>values[high]:raise ValueError('Lower bound must not exceed upper bound')
        except (ValueError,OverflowError) as error:return jsonify(error=str(error)),400
        record['features']=values
        with torch.inference_mode():prediction=net(encode([record],saved['schema']))[0].permute(1,2,0).numpy()
        candidates=[(i,r) for i,r in enumerate(records) if r['source']==source and r['material']==record['material']]
        def distance(item):
            _,r=item;total=0.
            for j,(key,_,_) in enumerate(FIELDS):
                a,b=values[key],r['features'][key]
                if a is not None and b is not None:total+=((a-b)/saved['schema']['scale'][j])**2
            return total
        index,nearest=min(candidates,key=distance)
        exact=distance((index,nearest))<1e-10
        return jsonify(prediction=png(prediction),reference=png(images[index].astype('float32')/255),
            source=source,material=record['material'],features=values,reference_trial=nearest['experiment'],
            reference_features=nearest['features'],reference_location={k:nearest.get(k) for k in ['file','member','video_time_seconds','source_frame','source_timestamp_ms']},
            exact_documented_conditions=bool(exact),warning='Illustrative typical appearance; not a specific frame or calibrated fire prediction. '
                'New combinations may be unsupported even within observed bounds. Source/camera differences remain.')
    return app


if __name__=='__main__':create_app().run(host='127.0.0.1',port=5050,debug=False)
