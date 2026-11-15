"use client";
import {useEffect, useRef, useState} from 'react';
export function LlmInsights({scenario}) {
  const [result,setResult]=useState(null),[status,setStatus]=useState(''),[busy,setBusy]=useState(false);
  const version=useRef(0);
  useEffect(()=>{version.current++;setResult(null);setStatus('');setBusy(false);},[scenario]);
  async function analyze(){const id=++version.current;setBusy(true);setStatus('Generating insights…');setResult(null);
    try{const response=await fetch('/insight-api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({data:JSON.stringify(scenario),data_type:'qualitative',instructions:'Explain these experimental simulation results and their assumptions. Do not claim validated physical safety or invent confidence scores.',context:'Illustrative CNN flame-size room simulation, not calibrated cabin physics.'})});const data=await response.json().catch(()=>({error:'Insight service unavailable. Try again later.'}));if(!response.ok)throw Error(data.error);if(id===version.current){setResult(data);setStatus('');}}
    catch(e){if(id===version.current)setStatus(e.message);}finally{if(id===version.current)setBusy(false);}}
  return <section className="insights-content"><h2>LLM insights</h2><p>Explain the applied hybrid parameters and room-simulation assumptions.</p>{scenario ? <><p>{scenario.conditions} · ignition: {scenario.ignition_module}</p><button type="button" disabled={busy} onClick={analyze}>Generate insights</button></> : <p>Run a simulation in the Flame simulation tab first.</p>}<p role="status">{status}</p>{result && <><p>{result.provider==='mock'?'Demo response — mock provider':`Provider: ${result.provider}`} · {result.model}</p><div style={{whiteSpace:'pre-wrap'}}>{result.output}</div></>}</section>;
}
