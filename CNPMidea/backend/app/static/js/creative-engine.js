/**
 * ============================================================================
 * SOOBIN COOL AQUA ENGINE (Lenis + GSAP Smooth Scroll & Refreshing Audio UX)
 * ----------------------------------------------------------------------------
 * Theo chuẩn antigravityrules.md:
 * 1. Smooth Scroll: Lenis đồng bộ trực tiếp với gsap.ticker & ScrollTrigger.update
 * 2. Soothing Micro-Interactions: Chuyển động êm dịu mắt, không intro rườm rà
 * 3. Refreshing Product Selection Sound: Âm thanh giọt nước mát lạnh khi chọn SP
 * 4. Order Celebration Modal & Sound: Thông báo Cảm ơn Khách hàng + Âm thanh chúc mừng
 * ============================================================================
 */
(function () {
  "use strict";

  // --------------------------------------------------------------------------
  // 0. CN() UTILITY (clsx + tailwind-merge standard per antigravityrules.md)
  // --------------------------------------------------------------------------
  window.cn = function (...inputs) {
    return inputs
      .flat(Infinity)
      .filter(Boolean)
      .map((x) => {
        if (typeof x === "string") return x.trim();
        if (typeof x === "object") {
          return Object.entries(x)
            .filter(([, v]) => Boolean(v))
            .map(([k]) => k.trim())
            .join(" ");
        }
        return "";
      })
      .filter(Boolean)
      .join(" ")
      .replace(/\s+/g, " ")
      .trim();
  };

  // --------------------------------------------------------------------------
  // 1. LENIS SMOOTH SCROLL + GSAP TICKER + SCROLLTRIGGER SYNC
  // --------------------------------------------------------------------------
  function initLenisAndGsapSync() {
    if (!document.getElementById("soobinScrollProgressBar")) {
      const bar = document.createElement("div");
      bar.id = "soobinScrollProgressBar";
      document.body.appendChild(bar);
    }

    if (window.gsap && window.ScrollTrigger) {
      window.gsap.registerPlugin(window.ScrollTrigger);
      if (window.Flip) window.gsap.registerPlugin(window.Flip);
    }

    if (typeof window.Lenis === "function") {
      const lenis = new window.Lenis({
        autoRaf: false,
        lerp: 0.09,
        duration: 1.05,
        smoothWheel: true,
        wheelMultiplier: 0.95,
      });
      window.soobinLenis = lenis;

      lenis.on("scroll", (e) => {
        if (window.ScrollTrigger) {
          window.ScrollTrigger.update();
        }
        const bar = document.getElementById("soobinScrollProgressBar");
        if (bar && typeof e.progress === "number") {
          bar.style.transform = `scaleX(${Math.max(0, Math.min(1, e.progress)).toFixed(4)})`;
        }
      });

      if (window.gsap) {
        window.gsap.ticker.add((time) => {
          lenis.raf(time * 1000);
        });
        window.gsap.ticker.lagSmoothing(0);
      } else {
        function raf(time) {
          lenis.raf(time);
          requestAnimationFrame(raf);
        }
        requestAnimationFrame(raf);
      }
    }
  }

  // --------------------------------------------------------------------------
  // 2. REFRESHING AUDIO ENGINE (PRODUCT SELECTION & ORDER CELEBRATION)
  // --------------------------------------------------------------------------
  let sfxEnabled = localStorage.getItem("soobin_sfx_enabled") !== "0";
  let sharedAudioCtx = null;
  let selectAudioPool = null;
  let celebrationAudioEl = null;
  let lastSelectSoundAt = 0;

  function getAudioContext() {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return null;
      if (!sharedAudioCtx) sharedAudioCtx = new AudioCtx();
      if (sharedAudioCtx.state === "suspended") {
        sharedAudioCtx.resume().catch(() => {});
      }
      return sharedAudioCtx;
    } catch (_) {
      return null;
    }
  }

  function updateSfxButtonUI() {
    const btn = document.getElementById("sfxToggleBtn");
    if (!btn) return;
    btn.innerHTML = sfxEnabled
      ? `<span>🔊 Âm thanh: Bật</span>`
      : `<span>🔇 Âm thanh: Tắt</span>`;
    btn.title = sfxEnabled
      ? "Đang bật âm thanh sảng khoái khi chọn sản phẩm & đặt hàng"
      : "Bấm để bật âm thanh tương tác";
  }

  window.toggleSoobinSoundEffects = function () {
    sfxEnabled = !sfxEnabled;
    localStorage.setItem("soobin_sfx_enabled", sfxEnabled ? "1" : "0");
    updateSfxButtonUI();
    if (sfxEnabled) {
      window.playRefreshingSelectSound();
    }
  };

  /**
   * Phát âm thanh giọt nước & chuông pha lê mát lạnh, sảng khoái khi lựa sản phẩm / chọn size / lọc danh mục
   */
  window.playRefreshingSelectSound = function (variant = "select") {
    if (!sfxEnabled) return;
    const now = performance.now();
    if (now - lastSelectSoundAt < 55) return;
    lastSelectSoundAt = now;

    // 1. Play pre-generated stereo WAV (/static/audio/water_select.wav)
    try {
      if (!selectAudioPool) {
        selectAudioPool = new Audio("/static/audio/water_select.wav");
        selectAudioPool.preload = "auto";
      }
      const clone = selectAudioPool.cloneNode();
      clone.volume = variant === "cart" ? 0.55 : 0.42;
      clone.play().catch(() => {});
    } catch (_) {}

    // 2. Supplement with Web Audio API crisp aqua droplet harmonic
    try {
      const ctx = getAudioContext();
      if (!ctx) return;
      const t0 = ctx.currentTime;

      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";

      if (variant === "cart") {
        osc.frequency.setValueAtTime(587.33, t0); // D5
        osc.frequency.exponentialRampToValueAtTime(1174.66, t0 + 0.14); // D6
      } else {
        osc.frequency.setValueAtTime(520, t0);
        osc.frequency.exponentialRampToValueAtTime(1046.5, t0 + 0.11);
      }

      gain.gain.setValueAtTime(0.001, t0);
      gain.gain.linearRampToValueAtTime(0.09, t0 + 0.012);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.22);

      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(t0);
      osc.stop(t0 + 0.23);
    } catch (_) {}
  };

  /**
   * Phát âm thanh chúc mừng rộn ràng, tươi mát khi đặt hàng / thanh toán thành công
   */
  window.playOrderCelebrationSound = function () {
    // 1. Play stereo celebration WAV (/static/audio/order_celebration.wav)
    try {
      if (!celebrationAudioEl) {
        celebrationAudioEl = new Audio("/static/audio/order_celebration.wav");
        celebrationAudioEl.preload = "auto";
      }
      celebrationAudioEl.currentTime = 0;
      celebrationAudioEl.volume = 0.78;
      celebrationAudioEl.play().catch(() => {});
    } catch (_) {}

    // 2. Web Audio API C-Major-9th Celebration Chime Fanfare
    try {
      const ctx = getAudioContext();
      if (!ctx) return;
      const notes = [
        { delay: 0.0, freq: 523.25, dur: 0.35 },   // C5
        { delay: 0.1, freq: 659.25, dur: 0.35 },   // E5
        { delay: 0.2, freq: 783.99, dur: 0.38 },   // G5
        { delay: 0.3, freq: 987.77, dur: 0.42 },   // B5
        { delay: 0.42, freq: 1046.5, dur: 0.95 },  // C6
        { delay: 0.42, freq: 1318.51, dur: 0.95 }, // E6
        { delay: 0.42, freq: 1567.98, dur: 1.0 },  // G6
      ];
      notes.forEach((n) => {
        const start = ctx.currentTime + n.delay;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "triangle";
        osc.frequency.setValueAtTime(n.freq, start);

        gain.gain.setValueAtTime(0.001, start);
        gain.gain.linearRampToValueAtTime(0.11, start + 0.018);
        gain.gain.exponentialRampToValueAtTime(0.0001, start + n.dur);

        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(start);
        osc.stop(start + n.dur + 0.02);
      });
    } catch (_) {}
  };

  // --------------------------------------------------------------------------
  // 3. ORDER SUCCESS THANK-YOU MODAL (#thankYouCelebrationModal)
  // --------------------------------------------------------------------------
  function ensureThankYouModalExists() {
    let modal = document.getElementById("thankYouCelebrationModal");
    if (modal) return modal;

    modal = document.createElement("div");
    modal.id = "thankYouCelebrationModal";
    modal.className = "hidden";
    modal.innerHTML = `
      <div class="thank-you-modal-card" id="thankYouModalCard">
        <div class="w-16 h-16 rounded-full bg-sky-100 border-2 border-sky-400 text-sky-600 flex items-center justify-center mx-auto mb-4 text-3xl font-black shadow-sm">
          ✓
        </div>
        <span class="inline-block px-3 py-1 rounded-full bg-teal-50 text-teal-700 border border-teal-200 text-[11px] font-extrabold uppercase tracking-wider mb-2">
          Đặt Hàng Thành Công
        </span>
        <h3 class="text-2xl font-black text-slate-900 tracking-tight" id="thankYouModalTitle">
          Xin Cảm Ơn Quý Khách!
        </h3>
        <p class="text-sm text-slate-600 mt-1.5 leading-relaxed" id="thankYouModalMessage">
          Cảm ơn bạn đã tin tưởng lựa chọn đồ bơi & phụ kiện tại <strong>Soobin Swimwear</strong>. Đơn hàng của bạn đang được chuẩn bị chu đáo!
        </p>

        <div class="mt-5 bg-sky-50/80 border border-sky-200 rounded-2xl p-4 text-left space-y-2 text-xs">
          <div class="flex justify-between items-center">
            <span class="text-slate-500 font-semibold">Mã đơn hàng:</span>
            <span class="font-black text-sky-700 text-sm" id="thankYouOrderCode">#SOOBIN</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-slate-500 font-semibold">Khách hàng:</span>
            <span class="font-bold text-slate-800" id="thankYouCustomerName">Quý khách</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-slate-500 font-semibold">Phương thức thanh toán:</span>
            <span class="font-bold text-slate-800" id="thankYouPaymentMethod">COD</span>
          </div>
          <div class="flex justify-between items-center pt-2 border-t border-sky-200/80">
            <span class="text-slate-700 font-extrabold">Tổng thanh toán:</span>
            <span class="font-black text-emerald-600 text-base" id="thankYouTotalAmount">0đ</span>
          </div>
        </div>

        <div class="mt-5 flex flex-wrap items-center justify-center gap-2.5">
          <button type="button" id="thankYouContinueBtn" class="px-5 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-700 text-white font-extrabold text-xs transition shadow-sm cursor-pointer">
            Tiếp tục mua sắm
          </button>
          <button type="button" id="thankYouViewOrdersBtn" class="px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs transition cursor-pointer">
            Xem lịch sử đơn hàng
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    modal.addEventListener("click", (e) => {
      if (e.target === modal) window.closeOrderThankYouModal();
    });
    const contBtn = modal.querySelector("#thankYouContinueBtn");
    if (contBtn) {
      contBtn.addEventListener("click", () => window.closeOrderThankYouModal());
    }
    const viewBtn = modal.querySelector("#thankYouViewOrdersBtn");
    if (viewBtn) {
      viewBtn.addEventListener("click", () => {
        window.closeOrderThankYouModal();
        if (typeof window.openOrdersModal === "function") {
          window.openOrdersModal();
        }
      });
    }
    return modal;
  }

  window.showOrderThankYouCelebration = function (orderInfo = {}) {
    window.playOrderCelebrationSound();
    const modal = ensureThankYouModalExists();

    const codeEl = document.getElementById("thankYouOrderCode");
    const nameEl = document.getElementById("thankYouCustomerName");
    const payEl = document.getElementById("thankYouPaymentMethod");
    const totalEl = document.getElementById("thankYouTotalAmount");
    const titleEl = document.getElementById("thankYouModalTitle");
    const msgEl = document.getElementById("thankYouModalMessage");

    const orderCode = orderInfo.order_code || orderInfo.code || "SOOBIN-NEW";
    const customerName = orderInfo.recipient_name || orderInfo.customer_name || "Quý khách";
    const paymentMethod = orderInfo.payment_method || "COD";
    const totalAmount = Number(orderInfo.total_amount || 0);

    if (codeEl) codeEl.textContent = `#${orderCode}`;
    if (nameEl) nameEl.textContent = customerName;
    if (payEl) {
      payEl.textContent =
        paymentMethod === "VIETQR"
          ? "Chuyển khoản VietQR"
          : paymentMethod === "CASH"
          ? "Tiền mặt tại quầy (POS)"
          : "Thanh toán khi nhận hàng (COD)";
    }
    if (totalEl) {
      totalEl.textContent = `${Math.round(totalAmount).toLocaleString("vi-VN")}đ`;
    }
    if (titleEl) {
      titleEl.textContent = orderInfo.is_pos
        ? "Thanh Toán POS Thành Công — Xin Cảm Ơn Quý Khách!"
        : "Xin Cảm Ơn Quý Khách Đã Đặt Hàng!";
    }
    if (msgEl) {
      msgEl.innerHTML = orderInfo.is_pos
        ? `Cảm ơn quý khách <strong>${customerName}</strong> đã mua sắm trực tiếp tại Showroom Soobin Swimwear. Hóa đơn điện tử đã sẵn sàng!`
        : `Cảm ơn quý khách <strong>${customerName}</strong> đã tin tưởng lựa chọn Soobin Swimwear. Chúc quý khách có những trải nghiệm bơi lội & kỳ nghỉ biển tuyệt vời!`;
    }

    modal.classList.remove("hidden");
    const card = document.getElementById("thankYouModalCard");
    if (card && window.gsap) {
      window.gsap.fromTo(
        card,
        { opacity: 0, scale: 0.88, y: 20 },
        { opacity: 1, scale: 1, y: 0, duration: 0.38, ease: "back.out(1.5)" }
      );
    }
  };

  window.closeOrderThankYouModal = function () {
    const modal = document.getElementById("thankYouCelebrationModal");
    if (!modal) return;
    modal.classList.add("hidden");
  };

  // --------------------------------------------------------------------------
  // 4. SOOTHING PRODUCT INTERACTION & WATER RIPPLE BINDER
  // --------------------------------------------------------------------------
  function spawnSoothingWaterRipple(clientX, clientY) {
    if (!clientX && !clientY) return;
    if (window.__soobinWaterCursor) return; // water-cursor.js already draws a splash on every click
    const ripple = document.createElement("div");
    ripple.className = "soobin-water-ripple";
    ripple.style.left = `${clientX}px`;
    ripple.style.top = `${clientY}px`;
    document.body.appendChild(ripple);
    setTimeout(() => ripple.remove(), 550);
  }

  function bindProductSelectionAudioAndRipple() {
    document.addEventListener(
      "click",
      (e) => {
        const trigger = e.target.closest(
          "[data-sfx-select], .cool-product-card, .aceternity-3d-card, .size-select-btn, .category-pill-btn, .quick-filter-btn, #catalogGrid button"
        );
        if (!trigger) return;
        spawnSoothingWaterRipple(e.clientX, e.clientY);
        const isCartAction =
          trigger.dataset.sfxSelect === "cart" ||
          (trigger.textContent && trigger.textContent.includes("Thêm"));
        window.playRefreshingSelectSound(isCartAction ? "cart" : "select");
      },
      { passive: true }
    );
  }

  // --------------------------------------------------------------------------
  // 5. FAST & SOOTHING TRANSITION HELPERS (NO CLUNKY OVERLAYS)
  // --------------------------------------------------------------------------
  window.playSoobinTransition = function (_mainTitle, _subTitle, onMidpointCallback) {
    window.playRefreshingSelectSound("select");
    if (typeof onMidpointCallback === "function") {
      onMidpointCallback();
    }
    const grid = document.getElementById("catalogGrid");
    if (grid && window.gsap) {
      window.gsap.fromTo(
        grid,
        { opacity: 0.45, y: 8 },
        { opacity: 1, y: 0, duration: 0.25, ease: "power2.out" }
      );
    }
  };

  window.runGsapFlipMorph = function (_selector, domUpdateCallback) {
    if (typeof domUpdateCallback === "function") {
      domUpdateCallback();
    }
  };

  // --------------------------------------------------------------------------
  // 6. CLEAN SONNER TOAST SYSTEM
  // --------------------------------------------------------------------------
  function initSonnerToastSystem() {
    if (!document.getElementById("soobinSonnerToaster")) {
      const toaster = document.createElement("div");
      toaster.id = "soobinSonnerToaster";
      document.body.appendChild(toaster);
    }

    window.notify = function (message, type = "info") {
      const toaster = document.getElementById("soobinSonnerToaster");
      if (!toaster) return;

      const palette = {
        success: { border: "#34d399", badge: "bg-emerald-500 text-white", icon: "✓", title: "Thành công" },
        error: { border: "#fb7185", badge: "bg-rose-500 text-white", icon: "✕", title: "Thông báo" },
        info: { border: "#38bdf8", badge: "bg-sky-500 text-white", icon: "💧", title: "Soobin Swimwear" },
      };
      const cfg = palette[type] || palette.info;

      const card = document.createElement("div");
      card.className = "sonner-toast-card";
      card.style.borderColor = cfg.border;
      card.innerHTML = `
        <span class="w-6 h-6 rounded-full ${cfg.badge} font-black text-xs flex items-center justify-center shrink-0 mt-0.5">${cfg.icon}</span>
        <div class="flex-1 min-w-0 text-xs">
          <div class="font-extrabold text-slate-900 tracking-tight">${cfg.title}</div>
          <div class="text-slate-600 mt-0.5 leading-relaxed break-words">${message}</div>
        </div>
        <button class="text-slate-400 hover:text-slate-700 text-xs font-bold px-1">✕</button>
      `;

      card.querySelector("button").addEventListener("click", () => card.remove());
      toaster.appendChild(card);

      while (toaster.children.length > 4) {
        toaster.firstElementChild.remove();
      }

      setTimeout(() => {
        if (window.gsap) {
          window.gsap.to(card, {
            opacity: 0,
            x: 24,
            duration: 0.22,
            onComplete: () => card.remove(),
          });
        } else {
          card.remove();
        }
      }, 3600);
    };
  }

  // --------------------------------------------------------------------------
  // 7. SOOTHING AMBIENT WATER WAVE CANVAS (FOR LOGIN & HERO BANNER)
  // --------------------------------------------------------------------------
  function mountSoothingWaterCanvas(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !window.THREE) return;

    const THREE = window.THREE;
    const section = canvas.parentElement || document.body;
    const width = section.clientWidth || window.innerWidth;
    const height = section.clientHeight || window.innerHeight;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(48, width / height, 0.1, 100);
    camera.position.set(0, 1.8, 6.2);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));

    const cols = 42;
    const rows = 22;
    const total = cols * rows;
    const geo = new THREE.BufferGeometry();
    const positions = new Float32Array(total * 3);
    const colors = new Float32Array(total * 3);

    const col1 = new THREE.Color(0x38bdf8);
    const col2 = new THREE.Color(0x2dd4bf);

    let k = 0;
    for (let x = 0; x < cols; x++) {
      for (let z = 0; z < rows; z++) {
        positions[k] = (x - cols / 2) * 0.32;
        positions[k + 1] = -0.8;
        positions[k + 2] = (z - rows / 2) * 0.3;

        const c = col1.clone().lerp(col2, x / cols);
        colors[k] = c.r;
        colors[k + 1] = c.g;
        colors[k + 2] = c.b;
        k += 3;
      }
    }

    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));

    const mat = new THREE.PointsMaterial({
      size: 0.048,
      vertexColors: true,
      transparent: true,
      opacity: 0.45,
    });

    const wavePoints = new THREE.Points(geo, mat);
    scene.add(wavePoints);

    const clock = new THREE.Clock();
    function animateWave() {
      requestAnimationFrame(animateWave);
      const t = clock.getElapsedTime();
      const pos = geo.attributes.position;
      let idx = 0;
      for (let x = 0; x < cols; x++) {
        for (let z = 0; z < rows; z++) {
          pos.array[idx + 1] =
            -0.65 +
            Math.sin(x * 0.2 + t * 0.9) * 0.18 +
            Math.cos(z * 0.22 + t * 0.75) * 0.14;
          idx += 3;
        }
      }
      pos.needsUpdate = true;
      renderer.render(scene, camera);
    }
    animateWave();

    window.addEventListener("resize", () => {
      const w = section.clientWidth || window.innerWidth;
      const h = section.clientHeight || window.innerHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    });
  }

  // --------------------------------------------------------------------------
  // INITIALIZE ON DOM READY
  // --------------------------------------------------------------------------
  document.addEventListener("DOMContentLoaded", () => {
    initLenisAndGsapSync();
    initSonnerToastSystem();
    bindProductSelectionAudioAndRipple();
    ensureThankYouModalExists();
    updateSfxButtonUI();
    setTimeout(() => {
      mountSoothingWaterCanvas("loginThreeOceanCanvas");
    }, 80);
  });
})();
