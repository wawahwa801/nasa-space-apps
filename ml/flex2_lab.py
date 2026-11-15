"""FLEX-2 RGB retrieval and live conditional-CNN interface."""
import base64
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
import torch
from flask import Blueprint,Flask,jsonify,render_template_string,request

from flex2_data import ROOT,FIELDS
from flex2_model import load,nearest
from spice_model import encode
from flame_display import centre_flame


def png(array):
    buffer=BytesIO();Image.fromarray(np.uint8(np.clip(array,0,1)*255)).save(buffer,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode()


def build_blueprint():
    bp=Blueprint('flex2',__name__,url_prefix='/flex2')
    template=(Path(__file__).resolve().parent/'templates'/'flex2.html').read_text()
    torch.set_num_threads(2);net,saved=load();report=saved['report']
    data=np.load(ROOT/'prepared.npz');manifest=json.loads((ROOT/'manifest.json').read_text());records=manifest['records']
    if report['dataset_sha256']!=hashlib.sha256((ROOT/'prepared.npz').read_bytes()).hexdigest():
        raise ValueError('FLEX-2 data changed; retrain before serving')
    if len(records)!=len(data['images']) or manifest['fuels']!=report['fuels']:raise ValueError('FLEX-2 manifest/checkpoint mismatch')
    train=np.where(data['splits']=='train')[0];fuels=manifest['fuels'];specs=[]
    aligned=[centre_flame(im) for im in data['images']]
    images=[png(im.astype('float32')/255) for im,alignment in aligned]
    for f,name in enumerate(fuels):
        idx=np.where(data['fuels']==f)[0];training=train[data['fuels'][train]==f]
        fields=[]
        for j,(key,label,unit) in enumerate(zip(FIELDS,['Chamber pressure','Chamber temperature'],['kPa','°C'])):
            fields.append(dict(key=key,label=label,unit=unit,min=float(data['features'][idx,j].min()),max=float(data['features'][idx,j].max()),
                training_min=float(data['features'][training,j].min()),training_max=float(data['features'][training,j].max()),
                default=float(data['features'][training[0],j])))
        specs.append(dict(name=name,fields=fields))
    library=[dict(id=r['run'],fuel=r['fuel'],split=r['split'],features=dict(zip(FIELDS,r['features'])),image=images[i],display_alignment=aligned[i][1]) for i,r in enumerate(records)]

    @bp.get('/')
    def index():return render_template_string(template)

    @bp.get('/api/info')
    def info():
        return jsonify(source='PSI-68',fuels=specs,fields=FIELDS,scale=saved['scale'].tolist(),library=library,
            report=report,features_note=manifest['features_note'],stage=manifest['stage'],preprocessing=manifest['preprocessing'],source_url=manifest['source_url'],
            display_note='Preview centres the detected luminous region using integer translation only. Original training targets, scale, colour and benchmark values are unchanged.')

    @bp.get('/api/predict')
    def predict():
        if any(len(request.args.getlist(k))!=1 for k in request.args):return jsonify(error='Duplicate query fields'),400
        unknown=set(request.args)-set(FIELDS)-{'fuel','mode','library'}
        if unknown:return jsonify(error='Unsupported input: '+', '.join(sorted(unknown))),400
        fuel=request.args.get('fuel',fuels[0]);mode=request.args.get('mode','cnn');lib=request.args.get('library','catalog')
        if fuel not in fuels or mode not in ['cnn','retrieval','hybrid'] or lib not in ['catalog','train']:
            return jsonify(error='Unknown fuel, mode or library'),400
        f=fuels.index(fuel);values=[]
        try:
            for spec in specs[f]['fields']:
                value=float(request.args.get(spec['key'],spec['default']))
                if not math.isfinite(value) or not spec['min']-1e-5<=value<=spec['max']+1e-5:
                    raise ValueError(spec['label']+' outside recorded range')
                values.append(value)
        except (ValueError,OverflowError) as error:return jsonify(error=str(error)),400
        idx,distances=nearest(data['features'],data['fuels'],np.array(values),f,saved['scale'].numpy(),train if lib=='train' else np.arange(len(records)))
        match=int(idx[0]);reference=library[match]
        if mode in ['cnn','hybrid']:
            with torch.inference_mode():prediction,_=net(encode(torch.tensor([values],dtype=torch.float32),torch.tensor([f]),saved['low'],saved['scale'],len(fuels)))
            display,alignment=centre_flame(np.uint8(prediction[0].permute(1,2,0).numpy().clip(0,1)*255))
            if mode=='hybrid':
                # Prototype: simple 50/50 pixel blend of generated CNN output and closest recorded image.
                retrieved=np.asarray(Image.open(BytesIO(base64.b64decode(reference['image'].split(',',1)[1]))).convert('RGB'),dtype=np.float32)
                display=np.uint8(np.clip(.5*display.astype(np.float32)+.5*retrieved,0,255))
            shown=png(display.astype('float32')/255)
        else:shown=reference['image'];alignment=reference['display_alignment']
        return jsonify(source='PSI-68',mode=mode,image=shown,features=dict(zip(FIELDS,values)),fuel=fuel,
            reference=reference,distance=float(distances[0]),
            outside_training_range=any(v<s['training_min']-1e-5 or v>s['training_max']+1e-5 for v,s in zip(values,specs[f]['fields'])),
            qualified_for_promotion=False,display_alignment=alignment)

    return bp


def create_app():
    app=Flask(__name__);app.register_blueprint(build_blueprint())
    from spice_data import ART as SPICE_ART
    if (SPICE_ART/'selected.pt').exists():
        from spice_lab import build_blueprint as spice_blueprint
        app.register_blueprint(spice_blueprint())
    @app.get('/')
    def index():
        from flask import redirect
        return redirect('/flex2/')
    return app


if __name__=='__main__':create_app().run(host='127.0.0.1',port=5051,debug=False)
