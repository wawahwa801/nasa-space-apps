"use client";

// Eclipse shader adapted from GradFlow by Meer bahadin (MIT).
// https://github.com/meerbahadin/gradflow/blob/main/src/core/shader.ts
// See black-hole.LICENSE.txt for the license notice.
import { useEffect, useRef } from "react";

const vertexSource = `
  attribute vec2 position;
  varying vec2 vUv;

  void main() {
    vUv = position * 0.5 + 0.5;
    gl_Position = vec4(position, 0.0, 1.0);
  }
`;
const fragmentSource = `  #ifdef GL_FRAGMENT_PRECISION_HIGH
    precision highp float;
  #else
    precision mediump float;
  #endif

  uniform float u_time;
  uniform vec3 u_color1;
  uniform vec3 u_color2;
  uniform vec3 u_color3;
  uniform float u_scale;
  uniform float u_noise;
  uniform vec2 u_resolution;
  varying vec2 vUv;
  float noise(vec2 st) {
    return fract(sin(dot(st, vec2(12.9898, 78.233))) * 43758.5453);
  }
  vec2 centered(vec2 uv) {
    vec2 p = uv - 0.5;
    p.x *= u_resolution.x / max(u_resolution.y, 1.0);
    return p;
  }

  // @Gradient Types (next)

  // the sun behind a moon: a dark disc with a crisp bright rim and a long soft
  // corona outside it. One side burns brighter, and that side drifts around.
  vec3 eclipseGradient(vec2 uv, float time) {
    vec2 p = centered(uv) * 2.0;
    float t = time * 0.6;

    float r = length(p);
    float a = atan(p.y, p.x);
    float radius = 0.58 / sqrt(max(u_scale, 0.05));

    // whole multiples of the angle only, so the atan seam never shows
    float wobble = 0.007 * sin(a * 3.0 + t * 0.7) + 0.004 * sin(a * 5.0 - t * 0.5);
    float d = r - radius - wobble;
    float away = max(d, 0.0);

    float arc = 0.5 + 0.5 * cos(a - t * 0.35 - 1.2);
    arc *= arc;

    float outside = smoothstep(-0.05, 0.0, d);
    float corona = exp(-away * (6.5 - 4.0 * arc)) * outside;
    float rim = exp(-abs(d) * 46.0);
    float flare = exp(-away * 2.2) * arc * outside;

    vec3 color = u_color2 * (1.0 - 0.45 * smoothstep(0.0, 1.8, r));
    // the disc itself, a shade under the sky around it
    color *= mix(0.4, 1.0, smoothstep(-0.3, 0.02, d));

    color += u_color1 * (corona * (0.5 + 0.5 * arc) + flare * 0.35);
    color += u_color3 * (rim * (0.35 + 0.65 * arc) + corona * corona * arc * 0.55);

    return clamp(color, 0.0, 1.0);
  }

  void main() {
    vec3 color = eclipseGradient(vUv, u_time);
    float grain = noise(vUv * 200.0 + u_time * 0.1);
    color *= 1.0 - u_noise * 0.4 + u_noise * grain * 0.4;
    gl_FragColor = vec4(color, 1.0);
  }
`;

function rgb(hex) {
  return [1, 3, 5].map(
    (offset) => parseInt(hex.slice(offset, offset + 2), 16) / 255,
  );
}

export function BlackHole({
  color1 = "#ff7a14",
  color2 = "#161616",
  color3 = "#ffa25b",
  speed = 0.6,
  scale = 1.2,
  noise = 0.14,
  className = "",
}) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const gl = canvas.getContext("webgl", {
      alpha: false,
      antialias: false,
      depth: false,
      powerPreference: "low-power",
    });
    if (!gl) return;

    let frame = 0;
    let previousTime = null;
    let elapsed = 0;
    let program = null;
    let buffer = null;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");

    function dispose() {
      cancelAnimationFrame(frame);
      frame = 0;
      if (buffer) gl.deleteBuffer(buffer);
      if (program) gl.deleteProgram(program);
      program = null;
      buffer = null;
    }

    function setup() {
      const shaders = [];
      for (const [type, source] of [
        [gl.VERTEX_SHADER, vertexSource],
        [gl.FRAGMENT_SHADER, fragmentSource],
      ]) {
        const shader = gl.createShader(type);
        if (!shader) {
          shaders.forEach((s) => gl.deleteShader(s));
          return;
        }
        gl.shaderSource(shader, source);
        gl.compileShader(shader);
        shaders.push(shader);
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
          shaders.forEach((s) => gl.deleteShader(s));
          return;
        }
      }
      program = gl.createProgram();
      if (!program) {
        shaders.forEach((s) => gl.deleteShader(s));
        return;
      }
      shaders.forEach((s) => gl.attachShader(program, s));
      gl.bindAttribLocation(program, 0, "position");
      gl.linkProgram(program);
      shaders.forEach((s) => gl.deleteShader(s));
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
        dispose();
        return;
      }
      buffer = gl.createBuffer();
      if (!buffer) {
        dispose();
        return;
      }
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(
        gl.ARRAY_BUFFER,
        new Float32Array([-1, -1, 3, -1, -1, 3]),
        gl.STATIC_DRAW,
      );
      gl.enableVertexAttribArray(0);
      gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
      gl.useProgram(program);
      for (const [name, value] of [
        ["u_color1", color1],
        ["u_color2", color2],
        ["u_color3", color3],
      ]) {
        gl.uniform3fv(gl.getUniformLocation(program, name), rgb(value));
      }
      gl.uniform1f(gl.getUniformLocation(program, "u_scale"), scale);
      gl.uniform1f(gl.getUniformLocation(program, "u_noise"), noise);
    }

    function draw(now) {
      frame = 0;
      if (!program || gl.isContextLost()) return;
      if (previousTime !== null && !motion.matches)
        elapsed += Math.min((now - previousTime) / 1000, 0.1) * speed;
      previousTime = now;
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      // Bound rendering cost on high-density and large displays.
      const ratio = Math.min(
        window.devicePixelRatio || 1,
        1.5,
        1920 / Math.max(width, height, 1),
      );
      const pixelWidth = Math.max(1, Math.round(width * ratio));
      const pixelHeight = Math.max(1, Math.round(height * ratio));
      if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
        canvas.width = pixelWidth;
        canvas.height = pixelHeight;
      }
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform2f(
        gl.getUniformLocation(program, "u_resolution"),
        width,
        height,
      );
      gl.uniform1f(gl.getUniformLocation(program, "u_time"), elapsed);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      canvas.style.opacity = "1";
      if (!motion.matches && !document.hidden && speed !== 0)
        frame = requestAnimationFrame(draw);
    }

    function restart() {
      cancelAnimationFrame(frame);
      frame = 0;
      previousTime = null;
      if (!document.hidden) draw(performance.now());
    }
    function lost(event) {
      event.preventDefault();
      cancelAnimationFrame(frame);
      frame = 0;
      program = null;
      buffer = null;
      canvas.style.opacity = "0";
    }
    function restored() {
      setup();
      restart();
    }
    const observer = new ResizeObserver(restart);
    observer.observe(canvas);
    motion.addEventListener("change", restart);
    document.addEventListener("visibilitychange", restart);
    canvas.addEventListener("webglcontextlost", lost);
    canvas.addEventListener("webglcontextrestored", restored);
    setup();
    restart();
    return () => {
      dispose();
      observer.disconnect();
      motion.removeEventListener("change", restart);
      document.removeEventListener("visibilitychange", restart);
      canvas.removeEventListener("webglcontextlost", lost);
      canvas.removeEventListener("webglcontextrestored", restored);
      canvas.style.opacity = "0";
    };
  }, [color1, color2, color3, speed, scale, noise]);

  return (
    <div
      className={`black-hole ${className}`}
      aria-hidden="true"
      style={{
        background: `radial-gradient(ellipse at 58% 43%, ${color2} 0%, ${color2} 18%, ${color3} 20%, ${color1} 23%, ${color2} 65%)`,
      }}
    >
      <canvas ref={canvasRef} style={{ opacity: 0 }} />
    </div>
  );
}
