// =============================================================================
// Soobin Swimwear - High-Fashion Editorial & GSAP Smooth Motion Storefront
// =============================================================================

let currentUser = null;
let currentProducts = [];
let selectedVariantId = null;
let selectedProduct = null;
let guestCart = JSON.parse(localStorage.getItem("soobin_guest_cart") || "[]");
let wishlistProductIds = new Set();
let catalogMorphLayout = "grid"; // grid | lookbook | compact
let heroSpotlightIndex = 0;

function getCustomerAuthHeaders(extra = {}) {
  const token = localStorage.getItem("customer_session_token");
  const headers = { ...extra };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

const _nativeCustomerFetch = window.fetch.bind(window);
window.fetch = function (input, init = {}) {
  const url = typeof input === "string" ? input : (input?.url || "");
  const custToken = localStorage.getItem("customer_session_token");
  if (custToken && url.startsWith("/api/")) {
    const mergedHeaders = new Headers(init.headers || {});
    if (!mergedHeaders.has("Authorization")) {
      mergedHeaders.set("Authorization", `Bearer ${custToken}`);
    }
    init = { ...init, headers: mergedHeaders };
  }
  return _nativeCustomerFetch(input, init);
};

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
  loadStoreTheme();
  checkAuth();
  initStorefrontRouter();
  loadLookbookBundles();
  loadAnnouncement();
  updateCartBadge();
  setupSearchInput();

  // Auto-cycle Hero Editorial Lookbook every 7 seconds
  setInterval(() => {
    const heroCard = document.getElementById("hero3DCard");
    if (heroCard && !heroCard.matches(":hover") && currentProducts.length > 1) {
      cycleHeroSpotlight(1);
    }
  }, 7000);

  if (window.startLiveSync) window.startLiveSync(async () => {
    // Product grid only lives in the shop view — skip refreshing it on the showcase home page
    const tasks = [loadAnnouncement(), loadStoreTheme(true), updateCartBadge()];
    if (storefrontView === "shop") tasks.push(loadProducts(true));
    await Promise.all(tasks);
    const ordersModal = document.getElementById("ordersModal");
    if (currentUser && ordersModal && !ordersModal.classList.contains("hidden")) await viewMyOrders();
  }, 8000);
});

// -----------------------------------------------------------------------------
// GSAP FLIP & SMOOTH LAYOUT TRANSITION ENGINE
// -----------------------------------------------------------------------------

function runMorphTransition(domMutationFn) {
  if (typeof window.runGsapFlipMorph === "function") {
    window.runGsapFlipMorph("[data-morph-id]", domMutationFn);
    return;
  }
  if (document.startViewTransition) {
    document.startViewTransition(() => {
      domMutationFn();
    });
    return;
  }
  domMutationFn();
}

function cycleHeroSpotlight(step = 1) {
  if (!currentProducts || currentProducts.length === 0) return;
  heroSpotlightIndex = (heroSpotlightIndex + step + currentProducts.length) % currentProducts.length;
  const p = currentProducts[heroSpotlightIndex];
  const imgEl = document.getElementById("heroSpotImg");
  const titleEl = document.getElementById("heroSpotTitle");
  const catEl = document.getElementById("heroSpotCategory");
  const priceEl = document.getElementById("heroSpotPrice");
  const tagEl = document.getElementById("heroSpotTag");
  if (!p || !imgEl) return;

  if (window.gsap) {
    window.gsap.to(imgEl, {
      opacity: 0.25,
      scale: 1.06,
      duration: 0.22,
      ease: "power2.in",
      onComplete: () => {
        if (tagEl) tagEl.innerText = p.discount_percent > 0 ? `🔥 ĐANG SALE -${p.discount_percent}%` : `✨ EDITORIAL LOOK #${heroSpotlightIndex + 1}`;
        imgEl.src = p.image_url;
        if (catEl) catEl.innerText = `${p.category_name} • ${p.target_audience}`;
        if (titleEl) titleEl.innerText = p.name;
        if (priceEl) priceEl.innerText = formatCurrency(p.discounted_price || p.base_price);

        window.gsap.fromTo(
          imgEl,
          { opacity: 0.25, scale: 1.08 },
          { opacity: 1, scale: 1, duration: 0.55, ease: "power3.out" }
        );
        if (titleEl) {
          window.gsap.fromTo(
            [catEl, titleEl, priceEl],
            { opacity: 0, y: 10 },
            { opacity: 1, y: 0, duration: 0.4, stagger: 0.05, ease: "power2.out" }
          );
        }
      },
    });
  } else {
    if (tagEl) tagEl.innerText = p.discount_percent > 0 ? `🔥 ĐANG SALE -${p.discount_percent}%` : `✨ EDITORIAL LOOK #${heroSpotlightIndex + 1}`;
    imgEl.src = p.image_url;
    if (catEl) catEl.innerText = `${p.category_name} • ${p.target_audience}`;
    if (titleEl) titleEl.innerText = p.name;
    if (priceEl) priceEl.innerText = formatCurrency(p.discounted_price || p.base_price);
  }
}

function openHeroSpotlightProduct() {
  if (!currentProducts || !currentProducts.length) return;
  const p = currentProducts[heroSpotlightIndex] || currentProducts[0];
  if (p) openProductModal(p.slug || p.id);
}

// -----------------------------------------------------------------------------
// MULTI-THEME & BANNER ENGINE (WITH SMOOTH GSAP CURTAIN TRANSITION)
// -----------------------------------------------------------------------------

async function loadStoreTheme(silent = false) {
  const localTheme = localStorage.getItem("soobin_user_theme");
  try {
    const res = await fetch("/api/v1/site-settings/theme", { cache: "no-store" });
    if (res.ok) {
      const cfg = await res.json();
      const activeTheme = localTheme || cfg.theme || "ocean-luxury";
      applyThemeToDocument(activeTheme, silent);
      if (cfg.hero_badge && document.getElementById("heroBadgeText")) {
        document.getElementById("heroBadgeText").innerText = cfg.hero_badge;
      }
      if (cfg.hero_title && document.getElementById("heroTitleText")) {
        document.getElementById("heroTitleText").innerText = cfg.hero_title;
      }
    }
  } catch (_) {
    if (localTheme) applyThemeToDocument(localTheme, true);
  }
}

function switchStoreTheme(themeName) {
  localStorage.setItem("soobin_user_theme", themeName);
  const labels = {
    "ocean-luxury": "Ocean Pearl Luxury",
    "sunset-ibiza": "Ibiza Sunset Resort",
    "midnight-vogue": "Midnight Vogue Dark",
    "minimal-atelier": "Zara Minimal Atelier"
  };
  const label = labels[themeName] || themeName;

  if (typeof window.playSoobinTransition === "function") {
    window.playSoobinTransition(label, "CHUYỂN ĐỔI CHỦ ĐỀ GIAO DIỆN", () => {
      applyThemeToDocument(themeName, false);
    });
  } else {
    applyThemeToDocument(themeName, false);
  }
  showToast(`✨ Đã chuyển sang chủ đề: ${label}`);
}
window.setStoreTheme = switchStoreTheme;

function applyThemeToDocument(themeName, silent) {
  document.documentElement.setAttribute("data-theme", themeName);
  document.querySelectorAll("[data-theme-btn]").forEach(btn => {
    const isMatch = btn.getAttribute("data-theme-btn") === themeName;
    btn.classList.toggle("ring-2", isMatch);
    btn.classList.toggle("ring-sky-500", isMatch);
    btn.classList.toggle("opacity-70", !isMatch);
  });
}

async function loadAnnouncement() {
  const primary = document.getElementById("announcementText");
  const clone = document.getElementById("announcementTextClone");
  if (!primary || !clone) return;
  try {
    const response = await fetch("/api/v1/site-settings/banner", { cache: "no-store" });
    if (!response.ok) return;
    const data = await response.json();
    primary.textContent = data.text;
    clone.textContent = data.text;
  } catch (_) {}
}

function showToast(msg, isError = false) {
  if (typeof window.notify === "function") {
    window.notify(msg, isError ? "error" : "success");
    return;
  }
  const toast = document.getElementById("toast");
  const toastMsg = document.getElementById("toastMessage");
  if (!toast) return;
  toastMsg.innerText = msg;
  toast.className = `fixed bottom-5 right-5 z-50 ${isError ? 'bg-rose-700' : 'bg-slate-900'} text-white px-4 py-3 rounded-xl shadow-xl text-sm flex items-center gap-2 transition transform translate-y-0`;
  toast.classList.remove("hidden");
  setTimeout(() => {
    toast.classList.add("hidden");
  }, 3500);
}

// -----------------------------------------------------------------------------
// AUTHENTICATION & VIP LOYALTY BAR
// -----------------------------------------------------------------------------

async function checkAuth() {
  try {
    const res = await fetch("/api/v1/auth/me", {
      headers: getCustomerAuthHeaders()
    });
    if (res.ok) {
      const user = await res.json();
      const roleCode = user.role?.code || user.role_code || "CUSTOMER";
      if (roleCode !== "CUSTOMER") {
        // Keep staff cookie intact for other tabs; render storefront as guest
        localStorage.removeItem("customer_session_token");
        currentUser = null;
        renderAuthGuest();
        updateWishlistBadge();
        return;
      }
      currentUser = user;
      renderAuthUser();
      await syncGuestCart();
      updateCartBadge();
      updateWishlistBadge();
      loadLoyaltySummary();
    } else {
      localStorage.removeItem("customer_session_token");
      currentUser = null;
      renderAuthGuest();
      updateWishlistBadge();
    }
  } catch (e) {
    currentUser = null;
    renderAuthGuest();
  }
}

async function loadLoyaltySummary() {
  if (!currentUser) return;
  try {
    const res = await fetch("/api/v1/orders/loyalty-summary", {
      headers: getCustomerAuthHeaders()
    });
    if (!res.ok) return;
    const data = await res.json();
    const badge = document.getElementById("loyaltyTierBadge");
    const pts = document.getElementById("loyaltyPointsText");
    const perk = document.getElementById("loyaltyPerkText");
    const bar = document.getElementById("loyaltyProgressBar");
    const tierName = data.current_tier || data.tier || "OCEAN MEMBER";
    if (badge) badge.innerText = `👑 HẠNG THẺ: ${tierName}`;
    if (pts) pts.innerText = `${data.points || 0} Điểm • Đã chi ${formatCurrency(data.total_spend || 0)}`;
    if (perk) perk.innerText = data.perk || "Tích điểm thành viên nhận ưu đãi";
    if (bar) bar.style.width = `${Math.max(12, data.progress_percent || 15)}%`;
  } catch (_) {}
}

function renderAuthUser() {
  const container = document.getElementById("authButtonContainer");
  if (!container) return;
  container.innerHTML = `
    <div class="relative group">
      <button class="flex items-center gap-2 px-3 py-1.5 text-xs font-bold bg-sky-50 text-sky-700 rounded-full border border-sky-200">
        <i data-lucide="user-check" class="w-4 h-4 text-sky-600"></i>
        <span>${currentUser.full_name}</span>
      </button>
      <div class="absolute right-0 top-full mt-1 w-56 bg-white text-slate-800 rounded-xl shadow-xl border border-slate-200 py-1.5 hidden group-hover:block z-50">
        <button onclick="viewMyOrders()" class="w-full px-3.5 py-2 text-left text-xs font-semibold text-slate-700 hover:bg-slate-50 flex items-center gap-2">
          <i data-lucide="package" class="w-4 h-4 text-sky-600"></i> Đơn hàng & Hóa đơn ĐT
        </button>
        <button onclick="openWishlistModal()" class="w-full px-3.5 py-2 text-left text-xs font-semibold text-slate-700 hover:bg-slate-50 flex items-center gap-2">
          <i data-lucide="heart" class="w-4 h-4 text-rose-500"></i> Danh sách yêu thích
        </button>
        <button onclick="openAddressBookModal()" class="w-full px-3.5 py-2 text-left text-xs font-semibold text-slate-700 hover:bg-slate-50 flex items-center gap-2">
          <i data-lucide="map-pin" class="w-4 h-4 text-emerald-600"></i> Sổ địa chỉ nhận hàng
        </button>
        <button onclick="handleLogout()" class="w-full px-3.5 py-2 text-left text-xs font-semibold text-rose-600 hover:bg-rose-50 flex items-center gap-2 border-t mt-1">
          <i data-lucide="log-out" class="w-4 h-4"></i> Đăng xuất
        </button>
      </div>
    </div>
  `;
  lucide.createIcons();
}

function renderAuthGuest() {
  const container = document.getElementById("authButtonContainer");
  if (!container) return;
  container.innerHTML = `
    <a href="/login" class="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-bold bg-sky-50 text-sky-600 hover:bg-sky-100 rounded-full transition">
      <i data-lucide="user" class="w-4 h-4"></i> Đăng Nhập
    </a>
  `;
  lucide.createIcons();
}

function openAuthModal() {
  window.location.href = "/login";
}

function closeAuthModal() {
  const el = document.getElementById("authModal");
  if (el) el.classList.add("hidden");
}

function switchAuthTab(tab) {
  const tabLogin = document.getElementById("tabLogin");
  const tabRegister = document.getElementById("tabRegister");
  const formLogin = document.getElementById("loginForm");
  const formRegister = document.getElementById("registerForm");

  if (tab === "login") {
    tabLogin.className = "pb-2 flex-1 text-center text-sky-600 border-b-2 border-sky-600";
    tabRegister.className = "pb-2 flex-1 text-center text-slate-400";
    formLogin.classList.remove("hidden");
    formRegister.classList.add("hidden");
  } else {
    tabRegister.className = "pb-2 flex-1 text-center text-sky-600 border-b-2 border-sky-600";
    tabLogin.className = "pb-2 flex-1 text-center text-slate-400";
    formRegister.classList.remove("hidden");
    formLogin.classList.add("hidden");
  }
}

function fillDemoLogin(email, pwd) {
  document.getElementById("loginEmail").value = email;
  document.getElementById("loginPassword").value = pwd;
}

async function handleLogin(e) {
  e.preventDefault();
  const email_or_phone = document.getElementById("loginEmail").value;
  const password = document.getElementById("loginPassword").value;

  try {
    const res = await fetch("/api/v1/auth/portal-login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email_or_phone, password, portal: "CUSTOMER" })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.detail || "Đăng nhập thất bại.", true);
      return;
    }
    closeAuthModal();
    showToast(`Xin chào ${data.user.full_name}!`);
    await checkAuth();
  } catch (err) {
    showToast("Lỗi kết nối máy chủ.", true);
  }
}

async function handleRegister(e) {
  e.preventDefault();
  const full_name = document.getElementById("regFullName").value;
  const email = document.getElementById("regEmail").value;
  const phone = document.getElementById("regPhone").value;
  const password = document.getElementById("regPassword").value;

  try {
    const res = await fetch("/api/v1/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ full_name, email, phone, password })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.detail || "Đăng ký thất bại.", true);
      return;
    }
    if (data.verification_token) {
      await fetch("/api/v1/auth/verify-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: data.verification_token })
      });
    }
    showToast("Đăng ký & xác minh email thành công! Vui lòng đăng nhập.");
    switchAuthTab("login");
    document.getElementById("loginEmail").value = email;
    document.getElementById("loginPassword").value = password;
  } catch (err) {
    showToast("Lỗi kết nối máy chủ.", true);
  }
}

async function handleLogout() {
  try {
    await fetch("/api/v1/auth/logout", {
      method: "POST",
      headers: getCustomerAuthHeaders()
    });
  } catch (_) {}
  localStorage.removeItem("customer_session_token");
  if (localStorage.getItem("user_role") === "CUSTOMER") {
    localStorage.removeItem("session_token");
    localStorage.removeItem("user_role");
    localStorage.removeItem("user_name");
  }
  currentUser = null;
  renderAuthGuest();
  updateCartBadge();
  updateWishlistBadge();
  showToast("Đã đăng xuất tài khoản khách hàng.");
}

// -----------------------------------------------------------------------------
// CATALOG, MORPH VIEW LAYOUTS & 3D PRODUCT CARDS
// -----------------------------------------------------------------------------

let activeCategory = "";
let isOutlet = false;
let productPage = 1;
const PRODUCTS_PER_PAGE = 20;

// -----------------------------------------------------------------------------
// STOREFRONT ROUTER — "#/" = trang chủ trình diễn, "#/shop/<danh-mục>" = lưới sản phẩm
// -----------------------------------------------------------------------------
let storefrontView = "home";
let activeShopRoute = null;

const SHOP_ROUTES = {
  "all": { cat: "", outlet: false, title: "Tất Cả Sản Phẩm", crumb: "Tất cả", illus: "goggles",
           desc: "Toàn bộ đồ bơi & phụ kiện đang bán tại Soobin." },
  "do-boi-nu": { cat: "do-boi-nu", outlet: false, title: "Đồ Bơi Nữ", crumb: "Đồ bơi nữ", illus: "umbrella",
                 desc: "Bikini, áo tắm một mảnh & rash guard — tôn dáng, chống UV UPF 50+." },
  "do-boi-nam": { cat: "do-boi-nam", outlet: false, title: "Đồ Bơi Nam", crumb: "Đồ bơi nam", illus: "medal",
                  desc: "Jammer thi đấu, boardshort đi biển & quần bơi boxer kháng Clo." },
  "phu-kien-boi-loi": { cat: "phu-kien-boi-loi", outlet: false, title: "Phụ Kiện Bơi Lội", crumb: "Phụ kiện", illus: "goggles",
                        desc: "Kính bơi, mũ bơi, chân vịt & túi chống nước." },
  "do-boi-tre-em": { cat: "do-boi-tre-em", outlet: false, title: "Đồ Bơi Trẻ Em", crumb: "Trẻ em", illus: "beachball",
                     desc: "Đồ bơi an toàn, chống nắng cho bé vui chơi cả ngày." },
  "sale": { cat: "", outlet: true, title: "Đang Giảm Giá", crumb: "Sale", illus: "starfish",
            desc: "Giá đã áp dụng ưu đãi trực tiếp — số lượng có hạn." },
};

function parseStorefrontHash() {
  const m = (location.hash || "").match(/^#\/shop(?:\/([\w-]+))?/);
  if (!m) return null;
  return m[1] || "all";
}

function setActiveRouteLinks(routeKey) {
  document.querySelectorAll("[data-route]").forEach((el) => {
    el.classList.toggle("is-active", !!routeKey && el.dataset.route === routeKey);
  });
}

function scrollStorefrontTop() {
  if (window.soobinLenis) window.soobinLenis.scrollTo(0, { immediate: true, force: true });
  window.scrollTo(0, 0);
}

function applyStorefrontRoute() {
  const routeKey = parseStorefrontHash();
  const homeView = document.getElementById("homeView");
  const shopView = document.getElementById("shopView");
  if (!homeView || !shopView) {
    // Not the storefront page layout — keep legacy behaviour
    loadProducts(true);
    return;
  }

  if (!routeKey) {
    // ---- HOME (showcase only, no product grid) ----
    const wasShop = storefrontView === "shop";
    storefrontView = "home";
    activeShopRoute = null;
    document.body.dataset.view = "home";
    setActiveRouteLinks(null);
    shopView.hidden = true;
    homeView.hidden = false;
    if (wasShop) scrollStorefrontTop();
    if (window.soobinMotion && typeof window.soobinMotion.setView === "function") window.soobinMotion.setView("home");
    return;
  }

  // ---- SHOP (product grid, no zoom effects) ----
  const route = SHOP_ROUTES[routeKey] || {
    cat: routeKey, outlet: false, title: "Bộ Sưu Tập", crumb: "Bộ sưu tập", illus: "goggles",
    desc: "Sản phẩm trong danh mục đã chọn.",
  };
  const enteringShop = storefrontView !== "shop";
  const routeChanged = activeShopRoute !== routeKey;

  if (enteringShop && window.soobinMotion && typeof window.soobinMotion.setView === "function") {
    window.soobinMotion.setView("shop");
  }
  storefrontView = "shop";
  activeShopRoute = routeKey;
  document.body.dataset.view = "shop";
  homeView.hidden = true;
  shopView.hidden = false;
  setActiveRouteLinks(routeKey);

  activeCategory = route.cat;
  isOutlet = route.outlet;
  if (routeChanged) productPage = 1;

  const titleEl = document.getElementById("catalogTitle");
  const crumbEl = document.getElementById("shopCrumb");
  const descEl = document.getElementById("shopDesc");
  const illusEl = document.getElementById("shopIllus");
  if (titleEl) titleEl.innerText = route.title;
  if (crumbEl) crumbEl.innerText = route.crumb;
  if (descEl) descEl.innerText = route.desc;
  if (illusEl) illusEl.src = `/static/images/illustrations/${route.illus}.svg`;
  document.title = `${route.title} — SOOBIN SWIMWEAR`;

  if (enteringShop || routeChanged) scrollStorefrontTop();
  loadProducts();
}

function navigateStorefront(hash) {
  if (location.hash === hash) applyStorefrontRoute();
  else location.hash = hash;
}

function initStorefrontRouter() {
  window.addEventListener("hashchange", applyStorefrontRoute);
  applyStorefrontRoute();
}

function setupSearchInput() {
  const inputs = ["searchInput", "mobileSearchInput"].map((id) => document.getElementById(id)).filter(Boolean);
  if (!inputs.length) return;
  let debounceTimer;
  inputs.forEach((input) => {
    input.addEventListener("input", () => {
      // Keep desktop & mobile search boxes in sync (loadProducts reads #searchInput)
      inputs.forEach((other) => { if (other !== input) other.value = input.value; });
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        productPage = 1;
        if (storefrontView !== "shop" && input.value.trim()) {
          navigateStorefront("#/shop/all");
        } else if (storefrontView === "shop") {
          loadProducts();
        }
      }, 300);
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && storefrontView !== "shop") navigateStorefront("#/shop/all");
    });
  });
}

function setCatalogMorphLayout(mode) {
  catalogMorphLayout = mode;
  ["grid", "lookbook", "compact"].forEach(m => {
    const btn = document.getElementById(`layoutBtn-${m}`);
    if (btn) {
      btn.className = m === mode
        ? "quick-filter-btn px-2.5 py-1.5 rounded-lg bg-white text-sky-700 shadow-sm flex items-center gap-1 transition"
        : "quick-filter-btn px-2.5 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 flex items-center gap-1 transition";
    }
  });
  runMorphTransition(() => {
    renderProductGrid(currentProducts);
  });
}

function filterCategory(catSlug) {
  navigateStorefront(`#/shop/${catSlug || "all"}`);
}

function filterOutlet() {
  navigateStorefront("#/shop/sale");
}

function applyFilters() {
  if (typeof window.playRefreshingSelectSound === "function") {
    window.playRefreshingSelectSound("select");
  }
  productPage = 1;
  loadProducts();
}

function applyQuickPriceRange(minP, maxP) {
  const minEl = document.getElementById("minPriceInput");
  const maxEl = document.getElementById("maxPriceInput");
  if (minEl) minEl.value = minP !== "" && minP !== null ? minP : "";
  if (maxEl) maxEl.value = maxP !== "" && maxP !== null ? maxP : "";
  applyFilters();
}

function changeProductPage(page) {
  productPage = Math.max(1, page);
  loadProducts();
  const toolbar = document.getElementById("catalogGrid");
  if (toolbar && window.soobinMotion && typeof window.soobinMotion.scrollToId === "function") {
    window.soobinMotion.scrollToId("catalogGrid");
  } else {
    toolbar?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

async function loadProducts(silent = false) {
  const grid = document.getElementById("productGrid");
  if (!grid) return;
  // storefront-plus.js hook: "Kết quả tìm theo ảnh" replaces the normal catalog query
  if (window.soobinPlus && typeof window.soobinPlus.interceptLoadProducts === "function" && window.soobinPlus.interceptLoadProducts(silent)) return;

  const audience = document.getElementById("audienceSelect") ? document.getElementById("audienceSelect").value : "";
  const sort = document.getElementById("sortSelect") ? document.getElementById("sortSelect").value : "newest";
  const search = document.getElementById("searchInput") ? document.getElementById("searchInput").value : "";
  const minPrice = document.getElementById("minPriceInput")?.value || "";
  const maxPrice = document.getElementById("maxPriceInput")?.value || "";

  let url = `/api/v1/catalog/products?sort_by=${sort}&limit=${PRODUCTS_PER_PAGE}&offset=${(productPage - 1) * PRODUCTS_PER_PAGE}`;
  if (activeCategory) url += `&category=${encodeURIComponent(activeCategory)}`;
  if (audience) url += `&audience=${encodeURIComponent(audience)}`;
  if (search) url += `&q=${encodeURIComponent(search)}`;
  if (minPrice) url += `&min_price=${encodeURIComponent(minPrice)}`;
  if (maxPrice) url += `&max_price=${encodeURIComponent(maxPrice)}`;
  if (isOutlet) url += `&on_sale=true`;

  try {
    const res = await fetch(url);
    const products = await res.json();
    currentProducts = products;
    window.products = products;

    const countBadge = document.getElementById("catalogCountBadge");
    if (countBadge) countBadge.innerText = `${products.length} mẫu hiển thị`;

    if (products.length > 0 && heroSpotlightIndex === 0) {
      const spot = products.find(p => p.discount_percent > 0) || products[0];
      if (spot && document.getElementById("heroSpotImg")) {
        document.getElementById("heroSpotTag").innerText = spot.discount_percent > 0 ? `🔥 ĐANG SALE -${spot.discount_percent}%` : "✨ EDITORIAL SPOTLIGHT";
        document.getElementById("heroSpotImg").src = spot.image_url;
        document.getElementById("heroSpotCategory").innerText = `${spot.category_name} • ${spot.target_audience}`;
        document.getElementById("heroSpotTitle").innerText = spot.name;
        document.getElementById("heroSpotPrice").innerText = formatCurrency(spot.discounted_price || spot.base_price);
      }
    }

    const pagination = document.getElementById("productPagination");
    if (pagination) pagination.innerHTML = products.length ? `
      <button onclick="changeProductPage(${productPage - 1})" ${productPage <= 1 ? "disabled" : ""} class="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:-translate-y-0.5 hover:shadow-lg disabled:opacity-40">← Trước</button>
      <span class="rounded-xl bg-sky-50 px-4 py-2 text-sm font-bold text-sky-700">Trang ${productPage}</span>
      <button onclick="changeProductPage(${productPage + 1})" ${products.length < PRODUCTS_PER_PAGE ? "disabled" : ""} class="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:-translate-y-0.5 hover:shadow-lg disabled:opacity-40">Tiếp →</button>
    ` : "";

    if (silent) {
      // Live-sync refresh: only re-render when data actually changed, so scroll
      // reveal animations do not replay every few seconds.
      const signature = JSON.stringify(products.map(p => [p.id, p.discounted_price, p.discount_percent, p.total_stock, p.image_url]))
        + `|${catalogMorphLayout}|${[...wishlistProductIds].join(",")}`;
      if (signature === window._lastProductGridSignature && grid.querySelector(".editorial-product-card")) return;
      window._lastProductGridSignature = signature;
      renderProductGrid(products);
    } else {
      window._lastProductGridSignature = null;
      runMorphTransition(() => renderProductGrid(products));
    }
  } catch (err) {
    grid.innerHTML = `<div class="col-span-full text-center text-rose-500 py-10">Lỗi khi tải danh sách sản phẩm.</div>`;
  }
}

function renderProductGrid(products) {
  const grid = document.getElementById("productGrid");
  if (!grid) return;

  if (catalogMorphLayout === "lookbook") {
    grid.className = "grid grid-cols-1 md:grid-cols-2 gap-8 morph-transition";
  } else if (catalogMorphLayout === "compact") {
    grid.className = "grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 morph-transition";
  } else {
    grid.className = "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 morph-transition";
  }

  if (!products || products.length === 0) {
    grid.innerHTML = `
      <div class="col-span-full py-16 text-center text-slate-400">
        <i data-lucide="package-search" class="w-12 h-12 mx-auto mb-2 text-slate-300"></i>
        <p class="font-semibold">Không tìm thấy sản phẩm nào phù hợp.</p>
      </div>
    `;
    lucide.createIcons();
    return;
  }

  grid.innerHTML = products.map((p) => {
    const isLiked = wishlistProductIds.has(p.id);
    const isCompared = (window.comparedProductIds || new Set()).has(p.id);
    const isLookbook = catalogMorphLayout === "lookbook";
    const savings = p.discount_percent > 0 ? Math.round(p.base_price - p.discounted_price) : 0;
    const gallery = Array.isArray(p.gallery_images) && p.gallery_images.length ? p.gallery_images : [p.image_url];

    return `
      <div data-morph-id="prod-${p.id}"
           class="editorial-product-card rounded-3xl overflow-hidden flex ${isLookbook ? 'flex-col sm:flex-row' : 'flex-col'} group">

        <!-- Product Image Frame -->
        <div class="relative bg-slate-100 ${isLookbook ? 'sm:w-1/2 aspect-[4/5]' : 'aspect-[4/5]'} overflow-hidden cursor-pointer" onclick="openProductModal('${p.slug}')">
          <img id="cardMainImg-${p.id}" src="${p.image_url}" alt="${p.name}" class="editorial-img-zoom w-full h-full object-cover">

          <div class="absolute top-3 left-3 flex flex-col gap-1.5 z-20">
            <span class="px-2.5 py-1 bg-slate-950/75 backdrop-blur-md text-white text-[10px] font-extrabold rounded-full uppercase tracking-wider">${p.target_audience}</span>
            ${p.discount_percent > 0 ? `
              <span class="px-2.5 py-1 bg-gradient-to-r from-rose-600 via-orange-500 to-amber-500 text-white text-[10px] font-black rounded-full shadow-lg">
                -${p.discount_percent}% SALE
              </span>
            ` : ''}
            ${p.total_stock <= 0 ? `<span class="px-2.5 py-1 bg-rose-700 text-white text-[10px] font-bold rounded-full">Hết hàng</span>` : ''}
          </div>

          <div class="z-20 absolute top-3 right-3 flex flex-col gap-1.5">
            <button type="button" onclick="toggleWishlistItem(event, ${p.id})" title="Yêu thích"
                    class="w-9 h-9 rounded-full ${isLiked ? 'bg-rose-500 text-white' : 'bg-white/90 text-rose-500 hover:bg-rose-500 hover:text-white'} backdrop-blur shadow-md flex items-center justify-center transition">
              <i data-lucide="heart" class="w-4 h-4 ${isLiked ? 'fill-current' : ''}"></i>
            </button>
            <button type="button" onclick="toggleCompareProduct(${p.id}, event)" title="So sánh sản phẩm"
                    class="w-9 h-9 rounded-full ${isCompared ? 'bg-cyan-500 text-slate-950 ring-2 ring-white' : 'bg-slate-900/80 text-cyan-300 hover:bg-cyan-500 hover:text-slate-950'} backdrop-blur shadow-md flex items-center justify-center transition">
              <i data-lucide="columns-3" class="w-4 h-4"></i>
            </button>
          </div>

          <!-- Multi-Image Mini Gallery Switcher on Card -->
          ${gallery.length > 1 ? `
            <div class="editorial-quick-bar absolute inset-x-2.5 bottom-2.5 p-1.5 rounded-2xl bg-slate-950/85 backdrop-blur-md border border-white/15 flex items-center justify-between gap-2 text-white text-[11px] font-bold z-20" onclick="event.stopPropagation()">
              <div class="flex items-center gap-1.5 pl-1">
                ${gallery.slice(0, 4).map((gUrl) => `
                  <img src="${gUrl}" onmouseenter="document.getElementById('cardMainImg-${p.id}').src='${gUrl}'" onclick="document.getElementById('cardMainImg-${p.id}').src='${gUrl}'"
                       class="w-7 h-7 rounded-lg object-cover border border-white/30 hover:border-cyan-400 cursor-pointer transition">
                `).join("")}
              </div>
              <button type="button" onclick="openProductModal('${p.slug}')" class="px-2.5 py-1 rounded-xl bg-white text-slate-950 font-extrabold text-[10px] flex items-center gap-1 shrink-0">
                <i data-lucide="eye" class="w-3 h-3"></i> Chi Tiết
              </button>
            </div>
          ` : ''}
        </div>

        <!-- Info Area -->
        <div class="p-4 ${isLookbook ? 'sm:w-1/2 flex flex-col justify-between' : 'flex-1 flex flex-col justify-between'} space-y-3">
          <div class="space-y-1">
            <div class="flex items-center justify-between">
              <span class="text-[10px] font-extrabold text-sky-500 uppercase tracking-widest">${p.category_name}</span>
              <span class="text-[10px] font-semibold ${p.total_stock > 5 ? 'text-emerald-600' : 'text-amber-600'}">Còn ${p.total_stock} chiếc</span>
            </div>
            <h3 class="font-extrabold text-sm line-clamp-2 hover:text-sky-500 cursor-pointer transition" onclick="openProductModal('${p.slug}')">
              ${p.name}
            </h3>
            ${isLookbook ? `<p class="text-xs text-slate-500 line-clamp-3 pt-1">Thiết kế chuẩn form Á Đông, chất liệu Carvico Ý kháng Clo & chống tia UV UPF 50+ cao cấp giúp tôn dáng và vận động linh hoạt.</p>` : ''}
          </div>

          <div class="pt-3 border-t border-slate-200/60 flex items-end justify-between gap-2">
            <div>
              ${p.discount_percent > 0 ? `
                <div class="flex items-center gap-1.5">
                  <span class="text-base font-black text-rose-600">${formatCurrency(p.discounted_price)}</span>
                  <span class="text-[11px] text-slate-400 line-through">${formatCurrency(p.base_price)}</span>
                </div>
                <span class="text-[10px] font-bold text-emerald-600 block">Tiết kiệm ${formatCurrency(savings)}</span>
              ` : `
                <span class="text-base font-black">${formatCurrency(p.base_price)}</span>
                <span class="text-[10px] text-slate-400 block">Giá niêm yết chính hãng</span>
              `}
            </div>
            <button onclick="openProductModal('${p.slug}')" class="px-3.5 py-2 bg-gradient-to-r from-sky-600 to-cyan-500 text-white rounded-xl text-xs font-extrabold shadow-md hover:shadow-sky-500/30 hover:scale-105 transition flex items-center gap-1">
              <span>Chọn Size</span>
              <i data-lucide="arrow-up-right" class="w-3.5 h-3.5"></i>
            </button>
          </div>
        </div>
      </div>
    `;
  }).join("");

  lucide.createIcons();

  // Scroll-driven zoom reveal (storefront-motion.js); fallback to simple stagger
  if (window.soobinMotion && typeof window.soobinMotion.revealCards === "function") {
    window.soobinMotion.revealCards(grid);
  } else if (window.gsap) {
    window.gsap.fromTo(
      "#productGrid > div",
      { opacity: 0, y: 22 },
      { opacity: 1, y: 0, duration: 0.48, stagger: 0.035, ease: "power2.out", overwrite: "auto" }
    );
  }
  // storefront-plus.js hook: fit badges + one-tap size chips on shop cards
  if (window.soobinPlus && typeof window.soobinPlus.onGridRendered === "function") window.soobinPlus.onGridRendered(grid, products);
}

// -----------------------------------------------------------------------------
// EDITORIAL PRODUCT DETAIL GALLERY, INTERACTIVE FABRIC ZOOM & SIZE CHART MODAL
// -----------------------------------------------------------------------------

function handleEditorialZoomMove(e, stageEl) {
  const rect = stageEl.getBoundingClientRect();
  const xPct = Math.max(0, Math.min(100, ((e.clientX - rect.left) / rect.width) * 100));
  const yPct = Math.max(0, Math.min(100, ((e.clientY - rect.top) / rect.height) * 100));
  stageEl.style.setProperty("--zoom-x", `${xPct.toFixed(1)}%`);
  stageEl.style.setProperty("--zoom-y", `${yPct.toFixed(1)}%`);
}

function switchEditorialMainPhoto(imgPath) {
  const imgEl = document.getElementById("detailMainImg");
  if (!imgEl || !imgPath) return;
  if (window.gsap) {
    window.gsap.to(imgEl, {
      opacity: 0.2,
      duration: 0.16,
      onComplete: () => {
        imgEl.src = imgPath;
        window.gsap.to(imgEl, { opacity: 1, duration: 0.32, ease: "power2.out" });
      },
    });
  } else {
    imgEl.src = imgPath;
  }
}

async function openProductModal(slug) {
  try {
    const res = await fetch(`/api/v1/catalog/products/${slug}`);
    if (!res.ok) throw new Error();
    const prod = await res.json();
    selectedProduct = prod;

    const modal = document.getElementById("productDetailModal");
    const content = document.getElementById("productModalContent");

    const firstAvail = prod.variants.find(v => v.available_quantity > 0) || prod.variants[0];
    selectedVariantId = firstAvail ? firstAvail.id : null;

    const companions = currentProducts.filter(x => x.id !== prod.id).slice(0, 2);
    const primaryImg = (prod.images && prod.images[0]) ? prod.images[0].file_path : "/static/images/placeholder.webp";
    const sp = prod.spatial_3d || {};
    const physics = sp.material_physics || {};

    content.innerHTML = `
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <!-- Left Column: High-Fashion Editorial Lookbook Gallery & Interactive Zoom Lens -->
        <div class="lg:col-span-6 space-y-3">
          <div onmousemove="handleEditorialZoomMove(event, this)"
               class="editorial-zoom-stage aspect-[4/5] bg-slate-100 rounded-2xl overflow-hidden border border-slate-200 relative shadow-md">
            <img id="detailMainImg" src="${primaryImg}" alt="${prod.name}" class="w-full h-full object-cover">
            ${prod.discount_percent > 0 ? `
              <div class="pointer-events-none absolute top-3 left-3 px-3 py-1 bg-gradient-to-r from-rose-600 to-amber-500 text-white font-black text-xs rounded-full shadow-lg">
                ĐANG GIẢM -${prod.discount_percent}%
              </div>
            ` : ''}
            <div class="pointer-events-none absolute bottom-3 inset-x-3 flex items-center justify-between px-3 py-1.5 bg-slate-950/75 backdrop-blur-md rounded-xl border border-white/15 text-white text-[11px] font-bold">
              <span class="text-cyan-300 flex items-center gap-1">🏊 ${prod.category_name}</span>
              <span id="detailActiveColorLabel" class="text-amber-300">${firstAvail ? `${firstAvail.color_name} • Size ${firstAvail.size_name}` : ''}</span>
            </div>
          </div>

          <!-- Thumbnail Strip (Multi-Angle Product Gallery) -->
          ${prod.images && prod.images.length > 1 ? `
            <div class="grid grid-cols-4 gap-2 pb-1">
              ${prod.images.map((img, i) => `
                <button type="button" onclick="switchEditorialMainPhoto('${img.file_path}')"
                        class="group relative aspect-square rounded-xl overflow-hidden border-2 ${i === 0 ? 'border-sky-500' : 'border-slate-200 hover:border-sky-400'} transition">
                  <img src="${img.file_path}" alt="${img.alt_text || prod.name}" class="w-full h-full object-cover group-hover:scale-105 transition">
                </button>
              `).join("")}
            </div>
          ` : ''}

          <!-- Material & Craftsmanship Highlights -->
          <div class="grid grid-cols-3 gap-2 text-center bg-slate-50 border border-slate-200/80 rounded-2xl p-3 text-xs">
            <div>
              <span class="text-[10px] text-slate-400 uppercase font-bold block">Chống Tia Cực Tím</span>
              <strong class="text-sky-700 font-extrabold">${physics.uv_protection || 'UPF 50+'}</strong>
            </div>
            <div class="border-x border-slate-200">
              <span class="text-[10px] text-slate-400 uppercase font-bold block">Kháng Nước Clo</span>
              <strong class="text-emerald-700 font-extrabold">${physics.chlorine_resistance_hours || 300} giờ bơi</strong>
            </div>
            <div>
              <span class="text-[10px] text-slate-400 uppercase font-bold block">Độ Co Giãn 4 Chiều</span>
              <strong class="text-amber-600 font-extrabold">${Math.round((physics.stretch_factor || 1.38) * 100)}% Recovery</strong>
            </div>
          </div>
        </div>

        <!-- Right Column: Details & Actions -->
        <div class="lg:col-span-6 space-y-4 flex flex-col justify-between">
          <div class="space-y-2.5">
            <div class="flex items-center justify-between">
              <span class="text-xs font-extrabold text-sky-600 uppercase tracking-wider">${prod.category_name} • Mã: ${prod.code}</span>
              <span class="text-xs font-bold text-amber-500 flex items-center gap-1">
                ★ ${prod.avg_rating || 5.0} <span class="text-slate-400 font-normal">(${prod.review_count || 0} đánh giá)</span>
              </span>
            </div>
            <h2 class="text-2xl font-black text-slate-900 leading-tight">${prod.name}</h2>

            <div class="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80 flex items-center justify-between">
              <div>
                ${prod.discount_percent > 0 ? `
                  <div class="flex items-center gap-2.5">
                    <span class="text-2xl font-black text-rose-600">${formatCurrency(prod.discounted_price)}</span>
                    <span class="text-sm text-slate-400 line-through">${formatCurrency(prod.base_price)}</span>
                    <span class="px-2.5 py-0.5 bg-rose-100 text-rose-700 text-xs font-extrabold rounded-full">-${prod.discount_percent}%</span>
                  </div>
                  <span class="text-[11px] text-emerald-700 font-semibold">✓ Giá ưu đãi trực tiếp tốt nhất từ cửa hàng</span>
                ` : `
                  <span class="text-2xl font-black text-sky-600">${formatCurrency(prod.base_price)}</span>
                  <span class="text-[11px] text-slate-500 block">Áp dụng thêm giảm 10% cho đơn từ 500K hoặc mã SOOBIN15</span>
                `}
              </div>
            </div>

            <p class="text-xs text-slate-600 leading-relaxed">${prod.description || 'Thiết kế thời trang biển cao cấp, ôm sát tôn dáng, co giãn 4 chiều và chống nắng UPF 50+.'}</p>
          </div>

          <!-- Variants Selector -->
          <div class="space-y-2.5 pt-2 border-t">
            <div class="flex items-center justify-between">
              <label class="block text-xs font-extrabold text-slate-800 uppercase tracking-wider">Chọn Size & Màu sắc:</label>
              <button type="button" onclick="closeProductModal(); toggleAIChatbox(true);" class="text-xs font-bold text-sky-600 hover:underline flex items-center gap-1">
                <i data-lucide="sparkles" class="w-3.5 h-3.5"></i> Hỏi AI tư vấn size chuẩn
              </button>
            </div>
            <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
              ${prod.variants.map(v => `
                <button onclick="selectVariant(${v.id})" id="varBtn-${v.id}" class="p-2.5 border rounded-xl text-left text-xs transition ${v.id === selectedVariantId ? 'border-sky-600 bg-sky-50 ring-2 ring-sky-500/20' : 'border-slate-200 hover:border-slate-300'} ${v.available_quantity <= 0 ? 'opacity-40 cursor-not-allowed' : ''}">
                  <div class="flex items-center justify-between">
                    <span class="font-extrabold text-slate-900">${v.size_name}</span>
                    <span class="w-3 h-3 rounded-full border" style="background:${v.color_hex || '#0284c7'}"></span>
                  </div>
                  <span class="text-slate-500 text-[11px] block">${v.color_name}</span>
                  <span class="text-[10px] block font-bold ${v.available_quantity > 0 ? 'text-emerald-600' : 'text-rose-500'}">
                    Tồn: ${v.available_quantity} chiếc
                  </span>
                </button>
              `).join("")}
            </div>
          </div>

          <!-- Size Chart View -->
          ${renderSizeChart(prod.size_chart)}

          <!-- Add to Cart, Instant Buy Now & Wishlist Action -->
          <div class="pt-3 border-t flex flex-wrap gap-2">
            <div class="w-16">
              <input type="number" id="detailQty" value="1" min="1" max="99" class="w-full text-center py-3 border rounded-xl text-sm font-bold focus:ring-2 focus:ring-sky-500 outline-none">
            </div>
            <button onclick="handleAddToCartFromModal()" data-sfx-select="cart" class="flex-1 py-3 bg-sky-600 hover:bg-sky-700 text-white font-extrabold rounded-xl shadow-sm transition flex items-center justify-center gap-1.5 text-xs sm:text-sm">
              <i data-lucide="shopping-bag" class="w-4 h-4"></i>
              <span>Thêm Vào Giỏ</span>
            </button>
            <button onclick="handleBuyNowFromModal()" data-sfx-select="cart" class="flex-1 py-3 bg-teal-600 hover:bg-teal-700 text-white font-extrabold rounded-xl shadow-sm transition flex items-center justify-center gap-1.5 text-xs sm:text-sm">
              <i data-lucide="zap" class="w-4 h-4"></i>
              <span>Mua Ngay</span>
            </button>
            <button onclick="toggleWishlistItem(event, ${prod.id})" title="Yêu thích" class="px-3.5 py-3 border border-rose-200 bg-rose-50 text-rose-600 hover:bg-rose-500 hover:text-white rounded-xl transition flex items-center justify-center">
              <i data-lucide="heart" class="w-4 h-4"></i>
            </button>
          </div>

          <!-- Complete The Look (Mix & Match) -->
          ${companions.length ? `
            <div class="pt-3 border-t border-dashed space-y-2">
              <span class="text-[11px] font-extrabold uppercase tracking-wider text-slate-500 block">✨ Gợi Ý Phối Đồ Cùng Bộ Sưu Tập (Mix & Match):</span>
              <div class="grid grid-cols-2 gap-2">
                ${companions.map(c => `
                  <div onclick="openProductModal('${c.slug}')" class="p-2 rounded-xl border border-slate-200 hover:border-sky-400 flex items-center gap-2 cursor-pointer transition bg-slate-50/60">
                    <img src="${c.image_url}" class="w-10 h-10 rounded-lg object-cover">
                    <div class="min-w-0">
                      <p class="text-[11px] font-bold text-slate-800 truncate">${c.name}</p>
                      <span class="text-[11px] font-extrabold text-sky-600">${formatCurrency(c.discounted_price || c.base_price)}</span>
                    </div>
                  </div>
                `).join("")}
              </div>
            </div>
          ` : ''}
        </div>
      </div>

      <!-- Customer Reviews Section -->
      <div class="mt-6 pt-5 border-t border-slate-200 space-y-3">
        <div class="flex items-center justify-between">
          <h4 class="text-sm font-extrabold text-slate-900 flex items-center gap-2">
            <i data-lucide="message-square-heart" class="w-4 h-4 text-amber-500"></i>
            Đánh Giá Từ Khách Hàng (${prod.review_count || 0})
          </h4>
        </div>
        ${(prod.reviews && prod.reviews.length > 0) ? `
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-48 overflow-y-auto pr-1">
            ${prod.reviews.map(r => `
              <div class="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-1 text-xs">
                <div class="flex items-center justify-between">
                  <strong class="text-slate-900">${r.customer_name}</strong>
                  <span class="text-amber-500 font-bold">${'★'.repeat(r.rating)}${'☆'.repeat(5 - r.rating)}</span>
                </div>
                <p class="text-slate-600">${r.content}</p>
                <span class="text-[10px] text-slate-400 block">${new Date(r.created_at).toLocaleDateString('vi-VN')}</span>
              </div>
            `).join("")}
          </div>
        ` : `
          <p class="text-xs text-slate-400 italic py-2">Chưa có đánh giá nào cho sản phẩm này. Hãy mua sắm và trở thành người đầu tiên đánh giá!</p>
        `}
      </div>
    `;

    lucide.createIcons();
    modal.classList.remove("hidden");
    // storefront-plus.js hook: fit recommendation + live "đang xem" presence
    if (window.soobinPlus && typeof window.soobinPlus.onProductModalOpen === "function") window.soobinPlus.onProductModalOpen(prod);
    if (window.gsap) {
      window.gsap.fromTo(
        modal.firstElementChild,
        { opacity: 0, y: 24, scale: 0.96 },
        { opacity: 1, y: 0, scale: 1, duration: 0.38, ease: "power3.out" }
      );
    }
  } catch (err) {
    showToast("Không thể mở chi tiết sản phẩm.", true);
  }
}

function selectVariant(variantId) {
  if (typeof window.playRefreshingSelectSound === "function") {
    window.playRefreshingSelectSound("select");
  }
  selectedVariantId = variantId;
  if (!selectedProduct) return;
  let chosenVar = null;
  selectedProduct.variants.forEach(v => {
    if (v.id === variantId) chosenVar = v;
    const btn = document.getElementById(`varBtn-${v.id}`);
    if (btn) {
      if (v.id === variantId) {
        btn.className = "p-2.5 border rounded-xl text-left text-xs transition border-sky-600 bg-sky-50 ring-2 ring-sky-500/20";
      } else {
        btn.className = `p-2.5 border rounded-xl text-left text-xs transition border-slate-200 hover:border-slate-300 ${v.available_quantity <= 0 ? 'opacity-40 cursor-not-allowed' : ''}`;
      }
    }
  });

  if (chosenVar) {
    const lbl = document.getElementById("detailActiveColorLabel");
    if (lbl) lbl.innerText = `${chosenVar.color_name} • Size ${chosenVar.size_name}`;
  }
}

function renderSizeChart(chart) {
  if (!chart || Object.keys(chart).length === 0) return '';
  const rows = Object.entries(chart).map(([size, specs]) => {
    const details = Object.entries(specs).map(([k, v]) => `${k}: ${v}`).join(", ");
    return `<tr class="border-b"><td class="py-1.5 font-bold text-slate-800">${size}</td><td class="py-1.5 text-slate-600 text-[11px]">${details}</td></tr>`;
  }).join("");

  return `
    <div class="bg-slate-50 p-3 rounded-xl border border-slate-200 text-xs">
      <span class="font-bold text-slate-800 flex items-center gap-1 mb-1">
        <i data-lucide="ruler" class="w-3.5 h-3.5 text-sky-600"></i> Bảng Đo Kích Thước Chuẩn (Size Chart)
      </span>
      <table class="w-full text-left">
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function closeProductModal() {
  document.getElementById("productDetailModal").classList.add("hidden");
}

// -----------------------------------------------------------------------------
// CART OPERATIONS (GUEST & LOGGED-IN)
// -----------------------------------------------------------------------------

function toggleCartDrawer() {
  const drawer = document.getElementById("cartDrawer");
  const backdrop = document.getElementById("cartDrawerBackdrop");
  if (drawer.classList.contains("translate-x-full")) {
    drawer.classList.remove("translate-x-full");
    backdrop.classList.remove("hidden");
    loadCartItems();
  } else {
    drawer.classList.add("translate-x-full");
    backdrop.classList.add("hidden");
  }
}

async function handleAddToCartFromModal() {
  if (!selectedVariantId) {
    showToast("Vui lòng chọn phân loại kích cỡ & màu sắc.", true);
    return false;
  }
  const qty = parseInt(document.getElementById("detailQty").value) || 1;

  if (currentUser) {
    try {
      const res = await fetch("/api/v1/cart/items", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ variant_id: selectedVariantId, quantity: qty })
      });
      const data = await res.json();
      if (!res.ok) {
        showToast(data.detail || "Không thể thêm vào giỏ.", true);
        return false;
      }
      showToast("Đã thêm sản phẩm vào giỏ hàng!");
      closeProductModal();
      updateCartBadge();
      toggleCartDrawer();
      return true;
    } catch (err) {
      showToast("Lỗi khi thêm giỏ hàng.", true);
      return false;
    }
  } else {
    const existing = guestCart.find(i => i.variant_id === selectedVariantId);
    if (existing) {
      existing.quantity += qty;
    } else {
      guestCart.push({ variant_id: selectedVariantId, quantity: qty });
    }
    localStorage.setItem("soobin_guest_cart", JSON.stringify(guestCart));
    showToast("Đã thêm vào giỏ hàng vãng lai!");
    closeProductModal();
    updateCartBadge();
    toggleCartDrawer();
    return true;
  }
}

async function handleBuyNowFromModal() {
  if (!selectedVariantId) {
    showToast("Vui lòng chọn phân loại kích cỡ & màu sắc.", true);
    return;
  }
  const added = await handleAddToCartFromModal();
  if (!added) return;
  setTimeout(() => {
    const drawer = document.getElementById("cartDrawer");
    const backdrop = document.getElementById("cartDrawerBackdrop");
    if (drawer && !drawer.classList.contains("translate-x-full")) {
      drawer.classList.add("translate-x-full");
      if (backdrop) backdrop.classList.add("hidden");
    }
    openCheckoutModal();
  }, 180);
}

async function syncGuestCart() {
  if (guestCart.length === 0) return;
  try {
    const res = await fetch("/api/v1/cart/merge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: guestCart })
    });
    if (res.ok) {
      const data = await res.json();
      guestCart = [];
      localStorage.removeItem("soobin_guest_cart");
      if (data.adjustments && data.adjustments.length > 0) {
        showToast(data.adjustments.join(" | "));
      }
      updateCartBadge();
    }
  } catch (e) {}
}

async function updateCartBadge() {
  const badge = document.getElementById("cartBadge");
  if (!badge) return;

  if (currentUser) {
    try {
      const res = await fetch("/api/v1/cart");
      if (res.ok) {
        const cart = await res.json();
        badge.innerText = cart.total_items || 0;
      }
    } catch (e) {}
  } else {
    const total = guestCart.reduce((sum, i) => sum + i.quantity, 0);
    badge.innerText = total;
  }
}

async function loadCartItems() {
  const list = document.getElementById("cartItemsList");
  if (!list) return;

  if (currentUser) {
    try {
      const res = await fetch("/api/v1/cart");
      const cart = await res.json();
      renderCartUI(cart.items, cart.discounted_subtotal || cart.subtotal);
    } catch (err) {
      list.innerHTML = `<div class="text-center text-rose-500 py-6">Lỗi tải giỏ hàng.</div>`;
    }
  } else {
    if (guestCart.length === 0) {
      renderCartUI([], 0);
      return;
    }
    let subtotal = 0;
    const items = [];
    for (const gi of guestCart) {
      let foundVar = null;
      let foundProd = null;
      for (const p of currentProducts) {
        const v = (p.variants || []).find(x => x.id === gi.variant_id);
        if (v) { foundVar = v; foundProd = p; break; }
      }
      // storefront-plus.js keeps a small variant cache (quick-add / trip sets) for guest carts
      if (!foundVar && window.soobinPlus && typeof window.soobinPlus.lookupVariant === "function") {
        const hit = window.soobinPlus.lookupVariant(gi.variant_id);
        if (hit) { foundVar = hit.variant; foundProd = hit.product; }
      }
      const unit_price = foundProd ? (foundProd.discounted_price || foundProd.base_price) : 0;
      const line_total = unit_price * gi.quantity;
      subtotal += line_total;
      items.push({
        variant_id: gi.variant_id,
        product_name: foundProd ? foundProd.name : `Biến thể #${gi.variant_id}`,
        size_name: foundVar ? foundVar.size_name : "",
        color_name: foundVar ? foundVar.color_name : "",
        unit_price: unit_price,
        quantity: gi.quantity,
        line_total: line_total,
        is_valid_for_checkout: true,
        image_url: foundProd ? foundProd.image_url : "/static/images/placeholder.webp"
      });
    }
    renderCartUI(items, subtotal);
  }
}

function renderCartUI(items, subtotal) {
  const list = document.getElementById("cartItemsList");
  const subtotalEl = document.getElementById("cartSubtotalText");
  subtotalEl.innerText = formatCurrency(subtotal);

  if (items.length === 0) {
    list.innerHTML = `
      <div class="py-16 text-center text-slate-400 space-y-2">
        <i data-lucide="shopping-bag" class="w-12 h-12 mx-auto text-slate-300"></i>
        <p class="font-medium text-sm">Giỏ hàng của bạn đang trống.</p>
        <button onclick="toggleCartDrawer()" class="px-4 py-2 bg-sky-50 text-sky-600 font-bold rounded-lg text-xs hover:bg-sky-100">Khám phá sản phẩm</button>
      </div>
    `;
    lucide.createIcons();
    return;
  }

  list.innerHTML = items.map(item => `
    <div class="p-3 bg-slate-50 border border-slate-200 rounded-xl flex gap-3 items-center">
      <img src="${item.image_url}" class="w-16 h-16 object-cover rounded-lg border bg-white">
      <div class="flex-1 min-w-0">
        <h4 class="font-bold text-xs text-slate-900 truncate">${item.product_name}</h4>
        <span class="text-[11px] text-slate-500 block">${item.size_name} - ${item.color_name}</span>
        ${item.discount_percent > 0 ? `
          <div class="flex items-center gap-1.5">
            <span class="font-extrabold text-xs text-rose-600">${formatCurrency(item.sale_price)}</span>
            <span class="text-[10px] text-slate-400 line-through">${formatCurrency(item.base_price || item.unit_price)}</span>
            <span class="px-1.5 py-0.2 bg-rose-100 text-rose-700 text-[9px] font-bold rounded">-${item.discount_percent}%</span>
          </div>
        ` : `
          <span class="font-bold text-xs text-sky-600">${formatCurrency(item.sale_price || item.unit_price)}</span>
        `}
        ${item.status_message ? `<span class="text-[10px] text-rose-500 block font-semibold">${item.status_message}</span>` : ''}
      </div>
      <div class="flex flex-col items-end gap-1.5">
        <div class="flex items-center border bg-white rounded-lg">
          <button onclick="updateCartQuantity(${item.variant_id}, ${item.quantity - 1})" class="px-2 py-0.5 text-xs text-slate-600 hover:bg-slate-100">-</button>
          <span class="px-2 text-xs font-bold">${item.quantity}</span>
          <button onclick="updateCartQuantity(${item.variant_id}, ${item.quantity + 1})" class="px-2 py-0.5 text-xs text-slate-600 hover:bg-slate-100">+</button>
        </div>
        <button onclick="updateCartQuantity(${item.variant_id}, 0)" class="text-[11px] text-rose-500 hover:text-rose-700">Xóa</button>
      </div>
    </div>
  `).join("");

  lucide.createIcons();
}

async function updateCartQuantity(variantId, newQty) {
  if (currentUser) {
    if (newQty <= 0) {
      await fetch(`/api/v1/cart/items/${variantId}`, { method: "DELETE" });
    } else {
      await fetch(`/api/v1/cart/items/${variantId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ quantity: newQty })
      });
    }
    loadCartItems();
    updateCartBadge();
  } else {
    if (newQty <= 0) {
      guestCart = guestCart.filter(i => i.variant_id !== variantId);
    } else {
      const itm = guestCart.find(i => i.variant_id === variantId);
      if (itm) itm.quantity = newQty;
    }
    localStorage.setItem("soobin_guest_cart", JSON.stringify(guestCart));
    loadCartItems();
    updateCartBadge();
  }
}

// -----------------------------------------------------------------------------
// CHECKOUT & DISCOUNT CALCULATION
// -----------------------------------------------------------------------------

function openCheckoutModal() {
  if (!currentUser) {
    showToast("Vui lòng đăng nhập trước khi tiến hành thanh toán.", true);
    openAuthModal();
    return;
  }
  document.getElementById("checkoutModal").classList.remove("hidden");
  document.getElementById("orderRecipientName").value = currentUser.full_name || "";
  document.getElementById("orderRecipientPhone").value = currentUser.phone || "";
  loadSavedAddressesForCheckout();
  recalculateCheckoutDiscount();
}

function closeCheckoutModal() {
  document.getElementById("checkoutModal").classList.add("hidden");
}

async function recalculateCheckoutDiscount() {
  const voucherCode = document.getElementById("voucherCodeInput").value.trim();
  const statusEl = document.getElementById("discountCalculationStatus");

  try {
    const res = await fetch(`/api/v1/orders/calculate-discount?voucher_code=${encodeURIComponent(voucherCode)}`, {
      method: "POST"
    });
    const calc = await res.json();

    document.getElementById("breakdownSubtotal").innerText = formatCurrency(calc.original_subtotal);
    document.getElementById("breakdownDiscountAmount").innerText = `-${formatCurrency(calc.winning_discount_amount)}`;
    document.getElementById("breakdownDiscountLabel").innerText = `Giảm giá (${getDiscountLabel(calc.selected_option_type)}):`;
    document.getElementById("breakdownShippingFee").innerText = formatCurrency(30000);
    document.getElementById("breakdownTotal").innerText = formatCurrency(calc.final_subtotal + 30000);

    if (calc.winning_discount_amount > 0) {
      statusEl.innerHTML = `
        <span class="text-emerald-700 font-medium">
          ✓ Phương án giảm tốt nhất được chọn tự động: <strong>${getDiscountLabel(calc.selected_option_type)}</strong> (-${formatCurrency(calc.winning_discount_amount)}).
        </span>
      `;
    } else {
      statusEl.innerHTML = `<span class="text-slate-400">Không có chương trình giảm giá nào được áp dụng.</span>`;
    }

    const vOpt = (calc.eligible_options || []).find(o => o.option_type === "VOUCHER");
    if (voucherCode && vOpt && vOpt.error) {
      statusEl.innerHTML += `<br><span class="text-rose-500 font-semibold">${vOpt.error}</span>`;
    }
  } catch (err) {
    statusEl.innerHTML = `<span class="text-rose-500">Lỗi tính khuyến mãi.</span>`;
  }
}

function getDiscountLabel(type) {
  if (type === "PRODUCT") return "Sale trực tiếp theo sản phẩm";
  if (type === "ORDER") return "Theo tổng hóa đơn (10%)";
  if (type === "VOUCHER") return "Voucher ưu đãi";
  return "Không";
}

async function submitOrder() {
  const name = document.getElementById("orderRecipientName").value.trim();
  const phone = document.getElementById("orderRecipientPhone").value.trim();
  const address = document.getElementById("orderShippingAddress").value.trim();
  const paymentMethod = document.querySelector('input[name="paymentMethod"]:checked').value;
  const voucherCode = document.getElementById("voucherCodeInput").value.trim();
  const saveAddressEl = document.getElementById("saveAddressOnCheckout");

  if (!name || !phone || !address) {
    showToast("Vui lòng điền đầy đủ họ tên, SĐT và địa chỉ giao hàng.", true);
    return;
  }

  try {
    if (saveAddressEl && saveAddressEl.checked && currentUser) {
      await fetch("/api/v1/auth/addresses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          recipient_name: name,
          recipient_phone: phone,
          address_line: address,
          is_default: false
        })
      }).catch(() => {});
    }

    const res = await fetch("/api/v1/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        recipient_name: name,
        recipient_phone: phone,
        shipping_address: address,
        payment_method: paymentMethod,
        voucher_code: voucherCode || null
      })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.detail || "Không thể tạo đơn hàng.", true);
      return;
    }

    closeCheckoutModal();
    const drawer = document.getElementById("cartDrawer");
    const backdrop = document.getElementById("cartDrawerBackdrop");
    if (drawer && !drawer.classList.contains("translate-x-full")) {
      drawer.classList.add("translate-x-full");
      if (backdrop) backdrop.classList.add("hidden");
    }
    updateCartBadge();
    loadLoyaltySummary();

    if (typeof window.playOrderCelebrationSound === "function") {
      window.playOrderCelebrationSound();
    }

    const thankMsgEl = document.getElementById("successThankYouCustomerMsg");
    if (thankMsgEl) {
      thankMsgEl.innerHTML = `Xin chân thành cảm ơn quý khách <strong>${name}</strong> đã tin tưởng mua sắm tại <strong>Soobin Swimwear</strong>! Đơn hàng trị giá <strong>${formatCurrency(data.total_amount)}</strong> của quý khách đang được chuẩn bị chu đáo.`;
    }

    document.getElementById("successOrderCode").innerText = data.order_code;
    const ordIdEl = document.getElementById("successOrderId");
    if (ordIdEl) ordIdEl.value = data.order_id;

    const vBox = document.getElementById("vietqrBox");
    if (data.payment_instruction) {
      vBox.classList.remove("hidden");
      const pi = data.payment_instruction;
      document.getElementById("vietqrImage").src = pi.qr_url;
      document.getElementById("vietqrContent").innerText = pi.transfer_content;
      document.getElementById("vietqrAmount").innerText = formatCurrency(data.total_amount);
      const bName = document.getElementById("vietqrBankName");
      const aNo = document.getElementById("vietqrAccountNo");
      const aName = document.getElementById("vietqrAccountName");
      const bBranch = document.getElementById("vietqrBranch");
      const badge = document.getElementById("vietqrPaymentStatusBadge");
      const resMsg = document.getElementById("vietqrConfirmResultMsg");
      if (bName) bName.innerText = pi.bank_name || pi.bank_code || "MBBank";
      if (aNo) aNo.innerText = pi.account_no || "0389998888";
      if (aName) aName.innerText = pi.account_name || "SOOBIN SWIMWEAR";
      if (bBranch) bBranch.innerText = pi.bank_branch || "Chi nhánh TP. Hồ Chí Minh";
      if (badge) {
        badge.className = "px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-bold text-[10px]";
        badge.innerText = data.payment_method === "VietQR" ? "Chờ chuyển khoản" : "Hỗ trợ chuyển khoản QR";
      }
      if (resMsg) resMsg.classList.add("hidden");
    } else {
      vBox.classList.add("hidden");
    }

    document.getElementById("orderSuccessModal").classList.remove("hidden");
  } catch (err) {
    showToast("Lỗi kết nối khi gửi đơn hàng.", true);
  }
}

async function customerReportBankTransfer(autoVerifyWebhook = false, customOrderId = null) {
  const orderId = customOrderId || document.getElementById("successOrderId")?.value;
  if (!orderId) return;
  const txnInput = document.getElementById("vietqrTxnRefInput");
  const txnRef = txnInput ? txnInput.value.trim() : "";

  try {
    const res = await fetch(`/api/v1/orders/${orderId}/customer-report-transfer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        transaction_ref: txnRef || null,
        note: autoVerifyWebhook ? "Đối soát tự động qua Webhook ngân hàng" : "Khách hàng xác nhận đã chuyển khoản qua QR",
        auto_verify_webhook: !!autoVerifyWebhook
      })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.detail || "Không thể gửi xác nhận chuyển khoản.", true);
      return;
    }
    showToast(data.message);
    const badge = document.getElementById("vietqrPaymentStatusBadge");
    const resMsg = document.getElementById("vietqrConfirmResultMsg");
    if (badge) {
      if (data.payment_status === "PAID") {
        badge.className = "px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-extrabold text-[10px]";
        badge.innerText = "✓ ĐÃ THANH TOÁN";
      } else {
        badge.className = "px-2 py-0.5 rounded-full bg-sky-100 text-sky-800 font-bold text-[10px]";
        badge.innerText = "🔔 Đã báo Shop kiểm tra";
      }
    }
    if (resMsg) {
      resMsg.innerText = data.message;
      resMsg.classList.remove("hidden");
    }
    if (customOrderId) {
      viewMyOrders();
    }
  } catch (err) {
    showToast("Lỗi kết nối khi xác nhận chuyển khoản.", true);
  }
}

function openInvoiceFromSuccessModal() {
  const orderId = document.getElementById("successOrderId")?.value;
  if (!orderId) return;
  closeSuccessModal();
  openInvoiceModal(orderId);
}

function closeSuccessModal() {
  document.getElementById("orderSuccessModal").classList.add("hidden");
}

// -----------------------------------------------------------------------------
// USER ORDERS LIST, INVOICE & REVIEW
// -----------------------------------------------------------------------------

async function viewMyOrders() {
  if (!currentUser) return;
  const modal = document.getElementById("ordersModal");
  const container = document.getElementById("ordersListContainer");
  modal.classList.remove("hidden");

  container.innerHTML = `<div class="text-center py-6 text-slate-400">Đang tải lịch sử đơn hàng...</div>`;

  try {
    const res = await fetch("/api/v1/orders");
    const orders = await res.json();

    if (orders.length === 0) {
      container.innerHTML = `<div class="text-center py-8 text-slate-400">Bạn chưa có đơn hàng nào.</div>`;
      return;
    }

    container.innerHTML = orders.map(o => `
      <div class="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-3">
        <div class="flex flex-wrap items-center justify-between gap-2 border-b pb-2">
          <div>
            <span class="font-mono font-bold text-sm text-sky-700">${o.code}</span>
            <span class="text-xs text-slate-400 block">${new Date(o.placed_at).toLocaleString('vi-VN')}</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="px-2.5 py-1 text-xs font-bold rounded-full ${getStatusBadgeClass(o.status)}">
              ${o.status}
            </span>
            <span class="text-xs font-semibold text-slate-500 bg-white border px-2 py-0.5 rounded">
              ${o.payment_method} (${o.payment_status})
            </span>
          </div>
        </div>

        <div class="flex justify-between text-xs text-slate-600">
          <div>
            <p>Người nhận: <strong>${o.recipient_name}</strong> - ${o.recipient_phone}</p>
            ${o.tracking_code ? `<p class="text-emerald-700 font-semibold">Mã vận đơn GHTK: ${o.tracking_code}</p>` : ''}
            ${o.invoice_code ? `<p class="text-sky-700 font-semibold">Hóa đơn ĐT: ${o.invoice_code}</p>` : ''}
          </div>
          <div class="text-right">
            <span class="text-slate-400 block">Tổng thanh toán:</span>
            <span class="text-base font-extrabold text-slate-900">${formatCurrency(o.total_amount)}</span>
          </div>
        </div>

        ${(o.items_summary && o.items_summary.length > 0) ? `
          <div class="bg-white border border-slate-100 rounded-lg p-2.5 space-y-1.5 text-xs">
            ${o.items_summary.map(it => `
              <div class="flex items-center justify-between gap-2">
                <span class="text-slate-700 font-medium">${it.product_name} <span class="text-slate-400">(${it.color}/${it.size}) x${it.quantity}</span></span>
                <div class="flex items-center gap-2">
                  <span class="font-bold text-slate-800">${formatCurrency(it.line_total)}</span>
                  ${o.status === "Đã giao" && it.product_id ? `
                    <button onclick="openReviewModal(${o.id}, ${it.product_id}, '${(it.product_name || '').replace(/'/g, "\\'")}')" class="px-2 py-0.5 bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 rounded font-bold text-[11px] transition">
                      ★ Đánh giá
                    </button>
                  ` : ''}
                </div>
              </div>
            `).join("")}
          </div>
        ` : ''}

        <div class="flex flex-wrap justify-between items-center gap-2 pt-2 border-t border-slate-200/70">
          <!-- Visual 5-Step Order Progress Timeline -->
          <div class="flex items-center gap-1 text-[10px] font-bold">
            <span class="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800">1. Đặt đơn</span>
            <span class="text-slate-300">→</span>
            <span class="px-2 py-0.5 rounded-full ${o.payment_status === 'PAID' || o.status === 'Đã giao' ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-600'}">2. Thanh toán</span>
            <span class="text-slate-300">→</span>
            <span class="px-2 py-0.5 rounded-full ${['Đã xử lý', 'Đang vận chuyển', 'Đã giao'].includes(o.status) ? 'bg-blue-100 text-blue-800' : 'bg-slate-200 text-slate-500'}">3. Xác nhận</span>
            <span class="text-slate-300">→</span>
            <span class="px-2 py-0.5 rounded-full ${o.status === 'Đã giao' ? 'bg-emerald-600 text-white' : 'bg-slate-200 text-slate-500'}">4. Hoàn tất & Hóa đơn</span>
          </div>

          <div class="flex flex-wrap justify-end gap-2">
            <button onclick="reorderPastOrder(${o.id})" class="px-3 py-1.5 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 rounded-lg text-xs font-bold transition flex items-center gap-1">
              <i data-lucide="rotate-ccw" class="w-3.5 h-3.5"></i> Mua Lại Đơn Này
            </button>
            <button onclick="openExchangeModal(${o.id}, '${o.code}')" class="px-3 py-1.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 rounded-lg text-xs font-bold transition flex items-center gap-1">
              <i data-lucide="repeat" class="w-3.5 h-3.5"></i> Đổi Size / Bảo Hành / Trả Hàng
            </button>
            <button onclick="openInvoiceModal('${o.invoice_code || o.id}')" class="px-3 py-1.5 bg-sky-50 text-sky-700 hover:bg-sky-100 border border-sky-200 rounded-lg text-xs font-bold transition flex items-center gap-1">
              <i data-lucide="file-text" class="w-3.5 h-3.5"></i> Hóa Đơn & QR Chuyển Khoản
            </button>
            ${o.payment_status !== "PAID" && o.status === "Chưa xử lý" ? `
              <button onclick="customerReportBankTransfer(true, ${o.id})" class="px-3 py-1.5 bg-amber-50 text-amber-800 hover:bg-amber-100 border border-amber-300 rounded-lg text-xs font-bold transition">
                ⚡ Xác Nhận Đã CK
              </button>
            ` : ''}
            ${o.status === "Chưa xử lý" ? `
              <button onclick="cancelMyOrder(${o.id})" class="px-3 py-1.5 bg-rose-50 text-rose-600 hover:bg-rose-100 rounded-lg text-xs font-bold transition">
                Hủy Đơn Hàng
              </button>
            ` : ''}
          </div>
        </div>
      </div>
    `).join("");
    lucide.createIcons();
  } catch (err) {
    container.innerHTML = `<div class="text-center text-rose-500 py-6">Lỗi tải danh sách đơn hàng.</div>`;
  }
}

async function cancelMyOrder(orderId) {
  if (!(await confirmDialog("Bạn có chắc chắn muốn hủy đơn hàng này không?"))) return;
  try {
    const res = await fetch(`/api/v1/orders/${orderId}/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: "Khách hàng tự hủy đơn" })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.detail || "Không thể hủy đơn hàng.", true);
      return;
    }
    showToast(data.message);
    viewMyOrders();
  } catch (err) {
    showToast("Lỗi khi hủy đơn.", true);
  }
}

function closeOrdersModal() {
  document.getElementById("ordersModal").classList.add("hidden");
}

function getStatusBadgeClass(status) {
  switch (status) {
    case "Chưa xử lý": return "bg-amber-100 text-amber-800";
    case "Đã xử lý": return "bg-blue-100 text-blue-800";
    case "Đang vận chuyển": return "bg-indigo-100 text-indigo-800";
    case "Đã giao": return "bg-emerald-100 text-emerald-800";
    case "Đã hủy": return "bg-slate-200 text-slate-700";
    case "Chờ hoàn tiền": return "bg-rose-100 text-rose-800";
    case "Đã hoàn tiền": return "bg-purple-100 text-purple-800";
    default: return "bg-slate-100 text-slate-800";
  }
}

function formatCurrency(val) {
  return new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND" }).format(val || 0);
}

// -----------------------------------------------------------------------------
// WISHLIST & DISCOUNT NOTIFICATIONS
// -----------------------------------------------------------------------------

async function updateWishlistBadge() {
  const badge = document.getElementById("wishlistBadge");
  if (!badge) return;
  if (!currentUser) {
    wishlistProductIds = new Set();
    badge.classList.add("hidden");
    return;
  }
  try {
    const res = await fetch("/api/v1/cart/wishlist");
    if (!res.ok) return;
    const items = await res.json();
    wishlistProductIds = new Set(items.map(i => i.product_id));
    if (items.length > 0) {
      badge.innerText = items.length;
      badge.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
    }
  } catch (err) {}
}

async function toggleWishlistItem(e, productId) {
  if (e) e.stopPropagation();
  if (!currentUser) {
    showToast("Vui lòng đăng nhập để lưu sản phẩm yêu thích!", true);
    openAuthModal();
    return;
  }
  try {
    const res = await fetch(`/api/v1/cart/wishlist/toggle/${productId}`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.detail || "Không thể cập nhật yêu thích.", true);
      return;
    }
    showToast(data.message);
    await updateWishlistBadge();
    loadProducts(true);
  } catch (err) {
    showToast("Lỗi kết nối Wishlist.", true);
  }
}

async function openWishlistModal() {
  if (!currentUser) {
    showToast("Vui lòng đăng nhập để xem Danh sách yêu thích!", true);
    openAuthModal();
    return;
  }
  document.getElementById("wishlistModal").classList.remove("hidden");
  const container = document.getElementById("wishlistItemsContainer");
  container.innerHTML = `<div class="text-center py-8 text-slate-400">Đang tải danh sách yêu thích...</div>`;

  try {
    const res = await fetch("/api/v1/cart/wishlist");
    const items = await res.json();
    if (!items || items.length === 0) {
      container.innerHTML = `<div class="text-center py-10 text-slate-400">Danh sách yêu thích của bạn đang trống. Hãy nhấn biểu tượng trái tim trên sản phẩm nhé!</div>`;
      return;
    }
    container.innerHTML = items.map(item => {
      const pName = item.name || item.product_name || "Sản phẩm";
      const pSlug = item.slug || item.product_slug || item.product_id;
      const salePrice = item.sale_price || item.discounted_price || item.base_price;
      const isOnSale = item.is_on_sale || item.on_sale || (item.discount_percent > 0);
      return `
      <div class="flex items-center justify-between gap-4 p-3.5 bg-slate-50 border border-slate-200 rounded-xl hover:border-rose-200 transition">
        <div class="flex items-center gap-3">
          <img src="${item.image_url || 'https://placehold.co/100x100/e0f2fe/0369a1?text=SooBin'}" class="w-16 h-16 rounded-lg object-cover border" />
          <div>
            <h4 class="font-bold text-slate-800 text-sm cursor-pointer hover:text-sky-600" onclick="closeWishlistModal(); openProductModal('${pSlug}')">${pName}</h4>
            <div class="flex items-center gap-2 mt-1">
              <span class="font-extrabold text-rose-600 text-sm">${formatCurrency(salePrice)}</span>
              ${isOnSale ? `
                <span class="text-xs text-slate-400 line-through">${formatCurrency(item.base_price)}</span>
                <span class="px-2 py-0.5 bg-rose-100 text-rose-700 rounded-full text-[10px] font-bold">🔥 Giảm -${item.discount_percent}%</span>
              ` : ''}
            </div>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <button onclick="closeWishlistModal(); openProductModal('${pSlug}')" class="px-3 py-1.5 bg-sky-600 hover:bg-sky-700 text-white text-xs font-bold rounded-lg transition">
            Chọn mua
          </button>
          <button onclick="removeWishlistItem(${item.product_id})" class="p-1.5 text-slate-400 hover:text-rose-600">
            <i data-lucide="trash-2" class="w-4 h-4"></i>
          </button>
        </div>
      </div>
    `;
    }).join("");
    lucide.createIcons();
  } catch (err) {
    container.innerHTML = `<div class="text-center py-6 text-rose-500">Lỗi tải danh sách yêu thích.</div>`;
  }
}

function closeWishlistModal() {
  document.getElementById("wishlistModal").classList.add("hidden");
}

async function removeWishlistItem(productId) {
  await fetch(`/api/v1/cart/wishlist/${productId}`, { method: "DELETE" });
  await updateWishlistBadge();
  openWishlistModal();
  loadProducts(true);
}

async function checkWishlistDiscounts() {
  try {
    const res = await fetch("/api/v1/cart/wishlist/check-discounts");
    const data = await res.json();
    if (data.discounted_count > 0) {
      showToast(`🎉 Tuyệt vời! Có ${data.discounted_count} sản phẩm trong mục Yêu thích của bạn đang giảm giá!`);
    } else {
      showToast("Hiện chưa có chương trình giảm giá mới cho các sản phẩm trong danh sách yêu thích.");
    }
    openWishlistModal();
  } catch (err) {
    showToast("Không thể kiểm tra khuyến mãi lúc này.", true);
  }
}

// -----------------------------------------------------------------------------
// USER ADDRESS BOOK
// -----------------------------------------------------------------------------

let cachedUserAddresses = [];

function openAddressBookModal() {
  if (!currentUser) return;
  document.getElementById("addressBookModal").classList.remove("hidden");
  loadAddressBook();
}

function closeAddressBookModal() {
  document.getElementById("addressBookModal").classList.add("hidden");
}

async function loadAddressBook() {
  const container = document.getElementById("addressBookList");
  if (!container) return;
  try {
    const res = await fetch("/api/v1/auth/addresses");
    cachedUserAddresses = await res.json();
    if (!cachedUserAddresses.length) {
      container.innerHTML = `<div class="text-center py-6 text-slate-400 text-xs">Chưa có địa chỉ giao hàng nào được lưu.</div>`;
      return;
    }
    container.innerHTML = cachedUserAddresses.map(a => `
      <div class="p-3 bg-white border border-slate-200 rounded-xl flex items-center justify-between gap-3">
        <div class="text-xs space-y-0.5">
          <div class="flex items-center gap-2">
            <span class="font-bold text-slate-800">${a.recipient_name}</span>
            <span class="text-slate-500">${a.recipient_phone}</span>
            ${a.is_default ? `<span class="px-2 py-0.5 bg-sky-100 text-sky-700 font-bold text-[10px] rounded-full">Mặc định</span>` : ''}
          </div>
          <p class="text-slate-600">${a.address_line}</p>
        </div>
        <button onclick="deleteAddress(${a.id})" class="text-rose-500 hover:text-rose-700 text-xs font-bold px-2 py-1">Xóa</button>
      </div>
    `).join("");
  } catch (err) {
    container.innerHTML = `<div class="text-rose-500 text-xs">Lỗi tải sổ địa chỉ.</div>`;
  }
}

async function handleAddAddress(e) {
  e.preventDefault();
  const recipient_name = document.getElementById("addrRecipientName").value.trim();
  const recipient_phone = document.getElementById("addrRecipientPhone").value.trim();
  const address_line = document.getElementById("addrLine").value.trim();
  const is_default = document.getElementById("addrIsDefault").checked;

  try {
    const res = await fetch("/api/v1/auth/addresses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ recipient_name, recipient_phone, address_line, is_default })
    });
    if (!res.ok) {
      const err = await res.json();
      showToast(err.detail || "Lỗi thêm địa chỉ.", true);
      return;
    }
    showToast("Đã lưu địa chỉ vào sổ địa chỉ!");
    document.getElementById("addrLine").value = "";
    loadAddressBook();
    loadSavedAddressesForCheckout();
  } catch (err) {
    showToast("Lỗi kết nối máy chủ.", true);
  }
}

async function deleteAddress(addrId) {
  await fetch(`/api/v1/auth/addresses/${addrId}`, { method: "DELETE" });
  showToast("Đã xóa địa chỉ.");
  loadAddressBook();
}

async function loadSavedAddressesForCheckout() {
  const select = document.getElementById("savedAddressSelect");
  if (!select || !currentUser) return;
  try {
    const res = await fetch("/api/v1/auth/addresses");
    cachedUserAddresses = await res.json();
    select.innerHTML = `<option value="">-- Nhập địa chỉ mới hoặc chọn từ sổ địa chỉ --</option>` +
      cachedUserAddresses.map(a => `<option value="${a.id}" ${a.is_default ? 'selected' : ''}>${a.recipient_name} - ${a.recipient_phone} (${a.address_line})</option>`).join("");
    const def = cachedUserAddresses.find(a => a.is_default);
    if (def) {
      document.getElementById("orderRecipientName").value = def.recipient_name;
      document.getElementById("orderRecipientPhone").value = def.recipient_phone;
      document.getElementById("orderShippingAddress").value = def.address_line;
    }
  } catch (err) {}
}

function applySelectedAddress() {
  const select = document.getElementById("savedAddressSelect");
  if (!select) return;
  const addrId = Number(select.value);
  const found = cachedUserAddresses.find(a => a.id === addrId);
  if (found) {
    document.getElementById("orderRecipientName").value = found.recipient_name;
    document.getElementById("orderRecipientPhone").value = found.recipient_phone;
    document.getElementById("orderShippingAddress").value = found.address_line;
  }
}

// -----------------------------------------------------------------------------
// PRINTABLE ELECTRONIC INVOICE MODAL
// -----------------------------------------------------------------------------

async function openInvoiceModal(codeOrId) {
  const modal = document.getElementById("invoiceModal");
  const body = document.getElementById("invoicePrintableArea");
  modal.classList.remove("hidden");
  body.innerHTML = `<div class="text-center py-8 text-slate-400">Đang tải hóa đơn điện tử...</div>`;

  try {
    const res = await fetch(`/api/v1/orders/invoices/${encodeURIComponent(codeOrId)}`);
    const inv = await res.json();
    if (!res.ok) {
      body.innerHTML = `<div class="text-center py-8 text-rose-500">${inv.detail || 'Không tìm thấy hóa đơn.'}</div>`;
      return;
    }

    const custName = inv.customer_name || inv.customer_snapshot?.name || "";
    const custPhone = inv.customer_phone || inv.customer_snapshot?.phone || "";
    const custAddr = inv.shipping_address || inv.customer_snapshot?.address || "";
    const bank = inv.bank_account || inv.store_snapshot?.bank_account || {};
    const policy = inv.after_sales_policy || inv.store_snapshot?.after_sales_policy || {};
    const isPaid = (inv.payment_status || "PAID") === "PAID";

    body.innerHTML = `
      <div class="border-2 border-slate-800 p-6 rounded-xl bg-white space-y-5 text-slate-800">
        <div class="flex justify-between items-start border-b-2 border-slate-800 pb-4">
          <div>
            <h2 class="text-xl font-black tracking-tight text-sky-800">SOOBIN SWIMWEAR ATELIER CO., LTD</h2>
            <p class="text-xs text-slate-500">Hệ Thống Thương Mại Điện Tử Thời Trang Đồ Bơi Cao Cấp</p>
            <p class="text-xs text-slate-500">Hotline: 1900 8866 • Website: soobinswimwear.vn</p>
          </div>
          <div class="text-right">
            <span class="px-2.5 py-1 ${isPaid ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'} font-bold text-xs rounded">
              ${isPaid ? 'HÓA ĐƠN ĐIỆN TỬ (ĐÃ THANH TOÁN)' : 'HÓA ĐƠN & PHIẾU THANH TOÁN QR'}
            </span>
            <p class="font-mono font-bold text-sm mt-1">${inv.code || inv.invoice_code}</p>
            <p class="text-xs text-slate-500">Ngày xuất: ${new Date(inv.issued_at).toLocaleString('vi-VN')}</p>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4 text-xs bg-slate-50 p-3.5 rounded-lg border">
          <div>
            <p class="text-slate-400 uppercase font-bold text-[10px]">Khách hàng / Người nhận</p>
            <p class="font-bold text-sm text-slate-800 mt-0.5">${custName}</p>
            <p>SĐT: ${custPhone}</p>
            <p>Địa chỉ: ${custAddr}</p>
          </div>
          <div class="text-right">
            <p class="text-slate-400 uppercase font-bold text-[10px]">Thông tin đơn hàng</p>
            <p class="font-mono font-bold text-sky-700 mt-0.5">Mã đơn: ${inv.order_code}</p>
            <p>Phương thức TT: <strong>${inv.payment_method}</strong></p>
            <p>Trạng thái TT: <strong class="${isPaid ? 'text-emerald-700' : 'text-amber-700'}">${inv.payment_status || 'PAID'}</strong></p>
          </div>
        </div>

        <table class="w-full text-left border-collapse text-xs">
          <thead>
            <tr class="border-b-2 border-slate-300 text-slate-600 uppercase">
              <th class="py-2">Sản phẩm</th>
              <th class="py-2">Phân loại</th>
              <th class="py-2 text-center">SL</th>
              <th class="py-2 text-right">Đơn giá</th>
              <th class="py-2 text-right">Thành tiền</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-200">
            ${(inv.items || []).map(it => `
              <tr>
                <td class="py-2.5 font-semibold">${it.product_name}</td>
                <td class="py-2.5 text-slate-500">${it.color || '-'} / ${it.size || '-'} (${it.sku || ''})</td>
                <td class="py-2.5 text-center font-bold">${it.quantity}</td>
                <td class="py-2.5 text-right">${formatCurrency(it.unit_price)}</td>
                <td class="py-2.5 text-right font-bold">${formatCurrency(it.line_total)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>

        <div class="border-t-2 border-slate-800 pt-3 space-y-1 text-xs">
          <div class="flex justify-between">
            <span class="text-slate-500">Tạm tính hàng hóa:</span>
            <span class="font-semibold">${formatCurrency(inv.subtotal)}</span>
          </div>
          <div class="flex justify-between text-emerald-700">
            <span>Chiết khấu / Khuyến mãi:</span>
            <span class="font-semibold">-${formatCurrency(inv.discount_amount)}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-slate-500">Phí vận chuyển:</span>
            <span class="font-semibold">${formatCurrency(inv.shipping_fee)}</span>
          </div>
          <div class="flex justify-between text-base font-black text-slate-900 pt-1 border-t">
            <span>TỔNG CỘNG THANH TOÁN:</span>
            <span class="text-sky-700">${formatCurrency(inv.total_amount)}</span>
          </div>
        </div>

        <!-- Shop Owner Bank Account & Order-Specific VietQR Section -->
        ${bank && bank.account_no ? `
          <div class="bg-sky-50/70 border border-sky-200 rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div class="space-y-1 text-xs flex-1">
              <div class="flex items-center gap-2">
                <span class="px-2 py-0.5 rounded bg-sky-600 text-white font-extrabold text-[10px] uppercase">Tài Khoản Nhận Chuyển Khoản Của Shop</span>
                <span class="text-[11px] font-bold ${isPaid ? 'text-emerald-700' : 'text-amber-700'}">
                  ${isPaid ? '✓ Đã nhận thanh toán đủ' : '• Quét mã QR bên cạnh để chuyển đúng số tiền hóa đơn'}
                </span>
              </div>
              <p class="pt-1">Ngân hàng thụ hưởng: <strong class="text-slate-900">${bank.bank_name || bank.bank_code}</strong> ${bank.bank_branch ? `(${bank.bank_branch})` : ''}</p>
              <p>Số tài khoản: <strong class="font-mono text-sm text-sky-700">${bank.account_no}</strong></p>
              <p>Chủ tài khoản: <strong class="text-slate-900">${bank.account_name}</strong></p>
              <p>Số tiền theo hóa đơn: <strong class="text-rose-600 font-extrabold">${formatCurrency(inv.total_amount)}</strong></p>
              <p>Nội dung chuyển khoản: <strong class="font-mono bg-white border border-sky-200 px-1.5 py-0.5 rounded text-rose-700">${bank.transfer_content || inv.order_code}</strong></p>
              ${!isPaid ? `
                <div class="pt-2 flex flex-wrap gap-2">
                  <button type="button" onclick="customerReportBankTransfer(false, ${inv.order_id}); openInvoiceModal('${inv.code}');" class="px-3 py-1.5 bg-sky-600 hover:bg-sky-700 text-white font-bold rounded-lg text-[11px]">
                    📨 Báo Shop Đã Chuyển Khoản
                  </button>
                  <button type="button" onclick="customerReportBankTransfer(true, ${inv.order_id}); setTimeout(() => openInvoiceModal('${inv.code}'), 400);" class="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-lg text-[11px]">
                    ⚡ Ngân Hàng Báo Có Tự Động (Auto-Verify)
                  </button>
                </div>
              ` : ''}
            </div>
            ${bank.qr_url ? `
              <div class="text-center shrink-0">
                <img src="${bank.qr_url}" alt="VietQR Hóa đơn" class="w-32 h-32 rounded-xl border-2 border-sky-200 bg-white p-1 shadow-sm mx-auto object-contain">
                <span class="text-[10px] font-bold text-slate-500 block mt-1">VietQR Tự Động Theo Giá Đơn</span>
              </div>
            ` : ''}
          </div>
        ` : ''}

        <!-- Warranty / Exchange / Return Policy Summary on Invoice -->
        <div class="bg-slate-50 border border-slate-200 rounded-xl p-3 text-[11px] text-slate-600 space-y-1">
          <div class="font-bold text-slate-800">🛡️ Chính sách Bảo hành & Đổi trả áp dụng cho Hóa đơn này:</div>
          <p>• Đổi Size / Đổi mẫu: <strong>Trong vòng ${policy.exchange_size_window_days ?? 15} ngày</strong> | Trả hàng / Hoàn tiền: <strong>Trong vòng ${policy.return_window_days ?? 7} ngày</strong> | Bảo hành sản phẩm: <strong>${policy.warranty_window_days ?? 90} ngày</strong>.</p>
          <p>• Bộ phận tiếp nhận hỗ trợ: <strong>Trung Tâm Chăm Sóc Khách Hàng & Bảo Hành Soobin Swimwear (Hotline 1900 8866)</strong>.</p>
        </div>

        <div class="text-center text-[11px] text-slate-400 pt-2 border-t border-dashed">
          Cảm ơn quý khách đã mua sắm tại Soobin Swimwear Atelier! Hóa đơn điện tử có giá trị đối chiếu và bảo hành chính hãng.
        </div>
      </div>
    `;
  } catch (err) {
    body.innerHTML = `<div class="text-center py-8 text-rose-500">Lỗi tải hóa đơn điện tử.</div>`;
  }
}

function closeInvoiceModal() {
  document.getElementById("invoiceModal").classList.add("hidden");
}

function printInvoiceContent() {
  const content = document.getElementById("invoicePrintableArea").innerHTML;
  const win = window.open("", "_blank", "width=800,height=700");
  win.document.write(`
    <html>
      <head>
        <title>In Hóa Đơn Điện Tử - Soobin Swimwear</title>
        <script src="https://cdn.tailwindcss.com"></script>
      </head>
      <body class="p-8" onload="window.print()">${content}</body>
    </html>
  `);
  win.document.close();
}

// -----------------------------------------------------------------------------
// PRODUCT REVIEW SUBMISSION & STYLIST FEEDBACK
// -----------------------------------------------------------------------------

function openReviewModal(orderId, productId, productName) {
  document.getElementById("reviewOrderId").value = orderId;
  document.getElementById("reviewProductId").value = productId;
  document.getElementById("reviewModalProductName").innerText = productName;
  document.getElementById("reviewRating").value = "5";
  document.getElementById("reviewContent").value = "";
  document.getElementById("reviewModal").classList.remove("hidden");
}

function closeReviewModal() {
  document.getElementById("reviewModal").classList.add("hidden");
}

async function submitProductReviewForm(e) {
  e.preventDefault();
  const order_id = Number(document.getElementById("reviewOrderId").value);
  const productId = Number(document.getElementById("reviewProductId").value);
  const rating = Number(document.getElementById("reviewRating").value);
  const content = document.getElementById("reviewContent").value.trim();

  try {
    const res = await fetch(`/api/v1/catalog/products/${productId}/reviews`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ order_id, rating, content })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.detail || "Không thể gửi đánh giá.", true);
      return;
    }
    showToast("Cảm ơn bạn đã đánh giá sản phẩm!");
    closeReviewModal();
    loadProducts(true);
  } catch (err) {
    showToast("Lỗi kết nối khi gửi đánh giá.", true);
  }
}

function openStylistModal() {
  if (currentUser) {
    document.getElementById("fbSenderName").value = currentUser.full_name || "";
    document.getElementById("fbSenderEmail").value = currentUser.email || "";
  }
  document.getElementById("stylistModal").classList.remove("hidden");
}

function closeStylistModal() {
  document.getElementById("stylistModal").classList.add("hidden");
}

async function submitStylistFeedback(e) {
  e.preventDefault();
  const sender_name = document.getElementById("fbSenderName").value.trim();
  const sender_email = document.getElementById("fbSenderEmail").value.trim();
  const message = document.getElementById("fbMessage").value.trim();

  try {
    const res = await fetch("/api/v1/site-settings/feedbacks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sender_name, sender_email, message })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.detail || "Không thể gửi yêu cầu.", true);
      return;
    }
    showToast(data.message);
    document.getElementById("fbMessage").value = "";
    closeStylistModal();
  } catch (err) {
    showToast("Lỗi kết nối máy chủ.", true);
  }
}

// -----------------------------------------------------------------------------
// AI SWIMWEAR & SIZE ADVISOR CHATBOX
// -----------------------------------------------------------------------------

function toggleAIChatbox(forceOpen = null) {
  const panel = document.getElementById("aiChatPanel");
  if (!panel) return;
  if (forceOpen === true) {
    panel.classList.remove("hidden");
  } else if (forceOpen === false) {
    panel.classList.add("hidden");
  } else {
    panel.classList.toggle("hidden");
  }
}

function sendQuickAIPrompt(text) {
  document.getElementById("aiChatInput").value = text;
  handleAIChatSubmit(new Event("submit"));
}

async function handleAIChatSubmit(e) {
  if (e && e.preventDefault) e.preventDefault();
  const input = document.getElementById("aiChatInput");
  const msg = input.value.trim();
  const hVal = document.getElementById("aiHeight")?.value;
  const wVal = document.getElementById("aiWeight")?.value;
  const bVal = document.getElementById("aiBust")?.value;
  const gVal = document.getElementById("aiGender")?.value;

  if (!msg && (!hVal || !wVal)) {
    showToast("Hãy nhập câu hỏi hoặc điền chiều cao & cân nặng để AI tư vấn nhé!", true);
    return;
  }

  const messagesBox = document.getElementById("aiChatMessages");
  const userLabel = msg || `Tư vấn giúp mình: Cao ${hVal}cm, nặng ${wVal}kg (${gVal || 'Nữ'})`;
  messagesBox.innerHTML += `
    <div class="flex justify-end">
      <div class="bg-sky-600 text-white px-3 py-2 rounded-2xl rounded-tr-none text-xs max-w-[85%] shadow-sm">
        ${userLabel}
      </div>
    </div>
  `;
  input.value = "";
  messagesBox.scrollTop = messagesBox.scrollHeight;

  try {
    const res = await fetch("/api/v1/catalog/ai-advisor", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: userLabel,
        height_cm: hVal ? Number(hVal) : null,
        weight_kg: wVal ? Number(wVal) : null,
        bust_cm: bVal ? Number(bVal) : null,
        gender: gVal || null
      })
    });
    const data = await res.json();

    const recsHtml = (data.suggested_products || []).map(p => `
      <div onclick="openProductModal('${p.slug || p.id}')" class="flex items-center justify-between gap-2 p-2 bg-sky-50 hover:bg-sky-100 border border-sky-200 rounded-lg cursor-pointer transition mt-1.5">
        <div class="flex items-center gap-2 min-w-0">
          <img src="${p.image_url}" class="w-8 h-8 rounded object-cover">
          <div class="min-w-0">
            <p class="font-bold text-slate-800 text-[11px] truncate">${p.name}</p>
            <p class="text-[10px] text-slate-500">Tồn: ${p.total_stock || 'Sẵn hàng'}</p>
          </div>
        </div>
        <span class="font-extrabold text-sky-700 text-xs whitespace-nowrap">${formatCurrency(p.discounted_price || p.base_price)}</span>
      </div>
    `).join("");

    messagesBox.innerHTML += `
      <div class="flex justify-start">
        <div class="bg-white border border-slate-200 text-slate-700 px-3.5 py-2.5 rounded-2xl rounded-tl-none text-xs max-w-[92%] shadow-sm space-y-1.5">
          ${data.recommended_size ? `<div class="inline-block px-2 py-0.5 bg-emerald-100 text-emerald-800 font-extrabold rounded text-[11px]">Size đề xuất: ${data.recommended_size}</div>` : ''}
          <p class="leading-relaxed whitespace-pre-line">${data.reply}</p>
          ${recsHtml ? `<div class="pt-1 border-t border-slate-100"><span class="text-[10px] font-bold uppercase text-sky-700">Sản phẩm gợi ý cho bạn:</span>${recsHtml}</div>` : ''}
        </div>
      </div>
    `;
    messagesBox.scrollTop = messagesBox.scrollHeight;
  } catch (err) {
    messagesBox.innerHTML += `
      <div class="text-xs text-rose-500 bg-rose-50 p-2 rounded-lg">Không thể kết nối AI Advisor lúc này.</div>
    `;
  }
}

// =============================================================================
// INTERACTIVE 3D SPATIAL PRODUCT VIEWER (WEBGL THREE.JS + 3D HOLOGRAM + BODY-FIT)
// =============================================================================

let spatial3dState = {
  product: null,
  mode: "webgl", // webgl | hologram | bodyfit
  rotX: 8,
  rotY: -22,
  zoom: 1.0,
  autoRotate: true,
  isDragging: false,
  lastX: 0,
  lastY: 0,
  activeColorHex: "#0284c7",
  activeColorName: "Xanh Đại Dương",
  activeLightPreset: "ocean-daylight",
  selectedVariantId: null,
  bodyHeight: 165,
  bodyWeight: 54,
  animFrameId: null,
  threeScene: null,
  threeCamera: null,
  threeRenderer: null,
  threeGroup: null,
  threeGarmentMats: [],
  threeAmbientLight: null,
  threeDirLight: null
};

async function openSpatial3DModal(slugOrId, evt) {
  if (evt) evt.stopPropagation();
  const modal = document.getElementById("spatial3dModal");
  const body = document.getElementById("spatial3dModalBody");
  if (!modal || !body) return;

  modal.classList.remove("hidden");
  body.innerHTML = `
    <div class="py-20 text-center text-cyan-300 space-y-3">
      <i data-lucide="rotate-3d" class="w-10 h-10 animate-spin mx-auto"></i>
      <p class="text-sm font-bold">Đang dựng mô hình không gian 3 chiều (360° Spatial Mesh)...</p>
    </div>
  `;
  lucide.createIcons();

  try {
    const res = await fetch(`/api/v1/catalog/products/${slugOrId}`);
    if (!res.ok) throw new Error();
    const prod = await res.json();

    const sp = prod.spatial_3d || {};
    const firstVar = prod.variants.find(v => v.available_quantity > 0) || prod.variants[0];
    const palettes = sp.color_palettes && sp.color_palettes.length > 0
      ? sp.color_palettes
      : [{ color_id: 1, color_name: "Xanh Đại Dương", color_hex: "#0284c7", available_quantity: 10 }];

    spatial3dState.product = prod;
    spatial3dState.mode = "webgl";
    spatial3dState.rotX = 10;
    spatial3dState.rotY = -20;
    spatial3dState.zoom = 1.0;
    spatial3dState.autoRotate = true;
    spatial3dState.selectedVariantId = firstVar ? firstVar.id : null;
    spatial3dState.activeColorHex = (firstVar && firstVar.color_hex) ? firstVar.color_hex : palettes[0].color_hex;
    spatial3dState.activeColorName = (firstVar && firstVar.color_name) ? firstVar.color_name : palettes[0].color_name;
    spatial3dState.bodyHeight = (sp.fit_simulation && sp.fit_simulation.default_height_cm) || 165;
    spatial3dState.bodyWeight = (sp.fit_simulation && sp.fit_simulation.default_weight_kg) || 54;

    document.getElementById("spatial3dModalTitle").innerText = `🌐 Phòng Không Gian 3D — ${prod.name}`;

    renderSpatial3DModalContent();
  } catch (err) {
    body.innerHTML = `<div class="py-12 text-center text-rose-400">Không thể tải dữ liệu 3D của sản phẩm.</div>`;
  }
}

function closeSpatial3DModal() {
  if (spatial3dState.engineViewer) {
    try { spatial3dState.engineViewer.destroy(); } catch (e) {}
    spatial3dState.engineViewer = null;
  }
  if (spatial3dState.animFrameId) {
    cancelAnimationFrame(spatial3dState.animFrameId);
    spatial3dState.animFrameId = null;
  }
  if (spatial3dState.threeRenderer) {
    try { spatial3dState.threeRenderer.dispose(); } catch (e) {}
    spatial3dState.threeRenderer = null;
  }
  const modal = document.getElementById("spatial3dModal");
  if (modal) modal.classList.add("hidden");
}

function renderSpatial3DModalContent() {
  const prod = spatial3dState.product;
  if (!prod) return;
  const sp = prod.spatial_3d || {};
  const physics = sp.material_physics || {};
  const hotspots = sp.spatial_hotspots || [];
  const palettes = sp.color_palettes || [];
  const imgUrl = (prod.images && prod.images[0]) ? prod.images[0].file_path : "/static/images/placeholder.webp";

  const body = document.getElementById("spatial3dModalBody");
  body.innerHTML = `
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      <!-- Left 8 Cols: 3D Interactive Spatial Stage -->
      <div class="lg:col-span-8 space-y-3">
        <!-- Top 3D Mode Switcher & Environment Lighting -->
        <div class="flex flex-wrap items-center justify-between gap-2 bg-slate-950/80 p-2.5 rounded-2xl border border-slate-800">
          <div class="flex flex-wrap items-center gap-1.5">
            <button onclick="switchSpatial3DMode('webgl')" id="btn3dMode-webgl"
                    class="px-3 py-1.5 rounded-xl text-xs font-extrabold transition flex items-center gap-1.5 ${spatial3dState.mode === 'webgl' ? 'bg-cyan-500 text-slate-950 shadow-lg shadow-cyan-500/25' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}">
              <i data-lucide="box" class="w-3.5 h-3.5"></i> Mô Hình 3D WebGL (360°)
            </button>
            <button onclick="switchSpatial3DMode('hologram')" id="btn3dMode-hologram"
                    class="px-3 py-1.5 rounded-xl text-xs font-extrabold transition flex items-center gap-1.5 ${spatial3dState.mode === 'hologram' ? 'bg-cyan-500 text-slate-950 shadow-lg shadow-cyan-500/25' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}">
              <i data-lucide="layers" class="w-3.5 h-3.5"></i> Tách Lớp Không Gian 3D
            </button>
            <button onclick="switchSpatial3DMode('bodyfit')" id="btn3dMode-bodyfit"
                    class="px-3 py-1.5 rounded-xl text-xs font-extrabold transition flex items-center gap-1.5 ${spatial3dState.mode === 'bodyfit' ? 'bg-cyan-500 text-slate-950 shadow-lg shadow-cyan-500/25' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}">
              <i data-lucide="user-check" class="w-3.5 h-3.5"></i> Mô Phỏng Dáng Người 3D
            </button>
          </div>

          <!-- Environment Lighting Selector -->
          <div class="flex items-center gap-1 text-[11px]">
            <span class="text-slate-400 font-semibold mr-1 hidden sm:inline">Ánh sáng 3D:</span>
            <button onclick="setSpatialLighting('ocean-daylight')" class="px-2 py-1 rounded-lg bg-sky-950/90 border border-sky-500/40 text-sky-300 hover:bg-sky-900 font-bold" title="Nắng Biển Địa Trung Hải">☀️ Biển</button>
            <button onclick="setSpatialLighting('ibiza-sunset')" class="px-2 py-1 rounded-lg bg-amber-950/90 border border-amber-500/40 text-amber-300 hover:bg-amber-900 font-bold" title="Hoàng Hôn Ibiza">🌅 Hoàng hôn</button>
            <button onclick="setSpatialLighting('neon-runway')" class="px-2 py-1 rounded-lg bg-purple-950/90 border border-purple-500/40 text-purple-300 hover:bg-purple-900 font-bold" title="Sàn Diễn Đêm Neon">💜 Neon</button>
            <button onclick="setSpatialLighting('studio-pure')" class="px-2 py-1 rounded-lg bg-slate-800 border border-slate-600 text-white hover:bg-slate-700 font-bold" title="Studio Chuẩn Màu">💡 Studio</button>
          </div>
        </div>

        <!-- Main 3D Viewport Stage -->
        <div id="spatialViewportContainer"
             class="spatial-stage-viewport relative h-[430px] sm:h-[490px] w-full rounded-3xl overflow-hidden border border-cyan-500/30 bg-gradient-to-b from-slate-950 via-sky-950/60 to-slate-950 flex items-center justify-center cursor-grab active:cursor-grabbing shadow-inner">

          <!-- Dynamic Ambient Glow Backdrop -->
          <div id="spatialStageBackdropGlow" class="absolute inset-0 pointer-events-none opacity-60 transition-all duration-700"
               style="background: radial-gradient(circle at 50% 45%, ${spatial3dState.activeColorHex}55 0%, rgba(8, 145, 178, 0.18) 45%, transparent 75%);"></div>

          <!-- 1. Three.js WebGL 3D Canvas Layer -->
          <canvas id="threeSpatialCanvas" class="w-full h-full block ${spatial3dState.mode === 'hologram' ? 'hidden' : ''}"></canvas>

          <!-- 2. Multi-Layer CSS 3D Spatial Hologram Stage -->
          <div id="hologramSpatialStage" class="${spatial3dState.mode === 'hologram' ? 'flex' : 'hidden'} w-full h-full items-center justify-center relative">
            <div id="hologramRig" class="spatial-hologram-rig relative w-72 h-80 sm:w-80 sm:h-96 flex items-center justify-center">
              <!-- Back Depth Grid Layer (Z = -75px) -->
              <div class="spatial-layer-back absolute inset-0 rounded-3xl border border-cyan-400/30 bg-gradient-to-br from-sky-900/40 via-slate-900/60 to-cyan-900/40 backdrop-blur-md p-4 flex flex-col justify-between pointer-events-none">
                <div class="flex justify-between items-center text-[10px] font-mono text-cyan-300/80">
                  <span>Z-DEPTH: -75mm</span>
                  <span>HYDRO-GRID 3D</span>
                </div>
                <div class="border-t border-dashed border-cyan-500/20 pt-2 text-[10px] text-sky-200/70 font-mono">
                  ${physics.fabric || 'Carvico Italian Lycra XtraLife'}
                </div>
              </div>

              <!-- 3D Turntable Pedestal Floor Ring (Rotated X 76deg) -->
              <div class="spatial-layer-pedestal absolute -bottom-12 w-72 h-72 rounded-full border-2 border-cyan-400/50 bg-cyan-500/10 flex items-center justify-center pointer-events-none pedestal-ring-glow shadow-[0_0_50px_rgba(6,182,212,0.4)]">
                <div class="w-52 h-52 rounded-full border border-dashed border-sky-300/40 flex items-center justify-center text-[10px] font-mono text-cyan-300">
                  360° SPATIAL ORBIT
                </div>
              </div>

              <!-- Middle Garment Cutout Layer (Z = +38px) -->
              <div class="spatial-layer-garment relative w-60 h-72 sm:w-64 sm:h-80 rounded-2xl overflow-hidden border-2 border-white/30 shadow-2xl group">
                <img id="hologramProductImg" src="${imgUrl}" alt="${prod.name}" class="w-full h-full object-cover">
                <div id="hologramColorOverlay" class="absolute inset-0 mix-blend-color opacity-35 transition-colors duration-300" style="background-color: ${spatial3dState.activeColorHex};"></div>
                <div class="absolute inset-x-0 bottom-0 p-2.5 bg-gradient-to-t from-slate-950/90 to-transparent text-white text-xs font-bold">
                  <span class="text-[10px] text-cyan-300 block uppercase">${prod.code} • MÀU: ${spatial3dState.activeColorName}</span>
                  <span class="truncate block">${prod.name}</span>
                </div>
              </div>

              <!-- Front Floating 3D Technical Hotspots Layer (Z = +88px) -->
              <div class="spatial-layer-front absolute inset-0 pointer-events-none">
                ${hotspots.map((hs, idx) => {
                  const posStyles = [
                    "top-4 -left-10",
                    "top-14 -right-12",
                    "bottom-16 -left-12",
                    "bottom-6 -right-10"
                  ][idx % 4];
                  return `
                    <div onclick="showHotspotDetail('${hs.title.replace(/'/g, "\\'")}', '${hs.detail.replace(/'/g, "\\'")}')"
                         class="pointer-events-auto cursor-pointer absolute ${posStyles} px-2.5 py-1.5 rounded-xl bg-slate-950/90 border border-cyan-400/60 text-white shadow-xl hover:scale-110 hover:bg-cyan-950 transition flex items-center gap-1.5">
                      <span class="w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
                      <span class="text-[10px] font-extrabold text-cyan-200 whitespace-nowrap">${hs.badge}</span>
                    </div>
                  `;
                }).join("")}
              </div>
            </div>
          </div>

          <!-- Top-Left Live 3D Telemetry HUD -->
          <div class="absolute top-3 left-3 pointer-events-none bg-slate-950/75 backdrop-blur-md border border-slate-800 rounded-2xl px-3 py-2 text-[11px] space-y-0.5">
            <div class="flex items-center gap-2 text-cyan-300 font-mono font-bold">
              <span id="hudAnglesText">Góc 3D: X: 10° | Y: -20° | Zoom: 100%</span>
            </div>
            <div class="text-[10px] text-slate-400">
              Màu đang chọn: <strong id="hudColorName" class="text-white">${spatial3dState.activeColorName}</strong>
            </div>
          </div>

          <!-- Hotspot Detail Banner -->
          <div id="spatialHotspotBanner" class="absolute top-3 right-3 max-w-xs bg-slate-950/90 backdrop-blur-md border border-cyan-500/40 rounded-2xl p-3 text-xs hidden">
            <div class="font-extrabold text-cyan-300 flex items-center justify-between gap-2">
              <span id="hotspotBannerTitle">Công nghệ 3D</span>
              <button onclick="document.getElementById('spatialHotspotBanner').classList.add('hidden')" class="text-slate-400 hover:text-white">✕</button>
            </div>
            <p id="hotspotBannerDetail" class="text-[11px] text-slate-300 mt-1 leading-relaxed"></p>
          </div>

          <!-- Bottom Interactive 3D Controls Bar -->
          <div class="absolute bottom-3 inset-x-3 flex flex-wrap items-center justify-between gap-2 bg-slate-950/85 backdrop-blur-md border border-slate-800/90 px-3.5 py-2 rounded-2xl text-xs">
            <div class="flex items-center gap-2">
              <button onclick="toggleSpatialAutoRotate()" id="btnAutoRotate3D" class="px-2.5 py-1 rounded-lg bg-cyan-500/20 border border-cyan-400/40 text-cyan-300 font-bold hover:bg-cyan-500/30 transition flex items-center gap-1">
                <i data-lucide="RefreshCw" class="w-3.5 h-3.5"></i> <span>Tự xoay 360°: BẬT</span>
              </button>
              <button onclick="resetSpatialCamera()" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold transition">
                Đặt lại góc nhìn
              </button>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-[11px] text-slate-400">Thu phóng 3D:</span>
              <input type="range" id="spatialZoomSlider" min="65" max="165" value="100" oninput="updateSpatialZoom(this.value)" class="w-24 accent-cyan-400 cursor-pointer">
            </div>
          </div>
        </div>

        <!-- 3D Body-Fit Visualizer Bar (Interactive Height & Weight Morphing) -->
        <div class="bg-slate-950/90 border border-slate-800 rounded-2xl p-3.5 grid grid-cols-1 sm:grid-cols-3 gap-4 items-center">
          <div>
            <div class="flex justify-between text-xs font-bold mb-1">
              <span class="text-slate-400">Chiều cao mô phỏng:</span>
              <span id="fitHeightLabel" class="text-cyan-300 font-mono">${spatial3dState.bodyHeight} cm</span>
            </div>
            <input type="range" min="145" max="190" value="${spatial3dState.bodyHeight}" oninput="updateBodyFitSimulation(this.value, null)" class="w-full accent-cyan-400 cursor-pointer">
          </div>
          <div>
            <div class="flex justify-between text-xs font-bold mb-1">
              <span class="text-slate-400">Cân nặng mô phỏng:</span>
              <span id="fitWeightLabel" class="text-cyan-300 font-mono">${spatial3dState.bodyWeight} kg</span>
            </div>
            <input type="range" min="40" max="95" value="${spatial3dState.bodyWeight}" oninput="updateBodyFitSimulation(null, this.value)" class="w-full accent-cyan-400 cursor-pointer">
          </div>
          <div class="bg-slate-900 border border-cyan-500/30 rounded-xl p-2.5 text-xs">
            <span class="text-[10px] text-slate-400 uppercase font-bold block">Độ ôm form 3D & Size gợi ý:</span>
            <strong id="fitRecommendationBadge" class="text-emerald-400 font-extrabold block mt-0.5">Size M • Ôm chuẩn Thủy động học</strong>
          </div>
        </div>
      </div>

      <!-- Right 4 Cols: Color Morphing, Physics Telemetry & Add To Cart -->
      <div class="lg:col-span-4 space-y-4 bg-slate-950/70 border border-slate-800 rounded-3xl p-4 sm:p-5">
        <div>
          <span class="text-[10px] font-extrabold uppercase tracking-widest text-cyan-400">${prod.category_name} • ${prod.code}</span>
          <h4 class="text-xl font-black text-white mt-0.5">${prod.name}</h4>
          <div class="flex items-baseline gap-2.5 mt-2">
            <span class="text-2xl font-black text-amber-400">${formatCurrency(prod.discounted_price || prod.base_price)}</span>
            ${prod.discount_percent > 0 ? `
              <span class="text-xs text-slate-500 line-through">${formatCurrency(prod.base_price)}</span>
              <span class="px-2 py-0.5 bg-rose-500/20 border border-rose-500/40 text-rose-300 text-[10px] font-extrabold rounded-full">-${prod.discount_percent}%</span>
            ` : ''}
          </div>
        </div>

        <!-- 3D Color Swatches -->
        <div class="space-y-2 pt-2 border-t border-slate-800">
          <label class="text-xs font-extrabold uppercase tracking-wider text-slate-300 block">1. Đổi Màu Trực Tiếp Trên Mô Hình 3D:</label>
          <div class="flex flex-wrap gap-2">
            ${palettes.map(c => `
              <button type="button" onclick="changeSpatial3DColor('${c.color_hex || '#0284c7'}', '${(c.color_name || '').replace(/'/g, "\\'")}')"
                      class="px-3 py-1.5 rounded-xl border border-slate-700 hover:border-cyan-400 bg-slate-900 text-xs font-bold flex items-center gap-2 transition">
                <span class="w-4 h-4 rounded-full border border-white/40 shadow-sm" style="background:${c.color_hex || '#0284c7'}"></span>
                <span>${c.color_name}</span>
              </button>
            `).join("")}
          </div>
        </div>

        <!-- 3D Material Physics Specs -->
        <div class="space-y-2 pt-2 border-t border-slate-800">
          <label class="text-xs font-extrabold uppercase tracking-wider text-slate-300 block">2. Thông Số Vật Lý Trong Không Gian 3D:</label>
          <div class="grid grid-cols-2 gap-2 text-xs">
            <div class="p-2.5 rounded-xl bg-slate-900 border border-slate-800">
              <span class="text-[10px] text-slate-400 block">Kháng Tia UV</span>
              <strong class="text-cyan-300">${physics.uv_protection || 'UPF 50+'}</strong>
            </div>
            <div class="p-2.5 rounded-xl bg-slate-900 border border-slate-800">
              <span class="text-[10px] text-slate-400 block">Kháng Nước Clo</span>
              <strong class="text-emerald-400">${physics.chlorine_resistance_hours || 300} giờ bơi</strong>
            </div>
            <div class="p-2.5 rounded-xl bg-slate-900 border border-slate-800">
              <span class="text-[10px] text-slate-400 block">Độ Co Giãn 4 Chiều</span>
              <strong class="text-amber-300">${Math.round((physics.stretch_factor || 1.38) * 100)}% Recovery</strong>
            </div>
            <div class="p-2.5 rounded-xl bg-slate-900 border border-slate-800">
              <span class="text-[10px] text-slate-400 block">Hệ Số Cản Nước</span>
              <strong class="text-purple-300">Cd = ${physics.hydro_drag_coeff || 0.18}</strong>
            </div>
          </div>
        </div>

        <!-- interactive Hotspots List -->
        <div class="space-y-1.5 pt-2 border-t border-slate-800">
          <label class="text-xs font-extrabold uppercase tracking-wider text-slate-300 block">3. Điểm Nóng Kỹ Thuật (Chạm Để Xem):</label>
          <div class="grid grid-cols-1 gap-1.5">
            ${hotspots.map(hs => `
              <button type="button" onclick="showHotspotDetail('${hs.title.replace(/'/g, "\\'")}', '${hs.detail.replace(/'/g, "\\'")}')"
                      class="p-2 rounded-xl bg-slate-900/90 hover:bg-slate-800 border border-slate-800 text-left flex items-center justify-between text-xs transition">
                <span class="font-bold text-slate-200">${hs.title}</span>
                <span class="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 text-[10px] font-bold">${hs.badge}</span>
              </button>
            `).join("")}
          </div>
        </div>

        <!-- Variant Selection & Add To Cart from 3D Showroom -->
        <div class="space-y-2.5 pt-2 border-t border-slate-800">
          <label class="text-xs font-extrabold uppercase tracking-wider text-slate-300 block">4. Chọn Biến Thể Size & Đặt Mua:</label>
          <select id="spatialVariantSelect" onchange="onSpatialVariantSelectChange(this.value)"
                  class="w-full px-3 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs font-bold outline-none focus:border-cyan-400">
            ${prod.variants.map(v => `
              <option value="${v.id}" ${v.id === spatial3dState.selectedVariantId ? 'selected' : ''} ${v.available_quantity <= 0 ? 'disabled' : ''}>
                Size ${v.size_name} — Màu ${v.color_name} (Còn ${v.available_quantity} chiếc)
              </option>
            `).join("")}
          </select>

          <button onclick="addFromSpatial3DToCart()" class="w-full py-3 bg-gradient-to-r from-cyan-500 via-sky-500 to-indigo-600 hover:brightness-110 text-slate-950 font-black text-xs uppercase tracking-wider rounded-xl shadow-xl shadow-cyan-500/25 transition flex items-center justify-center gap-2">
            <i data-lucide="shopping-bag" class="w-4 h-4"></i>
            <span>Thêm Sản Phẩm 3D Này Vào Giỏ</span>
          </button>
        </div>
      </div>
    </div>
  `;

  lucide.createIcons();
  setupSpatialViewportInteractions();
  initThreeSpatialScene();
  updateBodyFitSimulation(spatial3dState.bodyHeight, spatial3dState.bodyWeight);
}

function setupSpatialViewportInteractions() {
  const vp = document.getElementById("spatialViewportContainer");
  if (!vp) return;

  vp.onpointerdown = null;
  vp.addEventListener("pointerdown", (e) => {
    if (e.target.tagName === "BUTTON" || e.target.tagName === "INPUT") return;
    spatial3dState.isDragging = true;
    spatial3dState.autoRotate = false;
    spatial3dState.lastX = e.clientX;
    spatial3dState.lastY = e.clientY;
    const btn = document.getElementById("btnAutoRotate3D");
    if (btn) btn.innerHTML = `<span>Tự xoay 360°: TẮT</span>`;
  });

  window.addEventListener("pointermove", (e) => {
    if (!spatial3dState.isDragging) return;
    const dx = e.clientX - spatial3dState.lastX;
    const dy = e.clientY - spatial3dState.lastY;
    spatial3dState.lastX = e.clientX;
    spatial3dState.lastY = e.clientY;

    spatial3dState.rotY += dx * 0.65;
    spatial3dState.rotX = Math.max(-45, Math.min(45, spatial3dState.rotX - dy * 0.45));
    syncSpatialTransforms();
  });

  window.addEventListener("pointerup", () => {
    spatial3dState.isDragging = false;
  });

  vp.addEventListener("wheel", (e) => {
    e.preventDefault();
    const delta = e.deltaY < 0 ? 0.08 : -0.08;
    spatial3dState.zoom = Math.max(0.65, Math.min(1.65, spatial3dState.zoom + delta));
    const slider = document.getElementById("spatialZoomSlider");
    if (slider) slider.value = Math.round(spatial3dState.zoom * 100);
    syncSpatialTransforms();
  }, { passive: false });
}

function syncSpatialTransforms() {
  const hud = document.getElementById("hudAnglesText");
  const normY = ((Math.round(spatial3dState.rotY) % 360) + 360) % 360;
  if (hud && spatial3dState.mode === "hologram") {
    hud.innerText = `Góc 3D: X: ${Math.round(spatial3dState.rotX)}° | Y: ${normY}° | Zoom: ${Math.round(spatial3dState.zoom * 100)}%`;
  }

  const hScale = spatial3dState.bodyHeight / 165;
  const wScale = Math.pow(spatial3dState.bodyWeight / 54, 0.38);

  const rig = document.getElementById("hologramRig");
  if (rig) {
    rig.style.transform = `scale(${(spatial3dState.zoom * wScale).toFixed(3)}, ${(spatial3dState.zoom * hScale).toFixed(3)}) rotateX(${spatial3dState.rotX.toFixed(1)}deg) rotateY(${spatial3dState.rotY.toFixed(1)}deg)`;
  }

  if (spatial3dState.engineViewer) {
    spatial3dState.engineViewer.setBodyScale(wScale, hScale);
  }
}

function initThreeSpatialScene() {
  const prod = spatial3dState.product;
  if (!prod || !window.Soobin3DEngine) return;
  const sp = prod.spatial_3d || {};
  const imgUrl = (prod.images && prod.images[0]) ? prod.images[0].file_path : null;

  const viewer = window.Soobin3DEngine.mount("threeSpatialCanvas", {
    geometryType: sp.geometry_type || "onepiece_3d",
    targetAudience: prod.target_audience || "Nữ",
    colorHex: spatial3dState.activeColorHex || "#0284c7",
    imageUrl: imgUrl,
    autoRotate: spatial3dState.autoRotate,
    onTransformChange: (st) => {
      const hud = document.getElementById("hudAnglesText");
      const normY = ((Math.round(st.rotY) % 360) + 360) % 360;
      if (hud) {
        hud.innerText = `Góc 3D: X: ${Math.round(st.rotX)}° | Y: ${normY}° | Zoom: ${Math.round(st.zoom * 100)}%`;
      }
    }
  });
  spatial3dState.engineViewer = viewer;
}

function switchSpatial3DMode(mode) {
  spatial3dState.mode = mode;
  ["webgl", "hologram", "bodyfit"].forEach(m => {
    const btn = document.getElementById(`btn3dMode-${m}`);
    if (btn) {
      btn.className = `px-3 py-1.5 rounded-xl text-xs font-extrabold transition flex items-center gap-1.5 ${
        m === mode ? "bg-cyan-500 text-slate-950 shadow-lg shadow-cyan-500/25" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
      }`;
    }
  });

  const canvas = document.getElementById("threeSpatialCanvas");
  const holo = document.getElementById("hologramSpatialStage");
  if (mode === "hologram") {
    if (canvas) canvas.classList.add("hidden");
    if (holo) holo.classList.remove("hidden"), holo.classList.add("flex");
  } else {
    if (canvas) canvas.classList.remove("hidden");
    if (holo) holo.classList.add("hidden"), holo.classList.remove("flex");
    if (spatial3dState.engineViewer) {
      spatial3dState.engineViewer.setWireframe(mode === "bodyfit");
    }
  }
}

function changeSpatial3DColor(hex, colorName) {
  spatial3dState.activeColorHex = hex || "#0284c7";
  spatial3dState.activeColorName = colorName || "Xanh Đại Dương";

  const hudColor = document.getElementById("hudColorName");
  if (hudColor) hudColor.innerText = spatial3dState.activeColorName;

  const glow = document.getElementById("spatialStageBackdropGlow");
  if (glow) {
    glow.style.background = `radial-gradient(circle at 50% 45%, ${spatial3dState.activeColorHex}66 0%, rgba(8, 145, 178, 0.18) 45%, transparent 75%)`;
  }

  const holoOverlay = document.getElementById("hologramColorOverlay");
  if (holoOverlay) holoOverlay.style.backgroundColor = spatial3dState.activeColorHex;

  if (spatial3dState.engineViewer) {
    spatial3dState.engineViewer.setColor(spatial3dState.activeColorHex);
  }
}

function setSpatialLighting(presetId) {
  spatial3dState.activeLightPreset = presetId;
  const presets = {
    "ocean-daylight": { bg: "from-slate-950 via-sky-950/70 to-slate-950" },
    "ibiza-sunset": { bg: "from-stone-950 via-orange-950/70 to-slate-950" },
    "neon-runway": { bg: "from-slate-950 via-purple-950/75 to-indigo-950" },
    "studio-pure": { bg: "from-slate-900 via-slate-800 to-slate-950" }
  };
  const p = presets[presetId] || presets["ocean-daylight"];
  const vp = document.getElementById("spatialViewportContainer");
  if (vp) {
    vp.className = `spatial-stage-viewport relative h-[430px] sm:h-[490px] w-full rounded-3xl overflow-hidden border border-cyan-500/30 bg-gradient-to-b ${p.bg} flex items-center justify-center cursor-grab active:cursor-grabbing shadow-inner`;
  }
  if (spatial3dState.engineViewer) {
    spatial3dState.engineViewer.setLighting(presetId);
  }
}

function toggleSpatialAutoRotate() {
  spatial3dState.autoRotate = !spatial3dState.autoRotate;
  if (spatial3dState.engineViewer) {
    spatial3dState.engineViewer.setAutoRotate(spatial3dState.autoRotate);
  }
  const btn = document.getElementById("btnAutoRotate3D");
  if (btn) {
    btn.innerHTML = `<span>Tự xoay 360°: ${spatial3dState.autoRotate ? "BẬT" : "TẮT"}</span>`;
  }
}

function resetSpatialCamera() {
  spatial3dState.rotX = 10;
  spatial3dState.rotY = -20;
  spatial3dState.zoom = 1.0;
  const slider = document.getElementById("spatialZoomSlider");
  if (slider) slider.value = 100;
  if (spatial3dState.engineViewer) {
    spatial3dState.engineViewer.resetCamera();
  }
  syncSpatialTransforms();
}

function updateSpatialZoom(val) {
  spatial3dState.zoom = Number(val) / 100;
  if (spatial3dState.engineViewer) {
    spatial3dState.engineViewer.setZoom(spatial3dState.zoom);
  }
  syncSpatialTransforms();
}

function showHotspotDetail(title, detail) {
  const banner = document.getElementById("spatialHotspotBanner");
  if (!banner) return;
  document.getElementById("hotspotBannerTitle").innerText = `✦ ${title}`;
  document.getElementById("hotspotBannerDetail").innerText = detail;
  banner.classList.remove("hidden");
}

function updateBodyFitSimulation(heightVal, weightVal) {
  if (heightVal !== null) spatial3dState.bodyHeight = Number(heightVal);
  if (weightVal !== null) spatial3dState.bodyWeight = Number(weightVal);

  const hEl = document.getElementById("fitHeightLabel");
  const wEl = document.getElementById("fitWeightLabel");
  if (hEl) hEl.innerText = `${spatial3dState.bodyHeight} cm`;
  if (wEl) wEl.innerText = `${spatial3dState.bodyWeight} kg`;

  const h = spatial3dState.bodyHeight;
  const w = spatial3dState.bodyWeight;
  let recSize = "M";
  if (w < 47 && h < 158) recSize = "S";
  else if (w <= 56 && h <= 166) recSize = "M";
  else if (w <= 66 && h <= 174) recSize = "L";
  else if (w <= 76) recSize = "XL";
  else recSize = "2XL";

  const bmi = w / Math.pow(h / 100, 2);
  let fitFeel = "Vừa vặn tôn dáng chuẩn Resort";
  if (bmi < 18.8) fitFeel = "Ôm gọn thoải mái, không bó sát";
  else if (bmi > 23.5) fitFeel = "Độ nén cơ Hydro-Fit cao (Khuyên nhích 1 size nếu thích rộng)";

  const badge = document.getElementById("fitRecommendationBadge");
  if (badge) {
    badge.innerText = `Đề xuất Size ${recSize} • ${fitFeel}`;
  }

  syncSpatialTransforms();
}

function onSpatialVariantSelectChange(varId) {
  spatial3dState.selectedVariantId = Number(varId);
  if (spatial3dState.product && spatial3dState.product.variants) {
    const found = spatial3dState.product.variants.find(v => v.id === Number(varId));
    if (found) {
      changeSpatial3DColor(found.color_hex || "#0284c7", found.color_name || "");
    }
  }
}

async function addFromSpatial3DToCart() {
  const varSelect = document.getElementById("spatialVariantSelect");
  const varId = varSelect ? Number(varSelect.value) : spatial3dState.selectedVariantId;
  if (!varId) {
    showToast("Vui lòng chọn biến thể sản phẩm.", true);
    return;
  }
  selectedVariantId = varId;
  selectedProduct = spatial3dState.product;

  if (currentUser) {
    try {
      const res = await fetch("/api/v1/cart/items", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ variant_id: varId, quantity: 1 })
      });
      const data = await res.json();
      if (!res.ok) {
        showToast(data.detail || "Không thể thêm vào giỏ.", true);
        return;
      }
      showToast("🎉 Đã thêm sản phẩm từ Phòng 3D vào giỏ hàng!");
      closeSpatial3DModal();
      updateCartBadge();
      toggleCartDrawer();
    } catch (e) {
      showToast("Lỗi khi thêm vào giỏ.", true);
    }
  } else {
    const existing = guestCart.find(i => i.variant_id === varId);
    if (existing) existing.quantity += 1;
    else guestCart.push({ variant_id: varId, quantity: 1 });
    localStorage.setItem("soobin_guest_cart", JSON.stringify(guestCart));
    showToast("🎉 Đã thêm sản phẩm 3D vào giỏ hàng tạm!");
    closeSpatial3DModal();
    updateCartBadge();
    toggleCartDrawer();
  }
}

// =============================================================================
// MIX & MATCH 3D LOOKBOOK BUNDLES
// =============================================================================

let loadedBundles = [];

async function loadLookbookBundles() {
  const grid = document.getElementById("lookbookBundlesGrid");
  if (!grid) return;
  try {
    const res = await fetch("/api/v1/catalog/lookbook-bundles");
    if (!res.ok) return;
    loadedBundles = await res.json();
    if (!loadedBundles.length) return;

    grid.innerHTML = loadedBundles.map((b, bIdx) => `
      <div class="theme-surface rounded-3xl border p-5 shadow-lg space-y-4 relative overflow-hidden">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <span class="px-2.5 py-0.5 rounded-full bg-gradient-to-r ${b.theme_gradient} text-white text-[10px] font-black uppercase tracking-wider">${b.badge}</span>
            <h4 class="text-lg font-extrabold mt-1">${b.name}</h4>
          </div>
          <div class="text-right">
            <span class="text-[10px] text-slate-400 block">Trọn bộ ${b.items.length} món:</span>
            <span class="text-xl font-black text-rose-600">${formatCurrency(b.total_bundle_price)}</span>
          </div>
        </div>
        <p class="text-xs text-slate-500 leading-relaxed">${b.description}</p>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
          ${b.items.map(it => `
            <div class="p-2.5 rounded-2xl border border-slate-200/80 bg-slate-50/70 flex flex-col justify-between gap-2">
              <div class="flex items-center gap-2">
                <img src="${it.image_url}" class="w-12 h-12 rounded-xl object-cover border">
                <div class="min-w-0 flex-1">
                  <p class="text-xs font-bold text-slate-900 truncate">${it.name}</p>
                  <span class="text-[10px] text-slate-500 block">Size ${it.size_name} • ${it.color_name}</span>
                  <span class="text-xs font-extrabold text-sky-600">${formatCurrency(it.discounted_price)}</span>
                </div>
              </div>
              <button onclick="openProductModal('${it.product_id}')" class="w-full py-1 rounded-lg bg-slate-900 hover:bg-slate-800 text-cyan-300 text-[10px] font-bold transition flex items-center justify-center gap-1">
                <i data-lucide="eye" class="w-3 h-3"></i> Xem Chi Tiết Món Này
              </button>
            </div>
          `).join("")}
        </div>

        <div class="pt-2 border-t flex items-center justify-between gap-3">
          <span class="text-[11px] font-semibold text-emerald-600">✓ Đã kiểm tra tồn kho sẵn sàng cho toàn bộ Set</span>
          <button onclick="addLookbookBundleToCart(${bIdx})" class="px-4 py-2.5 rounded-xl bg-gradient-to-r ${b.theme_gradient} text-white font-extrabold text-xs shadow-md hover:scale-105 transition flex items-center gap-1.5">
            <i data-lucide="shopping-bag" class="w-4 h-4"></i>
            <span>Mua Trọn Bộ Phối Đồ (${b.items.length} Món)</span>
          </button>
        </div>
      </div>
    `).join("");
    lucide.createIcons();
  } catch (e) {}
}

async function addLookbookBundleToCart(bundleIdx) {
  const b = loadedBundles[bundleIdx];
  if (!b) return;

  if (currentUser) {
    try {
      const res = await fetch("/api/v1/cart/bundle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          bundle_name: b.name,
          items: b.items.map(i => ({ variant_id: i.variant_id, quantity: 1 }))
        })
      });
      const data = await res.json();
      if (!res.ok) {
        showToast(data.detail || "Không thể thêm Set phối đồ.", true);
        return;
      }
      showToast(data.message || "Đã thêm trọn bộ phối đồ vào giỏ hàng!");
      updateCartBadge();
      toggleCartDrawer();
    } catch (e) {
      showToast("Lỗi khi thêm Set phối đồ.", true);
    }
  } else {
    b.items.forEach(i => {
      const ex = guestCart.find(g => g.variant_id === i.variant_id);
      if (ex) ex.quantity += 1;
      else guestCart.push({ variant_id: i.variant_id, quantity: 1 });
    });
    localStorage.setItem("soobin_guest_cart", JSON.stringify(guestCart));
    showToast(`Đã thêm trọn bộ '${b.name}' vào giỏ hàng!`);
    updateCartBadge();
    toggleCartDrawer();
  }
}

// =============================================================================
// 3D PRODUCT COMPARISON MATRIX
// =============================================================================

window.comparedProductIds = new Set();

function toggleCompareProduct(productId, evt) {
  if (evt) evt.stopPropagation();
  if (window.comparedProductIds.has(productId)) {
    window.comparedProductIds.delete(productId);
    showToast("Đã bỏ sản phẩm khỏi danh sách so sánh 3D.");
  } else {
    if (window.comparedProductIds.size >= 4) {
      showToast("Chỉ có thể so sánh tối đa 4 sản phẩm cùng lúc.", true);
      return;
    }
    window.comparedProductIds.add(productId);
    showToast("Đã thêm vào thanh So sánh 3D!");
  }
  updateCompareFloatingBar();
  renderProductGrid(currentProducts);
}

function updateCompareFloatingBar() {
  const bar = document.getElementById("compareFloatingBar");
  const badge = document.getElementById("compareCountBadge");
  if (!bar || !badge) return;
  const count = window.comparedProductIds.size;
  badge.innerText = count;
  if (count > 0) bar.classList.remove("hidden");
  else bar.classList.add("hidden");
}

function clearCompareSelection() {
  window.comparedProductIds.clear();
  updateCompareFloatingBar();
  renderProductGrid(currentProducts);
}

async function openCompareModal() {
  if (window.comparedProductIds.size === 0) return;
  const modal = document.getElementById("compareModal");
  const content = document.getElementById("compareModalContent");
  modal.classList.remove("hidden");
  content.innerHTML = `<div class="py-12 text-center text-slate-400">Đang tổng hợp bảng so sánh thông số 3D...</div>`;

  try {
    const idsParam = [...window.comparedProductIds].join(",");
    const res = await fetch(`/api/v1/catalog/compare?ids=${idsParam}`);
    const items = await res.json();

    content.innerHTML = `
      <table class="w-full text-left border-collapse text-xs">
        <thead>
          <tr class="border-b bg-slate-50">
            <th class="p-3 font-extrabold text-slate-600 w-44">Tiêu chí so sánh</th>
            ${items.map(p => `
              <th class="p-3 min-w-[200px] align-top">
                <div class="space-y-2">
                  <img src="${p.image_url}" class="w-full h-36 object-cover rounded-2xl border">
                  <span class="text-[10px] font-bold text-sky-600 uppercase block">${p.category_name}</span>
                  <h4 class="font-extrabold text-sm text-slate-900">${p.name}</h4>
                  <div class="flex gap-1.5">
                    <button onclick="closeCompareModal(); openProductModal('${p.slug || p.id}')" class="flex-1 py-1.5 bg-sky-600 hover:bg-sky-700 text-white rounded-lg font-bold text-[11px]">Xem Chi Tiết & Chọn Size</button>
                  </div>
                </div>
              </th>
            `).join("")}
          </tr>
        </thead>
        <tbody class="divide-y">
          <tr>
            <td class="p-3 font-bold text-slate-600">Giá bán hiện tại</td>
            ${items.map(p => `
              <td class="p-3">
                <span class="text-base font-black text-rose-600">${formatCurrency(p.discounted_price)}</span>
                ${p.discount_percent > 0 ? `<span class="text-slate-400 line-through ml-1">${formatCurrency(p.base_price)}</span> <span class="text-emerald-600 font-bold">(-${p.discount_percent}%)</span>` : ''}
              </td>
            `).join("")}
          </tr>
          <tr>
            <td class="p-3 font-bold text-slate-600">Chất liệu & Co giãn</td>
            ${items.map(p => `<td class="p-3 font-semibold text-slate-700">${p.material_physics.fabric} (Co giãn ${Math.round(p.material_physics.stretch_factor * 100)}%)</td>`).join("")}
          </tr>
          <tr>
            <td class="p-3 font-bold text-slate-600">Kháng Clo & Chống UV</td>
            ${items.map(p => `<td class="p-3"><span class="px-2 py-0.5 bg-sky-100 text-sky-800 rounded font-bold">${p.material_physics.uv_protection}</span> • <span class="font-bold text-emerald-700">${p.material_physics.chlorine_resistance_hours}h Kháng Clo</span></td>`).join("")}
          </tr>
          <tr>
            <td class="p-3 font-bold text-slate-600">Các Size & Màu sắc</td>
            ${items.map(p => `<td class="p-3">Size: <strong>${p.sizes.join(", ") || "S, M, L"}</strong><br><span class="text-slate-500">Màu: ${p.colors.join(", ")}</span></td>`).join("")}
          </tr>
          <tr>
            <td class="p-3 font-bold text-slate-600">Tồn kho & Đánh giá</td>
            ${items.map(p => `<td class="p-3 font-bold ${p.total_stock > 0 ? 'text-emerald-600' : 'text-rose-600'}">Còn ${p.total_stock} chiếc • ★ ${p.avg_rating} (${p.review_count})</td>`).join("")}
          </tr>
        </tbody>
      </table>
    `;
  } catch (e) {
    content.innerHTML = `<div class="py-8 text-center text-rose-500">Lỗi khi tải bảng so sánh.</div>`;
  }
}

function closeCompareModal() {
  document.getElementById("compareModal").classList.add("hidden");
}

// =============================================================================
// RE-ORDER 1-CLICK & SIZE EXCHANGE / WARRANTY REQUEST
// =============================================================================

async function reorderPastOrder(orderId) {
  try {
    const res = await fetch(`/api/v1/orders/${orderId}/reorder`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.detail || "Không thể mua lại đơn hàng này.", true);
      return;
    }
    showToast(data.message);
    closeOrdersModal();
    updateCartBadge();
    toggleCartDrawer();
  } catch (e) {
    showToast("Lỗi khi thực hiện mua lại đơn hàng.", true);
  }
}

async function openExchangeModal(orderId, orderCode) {
  document.getElementById("exchangeOrderId").value = orderId;
  document.getElementById("exchangeModalOrderLabel").innerText = `Đơn hàng: ${orderCode}`;
  document.getElementById("exchangeReason").value = "";
  document.getElementById("exchangeRequestModal").classList.remove("hidden");
  try {
    const res = await fetch("/api/v1/site-settings/after-sales-policy", { cache: "no-store" });
    if (res.ok) {
      const p = await res.json();
      const exEl = document.getElementById("policyExchangeDaysLabel");
      const retEl = document.getElementById("policyReturnDaysLabel");
      const warEl = document.getElementById("policyWarrantyDaysLabel");
      const termsEl = document.getElementById("policyTermsText");
      if (exEl) exEl.innerText = `${p.exchange_size_window_days ?? 15} ngày`;
      if (retEl) retEl.innerText = `${p.return_window_days ?? 7} ngày`;
      if (warEl) warEl.innerText = `${p.warranty_window_days ?? 90} ngày`;
      if (termsEl && p.warranty_terms) termsEl.innerText = p.warranty_terms;
    }
  } catch (_) {}
}

function closeExchangeModal() {
  document.getElementById("exchangeRequestModal").classList.add("hidden");
}

async function submitExchangeRequestForm(e) {
  e.preventDefault();
  const orderId = document.getElementById("exchangeOrderId").value;
  const preferred_resolution = document.getElementById("exchangeResolution").value;
  const target_size = document.getElementById("exchangeTargetSize").value;
  const reason = document.getElementById("exchangeReason").value.trim();

  try {
    const res = await fetch(`/api/v1/orders/${orderId}/exchange-request`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_size, reason, preferred_resolution })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.detail || "Không thể gửi yêu cầu đổi size.", true);
      return;
    }
    showToast(data.message);
    closeExchangeModal();
  } catch (err) {
    showToast("Lỗi kết nối khi gửi yêu cầu đổi size.", true);
  }
}

