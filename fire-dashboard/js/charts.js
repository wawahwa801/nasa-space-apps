// Small SVG chart helpers: scatter plot and line chart, with hover tooltips.
// No external libraries, so the dashboard works offline and from file://.

(function () {
  const SVG_NS = "http://www.w3.org/2000/svg";
  const MARGIN = { top: 12, right: 16, bottom: 40, left: 52 };

  function el(name, attrs = {}, parent) {
    const node = document.createElementNS(SVG_NS, name);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (parent) parent.appendChild(node);
    return node;
  }

  function niceStep(span, count) {
    const raw = span / Math.max(count, 1);
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const norm = raw / mag;
    return (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag;
  }

  // Domain padded and snapped to nice ticks.
  function niceDomain(values, count = 5) {
    let lo = Math.min(...values);
    let hi = Math.max(...values);
    if (!isFinite(lo) || !isFinite(hi)) return { lo: 0, hi: 1, ticks: [0, 1] };
    if (lo === hi) { lo -= Math.abs(lo) * 0.1 || 1; hi += Math.abs(hi) * 0.1 || 1; }
    const step = niceStep(hi - lo, count);
    lo = Math.floor(lo / step) * step;
    hi = Math.ceil(hi / step) * step;
    const ticks = [];
    for (let t = lo; t <= hi + step / 2; t += step) ticks.push(+t.toPrecision(12));
    return { lo, hi, ticks };
  }

  function fmt(v) {
    if (v == null || !isFinite(v)) return "–";
    const a = Math.abs(v);
    if (a >= 10000) return (v / 1000).toLocaleString(undefined, { maximumFractionDigits: 1 }) + "K";
    if (a >= 100) return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
    if (a >= 1) return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
    return v.toLocaleString(undefined, { maximumSignificantDigits: 3 });
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // Tick labels show as many decimals as the tick spacing needs.
  function tickFmt(v, ticks) {
    const step = ticks.length > 1 ? Math.abs(ticks[1] - ticks[0]) : 1;
    if (Math.abs(v) >= 10000 && step >= 1000) return fmt(v);
    const decimals = Math.max(0, Math.min(6, -Math.floor(Math.log10(step) + 1e-9)));
    return v.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  }

  // One shared tooltip element. It lives in the dashboard's root so it picks up
  // the dashboard's styles (inside a shadow root when embedded).
  let tip;
  let tipHost = null;
  function setTooltipHost(node) {
    removeTooltip();
    tipHost = node;
  }
  function removeTooltip() {
    if (tip) tip.remove();
    tip = null;
  }
  function tooltip() {
    if (!tip) {
      tip = document.createElement("div");
      tip.className = "chart-tooltip";
      tip.setAttribute("role", "status");
      (tipHost || document.body).appendChild(tip);
    }
    return tip;
  }
  function showTip(html, clientX, clientY) {
    const t = tooltip();
    t.innerHTML = html;
    t.style.display = "block";
    const pad = 12;
    const w = t.offsetWidth;
    const h = t.offsetHeight;
    let x = clientX + pad;
    let y = clientY - h - pad;
    if (x + w > window.innerWidth - 8) x = clientX - w - pad;
    if (y < 8) y = clientY + pad;
    t.style.left = Math.max(8, x) + "px";
    t.style.top = y + "px";
  }
  function hideTip() { if (tip) tip.style.display = "none"; }

  function frame(container, height, xDom, yDom, xLabel, yLabel) {
    container.innerHTML = "";
    const width = Math.max(container.clientWidth, 260);
    const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, width: "100%", height, class: "chart-svg" }, container);
    const iw = width - MARGIN.left - MARGIN.right;
    const ih = height - MARGIN.top - MARGIN.bottom;
    const sx = (v) => MARGIN.left + ((v - xDom.lo) / (xDom.hi - xDom.lo)) * iw;
    const sy = (v) => MARGIN.top + ih - ((v - yDom.lo) / (yDom.hi - yDom.lo)) * ih;

    const grid = el("g", { class: "grid" }, svg);
    for (const t of yDom.ticks) {
      el("line", { x1: MARGIN.left, x2: MARGIN.left + iw, y1: sy(t), y2: sy(t) }, grid);
      const lbl = el("text", { x: MARGIN.left - 8, y: sy(t), class: "tick", "text-anchor": "end", "dominant-baseline": "middle" }, svg);
      lbl.textContent = tickFmt(t, yDom.ticks);
    }
    const xTicks = xDom.ticks.length > 8 ? xDom.ticks.filter((_, i) => i % 2 === 0) : xDom.ticks;
    for (const t of xTicks) {
      const lbl = el("text", { x: sx(t), y: MARGIN.top + ih + 18, class: "tick", "text-anchor": "middle" }, svg);
      lbl.textContent = tickFmt(t, xDom.ticks);
    }
    el("line", { x1: MARGIN.left, x2: MARGIN.left + iw, y1: MARGIN.top + ih, y2: MARGIN.top + ih, class: "baseline" }, svg);
    const xl = el("text", { x: MARGIN.left + iw / 2, y: height - 4, class: "axis-label", "text-anchor": "middle" }, svg);
    xl.textContent = xLabel;
    const yl = el("text", { x: 12, y: MARGIN.top + ih / 2, class: "axis-label", "text-anchor": "middle", transform: `rotate(-90 12 ${MARGIN.top + ih / 2})` }, svg);
    yl.textContent = yLabel;
    return { svg, sx, sy, iw, ih, width };
  }

  // Your-input marker: a diamond in primary ink with a surface ring and a label.
  function inputMarker(svg, x, y, label, width) {
    const g = el("g", { class: "input-marker" }, svg);
    const s = 7;
    el("path", { d: `M${x} ${y - s}L${x + s} ${y}L${x} ${y + s}L${x - s} ${y}Z` }, g);
    const right = x < width - 110;
    const t = el("text", { x: right ? x + 11 : x - 11, y: y - 9, "text-anchor": right ? "start" : "end", class: "marker-label" }, g);
    t.textContent = label;
  }

  /**
   * Scatter plot.
   * opts: { points: [{x, y, series, tip}], series: [{id, name, cls}],
   *         xLabel, yLabel, height, marker: {x, y, label} | null }
   */
  function scatter(container, opts) {
    const xs = opts.points.map((p) => p.x);
    const ys = opts.points.map((p) => p.y);
    if (opts.marker) { xs.push(opts.marker.x); ys.push(opts.marker.y); }
    const xDom = niceDomain(xs, 8);
    const yDom = niceDomain(ys, 5);
    const { svg, sx, sy, width } = frame(container, opts.height || 300, xDom, yDom, opts.xLabel, opts.yLabel);
    const dots = el("g", {}, svg);
    // Optional vertical dodge (px) so series at identical positions don't hide each other.
    const dodge = opts.dodge || 0;
    opts.series.forEach((s, si) => {
      const offset = (si - (opts.series.length - 1) / 2) * dodge;
      for (const p of opts.points.filter((q) => q.series === s.id)) {
        const c = el("circle", { cx: sx(p.x), cy: sy(p.y) + offset, r: 4.5, class: `dot ${s.cls}`, tabindex: 0 }, dots);
        c.setAttribute("aria-label", p.tip.replace(/<[^>]+>/g, " "));
        const show = (e) => {
          const r = c.getBoundingClientRect();
          showTip(p.tip, e.clientX ?? r.x + r.width / 2, e.clientY ?? r.y);
        };
        c.addEventListener("mousemove", show);
        c.addEventListener("focus", show);
        c.addEventListener("mouseleave", hideTip);
        c.addEventListener("blur", hideTip);
      }
    });
    if (opts.marker) inputMarker(svg, sx(opts.marker.x), sy(opts.marker.y), opts.marker.label, width);
  }

  /**
   * Line chart with crosshair tooltip. One series.
   * opts: { x: [], y: [], xLabel, yLabel, unit, height, ref: {value, label} | null }
   */
  function line(container, opts) {
    const pts = opts.x.map((x, i) => [x, opts.y[i]]).filter(([x, y]) => x != null && y != null);
    if (!pts.length) { container.innerHTML = '<p class="empty">No numeric values to plot.</p>'; return; }
    const ys = pts.map((p) => p[1]);
    if (opts.ref && opts.ref.value != null) ys.push(opts.ref.value);
    const xDom = niceDomain(pts.map((p) => p[0]), 6);
    const yDom = niceDomain(ys, 4);
    const { svg, sx, sy, iw, ih, width } = frame(container, opts.height || 180, xDom, yDom, opts.xLabel, opts.yLabel);

    const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${sx(x).toFixed(1)} ${sy(y).toFixed(1)}`).join("");
    el("path", { d, class: "series-line" }, svg);

    // Drawn after the data so the reference label stays readable.
    if (opts.ref && opts.ref.value != null) {
      const y = sy(opts.ref.value);
      el("line", { x1: MARGIN.left, x2: MARGIN.left + iw, y1: y, y2: y, class: "ref-line" }, svg);
      const below = y - MARGIN.top < 18;
      const t = el("text", { x: MARGIN.left + iw - 4, y: below ? y + 14 : y - 6, class: "marker-label", "text-anchor": "end" }, svg);
      t.textContent = opts.ref.label;
    }

    const cross = el("line", { y1: MARGIN.top, y2: MARGIN.top + ih, class: "crosshair", visibility: "hidden" }, svg);
    const dot = el("circle", { r: 4.5, class: "dot s1 hover-dot", visibility: "hidden" }, svg);
    const hit = el("rect", { x: MARGIN.left, y: MARGIN.top, width: iw, height: ih, fill: "transparent" }, svg);
    hit.addEventListener("mousemove", (e) => {
      const box = svg.getBoundingClientRect();
      const px = ((e.clientX - box.left) / box.width) * width;
      const xv = xDom.lo + ((px - MARGIN.left) / iw) * (xDom.hi - xDom.lo);
      let best = pts[0];
      for (const p of pts) if (Math.abs(p[0] - xv) < Math.abs(best[0] - xv)) best = p;
      cross.setAttribute("x1", sx(best[0]));
      cross.setAttribute("x2", sx(best[0]));
      cross.setAttribute("visibility", "visible");
      dot.setAttribute("cx", sx(best[0]));
      dot.setAttribute("cy", sy(best[1]));
      dot.setAttribute("visibility", "visible");
      showTip(`<strong>${fmt(best[1])} ${opts.unit || ""}</strong><br>${escapeHtml(opts.xLabel)}: ${fmt(best[0])}`, e.clientX, e.clientY);
    });
    hit.addEventListener("mouseleave", () => {
      cross.setAttribute("visibility", "hidden");
      dot.setAttribute("visibility", "hidden");
      hideTip();
    });
  }

  /**
   * Donut chart (part of a whole).
   * opts: { slices: [{ name, value, cls, tip }], size, center: { value, label }, label }
   * Slices are drawn in order, clockwise from 12 o'clock, with a surface-coloured
   * gap between them. Values must be >= 0; zero slices are skipped.
   */
  function donut(container, opts) {
    container.innerHTML = "";
    const size = opts.size || 200;
    const r = size / 2 - 4;
    const inner = r * 0.62;
    const cx = size / 2;
    const cy = size / 2;
    const slices = opts.slices.filter((s) => s.value > 0);
    const total = slices.reduce((a, s) => a + s.value, 0);
    const svg = el("svg", { viewBox: `0 0 ${size} ${size}`, width: size, height: size, class: "chart-svg donut", role: "img", "aria-label": opts.label || "" }, container);
    if (!total) {
      el("circle", { cx, cy, r: (r + inner) / 2, class: "donut-empty", "stroke-width": r - inner, fill: "none" }, svg);
    }
    const point = (radius, angle) => [cx + radius * Math.sin(angle), cy - radius * Math.cos(angle)];
    let start = 0;
    for (const s of slices) {
      const sweep = (s.value / total) * Math.PI * 2;
      let d;
      if (sweep >= Math.PI * 2 - 1e-9) {
        // A full ring needs two arcs.
        d = `M${cx} ${cy - r}A${r} ${r} 0 1 1 ${cx} ${cy + r}A${r} ${r} 0 1 1 ${cx} ${cy - r}Z` +
          `M${cx} ${cy - inner}A${inner} ${inner} 0 1 0 ${cx} ${cy + inner}A${inner} ${inner} 0 1 0 ${cx} ${cy - inner}Z`;
      } else {
        const end = start + sweep;
        const large = sweep > Math.PI ? 1 : 0;
        const [x1, y1] = point(r, start), [x2, y2] = point(r, end);
        const [x3, y3] = point(inner, end), [x4, y4] = point(inner, start);
        d = `M${x1} ${y1}A${r} ${r} 0 ${large} 1 ${x2} ${y2}L${x3} ${y3}A${inner} ${inner} 0 ${large} 0 ${x4} ${y4}Z`;
      }
      const path = el("path", { d, class: `donut-slice ${s.cls}`, "fill-rule": "evenodd", tabindex: 0 }, svg);
      path.setAttribute("aria-label", s.tip.replace(/<[^>]+>/g, " "));
      const show = (e) => {
        const b = path.getBoundingClientRect();
        showTip(s.tip, e.clientX ?? b.x + b.width / 2, e.clientY ?? b.y);
      };
      path.addEventListener("mousemove", show);
      path.addEventListener("focus", show);
      path.addEventListener("mouseleave", hideTip);
      path.addEventListener("blur", hideTip);
      start += sweep;
    }
    if (opts.center) {
      const v = el("text", { x: cx, y: cy - 2, class: "donut-value", "text-anchor": "middle" }, svg);
      v.textContent = opts.center.value;
      const l = el("text", { x: cx, y: cy + 16, class: "donut-label", "text-anchor": "middle" }, svg);
      l.textContent = opts.center.label;
    }
  }

  window.Charts = { scatter, line, donut, fmt, setTooltipHost, removeTooltip };
})();
