"use client";

// Embeds the standalone NASA comparison dashboard (../../fire-dashboard) in
// this page. It renders inside a shadow root so its CSS, element IDs and
// scripts stay separate from the Ember workspace on the same page.
// The files are copied to public/fire-dashboard by scripts/sync-fire-dashboard.mjs.

import { useEffect, useRef, useState } from "react";

const BASE = "/fire-dashboard";
const SCRIPTS = [
  "data/reference-data.js",
  "js/parameters.js",
  "js/charts.js",
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

export function FireSafetyComparison() {
  const hostRef = useRef(null);
  const [error, setError] = useState("");

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
        });
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
      if (unmount) unmount();
    };
  }, []);

  return (
    <>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div ref={hostRef} className="fire-dashboard-host" data-theme="dark" />
    </>
  );
}
