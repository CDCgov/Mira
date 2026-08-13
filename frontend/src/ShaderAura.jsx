import { useEffect, useRef } from "react";

/**
 * ShaderAura renders an animated GLSL fragment shader onto a transparent
 * <canvas>, producing a flowing "smokey" aura that sits behind another element
 * (e.g. a logo). Raw WebGL — no external dependencies.
 *
 * The shader builds a soft, animated smoke-like haze using fractal value noise
 * (fbm) domain-warped over time, tinted in CDC-blue → cyan → white, with an
 * alpha falloff so it blends over whatever is behind it.
 */

const VERTEX_SRC = `
attribute vec2 a_position;
void main() {
  gl_Position = vec4(a_position, 0.0, 1.0);
}
`;

const FRAGMENT_SRC = `
precision highp float;

uniform vec2  u_resolution;
uniform float u_time;
uniform vec3  u_bannerColor; // live --primary color so the smoke matches exactly

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  float a = hash(i);
  float b = hash(i + vec2(1.0, 0.0));
  float c = hash(i + vec2(0.0, 1.0));
  float d = hash(i + vec2(1.0, 1.0));
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}

float fbm(vec2 p) {
  float v = 0.0;
  float amp = 0.5;
  for (int i = 0; i < 5; i++) {
    v += amp * noise(p);
    p *= 2.0;
    amp *= 0.5;
  }
  return v;
}

void main() {
  vec2 uv = (gl_FragCoord.xy - 0.5 * u_resolution.xy) / min(u_resolution.x, u_resolution.y);
  float t = u_time * 0.25;

  // Domain-warped fractal noise for a living, swirling smoke texture.
  vec2 q = vec2(fbm(uv * 3.0 + t), fbm(uv * 3.0 - t + 5.2));
  float n = fbm(uv * 3.0 + q * 1.5 + t * 0.5);

  // Smoke that hugs the logo. Instead of a clean ring, the radius wobbles with
  // angular noise and the density is turbulent, so the boundary is wavy and
  // broken into wisps. It still fades fully before the canvas corners
  // (r < 0.5), so there is no visible square and it dissolves into the banner.
  float r = length(uv);
  float ang = atan(uv.y, uv.x);

  // Turbulent, angularly-varying density → breaks the circular symmetry.
  float density = fbm(uv * 5.0 + q * 1.8 + vec2(t * 0.5, -t * 0.4));
  density = pow(clamp(density, 0.0, 1.0), 1.8);

  // Wobbling ring radius so the smoke boundary is wavy, not a perfect circle.
  float wob = (fbm(vec2(ang * 2.0, r * 3.0) + t) - 0.5) * 0.14;
  float ringR = 0.42 + wob;
  float band = exp(-pow(r - ringR, 2.0) / 0.006);

  // Hard fade to transparent before the corners → seamless, no square.
  float clip = 1.0 - smoothstep(0.46, 0.50, r);

  float intensity = band * (0.20 + 0.80 * density) * clip;

  // Base tint is the live banner color (--primary), so the faint edges of the
  // smoke blend seamlessly in both light and dark themes; cyan/white are the
  // highlights layered on top.
  vec3 col = mix(u_bannerColor, vec3(0.35, 0.75, 1.0), n);
  col = mix(col, vec3(1.0), pow(n, 3.0) * 0.6);

  float alpha = clamp(intensity * 1.7, 0.0, 1.0);
  gl_FragColor = vec4(col, alpha);
}
`;

function compileShader(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(shader);
    gl.deleteShader(shader);
    throw new Error("Shader compile error: " + log);
  }
  return shader;
}

// Convert an HSL CSS-variable string like "211 100% 36%" into linear [0..1] RGB.
function hslVarToRgb(str) {
  const m = String(str).match(/(-?[\d.]+)\s+(-?[\d.]+)%\s+(-?[\d.]+)%/);
  if (!m) return null;
  const h = parseFloat(m[1]);
  const s = parseFloat(m[2]) / 100;
  const l = parseFloat(m[3]) / 100;
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const mm = l - c / 2;
  let r = 0;
  let g = 0;
  let b = 0;
  if (h < 60) [r, g, b] = [c, x, 0];
  else if (h < 120) [r, g, b] = [x, c, 0];
  else if (h < 180) [r, g, b] = [0, c, x];
  else if (h < 240) [r, g, b] = [0, x, c];
  else if (h < 300) [r, g, b] = [x, 0, c];
  else [r, g, b] = [c, 0, x];
  return [r + mm, g + mm, b + mm];
}

export default function ShaderAura({ className = "" }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const gl = canvas.getContext("webgl", { premultipliedAlpha: false, antialias: true });
    if (!gl) return; // WebGL unsupported — fail silently, nothing renders.

    let program;
    let raf = 0;
    let disposed = false;

    try {
      const vs = compileShader(gl, gl.VERTEX_SHADER, VERTEX_SRC);
      const fs = compileShader(gl, gl.FRAGMENT_SHADER, FRAGMENT_SRC);
      program = gl.createProgram();
      gl.attachShader(program, vs);
      gl.attachShader(program, fs);
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
        throw new Error("Program link error: " + gl.getProgramInfoLog(program));
      }
      gl.deleteShader(vs);
      gl.deleteShader(fs);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn("ShaderAura disabled:", err);
      return;
    }

    // Full-screen triangle covering the clip space.
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);

    const posLoc = gl.getAttribLocation(program, "a_position");
    const resLoc = gl.getUniformLocation(program, "u_resolution");
    const timeLoc = gl.getUniformLocation(program, "u_time");
    const bannerLoc = gl.getUniformLocation(program, "u_bannerColor");

    gl.useProgram(program);
    gl.enableVertexAttribArray(posLoc);
    gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

    // Read the live --primary color and push it to the shader so the smoke's
    // base tint matches the banner exactly; refresh it when the theme changes.
    function updateBannerColor() {
      const raw = getComputedStyle(document.documentElement).getPropertyValue("--primary");
      const rgb = hslVarToRgb(raw) || [0.0, 0.348, 0.72];
      gl.useProgram(program);
      gl.uniform3f(bannerLoc, rgb[0], rgb[1], rgb[2]);
    }
    updateBannerColor();
    const themeObserver = new MutationObserver(updateBannerColor);
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class", "style", "data-theme"],
    });

    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    function resize() {
      const rect = canvas.getBoundingClientRect();
      const w = Math.max(1, Math.round(rect.width * dpr));
      const h = Math.max(1, Math.round(rect.height * dpr));
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform2f(resLoc, canvas.width, canvas.height);
    }

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const start = performance.now();

    function render(now) {
      if (disposed) return;
      resize();
      gl.uniform1f(timeLoc, (now - start) / 1000);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      if (!reduceMotion) raf = requestAnimationFrame(render);
    }

    raf = requestAnimationFrame(render);

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      themeObserver.disconnect();
      gl.deleteBuffer(buffer);
      gl.deleteProgram(program);
    };
  }, []);

  return <canvas ref={canvasRef} aria-hidden="true" className={className} />;
}
