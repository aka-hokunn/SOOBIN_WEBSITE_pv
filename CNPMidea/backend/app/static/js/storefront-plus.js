/**
 * ============================================================================
 * SOOBIN STOREFRONT PLUS — tiện ích mua sắm cao cấp cho khách hàng
 * ----------------------------------------------------------------------------
 *  1. Hồ sơ size thông minh (localStorage + đồng bộ tài khoản) → badge "Vừa với bạn".
 *  2. Thêm nhanh 1 chạm: chip size trên thẻ sản phẩm (shop) + hiệu ứng bay vào giỏ.
 *  3. Bằng chứng xã hội thật: đơn hàng thật gần đây + "N người đang xem" (heartbeat).
 *  4. Stylist chuyến đi: phối set từ catalog thật, thêm cả set vào giỏ.
 *  5. Tìm kiếm bằng hình ảnh (bảng màu) → "Kết quả tìm theo ảnh" trong shop.
 *  Hooks từ app.js: interceptLoadProducts, onGridRendered, onProductModalOpen, lookupVariant.
 * ============================================================================
 */
(function () {
  "use strict";

  const API = "/api/v1/experience";
  const LS_PROFILE = "soobin_fit_profile";
  const LS_VARIANTS = "soobin_variant_meta";
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (v) =>
    typeof formatCurrency === "function" ? formatCurrency(v) : `${Math.round(Number(v) || 0).toLocaleString("vi-VN")}đ`;
  const toast = (msg, isError = false) => {
    if (typeof showToast === "function") showToast(msg, isError);
    else if (typeof window.notify === "function") window.notify(msg, isError ? "error" : "success");
  };
  const sfx = (variant = "select") => {
    if (typeof window.playRefreshingSelectSound === "function") window.playRefreshingSelectSound(variant);
  };
  const icons = () => { try { window.lucide && window.lucide.createIcons(); } catch (_) {} };
  const customer = () => (typeof currentUser !== "undefined" && currentUser ? currentUser : null);
  const view = () => (typeof storefrontView !== "undefined" ? storefrontView : "home");
  const shopRoute = () => (typeof activeShopRoute !== "undefined" ? activeShopRoute : null);

  async function api(path, opts = {}) {
    const res = await fetch(`${API}${path}`, opts);
    let data = null;
    try { data = await res.json(); } catch (_) {}
    if (!res.ok) throw new Error((data && data.detail) || "Không thể kết nối máy chủ.");
    return data;
  }
  const postJSON = (path, body) =>
    api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

  // ==========================================================================
  // MODAL HELPER
  // ==========================================================================
  const openModals = [];
  function makeModal(id, inner, extraClass = "") {
    let el = document.getElementById(id);
    if (el) return el;
    el = document.createElement("div");
    el.id = id;
    el.className = "sp-modal";
    el.setAttribute("role", "dialog");
    el.setAttribute("aria-modal", "true");
    el.innerHTML = `<div class="sp-sheet ${extraClass}" data-lenis-prevent>
      <button type="button" class="sp-x" data-close aria-label="Đóng">✕</button>${inner}</div>`;
    document.body.appendChild(el);
    el.addEventListener("click", (e) => { if (e.target === el || e.target.closest("[data-close]")) closeModal(el); });
    return el;
  }
  function openModal(el) {
    if (!el.classList.contains("is-open")) openModals.push(el);
    el.classList.add("is-open");
    window.soobinLenis && window.soobinLenis.stop && window.soobinLenis.stop();
    hideProof();
    if (window.gsap && !reduceMotion) {
      window.gsap.fromTo(el.querySelector(".sp-sheet"), { y: 28, opacity: 0, scale: 0.97 }, { y: 0, opacity: 1, scale: 1, duration: 0.5, ease: "expo.out" });
    }
  }
  function closeModal(el) {
    if (!el) return;
    el.classList.remove("is-open");
    const i = openModals.indexOf(el);
    if (i >= 0) openModals.splice(i, 1);
    if (!openModals.length && !document.querySelector("#luckyWheelModal.is-open")) {
      window.soobinLenis && window.soobinLenis.start && window.soobinLenis.start();
    }
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && openModals.length) { e.stopPropagation(); closeModal(openModals[openModals.length - 1]); }
  }, true);

  // ==========================================================================
  // 1. FIT PROFILE
  // ==========================================================================
  const FIT_FIELDS = [
    { key: "height_cm", label: "Chiều cao", unit: "cm", min: 60, max: 220 },
    { key: "weight_kg", label: "Cân nặng", unit: "kg", min: 10, max: 180 },
    { key: "bust_cm", label: "Vòng ngực", unit: "cm", min: 45, max: 170, adult: true },
    { key: "waist_cm", label: "Vòng eo", unit: "cm", min: 35, max: 160, adult: true },
    { key: "hip_cm", label: "Vòng mông", unit: "cm", min: 45, max: 180, adult: true },
  ];

  function readProfile() {
    try {
      const p = JSON.parse(localStorage.getItem(LS_PROFILE) || "null");
      return p && typeof p === "object" ? p : null;
    } catch (_) { return null; }
  }
  let profile = readProfile();
  const hasProfile = () => !!(profile && (profile.height_cm || profile.weight_kg));
  function cleanProfile(p = profile) {
    if (!p) return null;
    const out = { gender: ["Nữ", "Nam", "Trẻ em"].includes(p.gender) ? p.gender : "Nữ" };
    FIT_FIELDS.forEach((f) => { out[f.key] = p[f.key] ? Number(p[f.key]) : null; });
    if (out.gender === "Trẻ em") { out.bust_cm = null; out.waist_cm = null; out.hip_cm = null; }
    return out;
  }
  function profileSummary() {
    if (!hasProfile()) return "";
    const parts = [];
    if (profile.height_cm) parts.push(`${Math.round(profile.height_cm)}cm`);
    if (profile.weight_kg) parts.push(`${Number(profile.weight_kg)}kg`);
    return parts.join(" · ");
  }

  function setProfile(p, { sync = true } = {}) {
    profile = p ? { ...cleanProfile(p), saved_at: p.saved_at || new Date().toISOString() } : null;
    if (profile) localStorage.setItem(LS_PROFILE, JSON.stringify(profile));
    else localStorage.removeItem(LS_PROFILE);
    updateProfileLabels();
    syncAdvisorInputs();
    refreshGridMeta();
    if (sync && customer()) return pushProfile();
    return Promise.resolve();
  }

  async function pushProfile() {
    if (!customer()) return;
    if (!hasProfile()) { try { await api("/fit-profile", { method: "DELETE" }); } catch (_) {} return; }
    const data = await api("/fit-profile", {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cleanProfile()),
    });
    if (data && data.profile && data.profile.updated_at) {
      profile.saved_at = data.profile.updated_at;
      localStorage.setItem(LS_PROFILE, JSON.stringify(profile));
    }
  }

  let syncedFor = null;
  async function syncProfileWithAccount() {
    const u = customer();
    if (!u || syncedFor === u.id) return;
    syncedFor = u.id;
    try {
      const { profile: server } = await api("/fit-profile");
      if (server && (!hasProfile() || new Date(server.updated_at) > new Date(profile.saved_at || 0))) {
        setProfile({ ...server, saved_at: server.updated_at }, { sync: false });
      } else if (hasProfile() && !server) {
        await pushProfile();
      } else if (hasProfile() && server && new Date(profile.saved_at || 0) > new Date(server.updated_at)) {
        await pushProfile();
      }
    } catch (_) { syncedFor = null; }
  }

  function updateProfileLabels() {
    const adv = document.getElementById("spAdvisorFitLabel");
    if (adv) adv.textContent = hasProfile() ? `Hồ sơ size · ${profileSummary()}` : "Lưu hồ sơ size";
    const shop = document.getElementById("spShopFitLabel");
    if (shop) shop.textContent = hasProfile() ? `Hồ sơ size · ${profileSummary()}` : "Hồ sơ size";
    document.querySelectorAll(".sp-cta-fit").forEach((b) => b.classList.toggle("is-set", hasProfile()));
  }

  function syncAdvisorInputs() {
    if (!hasProfile()) return;
    const set = (id, v) => { const el = document.getElementById(id); if (el && v) el.value = v; };
    set("aiHeight", profile.height_cm);
    set("aiWeight", profile.weight_kg);
    set("aiBust", profile.bust_cm);
    const g = document.getElementById("aiGender");
    if (g && (profile.gender === "Nữ" || profile.gender === "Nam")) g.value = profile.gender;
  }

  function ensureFitModal() {
    const fields = FIT_FIELDS.map((f) => `
      <label class="sp-field" ${f.adult ? "data-adult" : ""}>
        <span>${f.label}</span>
        <input name="${f.key}" type="number" inputmode="decimal" min="${f.min}" max="${f.max}" step="0.5" placeholder="—">
        <em>${f.unit}</em>
      </label>`).join("");
    const el = makeModal("spFitModal", `
      <div class="sp-head">
        <span class="sp-eyebrow">Soobin Fit ID</span>
        <h3>Hồ sơ size của bạn</h3>
        <p>Lưu một lần — mọi sản phẩm hiện size vừa với bạn.</p>
      </div>
      <form class="sp-fit-form" novalidate>
        <div class="sp-seg" role="radiogroup" aria-label="Dành cho">
          ${["Nữ", "Nam", "Trẻ em"].map((g) => `<label><input type="radio" name="gender" value="${g}"><span>${g}</span></label>`).join("")}
        </div>
        <div class="sp-fields">${fields}</div>
        <p class="sp-fit-note" data-note></p>
        <div class="sp-actions">
          <button type="button" class="sp-btn-ghost" data-clear>Xoá hồ sơ</button>
          <button type="submit" class="sp-btn-primary">Lưu hồ sơ</button>
        </div>
      </form>`, "sp-fit-sheet");
    const form = el.querySelector("form");
    form.addEventListener("change", (e) => { if (e.target.name === "gender") toggleAdultFields(form); });
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const data = { gender: fd.get("gender") || "Nữ" };
      for (const f of FIT_FIELDS) {
        const raw = String(fd.get(f.key) || "").trim();
        if (!raw || (f.adult && data.gender === "Trẻ em")) { data[f.key] = null; continue; }
        const num = Number(raw.replace(",", "."));
        if (!Number.isFinite(num) || num < f.min || num > f.max) {
          toast(`${f.label} phải trong khoảng ${f.min}–${f.max}${f.unit}.`, true);
          form.querySelector(`[name="${f.key}"]`).focus();
          return;
        }
        data[f.key] = num;
      }
      if (!data.height_cm && !data.weight_kg) { toast("Nhập ít nhất chiều cao hoặc cân nặng nhé.", true); return; }
      try {
        await setProfile(data);
        sfx("select");
        toast(customer() ? "Đã lưu hồ sơ size vào tài khoản." : "Đã lưu hồ sơ size trên thiết bị này.");
        closeModal(el);
      } catch (err) { toast(err.message, true); }
    });
    el.querySelector("[data-clear]").addEventListener("click", async () => {
      await setProfile(null);
      form.reset();
      form.querySelector('[name="gender"][value="Nữ"]').checked = true;
      toggleAdultFields(form);
      toast("Đã xoá hồ sơ size.");
    });
    return el;
  }
  function toggleAdultFields(form) {
    const kid = (form.querySelector('[name="gender"]:checked') || {}).value === "Trẻ em";
    form.querySelectorAll("[data-adult]").forEach((f) => { f.hidden = kid; });
  }

  function openFitProfile(opts = {}) {
    const el = ensureFitModal();
    const form = el.querySelector("form");
    const p = profile || {};
    let gender = p.gender || "Nữ";
    const values = { ...p };
    if (opts.fromAdvisor) {
      const adv = (id) => (document.getElementById(id) || {}).value;
      if (adv("aiHeight")) values.height_cm = adv("aiHeight");
      if (adv("aiWeight")) values.weight_kg = adv("aiWeight");
      if (adv("aiBust")) values.bust_cm = adv("aiBust");
      if (!p.gender && adv("aiGender")) gender = adv("aiGender");
    }
    form.querySelectorAll('[name="gender"]').forEach((r) => { r.checked = r.value === gender; });
    FIT_FIELDS.forEach((f) => { form.querySelector(`[name="${f.key}"]`).value = values[f.key] || ""; });
    toggleAdultFields(form);
    el.querySelector("[data-clear]").hidden = !hasProfile();
    el.querySelector("[data-note]").textContent = customer()
      ? "Đồng bộ với tài khoản của bạn trên mọi thiết bị."
      : "Lưu trên thiết bị này · đăng nhập để đồng bộ.";
    openModal(el);
    setTimeout(() => form.querySelector('[name="height_cm"]').focus({ preventScroll: true }), 80);
  }

  // ==========================================================================
  // 2. SHOP GRID — fit badge + one-tap size chips
  // ==========================================================================
  let gridSeq = 0;
  let lastGrid = null;

  function fitBadge(fit) {
    if (!fit || fit.status !== "ok") return "";
    return `<span class="sp-fit-badge is-${fit.level}" title="Theo hồ sơ size của bạn · độ tin cậy ${fit.confidence}%">
      <i aria-hidden="true">✓</i>Vừa với bạn: <b>${esc(fit.size)}</b><small>${fit.confidence}%</small>${fit.in_stock ? "" : "<em>tạm hết</em>"}</span>`;
  }

  function chipsHtml(p, meta) {
    const sizes = (meta.sizes || []).filter((s) => s.variant_id);
    if (!sizes.length || !sizes.some((s) => s.in_stock)) return "";
    const fitSize = meta.fit && meta.fit.status === "ok" ? meta.fit.size : null;
    const single = sizes.length === 1;
    const chips = sizes.slice(0, 6).map((s) => {
      const label = single ? "+ Thêm nhanh" : esc(s.size_label);
      const title = s.in_stock ? `Thêm ${single ? "" : "size " + s.size_label + " "}vào giỏ` : `Size ${s.size_label} tạm hết`;
      return `<button type="button" class="sp-chip${s.size_code === fitSize ? " is-fit" : ""}${single ? " is-wide" : ""}"
        data-sp-add="${p.id}" data-size="${esc(s.size_code)}" ${s.in_stock ? "" : "disabled"} title="${esc(title)}" aria-label="${esc(title)}">${label}</button>`;
    }).join("");
    return `<div class="sp-chips" role="group" aria-label="Thêm nhanh theo size">
      ${single ? "" : `<span class="sp-chips-ico" aria-hidden="true"><i data-lucide="shopping-bag" class="w-3 h-3"></i></span>`}${chips}</div>`;
  }

  function decorateCard(grid, p, meta) {
    const card = grid.querySelector(`[data-morph-id="prod-${p.id}"]`);
    if (!card) return;
    card.querySelectorAll(".sp-card-plus").forEach((n) => n.remove());
    const info = card.lastElementChild;
    const priceRow = info && Array.from(info.children).find((c) => c.classList.contains("pt-3"));
    if (!info || !priceRow) return;
    const sim = visual && typeof p.similarity === "number"
      ? `<span class="sp-sim" title="Độ tương đồng màu sắc với ảnh của bạn">${(p.palette || []).slice(0, 3).map((h) => `<i style="background:${esc(h)}"></i>`).join("")}Tương đồng ${p.similarity}%</span>`
      : "";
    const badge = fitBadge(meta.fit);
    const chips = chipsHtml(p, meta);
    if (!badge && !chips && !sim) return;
    const block = document.createElement("div");
    block.className = "sp-card-plus";
    block.innerHTML = `${badge || sim ? `<div class="sp-card-tags">${badge}${sim}</div>` : ""}${chips}`;
    info.insertBefore(block, priceRow);
  }

  const metaCache = new Map();
  async function onGridRendered(grid, products) {
    lastGrid = { grid, products };
    if (!grid || !Array.isArray(products) || !products.length || view() !== "shop") return;
    const seq = ++gridSeq;
    let items = {};
    try {
      const data = await postJSON("/fit/recommend", {
        product_ids: products.map((p) => p.id).slice(0, 40),
        profile: hasProfile() ? cleanProfile() : null,
      });
      items = data.items || {};
    } catch (_) { return; }
    if (seq !== gridSeq) return;
    products.forEach((p) => {
      const meta = items[String(p.id)];
      if (!meta) return;
      metaCache.set(p.id, { ...meta, product: p });
      decorateCard(grid, p, meta);
    });
    icons();
  }
  function refreshGridMeta() {
    if (lastGrid && view() === "shop") onGridRendered(lastGrid.grid, lastGrid.products);
  }

  // ---- guest-cart variant cache (so the drawer can show names & prices) ----
  function readVariantCache() {
    try { return JSON.parse(localStorage.getItem(LS_VARIANTS) || "{}") || {}; } catch (_) { return {}; }
  }
  function rememberVariant(variantId, product, variant) {
    if (!variantId || !product) return;
    const cache = readVariantCache();
    cache[variantId] = {
      p: { id: product.id, name: product.name, slug: product.slug, image_url: product.image_url,
           discounted_price: product.discounted_price, base_price: product.base_price },
      v: { id: variantId, size_name: variant.size_name || "", color_name: variant.color_name || "" },
      t: Date.now(),
    };
    const keys = Object.keys(cache);
    if (keys.length > 120) keys.sort((a, b) => cache[a].t - cache[b].t).slice(0, keys.length - 120).forEach((k) => delete cache[k]);
    try { localStorage.setItem(LS_VARIANTS, JSON.stringify(cache)); } catch (_) {}
  }
  function lookupVariant(variantId) {
    const hit = readVariantCache()[variantId];
    if (!hit) return null;
    return { product: { ...hit.p, variants: [] }, variant: hit.v };
  }

  async function addToCart(lines, bundleName) {
    const valid = lines.filter((l) => l.variant_id);
    if (!valid.length) throw new Error("Không có sản phẩm còn hàng để thêm.");
    valid.forEach((l) => rememberVariant(l.variant_id, l.product, l.variant || {}));
    if (customer()) {
      const single = valid.length === 1;
      const res = await fetch(single ? "/api/v1/cart/items" : "/api/v1/cart/bundle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(single
          ? { variant_id: valid[0].variant_id, quantity: valid[0].quantity || 1 }
          : { bundle_name: bundleName || "Set Soobin", items: valid.map((l) => ({ variant_id: l.variant_id, quantity: l.quantity || 1 })) }),
      });
      let data = {};
      try { data = await res.json(); } catch (_) {}
      if (!res.ok) throw new Error(data.detail || "Không thể thêm vào giỏ.");
    } else {
      if (typeof guestCart === "undefined") throw new Error("Giỏ hàng chưa sẵn sàng.");
      for (const l of valid) {
        const ex = guestCart.find((g) => g.variant_id === l.variant_id);
        const nextQty = (ex ? ex.quantity : 0) + (l.quantity || 1);
        if (l.available && nextQty > l.available) throw new Error(`${l.variant && l.variant.size_name ? "Size " + l.variant.size_name : "Sản phẩm"} chỉ còn ${l.available} chiếc.`);
      }
      valid.forEach((l) => {
        const ex = guestCart.find((g) => g.variant_id === l.variant_id);
        if (ex) ex.quantity += l.quantity || 1;
        else guestCart.push({ variant_id: l.variant_id, quantity: l.quantity || 1 });
      });
      localStorage.setItem("soobin_guest_cart", JSON.stringify(guestCart));
    }
    if (typeof updateCartBadge === "function") updateCartBadge();
  }

  function bump(el) {
    if (!el || !window.gsap || reduceMotion) return;
    window.gsap.fromTo(el, { scale: 1 }, { scale: 1.22, duration: 0.16, yoyo: true, repeat: 1, ease: "power2.out", clearProps: "scale" });
  }
  function flyToCart(fromEl, imgSrc) {
    const target = (document.getElementById("cartBadge") || {}).closest ? document.getElementById("cartBadge").closest("button") : null;
    if (!fromEl || !target || reduceMotion || !window.gsap) { bump(target); return; }
    const a = fromEl.getBoundingClientRect();
    const b = target.getBoundingClientRect();
    const size = 54;
    const dot = document.createElement("img");
    dot.src = imgSrc || "/static/images/placeholder.webp";
    dot.alt = "";
    dot.className = "sp-fly";
    dot.style.left = `${a.left + a.width / 2 - size / 2}px`;
    dot.style.top = `${a.top + a.height / 2 - size / 2}px`;
    document.body.appendChild(dot);
    const dx = b.left + b.width / 2 - (a.left + a.width / 2);
    const dy = b.top + b.height / 2 - (a.top + a.height / 2);
    window.gsap.timeline({ onComplete: () => { dot.remove(); bump(target); } })
      .fromTo(dot, { scale: 0.3, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.2, ease: "back.out(2.2)" })
      .to(dot, { x: dx, duration: 0.75, ease: "power2.out" })
      .to(dot, { y: dy, duration: 0.75, ease: "power3.in" }, "<")
      .to(dot, { scale: 0.28, opacity: 0.35, duration: 0.75, ease: "power2.in" }, "<");
  }

  async function quickAdd(productId, sizeCode, chip) {
    const meta = metaCache.get(productId);
    if (!meta) return;
    const size = (meta.sizes || []).find((s) => s.size_code === sizeCode);
    if (!size || !size.in_stock) return;
    const p = meta.product;
    chip.disabled = true;
    chip.classList.add("is-busy");
    sfx("cart");
    try {
      await addToCart([{
        variant_id: size.variant_id, quantity: 1, product: p, available: size.available,
        variant: { size_name: size.size_code === "FREESIZE" ? "Freesize" : `Size ${size.size_label}`, color_name: size.color_name },
      }]);
      const card = chip.closest(".editorial-product-card");
      flyToCart(card ? card.querySelector("img") : chip, p.image_url);
      chip.classList.add("is-added");
      setTimeout(() => chip.classList.remove("is-added"), 1200);
      toast(`Đã thêm ${size.size_code === "FREESIZE" ? "" : "size " + size.size_label + " · "}${p.name}`);
    } catch (err) {
      toast(err.message, true);
    } finally {
      chip.disabled = false;
      chip.classList.remove("is-busy");
    }
  }

  document.addEventListener("click", (e) => {
    const chip = e.target.closest("[data-sp-add]");
    if (!chip) return;
    e.preventDefault();
    e.stopPropagation();
    quickAdd(Number(chip.dataset.spAdd), chip.dataset.size, chip);
  });

  // ==========================================================================
  // 3a. PRODUCT MODAL — fit card + live presence
  // ==========================================================================
  const viewerId = (() => {
    let id = sessionStorage.getItem("soobin_viewer_id");
    if (!id || !/^[A-Za-z0-9_-]{8,64}$/.test(id)) {
      const rnd = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : `${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
      id = rnd.replace(/[^A-Za-z0-9_-]/g, "").slice(0, 40);
      sessionStorage.setItem("soobin_viewer_id", id);
    }
    return id;
  })();
  const presence = { pid: null, timer: null };

  function renderPresence(n) {
    const stage = document.querySelector("#productModalContent .editorial-zoom-stage");
    if (!stage) return;
    let pill = stage.querySelector(".sp-live-pill");
    if (n < 2) { if (pill) pill.remove(); return; }
    if (!pill) {
      pill = document.createElement("div");
      pill.className = "sp-live-pill";
      stage.appendChild(pill);
      if (window.gsap && !reduceMotion) window.gsap.fromTo(pill, { y: -8, opacity: 0 }, { y: 0, opacity: 1, duration: 0.45, ease: "power3.out" });
    }
    pill.innerHTML = `<span class="sp-live-dot" aria-hidden="true"></span>${n} người đang xem`;
  }
  async function beat() {
    if (!presence.pid) return;
    const pid = presence.pid;
    try {
      const data = await postJSON("/presence", { product_id: pid, viewer_id: viewerId });
      if (presence.pid === pid) renderPresence(data.viewers || 0);
    } catch (_) {}
  }
  function startPresence(pid) {
    if (presence.pid && presence.pid !== pid) stopPresence();
    presence.pid = pid;
    clearInterval(presence.timer);
    beat();
    presence.timer = setInterval(beat, 20000);
  }
  function stopPresence(useBeacon = false) {
    if (!presence.pid) return;
    const body = JSON.stringify({ product_id: presence.pid, viewer_id: viewerId });
    presence.pid = null;
    clearInterval(presence.timer);
    if (useBeacon && navigator.sendBeacon) navigator.sendBeacon(`${API}/presence/leave`, new Blob([body], { type: "application/json" }));
    else fetch(`${API}/presence/leave`, { method: "POST", headers: { "Content-Type": "application/json" }, body, keepalive: true }).catch(() => {});
  }
  window.addEventListener("pagehide", () => stopPresence(true));

  function watchProductModal() {
    const modal = document.getElementById("productDetailModal");
    if (!modal || modal.__spWatched) return;
    modal.__spWatched = true;
    new MutationObserver(() => { if (modal.classList.contains("hidden")) stopPresence(); })
      .observe(modal, { attributes: true, attributeFilter: ["class"] });
  }

  async function renderModalFit(prod) {
    const variants = prod.variants || [];
    const firstBtn = variants.length ? document.getElementById(`varBtn-${variants[0].id}`) : null;
    const gridEl = firstBtn ? firstBtn.parentElement : null;
    if (!gridEl) return;
    const sized = variants.some((v) => v.size_code && v.size_code.toUpperCase() !== "FREESIZE");
    if (!sized || !["Nữ", "Nam", "Trẻ em"].includes(prod.target_audience)) return;
    const box = document.createElement("div");
    box.className = "sp-modal-fit";
    gridEl.parentElement.insertBefore(box, gridEl);
    if (!hasProfile()) {
      box.classList.add("is-cta");
      box.innerHTML = `<button type="button" data-fit-edit><i data-lucide="ruler" class="w-4 h-4"></i><span>Tạo hồ sơ size để biết size vừa với bạn</span><i data-lucide="chevron-right" class="w-4 h-4"></i></button>`;
      icons();
      return;
    }
    let meta = null;
    try {
      const data = await postJSON("/fit/recommend", { product_ids: [prod.id], profile: cleanProfile() });
      meta = (data.items || {})[String(prod.id)];
    } catch (_) {}
    if (typeof selectedProduct !== "undefined" && selectedProduct && selectedProduct.id !== prod.id) return;
    const fit = meta && meta.fit;
    if (!fit || fit.status !== "ok") {
      box.remove();
      return;
    }
    box.classList.add(`is-${fit.level}`);
    const basis = fit.basis === "product_chart" ? "theo bảng size sản phẩm" : "theo bảng size chuẩn";
    box.innerHTML = `
      <div class="sp-modal-fit-size">${esc(fit.size)}</div>
      <div class="sp-modal-fit-txt">
        <strong>Vừa với bạn: size ${esc(fit.size)}${fit.in_stock ? "" : " · đang tạm hết"}</strong>
        <span>Độ tin cậy ${fit.confidence}% · ${basis}${fit.alt_size ? ` · cân nhắc ${esc(fit.alt_size)}` : ""}</span>
      </div>
      <button type="button" data-fit-edit>Sửa</button>`;
    // Tag every variant button of the recommended size
    variants.forEach((v) => {
      if ((v.size_code || "").toUpperCase() !== fit.size) return;
      const btn = document.getElementById(`varBtn-${v.id}`);
      if (btn && !btn.querySelector(".sp-var-tag")) {
        const tag = document.createElement("span");
        tag.className = "sp-var-tag";
        tag.textContent = "Vừa";
        btn.appendChild(tag);
      }
    });
    // Pre-select the best-stocked variant of the fitting size (silently)
    const current = variants.find((v) => typeof selectedVariantId !== "undefined" && v.id === selectedVariantId);
    if (!current || (current.size_code || "").toUpperCase() !== fit.size) {
      const best = variants.filter((v) => (v.size_code || "").toUpperCase() === fit.size && v.available_quantity > 0)
        .sort((a, b) => b.available_quantity - a.available_quantity)[0];
      if (best && typeof selectVariant === "function") {
        const sound = window.playRefreshingSelectSound;
        window.playRefreshingSelectSound = null;
        try { selectVariant(best.id); } finally { window.playRefreshingSelectSound = sound; }
      }
    }
  }

  function onProductModalOpen(prod) {
    if (!prod) return;
    watchProductModal();
    const img = (prod.images && prod.images[0] && prod.images[0].file_path) || "/static/images/placeholder.webp";
    (prod.variants || []).forEach((v) => rememberVariant(v.id, { ...prod, image_url: img }, { size_name: v.size_name, color_name: v.color_name }));
    startPresence(prod.id);
    renderModalFit(prod);
  }
  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-fit-edit]")) openFitProfile();
  });

  // ==========================================================================
  // 3b. SOCIAL PROOF TOAST (real orders, anonymised)
  // ==========================================================================
  const PROOF_MAX = 6;
  const proof = {
    items: [], el: null, timer: null, hideTimer: null, watch: null,
    seen: new Set(JSON.parse(sessionStorage.getItem("sp_proof_seen") || "[]")),
    count: Number(sessionStorage.getItem("sp_proof_count") || 0),
    off: sessionStorage.getItem("sp_proof_off") === "1",
  };

  function overlayOpen() {
    if (document.hidden || document.body.classList.contains("is-immersive")) return true;
    if (document.querySelector("#luckyWheelModal.is-open, #lwResult.is-open, .sp-modal.is-open")) return true;
    const drawer = document.getElementById("cartDrawer");
    if (drawer && !drawer.classList.contains("translate-x-full")) return true;
    const chat = document.getElementById("aiChatPanel");
    if (chat && !chat.classList.contains("hidden")) return true;
    for (const el of document.querySelectorAll(".fixed.inset-0")) {
      if (!el.classList.contains("hidden") && el.getClientRects().length) return true;
    }
    return false;
  }

  function hideProof() {
    clearTimeout(proof.hideTimer);
    clearInterval(proof.watch);
    if (proof.el) proof.el.classList.remove("is-visible");
  }

  function scheduleProof(ms) {
    clearTimeout(proof.timer);
    if (proof.off || proof.count >= PROOF_MAX) return;
    proof.timer = setTimeout(showNextProof, ms);
  }

  function showNextProof() {
    if (proof.off || proof.count >= PROOF_MAX) return;
    if (overlayOpen()) { scheduleProof(9000); return; }
    const item = proof.items.find((x) => !proof.seen.has(x.key));
    if (!item) return;
    proof.seen.add(item.key);
    proof.count += 1;
    sessionStorage.setItem("sp_proof_seen", JSON.stringify([...proof.seen].slice(-40)));
    sessionStorage.setItem("sp_proof_count", String(proof.count));

    if (!proof.el) {
      proof.el = document.createElement("div");
      proof.el.className = "sp-proof";
      proof.el.setAttribute("role", "status");
      proof.el.setAttribute("aria-live", "polite");
      document.body.appendChild(proof.el);
      proof.el.addEventListener("click", (e) => {
        if (e.target.closest(".sp-proof-x")) {
          proof.off = true;
          sessionStorage.setItem("sp_proof_off", "1");
          hideProof();
          return;
        }
        const slug = proof.el.dataset.slug;
        hideProof();
        if (slug && typeof openProductModal === "function") openProductModal(slug);
      });
    }
    const where = item.province ? ` ở ${esc(item.province)}` : "";
    const verb = item.minutes_ago < 60 ? "vừa mua" : "đã mua";
    proof.el.dataset.slug = item.product_slug || item.product_id;
    proof.el.innerHTML = `
      <img src="${esc(item.image_url)}" alt="">
      <div class="sp-proof-txt">
        <p><b>${esc(item.buyer)}</b>${where} ${verb}</p>
        <p class="sp-proof-name">${esc(item.product_name)}</p>
        <span>${esc(item.time_label)}<i aria-hidden="true">·</i>đơn hàng thật</span>
      </div>
      <button type="button" class="sp-proof-x" aria-label="Ẩn thông báo mua hàng">×</button>`;
    requestAnimationFrame(() => proof.el.classList.add("is-visible"));
    proof.watch = setInterval(() => { if (overlayOpen()) hideProof(); }, 400);
    proof.hideTimer = setTimeout(hideProof, 6500);
    scheduleProof(42000 + Math.random() * 26000);
  }

  async function initProof() {
    if (proof.off || proof.count >= PROOF_MAX) return;
    try {
      const data = await api("/recent-purchases?limit=12");
      proof.items = (data.items || []).filter((x) => x.product_name);
    } catch (_) { return; }
    if (proof.items.length) scheduleProof(14000);
  }

  // ==========================================================================
  // 4. TRIP STYLIST
  // ==========================================================================
  const TRIPS = [
    { id: "bien", label: "Biển", icon: "🏖️" },
    { id: "ho-boi", label: "Hồ bơi", icon: "🏊" },
    { id: "thi-dau", label: "Thi đấu", icon: "🏅" },
    { id: "resort", label: "Resort", icon: "🌴" },
  ];
  const STYLES = [
    { id: "nang-dong", label: "Năng động" }, { id: "thanh-lich", label: "Thanh lịch" },
    { id: "kin-dao", label: "Kín đáo" }, { id: "noi-bat", label: "Nổi bật" },
  ];
  const BUDGETS = [
    { v: "", label: "Không giới hạn" }, { v: "1000000", label: "≤ 1 triệu" }, { v: "1500000", label: "≤ 1,5 triệu" },
    { v: "2500000", label: "≤ 2,5 triệu" }, { v: "4000000", label: "≤ 4 triệu" },
  ];
  let tripSet = null;

  function ensureTripModal() {
    const radios = (name, list, key = "id") => list.map((o, i) => `
      <label class="sp-pill"><input type="radio" name="${name}" value="${esc(o[key])}" ${i === 0 ? "checked" : ""}><span>${o.icon ? `<b>${o.icon}</b>` : ""}${esc(o.label)}</span></label>`).join("");
    const el = makeModal("spTripModal", `
      <div class="sp-trip-grid">
        <form class="sp-trip-form" novalidate>
          <div class="sp-head">
            <span class="sp-eyebrow">Soobin Trip Stylist</span>
            <h3>Stylist chuyến đi</h3>
          </div>
          <fieldset><legend>Chuyến đi</legend><div class="sp-tiles">${radios("trip_type", TRIPS)}</div></fieldset>
          <fieldset class="sp-row">
            <legend>Số ngày</legend>
            <div class="sp-stepper"><button type="button" data-step="-1" aria-label="Bớt 1 ngày">−</button><output name="daysOut">3</output><button type="button" data-step="1" aria-label="Thêm 1 ngày">+</button></div>
          </fieldset>
          <fieldset><legend>Dành cho</legend><div class="sp-seg">${["Nữ", "Nam", "Trẻ em"].map((g, i) => `<label><input type="radio" name="gender" value="${g}" ${i === 0 ? "checked" : ""}><span>${g}</span></label>`).join("")}</div></fieldset>
          <fieldset><legend>Phong cách</legend><div class="sp-pills">${radios("style", STYLES)}</div></fieldset>
          <fieldset><legend>Ngân sách</legend><div class="sp-pills">${radios("budget", BUDGETS, "v")}</div></fieldset>
          <button type="submit" class="sp-btn-primary sp-btn-block"><i data-lucide="sparkles" class="w-4 h-4"></i>Phối set cho tôi</button>
        </form>
        <section class="sp-trip-result" aria-live="polite">
          <div class="sp-trip-empty">
            <img src="/static/images/illustrations/umbrella.svg" alt="" onerror="this.remove()">
            <p>Chọn chuyến đi — Soobin phối trọn set từ hàng đang có sẵn.</p>
          </div>
        </section>
      </div>`, "sp-trip-sheet");
    const form = el.querySelector("form");
    let days = 3;
    form.querySelectorAll("[data-step]").forEach((b) => b.addEventListener("click", () => {
      days = Math.max(1, Math.min(14, days + Number(b.dataset.step)));
      form.querySelector("output").textContent = String(days);
      sfx("select");
    }));
    form.addEventListener("change", () => sfx("select"));
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const gender = fd.get("gender") || "Nữ";
      const body = {
        trip_type: fd.get("trip_type"), days, gender, style: fd.get("style"),
        budget: fd.get("budget") ? Number(fd.get("budget")) : null,
        profile: hasProfile() && cleanProfile().gender === gender ? cleanProfile() : null,
      };
      const result = el.querySelector(".sp-trip-result");
      result.innerHTML = `<div class="sp-trip-loading"><span></span><span></span><span></span></div>`;
      const btn = form.querySelector('[type="submit"]');
      btn.disabled = true;
      try {
        tripSet = await postJSON("/trip-stylist", body);
        renderTripResult(result, tripSet);
      } catch (err) {
        result.innerHTML = `<p class="sp-trip-error">${esc(err.message)}</p>`;
      } finally { btn.disabled = false; }
    });
    el.querySelector(".sp-trip-result").addEventListener("click", async (e) => {
      const open = e.target.closest("[data-open-product]");
      if (open) {
        closeModal(el);
        if (typeof openProductModal === "function") openProductModal(open.dataset.openProduct);
        return;
      }
      const add = e.target.closest("[data-add-set]");
      if (!add || !tripSet || !tripSet.items.length) return;
      add.disabled = true;
      sfx("cart");
      try {
        await addToCart(tripSet.items.map((it) => ({
          variant_id: it.variant_id, quantity: 1,
          product: { id: it.product_id, name: it.name, slug: it.slug, image_url: it.image_url, discounted_price: it.unit_price, base_price: it.base_price },
          variant: { size_name: it.size_code === "FREESIZE" ? "Freesize" : `Size ${it.size_label}`, color_name: it.color_name },
        })), tripSet.title);
        flyToCart(add, tripSet.items[0].image_url);
        toast(`Đã thêm ${tripSet.items.length} món của ${tripSet.title} vào giỏ.`);
        setTimeout(() => {
          closeModal(el);
          if (typeof toggleCartDrawer === "function") toggleCartDrawer();
        }, 650);
      } catch (err) {
        toast(err.message, true);
      } finally { add.disabled = false; }
    });
    return el;
  }

  function renderTripResult(box, set) {
    if (!set.items || !set.items.length) {
      box.innerHTML = `<p class="sp-trip-error">Chưa tìm được set phù hợp — thử nới ngân sách hoặc đổi phong cách nhé.</p>`;
      return;
    }
    const over = set.budget && !set.within_budget ? set.total_price - set.budget : 0;
    box.innerHTML = `
      <header class="sp-trip-head">
        <div><h4>${esc(set.title)}</h4><span>${esc(set.subtitle)}</span></div>
        <div class="sp-trip-total"><small>Tổng sau giảm</small><strong>${money(set.total_price)}</strong>
          ${set.savings > 0 ? `<em>Tiết kiệm ${money(set.savings)}</em>` : ""}</div>
      </header>
      <ul class="sp-trip-items">
        ${set.items.map((it) => `
          <li>
            <button type="button" class="sp-trip-img" data-open-product="${esc(it.slug)}" aria-label="Xem ${esc(it.name)}"><img src="${esc(it.image_url)}" alt=""></button>
            <div class="sp-trip-info">
              <span class="sp-trip-role">${esc(it.role_label)}</span>
              <button type="button" class="sp-trip-name" data-open-product="${esc(it.slug)}">${esc(it.name)}</button>
              <p>${esc(it.reason)}</p>
              <span class="sp-trip-meta">${[it.size_note, it.color_name].filter(Boolean).map(esc).join(" · ")}</span>
            </div>
            <div class="sp-trip-price">
              <strong>${money(it.unit_price)}</strong>
              ${it.discount_percent > 0 ? `<s>${money(it.base_price)}</s>` : ""}
            </div>
          </li>`).join("")}
      </ul>
      <footer class="sp-trip-foot">
        <span class="${over ? "is-over" : "is-ok"}">${set.budget ? (over ? `Vượt ngân sách ${money(over)}` : "✓ Trong ngân sách") : `${set.items.length} món · đều còn hàng`}</span>
        <button type="button" class="sp-btn-primary" data-add-set><i data-lucide="shopping-bag" class="w-4 h-4"></i>Thêm cả set vào giỏ</button>
      </footer>`;
    icons();
    if (window.gsap && !reduceMotion) {
      window.gsap.fromTo(box.querySelectorAll(".sp-trip-items li"), { y: 14, opacity: 0 }, { y: 0, opacity: 1, duration: 0.45, stagger: 0.06, ease: "power3.out" });
    }
  }

  function openTripStylist() {
    if (typeof toggleAIChatbox === "function") toggleAIChatbox(false);
    const el = ensureTripModal();
    const g = hasProfile() ? profile.gender : null;
    if (g && !el.dataset.prefilled) {
      const r = el.querySelector(`[name="gender"][value="${g}"]`);
      if (r) r.checked = true;
      el.dataset.prefilled = "1";
    }
    icons();
    openModal(el);
  }

  // ==========================================================================
  // 5. VISUAL SEARCH
  // ==========================================================================
  const MAX_BYTES = 6 * 1024 * 1024;
  const OK_TYPES = ["image/jpeg", "image/png", "image/webp"];
  const VS_CATS = [
    { v: "", label: "Tất cả" }, { v: "do-boi-nu", label: "Đồ bơi nữ" }, { v: "do-boi-nam", label: "Đồ bơi nam" },
    { v: "do-boi-tre-em", label: "Trẻ em" }, { v: "phu-kien-boi-loi", label: "Phụ kiện" },
  ];
  let visual = null;
  let pendingFile = null;

  function ensureVisualModal() {
    const el = makeModal("spVisualModal", `
      <div class="sp-head">
        <span class="sp-eyebrow">Soobin Lens</span>
        <h3>Tìm bằng hình ảnh</h3>
      </div>
      <label class="sp-drop" tabindex="0">
        <input type="file" accept="image/jpeg,image/png,image/webp" hidden>
        <div class="sp-drop-empty">
          <i data-lucide="image-plus" class="w-7 h-7"></i>
          <strong>Kéo thả hoặc chọn ảnh</strong>
          <span>JPG, PNG, WEBP · tối đa 6MB · dán Ctrl+V</span>
        </div>
        <img class="sp-drop-preview" alt="Ảnh đã chọn" hidden>
      </label>
      <div class="sp-pills sp-vs-cats">${VS_CATS.map((c, i) => `<label class="sp-pill"><input type="radio" name="vs_cat" value="${c.v}" ${i === 0 ? "checked" : ""}><span>${c.label}</span></label>`).join("")}</div>
      <p class="sp-vs-status" aria-live="polite"></p>
      <button type="button" class="sp-btn-primary sp-btn-block" data-vs-run disabled><i data-lucide="scan-search" class="w-4 h-4"></i>Tìm sản phẩm cùng tông màu</button>`, "sp-visual-sheet");
    const input = el.querySelector('input[type="file"]');
    const drop = el.querySelector(".sp-drop");
    input.addEventListener("change", () => input.files[0] && pickFile(input.files[0]));
    drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } });
    ["dragenter", "dragover"].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.add("is-drag"); }));
    ["dragleave", "drop"].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.remove("is-drag"); }));
    drop.addEventListener("drop", (e) => { const f = e.dataTransfer && e.dataTransfer.files[0]; if (f) pickFile(f); });
    el.querySelector("[data-vs-run]").addEventListener("click", runVisualSearch);
    document.addEventListener("paste", (e) => {
      if (!el.classList.contains("is-open")) return;
      const f = Array.from((e.clipboardData || {}).files || []).find((x) => x.type.startsWith("image/"));
      if (f) pickFile(f);
    });
    return el;
  }

  function pickFile(file) {
    const el = ensureVisualModal();
    const status = el.querySelector(".sp-vs-status");
    const run = el.querySelector("[data-vs-run]");
    if (!OK_TYPES.includes(file.type)) { status.textContent = "Chỉ hỗ trợ ảnh JPG, PNG hoặc WEBP."; status.classList.add("is-err"); return; }
    if (file.size > MAX_BYTES) { status.textContent = "Ảnh quá lớn — tối đa 6MB."; status.classList.add("is-err"); return; }
    status.classList.remove("is-err");
    status.textContent = "";
    pendingFile = file;
    const img = el.querySelector(".sp-drop-preview");
    if (img.dataset.url) URL.revokeObjectURL(img.dataset.url);
    img.dataset.url = URL.createObjectURL(file);
    img.src = img.dataset.url;
    img.hidden = false;
    el.querySelector(".sp-drop").classList.add("has-image");
    run.disabled = false;
    sfx("select");
  }

  async function runVisualSearch() {
    const el = ensureVisualModal();
    if (!pendingFile) return;
    const run = el.querySelector("[data-vs-run]");
    const status = el.querySelector(".sp-vs-status");
    const cat = (el.querySelector('[name="vs_cat"]:checked') || {}).value || "";
    const fd = new FormData();
    fd.append("image", pendingFile, pendingFile.name || "image");
    if (cat) fd.append("category", cat);
    run.disabled = true;
    status.classList.remove("is-err");
    status.textContent = "Đang phân tích màu sắc…";
    try {
      const data = await api("/visual-search", { method: "POST", body: fd });
      if (!data.results || !data.results.length) throw new Error("Chưa tìm thấy sản phẩm cùng tông màu.");
      const preview = el.querySelector(".sp-drop-preview").src;
      visual = { results: data.results, palette: data.palette || [], preview, category: cat, rendered: false };
      status.textContent = "";
      closeModal(el);
      if (view() === "shop" && shopRoute() === "all") {
        if (typeof productPage !== "undefined") productPage = 1;
        loadProducts();
      } else if (typeof navigateStorefront === "function") {
        navigateStorefront("#/shop/all");
      }
    } catch (err) {
      status.textContent = err.message;
      status.classList.add("is-err");
    } finally { run.disabled = false; }
  }

  function renderVisualBanner() {
    const grid = document.getElementById("productGrid");
    if (!grid || !visual) return;
    let banner = document.getElementById("spVisualBanner");
    if (!banner) {
      banner = document.createElement("div");
      banner.id = "spVisualBanner";
      banner.className = "sp-visual-banner";
      grid.parentElement.insertBefore(banner, grid);
      banner.addEventListener("click", (e) => {
        if (e.target.closest("[data-vs-clear]")) clearVisual(true);
        if (e.target.closest("[data-vs-retry]")) openVisualSearch();
      });
    }
    banner.innerHTML = `
      <img src="${esc(visual.preview)}" alt="Ảnh tìm kiếm">
      <div class="sp-vb-txt">
        <strong>Kết quả tìm theo ảnh</strong>
        <span class="sp-swatches">${visual.palette.slice(0, 5).map((c) => `<i style="background:${esc(c.hex)}" title="${esc(c.hex)}"></i>`).join("")}
          <em>${visual.results.length} sản phẩm cùng tông màu</em></span>
      </div>
      <button type="button" class="sp-vb-retry" data-vs-retry>Đổi ảnh</button>
      <button type="button" class="sp-vb-clear" data-vs-clear aria-label="Xoá kết quả tìm theo ảnh">✕ Xoá</button>`;
  }

  function clearVisual(reload = true) {
    if (!visual) return;
    visual = null;
    const banner = document.getElementById("spVisualBanner");
    if (banner) banner.remove();
    if (reload && view() === "shop" && typeof loadProducts === "function") {
      if (typeof productPage !== "undefined") productPage = 1;
      loadProducts();
    }
  }

  function interceptLoadProducts(silent) {
    if (!visual) return false;
    if (shopRoute() !== "all") { clearVisual(false); return false; }
    if (silent && visual.rendered) return true;
    visual.rendered = true;
    const grid = document.getElementById("productGrid");
    try { currentProducts = visual.results; } catch (_) {}
    window.products = visual.results;
    const badge = document.getElementById("catalogCountBadge");
    if (badge) badge.innerText = `${visual.results.length} kết quả theo ảnh`;
    const pag = document.getElementById("productPagination");
    if (pag) pag.innerHTML = "";
    renderVisualBanner();
    window._lastProductGridSignature = null;
    if (grid && typeof renderProductGrid === "function") {
      if (typeof runMorphTransition === "function") runMorphTransition(() => renderProductGrid(visual.results));
      else renderProductGrid(visual.results);
    }
    return true;
  }

  function openVisualSearch() {
    const el = ensureVisualModal();
    icons();
    openModal(el);
  }

  function wireVisualEntry() {
    document.querySelectorAll("[data-visual-search]").forEach((btn) => {
      btn.addEventListener("click", (e) => { e.preventDefault(); openVisualSearch(); });
      const box = btn.parentElement;
      ["dragenter", "dragover"].forEach((t) => box.addEventListener(t, (e) => {
        if (e.dataTransfer && Array.from(e.dataTransfer.types || []).includes("Files")) { e.preventDefault(); box.classList.add("sp-drop-hint"); }
      }));
      ["dragleave", "drop"].forEach((t) => box.addEventListener(t, () => box.classList.remove("sp-drop-hint")));
      box.addEventListener("drop", (e) => {
        const f = e.dataTransfer && e.dataTransfer.files[0];
        if (!f) return;
        e.preventDefault();
        openVisualSearch();
        pickFile(f);
      });
    });
    // Typing a keyword or changing filters leaves the image-result state
    ["searchInput", "mobileSearchInput"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener("input", () => clearVisual(false), true);
    });
    const toolbar = document.getElementById("catalogGrid");
    if (toolbar) {
      toolbar.addEventListener("change", () => clearVisual(false), true);
      toolbar.addEventListener("click", (e) => {
        const b = e.target.closest("button.quick-filter-btn");
        if (b && !(b.id || "").startsWith("layoutBtn-")) clearVisual(false);
      }, true);
    }
    window.addEventListener("hashchange", () => {
      if (!/^#\/shop\/all\b/.test(location.hash) && !/^#\/shop\/?$/.test(location.hash)) clearVisual(false);
    });
  }

  // ==========================================================================
  // BOOT
  // ==========================================================================
  let lastUserId = null;
  function watchSession() {
    const u = customer();
    const id = u ? u.id : null;
    if (id !== lastUserId) {
      lastUserId = id;
      syncedFor = null;
      if (id) syncProfileWithAccount();
    }
  }

  function boot() {
    updateProfileLabels();
    syncAdvisorInputs();
    wireVisualEntry();
    watchProductModal();
    setInterval(watchSession, 1500);
    setTimeout(watchSession, 600);
    setTimeout(initProof, 2500);
  }

  window.soobinPlus = {
    openFitProfile, openTripStylist, openVisualSearch, clearVisual,
    interceptLoadProducts, onGridRendered, onProductModalOpen, lookupVariant,
    getProfile: () => (hasProfile() ? cleanProfile() : null),
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
