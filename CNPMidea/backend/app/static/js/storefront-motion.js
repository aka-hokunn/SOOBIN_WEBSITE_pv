/**
 * ============================================================================
 * SOOBIN STOREFRONT MOTION ENGINE
 * ----------------------------------------------------------------------------
 * Theo antigravityrules.md (bản HTML thuần, không React):
 *  - Lenis smooth scroll (khởi tạo ở creative-engine.js) đồng bộ gsap.ticker
 *    + ScrollTrigger.update  →  mọi hiệu ứng bên dưới đều chạy trên nền đó.
 *  - GSAP ScrollTrigger: zoom-in khi phần tử đi vào, zoom-out khi rời khỏi
 *    màn hình, ghim (pin) + trượt ngang cho Showcase Hot/Trending,
 *    containerAnimation cho parallax ảnh trong từng thẻ.
 *  - Magic UI Marquee, Aceternity 3D Card / Spotlight glare, Magnetic CTA,
 *    Number Ticker, Velocity Marquee phản ứng theo tốc độ cuộn.
 *  - Tôn trọng prefers-reduced-motion; mobile dùng vuốt ngang native.
 *  - Hai chế độ xem: "home" (trang chủ trình diễn zoom in/out, mặt biển
 *    Three.js, cửa sổ bãi biển) và "shop" (lưới sản phẩm, KHÔNG zoom —
 *    toàn bộ ScrollTrigger của trang chủ được tắt khi vào danh mục).
 * ============================================================================
 */
(function () {
  "use strict";

  const gsap = window.gsap;
  const ST = window.ScrollTrigger;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;

  const state = {
    showcase: null,
    cardBatch: [],
    showcaseCards: [],
    showcaseMode: "hot",
    velocityRows: [],
    velocityActive: false,
    countdownTimer: null,
    coverCards: [],
    coverProgress: 0,
    view: null,
    booted: false,
    homeBuilt: false,
  };

  // --------------------------------------------------------------------------
  // HELPERS
  // --------------------------------------------------------------------------
  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const money = (v) =>
    typeof window.formatCurrency === "function"
      ? window.formatCurrency(v)
      : `${Math.round(Number(v) || 0).toLocaleString("vi-VN")}đ`;

  const pad2 = (n) => String(Math.max(0, n)).padStart(2, "0");

  function headerOffset() {
    const h = document.querySelector("header.sticky");
    return h ? h.offsetHeight : 64;
  }

  function syncHeaderVar() {
    document.documentElement.style.setProperty("--soobin-header-h", `${headerOffset()}px`);
  }

  function scrollToId(id) {
    const el = document.getElementById(id);
    if (!el) return;
    if (window.soobinLenis) {
      window.soobinLenis.scrollTo(el, { offset: -headerOffset(), duration: 1.4 });
    } else {
      const y = el.getBoundingClientRect().top + window.scrollY - headerOffset();
      window.scrollTo({ top: y, behavior: "smooth" });
    }
  }

  function openProduct(slug) {
    if (!slug) return;
    if (typeof window.playRefreshingSelectSound === "function") window.playRefreshingSelectSound("select");
    if (typeof window.openProductModal === "function") window.openProductModal(slug);
  }

  let refreshTimer = null;
  function scheduleRefresh() {
    if (!ST) return;
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(() => ST.refresh(), 220);
  }

  // --------------------------------------------------------------------------
  // 1. SCROLL ZOOM REVEAL (zoom-in khi vào, zoom-out khi rời màn hình)
  // --------------------------------------------------------------------------
  function initZoomReveal(root = document) {
    if (!gsap || !ST || reduceMotion) return;

    root.querySelectorAll("[data-zoom-reveal]").forEach((el) => {
      if (el.dataset.zoomBound) return;
      el.dataset.zoomBound = "1";
      const mode = el.getAttribute("data-zoom-reveal");

      gsap.fromTo(
        el,
        { scale: 0.86, opacity: 0, y: 70 },
        {
          scale: 1, opacity: 1, y: 0, ease: "none",
          scrollTrigger: { trigger: el, start: "top 96%", end: "top 62%", scrub: 0.6 },
        }
      );

      if (mode !== "in") {
        gsap.fromTo(
          el,
          { scale: 1, opacity: 1, y: 0 },
          {
            scale: 0.93, opacity: 0.35, y: -40, ease: "none", immediateRender: false,
            scrollTrigger: { trigger: el, start: "bottom 38%", end: "bottom top", scrub: 0.6 },
          }
        );
      }
    });

    root.querySelectorAll("[data-zoom-stagger]").forEach((wrap) => {
      if (wrap.dataset.zoomBound) return;
      wrap.dataset.zoomBound = "1";
      gsap.fromTo(
        wrap.children,
        { scale: 0.8, opacity: 0, y: 60 },
        {
          scale: 1, opacity: 1, y: 0, duration: 0.9, ease: "expo.out", stagger: 0.12,
          scrollTrigger: { trigger: wrap, start: "top 85%", toggleActions: "play none none reverse" },
        }
      );
    });

    root.querySelectorAll("[data-split-heading]").forEach((el) => {
      if (el.dataset.splitBound) return;
      el.dataset.splitBound = "1";
      gsap.fromTo(
        el,
        { clipPath: "inset(0 0 100% 0)", y: 34 },
        {
          clipPath: "inset(0 0 0% 0)", y: 0, duration: 1.1, ease: "expo.out",
          scrollTrigger: { trigger: el, start: "top 88%", toggleActions: "play none none reverse" },
        }
      );
    });
  }

  /**
   * Thẻ sản phẩm lưới catalog (chỉ có ở trang danh mục "shop"): chỉ hiện dần
   * nhẹ nhàng — KHÔNG zoom in/out để khách lướt và so sánh sản phẩm nhanh.
   */
  function revealCards(container) {
    const grid = container || document.getElementById("productGrid");
    if (!grid) return;
    const cards = grid.querySelectorAll(".editorial-product-card");
    state.cardBatch.forEach((t) => t.kill());
    state.cardBatch = [];
    if (!cards.length || !gsap || reduceMotion) return;

    gsap.fromTo(
      cards,
      { opacity: 0, y: 14 },
      {
        opacity: 1, y: 0, duration: 0.4, ease: "power2.out",
        stagger: { each: 0.025, from: "start" }, overwrite: true, clearProps: "opacity,transform",
      }
    );
  }

  // --------------------------------------------------------------------------
  // 2. COVER (TRANG BÌA): headline mask reveal, fan thẻ Hot, number ticker
  // --------------------------------------------------------------------------
  function animateCounters() {
    document.querySelectorAll("[data-count-to]").forEach((el) => {
      const target = Number(el.getAttribute("data-count-to") || 0);
      if (!gsap || reduceMotion) {
        el.textContent = target.toLocaleString("vi-VN");
        return;
      }
      const obj = { v: 0 };
      gsap.to(obj, {
        v: target, duration: 1.8, ease: "power3.out", delay: 0.35,
        onUpdate: () => (el.textContent = Math.round(obj.v).toLocaleString("vi-VN")),
      });
    });
  }

  function coverIntro() {
    if (!gsap || reduceMotion) return;
    const lines = document.querySelectorAll("#coverHeadline .split-line");
    lines.forEach((line) => {
      if (line.parentElement.classList.contains("split-mask")) return;
      const mask = document.createElement("span");
      mask.className = "split-mask block";
      line.parentNode.insertBefore(mask, line);
      mask.appendChild(line);
    });
    gsap.timeline({ defaults: { ease: "expo.out" } })
      .from(lines, { yPercent: 110, rotate: 2.5, duration: 1.15, stagger: 0.12 })
      .from("[data-cover-intro]", { y: 26, opacity: 0, duration: 0.9, stagger: 0.08 }, 0.25)
      .from(".cover-sun", { y: 90, opacity: 0, duration: 1.6 }, 0)
      .from(".cover-cloud-a", { x: -160, opacity: 0, duration: 1.8 }, 0.1)
      .from(".cover-cloud-b", { x: 160, opacity: 0, duration: 1.8 }, 0.2)
      .from(".cover-gulls", { x: -80, y: 30, opacity: 0, duration: 2 }, 0.5)
      .from(".cover-scroll-hint", { y: 20, opacity: 0, duration: 0.8 }, 1);
  }

  function coverLayout() {
    const narrow = window.innerWidth < 640;
    return [
      { xPercent: -50, rotation: 0, scale: 1, zIndex: 3 },
      { xPercent: narrow ? -92 : -108, rotation: -9, scale: 0.86, zIndex: 2 },
      { xPercent: narrow ? -8 : 8, rotation: 9, scale: 0.86, zIndex: 1 },
    ];
  }

  function renderCover(data) {
    const stats = data.stats || {};
    const setCount = (id, v) => {
      const el = document.getElementById(id);
      if (el) el.setAttribute("data-count-to", String(Math.round(Number(v) || 0)));
    };
    setCount("coverStatProducts", stats.total_products);
    setCount("coverStatSold", stats.total_sold);
    setCount("coverStatDiscount", stats.max_discount_percent);
    const ctaLabel = document.getElementById("coverSaleCtaLabel");
    if (ctaLabel && stats.max_discount_percent > 0) ctaLabel.textContent = "giảm sâu nhất";
    animateCounters();

    const picks = (data.hot && data.hot.length ? data.hot : data.trending || []).slice(0, 3);
    const box = document.getElementById("coverCards");
    if (!box || !picks.length) return;

    // Order in DOM: back cards first so the hero card stays on top
    const order = [1, 2, 0].filter((i) => picks[i]);
    box.innerHTML = order
      .map((i) => {
        const p = picks[i];
        const priceHtml =
          p.discount_percent > 0
            ? `<span class="font-black text-amber-300">${money(p.discounted_price)}</span><span class="ml-1.5 text-[11px] text-white/60 line-through">${money(p.base_price)}</span>`
            : `<span class="font-black">${money(p.base_price)}</span>`;
        return `
          <div class="cover-card" data-idx="${i}" data-slug="${esc(p.slug)}" data-cursor-label="Xem nhanh">
            <img src="${esc(p.image_url)}" alt="${esc(p.name)}" loading="eager">
            ${p.discount_percent > 0 ? `<span class="absolute top-3 left-3 px-2.5 py-1 rounded-full bg-rose-600 text-white text-[10px] font-black shadow">-${Math.round(p.discount_percent)}%</span>` : ""}
            <span class="absolute top-3 right-3 px-2.5 py-1 rounded-full bg-white/90 text-slate-900 text-[10px] font-black">#${i + 1} HOT</span>
            <div class="cover-card-info">
              <span class="block text-[10px] font-extrabold uppercase tracking-widest text-cyan-300">${esc(p.category_name)}</span>
              <span class="block text-sm font-extrabold leading-snug line-clamp-2">${esc(p.name)}</span>
              <span class="block text-sm mt-1">${priceHtml}</span>
            </div>
          </div>`;
      })
      .join("");

    const top = picks[0];
    const chipSold = document.getElementById("coverChipSold");
    const chipSoldText = document.getElementById("coverChipSoldText");
    if (chipSold && chipSoldText) {
      chipSoldText.textContent = top.sold_count > 0 ? `${top.sold_count} khách đã mua mẫu này` : "Mẫu nổi bật mùa hè";
      chipSold.classList.remove("hidden");
    }
    const chipRating = document.getElementById("coverChipRating");
    const chipRatingText = document.getElementById("coverChipRatingText");
    if (chipRating && chipRatingText) {
      chipRatingText.textContent =
        stats.avg_rating > 0 ? `${stats.avg_rating}/5 đánh giá trung bình` : "Đổi size dễ dàng";
      chipRating.classList.remove("hidden");
    }

    const cards = box.querySelectorAll(".cover-card");
    const layout = coverLayout();
    if (!gsap) return;

    cards.forEach((c) => {
      const L = layout[Number(c.dataset.idx)];
      gsap.set(c, { xPercent: L.xPercent, yPercent: -50, rotation: L.rotation, scale: L.scale, zIndex: L.zIndex });
    });

    if (!reduceMotion) {
      gsap.from(cards, {
        y: 160, opacity: 0, rotation: 0, scale: 0.6, duration: 1.3, ease: "expo.out", stagger: 0.12, delay: 0.15,
        onComplete: () => {
          cards.forEach((c, k) =>
            gsap.to(c, { y: k % 2 ? 10 : -12, duration: 3.2 + k * 0.4, ease: "sine.inOut", yoyo: true, repeat: -1 })
          );
        },
      });
      gsap.from([chipSold, chipRating], { scale: 0, opacity: 0, duration: 0.8, ease: "back.out(2)", stagger: 0.15, delay: 1 });

      // Desktop: card hover lift + mouse parallax tilt of the whole fan
      if (finePointer) {
        const stage = document.getElementById("coverStage");
        const rotY = gsap.quickTo(box, "rotationY", { duration: 0.8, ease: "power3.out" });
        const rotX = gsap.quickTo(box, "rotationX", { duration: 0.8, ease: "power3.out" });
        gsap.set(box, { transformStyle: "preserve-3d", transformPerspective: 1400 });
        stage.addEventListener("mousemove", (e) => {
          const r = stage.getBoundingClientRect();
          rotY(((e.clientX - r.left) / r.width - 0.5) * 14);
          rotX(-((e.clientY - r.top) / r.height - 0.5) * 10);
        });
        stage.addEventListener("mouseleave", () => { rotY(0); rotX(0); });
        cards.forEach((c) => {
          const L = layout[Number(c.dataset.idx)];
          c.addEventListener("mouseenter", () => gsap.to(c, { scale: L.scale + 0.06, zIndex: 5, duration: 0.5, ease: "power3.out" }));
          c.addEventListener("mouseleave", () => gsap.to(c, { scale: L.scale, zIndex: L.zIndex, duration: 0.6, ease: "power3.out" }));
        });
      }

      // Scroll: cards spread apart then sink into the sea (driven by initCoverScroll)
      state.coverCards = Array.from(cards);
      spreadCoverCards(state.coverProgress);
    }

    box.addEventListener("click", (e) => {
      const card = e.target.closest("[data-slug]");
      if (card) openProduct(card.dataset.slug);
    });
  }

  // --------------------------------------------------------------------------
  // 3. PINNED HORIZONTAL SHOWCASE (HOT → TRENDING)
  // --------------------------------------------------------------------------
  function showcaseCardHtml(p, rank, kind) {
    const sale = p.discount_percent > 0;
    const soldLabel = p.sold_count > 0 ? `Đã bán ${p.sold_count}` : "Mới về";
    const rating = p.review_count > 0 ? `<span class="text-amber-300">★ ${p.avg_rating}</span><span class="text-sky-200/50">(${p.review_count})</span>` : "";
    return `
      <article class="sc-card" data-sc-kind="${kind}" data-slug="${esc(p.slug)}">
        <div class="sc-card-img">
          <img src="${esc(p.image_url)}" alt="${esc(p.name)}" loading="lazy">
          <div class="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent to-transparent"></div>
          <span class="sc-rank">${pad2(rank)}</span>
          <div class="absolute top-3 left-3 flex flex-col gap-1.5 z-[3]">
            ${sale ? `<span class="px-2.5 py-1 rounded-full bg-rose-600 text-white text-[10px] font-black">-${Math.round(p.discount_percent)}%</span>` : ""}
            <span class="px-2.5 py-1 rounded-full bg-white/90 text-slate-900 text-[10px] font-black">${kind === "hot" ? "🔥 HOT" : "📈 TREND"}</span>
          </div>
        </div>
        <div class="sc-card-body p-4 space-y-2">
          <span class="block text-[10px] font-extrabold uppercase tracking-widest text-cyan-300 truncate">${esc(p.category_name)}</span>
          <h3 class="font-extrabold text-sm leading-snug line-clamp-2 min-h-[2.5rem]">${esc(p.name)}</h3>
          <div class="flex items-end justify-between gap-2 pt-1">
            <div class="min-w-0">
              <span class="block text-base font-black whitespace-nowrap ${sale ? "text-amber-300" : "text-white"}">${money(sale ? p.discounted_price : p.base_price)}</span>
              ${sale ? `<span class="text-[11px] text-sky-200/50 line-through">${money(p.base_price)}</span>` : `<span class="text-[11px] text-sky-200/50">Giá chính hãng</span>`}
            </div>
            <span class="shrink-0 whitespace-nowrap px-3 py-1.5 rounded-xl bg-white text-slate-950 text-[11px] font-extrabold">Chọn Size →</span>
          </div>
          <div class="sc-card-meta flex items-center gap-2 text-[11px] font-bold text-sky-100/80 pt-1 border-t border-white/10">
            <span>${soldLabel}</span>${rating ? `<span class="text-sky-200/30">•</span>${rating}` : ""}
          </div>
        </div>
        <div class="sc-card-glare"></div>
      </article>`;
  }

  function renderShowcase(data) {
    const track = document.getElementById("showcaseTrack");
    if (!track) return;
    const hot = data.hot || [];
    const trending = data.trending || [];
    if (!hot.length && !trending.length) {
      document.getElementById("showcaseHot")?.classList.add("hidden");
      return;
    }

    const introPanel = (word, title, desc) => `
      <div class="sc-panel-intro" data-sc-intro>
        <span class="sc-outline-word">${word}</span>
        <h3 class="text-2xl font-black mt-4">${title}</h3>
        <p class="text-sm text-sky-100/70 mt-2 max-w-xs">${desc}</p>
      </div>`;

    track.innerHTML =
      introPanel("HOT", "Bán chạy nhất", `${hot.length} mẫu được chọn mua nhiều nhất tại Soobin.`) +
      hot.map((p, i) => showcaseCardHtml(p, i + 1, "hot")).join("") +
      (trending.length
        ? `<div class="sc-panel-intro" data-sc-trend-start>
             <span class="sc-outline-word">TREND</span>
             <h3 class="text-2xl font-black mt-4">Đang thịnh hành</h3>
             <p class="text-sm text-sky-100/70 mt-2 max-w-xs">Xu hướng được săn đón & đánh giá cao trong 30 ngày qua.</p>
           </div>` + trending.map((p, i) => showcaseCardHtml(p, i + 1, "trend")).join("")
        : "") +
      `<div class="sc-panel-intro">
         <h3 class="text-3xl font-black leading-tight">Chưa thấy mẫu<br>ưng ý?</h3>
         <p class="text-sm text-sky-100/70 mt-2 max-w-xs">Lọc theo size, giá và đối tượng trong từng bộ sưu tập.</p>
         <div class="flex flex-wrap gap-2 mt-5">
           <a href="#/shop/all" class="category-pill-btn px-5 py-3 rounded-full bg-white text-slate-950 text-xs font-extrabold">Xem tất cả sản phẩm →</a>
           <button type="button" data-sc-goto="flashSaleSection" class="px-5 py-3 rounded-full border border-white/30 text-white text-xs font-extrabold hover:bg-white/10">Săn Sale</button>
         </div>
       </div>`;

    if (window.lucide) window.lucide.createIcons();

    track.addEventListener("click", (e) => {
      const go = e.target.closest("[data-sc-goto]");
      if (go) { scrollToId(go.dataset.scGoto); return; }
      const card = e.target.closest("[data-slug]");
      if (card && !track.dataset.dragMoved) openProduct(card.dataset.slug);
    });

    // Spotlight glare follows the cursor (Aceternity card spotlight)
    if (finePointer) {
      track.addEventListener("mousemove", (e) => {
        const card = e.target.closest(".sc-card");
        if (!card) return;
        const r = card.getBoundingClientRect();
        card.style.setProperty("--glare-x", `${((e.clientX - r.left) / r.width) * 100}%`);
        card.style.setProperty("--glare-y", `${((e.clientY - r.top) / r.height) * 100}%`);
      });
    }

    state.showcaseCards = Array.from(track.querySelectorAll(".sc-card"));
    setupShowcaseMotion(track, hot.length, trending.length);
  }

  function setShowcaseMode(mode) {
    if (state.showcaseMode === mode) return;
    state.showcaseMode = mode;
    const title = document.getElementById("showcaseModeTitle");
    const desc = document.getElementById("showcaseModeDesc");
    document.getElementById("scPillHot")?.classList.toggle("is-active", mode === "hot");
    document.getElementById("scPillTrend")?.classList.toggle("is-active", mode === "trend");
    const apply = () => {
      if (title) title.textContent = mode === "hot" ? "Đang Hot Nhất" : "Đang Thịnh Hành";
      if (desc) desc.textContent = mode === "hot"
        ? "Những mẫu được khách hàng chọn mua nhiều nhất."
        : "Xu hướng mới nổi được săn đón trong 30 ngày qua.";
    };
    if (!gsap || reduceMotion) return apply();
    gsap.to([title, desc], {
      y: -14, opacity: 0, duration: 0.2, ease: "power2.in", stagger: 0.03,
      onComplete: () => {
        apply();
        gsap.fromTo([title, desc], { y: 14, opacity: 0 }, { y: 0, opacity: 1, duration: 0.45, ease: "expo.out", stagger: 0.04 });
      },
    });
  }

  function updateShowcaseHud(progress, viewportCenterX) {
    const bar = document.getElementById("scProgressBar");
    if (bar) bar.style.transform = `scaleX(${Math.max(0, Math.min(1, progress)).toFixed(4)})`;

    let current = null;
    for (const card of state.showcaseCards) {
      const r = card.getBoundingClientRect();
      if (r.left <= viewportCenterX) current = card;
      else break;
    }
    current = current || state.showcaseCards[0];
    if (!current) return;
    const kind = current.dataset.scKind;
    setShowcaseMode(kind === "trend" ? "trend" : "hot");
    const sameKind = state.showcaseCards.filter((c) => c.dataset.scKind === kind);
    const idx = sameKind.indexOf(current) + 1;
    const counter = document.getElementById("scCounter");
    if (counter) counter.textContent = `${pad2(idx)} / ${pad2(sameKind.length)}`;
  }

  function setupShowcaseMotion(track) {
    const section = document.getElementById("showcaseHot");
    const viewport = document.getElementById("showcaseViewport");
    if (!section || !viewport) return;

    const nativeMode = () => {
      viewport.classList.add("showcase-native-scroll");
      const onScroll = () => {
        const max = viewport.scrollWidth - viewport.clientWidth;
        updateShowcaseHud(max > 0 ? viewport.scrollLeft / max : 0, window.innerWidth / 2);
      };
      viewport.addEventListener("scroll", onScroll, { passive: true });
      onScroll();
      return () => {
        viewport.removeEventListener("scroll", onScroll);
        viewport.classList.remove("showcase-native-scroll");
      };
    };

    if (!gsap || !ST || reduceMotion) {
      nativeMode();
      return;
    }

    const mm = gsap.matchMedia();

    mm.add("(min-width: 768px) and (min-height: 540px)", () => {
      const distance = () => Math.max(0, track.scrollWidth - window.innerWidth);

      const tween = gsap.to(track, {
        x: () => -distance(),
        ease: "none",
        scrollTrigger: {
          trigger: section,
          start: () => `top ${headerOffset()}px`,
          end: () => `+=${distance()}`,
          pin: true,
          scrub: 0.9,
          anticipatePin: 1,
          invalidateOnRefresh: true,
          onUpdate: (self) => updateShowcaseHud(self.progress, window.innerWidth / 2),
          onToggle: (self) => document.body.classList.toggle("is-immersive", self.isActive),
        },
      });

      // Each card: zoom-in + un-rotate as it slides to centre, zoom-out as it leaves
      track.querySelectorAll(".sc-card").forEach((card) => {
        gsap.timeline({
          scrollTrigger: { trigger: card, containerAnimation: tween, start: "left right", end: "right left", scrub: true },
        })
          .fromTo(card, { scale: 0.8, rotationY: -18, opacity: 0.35 }, { scale: 1, rotationY: 0, opacity: 1, ease: "power2.out", duration: 0.42 })
          .to(card, { scale: 1, duration: 0.16 })
          .to(card, { scale: 0.88, rotationY: 14, opacity: 0.5, ease: "power1.in", duration: 0.42 });

        const img = card.querySelector(".sc-card-img img");
        if (img) {
          gsap.fromTo(img, { xPercent: -8 }, {
            xPercent: 8, ease: "none",
            scrollTrigger: { trigger: card, containerAnimation: tween, start: "left right", end: "right left", scrub: true },
          });
        }
      });

      // Outline words drift for depth
      track.querySelectorAll(".sc-outline-word").forEach((w) => {
        gsap.fromTo(w, { xPercent: 12 }, {
          xPercent: -12, ease: "none",
          scrollTrigger: { trigger: w, containerAnimation: tween, start: "left right", end: "right left", scrub: true },
        });
      });

      gsap.set(track.querySelectorAll(".sc-card"), { transformPerspective: 1200 });
      updateShowcaseHud(0, window.innerWidth / 2);
      return () => document.body.classList.remove("is-immersive");
    });

    mm.add("(max-width: 767px), (max-height: 539px)", () => nativeMode());
  }

  // --------------------------------------------------------------------------
  // 4. FLASH SALE: drag rail có quán tính, countdown thật, velocity marquee
  // --------------------------------------------------------------------------
  function saleCardHtml(p) {
    const sold = Number(p.sold_count || 0);
    const stock = Number(p.total_stock || 0);
    const soldPct = sold + stock > 0 ? Math.round((sold / (sold + stock)) * 100) : 0;
    return `
      <article class="sale-card cursor-pointer" data-slug="${esc(p.slug)}" data-tilt>
        <div class="sale-card-img">
          <img src="${esc(p.image_url)}" alt="${esc(p.name)}" loading="lazy" draggable="false">
          <span class="absolute top-3 left-3 px-2.5 py-1 rounded-full bg-gradient-to-r from-rose-600 to-orange-500 text-white text-[11px] font-black shadow">-${Math.round(p.discount_percent)}%</span>
        </div>
        <div class="p-3.5 space-y-2">
          <h3 class="font-extrabold text-[13px] leading-snug line-clamp-2 min-h-[2.4rem] text-slate-900">${esc(p.name)}</h3>
          <div class="flex items-baseline gap-1.5">
            <span class="text-base font-black text-rose-600">${money(p.discounted_price)}</span>
            <span class="text-[11px] text-slate-400 line-through">${money(p.base_price)}</span>
          </div>
          <span class="block text-[11px] font-bold text-emerald-600">Tiết kiệm ${money(p.base_price - p.discounted_price)}</span>
          <div class="sale-stock-bar"><span style="width:${Math.max(6, soldPct)}%"></span></div>
          <div class="flex justify-between text-[10px] font-bold text-slate-500">
            <span>${sold > 0 ? `Đã bán ${sold}` : "Vừa mở bán"}</span>
            <span class="${stock <= 5 ? "text-rose-600" : ""}">Còn ${stock} chiếc</span>
          </div>
        </div>
      </article>`;
  }

  function bindDragRail(rail) {
    let down = false, startX = 0, startLeft = 0, lastX = 0, lastT = 0, vel = 0, moved = 0;

    rail.addEventListener("pointerdown", (e) => {
      if (e.pointerType !== "mouse" || e.button !== 0) return;
      down = true; moved = 0;
      startX = lastX = e.clientX; startLeft = rail.scrollLeft; lastT = performance.now(); vel = 0;
      if (gsap) gsap.killTweensOf(rail);
    });
    window.addEventListener("pointermove", (e) => {
      if (!down) return;
      const dx = e.clientX - startX;
      moved = Math.max(moved, Math.abs(dx));
      if (moved > 5) rail.classList.add("is-dragging");
      rail.scrollLeft = startLeft - dx;
      const now = performance.now();
      const dt = Math.max(1, now - lastT);
      vel = (e.clientX - lastX) / dt;
      lastX = e.clientX; lastT = now;
    });
    window.addEventListener("pointerup", () => {
      if (!down) return;
      down = false;
      rail.classList.remove("is-dragging");
      rail.dataset.dragMoved = moved > 5 ? "1" : "";
      setTimeout(() => (rail.dataset.dragMoved = ""), 60);
      if (gsap && Math.abs(vel) > 0.05) {
        gsap.to(rail, { scrollLeft: rail.scrollLeft - vel * 420, duration: 1.1, ease: "power3.out" });
      }
    });
  }

  function nudgeSaleRail(dir) {
    const rail = document.getElementById("saleRail");
    if (!rail) return;
    const target = rail.scrollLeft + dir * rail.clientWidth * 0.75;
    if (gsap) gsap.to(rail, { scrollLeft: target, duration: 0.95, ease: "power3.inOut", overwrite: true });
    else rail.scrollBy({ left: dir * rail.clientWidth * 0.75, behavior: "smooth" });
    if (typeof window.playRefreshingSelectSound === "function") window.playRefreshingSelectSound("select");
  }

  function startCountdown(endsAtIso) {
    const wrap = document.getElementById("saleCountdownWrap");
    if (!wrap || !endsAtIso) return;
    const end = new Date(endsAtIso).getTime();
    if (!isFinite(end)) return;
    const tick = () => {
      const diff = end - Date.now();
      if (diff <= 0) {
        wrap.classList.add("hidden");
        wrap.classList.remove("flex");
        clearInterval(state.countdownTimer);
        return;
      }
      const s = Math.floor(diff / 1000);
      document.getElementById("cdDays").textContent = pad2(Math.floor(s / 86400));
      document.getElementById("cdHours").textContent = pad2(Math.floor((s % 86400) / 3600));
      document.getElementById("cdMins").textContent = pad2(Math.floor((s % 3600) / 60));
      document.getElementById("cdSecs").textContent = pad2(s % 60);
    };
    wrap.classList.remove("hidden");
    wrap.classList.add("flex");
    tick();
    clearInterval(state.countdownTimer);
    state.countdownTimer = setInterval(tick, 1000);
  }

  function renderVelocityMarquee(products) {
    const rows = [document.getElementById("velocityRowA"), document.getElementById("velocityRowB")];
    if (!rows[0] || !products.length) return;
    const chip = (p) => `
      <span class="velocity-chip" data-slug="${esc(p.slug)}">
        <img src="${esc(p.image_url)}" alt="" loading="lazy">
        <span>${esc(p.name)}</span>
        <span class="${p.discount_percent > 0 ? "text-rose-600" : "text-sky-600"}">${money(p.discount_percent > 0 ? p.discounted_price : p.base_price)}</span>
      </span>`;
    const half = Math.ceil(products.length / 2);
    const sets = [products.slice(0, half), products.slice(half).length ? products.slice(half) : products.slice(0, half)];

    state.velocityRows = rows.map((row, k) => {
      const html = sets[k].map(chip).join("");
      row.innerHTML = html + html; // duplicated for seamless loop
      row.addEventListener("click", (e) => {
        const c = e.target.closest("[data-slug]");
        if (c) openProduct(c.dataset.slug);
      });
      const dir = Number(row.parentElement.getAttribute("data-velocity-marquee") || 1);
      return {
        el: row, dir, x: 0,
        setX: gsap ? gsap.quickSetter(row, "x", "px") : null,
        skew: gsap ? gsap.quickTo(row, "skewX", { duration: 0.5, ease: "power3.out" }) : null,
      };
    });

    if (!gsap || reduceMotion) return;

    if (ST) {
      ST.create({
        trigger: "#flashSaleSection",
        start: "top bottom",
        end: "bottom top",
        onToggle: (self) => (state.velocityActive = self.isActive),
      });
    }

    gsap.ticker.add((time, deltaTime) => {
      if (!state.velocityActive) return;
      const lenis = window.soobinLenis;
      const v = lenis ? lenis.velocity || 0 : 0;
      const scrollDir = lenis && lenis.direction ? lenis.direction : 1;
      const speed = (0.045 + Math.min(Math.abs(v), 40) * 0.012) * deltaTime;
      state.velocityRows.forEach((r) => {
        const half = r.el.scrollWidth / 2;
        if (!half) return;
        r.x -= speed * r.dir * scrollDir;
        if (r.x <= -half) r.x += half;
        if (r.x > 0) r.x -= half;
        r.setX(r.x);
        r.skew(Math.max(-8, Math.min(8, -v * 0.35 * r.dir)));
      });
    });
  }

  function renderSale(data) {
    const section = document.getElementById("flashSaleSection");
    const rail = document.getElementById("saleRail");
    const sale = data.sale || [];
    if (!section || !rail) return;
    if (!sale.length) {
      section.classList.add("hidden");
      return;
    }
    section.classList.remove("hidden");
    const maxPct = document.getElementById("saleMaxPct");
    if (maxPct) maxPct.textContent = String(Math.round(Math.max(...sale.map((p) => p.discount_percent))));

    rail.innerHTML = sale.map(saleCardHtml).join("");
    rail.addEventListener("click", (e) => {
      if (rail.dataset.dragMoved) return;
      const card = e.target.closest("[data-slug]");
      if (card) openProduct(card.dataset.slug);
    });
    bindDragRail(rail);
    startCountdown(data.sale_ends_at);

    const seen = new Set();
    const pool = [...(data.hot || []), ...(data.trending || []), ...sale].filter((p) => !seen.has(p.id) && seen.add(p.id));
    renderVelocityMarquee(pool);

    if (gsap && ST && !reduceMotion) {
      gsap.fromTo(
        rail.querySelectorAll(".sale-card"),
        { x: 120, opacity: 0, scale: 0.88, rotationY: -12 },
        {
          x: 0, opacity: 1, scale: 1, rotationY: 0, duration: 1, ease: "expo.out", stagger: 0.07,
          scrollTrigger: { trigger: rail, start: "top 85%", toggleActions: "play none none reverse" },
        }
      );
    }
    bindTilt(rail.querySelectorAll("[data-tilt]"));
  }

  // --------------------------------------------------------------------------
  // 4b. HOME SCROLL STORY: lặn xuống biển, cửa sổ bãi biển, cổng danh mục
  // --------------------------------------------------------------------------
  /** Quạt thẻ Hot dãn ra theo tiến trình cuộn trang bìa (0 → 0.5). */
  function spreadCoverCards(p) {
    if (!gsap || !state.coverCards.length) return;
    const e = Math.min(1, Math.max(0, p / 0.5));
    const layout = coverLayout();
    state.coverCards.forEach((c) => {
      const idx = Number(c.dataset.idx);
      const L = layout[idx];
      const dir = idx === 1 ? -1 : idx === 2 ? 1 : 0;
      gsap.set(c, { xPercent: L.xPercent + dir * 28 * e, rotation: L.rotation + dir * 7 * e });
    });
  }

  /**
   * Trang bìa: ghim lại (desktop) — chữ zoom-in rồi tan biến, mặt trời & mây
   * bay lên, quạt sản phẩm dãn ra rồi chìm xuống, camera Three.js lặn dưới
   * mặt nước và chuyển màu sang nền "đại dương sâu" của phần Showcase.
   */
  function initCoverScroll() {
    const cover = document.getElementById("storeCover");
    if (!cover) return;
    if (!gsap || !ST || reduceMotion) return;

    const mm = gsap.matchMedia();
    mm.add({ desktop: "(min-width: 1024px)", mobile: "(max-width: 1023px)" }, (ctx) => {
      const { desktop } = ctx.conditions;
      const tl = gsap.timeline({
        defaults: { ease: "none" },
        scrollTrigger: {
          trigger: cover,
          start: () => (desktop ? `top ${headerOffset()}px` : "top top"),
          end: () => (desktop ? "+=110%" : "bottom top"),
          pin: desktop,
          scrub: 0.8,
          anticipatePin: 1,
          invalidateOnRefresh: true,
          onUpdate: (self) => {
            state.coverProgress = self.progress;
            if (window.soobinOcean) window.soobinOcean.setDive(self.progress);
            spreadCoverCards(self.progress);
          },
        },
      });
      tl.to(".cover-scroll-hint", { opacity: 0, y: 24, duration: 0.12 }, 0)
        .to("#coverTextCol", { scale: 1.3, yPercent: -16, opacity: 0, filter: "blur(4px)", duration: 0.5 }, 0)
        .to(".cover-sun", { yPercent: -150, scale: 1.45, duration: 1 }, 0)
        .to(".cover-cloud-a", { xPercent: -70, yPercent: -90, scale: 1.35, duration: 1 }, 0)
        .to(".cover-cloud-b", { xPercent: 70, yPercent: -70, scale: 1.3, duration: 1 }, 0)
        .to(".cover-gulls", { xPercent: 90, yPercent: -140, duration: 1 }, 0)
        .to(".cover-sky", { opacity: 0, duration: 0.35 }, 0.35)
        .to("#coverStage", { scale: 1.16, duration: 0.5 }, 0)
        .to("#coverStage", { yPercent: 75, scale: 0.72, opacity: 0, duration: 0.42 }, 0.55)
        .to("#coverDiveShade", { opacity: 1, duration: 0.3 }, 0.62)
        .fromTo("#coverDiveCaption", { opacity: 0, scale: 0.8 }, { opacity: 1, scale: 1, duration: 0.2, ease: "power2.out" }, 0.74)
        .to("#coverDiveCaption", { opacity: 0, scale: 1.25, duration: 0.1 }, 0.92);
      return () => {
        if (window.soobinOcean) window.soobinOcean.setDive(0);
      };
    });
  }

  /** Đặt tâm scale của từng lớp cảnh về giữa khung để zoom-out đồng tâm. */
  function syncBeachOrigins() {
    const win = document.getElementById("bzWindow");
    if (!win || !gsap) return;
    const cx = win.clientWidth / 2;
    const cy = win.clientHeight * 0.55;
    win.querySelectorAll("[data-depth]").forEach((layer) => {
      const ox = cx - layer.offsetLeft;
      const oy = cy - layer.offsetTop;
      gsap.set(layer, { transformOrigin: `${ox}px ${oy}px` });
    });
  }

  /**
   * Cửa sổ bãi biển: một vòng tròn nhỏ giữa nền đại dương sâu mở rộng ra toàn
   * màn hình, trong khi từng lớp cảnh (mặt trời, mây, sóng, cát, cây dừa…)
   * zoom-out với tốc độ khác nhau tạo chiều sâu; cuối cùng lời kêu gọi xuất hiện.
   */
  function initBeachZoom() {
    const section = document.getElementById("beachZoom");
    const win = document.getElementById("bzWindow");
    if (!section || !win || section.dataset.bzBound) return;
    section.dataset.bzBound = "1";

    if (!gsap || !ST || reduceMotion) {
      section.classList.add("bz-static");
      return;
    }

    const layers = Array.from(win.querySelectorAll("[data-depth]"));
    const mm = gsap.matchMedia();

    mm.add("(min-width: 768px)", () => {
      syncBeachOrigins();
      const tl = gsap.timeline({
        defaults: { ease: "none" },
        scrollTrigger: {
          trigger: section,
          start: () => `top ${headerOffset()}px`,
          end: "+=150%",
          pin: true,
          scrub: 0.8,
          anticipatePin: 1,
          invalidateOnRefresh: true,
          onRefreshInit: syncBeachOrigins,
        },
      });
      tl.fromTo(win, { "--bz-r": "10%" }, { "--bz-r": "82%", duration: 0.62, ease: "power1.in" }, 0)
        .fromTo("#bzIntro", { scale: 1, opacity: 1 }, { scale: 0.5, opacity: 0, duration: 0.38 }, 0.04);
      layers.forEach((layer) => {
        const depth = Number(layer.dataset.depth) || 1.4;
        tl.fromTo(layer, { scale: depth }, { scale: 1, duration: 0.78, ease: "power2.out" }, 0);
      });
      tl.fromTo("#bzCopy", { scale: 1.35, opacity: 0, y: 30 }, { scale: 1, opacity: 1, y: 0, duration: 0.24, ease: "power2.out" }, 0.62)
        .to({}, { duration: 0.14 });
      return () => {};
    });

    mm.add("(max-width: 767px)", () => {
      section.classList.add("bz-static");
      return () => section.classList.remove("bz-static");
    });
  }

  /** Cổng danh mục: thẻ zoom-in từ xa (ảnh bên trong zoom-out ngược chiều). */
  function initCategoryZoom() {
    const grid = document.getElementById("catGrid");
    if (!grid || grid.dataset.zoomBound || !gsap || !ST || reduceMotion) return;
    grid.dataset.zoomBound = "1";

    grid.querySelectorAll(".cat-tile").forEach((tile, i) => {
      const media = tile.querySelector(".cat-tile-media img");
      const illus = tile.querySelector(".cat-tile-illus");
      const tl = gsap.timeline({
        scrollTrigger: { trigger: grid, start: "top 98%", end: "top 30%", scrub: 0.7 },
      });
      tl.fromTo(
        tile,
        { scale: 0.7, y: 160 + i * 50, rotationX: 24, opacity: 0.15, transformPerspective: 1200, transformOrigin: "50% 100%" },
        { scale: 1, y: 0, rotationX: 0, opacity: 1, ease: "power2.out", duration: 1 },
        i * 0.08
      );
      if (media) tl.fromTo(media, { scale: 1.5 }, { scale: 1.06, ease: "none", duration: 1 }, i * 0.08);
      if (illus) tl.fromTo(illus, { scale: 0, rotation: -45 }, { scale: 1, rotation: 0, ease: "back.out(1.7)", duration: 0.5 }, 0.45 + i * 0.08);

      // Zoom-out nhẹ khi cuộn qua khỏi màn hình
      gsap.fromTo(tile, { scale: 1, opacity: 1 }, {
        scale: 0.9, opacity: 0.4, ease: "none", immediateRender: false,
        scrollTrigger: { trigger: tile, start: "bottom 40%", end: "bottom top", scrub: 0.6 },
      });
    });
  }

  /** Hình vẽ trang trí (sao biển, vỏ sò, phao…) trôi nhẹ theo cuộn. */
  function initDecorParallax(root = document) {
    if (!gsap || !ST || reduceMotion) return;
    root.querySelectorAll("#homeView [data-parallax]").forEach((el) => {
      if (el.dataset.pxBound) return;
      el.dataset.pxBound = "1";
      const amt = Number(el.dataset.parallax) || 60;
      gsap.fromTo(el, { y: -amt / 2, rotation: -10 }, {
        y: amt, rotation: 14, ease: "none",
        scrollTrigger: { trigger: el.parentElement, start: "top bottom", end: "bottom top", scrub: true },
      });
    });
  }

  // --------------------------------------------------------------------------
  // 5. MICRO-INTERACTIONS: magnetic CTA, 3D tilt, cursor label, back-to-top
  // --------------------------------------------------------------------------
  function bindMagnetic() {
    if (!gsap || !finePointer || reduceMotion) return;
    document.querySelectorAll("[data-magnetic]").forEach((btn) => {
      if (btn.dataset.magBound) return;
      btn.dataset.magBound = "1";
      const xTo = gsap.quickTo(btn, "x", { duration: 0.5, ease: "power3.out" });
      const yTo = gsap.quickTo(btn, "y", { duration: 0.5, ease: "power3.out" });
      btn.addEventListener("mousemove", (e) => {
        const r = btn.getBoundingClientRect();
        xTo((e.clientX - (r.left + r.width / 2)) * 0.3);
        yTo((e.clientY - (r.top + r.height / 2)) * 0.4);
      });
      btn.addEventListener("mouseleave", () => {
        gsap.to(btn, { x: 0, y: 0, duration: 0.9, ease: "elastic.out(1, 0.4)" });
      });
    });
  }

  function bindTilt(nodes) {
    if (!gsap || !finePointer || reduceMotion) return;
    nodes.forEach((el) => {
      if (el.dataset.tiltBound) return;
      el.dataset.tiltBound = "1";
      gsap.set(el, { transformPerspective: 900 });
      const rx = gsap.quickTo(el, "rotationX", { duration: 0.5, ease: "power3.out" });
      const ry = gsap.quickTo(el, "rotationY", { duration: 0.5, ease: "power3.out" });
      el.addEventListener("mousemove", (e) => {
        const r = el.getBoundingClientRect();
        ry(((e.clientX - r.left) / r.width - 0.5) * 12);
        rx(-((e.clientY - r.top) / r.height - 0.5) * 10);
      });
      el.addEventListener("mouseleave", () => { rx(0); ry(0); });
    });
  }

  function initCursorLabel() {
    if (!gsap || !finePointer || reduceMotion) return;
    const label = document.createElement("div");
    label.className = "soobin-cursor-label";
    document.body.appendChild(label);
    const xTo = gsap.quickTo(label, "x", { duration: 0.35, ease: "power3.out" });
    const yTo = gsap.quickTo(label, "y", { duration: 0.35, ease: "power3.out" });
    let current = null;
    window.addEventListener("mousemove", (e) => {
      xTo(e.clientX + 18);
      yTo(e.clientY + 18);
      const host = e.target.closest ? e.target.closest("[data-cursor-label]") : null;
      if (host !== current) {
        current = host;
        if (host) {
          label.textContent = host.getAttribute("data-cursor-label");
          gsap.to(label, { opacity: 1, scale: 1, duration: 0.3, ease: "back.out(2)" });
        } else {
          gsap.to(label, { opacity: 0, scale: 0.4, duration: 0.25, ease: "power2.in" });
        }
      }
    }, { passive: true });
  }

  function initBackToTop() {
    if (document.getElementById("soobinBackToTop")) return;
    const btn = document.createElement("button");
    btn.id = "soobinBackToTop";
    btn.type = "button";
    btn.setAttribute("aria-label", "Lên đầu trang");
    const C = 2 * Math.PI * 22;
    btn.innerHTML = `
      <svg class="btt-ring" width="50" height="50" viewBox="0 0 50 50">
        <circle cx="25" cy="25" r="22" fill="none" stroke="#e0f2fe" stroke-width="3"></circle>
        <circle id="soobinBttRing" cx="25" cy="25" r="22" fill="none" stroke="#0284c7" stroke-width="3" stroke-linecap="round"
                stroke-dasharray="${C.toFixed(2)}" stroke-dashoffset="${C.toFixed(2)}"></circle>
      </svg>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m18 15-6-6-6 6"/></svg>`;
    document.body.appendChild(btn);
    const ring = btn.querySelector("#soobinBttRing");
    btn.addEventListener("click", () => {
      if (window.soobinLenis) window.soobinLenis.scrollTo(0, { duration: 1.6 });
      else window.scrollTo({ top: 0, behavior: "smooth" });
    });
    const update = () => {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      const p = max > 0 ? window.scrollY / max : 0;
      ring.setAttribute("stroke-dashoffset", (C * (1 - p)).toFixed(2));
      btn.classList.toggle("is-visible", window.scrollY > window.innerHeight * 0.8);
    };
    if (window.soobinLenis) window.soobinLenis.on("scroll", update);
    else window.addEventListener("scroll", update, { passive: true });
    update();
  }

  // --------------------------------------------------------------------------
  // 6. BOOT + VIEW SWITCHING (home ⇄ shop)
  // --------------------------------------------------------------------------
  function disableAllTriggers() {
    if (ST) ST.getAll().forEach((t) => t.disable());
  }

  async function loadShowcase() {
    let data = null;
    try {
      const res = await fetch("/api/v1/catalog/showcase?per_rail=8");
      if (!res.ok) throw new Error("showcase");
      data = await res.json();
      state.showcase = data;
      renderCover(data);
      renderShowcase(data);
    } catch (_) {
      document.getElementById("showcaseHot")?.classList.add("hidden");
    }
    // Create remaining triggers in page order (after the pinned showcase)
    initBeachZoom();
    initCategoryZoom();
    if (data) renderSale(data);
    initZoomReveal();
    initDecorParallax();
    bindMagnetic();
    if (window.lucide) window.lucide.createIcons();
    if (ST && typeof ST.sort === "function") ST.sort();
    scheduleRefresh();
    // Customer may have opened a category while the showcase was loading
    if (state.view === "shop") disableAllTriggers();
  }

  function buildHome() {
    if (state.homeBuilt) return;
    state.homeBuilt = true;
    coverIntro();
    initCoverScroll();
    loadShowcase();
  }

  /** Được app.js gọi khi đổi route: "home" bật lại hiệu ứng, "shop" tắt hết. */
  function setView(view) {
    state.view = view;
    if (!state.booted) return; // boot() will read state.view
    if (view === "shop") {
      disableAllTriggers();
      document.body.classList.remove("is-immersive");
      if (window.soobinOcean) window.soobinOcean.pause();
      return;
    }
    if (window.soobinOcean) window.soobinOcean.resume();
    if (!state.homeBuilt) {
      buildHome();
      return;
    }
    requestAnimationFrame(() => {
      if (!ST) return;
      ST.getAll().forEach((t) => t.enable());
      syncHeaderVar();
      ST.refresh();
    });
  }

  function boot() {
    if (!document.getElementById("storeCover")) return; // storefront only
    syncHeaderVar();
    if (gsap && ST) gsap.registerPlugin(ST);
    state.booted = true;
    state.view = state.view || document.body.dataset.view || "home";

    bindMagnetic();
    initCursorLabel();
    initBackToTop();

    if (state.view === "shop") {
      if (window.soobinOcean) window.soobinOcean.pause();
    } else {
      buildHome();
    }

    // Keep trigger positions correct when async content changes page height
    if ("ResizeObserver" in window) {
      let lastH = document.body.scrollHeight;
      new ResizeObserver(() => {
        const h = document.body.scrollHeight;
        if (Math.abs(h - lastH) > 4) {
          lastH = h;
          syncHeaderVar();
          if (state.view !== "shop") scheduleRefresh();
        }
      }).observe(document.body);
    }
    window.addEventListener("load", () => { if (state.view !== "shop") scheduleRefresh(); });
  }

  window.soobinMotion = { revealCards, scrollToId, nudgeSaleRail, refresh: scheduleRefresh, initZoomReveal, setView };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
