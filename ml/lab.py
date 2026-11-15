"""Simple BASS-II experiment and separate NASA FLEX conditions browser."""
import base64
from io import BytesIO
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
import torch
from flask import Flask,jsonify,render_template,request,send_file
from jinja2 import DictLoader

from bass_study import WORK,SIZE
from flex_images import ROOT as FLEX_WORK
from flex_train import ART as FLEX_ART
from bass_train import load_model
from flame import DATA,OUT
from flex_data import RELEASES


def png(array):
    image=Image.fromarray(np.uint8(np.clip(array,0,1)*255));buffer=BytesIO();image.save(buffer,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode()


def create_app():
    app=Flask(__name__);torch.set_num_threads(2)
    if (OUT/'flex2-study'/'selected.pt').exists():
        from flex2_lab import build_blueprint as flex2_blueprint
        app.register_blueprint(flex2_blueprint())
    # SPICE also runs independently via spice_lab.py, without BASS/FLEX artifacts.
    if (OUT/'spice-study'/'selected.pt').exists():
        from spice_lab import build_blueprint
        app.register_blueprint(build_blueprint())
    app.jinja_loader=DictLoader({'lab.html':(Path(__file__).resolve().parent/'templates'/'lab.html').read_text()})
    engines={}
    definitions=[
        ('bass',WORK,OUT/'bass-study','BASS-II · PMMA film',
         [('Initial oxygen','% by volume'),('Film thickness','mm'),('Film width','cm')],
         'Aligned color-masked PMMA targets; visually stable-window proxy, not measured steady conditions.'),
        ('flex',FLEX_WORK,FLEX_ART,'FLEX · Methanol droplets',
         [('Initial oxygen','% mole fraction'),('Pressure','kPa'),('Initial CO₂','% mole fraction'),('Initial droplet diameter','mm')],
         'Background-subtracted 16-bit camera-B signal, shown in monochrome; not RGB color or thermal calibration.')]
    for domain,work,art,title,labels,description in definitions:
        net,saved=load_model(art);report=saved['report'];data=np.load(work/'prepared.npz')
        images=data['images'];features=data['features'];trials=data['trials'];train=np.where(data['splits']=='train')[0]
        if images.shape[1:]!=(SIZE,SIZE,3):raise ValueError('Regenerate '+domain+' targets')
        high=saved['low']+saved['scale']
        specs=[dict(key=key,label=labels[i][0],unit=labels[i][1],min=float(saved['low'][i]),
                    max=float(high[i]),default=float(features[train[0],i])) for i,key in enumerate(report['fields'])]
        if domain=='bass':raw_count=len(images)*10;background_count=0
        else:
            inventory=json.loads((work/'inventory.json').read_text())
            raw_count=sum(sum(m['role']=='target' for m in r.get('members',[])) for r in inventory if r['run'] in trials)
            background_count=sum(sum(m['role']=='background' for m in r.get('members',[])) for r in inventory if r['run'] in trials)
        engines[domain]=dict(net=net,saved=saved,data=data,images=images,features=features,
            trials=trials,train=train,specs=specs,report=report,title=title,description=description,
            raw_count=raw_count,background_count=background_count)
    flex=json.loads((DATA/'flex'/'conditions.json').read_text())

    @app.get('/')
    def index():return render_template('lab.html')

    @app.get('/api/info')
    def info():
        domain=request.args.get('domain','bass')
        if domain not in engines:return jsonify(error='Unknown experiment domain'),400
        e=engines[domain]
        return jsonify(domain=domain,domains=[dict(id=k,label=v['title']) for k,v in engines.items()],
            features=e['specs'],report=e['report'],description=e['description'],
            independent_targets=len(e['images']),raw_frames_used=e['raw_count'],background_frames_used=e['background_count'],
            limitation='Image-derived weak targets and very small whole-run evaluation splits; no verified physical accuracy.')

    @app.get('/api/predict')
    def predict():
        domain=request.args.get('domain','bass')
        if domain not in engines:return jsonify(error='Unknown experiment domain'),400
        e=engines[domain];specs=e['specs'];saved=e['saved'];fields=e['report']['fields']
        unknown=set(request.args)-set(fields)-{'domain'}
        if unknown:return jsonify(error='Unsupported input: '+', '.join(sorted(unknown))),400
        values=[]
        try:
            for f in specs:
                value=float(request.args.get(f['key'],f['default']))
                if not math.isfinite(value) or not f['min']-1e-6<=value<=f['max']+1e-6:
                    raise ValueError(f"{f['label']} must be within {f['min']:g}–{f['max']:g}")
                values.append(value)
        except (ValueError,OverflowError) as error:return jsonify(error=str(error)),400
        tensor=torch.tensor([values],dtype=torch.float32)
        with torch.inference_mode():rgb,mask=e['net']((tensor-saved['low'])/saved['scale'])
        train=e['train'];features=e['features']
        distance=np.mean(((features[train]-np.array(values))/saved['scale'].numpy())**2,axis=1)
        nearest=int(train[int(distance.argmin())])
        return jsonify(domain=domain,prediction=png(rgb[0].permute(1,2,0).numpy()),mask=png(mask.sigmoid()[0,0].numpy()),
            reference=png(e['images'][nearest].astype('float32')/255),reference_trial=str(e['trials'][nearest]),
            reference_features={key:float(features[nearest,i]) for i,key in enumerate(fields)},
            exact_conditions=bool(distance.min()<1e-8),qualified_for_promotion=False,
            warning=e['report']['promotion_note'])

    @app.get('/api/flex')
    def flex_info():return jsonify(releases=flex,image_model_trained=True,trained_release='PSI-69',trained_runs=engines['flex']['report']['trials'],qualified_for_promotion=False)

    @app.get('/api/flex/csv/<source>')
    def flex_csv(source):
        if source not in RELEASES:return jsonify(error='Unknown FLEX release'),404
        return send_file(DATA/'multi'/source/RELEASES[source][1],as_attachment=True,mimetype='application/octet-stream')

    return app


if __name__=='__main__':create_app().run(host='127.0.0.1',port=5050,debug=False)
