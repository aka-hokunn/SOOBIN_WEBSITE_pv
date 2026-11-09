/**
 * ============================================================================
 * SOOBIN LUCKY WHEEL — bảng quản lý cho ADMIN & MANAGER (dùng chung 1 module)
 *  - Cấu hình: bật/tắt, tiêu đề, số lượt / chu kỳ, thời gian reset, nạp lại
 *    voucher mỗi chu kỳ, hạn dùng voucher trúng thưởng, nút "Reset ngay".
 *  - Ô quay: voucher phần thưởng, tỷ lệ ra (%), số lượng voucher trong vòng quay
 *    (bỏ trống voucher hoặc số lượng ⇒ ô KHÔNG TRÚNG THƯỞNG), màu, bật/tắt.
 *  - Kho voucher: Manager can thiệp giống Admin (tạo, bật/tắt, gắn vào ô quay).
 *  - Thống kê + lịch sử lượt quay gần nhất, xem trước bánh xe trực tiếp.
 * ============================================================================
 */
(function () {
  "use strict";

  const API = "/api/v1/lucky-wheel";
  const state = { data: null, vouchers: [], preview: null, timer: null, root: null };

  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (v) => `${Math.round(Number(v) || 0).toLocaleString("vi-VN")}đ`;
  const fmtTime = (iso) => new Date(iso).toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" });
  const say = (msg, type = "success") => (typeof window.notify === "function" ? window.notify(msg, type) : alert(msg));

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

  function splitInterval(minutes) {
    const m = Number(minutes) || 1440;
    if (m % 1440 === 0) return { value: m / 1440, unit: 1440 };
    if (m % 60 === 0) return { value: m / 60, unit: 60 };
    return { value: m, unit: 1 };
  }

  function countdown(iso) {
    const s = Math.max(0, Math.floor((new Date(iso).getTime() - Date.now()) / 1000));
    const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
    const p = (n) => String(n).padStart(2, "0");
    return `${d > 0 ? d + " ngày " : ""}${p(h)}:${p(m)}:${p(x)}`;
  }

  // --------------------------------------------------------------------------
  // RENDER
  // --------------------------------------------------------------------------
  function shell() {
    state.root.innerHTML = `
      <div class="space-y-4">
        <div class="lwa-card flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 class="lwa-h" style="font-size:18px">🎡 Vòng Quay May Mắn — Voucher riêng cho khách hàng</h2>
            <p class="lwa-muted mt-1">Ô không chọn voucher hoặc không nhập số lượng sẽ mặc định là <b>không trúng thưởng</b>. Xác suất thực = tỷ lệ của ô ÷ tổng tỷ lệ các ô đang bật.</p>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <span class="lwa-muted">Reset sau: <b id="lwaCountdown" style="color:var(--c-accent)">--:--:--</b></span>
            <button type="button" class="lwa-btn lwa-btn-ghost" data-act="reload">↻ Làm mới</button>
            <button type="button" class="lwa-btn lwa-btn-gold" data-act="reset">⟲ Reset vòng quay ngay</button>
          </div>
        </div>
        <div class="lwa-stats" id="lwaStats"></div>
        <div class="lwa-grid">
          <div class="space-y-4">
            <form class="lwa-card space-y-3" id="lwaConfig"></form>
            <div class="lwa-card">
              <h3 class="lwa-h">👀 Xem trước bánh xe</h3>
              <p class="lwa-muted mb-2">Cập nhật ngay khi bạn chỉnh nhãn, màu hoặc bật/tắt ô.</p>
              <div id="lwaPreview"></div>
            </div>
          </div>
          <div class="space-y-4">
            <div class="lwa-card space-y-3">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <h3 class="lwa-h">🎯 Các ô trên vòng quay</h3>
                <div class="flex gap-2">
                  <button type="button" class="lwa-btn lwa-btn-ghost" data-act="add-slot">+ Thêm ô</button>
                  <button type="button" class="lwa-btn lwa-btn-primary" data-act="save-all">💾 Lưu tất cả ô</button>
                </div>
              </div>
              <div id="lwaWeights"></div>
              <div class="overflow-x-auto"><table class="lwa-table" id="lwaSlots"></table></div>
            </div>
            <div class="lwa-card space-y-3" id="lwaVouchers"></div>
            <div class="lwa-card">
              <h3 class="lwa-h mb-2">🕘 Lượt quay gần đây</h3>
              <div class="overflow-x-auto"><table class="lwa-table" id="lwaRecent"></table></div>
            </div>
          </div>
        </div>
      </div>`;
    state.root.querySelector('[data-act="reload"]').addEventListener("click", load);
    state.root.querySelector('[data-act="reset"]').addEventListener("click", resetNow);
    state.root.querySelector('[data-act="add-slot"]').addEventListener("click", () => addSlot());
    state.root.querySelector('[data-act="save-all"]').addEventListener("click", saveAll);
  }

  function renderStats() {
    const s = state.data.stats;
    document.getElementById("lwaStats").innerHTML = [
      ["Tổng lượt quay", s.total_spins], ["Lượt trúng", s.total_wins], ["Tỷ lệ trúng thực tế", `${s.win_rate_percent}%`],
      ["Lượt quay chu kỳ này", s.period_spins], ["Voucher đã được dùng", s.vouchers_redeemed],
    ].map(([k, v]) => `<div class="lwa-stat"><b>${v}</b><span>${k}</span></div>`).join("");
  }

  function renderConfig() {
    const c = state.data.config;
    const iv = splitInterval(c.reset_interval_minutes);
    const form = document.getElementById("lwaConfig");
    form.innerHTML = `
      <div class="flex items-center justify-between">
        <h3 class="lwa-h">⚙️ Cấu hình vòng quay</h3>
        <label class="flex items-center gap-2 lwa-muted"><span>${c.enabled ? "Đang bật" : "Đang tắt"}</span>
          <span class="lwa-switch"><input type="checkbox" name="enabled" ${c.enabled ? "checked" : ""}><span></span></span></label>
      </div>
      <label class="lwa-field">Tên vòng quay<input class="lwa-input" name="title" maxlength="120" value="${esc(c.title)}" required></label>
      <label class="lwa-field">Mô tả ngắn<input class="lwa-input" name="subtitle" maxlength="120" value="${esc(c.subtitle || "")}"></label>
      <div class="grid grid-cols-2 gap-2">
        <label class="lwa-field">Số lượt / khách / chu kỳ<input class="lwa-input" type="number" min="1" max="50" name="spins_per_period" value="${c.spins_per_period}" required></label>
        <label class="lwa-field">Hạn voucher trúng (ngày)<input class="lwa-input" type="number" min="1" max="365" name="voucher_valid_days" value="${c.voucher_valid_days}" required></label>
      </div>
      <div class="lwa-field">Thời gian reset vòng quay (chu kỳ)
        <div class="grid grid-cols-2 gap-2">
          <input class="lwa-input" type="number" min="1" name="interval_value" value="${iv.value}" required>
          <select class="lwa-select" name="interval_unit">
            <option value="1" ${iv.unit === 1 ? "selected" : ""}>phút</option>
            <option value="60" ${iv.unit === 60 ? "selected" : ""}>giờ</option>
            <option value="1440" ${iv.unit === 1440 ? "selected" : ""}>ngày</option>
          </select>
        </div>
      </div>
      <label class="flex items-start gap-2 lwa-muted" style="font-size:12px">
        <span class="lwa-switch" style="margin-top:2px"><input type="checkbox" name="restock_on_reset" ${c.restock_on_reset ? "checked" : ""}><span></span></span>
        <span>Mỗi lần reset: hồi lượt quay cho khách <b>và nạp lại số lượng voucher</b> của từng ô.</span>
      </label>
      <p class="lwa-muted">Chu kỳ hiện tại bắt đầu ${fmtTime(state.data.current_period_start)} · kết thúc ${fmtTime(state.data.next_reset_at)}</p>
      <button type="submit" class="lwa-btn lwa-btn-primary w-full">💾 Lưu cấu hình</button>`;
    form.onsubmit = saveConfig;
  }

  function voucherOptions(selected) {
    return `<option value="">— Không trúng thưởng —</option>` + state.vouchers.map((v) =>
      `<option value="${v.id}" ${Number(selected) === v.id ? "selected" : ""}>${esc(v.code)} · -${v.discount_percent}%${v.minimum_order_amount > 0 ? ` (≥${Math.round(v.minimum_order_amount / 1000)}k)` : ""}${v.is_active ? "" : " · mẫu ẩn"}</option>`).join("");
  }

  function renderSlots() {
    const table = document.getElementById("lwaSlots");
    table.innerHTML = `
      <thead><tr><th>Bật</th><th>Màu</th><th>Nhãn hiển thị</th><th>Voucher phần thưởng</th><th>Tỷ lệ ra (%)</th><th>Số lượng</th><th>Còn lại</th><th>Xác suất thực</th><th>Đã trúng</th><th></th></tr></thead>
      <tbody>${state.data.slots.map((s) => `
        <tr data-id="${s.id}" class="${s.is_active ? "" : "is-off"}">
          <td><span class="lwa-switch"><input type="checkbox" data-f="is_active" ${s.is_active ? "checked" : ""}><span></span></span></td>
          <td><input type="color" class="lwa-color" data-f="color" value="${esc(s.color)}"></td>
          <td style="min-width:140px"><input class="lwa-input" data-f="label" maxlength="80" value="${esc(s.label)}" placeholder="Tự động"></td>
          <td style="min-width:190px"><select class="lwa-select" data-f="promotion_id">${voucherOptions(s.promotion_id)}</select></td>
          <td style="width:96px"><input class="lwa-input" type="number" min="0" max="100" step="0.1" data-f="win_weight" value="${s.win_weight}"></td>
          <td style="width:104px"><input class="lwa-input" type="number" min="0" step="1" data-f="quantity_total" value="${s.quantity_total ?? ""}" placeholder="Trống"></td>
          <td>${s.quantity_total ? `<b>${s.quantity_remaining ?? 0}</b>/${s.quantity_total}` : "—"}</td>
          <td><b data-prob>${s.probability_percent}%</b><div data-kind style="margin-top:2px">${kindPill(s.promotion_id, s.quantity_total)}</div></td>
          <td>${s.win_count}</td>
          <td class="whitespace-nowrap">
            <button type="button" class="lwa-btn lwa-btn-primary" data-row="save">Lưu</button>
            <button type="button" class="lwa-btn lwa-btn-danger" data-row="del" title="Xoá ô">✕</button>
          </td>
        </tr>`).join("")}</tbody>`;

    table.querySelectorAll("tbody tr").forEach((tr) => {
      tr.querySelectorAll("[data-f]").forEach((el) => el.addEventListener("input", () => { tr.dataset.dirty = "1"; liveUpdate(); }));
      tr.querySelectorAll("[data-f]").forEach((el) => el.addEventListener("change", () => { tr.dataset.dirty = "1"; liveUpdate(); }));
      tr.querySelector('[data-row="save"]').addEventListener("click", () => saveRow(tr));
      tr.querySelector('[data-row="del"]').addEventListener("click", () => deleteRow(tr));
    });
    liveUpdate();
  }

  function kindPill(promotionId, qty) {
    return promotionId && Number(qty) > 0
      ? `<span class="lwa-pill lwa-pill-prize">🎁 Có thưởng</span>`
      : `<span class="lwa-pill lwa-pill-none">🌊 Không trúng</span>`;
  }

  function readRow(tr) {
    const get = (f) => tr.querySelector(`[data-f="${f}"]`);
    const qty = get("quantity_total").value.trim();
    return {
      is_active: get("is_active").checked,
      color: get("color").value,
      label: get("label").value.trim(),
      promotion_id: get("promotion_id").value ? Number(get("promotion_id").value) : null,
      win_weight: Number(get("win_weight").value || 0),
      quantity_total: qty === "" ? null : Number(qty),
    };
  }

  /** Recompute probabilities, weight bar and the wheel preview from the current (unsaved) inputs. */
  function liveUpdate() {
    const rows = [...document.querySelectorAll("#lwaSlots tbody tr")].map((tr) => ({ tr, v: readRow(tr), id: Number(tr.dataset.id) }));
    const active = rows.filter((r) => r.v.is_active);
    const total = active.reduce((sum, r) => sum + Math.max(0, r.v.win_weight), 0);
    rows.forEach(({ tr, v }) => {
      tr.classList.toggle("is-off", !v.is_active);
      tr.querySelector("[data-prob]").textContent = v.is_active && total > 0 ? `${((Math.max(0, v.win_weight) / total) * 100).toFixed(2)}%` : "0%";
      tr.querySelector("[data-kind]").innerHTML = kindPill(v.promotion_id, v.quantity_total);
    });
    const bar = active.map((r) => `<i style="width:${total > 0 ? (Math.max(0, r.v.win_weight) / total) * 100 : 0}%;background:${esc(r.v.color)}" title="${esc(r.v.label)}"></i>`).join("");
    const prizeShare = total > 0 ? active.filter((r) => r.v.promotion_id && r.v.quantity_total > 0).reduce((s, r) => s + r.v.win_weight, 0) / total * 100 : 0;
    const okTotal = Math.abs(total - 100) < 0.001;
    document.getElementById("lwaWeights").innerHTML = `
      <div class="lwa-weight-bar">${bar}</div>
      <div class="flex flex-wrap justify-between gap-2 mt-1.5">
        <span class="${okTotal ? "lwa-ok" : "lwa-warn"}">Tổng tỷ lệ các ô đang bật: ${total.toFixed(1)}% ${okTotal ? "✓" : "— hệ thống tự quy đổi theo tỷ lệ tương đối"}</span>
        <span class="lwa-muted">Cơ hội trúng thưởng mỗi lượt ≈ <b>${prizeShare.toFixed(1)}%</b> · ${active.length} ô đang bật (2–12)</span>
      </div>`;

    if (window.SoobinWheel) {
      const host = document.getElementById("lwaPreview");
      const slots = active.map((r) => {
        const voucher = state.vouchers.find((x) => x.id === r.v.promotion_id);
        const isPrize = !!(r.v.promotion_id && r.v.quantity_total > 0);
        return { label: r.v.label || (isPrize && voucher ? `Giảm ${voucher.discount_percent}%` : "Chúc may mắn"), color: r.v.color, is_prize: isPrize, discount_percent: isPrize && voucher ? voucher.discount_percent : null, in_stock: true };
      });
      if (slots.length >= 2) {
        state.preview?.destroy();
        state.preview = window.SoobinWheel.mount(host, slots, { compact: true, hubText: "XEM" });
      } else {
        host.innerHTML = `<p class="lwa-warn">Cần ít nhất 2 ô đang bật để hiển thị vòng quay.</p>`;
      }
    }
  }

  function renderVouchers() {
    const box = document.getElementById("lwaVouchers");
    box.innerHTML = `
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h3 class="lwa-h">🎟️ Kho voucher (Admin & Manager)</h3>
        <span class="lwa-muted">Khách trúng sẽ nhận <b>mã riêng SPIN-xxxx</b> sinh từ voucher mẫu.</span>
      </div>
      <form id="lwaNewVoucher" class="grid grid-cols-2 md:grid-cols-6 gap-2">
        <input class="lwa-input" name="code" required maxlength="40" placeholder="Mã (VD: SEA20)" style="text-transform:uppercase">
        <input class="lwa-input md:col-span-2" name="name" required maxlength="120" placeholder="Tên voucher">
        <input class="lwa-input" name="pct" type="number" min="1" max="90" step="0.5" required placeholder="% giảm">
        <input class="lwa-input" name="min" type="number" min="0" step="1000" placeholder="Đơn tối thiểu">
        <input class="lwa-input" name="days" type="number" min="1" max="3650" value="365" placeholder="Hiệu lực (ngày)">
        <label class="md:col-span-4 flex items-center gap-2 lwa-muted" style="font-size:12px">
          <span class="lwa-switch"><input type="checkbox" name="hidden" checked><span></span></span>
          Chỉ dùng làm quà vòng quay (ẩn, khách không tự nhập mã mẫu được)
        </label>
        <button type="submit" class="lwa-btn lwa-btn-primary md:col-span-2">+ Tạo voucher</button>
      </form>
      <div class="overflow-x-auto"><table class="lwa-table">
        <thead><tr><th>Mã</th><th>Tên</th><th>Giảm</th><th>Đơn tối thiểu</th><th>Đã dùng</th><th>Trạng thái</th><th></th></tr></thead>
        <tbody>${state.vouchers.slice(0, 40).map((v) => `
          <tr data-vid="${v.id}">
            <td><b style="font-family:ui-monospace,monospace">${esc(v.code)}</b></td>
            <td style="max-width:220px">${esc(v.name)}</td>
            <td><b>-${v.discount_percent}%</b></td>
            <td>${v.minimum_order_amount > 0 ? money(v.minimum_order_amount) : "—"}</td>
            <td>${v.used_count}${v.usage_limit ? "/" + v.usage_limit : ""}</td>
            <td>${v.is_active ? `<span class="lwa-pill lwa-pill-win">Công khai</span>` : `<span class="lwa-pill lwa-pill-lose">Mẫu ẩn</span>`}</td>
            <td class="whitespace-nowrap">
              <button type="button" class="lwa-btn lwa-btn-ghost" data-v="toggle">${v.is_active ? "Ẩn" : "Công khai"}</button>
              <button type="button" class="lwa-btn lwa-btn-gold" data-v="attach">+ Gắn vào ô</button>
            </td>
          </tr>`).join("") || `<tr><td colspan="7" class="lwa-muted">Chưa có voucher nào.</td></tr>`}</tbody>
      </table></div>`;
    box.querySelector("#lwaNewVoucher").addEventListener("submit", createVoucher);
    box.querySelectorAll("[data-vid]").forEach((tr) => {
      const id = Number(tr.dataset.vid);
      tr.querySelector('[data-v="toggle"]').addEventListener("click", () => toggleVoucher(id));
      tr.querySelector('[data-v="attach"]').addEventListener("click", () => addSlot(id));
    });
  }

  function renderRecent() {
    const rows = state.data.recent_spins;
    document.getElementById("lwaRecent").innerHTML = `
      <thead><tr><th>Thời gian</th><th>Khách hàng</th><th>Kết quả</th><th>Ô</th><th>Mã voucher</th></tr></thead>
      <tbody>${rows.map((r) => `
        <tr><td class="whitespace-nowrap">${fmtTime(r.created_at)}</td>
          <td>${esc(r.customer)}<div class="lwa-muted">${esc(r.email)}</div></td>
          <td>${r.is_win ? `<span class="lwa-pill lwa-pill-win">🎉 Trúng</span>` : `<span class="lwa-pill lwa-pill-lose">Không trúng</span>`}</td>
          <td>${esc(r.slot_label)}</td>
          <td style="font-family:ui-monospace,monospace">${esc(r.voucher_code || "—")}</td></tr>`).join("") || `<tr><td colspan="5" class="lwa-muted">Chưa có lượt quay nào.</td></tr>`}</tbody>`;
  }

  function renderAll() {
    renderStats();
    renderConfig();
    renderSlots();
    renderVouchers();
    renderRecent();
    clearInterval(state.timer);
    const tick = () => { const el = document.getElementById("lwaCountdown"); if (el && state.data) el.textContent = countdown(state.data.next_reset_at); };
    tick();
    state.timer = setInterval(tick, 1000);
  }

  // --------------------------------------------------------------------------
  // ACTIONS
  // --------------------------------------------------------------------------
  async function load() {
    try {
      const [data, vouchers] = await Promise.all([api(`${API}/manage`), api(`${API}/manage/vouchers`)]);
      state.data = data;
      state.vouchers = vouchers;
      renderAll();
    } catch (err) {
      say(`Không tải được dữ liệu vòng quay: ${err.message}`, "error");
    }
  }

  async function saveConfig(e) {
    e.preventDefault();
    const f = e.target;
    const minutes = Number(f.interval_value.value) * Number(f.interval_unit.value);
    try {
      const r = await api(`${API}/manage/config`, {
        method: "PUT",
        body: JSON.stringify({
          enabled: f.enabled.checked, title: f.title.value, subtitle: f.subtitle.value,
          spins_per_period: Number(f.spins_per_period.value), voucher_valid_days: Number(f.voucher_valid_days.value),
          reset_interval_minutes: minutes, restock_on_reset: f.restock_on_reset.checked,
        }),
      });
      say(r.message);
      load();
    } catch (err) { say(err.message, "error"); }
  }

  async function saveRow(tr, quiet = false) {
    try {
      await api(`${API}/manage/slots/${tr.dataset.id}`, { method: "PUT", body: JSON.stringify(readRow(tr)) });
      delete tr.dataset.dirty;
      if (!quiet) { say("Đã lưu ô vòng quay."); load(); }
      return true;
    } catch (err) { say(err.message, "error"); return false; }
  }

  async function saveAll() {
    const rows = [...document.querySelectorAll("#lwaSlots tbody tr")];
    // Enable rows first, then disable — keeps the "2–12 active slots" rule satisfied mid-way
    const ordered = rows.sort((a, b) => Number(readRow(b).is_active) - Number(readRow(a).is_active));
    let ok = 0;
    for (const tr of ordered) if (await saveRow(tr, true)) ok++;
    say(`Đã lưu ${ok}/${rows.length} ô vòng quay.`, ok === rows.length ? "success" : "error");
    load();
  }

  async function deleteRow(tr) {
    if (!confirm("Xoá ô này khỏi vòng quay?")) return;
    try { await api(`${API}/manage/slots/${tr.dataset.id}`, { method: "DELETE" }); say("Đã xoá ô."); load(); }
    catch (err) { say(err.message, "error"); }
  }

  async function addSlot(promotionId = null) {
    try {
      const body = promotionId ? { promotion_id: promotionId, quantity_total: 10, win_weight: 5 } : { promotion_id: null, win_weight: 10, label: "Chúc may mắn" };
      const r = await api(`${API}/manage/slots`, { method: "POST", body: JSON.stringify(body) });
      say(r.message);
      load();
    } catch (err) { say(err.message, "error"); }
  }

  async function resetNow() {
    if (!confirm("Reset vòng quay ngay? Mọi khách được hồi lượt quay và số lượng voucher sẽ được nạp lại.")) return;
    try { const r = await api(`${API}/manage/reset`, { method: "POST" }); say(r.message); load(); }
    catch (err) { say(err.message, "error"); }
  }

  async function createVoucher(e) {
    e.preventDefault();
    const f = e.target;
    const now = new Date();
    const ends = new Date(now.getTime() + Number(f.days.value || 365) * 86400000);
    try {
      const r = await api("/api/v1/promotions", {
        method: "POST",
        body: JSON.stringify({
          code: f.code.value.trim().toUpperCase(), name: f.name.value.trim(), promotion_type: "VOUCHER",
          discount_percent: Number(f.pct.value), minimum_order_amount: Number(f.min.value || 0), usage_limit: null,
          starts_at: new Date(now.getTime() - 60000).toISOString(), ends_at: ends.toISOString(), eligible_customer_ids: null,
        }),
      });
      if (f.hidden.checked) await api(`/api/v1/promotions/${r.id}/toggle`, { method: "POST" });
      say(`Đã tạo voucher ${r.code}.`);
      load();
    } catch (err) { say(err.message, "error"); }
  }

  async function toggleVoucher(id) {
    try { const r = await api(`/api/v1/promotions/${id}/toggle`, { method: "POST" }); say(r.message); load(); }
    catch (err) { say(err.message, "error"); }
  }

  function init() {
    const root = document.getElementById("luckyWheelAdminRoot");
    if (!root) return;
    state.root = root;
    root.classList.add("lwa-root");
    if (root.dataset.theme === "dark") root.classList.add("lwa-dark");
    shell();
    load();
  }

  window.soobinWheelAdmin = { load: () => (state.root ? load() : init()) };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
