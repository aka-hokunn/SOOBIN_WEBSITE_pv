(() => {
  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function notify(message, tone = "info") {
    let root = document.getElementById("app-notices");
    if (!root) {
      root = document.createElement("div");
      root.id = "app-notices";
      root.className = "fixed right-4 top-4 z-[100] flex w-[min(92vw,380px)] flex-col gap-2";
      root.setAttribute("aria-live", "polite");
      document.body.appendChild(root);
    }
    const styles = tone === "error" ? "border-rose-300 bg-rose-50 text-rose-900" : tone === "success" ? "border-emerald-300 bg-emerald-50 text-emerald-900" : "border-sky-300 bg-white text-slate-800";
    const item = document.createElement("div");
    item.className = `app-notice flex items-start gap-3 rounded-2xl border p-4 shadow-xl backdrop-blur ${styles}`;
    item.innerHTML = `<span class="mt-0.5 text-lg">${tone === "error" ? "!" : tone === "success" ? "✓" : "✦"}</span><p class="flex-1 text-sm font-semibold leading-5">${escapeHtml(message)}</p><button type="button" aria-label="Đóng thông báo" class="font-bold opacity-60 hover:opacity-100">×</button>`;
    item.querySelector("button").onclick = () => item.remove();
    root.appendChild(item);
    setTimeout(() => item.remove(), 4200);
  }

  function dialog({ title, message, input, initialValue }) {
    return new Promise(resolve => {
      const overlay = document.createElement("div");
      overlay.className = "fixed inset-0 z-[110] grid place-items-center bg-slate-950/55 p-4 backdrop-blur-sm";
      overlay.innerHTML = `<section class="app-dialog w-full max-w-md rounded-3xl border border-white/60 bg-white p-6 shadow-2xl"><div class="mb-4 flex items-start gap-3"><span class="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-sky-500 to-indigo-600 text-white">✦</span><div><h2 class="text-lg font-extrabold text-slate-900">${escapeHtml(title)}</h2><p class="mt-1 text-sm leading-6 text-slate-600">${escapeHtml(message)}</p></div></div>${input ? `<input class="app-dialog-input mb-5 w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-sky-500" value="${escapeHtml(initialValue || "")}" />` : ""}<div class="flex justify-end gap-2"><button data-cancel class="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-600 hover:bg-slate-50">${input ? "Hủy" : "Không"}</button><button data-accept class="rounded-xl bg-gradient-to-r from-sky-600 to-indigo-600 px-4 py-2 text-sm font-bold text-white shadow-lg shadow-sky-900/20">${input ? "Tiếp tục" : "Đồng ý"}</button></div></section>`;
      document.body.appendChild(overlay);
      const field = overlay.querySelector("input");
      const finish = value => { overlay.remove(); resolve(value); };
      overlay.querySelector("[data-cancel]").onclick = () => finish(input ? null : false);
      overlay.querySelector("[data-accept]").onclick = () => finish(input ? field.value : true);
      overlay.addEventListener("click", event => { if (event.target === overlay) finish(input ? null : false); });
      if (field) { field.focus(); field.select(); }
    });
  }

  window.notify = notify;
  window.confirmDialog = message => dialog({ title: "Xác nhận thao tác", message });
  window.promptDialog = (message, initialValue = "") => dialog({ title: "Thông tin cần nhập", message, input: true, initialValue });
  window.alert = message => notify(message, /lỗi|không thể|thất bại|bị từ chối/i.test(String(message)) ? "error" : "info");

  const style = document.createElement("style");
  style.textContent = `@keyframes notice-in{from{opacity:0;transform:translate3d(22px,-8px,0) scale(.97)}to{opacity:1;transform:translate3d(0,0,0) scale(1)}}@keyframes dialog-in{from{opacity:0;transform:translateY(14px) scale(.97)}to{opacity:1;transform:translateY(0) scale(1)}}@keyframes page-arrive{from{opacity:.7}to{opacity:1}}body{animation:page-arrive .35s ease-out}button:not(:disabled){transition:transform .18s ease,filter .18s ease,box-shadow .18s ease}button:not(:disabled):hover{filter:brightness(1.04)}button:not(:disabled):active{transform:scale(.985)}.app-notice{animation:notice-in .25s cubic-bezier(.2,.8,.2,1)}.app-dialog{animation:dialog-in .22s ease-out}@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;transition-duration:.01ms!important;scroll-behavior:auto!important}}`;
  document.head.appendChild(style);
})();
