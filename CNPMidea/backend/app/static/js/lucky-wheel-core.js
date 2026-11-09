/**
 * ============================================================================
 * SOOBIN LUCKY WHEEL CORE — SVG wheel renderer + GSAP spin physics
 * Dùng chung cho: cửa hàng (khách quay) và bản xem trước ở cổng Admin/Manager.
 * ============================================================================
 */
(function () {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";
  let uid = 0;

  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function pt(deg, r) {
    const rad = (deg * Math.PI) / 180;
    return [+(r * Math.sin(rad)).toFixed(2), +(-r * Math.cos(rad)).toFixed(2)];
  }

  function splitLabel(text, max = 12) {
    const words = String(text || "").trim().split(/\s+/);
    const lines = [];
    let line = "";
    words.forEach((w) => {
      if ((line + " " + w).trim().length > max && line) {
        lines.push(line);
        line = w;
      } else {
        line = (line + " " + w).trim();
      }
    });
    if (line) lines.push(line);
    return lines.slice(0, 2);
  }

  function shade(hex, amt) {
    let c = String(hex || "#0ea5e9").replace("#", "");
    if (c.length === 3) c = c.split("").map((x) => x + x).join("");
    const n = parseInt(c, 16);
    const clamp = (v) => Math.max(0, Math.min(255, v));
    const r = clamp((n >> 16) + amt), g = clamp(((n >> 8) & 0xff) + amt), b = clamp((n & 0xff) + amt);
    return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
  }

  function slotTexts(slot) {
    const pct = slot.discount_percent;
    if (slot.is_prize && pct) {
      const label = String(slot.label || "");
      const generic = /^giảm\s*\d+([.,]\d+)?\s*%$/i.test(label.trim());
      // Drop the percentage from custom labels (it is already shown big), e.g. "JACKPOT -50%" → "JACKPOT"
      const custom = label.replace(/[-–]?\s*\d+([.,]\d+)?\s*%/g, "").trim();
      return { big: `-${Number(pct).toString().replace(/\.0+$/, "")}%`, small: generic || !custom ? "VOUCHER" : custom.toUpperCase().slice(0, 12), prize: true };
    }
    return { lines: splitLabel(slot.label || "Chúc may mắn"), prize: false };
  }

  /**
   * Render a wheel into `host`. slots: [{label,color,is_prize,discount_percent,in_stock}]
   * Returns a controller with spinTo(index) and destroy().
   */
  function mount(host, slots, opts = {}) {
    const id = `sw${++uid}`;
    const n = Math.max(2, slots.length);
    const a = 360 / n;
    const R = 198;

    const segs = slots.map((s, i) => {
      const a0 = i * a, a1 = (i + 1) * a;
      const [x0, y0] = pt(a0, R), [x1, y1] = pt(a1, R);
      const large = a > 180 ? 1 : 0;
      const base = s.color || "#0ea5e9";
      const c = a0 + a / 2;
      const t = slotTexts(s);
      let label;
      if (t.prize) {
        label = `
          <text class="sw-txt-big" y="${-R * 0.64}" text-anchor="middle">${esc(t.big)}</text>
          <text class="sw-txt-small" y="${-R * 0.64 + 20}" text-anchor="middle">${esc(t.small)}</text>
          <text class="sw-txt-icon" y="${-R * 0.33}" text-anchor="middle">🎁</text>`;
      } else {
        const ls = t.lines;
        label = `<text class="sw-txt-icon" y="${-R * 0.74}" text-anchor="middle">🌊</text>` +
          ls.map((l, k) => `<text class="sw-txt-mid" y="${-R * 0.56 + k * 16}" text-anchor="middle">${esc(l)}</text>`).join("");
      }
      return `
        <path d="M0 0 L${x0} ${y0} A${R} ${R} 0 ${large} 1 ${x1} ${y1} Z" fill="url(#${id}-g${i})" class="sw-seg ${s.in_stock === false && s.is_prize ? "is-out" : ""}" data-i="${i}"></path>
        <linearGradient id="${id}-g${i}" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="${pt(c, R)[0]}" y2="${pt(c, R)[1]}">
          <stop offset="0" stop-color="${shade(base, 40)}"/><stop offset="1" stop-color="${shade(base, -18)}"/>
        </linearGradient>
        <g transform="rotate(${c.toFixed(2)})">${label}</g>`;
    }).join("");

    const separators = slots.map((_, i) => {
      const [x, y] = pt(i * a, R);
      return `<line x1="0" y1="0" x2="${x}" y2="${y}" class="sw-sep"></line>`;
    }).join("");

    const bulbs = Array.from({ length: n * 2 }, (_, i) => {
      const [x, y] = pt(i * (a / 2) + a / 4, 212);
      return `<circle cx="${x}" cy="${y}" r="5.2" class="sw-bulb ${i % 2 ? "b" : "a"}"></circle>`;
    }).join("");

    host.innerHTML = `
      <div class="sw-wrap ${opts.compact ? "is-compact" : ""}">
        <svg class="sw-svg" viewBox="-236 -246 472 482" role="img" aria-label="Vòng quay may mắn">
          <defs>
            <linearGradient id="${id}-rim" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stop-color="#fde68a"/><stop offset="0.35" stop-color="#f59e0b"/>
              <stop offset="0.65" stop-color="#b45309"/><stop offset="1" stop-color="#fcd34d"/>
            </linearGradient>
            <radialGradient id="${id}-gloss" cx="50%" cy="38%" r="62%">
              <stop offset="0" stop-color="#fff" stop-opacity="0.32"/><stop offset="0.55" stop-color="#fff" stop-opacity="0.05"/>
              <stop offset="1" stop-color="#000" stop-opacity="0.18"/>
            </radialGradient>
            <radialGradient id="${id}-hub" cx="40%" cy="35%" r="70%">
              <stop offset="0" stop-color="#ffffff"/><stop offset="0.45" stop-color="#e0f2fe"/><stop offset="1" stop-color="#0284c7"/>
            </radialGradient>
            <filter id="${id}-sh" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="#020617" flood-opacity="0.45"/>
            </filter>
          </defs>
          <circle r="226" fill="url(#${id}-rim)" filter="url(#${id}-sh)"></circle>
          <circle r="203" fill="#0c4a6e"></circle>
          <g class="sw-bulbs">${bulbs}</g>
          <g class="sw-rotor">
            ${segs}
            ${separators}
            <circle r="${R}" fill="url(#${id}-gloss)" pointer-events="none"></circle>
            <circle r="${R * 0.26}" fill="none" stroke="rgba(255,255,255,0.35)" stroke-width="2" stroke-dasharray="4 6"></circle>
          </g>
          <g class="sw-hub" tabindex="0" role="button" aria-label="Quay">
            <circle r="52" fill="#0c4a6e" opacity="0.35" class="sw-hub-pulse"></circle>
            <circle r="46" fill="url(#${id}-rim)"></circle>
            <circle r="39" fill="url(#${id}-hub)"></circle>
            <text class="sw-hub-txt" y="7" text-anchor="middle">${esc(opts.hubText || "QUAY")}</text>
          </g>
          <g class="sw-pointer">
            <path d="M0 -176 L-19 -228 Q0 -246 19 -228 Z" fill="url(#${id}-rim)" stroke="#78350f" stroke-width="3" stroke-linejoin="round"></path>
            <circle cx="0" cy="-226" r="6" fill="#fff" stroke="#78350f" stroke-width="2.5"></circle>
          </g>
        </svg>
      </div>`;

    const svg = host.querySelector(".sw-svg");
    const rotor = host.querySelector(".sw-rotor");
    const pointer = host.querySelector(".sw-pointer");
    const hub = host.querySelector(".sw-hub");
    const state = { rot: 0, spinning: false, idleTween: null };
    const gsap = window.gsap;

    function setRot(v) {
      state.rot = v;
      if (gsap) gsap.set(rotor, { rotation: v, svgOrigin: "0 0" });
      else rotor.setAttribute("transform", `rotate(${v})`);
    }

    function idle(on) {
      if (!gsap) return;
      if (state.idleTween) { state.idleTween.kill(); state.idleTween = null; }
      if (on && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        const obj = { v: state.rot };
        state.idleTween = gsap.to(obj, { v: state.rot + 360, duration: opts.idleSeconds || 60, ease: "none", repeat: -1, onUpdate: () => setRot(obj.v) });
      }
    }

    function tickPointer() {
      if (!gsap) return;
      gsap.fromTo(pointer, { rotation: -22, svgOrigin: "0 -226" }, { rotation: 0, svgOrigin: "0 -226", duration: 0.22, ease: "back.out(3)", overwrite: true });
    }

    /** Spin so that slot `index` stops under the pointer. Resolves when finished. */
    function spinTo(index, { duration = 6.4, onTick } = {}) {
      return new Promise((resolve) => {
        idle(false);
        state.spinning = true;
        host.querySelector(".sw-wrap").classList.add("is-spinning");
        const center = index * a + a / 2;
        const jitter = (Math.random() - 0.5) * a * 0.56;
        const want = -(center) + jitter;
        const cur = state.rot;
        const delta = (((want - cur) % 360) + 360) % 360;
        const final = cur + 360 * 7 + delta;
        if (!gsap) { setRot(final); state.spinning = false; resolve(); return; }
        const obj = { v: cur };
        let lastStep = Math.floor(cur / a);
        gsap.timeline()
          .to(obj, { v: cur - 14, duration: 0.35, ease: "power2.out", onUpdate: () => setRot(obj.v) })
          .to(obj, {
            v: final, duration, ease: "power4.out",
            onUpdate: () => {
              setRot(obj.v);
              const step = Math.floor(obj.v / a);
              if (step !== lastStep) { lastStep = step; tickPointer(); if (onTick) onTick(); }
            },
            onComplete: () => {
              state.spinning = false;
              host.querySelector(".sw-wrap").classList.remove("is-spinning");
              const seg = host.querySelector(`.sw-seg[data-i="${index}"]`);
              if (seg) { seg.classList.add("is-winner"); setTimeout(() => seg.classList.remove("is-winner"), 4200); }
              resolve();
            },
          });
      });
    }

    if (opts.idle) idle(true);

    return {
      svg, hub, spinTo, idle,
      get spinning() { return state.spinning; },
      destroy() { idle(false); host.innerHTML = ""; },
    };
  }

  window.SoobinWheel = { mount, slotTexts };
})();

