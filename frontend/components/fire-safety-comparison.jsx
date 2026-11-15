"use client";

// Embeds the NASA comparison dashboard (../../fire-dashboard) in this page.
// It renders inside a shadow root so its CSS, element IDs and scripts stay
// separate from the rest of the page. Its inputs come from the page's
// Parameters panel (`inputs`, base units), so it shows results only.
// The files are copied to public/fire-dashboard by scripts/sync-fire-dashboard.mjs.

import { useEffect, useRef, useState } from "react";

const BASE = "/fire-dashboard";
const SCRIPTS = [
  "data/reference-data.js",
  "js/parameters.js",
  "js/charts.js",
  "js/monitoring.js",
  "js/app.js",
];

// Load the dashboard scripts once, in order, even if the component remounts.
let scriptsReady = null;
function loadScripts() {
  if (!scriptsReady) {
    scriptsReady = SCRIPTS.reduce(
      (chain, src) =>
        chain.then(
          () =>
            new Promise((resolve, reject) => {
              const script = document.createElement("script");
              script.src = `${BASE}/${src}`;
              script.async = false;
              script.onload = resolve;
              script.onerror = () => reject(new Error(`Could not load ${src}`));
              document.head.appendChild(script);
            }),
        ),
      Promise.resolve(),
    );
    scriptsReady.catch(() => {
      scriptsReady = null;
    });
  }
  return scriptsReady;
}

/**
 * Props:
 *   inputs         - dashboard input values in base units (see fire-dashboard/js/parameters.js)
 *   onDefinitions  - called once with { sections, units, example } after the scripts load
 *   onGotoField    - called with a dashboard field id when an assessment item is clicked
 *   onLoadExample  - called when the user asks for the example scenario
 */
export function FireSafetyComparison({ inputs, onDefinitions, onGotoField, onLoadExample }) {
  const hostRef = useRef(null);
  const mountedRef = useRef(false);
  const [error, setError] = useState("");
  // Keep the latest props for handlers registered once at mount.
  const latest = useRef({ inputs, onDefinitions, onGotoField, onLoadExample });
  latest.current = { inputs, onDefinitions, onGotoField, onLoadExample };

  useEffect(() => {
    let cancelled = false;
    let unmount = null;

    (async () => {
      try {
        const response = await fetch(`${BASE}/index.html`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const page = new DOMParser().parseFromString(
          await response.text(),
          "text/html",
        );
        page.querySelectorAll("script").forEach((node) => node.remove());
        await loadScripts();
        if (cancelled) return;
        latest.current.onDefinitions?.({
          sections: window.PARAMETER_SECTIONS,
          units: window.UNIT_SYSTEMS,
          example: window.EXAMPLE_INPUT,
        });

        const host = hostRef.current;
        const shadow = host.shadowRoot || host.attachShadow({ mode: "open" });
        shadow.replaceChildren();

        // Wait for the stylesheet so charts measure their final width.
        const link = document.createElement("link");
        link.rel = "stylesheet";
        link.href = `${BASE}/styles.css`;
        await new Promise((resolve) => {
          link.onload = resolve;
          link.onerror = resolve;
          shadow.append(link);
        });
        if (cancelled) return;

        const content = document.createElement("div");
        content.innerHTML = page.body.innerHTML;
        shadow.append(...content.childNodes);
        unmount = window.FireDashboard.mount(shadow, {
          embedded: true,
          title: "",
          externalInputs: true,
          inputs: latest.current.inputs,
          subtitle: "Results use the values in the Parameters panel.",
          onGotoField: (id) => latest.current.onGotoField?.(id),
          onLoadExample: () => latest.current.onLoadExample?.(),
        });
        mountedRef.current = true;
      } catch (err) {
        if (!cancelled) {
          setError(
            `The NASA comparison could not load (${err.message}). Run "npm run sync:fire-dashboard" and reload.`,
          );
        }
      }
    })();

    return () => {
      cancelled = true;
      mountedRef.current = false;
      if (unmount) unmount();
    };
  }, []);

  useEffect(() => {
    if (mountedRef.current) window.FireDashboard?.setInputs(inputs);
  }, [inputs]);

  return (
    <>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div ref={hostRef} className="fire-dashboard-host" data-theme="ember" />
    </>
  );
}
