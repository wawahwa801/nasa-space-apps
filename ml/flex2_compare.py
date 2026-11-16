"""Local three-way comparison using a completed discovery training run."""
import argparse
import hashlib
import json
import math
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
<select id="run" aria-label="Recorded conditions"></select><div id="controls" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:18px;margin-top:24px"></div><div id="renderControls" style="display:flex;flex-wrap:wrap;gap:24px;margin-top:24px"></div><p id="status" role="status">Loading…</p>
<main><section><h2>Trained hybrid</h2><img id="hybrid" alt="Trained hybrid prediction"><p id="hybridNote"></p></section><section><h2>Normal CNN</h2><img id="cnn" alt="Published CNN prediction"><p>Published 100-run CNN, using fuel, pressure and temperature.</p></section><section><h2>Feature retrieval</h2><img id="retrieval" alt="Retrieved recorded flame"><p id="retrievalNote"></p></section></main>
<details id="geometryPanel" hidden><summary>Predicted geometry probability (weak supervision)</summary><img id="geometryMask" style="max-width:256px" alt="Uncalibrated predicted flame mask"><p>Mask uses the centered training coordinate frame. This is an image-derived probability map, not a validated physical boundary for the PINN.</p></details><p id="conditions"></p><p>All numeric hybrid features have sliders; categorical features have selectors. Fuel comes from the recorded preset. Normal CNN and retrieval use only fuel, pressure and temperature. Flags indicate missing measurements; changing them does not supply a measured value. Camera codes and campaign are nuisance inputs. Slider combinations may be unsupported by training data; predictions are experimental. Display alignment translates the luminous region without resizing.</p>
<script>
let version=0,generation=0,renders=0,info,busy=false,pending=false;const $=id=>document.getElementById(id);
function preset(){generation++;const r=info.runs.find(x=>x.id===$('run').value);for(const [key,value] of Object.entries(r.values)){const el=$(key);el.value=value;const out=$(key+'Out');if(out)out.textContent=value;}update();}
function update(){version++;pending=true;$('status').textContent='Updating comparison…';pump();}
async function pump(){if(busy||!pending)return;pending=false;busy=true;const v=version,g=generation;const params=new URLSearchParams({run:$('run').value});for(const s of [...info.numeric,...info.categories,...(info.renderer||[])])params.set(s.key,$(s.key).value);
try{const response=await fetch('/api/compare?'+params);const r=await response.json();if(!response.ok)throw Error(r.error);if(g===generation){for(const k of ['hybrid','cnn','retrieval'])$(k).src=r[k];$('hybrid').dataset.renderCount=String(++renders);$('geometryPanel').hidden=!r.mask;if(r.mask)$('geometryMask').src=r.mask;$('hybrid').dataset.inputVersion=String(v);$('hybridNote').textContent=r.model_note+' · reference '+r.hybrid_reference;$('retrievalNote').textContent='Recorded training run '+r.retrieval_reference;$('conditions').textContent=r.conditions;$('status').textContent=pending?'Live prediction · updating while you drag…':'Comparison ready';}}catch(e){if(v===version)$('status').textContent=e.message;}finally{busy=false;pump();}}
fetch('/api/runs').then(r=>r.json()).then(r=>{info=r;for(const x of r.runs)$('run').add(new Option(x.label,x.id));
for(const s of r.numeric){const label=document.createElement('label');label.textContent=s.label+' ('+s.unit+')';const output=document.createElement('output');output.id=s.key+'Out';output.style.display='block';const input=document.createElement('input');input.type='range';input.id=s.key;input.min=s.min;input.max=s.max;input.step=s.step;input.style.width='100%';input.disabled=s.min===s.max;input.setAttribute('aria-label',s.label);input.oninput=()=>{output.textContent=Number(input.value).toFixed(3);update();};label.append(output,input);$('controls').append(label);}
for(const s of r.categories){const label=document.createElement('label');label.textContent=s.label;const select=document.createElement('select');select.id=s.key;select.style.display='block';select.add(new Option('Unknown / unseen code','unknown'));for(const [j,value] of s.levels)select.add(new Option(value,value));select.onchange=update;label.append(select);$('controls').append(label);}
for(const s of r.renderer||[]){const label=document.createElement('label');label.textContent=s.label;const output=document.createElement('output');output.textContent=s.default;output.style.display='block';const input=document.createElement('input');input.type='range';input.id=s.key;input.min=s.min;input.max=s.max;input.step='0.01';input.value=s.default;input.setAttribute('aria-label',s.label);input.oninput=()=>{output.textContent=Number(input.value).toFixed(2);update();};label.append(output,input);$('renderControls').append(label);}$('run').onchange=preset;preset();}).catch(e=>$('status').textContent=e.message);
</script></html>'''


def create_app(run_dir,texture=False,*,baseline_data_dir=None,baseline_checkpoint=None):
    base_root=Path(baseline_data_dir) if baseline_data_dir is not None else ROOT
    run_dir=Path(run_dir);training=run_dir/'training'
    snapshot=run_dir/'snapshot.json'
    if snapshot.exists():
        for name,expected in json.loads(snapshot.read_text())['files'].items():
            path=run_dir/name
            if path.stat().st_size!=expected['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest()!=expected['sha256']:
                raise ValueError('Published model snapshot checksum mismatch: '+name)
    checkpoints=[]
    for path in training.glob('seed-*-best.pt'):
        saved=torch.load(path,map_location='cpu',weights_only=True)
        checkpoints.append((saved['validation']['weighted_mae'],path,saved))
    final_fit=(training/'final.pt').exists()
    if final_fit:saved=torch.load(training/'final.pt',map_location='cpu',weights_only=True)
    elif checkpoints:_,_,saved=min(checkpoints,key=lambda item:item[0])
    else:raise ValueError('No trained hybrid checkpoint found')
    dataset=run_dir/'expanded'
    if not final_fit and hashlib.sha256((dataset/'manifest.json').read_bytes()).hexdigest()!=saved['metadata']['manifest_sha256']:
        raise ValueError('Hybrid dataset differs from training manifest')
    d,m,x,refs,evidence_hash=load_verified(dataset)
    if 'preprocessing' in saved['metadata']:
        from flex2_continuous import frozen_features
        x=frozen_features(d,saved['metadata'])
    if evidence_hash!=saved['metadata']['evidence_sha256'] or d['feature_names']!=saved['metadata']['features']:
        raise ValueError('Hybrid feature schema/evidence differs from checkpoint')
    if d['groups'].tolist()!=saved['metadata']['target_ids']:raise ValueError('Hybrid target IDs differ from checkpoint')
    torch.set_num_threads(2)
    shape=saved['metadata'].get('architecture')=='aligned-soft-shape-v1'
    geometry=saved['metadata'].get('architecture')=='multiscale-geometry-v1'
    continuous=saved['metadata'].get('architecture')=='soft-reference-generator-v1'
    if geometry:
        from flex2_geometry import GeometryHybrid
        from flex2_shape import aligned_data
        from flex2_continuous import soft_references
        hybrid=GeometryHybrid(x.shape[1])
    elif shape:
        from flex2_shape import ShapeHybrid,aligned_data
        from flex2_continuous import soft_references
        hybrid=ShapeHybrid(x.shape[1])
    elif continuous:
        from flex2_continuous import ContinuousCNN,soft_references
        hybrid=ContinuousCNN(x.shape[1])
    else:hybrid=RetrievalConditioned(x.shape[1]*3)
    hybrid.load_state_dict(saved['state']);hybrid.eval()
    cnn,cnn_saved=load(baseline_checkpoint);base=np.load(base_root/'prepared.npz');train=np.where(base['splits']=='train')[0]
    images=torch.tensor(d['images']).permute(0,3,1,2).float()/255;conditions=torch.tensor(x)
    if shape or geometry:
        aligned,aligned_masks=aligned_data(d['images'],d['masks']);images=torch.tensor(aligned).permute(0,3,1,2).float()/255
    if texture:
        if not geometry:raise ValueError('Texture compositor requires the generated geometry model')
        from flex2_texture import texture_composite
        import torch.nn.functional as F
        appearance_masks=F.avg_pool2d(F.max_pool2d(torch.tensor(aligned_masks).unsqueeze(1),13,1,6),7,1,3)
    if continuous:
        with torch.inference_mode():embedding_bank=torch.cat([hybrid.encode_references(b) for b in images.split(8)])
    if geometry:
        with torch.inference_mode():
            encoded=[hybrid.encode_references(b) for b in images.split(8)]
            pyramid_banks=[torch.cat([parts[k] for parts in encoded]) for k in range(3)]
    base_manifest=json.loads((base_root/'manifest.json').read_text())
    eligible=[i for i,f in enumerate(d['fuels']) if m['fuels'][int(f)] in base_manifest['fuels']]
    eligible.sort(key=lambda i:(str(d['splits'][i])!='test',str(d['groups'][i])))
    numeric_labels=[('Pressure','kPa'),('Chamber temperature','°C'),('Support fiber','0 / 1'),('Igniter power','W'),('Power missing flag','0 / 1'),('Igniter on-time','s'),('On-time missing flag','0 / 1'),('Time since igniter-on','s')]
    control_specs=[]
    for j,(label,unit) in enumerate(numeric_labels):
        raw=d['feature_raw_values'][:,j]
        control_specs.append(dict(key=f'n{j}',label=label,unit=unit,min=float(raw.min()),max=float(raw.max()),step=1 if j in (2,4,6) else 'any'))
    category_specs=[]
    for prefix,label in [('campaign','Campaign'),('camera_shutter_code','Camera shutter code'),('camera_gain_code','Camera gain code')]:
        levels=[(j,name.split('=',1)[1]) for j,name in enumerate(d['feature_names']) if name.startswith(prefix+'=')]
        category_specs.append(dict(key=prefix,label=label,levels=levels))
    def defaults(i):
        out={f'n{j}':float(d['feature_raw_values'][i,j]) for j in range(8)}
        for spec in category_specs:
            selected=next((value for j,value in spec['levels'] if x[i,j]>.5),'unknown')
            out[spec['key']]=selected
        return out
    def shown(im):
        if isinstance(im,torch.Tensor):im=np.uint8(im.permute(1,2,0).numpy().clip(0,1)*255)
        aligned,_=centre_flame(im);return png(aligned.astype('float32')/255)
    app=Flask(__name__)
    @app.get('/')
    def index():
        page=PAGE
        if texture:
            page=page.replace('<h1>','<p>Visual compositing prototype: learned CNN mask + smoothly weighted recorded RGB. Source detail is warped and rescaled; rendered geometry is uncalibrated. This is not a newly trained model or an accuracy result.</p><h1>',1)
            page=page.replace('Predicted geometry probability (weak supervision)','Combined CNN/retrieval mask (uncalibrated)')
        return render_template_string(page)
    @app.get('/api/runs')
    def runs():return jsonify(runs=[dict(id=str(d['groups'][i]),label=f"{d['groups'][i]} · {m['fuels'][int(d['fuels'][i])]} · {d['splits'][i]}",values=defaults(i)) for i in eligible],numeric=control_specs,categories=category_specs,renderer=[dict(key='geometry_share',label='Learned shape influence (rendering)',min=0,max=1,default=.8),dict(key='concentration',label='Reference detail concentration (rendering)',min=1,max=4,default=2)] if texture else [])
    @app.get('/api/compare')
    def compare():
        matches=[i for i in eligible if str(d['groups'][i])==request.args.get('run')]
        if len(matches)!=1:return jsonify(error='Choose a supported recorded run'),400
        i=matches[0];fuel=m['fuels'][int(d['fuels'][i])];f=base_manifest['fuels'].index(fuel)
        unknown=set(request.args)-({'run','geometry_share','concentration'} if texture else {'run'})-{s['key'] for s in control_specs+category_specs}
        if unknown or any(len(request.args.getlist(k))!=1 for k in request.args):return jsonify(error='Unsupported or duplicate controls'),400
        query=x[i].copy();raw=d['feature_raw_values'][i].copy();geometry_share=.8;concentration=2.
        if texture:
            try:
                geometry_share=float(request.args.get('geometry_share',.8));concentration=float(request.args.get('concentration',2.))
                if not math.isfinite(geometry_share) or not 0<=geometry_share<=1 or not math.isfinite(concentration) or not 1<=concentration<=4:raise ValueError('Invalid rendering controls')
            except ValueError as error:return jsonify(error=str(error)),400
        try:
            for j,spec in enumerate(control_specs):
                value=float(request.args.get(spec['key'],raw[j]))
                if not math.isfinite(value) or not spec['min']<=value<=spec['max'] or (j in (2,4,6) and value not in (0,1)):raise ValueError('Invalid '+spec['label'])
                raw[j]=value;query[j]=np.clip((value-d['feature_low'][j])/d['feature_scale'][j],-.25,1.25)
            for spec in category_specs:
                value=request.args.get(spec['key'],defaults(i)[spec['key']])
                if value not in [v for _,v in spec['levels']]+['unknown']:raise ValueError('Invalid '+spec['label'])
                for j,level in spec['levels']:query[j]=float(value==level)
        except ValueError as error:return jsonify(error=str(error)),400
        hybrid_candidates=np.where((d['splits']=='train') & (d['fuels']==d['fuels'][i]) & (d['groups']!=d['groups'][i]))[0]
        ref=int(hybrid_candidates[np.argmin(np.mean((x[hybrid_candidates]-query)**2,axis=1))])
        candidates=train[base['groups'][train]!=d['groups'][i]]
        ranking,_=nearest(base['features'],base['fuels'],raw[:2],f,cnn_saved['scale'].numpy(),candidates)
        normal_ref=int(ranking[0])
        with torch.inference_mode():
            mask_image=None
            if geometry:
                weights=soft_references(torch.tensor(query[None]),conditions,torch.tensor(d['fuels']),torch.tensor([d['fuels'][i]]),torch.tensor([i]),saved['metadata']['temperature'])
                pyramid=[torch.einsum('bn,nchw->bchw',weights,bank) for bank in pyramid_banks]
                rgb,mask_logits=hybrid.decode(torch.tensor(query[None]),weights@conditions,pyramid)
                if texture:
                    pool=torch.where((torch.tensor(d['fuels'])==d['fuels'][i]) & (torch.arange(len(x))!=i))[0]
                    rgb,composite_mask=texture_composite(mask_logits.sigmoid(),images[pool],appearance_masks[pool],weights[0,pool],geometry_share,concentration)
                    mask_logits=torch.logit(composite_mask.clamp(.0001,.9999))
                prediction=rgb[0];mask_image=png(np.repeat(mask_logits[0,0].sigmoid().numpy()[:,:,None],3,axis=2))
            elif shape:
                weights=soft_references(torch.tensor(query[None]),conditions,torch.tensor(d['fuels']),torch.tensor([d['fuels'][i]]),torch.tensor([i]),saved['metadata']['temperature'])
                prediction=hybrid(torch.tensor(query[None]),weights@conditions,torch.einsum('bn,nchw->bchw',weights,images))[0][0]
            elif continuous:
                weights=soft_references(torch.tensor(query[None]),conditions,torch.tensor(d['fuels']),torch.tensor([d['fuels'][i]]),torch.tensor([i]),saved['metadata']['temperature'])
                embedding=.5*torch.einsum('bn,nchw->bchw',weights,embedding_bank)+.5*hybrid.encode_references(torch.einsum('bn,nchw->bchw',weights,images))
                prediction=hybrid.decode(torch.tensor(query[None]),weights@conditions,embedding)[0]
            else:prediction=hybrid(torch.tensor(query[None]),conditions[ref:ref+1],images[ref:ref+1])[0]
            original,_=cnn(encode(torch.tensor(raw[None,:2]),torch.tensor([f]),cnn_saved['low'],cnn_saved['scale'],len(base_manifest['fuels'])))
        return jsonify(mask=mask_image,hybrid=shown(prediction),cnn=shown(original[0]),retrieval=shown(base['images'][normal_ref]),seed=saved['seed'],model_note=f"{'CNN mask + retrieved texture · ' if texture else 'Generated geometry hybrid · ' if geometry else 'Aligned shape hybrid · ' if shape else ''}All {len(x)} runs fitted · no held-out score" if final_fit else f"Validation-selected seed {saved['seed']}",hybrid_reference=str(d['groups'][ref]),retrieval_reference=str(base['groups'][normal_ref]),conditions=f"{fuel} · {raw[0]:.2f} kPa · {raw[1]:.2f} °C · experimental input combination")
    return app


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-dir',type=Path,default=ROOT.parent/'flex2-continuous-model');p.add_argument('--port',type=int,default=5053);p.add_argument('--texture-composite',action='store_true');a=p.parse_args();create_app(a.run_dir,a.texture_composite).run(host='127.0.0.1',port=a.port,debug=False)
