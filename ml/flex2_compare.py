"""Local three-way comparison using a completed discovery training run."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from flask import Flask, jsonify, render_template_string, request

from flex2_data import ROOT
from flex2_lab import png
from flex2_model import load, nearest
from flex2_overnight import load_verified, RetrievalConditioned
from flame_display import centre_flame
from spice_model import encode


PAGE='''<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FLEX-2 model comparison</title>
<style>body{background:#101114;color:#eee;font:16px system-ui;max-width:1300px;margin:auto;padding:24px}p,small{color:#b8bfcb;line-height:1.5}select{padding:12px;max-width:100%;background:#222;color:white}main{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}img{width:100%;background:black}section{background:#191c22;padding:16px;border-radius:12px}#status{min-height:30px}@media(max-width:700px){main{grid-template-columns:1fr}}</style>
<h1>FLEX-2 trained model comparison</h1><p>Choose a recorded condition to compare the trained retrieval-conditioned CNN, published feature-only CNN, and normal pressure/temperature retrieval. All references come from training runs, with the chosen run excluded.</p>
<select id="run" aria-label="Recorded conditions"></select><p id="status" role="status">Loading…</p>
<main><section><h2>Trained hybrid</h2><img id="hybrid" alt="Trained hybrid prediction"><p id="hybridNote"></p></section><section><h2>Normal CNN</h2><img id="cnn" alt="Published CNN prediction"><p>Published 100-run CNN, using fuel, pressure and temperature.</p></section><section><h2>Feature retrieval</h2><img id="retrieval" alt="Retrieved recorded flame"><p id="retrievalNote"></p></section></main>
<p id="conditions"></p><p>The hybrid uses the chosen run’s verified apparatus, timing, campaign and camera covariates. These are recorded-condition comparisons. Predictions remain experimental; image appearance does not establish physical accuracy. Display alignment translates the luminous region without resizing.</p>
<script>let version=0;const $=id=>document.getElementById(id);async function update(){const v=++version;$('status').textContent='Generating comparison…';try{const response=await fetch('/api/compare?run='+encodeURIComponent($('run').value));const r=await response.json();if(!response.ok)throw Error(r.error);if(v!==version)return;for(const k of ['hybrid','cnn','retrieval'])$(k).src=r[k];$('hybridNote').textContent='Trained seed '+r.seed+' · reference '+r.hybrid_reference;$('retrievalNote').textContent='Recorded training run '+r.retrieval_reference;$('conditions').textContent=r.conditions;$('status').textContent='Comparison ready';}catch(e){if(v===version)$('status').textContent=e.message;}}fetch('/api/runs').then(r=>r.json()).then(r=>{for(const x of r.runs)$('run').add(new Option(x.label,x.id));$('run').onchange=update;update();}).catch(e=>$('status').textContent=e.message);</script></html>'''


def create_app(run_dir):
    run_dir=Path(run_dir);training=run_dir/'training'
    checkpoints=[]
    for path in training.glob('seed-*-best.pt'):
        saved=torch.load(path,map_location='cpu',weights_only=True)
        checkpoints.append((saved['validation']['weighted_mae'],path,saved))
    if not checkpoints:raise ValueError('No trained hybrid checkpoint found')
    _,_,saved=min(checkpoints,key=lambda item:item[0])
    dataset=run_dir/'expanded'
    if hashlib.sha256((dataset/'manifest.json').read_bytes()).hexdigest()!=saved['metadata']['manifest_sha256']:
        raise ValueError('Hybrid dataset differs from training manifest')
    d,m,x,refs,evidence_hash=load_verified(dataset)
    if evidence_hash!=saved['metadata']['evidence_sha256'] or d['feature_names']!=saved['metadata']['features']:
        raise ValueError('Hybrid feature schema/evidence differs from checkpoint')
    if d['groups'].tolist()!=saved['metadata']['target_ids']:raise ValueError('Hybrid target IDs differ from checkpoint')
    torch.set_num_threads(2)
    hybrid=RetrievalConditioned(x.shape[1]*3);hybrid.load_state_dict(saved['state']);hybrid.eval()
    cnn,cnn_saved=load();base=np.load(ROOT/'prepared.npz');train=np.where(base['splits']=='train')[0]
    images=torch.tensor(d['images']).permute(0,3,1,2).float()/255;conditions=torch.tensor(x)
    base_manifest=json.loads((ROOT/'manifest.json').read_text())
    eligible=[i for i,f in enumerate(d['fuels']) if m['fuels'][int(f)] in base_manifest['fuels']]
    eligible.sort(key=lambda i:(str(d['splits'][i])!='test',str(d['groups'][i])))
    def shown(im):
        if isinstance(im,torch.Tensor):im=np.uint8(im.permute(1,2,0).numpy().clip(0,1)*255)
        aligned,_=centre_flame(im);return png(aligned.astype('float32')/255)
    app=Flask(__name__)
    @app.get('/')
    def index():return render_template_string(PAGE)
    @app.get('/api/runs')
    def runs():return jsonify(runs=[dict(id=str(d['groups'][i]),label=f"{d['groups'][i]} · {m['fuels'][int(d['fuels'][i])]} · {d['splits'][i]}") for i in eligible])
    @app.get('/api/compare')
    def compare():
        matches=[i for i in eligible if str(d['groups'][i])==request.args.get('run')]
        if len(matches)!=1:return jsonify(error='Choose a supported recorded run'),400
        i=matches[0];ref=int(refs[i]);fuel=m['fuels'][int(d['fuels'][i])];f=base_manifest['fuels'].index(fuel)
        candidates=train[base['groups'][train]!=d['groups'][i]]
        ranking,_=nearest(base['features'],base['fuels'],d['features'][i],f,cnn_saved['scale'].numpy(),candidates)
        normal_ref=int(ranking[0])
        with torch.inference_mode():
            prediction=hybrid(conditions[i:i+1],conditions[ref:ref+1],images[ref:ref+1])[0]
            original,_=cnn(encode(torch.tensor(d['features'][i:i+1]),torch.tensor([f]),cnn_saved['low'],cnn_saved['scale'],len(base_manifest['fuels'])))
        return jsonify(hybrid=shown(prediction),cnn=shown(original[0]),retrieval=shown(base['images'][normal_ref]),seed=saved['seed'],hybrid_reference=str(d['groups'][ref]),retrieval_reference=str(base['groups'][normal_ref]),conditions=f"{d['groups'][i]} · {fuel} · {d['features'][i,0]:.2f} kPa · {d['features'][i,1]:.2f} °C · {d['splits'][i]}")
    return app


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-dir',type=Path,required=True);p.add_argument('--port',type=int,default=5053);a=p.parse_args();create_app(a.run_dir).run(host='127.0.0.1',port=a.port,debug=False)
