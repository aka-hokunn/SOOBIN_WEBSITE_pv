/**
 * ============================================================================
 * SOOBIN WATER CURSOR — con trỏ chuột tạo gợn sóng nước
 * ----------------------------------------------------------------------------
 *  - Di chuột: các vòng sóng lan toả nhẹ theo vệt di chuyển + giọt nước phát sáng
 *    bám theo con trỏ (nội suy mượt).
 *  - Click: "té nước" — 3 vòng sóng lớn + giọt nước bắn ra.
 *  - Một canvas toàn màn hình (pointer-events: none), chỉ vẽ khi có sóng → nhẹ CPU.
 *  - Tắt trên thiết bị cảm ứng (chỉ giữ hiệu ứng chạm) & prefers-reduced-motion.
 * ============================================================================
 */
(function () {
  "use strict";

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;

  window.__soobinWaterCursor = true;

  const cv = document.createElement("canvas");
  cv.id = "soobinWaterCursor";
  cv.setAttribute("aria-hidden", "true");
  Object.assign(cv.style, { position: "fixed", inset: "0", width: "100vw", height: "100vh", pointerEvents: "none", zIndex: "10060" });
  const c = cv.getContext("2d");
  let dpr = 1, W = 0, H = 0;

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = cv.width = Math.floor(innerWidth * dpr);
    H = cv.height = Math.floor(innerHeight * dpr);
  }

  const ripples = [];
  const drops = [];
  const pointer = { x: -100, y: -100, tx: -100, ty: -100, visible: false, lastX: 0, lastY: 0, lastT: 0, overDark: false };
  let running = false;

  function addRipple(x, y, maxR, life, strength = 1, delay = 0) {
    ripples.push({ x, y, maxR: maxR * dpr, life, t0: performance.now() + delay, strength });
    if (ripples.length > 60) ripples.shift();
    wake();
  }

  function splash(x, y) {
    addRipple(x, y, 74, 1100, 1.25);
    addRipple(x, y, 52, 950, 1, 90);
    addRipple(x, y, 30, 800, 0.9, 180);
    for (let i = 0; i < 10; i++) {
      const a = (i / 10) * Math.PI * 2 + Math.random() * 0.4;
      const sp = (1.6 + Math.random() * 2.6) * dpr;
      drops.push({ x: x * dpr, y: y * dpr, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp - 2.2 * dpr, life: 40 + Math.random() * 20, age: 0, r: (1.4 + Math.random() * 1.8) * dpr });
    }
    wake();
  }

  function wake() {
    if (running) return;
    running = true;
    requestAnimationFrame(frame);
  }

  function frame(now) {
    c.clearRect(0, 0, W, H);
    const tint = pointer.overDark ? "186, 230, 253" : "2, 132, 199";
    for (let i = ripples.length - 1; i >= 0; i--) {
      const r = ripples[i];
      const t = (now - r.t0) / r.life;
      if (t < 0) continue;
      if (t >= 1) { ripples.splice(i, 1); continue; }
      const ease = 1 - Math.pow(1 - t, 3);
      const rad = 3 * dpr + ease * r.maxR;
      const alpha = (1 - t) * 0.75 * r.strength;
      const x = r.x * dpr, y = r.y * dpr;
      // Main ring (slightly flattened = water surface perspective)
      c.lineWidth = Math.max(0.8, 2.2 * (1 - t)) * dpr;
      c.strokeStyle = `rgba(${tint}, ${alpha})`;
      c.beginPath(); c.ellipse(x, y, rad, rad * 0.62, 0, 0, Math.PI * 2); c.stroke();
      // Inner highlight ring
      c.lineWidth = Math.max(0.6, 1.2 * (1 - t)) * dpr;
      c.strokeStyle = `rgba(255, 255, 255, ${alpha * 0.85})`;
      c.beginPath(); c.ellipse(x, y - 1 * dpr, rad * 0.72, rad * 0.72 * 0.62, 0, Math.PI * 1.05, Math.PI * 1.95); c.stroke();
    }

    for (let i = drops.length - 1; i >= 0; i--) {
      const d = drops[i];
      d.vy += 0.16 * dpr; d.x += d.vx; d.y += d.vy; d.age++;
      const a = 1 - d.age / d.life;
      if (a <= 0) { drops.splice(i, 1); continue; }
      c.fillStyle = `rgba(${tint}, ${a * 0.9})`;
      c.beginPath(); c.arc(d.x, d.y, d.r, 0, Math.PI * 2); c.fill();
      c.fillStyle = `rgba(255,255,255,${a * 0.9})`;
      c.beginPath(); c.arc(d.x - d.r * 0.3, d.y - d.r * 0.3, d.r * 0.35, 0, Math.PI * 2); c.fill();
    }

    // Glowing droplet that follows the cursor
    let following = false;
    if (finePointer && pointer.visible) {
      pointer.x += (pointer.tx - pointer.x) * 0.2;
      pointer.y += (pointer.ty - pointer.y) * 0.2;
      const x = pointer.x * dpr, y = pointer.y * dpr;
      const g = c.createRadialGradient(x, y, 0, x, y, 16 * dpr);
      g.addColorStop(0, `rgba(${tint}, 0.30)`);
      g.addColorStop(1, `rgba(${tint}, 0)`);
      c.fillStyle = g;
      c.beginPath(); c.arc(x, y, 16 * dpr, 0, Math.PI * 2); c.fill();
      following = Math.abs(pointer.tx - pointer.x) > 0.3 || Math.abs(pointer.ty - pointer.y) > 0.3;
    }

    if (ripples.length || drops.length || following) requestAnimationFrame(frame);
    else running = false; // last frame already painted the resting glow
  }

  function isDarkAt(el) {
    return !!(el && el.closest && el.closest("#showcaseHot, #beachZoom .bz-intro, #luckyWheelTeaser, #luckyWheelModal, footer, .footer-wave, .cover-dive-shade"));
  }

  function onMove(e) {
    if (e.pointerType && e.pointerType !== "mouse") return;
    pointer.tx = e.clientX; pointer.ty = e.clientY;
    if (!pointer.visible) { pointer.x = e.clientX; pointer.y = e.clientY; pointer.visible = true; }
    pointer.overDark = isDarkAt(e.target);
    const now = performance.now();
    const dx = e.clientX - pointer.lastX, dy = e.clientY - pointer.lastY;
    const dist = Math.hypot(dx, dy);
    if (dist > 34 || (dist > 8 && now - pointer.lastT > 120)) {
      const speed = Math.min(1, dist / 120);
      addRipple(e.clientX, e.clientY, 18 + speed * 22, 900, 0.55 + speed * 0.5);
      pointer.lastX = e.clientX; pointer.lastY = e.clientY; pointer.lastT = now;
    }
    wake();
  }

  function onDown(e) {
    if (e.button !== undefined && e.button !== 0) return;
    pointer.overDark = isDarkAt(e.target);
    splash(e.clientX, e.clientY);
  }

  function boot() {
    resize();
    document.body.appendChild(cv);
    window.addEventListener("resize", resize);
    if (finePointer) {
      window.addEventListener("pointermove", onMove, { passive: true });
      document.addEventListener("mouseleave", () => { pointer.visible = false; wake(); });
    }
    window.addEventListener("pointerdown", onDown, { passive: true });
  }

  window.soobinWaterCursor = { splash, ripple: addRipple };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
