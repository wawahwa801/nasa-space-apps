"""Standalone or mounted SPICE retrieval/CNN comparison, localhost only."""
import base64
from io import BytesIO
import json
import math
from pathlib import Path
import zipfile

import numpy as np
from PIL import Image
import torch
from flask import Blueprint, Flask, jsonify, render_template_string, request, send_file

from spice_data import ROOT, SOURCE, FIELDS
from spice_model import load, encode, nearest


def png(array):
    stream=BytesIO();Image.fromarray(np.uint8(np.clip(array,0,1)*255)).save(stream,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(stream.getvalue()).decode()


def build_blueprint():
    bp=Blueprint('spice',__name__,url_prefix='/spice')
    template=(Path(__file__).resolve().parent/'templates'/'spice.html').read_text()
    torch.set_num_threads(2)
    net,saved=load();report=saved['report'];d=np.load(ROOT/'prepared.npz')
    manifest=json.loads((ROOT/'manifest.json').read_text());records=manifest['records']
    if len(records)!=len(d['images']) or report['dataset_sha256']!=__import__('hashlib').sha256((ROOT/'prepared.npz').read_bytes()).hexdigest():
        raise ValueError('SPICE dataset changed: retrain before serving')
    fuel_names=manifest['fuels'];train=np.where(d['splits']=='train')[0]
    fields=[dict(key=key,label=label,unit=unit) for key,label,unit in zip(FIELDS,
        ['Nozzle diameter','Fuel flow','Air co-flow'],['mm','sccm','cm/s'])]
    fuel_specs=[]
    for f,name in enumerate(fuel_names):
        idx=np.where(d['fuels']==f)[0];training=train[d['fuels'][train]==f]
        bounds=[dict(**spec,min=float(d['features'][idx,j].min()),max=float(d['features'][idx,j].max()),
            training_min=float(d['features'][training,j].min()),training_max=float(d['features'][training,j].max()),
            default=float(d['features'][training[0],j])) for j,spec in enumerate(fields)]
        fuel_specs.append(dict(name=name,fields=bounds,nozzles=sorted(set(d['features'][idx,0].astype(float).tolist()))))

    @bp.get('/')
    def index():return render_template_string(template)

    @bp.get('/api/info')
    def info():
        return jsonify(fuels=fuel_specs,report=report,
            examples=[dict(id=r['id'],fuel=r['fuel'],features=dict(zip(FIELDS,r['features'])),split=r['split']) for r in records],
            source_url=manifest['source_url'],preprocessing=manifest['preprocessing'])

    @bp.get('/api/predict')
    def predict():
        unknown=set(request.args)-set(FIELDS)-{'fuel','library'}
        if unknown:return jsonify(error='Unsupported input: '+', '.join(sorted(unknown))),400
        if any(len(request.args.getlist(k))!=1 for k in request.args):
            return jsonify(error='Duplicate input fields'),400
        name=request.args.get('fuel',fuel_names[0]);library=request.args.get('library','catalog')
        if name not in fuel_names or library not in ['catalog','train']:
            return jsonify(error='Unknown fuel or image library'),400
        f=fuel_names.index(name);spec=fuel_specs[f];values=[]
        try:
            for field in spec['fields']:
                value=float(request.args.get(field['key'],field['default']))
                if not math.isfinite(value) or not field['min']-1e-5<=value<=field['max']+1e-5:
                    raise ValueError(field['label']+' is outside the recorded range')
                values.append(value)
            if not any(abs(values[0]-v)<1e-5 for v in spec['nozzles']):
                raise ValueError('Choose a recorded nozzle diameter')
        except (ValueError,OverflowError) as error:return jsonify(error=str(error)),400
        x=torch.tensor([values],dtype=torch.float32)
        with torch.inference_mode():
            prediction,_=net(encode(x,torch.tensor([f]),saved['low'],saved['scale'],len(fuel_names)))
        indices,distances=nearest(d['features'],d['fuels'],np.array(values),f,saved['scale'].numpy(),
            np.arange(len(records)) if library=='catalog' else train)
        choices=[]
        for idx,distance in zip(indices[:3],distances[:3]):
            r=records[int(idx)];choices.append(dict(id=r['id'],split=r['split'],distance=float(distance),
                features=dict(zip(FIELDS,r['features'])),excel_row=r['excel_row'],
                exact_conditions=bool(np.allclose(r['features'],values,atol=1e-5,rtol=0)),
                image=png(d['images'][idx].astype('float32')/255),original_url='/spice/api/source/'+r['id']))
        outside_training=any(value<field['training_min']-1e-5 or value>field['training_max']+1e-5
            for value,field in zip(values,spec['fields']))
        return jsonify(prediction=png(prediction[0].permute(1,2,0).numpy()),matches=choices,library=library,
            outside_training_range=outside_training,qualified_for_promotion=False,
            warning='CNN generated estimate; feature combinations may be unobserved even inside individual ranges. Retrieval returns recorded conditions, which may differ from your request.')

    @bp.get('/api/source/<identifier>')
    def source(identifier):
        found=[r for r in records if r['id']==identifier]
        if len(found)!=1:return jsonify(error='Unknown image'),404
        r=found[0]
        with zipfile.ZipFile(SOURCE/r['archive']) as archive:raw=archive.read(r['member'])
        return send_file(BytesIO(raw),mimetype='image/jpeg',download_name=identifier+'.jpg')

    return bp


def create_app():
    app=Flask(__name__);app.register_blueprint(build_blueprint())
    @app.get('/')
    def index():
        from flask import redirect
        return redirect('/spice/')
    return app


if __name__=='__main__':
    create_app().run(host='127.0.0.1',port=5051,debug=False)
