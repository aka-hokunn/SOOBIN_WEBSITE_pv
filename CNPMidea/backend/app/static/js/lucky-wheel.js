/**
 * ============================================================================
 * SOOBIN LUCKY WHEEL — trải nghiệm vòng quay may mắn cho khách hàng
 * ----------------------------------------------------------------------------
 *  - Nút mở nhanh (mọi trang), khối giới thiệu ở trang chủ, modal vòng quay.
 *  - Kết quả do server quyết định (POST /api/v1/lucky-wheel/spin) → bánh xe
 *    GSAP quay chậm dần đúng ô trúng, kim lắc + tiếng "tách" mỗi khi qua ô.
 *  - Trúng: pháo hoa nổ khắp màn hình + âm thanh chúc mừng + vé voucher riêng.
 *  - Trượt: lời chia buồn & chúc may mắn lần sau + giờ mở lượt mới.
 * ============================================================================
 */
(function () {
  "use strict";

  const API = "/api/v1/lucky-wheel";
  const CHECKIN_API = "/api/v1/experience/checkin";
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const state = { data: null, wheel: null, teaser: null, busy: false, countdown: null, tab: "prizes", vouchers: [], checkin: null, checkinBusy: false };

  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (v) => `${Math.round(Number(v) || 0).toLocaleString("vi-VN")}đ`;
  const fmtDate = (iso) => new Date(iso).toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });
  const toast = (msg, type = "info") => {
    if (typeof window.notify === "function") window.notify(msg, type);
    else if (typeof window.showToast === "function") window.showToast(msg, type === "error");
  };

  function periodText(minutes) {
    const m = Number(minutes) || 1440;
    if (m % 1440 === 0) return `${m / 1440} ngày`;
    if (m % 60 === 0) return `${m / 60} giờ`;
    return `${m} phút`;
  }

  function countdownText(iso) {
    const diff = Math.max(0, new Date(iso).getTime() - Date.now());
    const s = Math.floor(diff / 1000);
    const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    const p = (n) => String(n).padStart(2, "0");
    return d > 0 ? `${d}n ${p(h)}:${p(m)}:${p(sec)}` : `${p(h)}:${p(m)}:${p(sec)}`;
  }

  // --------------------------------------------------------------------------
  // SOUND (Web Audio, tôn trọng nút bật/tắt âm thanh của cửa hàng)
  // --------------------------------------------------------------------------
  let audioCtx = null;
  const sfxOn = () => localStorage.getItem("soobin_sfx_enabled") !== "0";
  function ctx() {
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      if (audioCtx.state === "suspended") audioCtx.resume();
      return audioCtx;
    } catch (_) { return null; }
  }
  function tone(freq, start, dur, type = "sine", vol = 0.08, glideTo) {
    const c = ctx(); if (!c) return;
    const t0 = c.currentTime + start;
    const o = c.createOscillator(), g = c.createGain();
    o.type = type; o.frequency.setValueAtTime(freq, t0);
    if (glideTo) o.frequency.exponentialRampToValueAtTime(glideTo, t0 + dur);
    g.gain.setValueAtTime(0.0001, t0); g.gain.linearRampToValueAtTime(vol, t0 + 0.012);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    o.connect(g); g.connect(c.destination); o.start(t0); o.stop(t0 + dur + 0.02);
  }
  const sTick = () => sfxOn() && tone(1900, 0, 0.035, "square", 0.025);
  function sPop() {
    if (!sfxOn()) return;
    const c = ctx(); if (!c) return;
    const len = 0.35, buf = c.createBuffer(1, c.sampleRate * len, c.sampleRate), data = buf.getChannelData(0);
    for (let i = 0; i < data.length; i++) data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / data.length, 3);
    const src = c.createBufferSource(), f = c.createBiquadFilter(), g = c.createGain();
    f.type = "lowpass"; f.frequency.value = 900 + Math.random() * 900; g.gain.value = 0.12;
    src.buffer = buf; src.connect(f); f.connect(g); g.connect(c.destination); src.start();
  }
  function sWin() {
    if (!sfxOn()) return;
    if (typeof window.playOrderCelebrationSound === "function") window.playOrderCelebrationSound();
    else [523, 659, 784, 1046].forEach((f, i) => tone(f, i * 0.1, 0.5, "triangle", 0.1));
  }
  function sLose() {
    if (!sfxOn()) return;
    tone(392, 0, 0.45, "sine", 0.07, 370);
    tone(294, 0.32, 0.7, "sine", 0.07, 262);
  }

  // --------------------------------------------------------------------------
  // FIREWORKS — pháo hoa nổ khắp màn hình (canvas, nền trong suốt)
  // --------------------------------------------------------------------------
  function fireworks(duration = 5600) {
    if (reduceMotion) return;
    document.getElementById("lwFireworks")?.remove();
    const cv = document.createElement("canvas");
    cv.id = "lwFireworks";
    document.body.appendChild(cv);
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const W = (cv.width = innerWidth * dpr), H = (cv.height = innerHeight * dpr);
    const c = cv.getContext("2d");
    const G = 0.16 * dpr;
    const palettes = [["#fde68a", "#f59e0b"], ["#22d3ee", "#e0f2fe"], ["#f43f5e", "#fda4af"], ["#a78bfa", "#ffffff"], ["#34d399", "#fef9c3"], ["#fb923c", "#fde68a"]];
    const rockets = [], parts = [];
    const rnd = (a, b) => a + Math.random() * (b - a);
    const t0 = performance.now();
    let next = 0;

    function launch(xFrac) {
      const x = (xFrac ?? rnd(0.08, 0.92)) * W;
      const ty = rnd(0.1, 0.48) * H;
      rockets.push({ x, y: H + 6, px: x, py: H + 6, vx: rnd(-0.8, 0.8) * dpr, vy: -Math.sqrt(2 * G * (H - ty)), ty, pal: palettes[Math.floor(Math.random() * palettes.length)] });
    }
    function explode(r) {
      sPop();
      const ring = Math.random() < 0.3;
      const count = Math.floor(rnd(90, 140));
      for (let i = 0; i < count; i++) {
        const ang = ring ? (i / count) * Math.PI * 2 : Math.random() * Math.PI * 2;
        const sp = (ring ? 6 : rnd(1.8, 9)) * dpr;
        parts.push({ x: r.x, y: r.y, vx: Math.cos(ang) * sp, vy: Math.sin(ang) * sp, age: 0, life: rnd(55, 90), col: r.pal[i % 2], size: rnd(1.6, 3) * dpr, flicker: Math.random() < 0.35 });
      }
    }
    // Opening salvo: instant bursts all over the screen, then rockets keep coming
    [[0.18, 0.28], [0.82, 0.24], [0.5, 0.18], [0.3, 0.55], [0.7, 0.5], [0.08, 0.7], [0.92, 0.68]].forEach(([fx, fy], i) =>
      setTimeout(() => explode({ x: fx * W, y: fy * H, pal: palettes[i % palettes.length] }), i * 110));
    [0.15, 0.5, 0.85].forEach((f, i) => setTimeout(() => launch(f), 300 + i * 160));

    function frame(now) {
      const elapsed = now - t0;
      if (elapsed < duration && now > next) { launch(); if (Math.random() < 0.45) launch(); next = now + rnd(220, 420); }
      c.globalCompositeOperation = "destination-out";
      c.fillStyle = "rgba(0,0,0,0.24)";
      c.fillRect(0, 0, W, H);
      c.globalCompositeOperation = "lighter";
      for (let i = rockets.length - 1; i >= 0; i--) {
        const r = rockets[i];
        r.px = r.x; r.py = r.y;
        r.x += r.vx; r.y += r.vy; r.vy += G;
        c.strokeStyle = "#fff7d6";
        c.lineWidth = 2.4 * dpr;
        c.lineCap = "round";
        c.beginPath(); c.moveTo(r.px, r.py); c.lineTo(r.x, r.y); c.stroke();
        if (r.vy >= -0.4 * dpr || r.y <= r.ty) { explode(r); rockets.splice(i, 1); }
      }
      for (let i = parts.length - 1; i >= 0; i--) {
        const p = parts[i];
        p.vx *= 0.965; p.vy = p.vy * 0.965 + G * 0.35;
        p.x += p.vx; p.y += p.vy; p.age++;
        const alpha = Math.max(0, 1 - p.age / p.life);
        if (alpha <= 0) { parts.splice(i, 1); continue; }
        c.globalAlpha = p.flicker ? alpha * (0.4 + Math.random() * 0.6) : alpha;
        c.fillStyle = p.col;
        c.beginPath(); c.arc(p.x, p.y, p.size, 0, Math.PI * 2); c.fill();
      }
      c.globalAlpha = 1;
      if (elapsed < duration || rockets.length || parts.length) requestAnimationFrame(frame);
      else cv.remove();
    }
    requestAnimationFrame(frame);
  }

  // --------------------------------------------------------------------------
  // DOM
  // --------------------------------------------------------------------------
  function ensureDom() {
    if (document.getElementById("luckyWheelModal")) return;

    const launcher = document.createElement("button");
    launcher.type = "button";
    launcher.id = "luckyWheelLauncher";
    launcher.setAttribute("aria-label", "Vòng quay may mắn");
    launcher.title = "Vòng quay may mắn";
    launcher.innerHTML = `<span class="lw-launch-ico">🎡</span><span class="fab-label">Vòng quay</span><span class="lw-launch-badge" id="lwLaunchBadge">🎁</span>`;
    launcher.addEventListener("click", open);
    document.body.appendChild(launcher);

    const modal = document.createElement("div");
    modal.id = "luckyWheelModal";
    modal.setAttribute("role", "dialog");
    modal.setAttribute("aria-modal", "true");
    modal.innerHTML = `
      <div class="lw-panel" data-lenis-prevent>
        <button type="button" class="lw-close" aria-label="Đóng">✕</button>
        <div class="lw-stage"><div id="lwWheelHost"></div></div>
        <div class="lw-info">
          <span class="lw-eyebrow">Soobin Lucky Wheel</span>
          <h3 class="lw-title" id="lwTitle">Vòng Quay Đại Dương</h3>
          <p class="lw-sub" id="lwSub"></p>
          <div class="lw-chips" id="lwChips"></div>
          <button type="button" class="lw-spin-btn" id="lwSpinBtn">🎡 QUAY NGAY</button>
          <p class="lw-note" id="lwNote"></p>
          <div class="lw-tabs">
            <button type="button" class="lw-tab is-active" data-lw-tab="prizes">Phần quà</button>
            <button type="button" class="lw-tab" data-lw-tab="checkin">🐚 Điểm danh</button>
            <button type="button" class="lw-tab" data-lw-tab="mine">Ví voucher của tôi</button>
          </div>
          <div id="lwTabBody"></div>
        </div>
      </div>`;
    document.body.appendChild(modal);
    modal.addEventListener("click", (e) => { if (e.target === modal) close(); });
    modal.querySelector(".lw-close").addEventListener("click", close);
    modal.querySelector("#lwSpinBtn").addEventListener("click", spin);
    modal.querySelectorAll("[data-lw-tab]").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.lwTab)));

    const result = document.createElement("div");
    result.id = "lwResult";
    result.addEventListener("click", (e) => { if (e.target === result) hideResult(); });
    document.body.appendChild(result);

    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      if (result.classList.contains("is-open")) hideResult();
      else if (modal.classList.contains("is-open") && !state.busy) close();
    });
  }

  function isCustomer() { return state.data && state.data.spins_left !== null && state.data.spins_left !== undefined; }

  function renderInfo() {
    const d = state.data;
    if (!d) return;
    document.getElementById("lwTitle").textContent = d.title || "Vòng Quay May Mắn";
    document.getElementById("lwSub").textContent = d.subtitle || "";
    const chips = [];
    const bonus = Number(d.bonus_spins) || 0;
    if (isCustomer()) chips.push(`<span class="lw-chip">🎟️ Lượt còn lại: <strong>${d.spins_left}/${d.spins_per_period + bonus}</strong>${bonus ? ` <small style="opacity:.75">(+${bonus} 🐚)</small>` : ""}</span>`);
    else chips.push(`<span class="lw-chip">🎟️ <strong>${d.spins_per_period}</strong> lượt / ${periodText(d.reset_interval_minutes)}</span>`);
    chips.push(`<span class="lw-chip">⏳ Lượt mới sau <strong id="lwCountdown">${countdownText(d.next_reset_at)}</strong></span>`);
    chips.push(`<span class="lw-chip">🎁 Voucher riêng, hạn <strong>${d.voucher_valid_days} ngày</strong></span>`);
    document.getElementById("lwChips").innerHTML = chips.join("");

    const btn = document.getElementById("lwSpinBtn");
    const note = document.getElementById("lwNote");
    btn.disabled = state.busy || !d.enabled || (isCustomer() && !d.can_spin);
    if (!d.enabled) { btn.textContent = "Vòng quay đang tạm dừng"; note.textContent = "Hẹn bạn quay lại sau nhé!"; }
    else if (!d.logged_in) { btn.textContent = "🎡 ĐĂNG NHẬP ĐỂ QUAY"; btn.disabled = false; note.innerHTML = `Voucher trúng thưởng được lưu vào tài khoản của bạn. <a href="/login">Đăng nhập / Đăng ký</a>`; }
    else if (!isCustomer()) { btn.textContent = "Chỉ dành cho khách hàng"; btn.disabled = true; note.textContent = "Tài khoản nhân viên không tham gia vòng quay."; }
    else if (!d.can_spin) { btn.textContent = "Bạn đã hết lượt quay"; note.textContent = state.checkin && !state.checkin.checked_in_today ? "Điểm danh nhận Vỏ Sò — đủ 3 Vỏ Sò được thêm 1 lượt quay." : "Lượt quay mới sẽ tự mở khi đồng hồ đếm ngược kết thúc."; }
    else { btn.textContent = state.busy ? "Đang quay..." : `🎡 QUAY NGAY (${d.spins_left} lượt)`; note.textContent = "Kết quả được hệ thống quyết định ngẫu nhiên theo tỷ lệ công bố của cửa hàng."; }

    const badge = document.getElementById("lwLaunchBadge");
    if (badge) badge.textContent = isCustomer() ? String(d.spins_left) : "🎁";
    renderTab();
  }

  function renderTab() {
    const body = document.getElementById("lwTabBody");
    if (!body || !state.data) return;
    document.querySelectorAll("[data-lw-tab]").forEach((b) => b.classList.toggle("is-active", b.dataset.lwTab === state.tab));
    const ciTab = document.querySelector('[data-lw-tab="checkin"]');
    if (ciTab) ciTab.innerHTML = `🐚 Điểm danh${state.checkin && !state.checkin.checked_in_today ? '<span class="lw-tab-dot" aria-label="Chưa điểm danh hôm nay"></span>' : ""}`;
    if (state.tab === "checkin") { renderCheckin(body); return; }
    if (state.tab === "prizes") {
      body.innerHTML = `<div class="lw-odds">${state.data.slots.map((s) => `
        <span><i style="background:${esc(s.color)}"></i>${esc(s.label)}${s.is_prize && !s.in_stock ? " · <em style='opacity:.6'>tạm hết</em>" : ""}</span>`).join("")}</div>`;
      return;
    }
    if (!isCustomer()) { body.innerHTML = `<p class="lw-empty">Đăng nhập tài khoản khách hàng để xem voucher đã trúng.</p>`; return; }
    if (!state.vouchers.length) { body.innerHTML = `<p class="lw-empty">Bạn chưa có voucher nào từ vòng quay — thử vận may ngay nhé! 🍀</p>`; return; }
    const statusText = { AVAILABLE: "Còn hiệu lực", USED: "Đã sử dụng", EXPIRED: "Đã hết hạn", LOCKED: "Tạm khoá" };
    body.innerHTML = `<div class="lw-list">${state.vouchers.map((v) => `
      <div class="lw-voucher ${v.status !== "AVAILABLE" ? "is-dim" : ""}">
        <span class="lw-voucher-pct">-${v.discount_percent}%</span>
        <div><span class="lw-voucher-code">${esc(v.code)}</span>
          <small>${statusText[v.status] || v.status} · HSD ${fmtDate(v.ends_at)}${v.minimum_order_amount > 0 ? ` · đơn từ ${money(v.minimum_order_amount)}` : ""}</small></div>
        ${v.status === "AVAILABLE" ? `<button type="button" class="lw-copy" data-copy="${esc(v.code)}">Sao chép</button>` : ""}
      </div>`).join("")}</div>`;
    body.querySelectorAll("[data-copy]").forEach((b) => b.addEventListener("click", () => copyCode(b.dataset.copy)));
  }

  function setTab(tab) {
    state.tab = tab;
    if (tab === "mine" && isCustomer()) loadVouchers().then(renderTab);
    if (tab === "checkin" && isCustomer() && !state.checkin) loadCheckin().then(renderTab);
    renderTab();
  }

  // --------------------------------------------------------------------------
  // ĐIỂM DANH NHẬN VỎ SÒ — 3 Vỏ Sò = +1 lượt quay trong chu kỳ hiện tại
  // --------------------------------------------------------------------------
  async function loadCheckin() {
    if (!isCustomer()) { state.checkin = null; return null; }
    try {
      const res = await fetch(CHECKIN_API);
      state.checkin = res.ok ? await res.json() : null;
    } catch (_) { state.checkin = null; }
    return state.checkin;
  }

  function renderCheckin(body) {
    if (!state.data.logged_in) { body.innerHTML = `<p class="lw-empty">Đăng nhập để điểm danh mỗi ngày — cứ 3 Vỏ Sò đổi 1 lượt quay. <a href="/login" style="color:#fde68a;font-weight:800;text-decoration:underline">Đăng nhập</a></p>`; return; }
    if (!isCustomer()) { body.innerHTML = `<p class="lw-empty">Điểm danh chỉ dành cho tài khoản khách hàng.</p>`; return; }
    const ci = state.checkin;
    if (!ci) { body.innerHTML = `<p class="lw-empty">Đang tải lịch điểm danh…</p>`; return; }
    const per = ci.shells_per_spin || 3;
    const days = ci.days.map((d) => `
      <div class="lw-ci-day is-${d.status}${d.shells > 1 ? " is-big" : ""}" title="Ngày ${d.day}: +${d.shells} Vỏ Sò">
        <span>N${d.day}</span><b>🐚</b><small>+${d.shells}</small>
      </div>`).join("");
    const shells = Array.from({ length: per }, (_, i) => `<i class="${i < ci.shells_progress ? "is-on" : ""}">${i < ci.shells_progress ? "🐚" : ""}</i>`).join("");
    body.innerHTML = `
      <div class="lw-checkin">
        <div class="lw-ci-days">${days}</div>
        <div class="lw-ci-meter">
          <span class="lw-ci-shells" aria-label="${ci.shells_progress}/${per} Vỏ Sò">${shells}</span>
          <span><strong>${ci.shells_progress}/${per}</strong> Vỏ Sò → +1 lượt${ci.bonus_spins_this_cycle ? ` · đã nhận <strong>+${ci.bonus_spins_this_cycle}</strong> lượt chu kỳ này` : ""}</span>
        </div>
        <button type="button" class="lw-ci-btn" id="lwCheckinBtn" ${ci.checked_in_today || state.checkinBusy ? "disabled" : ""}>
          ${ci.checked_in_today ? `Đã điểm danh · chuỗi ${ci.streak}/7 ngày` : `Điểm danh hôm nay · +${ci.next_reward} 🐚`}
        </button>
      </div>`;
    const btn = body.querySelector("#lwCheckinBtn");
    if (btn) btn.addEventListener("click", doCheckin);
  }

  function shellBurst(fromEl) {
    if (reduceMotion || !window.gsap || !fromEl) return;
    const r = fromEl.getBoundingClientRect();
    for (let i = 0; i < 10; i++) {
      const s = document.createElement("span");
      s.className = "lw-ci-burst";
      s.textContent = i % 3 === 0 ? "✨" : "🐚";
      s.style.left = `${r.left + r.width / 2}px`;
      s.style.top = `${r.top + r.height / 2}px`;
      document.body.appendChild(s);
      const ang = (Math.PI * 2 * i) / 10 + Math.random() * 0.4;
      const dist = 60 + Math.random() * 70;
      window.gsap.fromTo(s, { x: 0, y: 0, scale: 0.4, opacity: 1 }, {
        x: Math.cos(ang) * dist, y: Math.sin(ang) * dist - 30, scale: 1.1, opacity: 0, rotation: Math.random() * 120 - 60,
        duration: 0.9 + Math.random() * 0.4, ease: "power3.out", onComplete: () => s.remove(),
      });
    }
  }

  async function doCheckin(e) {
    if (state.checkinBusy || !isCustomer()) return;
    const btn = e && e.currentTarget;
    state.checkinBusy = true;
    if (btn) btn.disabled = true;
    try {
      const res = await fetch(CHECKIN_API, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Không thể điểm danh lúc này.");
      state.checkin = data;
      shellBurst(btn);
      if (sfxOn()) [880, 1175, 1568].forEach((f, i) => tone(f, i * 0.08, 0.28, "triangle", 0.06));
      toast(data.message || "Điểm danh thành công!", "success");
      await refresh();
      if (data.bonus_spins_awarded && state.wheel && window.gsap && !reduceMotion) {
        window.gsap.fromTo("#lwSpinBtn", { scale: 1 }, { scale: 1.05, duration: 0.18, yoyo: true, repeat: 3, ease: "power2.out" });
      }
    } catch (err) {
      toast(err.message || "Không thể điểm danh lúc này.", "error");
      await loadCheckin();
    } finally {
      state.checkinBusy = false;
      renderInfo();
    }
  }

  async function copyCode(code) {
    try { await navigator.clipboard.writeText(code); toast(`Đã sao chép mã ${code}`, "success"); }
    catch (_) { toast(`Mã của bạn: ${code}`, "info"); }
    localStorage.setItem("soobin_pending_voucher", code);
  }

  // --------------------------------------------------------------------------
  // DATA
  // --------------------------------------------------------------------------
  async function loadState() {
    try {
      const res = await fetch(API);
      if (!res.ok) throw new Error();
      state.data = await res.json();
    } catch (_) { state.data = null; }
    return state.data;
  }

  async function loadVouchers() {
    try {
      const res = await fetch(`${API}/my-vouchers`);
      state.vouchers = res.ok ? await res.json() : [];
    } catch (_) { state.vouchers = []; }
  }

  function mountWheels() {
    if (!state.data || !window.SoobinWheel) return;
    const host = document.getElementById("lwWheelHost");
    if (host && !state.busy) {
      state.wheel?.destroy();
      state.wheel = window.SoobinWheel.mount(host, state.data.slots, { hubText: "QUAY" });
      state.wheel.hub.addEventListener("click", spin);
      state.wheel.hub.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); spin(); } });
    }
    renderTeaser();
  }

  function startCountdown() {
    clearInterval(state.countdown);
    state.countdown = setInterval(() => {
      if (!state.data) return;
      const left = new Date(state.data.next_reset_at).getTime() - Date.now();
      document.querySelectorAll("#lwCountdown, #lwtCountdown").forEach((el) => (el.textContent = countdownText(state.data.next_reset_at)));
      if (left <= 0 && !state.busy) refresh();
    }, 1000);
  }

  async function refresh() {
    await loadState();
    if (!state.data) return;
    mountWheels();
    renderInfo();
  }

  // --------------------------------------------------------------------------
  // OPEN / CLOSE / SPIN
  // --------------------------------------------------------------------------
  async function open() {
    ensureDom();
    const modal = document.getElementById("luckyWheelModal");
    modal.classList.add("is-open");
    window.soobinLenis?.stop();
    if (!state.data) await refresh(); else { mountWheels(); renderInfo(); }
    if (isCustomer()) loadVouchers().then(renderTab);
    if (isCustomer()) {
      loadCheckin().then((ci) => {
        // Chưa điểm danh hôm nay → mở sẵn tab Điểm danh (một chạm là nhận Vỏ Sò)
        if (ci && !ci.checked_in_today && state.tab === "prizes") state.tab = "checkin";
        renderInfo();
      });
    }
    if (window.gsap && !reduceMotion) {
      window.gsap.fromTo(modal.querySelector(".lw-panel"), { y: 40, scale: 0.94, opacity: 0 }, { y: 0, scale: 1, opacity: 1, duration: 0.6, ease: "expo.out" });
      window.gsap.fromTo(modal.querySelector(".lw-stage"), { rotation: -25, scale: 0.7 }, { rotation: 0, scale: 1, duration: 1.1, ease: "elastic.out(1, 0.7)" });
    }
  }

  function close() {
    if (state.busy) return;
    document.getElementById("luckyWheelModal")?.classList.remove("is-open");
    window.soobinLenis?.start();
  }

  async function spin() {
    if (state.busy || !state.data) return;
    const d = state.data;
    if (!d.logged_in) { window.location.href = "/login"; return; }
    if (!isCustomer()) { toast("Vòng quay chỉ dành cho tài khoản khách hàng.", "error"); return; }
    if (!d.enabled) { toast("Vòng quay đang tạm dừng.", "error"); return; }
    if (!d.can_spin) { toast(`Bạn đã hết lượt. Lượt mới sau ${countdownText(d.next_reset_at)}.`, "error"); return; }

    state.busy = true;
    renderInfo();
    let result;
    try {
      const res = await fetch(`${API}/spin`, { method: "POST" });
      result = await res.json();
      if (!res.ok) throw new Error(result.detail || "Không thể quay lúc này.");
    } catch (err) {
      state.busy = false;
      toast(err.message || "Không thể quay lúc này.", "error");
      await refresh();
      return;
    }

    await state.wheel.spinTo(result.slot_index, { onTick: sTick });
    state.busy = false;
    state.data.spins_left = result.spins_left;
    state.data.can_spin = result.spins_left > 0;
    state.data.next_reset_at = result.next_reset_at;
    renderInfo();

    if (result.is_win) {
      fireworks();
      sWin();
      if (result.voucher) localStorage.setItem("soobin_pending_voucher", result.voucher.code);
      showResult(result);
      loadVouchers().then(renderTab);
    } else {
      sLose();
      showResult(result);
    }
    loadState().then(() => { renderInfo(); renderTeaser(); });
  }

  function showResult(r) {
    const box = document.getElementById("lwResult");
    const v = r.voucher;
    if (r.is_win && v) {
      box.innerHTML = `
        <div class="lw-result-card is-win" role="alertdialog">
          <img class="lw-result-art" src="/static/images/illustrations/medal.svg" alt="">
          <div class="lw-result-kicker" style="color:#b45309">🎉 Trúng thưởng</div>
          <h3 class="lw-result-title">Chúc Mừng Bạn!</h3>
          <p class="lw-result-msg">${esc(r.message)}</p>
          <div class="lw-ticket">
            <span class="lw-ticket-pct">-${v.discount_percent}%</span>
            <div><span class="lw-ticket-code">${esc(v.code)}</span>
              <small>Dùng 1 lần · HSD ${fmtDate(v.ends_at)}${v.minimum_order_amount > 0 ? ` · đơn từ ${money(v.minimum_order_amount)}` : ""}</small></div>
          </div>
          <div class="lw-result-actions">
            <button type="button" class="lw-btn lw-btn-gold" data-act="copy">📋 Sao chép mã</button>
            <button type="button" class="lw-btn lw-btn-primary" data-act="shop">Mua sắm ngay</button>
            <button type="button" class="lw-btn lw-btn-ghost" data-act="close">Đóng</button>
          </div>
        </div>`;
    } else {
      const more = state.data && state.data.spins_left > 0;
      box.innerHTML = `
        <div class="lw-result-card is-lose" role="alertdialog">
          <img class="lw-result-art" src="/static/images/illustrations/shell.svg" alt="">
          <div class="lw-result-kicker" style="color:#0369a1">Lần này chưa may mắn</div>
          <h3 class="lw-result-title">Tiếc Quá! 🌊</h3>
          <p class="lw-result-msg">${esc(r.message)}<br>Đừng buồn nhé — biển cả luôn có những con sóng mới. 🍀</p>
          <p class="lw-result-msg" style="margin-top:.4rem;font-weight:700;color:#0c4a6e">${more ? `Bạn còn ${state.data.spins_left} lượt quay.` : `Lượt mới sau ${countdownText(r.next_reset_at)}.`}</p>
          <div class="lw-result-actions">
            ${more ? `<button type="button" class="lw-btn lw-btn-gold" data-act="again">Quay tiếp</button>` : `<button type="button" class="lw-btn lw-btn-primary" data-act="shop">Xem bộ sưu tập</button>`}
            <button type="button" class="lw-btn lw-btn-ghost" data-act="close">Đóng</button>
          </div>
        </div>`;
    }
    box.classList.add("is-open");
    const card = box.querySelector(".lw-result-card");
    if (window.gsap && !reduceMotion) {
      window.gsap.fromTo(card, { scale: 0.6, y: 40, opacity: 0, rotation: r.is_win ? -6 : 0 }, { scale: 1, y: 0, opacity: 1, rotation: 0, duration: 0.8, ease: "elastic.out(1, 0.65)" });
      window.gsap.fromTo(card.querySelector(".lw-result-art"), { scale: 0, rotation: -60 }, { scale: 1, rotation: 0, duration: 0.9, delay: 0.15, ease: "back.out(2)" });
      if (!r.is_win) window.gsap.fromTo(card.querySelector(".lw-result-title"), { x: -8 }, { x: 0, duration: 0.5, ease: "elastic.out(1, 0.3)", delay: 0.3 });
    }
    box.querySelectorAll("[data-act]").forEach((b) => b.addEventListener("click", () => {
      const act = b.dataset.act;
      if (act === "copy" && v) copyCode(v.code);
      if (act === "close") hideResult();
      if (act === "again") { hideResult(); setTimeout(spin, 250); }
      if (act === "shop") { hideResult(); close(); location.hash = "#/shop/all"; }
    }));
  }

  function hideResult() { document.getElementById("lwResult")?.classList.remove("is-open"); }

  // --------------------------------------------------------------------------
  // HOME TEASER (trang chủ)
  // --------------------------------------------------------------------------
  function renderTeaser() {
    const host = document.getElementById("lwTeaserWheel");
    if (!host || !state.data || !window.SoobinWheel) return;
    const sig = JSON.stringify(state.data.slots.map((s) => [s.id, s.label, s.color, s.in_stock]));
    if (host.dataset.sig !== sig) {
      host.dataset.sig = sig;
      state.teaser?.destroy();
      state.teaser = window.SoobinWheel.mount(host, state.data.slots, { compact: true, idle: true, idleSeconds: 48, hubText: "QUAY" });
      state.teaser.hub.addEventListener("click", open);
    }
    const d = state.data;
    const set = (id, html) => { const el = document.getElementById(id); if (el) el.innerHTML = html; };
    set("lwtTitle", esc(d.title));
    set("lwtSub", esc(d.subtitle || ""));
    set("lwtChips", `
      <span class="lw-chip">🎟️ <strong>${d.spins_per_period}</strong> lượt / ${periodText(d.reset_interval_minutes)}</span>
      <span class="lw-chip">⏳ Làm mới sau <strong id="lwtCountdown">${countdownText(d.next_reset_at)}</strong></span>
      <span class="lw-chip">🎁 Giảm đến <strong>${Math.max(0, ...d.slots.filter((s) => s.is_prize).map((s) => s.discount_percent || 0))}%</strong></span>`);
    document.getElementById("luckyWheelTeaser")?.classList.toggle("hidden", !d.enabled);
  }

  // --------------------------------------------------------------------------
  // CHECKOUT: tự điền voucher vừa trúng
  // --------------------------------------------------------------------------
  function hookCheckout() {
    const original = window.openCheckoutModal;
    if (typeof original !== "function" || original.__lwHooked) return;
    const wrapped = function (...args) {
      const out = original.apply(this, args);
      const code = localStorage.getItem("soobin_pending_voucher");
      const input = document.getElementById("voucherCodeInput");
      if (code && input && !input.value) {
        input.value = code;
        localStorage.removeItem("soobin_pending_voucher");
        if (typeof window.recalculateCheckoutDiscount === "function") setTimeout(() => window.recalculateCheckoutDiscount(), 120);
        toast(`Đã tự điền voucher vòng quay ${code}`, "success");
      }
      return out;
    };
    wrapped.__lwHooked = true;
    window.openCheckoutModal = wrapped;
  }

  async function boot() {
    ensureDom();
    hookCheckout();
    document.querySelectorAll("[data-open-wheel]").forEach((b) => b.addEventListener("click", open));
    await refresh();
    startCountdown();
    // Re-check once the customer session has been resolved by app.js
    setTimeout(refresh, 1800);
  }

  window.soobinLuckyWheel = { open, close, refresh, fireworks, showResult };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
