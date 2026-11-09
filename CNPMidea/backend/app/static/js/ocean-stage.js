/**
 * ============================================================================
 * SOOBIN OCEAN STAGE — Three.js WebGL sea surface for the storefront cover
 * ----------------------------------------------------------------------------
 * Theo antigravityrules.md (3D & Interactive Media): một mặt biển shader nhẹ,
 * tinh tế làm nền trang bìa. Sóng Gerstner-lite + phản chiếu mặt trời + sương
 * chân trời hoà vào bầu trời CSS. Đồng bộ với gsap.ticker (chung nhịp Lenis)
 * và nhận tiến trình cuộn để "lặn" xuống biển (setDive).
 *  - Tự tạm dừng khi ra khỏi màn hình / tab ẩn / đang ở trang danh mục.
 *  - prefers-reduced-motion: chỉ vẽ một khung tĩnh.
 * ============================================================================
 */
(function () {
  "use strict";

  const THREE = window.THREE;
  const canvas = document.getElementById("oceanCanvas");
  if (!THREE || !canvas) return;

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "low-power" });
  } catch (_) {
    canvas.style.display = "none";
    return;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.setClearColor(0x000000, 0);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 400);

  const MAX_RIPPLES = 8;
  const uniforms = {
    uTime: { value: 0 },
    uSunX: { value: 0.32 },
    uDive: { value: 0 },
    uDeep: { value: new THREE.Color("#0369a1") },
    uShallow: { value: new THREE.Color("#22d3ee") },
    uHorizon: { value: new THREE.Color("#dff3ff") },
    uAbyss: { value: new THREE.Color("#071e33") },
    // x, z (local plane coords), start time, strength — mouse-made ripples
    uRipples: { value: Array.from({ length: MAX_RIPPLES }, () => new THREE.Vector4(0, 0, -100, 0)) },
  };

  const vertexShader = /* glsl */ `
    uniform float uTime;
    uniform vec4 uRipples[${MAX_RIPPLES}];
    varying vec3 vWorld;
    varying vec3 vNormal;
    varying float vHeight;

    float wave(vec2 p, vec2 dir, float freq, float amp, float speed, inout vec2 grad) {
      float ph = dot(dir, p) * freq + uTime * speed;
      grad += dir * freq * amp * cos(ph);
      return amp * sin(ph);
    }

    void main() {
      vec3 p = position;
      vec2 g = vec2(0.0);
      float h = 0.0;
      h += wave(p.xz, normalize(vec2(1.0, 0.55)), 0.20, 0.46, 0.95, g);
      h += wave(p.xz, normalize(vec2(-0.65, 1.0)), 0.33, 0.24, 1.45, g);
      h += wave(p.xz, normalize(vec2(0.25, -1.0)), 0.58, 0.11, 2.05, g);
      h += wave(p.xz, normalize(vec2(1.0, -0.35)), 1.05, 0.05, 2.90, g);
      h += wave(p.xz, normalize(vec2(-1.0, -0.2)), 1.90, 0.022, 3.80, g);

      // Concentric ripples spawned by the cursor
      for (int i = 0; i < ${MAX_RIPPLES}; i++) {
        vec4 rp = uRipples[i];
        float age = uTime - rp.z;
        if (rp.w <= 0.0 || age < 0.0 || age > 5.0) continue;
        vec2 dv = p.xz - rp.xy;
        float d = length(dv) + 0.0001;
        float front = age * 3.4;
        float env = exp(-age * 0.75) * smoothstep(front + 1.2, front - 1.5, d) * exp(-d * 0.11);
        float k = 2.2;
        float ph = d * k - age * 7.5;
        float a = rp.w * 0.55 * env;
        h += a * sin(ph);
        g += (dv / d) * a * k * cos(ph);
      }

      p.y += h;
      vHeight = h;
      vNormal = normalize(vec3(-g.x, 1.0, -g.y));
      vec4 wp = modelMatrix * vec4(p, 1.0);
      vWorld = wp.xyz;
      gl_Position = projectionMatrix * viewMatrix * wp;
    }
  `;

  const fragmentShader = /* glsl */ `
    uniform vec3 uDeep;
    uniform vec3 uShallow;
    uniform vec3 uHorizon;
    uniform vec3 uAbyss;
    uniform float uSunX;
    uniform float uDive;
    varying vec3 vWorld;
    varying vec3 vNormal;
    varying float vHeight;

    void main() {
      vec3 n = normalize(vNormal);
      vec3 viewDir = normalize(cameraPosition - vWorld);
      float fres = pow(1.0 - max(dot(n, viewDir), 0.0), 3.0);

      vec3 sunDir = normalize(vec3(uSunX, 0.30, -1.0));
      vec3 refl = reflect(-viewDir, n);
      float rs = max(dot(refl, sunDir), 0.0);
      float spec = pow(rs, 220.0) * 1.8 + pow(rs, 26.0) * 0.22;

      float crest = smoothstep(-0.55, 0.65, vHeight);
      vec3 col = mix(uDeep, uShallow, crest * 0.62 + 0.12);
      col = mix(col, uHorizon, fres * 0.6);
      col += vec3(1.0, 0.97, 0.86) * spec;
      col = mix(col, vec3(1.0), smoothstep(0.50, 0.78, vHeight) * 0.28);

      float dist = length(cameraPosition.xz - vWorld.xz);
      float fog = smoothstep(28.0, 120.0, dist);
      col = mix(col, uHorizon, fog);

      col = mix(col, uAbyss, uDive);
      gl_FragColor = vec4(col, 1.0);
    }
  `;

  const geometry = new THREE.PlaneGeometry(320, 220, 220, 150);
  geometry.rotateX(-Math.PI / 2);
  const material = new THREE.ShaderMaterial({ uniforms, vertexShader, fragmentShader });
  const sea = new THREE.Mesh(geometry, material);
  sea.position.z = -70;
  scene.add(sea);

  // Camera rig: calm horizon at rest -> dives below the surface while scrolling
  const rig = { y: 4.2, lookY: 6.0, sway: 0, swayTarget: 0, dive: 0 };
  function placeCamera() {
    const d = rig.dive;
    // Lower towards the waves and pitch down until the sea fills the frame
    const y = rig.y - d * 2.8;
    const lookY = rig.lookY - d * 38.0;
    camera.position.set(rig.sway * 1.2, y, 14);
    camera.lookAt(rig.sway * 3.0, lookY, -20);
  }

  function resize() {
    const w = canvas.clientWidth || canvas.parentElement.clientWidth;
    const h = canvas.clientHeight || canvas.parentElement.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    // Keep the horizon framing pleasant on tall (mobile) screens
    camera.fov = camera.aspect < 0.8 ? 58 : 45;
    camera.updateProjectionMatrix();
    renderOnce();
  }

  function renderOnce() {
    placeCamera();
    renderer.render(scene, camera);
  }

  // Visibility gating
  let onScreen = true;
  let enabled = true;
  if ("IntersectionObserver" in window) {
    new IntersectionObserver((entries) => {
      onScreen = entries[0].isIntersecting;
    }, { threshold: 0 }).observe(canvas);
  }

  // Pointer: sun glint & camera sway follow the cursor softly
  window.addEventListener("pointermove", (e) => {
    const nx = e.clientX / window.innerWidth - 0.5;
    rig.swayTarget = nx * 0.6;
    uniforms.uSunX.value = 0.32 + nx * 0.25;
    maybeRipple(e, 0.75, false);
  }, { passive: true });
  window.addEventListener("pointerdown", (e) => maybeRipple(e, 1.6, true), { passive: true });

  // Cursor → ray → sea plane (y = 0) → ripple in local plane coordinates
  const raycaster = new THREE.Raycaster();
  const seaPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const ndc = new THREE.Vector2();
  const hit = new THREE.Vector3();
  let rippleCursor = 0;
  let lastRipple = { x: 1e9, z: 1e9, t: 0 };

  function maybeRipple(e, strength, force) {
    if (reduceMotion || !enabled || !onScreen || rig.dive > 0.5) return;
    const rect = canvas.getBoundingClientRect();
    if (e.clientY < rect.top || e.clientY > rect.bottom || e.clientX < rect.left || e.clientX > rect.right) return;
    ndc.set(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1);
    raycaster.setFromCamera(ndc, camera);
    if (!raycaster.ray.intersectPlane(seaPlane, hit)) return;
    const lx = hit.x - sea.position.x;
    const lz = hit.z - sea.position.z;
    const now = uniforms.uTime.value;
    const moved = Math.hypot(lx - lastRipple.x, lz - lastRipple.z);
    if (!force && (moved < 1.6 || now - lastRipple.t < 0.12)) return;
    lastRipple = { x: lx, z: lz, t: now };
    // Farther water needs bigger rings to stay visible
    const distBoost = Math.min(2.2, 1 + Math.max(0, -hit.z) / 30);
    uniforms.uRipples.value[rippleCursor].set(lx, lz, now, strength * distBoost);
    rippleCursor = (rippleCursor + 1) % MAX_RIPPLES;
  }

  let elapsed = 0;
  function tick(_time, deltaMs) {
    if (!enabled || !onScreen || document.hidden) return;
    const dt = Math.min(0.05, (deltaMs || 16) / 1000);
    elapsed += dt;
    uniforms.uTime.value = elapsed;
    rig.sway += (rig.swayTarget - rig.sway) * 0.04;
    renderOnce();
  }

  window.addEventListener("resize", resize);
  resize();

  if (reduceMotion) {
    uniforms.uTime.value = 2.0;
    renderOnce();
  } else if (window.gsap) {
    window.gsap.ticker.add(tick);
  } else {
    let last = performance.now();
    const loop = (now) => {
      tick(now, now - last);
      last = now;
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  window.soobinOcean = {
    /** p: 0 → 1 tiến trình cuộn của trang bìa (lặn xuống biển). */
    setDive(p) {
      const v = Math.max(0, Math.min(1, p));
      rig.dive = v;
      uniforms.uDive.value = Math.max(0, (v - 0.55) / 0.45);
      if (reduceMotion || !onScreen) renderOnce();
    },
    pause() { enabled = false; },
    resume() { enabled = true; resize(); },
  };
})();
