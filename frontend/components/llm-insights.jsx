"use client";
import { useEffect, useId, useRef, useState } from "react";

function InsightSection({ title, children, initialOpen = false }) {
  const [open, setOpen] = useState(initialOpen);
  const id = useId();
  return <div className="insight-group">
    <h3><button type="button" className="insight-header" aria-expanded={open} aria-controls={id}
      onClick={() => setOpen(v => !v)}><span>{title}</span><span aria-hidden="true">{open ? "−" : "+"}</span></button></h3>
    <div id={id} hidden={!open} className="insight-group-body">{children}</div>
  </div>;
}

export function LlmInsights({ scenario }) {
  const [open, setOpen] = useState(false);
  const [result, setResult] = useState(null), [status, setStatus] = useState(""), [busy, setBusy] = useState(false);
  const version = useRef(0);
  const id = useId();
  useEffect(() => { version.current++; setResult(null); setStatus(""); setBusy(false); }, [scenario]);
  async function analyze() {
    if (!scenario || busy) return;
    const current = ++version.current;
    setBusy(true); setStatus("Generating insights…"); setResult(null);
    try {
      // Same-origin call to the Flask backend (Vercel routes /api/* to it; locally Next.js
      // rewrites it to port 5000). The LLM key stays on the server.
      const response = await fetch("/api/analyze", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data: JSON.stringify(scenario), data_type: "qualitative",
          instructions: "Explain these experimental simulation results and their assumptions. Do not claim validated physical safety or invent confidence scores.",
          context: "Illustrative CNN flame-size room simulation, not calibrated cabin physics." }),
      });
      const data = await response.json().catch(() => ({ error: "Insight service unavailable. Try again later." }));
      if (!response.ok) throw Error(data.error || "Insight service unavailable.");
      if (current === version.current) { setResult(data); setStatus(""); }
    } catch (error) { if (current === version.current) setStatus(error.message); }
    finally { if (current === version.current) setBusy(false); }
  }
  const uncertainty = scenario?.uncertainty;
  return <section className="insights-content" aria-label="Simulation AI insights">
    <h2><button type="button" className="insights-toggle" aria-expanded={open} aria-controls={id}
      onClick={() => setOpen(v => !v)}><span><small>Explain this simulation</small>AI insights</span><span aria-hidden="true">{open ? "−" : "+"}</span></button></h2>
    <div id={id} hidden={!open} className="insights-body">
      <p className="hybrid-muted">Review the explanation, applied conditions and model assumptions in one place.</p>
      <InsightSection title="Summary" initialOpen>
        {scenario ? <><p>{scenario.conditions} · ignition: {scenario.ignition_module}</p>
          <button type="button" className="insight-generate" disabled={busy} onClick={analyze}>{busy ? "Generating…" : "Generate insights"}</button></>
          : <p>Run a simulation above to generate its explanation.</p>}
        <p role="status">{status}</p>
        {result && <><p className="hybrid-muted">{result.provider === "mock" ? "Demo response — mock provider" : `Provider: ${result.provider}`} · {result.model}</p>
          <div className="insight-output">{result.output}</div></>}
      </InsightSection>
      <InsightSection title="Applied parameters">
        {scenario ? <dl className="insight-parameters"><div><dt>Conditions</dt><dd>{scenario.conditions}</dd></div>
          <div><dt>Ignition room</dt><dd>{scenario.ignition_module}</dd></div>
          <div><dt>Environment</dt><dd>{scenario.environment?.rooms?.length ?? "—"} rooms · {scenario.environment?.edges?.length ?? "—"} hallways</dd></div>
          <div><dt>Image-derived diameter</dt><dd>{Number.isFinite(scenario.initial_diameter_mm) ? `${scenario.initial_diameter_mm.toFixed(2)} mm (assumed equivalent proxy)` : "Not available"}</dd></div>
          <div><dt>Assumed burn constant</dt><dd>{scenario.k_mm2_s ?? "—"} mm²/s</dd></div>
        </dl> : <p>Applied parameters appear after a simulation finishes.</p>}
      </InsightSection>
      <InsightSection title="Assumptions & uncertainty">
        <p>These are exploratory scenarios, not calibrated safety predictions or confidence intervals.</p>
        {scenario ? <>{scenario.assumptions?.length > 0 && <ul>{scenario.assumptions.map((item, index) => <li key={index}>{item}</li>)}</ul>}
          {uncertainty?.statement && <p>{uncertainty.statement}</p>}</> : <p>Run a simulation to inspect its specific assumptions.</p>}
      </InsightSection>
    </div>
  </section>;
}
