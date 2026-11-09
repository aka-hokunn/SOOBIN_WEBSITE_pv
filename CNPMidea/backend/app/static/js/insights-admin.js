/**
 * ============================================================================
 * SOOBIN — PHÂN TÍCH & TĂNG TRƯỞNG (Insights) — module dùng chung ADMIN & MANAGER
 *  - KPI nhanh: doanh thu / đơn hôm nay, biến thể sắp hết, khách nguy cơ rời bỏ.
 *  - Dự báo nhập hàng: tốc độ bán → số ngày còn hàng → gợi ý nhập; tạo phiếu nhập
 *    nháp (dùng API /inventory/receipts/confirm sẵn có) hoặc xuất CSV.
 *  - Phân khúc RFM + gửi voucher chăm sóc cá nhân (CARE-XXXXXX).
 *  - Hiệu quả vòng quay may mắn.
 *  - Nhật ký thao tác nhân sự.
 * Gắn vào #insightsAdminRoot (data-theme="dark" | "light").
 * ============================================================================
 */
(function () {
  "use strict";

  const API = "/api/v1/insights";
  const TABS = [
    { id: "forecast", label: "Dự báo nhập hàng", icon: "📦" },
    { id: "rfm", label: "Phân khúc RFM", icon: "🎯" },
    { id: "wheel", label: "Hiệu quả vòng quay", icon: "🎡" },
    { id: "audit", label: "Nhật ký thao tác", icon: "🛡️" },
  ];
  const STATUS_LABEL = { CRITICAL: "Khẩn cấp", WARNING: "Sắp hết", OK: "Ổn định", NO_SALES: "Chưa bán" };
  const PAGE = 120;

  const state = {
    root: null, tab: "forecast", kpis: null, loadedAt: null,
    forecast: null, fDays: 30, fFilter: "ALL", fQuery: "", fLimit: PAGE, fSel: new Set(),
    rfm: null, rSeg: "", rQuery: "", rSel: new Set(), lastIssued: null,
    wheel: null,
    audit: null, aQuery: "", aMethod: "", aOffset: 0, aLimit: 30,
    suppliers: null,
  };

  // --------------------------------------------------------------------------
  // helpers
  // --------------------------------------------------------------------------
  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const num = (v) => Math.round(Number(v) || 0).toLocaleString("vi-VN");
  const money = (v) => `${num(v)}đ`;
  const short = (v) => {
    const n = Number(v) || 0;
    if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(1).replace(".0", "")} tỷ`;
    if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(1).replace(".0", "")}tr`;
    if (Math.abs(n) >= 1e3) return `${Math.round(n / 1e3)}k`;
    return `${n}`;
  };
  const fmtTime = (iso) => new Date(iso).toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit", year: "2-digit" });
  const fmtDate = (iso) => new Date(iso).toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });
  const say = (msg, type = "success") => (typeof window.notify === "function" ? window.notify(msg, type) : alert(msg));
  const $ = (sel) => state.root.querySelector(sel);
  const $$ = (sel) => [...state.root.querySelectorAll(sel)];
  const reduced = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function headers(json = true) {
    const token = localStorage.getItem("session_token");
    const h = token ? { Authorization: `Bearer ${token}` } : {};
    if (json) h["Content-Type"] = "application/json";
    return h;
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, { ...opts, headers: headers(opts.body !== undefined) });
    let data = {};
    try { data = await res.json(); } catch (_) {}
    if (!res.ok) {
      const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join(", ") : data.detail;
      throw new Error(detail || `Lỗi ${res.status}`);
    }
    return data;
  }

  function animateIn(nodes) {
    if (!window.gsap || reduced() || !nodes || !nodes.length) return;
    window.gsap.fromTo(nodes, { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: 0.45, ease: "power3.out", stagger: 0.04, clearProps: "transform,opacity" });
  }

  function countUp(el, value, formatter) {
    if (!el) return;
    if (!window.gsap || reduced()) { el.textContent = formatter(value); return; }
    const o = { v: 0 };
    window.gsap.to(o, { v: value, duration: 0.9, ease: "power2.out", onUpdate: () => { el.textContent = formatter(o.v); } });
  }

  function skeleton(rows = 5) {
    return `<div class="space-y-3 p-2">${Array.from({ length: rows }, (_, i) => `<div class="ins-skel" style="width:${90 - i * 9}%"></div>`).join("")}</div>`;
  }

  // --------------------------------------------------------------------------
  // shell + KPI strip
  // --------------------------------------------------------------------------
  function shell() {
    state.root.innerHTML = `
      <div class="space-y-4">
        <div class="ins-hero flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 class="ins-title"><i>📈</i> Phân Tích &amp; Tăng Trưởng</h2>
            <p class="lwa-muted mt-1" id="insUpdated">Đang tải dữ liệu…</p>
          </div>
          <button type="button" class="lwa-btn lwa-btn-ghost" data-act="reload">↻ Làm mới</button>
        </div>
        <div class="ins-kpis" id="insKpis"></div>
        <div class="ins-tabs" id="insTabs" role="tablist">
          ${TABS.map((t) => `<button type="button" class="ins-tab" role="tab" data-tab="${t.id}">${t.icon} ${t.label}<span class="t-badge hidden" data-badge="${t.id}"></span></button>`).join("")}
        </div>
        <div id="insPanel"></div>
      </div>`;
    $('[data-act="reload"]').addEventListener("click", () => load(true));
    $$("#insTabs [data-tab]").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));
    renderKpis();
  }

  function renderKpis() {
    const box = $("#insKpis");
    const k = state.kpis;
    if (!k) {
      box.innerHTML = Array.from({ length: 4 }, () => `<div class="ins-kpi">${skeleton(2)}</div>`).join("");
      return;
    }
    const delta = (cur, prev) => {
      if (!prev) return cur ? `<span class="ins-up">▲ mới</span> so với hôm qua` : "Chưa có phát sinh";
      const p = ((cur - prev) / prev) * 100;
      return `<span class="${p >= 0 ? "ins-up" : "ins-down"}">${p >= 0 ? "▲" : "▼"} ${Math.abs(p).toFixed(0)}%</span> so với hôm qua`;
    };
    const cards = [
      { key: "rev", tab: null, label: "Doanh thu hôm nay", value: k.revenue_today, fmt: money, sub: delta(k.revenue_today, k.revenue_yesterday), ico: "💰", tint: "#0ea5e9" },
      { key: "ord", tab: null, label: "Đơn hàng hôm nay", value: k.orders_today, fmt: num, sub: delta(k.orders_today, k.orders_yesterday), ico: "🧾", tint: "#8b5cf6" },
      { key: "low", tab: "forecast", label: "Biến thể sắp hết", value: k.low_stock_variants, fmt: num, sub: "Tồn ≤ ngưỡng cảnh báo", ico: "📦", tint: "#f59e0b" },
      { key: "risk", tab: "rfm", label: "Khách nguy cơ rời bỏ", value: k.customers_at_risk, fmt: num, sub: `${num(k.customers_need_attention)} khách cần chăm sóc`, ico: "💔", tint: "#f43f5e" },
    ];
    box.innerHTML = cards.map((c) => `
      <button type="button" class="ins-kpi" ${c.tab ? `data-goto="${c.tab}"` : ""}>
        <span class="k-ico" style="background:${c.tint}22">${c.ico}</span>
        <span class="k-label">${c.label}</span>
        <b class="k-value" data-kpi="${c.key}">0</b>
        <span class="k-sub">${c.sub}</span>
        <span class="k-bar" style="background:linear-gradient(90deg, ${c.tint}, transparent)"></span>
      </button>`).join("");
    cards.forEach((c) => countUp(box.querySelector(`[data-kpi="${c.key}"]`), Number(c.value) || 0, c.fmt));
    box.querySelectorAll("[data-goto]").forEach((b) => b.addEventListener("click", () => {
      if (b.dataset.goto === "rfm") { state.rSeg = "AT_RISK"; state.rSel.clear(); }
      if (b.dataset.goto === "forecast") { state.fFilter = "ALL"; }
      setTab(b.dataset.goto);
    }));
  }

  function setTab(tab) {
    state.tab = tab;
    $$("#insTabs [data-tab]").forEach((b) => b.classList.toggle("is-active", b.dataset.tab === tab));
    renderPanel();
    loadTab(tab);
  }

  function renderPanel() {
    const panel = $("#insPanel");
    if (state.tab === "forecast") return renderForecast(panel);
    if (state.tab === "rfm") return renderRfm(panel);
    if (state.tab === "wheel") return renderWheel(panel);
    return renderAudit(panel);
  }

  async function loadKpis() {
    try {
      state.kpis = await api(`${API}/kpis`);
      state.loadedAt = new Date();
      renderKpis();
      const up = $("#insUpdated");
      if (up) up.textContent = `Cập nhật lúc ${state.loadedAt.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}`;
    } catch (err) {
      const up = $("#insUpdated");
      if (up) up.textContent = err.message;
    }
  }

  async function loadTab(tab, force = false) {
    try {
      if (tab === "forecast" && (force || !state.forecast || state.forecast.params.days !== state.fDays)) {
        state.forecast = await api(`${API}/restock-forecast?days=${state.fDays}`);
        updateBadges();
      } else if (tab === "rfm" && (force || !state.rfm)) {
        state.rfm = await api(`${API}/rfm`);
      } else if (tab === "wheel" && (force || !state.wheel)) {
        state.wheel = await api(`${API}/wheel-performance`);
      } else if (tab === "audit") {
        const qs = new URLSearchParams({ limit: state.aLimit, offset: state.aOffset });
        if (state.aQuery) qs.set("q", state.aQuery);
        if (state.aMethod) qs.set("method", state.aMethod);
        state.audit = await api(`${API}/audit-logs?${qs}`);
      } else {
        return;
      }
      if (state.tab === tab) renderPanel();
    } catch (err) {
      if (state.tab === tab) $("#insPanel").innerHTML = `<div class="lwa-card ins-empty">⚠️ ${esc(err.message)}</div>`;
    }
  }

  function updateBadges() {
    const crit = state.forecast ? state.forecast.summary.critical : 0;
    const b = $('[data-badge="forecast"]');
    if (b) { b.textContent = crit; b.classList.toggle("hidden", !crit); }
  }

  // --------------------------------------------------------------------------
  // 1. FORECAST
  // --------------------------------------------------------------------------
  function forecastRows() {
    if (!state.forecast) return [];
    const q = state.fQuery.trim().toLowerCase();
    return state.forecast.items.filter((i) => {
      if (state.fFilter === "NEED" && !(i.suggested_qty > 0 && (i.status === "CRITICAL" || i.status === "WARNING"))) return false;
      if (!["ALL", "NEED"].includes(state.fFilter) && i.status !== state.fFilter) return false;
      if (q && !`${i.product_name} ${i.sku} ${i.size} ${i.color}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }

  function renderForecast(panel) {
    const f = state.forecast;
    if (!f) { panel.innerHTML = `<div class="lwa-card">${skeleton(6)}</div>`; return; }
    const s = f.summary;
    const chips = [
      ["ALL", "Tất cả", f.items.length], ["NEED", "Cần nhập", s.critical + s.warning],
      ["CRITICAL", STATUS_LABEL.CRITICAL, s.critical], ["WARNING", STATUS_LABEL.WARNING, s.warning],
      ["OK", STATUS_LABEL.OK, s.ok], ["NO_SALES", STATUS_LABEL.NO_SALES, s.no_sales],
    ];
    const rows = forecastRows();
    const shown = rows.slice(0, state.fLimit);
    panel.innerHTML = `
      <div class="lwa-card space-y-3">
        <div class="lwa-stats" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr))">
          <div class="lwa-stat"><b class="ins-down">${num(s.critical)}</b><span>Hết trong &lt; 7 ngày</span></div>
          <div class="lwa-stat"><b style="color:var(--c-warn)">${num(s.warning)}</b><span>Hết trong 7–14 ngày</span></div>
          <div class="lwa-stat"><b>${num(s.total_suggested_units)}</b><span>Tổng SL gợi ý nhập</span></div>
          <div class="lwa-stat"><b>${short(s.estimated_cost)}</b><span>Chi phí ước tính</span></div>
        </div>
        <div class="ins-toolbar">
          <div class="ins-chips">${chips.map(([k, l, c]) => `<button type="button" class="ins-chip ${state.fFilter === k ? "is-active" : ""}" data-filter="${k}">${l}<b>${num(c)}</b></button>`).join("")}</div>
          <div class="flex flex-wrap items-center gap-2">
            <select class="lwa-select" data-f="days" title="Khoảng thời gian tính tốc độ bán">
              ${[7, 14, 30, 60, 90].map((d) => `<option value="${d}" ${state.fDays === d ? "selected" : ""}>Bán ${d} ngày qua</option>`).join("")}
            </select>
            <input class="lwa-input" data-f="q" placeholder="Tìm sản phẩm / SKU…" value="${esc(state.fQuery)}" style="min-width:190px">
          </div>
        </div>
        <div class="ins-toolbar">
          <span class="lwa-muted">Gợi ý = đủ bán ${f.params.cover_days} ngày + ${f.params.safety_days} ngày dự phòng − tồn hiện có</span>
          <div class="flex flex-wrap gap-2">
            <button type="button" class="lwa-btn lwa-btn-ghost" data-act="pick-need">✓ Chọn hàng cần nhập</button>
            <button type="button" class="lwa-btn lwa-btn-ghost" data-act="csv">⬇ Xuất CSV</button>
            <button type="button" class="lwa-btn lwa-btn-primary" data-act="draft" ${state.fSel.size ? "" : "disabled style=\"opacity:.5;cursor:not-allowed\""}>📝 Tạo phiếu nhập nháp (${state.fSel.size})</button>
          </div>
        </div>
        <div class="overflow-x-auto">
          <table class="lwa-table ins-table">
            <thead><tr>
              <th><input type="checkbox" class="ins-check" data-act="sel-all" ${shown.length && shown.every((r) => state.fSel.has(r.variant_id)) ? "checked" : ""}></th>
              <th>Sản phẩm</th><th>Size / Màu</th><th>Tồn</th><th>Đã bán</th><th>Tốc độ / ngày</th><th>Còn ~ ngày</th><th>Gợi ý nhập</th><th>Trạng thái</th>
            </tr></thead>
            <tbody>${shown.length ? shown.map(forecastRow).join("") : `<tr><td colspan="9" class="ins-empty">Không có biến thể phù hợp.</td></tr>`}</tbody>
          </table>
        </div>
        ${rows.length > shown.length ? `<div class="text-center"><button type="button" class="lwa-btn lwa-btn-ghost" data-act="more">Hiển thị thêm (${num(rows.length - shown.length)})</button></div>` : ""}
      </div>`;

    panel.querySelectorAll("[data-filter]").forEach((b) => b.addEventListener("click", () => { state.fFilter = b.dataset.filter; state.fLimit = PAGE; renderPanel(); }));
    panel.querySelector('[data-f="days"]').addEventListener("change", (e) => { state.fDays = Number(e.target.value); state.fSel.clear(); renderForecast(panel); loadTab("forecast"); });
    const qInput = panel.querySelector('[data-f="q"]');
    qInput.addEventListener("input", debounce(() => { state.fQuery = qInput.value; state.fLimit = PAGE; renderPanel(); focusEnd('[data-f="q"]'); }, 250));
    panel.querySelector('[data-act="sel-all"]').addEventListener("change", (e) => {
      shown.forEach((r) => (e.target.checked ? state.fSel.add(r.variant_id) : state.fSel.delete(r.variant_id)));
      renderPanel();
    });
    panel.querySelectorAll("tbody [data-vid]").forEach((cb) => cb.addEventListener("change", () => {
      const id = Number(cb.dataset.vid);
      cb.checked ? state.fSel.add(id) : state.fSel.delete(id);
      cb.closest("tr").classList.toggle("is-sel", cb.checked);
      const btn = panel.querySelector('[data-act="draft"]');
      btn.textContent = `📝 Tạo phiếu nhập nháp (${state.fSel.size})`;
      btn.disabled = !state.fSel.size;
      btn.style.opacity = state.fSel.size ? "" : ".5";
      btn.style.cursor = state.fSel.size ? "" : "not-allowed";
    }));
    panel.querySelector('[data-act="pick-need"]').addEventListener("click", () => {
      state.fSel = new Set(f.items.filter((i) => i.suggested_qty > 0 && (i.status === "CRITICAL" || i.status === "WARNING")).map((i) => i.variant_id));
      if (!state.fSel.size) say("Hiện chưa có biến thể nào cần nhập gấp.", "info");
      renderPanel();
    });
    panel.querySelector('[data-act="csv"]').addEventListener("click", exportCsv);
    panel.querySelector('[data-act="draft"]').addEventListener("click", () => state.fSel.size && openDraft());
    const more = panel.querySelector('[data-act="more"]');
    if (more) more.addEventListener("click", () => { state.fLimit += PAGE; renderPanel(); });
    animateIn(panel.querySelectorAll(".lwa-stat"));
  }

  function forecastRow(i) {
    const sel = state.fSel.has(i.variant_id);
    const days = i.days_to_stockout;
    const pct = days === null ? 0 : Math.max(4, Math.min(100, (days / 30) * 100));
    const barColor = i.status === "CRITICAL" ? "#e11d48" : i.status === "WARNING" ? "#f59e0b" : "#10b981";
    return `
      <tr class="${sel ? "is-sel" : ""}">
        <td><input type="checkbox" class="ins-check" data-vid="${i.variant_id}" ${sel ? "checked" : ""}></td>
        <td style="min-width:220px"><div class="flex items-center gap-2">
          ${i.image_url ? `<img class="ins-thumb" src="${esc(i.image_url)}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">` : `<span class="ins-thumb"></span>`}
          <div><div style="font-weight:800">${esc(i.product_name)}</div><div class="ins-mono">${esc(i.sku)}</div></div>
        </div></td>
        <td class="whitespace-nowrap">${esc(i.size)} · <span class="ins-dot" style="background:${esc(i.color_hex || "#cbd5e1")}"></span> ${esc(i.color)}</td>
        <td><b class="${i.available_quantity <= 0 ? "ins-down" : ""}">${num(i.available_quantity)}</b></td>
        <td>${num(i.units_sold)}</td>
        <td>${i.daily_velocity ? i.daily_velocity.toLocaleString("vi-VN", { maximumFractionDigits: 2 }) : "—"}</td>
        <td class="whitespace-nowrap">${days === null ? "—" : `<div class="flex items-center gap-2"><b>${days.toLocaleString("vi-VN")}</b><span class="ins-meter"><i style="width:${pct}%;background:${barColor}"></i></span></div>`}</td>
        <td><b style="color:var(--c-accent)">${i.suggested_qty ? `+${num(i.suggested_qty)}` : "—"}</b></td>
        <td><span class="ins-st ins-st-${i.status}">${STATUS_LABEL[i.status]}</span></td>
      </tr>`;
  }

  function exportCsv() {
    const rows = state.fSel.size ? state.forecast.items.filter((i) => state.fSel.has(i.variant_id)) : forecastRows();
    const head = ["SKU", "Sản phẩm", "Size", "Màu", "Tồn", `Đã bán ${state.fDays} ngày`, "Tốc độ/ngày", "Còn ~ngày", "Gợi ý nhập", "Giá vốn gợi ý", "Trạng thái"];
    const cell = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const lines = [head.map(cell).join(",")].concat(rows.map((i) => [
      i.sku, i.product_name, i.size, i.color, i.available_quantity, i.units_sold, i.daily_velocity,
      i.days_to_stockout ?? "", i.suggested_qty, i.suggested_unit_cost, STATUS_LABEL[i.status],
    ].map(cell).join(",")));
    const blob = new Blob(["\ufeff" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `du-bao-nhap-hang-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
    say(`Đã xuất ${rows.length} dòng ra CSV.`);
  }

  async function openDraft() {
    const items = state.forecast.items.filter((i) => state.fSel.has(i.variant_id));
    if (!state.suppliers) {
      try { state.suppliers = (await api("/api/v1/inventory/suppliers")).filter((s) => s.is_active !== false); }
      catch (err) { say(err.message, "error"); return; }
    }
    if (!state.suppliers.length) { say("Chưa có nhà cung cấp nào. Vui lòng tạo nhà cung cấp trong cổng Kho trước.", "error"); return; }
    const wrap = document.createElement("div");
    wrap.className = "ins-modal";
    wrap.innerHTML = `
      <form class="ins-modal-card space-y-3">
        <div class="flex items-start justify-between gap-3">
          <div>
            <h3 class="lwa-h" style="font-size:17px">📝 Phiếu nhập nháp</h3>
            <p class="lwa-muted mt-1">Kiểm tra số lượng & giá vốn trước khi xác nhận. Xác nhận sẽ cộng tồn kho ngay.</p>
          </div>
          <button type="button" class="lwa-btn lwa-btn-ghost" data-close>✕</button>
        </div>
        <div class="grid gap-2 sm:grid-cols-2">
          <label class="lwa-field">Nhà cung cấp
            <select class="lwa-select" name="supplier" required>${state.suppliers.map((s) => `<option value="${s.id}">${esc(s.code)} · ${esc(s.name)}</option>`).join("")}</select>
          </label>
          <label class="lwa-field">Ghi chú
            <input class="lwa-input" name="note" maxlength="300" value="Nhập theo Dự báo nhập hàng (${state.fDays} ngày)">
          </label>
        </div>
        <div class="overflow-x-auto">
          <table class="lwa-table ins-table">
            <thead><tr><th>Sản phẩm</th><th>Tồn</th><th>Số lượng</th><th>Giá vốn (đ)</th><th>Thành tiền</th><th></th></tr></thead>
            <tbody>${items.map((i) => `
              <tr data-vid="${i.variant_id}">
                <td style="min-width:200px"><div style="font-weight:800">${esc(i.product_name)}</div><div class="ins-mono">${esc(i.sku)} · ${esc(i.size)} / ${esc(i.color)}</div></td>
                <td>${num(i.available_quantity)}</td>
                <td style="width:100px"><input class="lwa-input" type="number" min="1" step="1" data-q value="${Math.max(1, i.suggested_qty || 10)}" required></td>
                <td style="width:130px"><input class="lwa-input" type="number" min="0" step="1000" data-c value="${Math.round(i.suggested_unit_cost || 0)}" required></td>
                <td class="whitespace-nowrap" data-line>—</td>
                <td><button type="button" class="lwa-btn lwa-btn-danger" data-rm title="Bỏ dòng">✕</button></td>
              </tr>`).join("")}</tbody>
          </table>
        </div>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="lwa-muted">Tổng: <span class="ins-total" data-total>0đ</span> · <span data-count></span></div>
          <div class="flex gap-2">
            <button type="button" class="lwa-btn lwa-btn-ghost" data-close>Huỷ</button>
            <button type="submit" class="lwa-btn lwa-btn-primary">✓ Xác nhận nhập kho</button>
          </div>
        </div>
      </form>`;
    document.body.appendChild(wrap);
    // Kế thừa theme + biến màu của module
    wrap.classList.add(...[...state.root.classList].filter((c) => /^(lwa|ins)-/.test(c)));
    const form = wrap.querySelector("form");
    const recalc = () => {
      let total = 0, units = 0;
      const trs = [...form.querySelectorAll("tbody tr")];
      trs.forEach((tr) => {
        const q = Number(tr.querySelector("[data-q]").value) || 0;
        const c = Number(tr.querySelector("[data-c]").value) || 0;
        tr.querySelector("[data-line]").textContent = money(q * c);
        total += q * c; units += q;
      });
      form.querySelector("[data-total]").textContent = money(total);
      form.querySelector("[data-count]").textContent = `${trs.length} dòng · ${num(units)} sản phẩm`;
    };
    const close = () => wrap.remove();
    form.addEventListener("input", recalc);
    form.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", close));
    wrap.addEventListener("click", (e) => { if (e.target === wrap) close(); });
    form.querySelectorAll("[data-rm]").forEach((b) => b.addEventListener("click", () => {
      b.closest("tr").remove();
      if (!form.querySelector("tbody tr")) close(); else recalc();
    }));
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const payload = {
        supplier_id: Number(form.supplier.value),
        note: form.note.value.trim() || null,
        items: [...form.querySelectorAll("tbody tr")].map((tr) => ({
          variant_id: Number(tr.dataset.vid),
          quantity: Number(tr.querySelector("[data-q]").value),
          unit_cost: Number(tr.querySelector("[data-c]").value),
        })),
      };
      if (payload.items.some((i) => !(i.quantity > 0) || i.unit_cost < 0)) { say("Số lượng phải > 0 và giá vốn không âm.", "error"); return; }
      const btn = form.querySelector('[type="submit"]');
      btn.disabled = true; btn.textContent = "Đang xác nhận…";
      try {
        const r = await api("/api/v1/inventory/receipts/confirm", { method: "POST", body: JSON.stringify(payload) });
        say(`${r.message}${r.receipt && r.receipt.code ? ` (${r.receipt.code})` : ""}`);
        close();
        state.fSel.clear();
        loadTab("forecast", true);
        loadKpis();
      } catch (err) {
        say(err.message, "error");
        btn.disabled = false; btn.textContent = "✓ Xác nhận nhập kho";
      }
    });
    recalc();
    if (window.gsap && !reduced()) window.gsap.fromTo(form, { opacity: 0, y: 24, scale: 0.98 }, { opacity: 1, y: 0, scale: 1, duration: 0.4, ease: "power3.out" });
  }

  // --------------------------------------------------------------------------
  // 2. RFM
  // --------------------------------------------------------------------------
  function segMeta(code) {
    return (state.rfm && state.rfm.segments.find((s) => s.code === code)) || { label: code, color: "#64748b" };
  }

  function rfmRows() {
    if (!state.rfm) return [];
    const q = state.rQuery.trim().toLowerCase();
    return state.rfm.customers.filter((c) =>
      (!state.rSeg || c.segment === state.rSeg) &&
      (!q || `${c.name} ${c.email} ${c.phone || ""}`.toLowerCase().includes(q)));
  }

  function score(n) {
    return `<span class="ins-score">${[1, 2, 3, 4, 5].map((i) => `<i class="${i <= n ? "on" : ""}"></i>`).join("")}</span>`;
  }

  function renderRfm(panel) {
    const d = state.rfm;
    if (!d) { panel.innerHTML = `<div class="lwa-card">${skeleton(6)}</div>`; return; }
    const rows = rfmRows();
    const seg = state.rSeg ? segMeta(state.rSeg) : null;
    panel.innerHTML = `
      <div class="space-y-3">
        <div class="ins-segs">${d.segments.map((s) => `
          <button type="button" class="ins-seg ${state.rSeg === s.code ? "is-active" : ""}" data-seg="${s.code}" style="--seg:${s.color}" title="${esc(s.hint)}">
            <span class="s-name">${esc(s.label)}</span>
            <b class="s-count">${num(s.count)}</b>
            <span class="s-meta">${short(s.total_spend)}đ${s.avg_recency_days !== null ? ` · ~${s.avg_recency_days} ngày` : ""}</span>
          </button>`).join("")}</div>

        <div class="lwa-card space-y-3">
          <div class="ins-toolbar">
            <div class="flex items-center gap-2">
              <h3 class="lwa-h">${seg ? `<span class="ins-segpill" style="--seg:${seg.color}">${esc(seg.label)}</span>` : "Tất cả khách hàng"}</h3>
              <span class="lwa-muted">${num(rows.length)} / ${num(d.total_customers)} khách</span>
              ${seg ? `<button type="button" class="lwa-btn lwa-btn-ghost" data-act="clear-seg" style="padding:.3rem .6rem">✕ Bỏ lọc</button>` : ""}
            </div>
            <input class="lwa-input" data-f="q" placeholder="Tìm tên, email, SĐT…" value="${esc(state.rQuery)}" style="min-width:220px">
          </div>

          <form class="ins-actionbar" data-form="voucher">
            <label class="lwa-field">Giảm (%)<input class="lwa-input" type="number" name="pct" min="1" max="90" step="1" value="10" required></label>
            <label class="lwa-field">Hạn dùng (ngày)<input class="lwa-input" type="number" name="days" min="1" max="365" value="14" required></label>
            <label class="lwa-field">Đơn tối thiểu (đ)<input class="lwa-input" type="number" name="min" min="0" step="10000" value="0"></label>
            <div class="flex flex-wrap gap-2 ml-auto">
              <button type="submit" class="lwa-btn lwa-btn-primary" data-mode="selected" ${state.rSel.size ? "" : "disabled style=\"opacity:.5;cursor:not-allowed\""}>💌 Gửi cho khách đã chọn (${state.rSel.size})</button>
              ${seg ? `<button type="submit" class="lwa-btn lwa-btn-gold" data-mode="segment" ${segMeta(state.rSeg).count ? "" : "disabled style=\"opacity:.5\""}>🎁 Gửi cả nhóm «${esc(seg.label)}» (${num(segMeta(state.rSeg).count)})</button>` : ""}
            </div>
          </form>
          ${state.lastIssued ? `
            <div class="lwa-card" style="padding:.8rem 1rem">
              <div class="flex items-center justify-between gap-2 mb-2"><b style="font-size:12.5px">✅ ${esc(state.lastIssued.message)}</b>
                <button type="button" class="lwa-btn lwa-btn-ghost" data-act="copy-codes" style="padding:.3rem .6rem">⧉ Sao chép mã</button></div>
              <div class="ins-codes">${state.lastIssued.vouchers.map((v) => `<span class="ins-code" title="${esc(v.email)}">${esc(v.code)} · ${esc(v.name)}</span>`).join("")}</div>
            </div>` : ""}

          <div class="overflow-x-auto">
            <table class="lwa-table ins-table">
              <thead><tr>
                <th><input type="checkbox" class="ins-check" data-act="sel-all" ${rows.length && rows.every((r) => state.rSel.has(r.account_id)) ? "checked" : ""}></th>
                <th>Khách hàng</th><th>Phân khúc</th><th>R · F · M</th><th>Đơn gần nhất</th><th>Số đơn</th><th>Tổng chi tiêu</th>
              </tr></thead>
              <tbody>${rows.length ? rows.slice(0, 300).map((c) => {
                const m = segMeta(c.segment);
                const sel = state.rSel.has(c.account_id);
                return `
                <tr class="${sel ? "is-sel" : ""}">
                  <td><input type="checkbox" class="ins-check" data-aid="${c.account_id}" ${sel ? "checked" : ""}></td>
                  <td style="min-width:200px"><div style="font-weight:800">${esc(c.name)}</div><div class="ins-mono">${esc(c.email)}</div></td>
                  <td><span class="ins-segpill" style="--seg:${m.color}">${esc(c.segment_label)}</span></td>
                  <td class="whitespace-nowrap" title="R${c.r} F${c.f} M${c.m}">${score(c.r)} ${score(c.f)} ${score(c.m)}</td>
                  <td class="whitespace-nowrap">${c.last_order_at ? fmtDate(c.last_order_at) : "—"}<div class="lwa-muted" style="font-size:10.5px">${c.recency_days === 0 ? "hôm nay" : `${num(c.recency_days)} ngày trước`}</div></td>
                  <td>${num(c.orders)}</td>
                  <td><b>${money(c.spend)}</b></td>
                </tr>`;
              }).join("") : `<tr><td colspan="7" class="ins-empty">Chưa có khách hàng trong nhóm này.</td></tr>`}</tbody>
            </table>
          </div>
        </div>
      </div>`;

    panel.querySelectorAll("[data-seg]").forEach((b) => b.addEventListener("click", () => {
      state.rSeg = state.rSeg === b.dataset.seg ? "" : b.dataset.seg;
      state.rSel.clear();
      renderPanel();
    }));
    const clear = panel.querySelector('[data-act="clear-seg"]');
    if (clear) clear.addEventListener("click", () => { state.rSeg = ""; state.rSel.clear(); renderPanel(); });
    const qInput = panel.querySelector('[data-f="q"]');
    qInput.addEventListener("input", debounce(() => { state.rQuery = qInput.value; renderPanel(); focusEnd('[data-f="q"]'); }, 250));
    panel.querySelector('[data-act="sel-all"]').addEventListener("change", (e) => {
      rows.forEach((r) => (e.target.checked ? state.rSel.add(r.account_id) : state.rSel.delete(r.account_id)));
      renderPanel();
    });
    panel.querySelectorAll("[data-aid]").forEach((cb) => cb.addEventListener("change", () => {
      const id = Number(cb.dataset.aid);
      cb.checked ? state.rSel.add(id) : state.rSel.delete(id);
      cb.closest("tr").classList.toggle("is-sel", cb.checked);
      const btn = panel.querySelector('[data-mode="selected"]');
      btn.textContent = `💌 Gửi cho khách đã chọn (${state.rSel.size})`;
      btn.disabled = !state.rSel.size;
      btn.style.opacity = state.rSel.size ? "" : ".5";
      btn.style.cursor = state.rSel.size ? "" : "not-allowed";
    }));
    const form = panel.querySelector('[data-form="voucher"]');
    form.addEventListener("submit", (e) => { e.preventDefault(); sendVouchers(form, (e.submitter && e.submitter.dataset.mode) || "selected"); });
    const copy = panel.querySelector('[data-act="copy-codes"]');
    if (copy) copy.addEventListener("click", () => {
      const text = state.lastIssued.vouchers.map((v) => `${v.code}\t${v.name}\t${v.email}`).join("\n");
      (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(() => say("Đã sao chép danh sách mã."), () => say("Không thể sao chép tự động.", "error"));
    });
    animateIn(panel.querySelectorAll(".ins-seg"));
  }

  async function sendVouchers(form, mode) {
    const body = {
      discount_percent: Number(form.pct.value),
      valid_days: Number(form.days.value),
      minimum_order_amount: Number(form.min.value || 0),
    };
    let who;
    if (mode === "segment" && state.rSeg) {
      body.segment = state.rSeg;
      who = `toàn bộ ${num(segMeta(state.rSeg).count)} khách nhóm «${segMeta(state.rSeg).label}»`;
    } else {
      if (!state.rSel.size) { say("Hãy chọn ít nhất một khách hàng.", "error"); return; }
      body.account_ids = [...state.rSel];
      who = `${num(state.rSel.size)} khách đã chọn`;
    }
    if (!confirm(`Gửi voucher giảm ${body.discount_percent}% (hạn ${body.valid_days} ngày) cho ${who}?\nMỗi khách nhận 1 mã riêng, dùng 1 lần.`)) return;
    try {
      const r = await api(`${API}/rfm/vouchers`, { method: "POST", body: JSON.stringify(body) });
      state.lastIssued = r;
      state.rSel.clear();
      say(r.message);
      renderPanel();
    } catch (err) { say(err.message, "error"); }
  }

  // --------------------------------------------------------------------------
  // 3. WHEEL PERFORMANCE
  // --------------------------------------------------------------------------
  function renderWheel(panel) {
    const d = state.wheel;
    if (!d) { panel.innerHTML = `<div class="lwa-card">${skeleton(6)}</div>`; return; }
    const t = d.totals;
    const maxShare = Math.max(1, ...d.slots.map((s) => s.spins));
    panel.innerHTML = `
      <div class="space-y-3">
        <div class="lwa-stats" style="grid-template-columns:repeat(auto-fit,minmax(140px,1fr))">
          ${[
            ["Tổng lượt quay", num(t.total_spins)], ["Tỷ lệ trúng", `${t.win_rate_percent}%`],
            ["Voucher đã phát", num(t.vouchers_issued)], ["Voucher đã dùng", num(t.vouchers_used)],
            ["Tỷ lệ sử dụng", `${t.usage_rate_percent}%`], ["Doanh thu mang lại", short(t.revenue) + "đ"],
            ["Chi phí giảm giá", short(t.discount) + "đ"],
          ].map(([k, v]) => `<div class="lwa-stat"><b>${v}</b><span>${k}</span></div>`).join("")}
        </div>
        <div class="lwa-grid" style="grid-template-columns:minmax(0,1fr)">
          <div class="lwa-card">
            <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
              <h3 class="lwa-h">📊 Lượt quay ${d.daily.length} ngày gần nhất</h3>
              <div class="ins-legend"><span style="--sw:var(--c-accent);opacity:.6">Lượt quay</span><span style="--sw:#f59e0b">Lượt trúng</span></div>
            </div>
            ${wheelChart(d.daily)}
          </div>
          <div class="lwa-card">
            <h3 class="lwa-h mb-2">🎯 Hiệu quả theo ô</h3>
            <div class="overflow-x-auto">
              <table class="lwa-table ins-table">
                <thead><tr><th>Ô quay</th><th>Lượt rơi vào</th><th>Tỷ trọng</th><th>Trúng</th><th>Voucher đã dùng</th><th>Doanh thu</th></tr></thead>
                <tbody>${d.slots.length ? d.slots.map((s) => `
                  <tr class="${s.is_active ? "" : "is-off"}">
                    <td class="whitespace-nowrap"><span class="ins-dot" style="background:${esc(s.color)}"></span> <b>${esc(s.label)}</b></td>
                    <td>${num(s.spins)}</td>
                    <td class="whitespace-nowrap"><div class="flex items-center gap-2"><span class="ins-meter" style="width:110px"><i style="width:${(s.spins / maxShare) * 100}%;background:${esc(s.color)}"></i></span>${s.share_percent}%</div></td>
                    <td>${num(s.wins)}</td>
                    <td>${num(s.used)}${s.wins ? ` <span class="lwa-muted">(${Math.round((s.used / s.wins) * 100)}%)</span>` : ""}</td>
                    <td><b>${money(s.revenue)}</b></td>
                  </tr>`).join("") : `<tr><td colspan="6" class="ins-empty">Chưa có dữ liệu vòng quay.</td></tr>`}</tbody>
              </table>
            </div>
          </div>
        </div>
      </div>`;
    animateIn(panel.querySelectorAll(".lwa-stat"));
    if (window.gsap && !reduced()) {
      window.gsap.from(panel.querySelectorAll(".ins-chart rect[data-h]"), { scaleY: 0, transformOrigin: "50% 100%", duration: 0.6, ease: "power3.out", stagger: 0.025 });
    }
  }

  function wheelChart(daily) {
    const W = 700, H = 190, padL = 30, padB = 22, padT = 10;
    const max = Math.max(1, ...daily.map((d) => d.spins));
    const step = (W - padL - 6) / daily.length;
    const bw = Math.max(6, step * 0.62);
    const y = (v) => H - padB - ((H - padB - padT) * v) / max;
    const ticks = [0, Math.ceil(max / 2), max].filter((v, i, a) => a.indexOf(v) === i);
    return `
      <svg class="ins-chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Biểu đồ lượt quay theo ngày">
        <defs><linearGradient id="insWinGrad" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#f59e0b"/><stop offset="1" stop-color="#f43f5e"/></linearGradient></defs>
        ${ticks.map((v) => `<line class="grid" x1="${padL}" x2="${W}" y1="${y(v)}" y2="${y(v)}"/><text x="${padL - 6}" y="${y(v) + 3}" text-anchor="end">${v}</text>`).join("")}
        ${daily.map((d, i) => {
          const x = padL + i * step + (step - bw) / 2;
          const dt = new Date(d.date + "T00:00:00");
          return `
            <g><title>${dt.toLocaleDateString("vi-VN")}: ${d.spins} lượt quay, ${d.wins} lượt trúng</title>
              <rect data-h class="bar" x="${x}" y="${y(d.spins)}" width="${bw}" height="${H - padB - y(d.spins)}" rx="3"/>
              <rect data-h class="bar-win" x="${x + bw * 0.2}" y="${y(d.wins)}" width="${bw * 0.6}" height="${H - padB - y(d.wins)}" rx="2"/>
              ${daily.length <= 16 || i % 2 === 0 ? `<text x="${x + bw / 2}" y="${H - 6}" text-anchor="middle">${dt.getDate()}/${dt.getMonth() + 1}</text>` : ""}
            </g>`;
        }).join("")}
      </svg>`;
  }

  // --------------------------------------------------------------------------
  // 4. AUDIT LOG
  // --------------------------------------------------------------------------
  function renderAudit(panel) {
    const d = state.audit;
    const page = d ? Math.floor(d.offset / d.limit) + 1 : 1;
    const pages = d ? Math.max(1, Math.ceil(d.total / d.limit)) : 1;
    panel.innerHTML = `
      <div class="lwa-card space-y-3">
        <div class="ins-toolbar">
          <h3 class="lwa-h">🛡️ Nhật ký thao tác nhân sự ${d ? `<span class="lwa-muted">· ${num(d.total)} bản ghi</span>` : ""}</h3>
          <div class="flex flex-wrap items-center gap-2">
            <select class="lwa-select" data-f="method">
              ${[["", "Mọi thao tác"], ["POST", "POST · Tạo"], ["PUT", "PUT · Sửa"], ["PATCH", "PATCH · Sửa"], ["DELETE", "DELETE · Xoá"]]
                .map(([v, l]) => `<option value="${v}" ${state.aMethod === v ? "selected" : ""}>${l}</option>`).join("")}
            </select>
            <input class="lwa-input" data-f="q" placeholder="Tìm người thực hiện, nội dung…" value="${esc(state.aQuery)}" style="min-width:230px">
          </div>
        </div>
        ${!d ? skeleton(6) : `
        <div class="overflow-x-auto">
          <table class="lwa-table ins-table">
            <thead><tr><th>Thời gian</th><th>Người thực hiện</th><th>Thao tác</th><th>Nội dung</th><th>Đường dẫn</th><th>IP</th></tr></thead>
            <tbody>${d.items.length ? d.items.map((r) => `
              <tr>
                <td class="whitespace-nowrap">${fmtTime(r.created_at)}</td>
                <td class="whitespace-nowrap"><b>${esc(r.account_name)}</b> <span class="ins-role">${esc(r.role_code)}</span></td>
                <td><span class="ins-method ins-m-${esc(r.method)}">${esc(r.method)}</span></td>
                <td style="min-width:220px;font-weight:700">${esc(r.summary)}</td>
                <td class="ins-mono">${esc(r.path)}</td>
                <td class="ins-mono">${esc(r.ip || "—")}</td>
              </tr>`).join("") : `<tr><td colspan="6" class="ins-empty">Chưa có thao tác nào được ghi nhận.</td></tr>`}</tbody>
          </table>
        </div>
        <div class="flex items-center justify-between gap-2">
          <span class="lwa-muted">Trang ${page} / ${pages}</span>
          <div class="flex gap-2">
            <button type="button" class="lwa-btn lwa-btn-ghost" data-page="-1" ${page <= 1 ? "disabled style=\"opacity:.45\"" : ""}>← Trước</button>
            <button type="button" class="lwa-btn lwa-btn-ghost" data-page="1" ${page >= pages ? "disabled style=\"opacity:.45\"" : ""}>Sau →</button>
          </div>
        </div>`}
      </div>`;
    panel.querySelector('[data-f="method"]').addEventListener("change", (e) => { state.aMethod = e.target.value; state.aOffset = 0; loadTab("audit"); });
    const qInput = panel.querySelector('[data-f="q"]');
    qInput.addEventListener("input", debounce(() => { state.aQuery = qInput.value.trim(); state.aOffset = 0; loadTab("audit").then(() => focusEnd('[data-f="q"]')); }, 350));
    panel.querySelectorAll("[data-page]").forEach((b) => b.addEventListener("click", () => {
      if (b.disabled) return;
      state.aOffset = Math.max(0, state.aOffset + Number(b.dataset.page) * state.aLimit);
      loadTab("audit");
    }));
  }

  // --------------------------------------------------------------------------
  // misc
  // --------------------------------------------------------------------------
  function debounce(fn, ms) {
    let t;
    return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
  }

  function focusEnd(sel) {
    const el = $(sel);
    if (!el) return;
    el.focus();
    const v = el.value;
    el.setSelectionRange(v.length, v.length);
  }

  async function load(force = false) {
    if (!state.root) return init();
    loadKpis();
    if (force) ["forecast", "rfm", "wheel"].forEach((k) => { if (k !== state.tab) state[k] = null; });
    await loadTab(state.tab, force);
  }

  function init() {
    const root = document.getElementById("insightsAdminRoot");
    if (!root) return;
    state.root = root;
    root.classList.add("lwa-root", "ins-root");
    if (root.dataset.theme === "dark") root.classList.add("lwa-dark", "ins-dark");
    shell();
    setTab(state.tab);
    loadKpis();
  }

  window.soobinInsights = { load: () => (state.root ? load(true) : init()) };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
