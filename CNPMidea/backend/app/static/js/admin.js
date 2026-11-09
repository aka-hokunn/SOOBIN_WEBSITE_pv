// =============================================================================
// Soobin Swimwear - Admin & Manager Portal Controller
// =============================================================================

let allVariants = [];
let allSuppliers = [];

document.addEventListener("DOMContentLoaded", () => {
  loadDashboardData();
  loadSuppliers();
  loadVariantsForReceipt();
});

function switchTab(tab) {
  const tabs = ['dashboard', 'orders', 'refunds', 'inventory', 'users'];
  tabs.forEach(t => {
    const btn = document.getElementById(`btnTab${capitalize(t)}`);
    const content = document.getElementById(`tabContent${capitalize(t)}`);
    if (t === tab) {
      if (btn) btn.className = "px-3 py-1.5 text-xs font-bold rounded-lg bg-sky-600 text-white transition flex items-center gap-1.5";
      if (content) content.classList.remove("hidden");
    } else {
      if (btn) btn.className = "px-3 py-1.5 text-xs font-bold rounded-lg hover:bg-slate-800 text-slate-300 transition flex items-center gap-1.5";
      if (content) content.classList.add("hidden");
    }
  });

  if (tab === 'dashboard') loadDashboardData();
  if (tab === 'orders') loadAdminOrders();
  if (tab === 'refunds') loadAdminRefunds();
  if (tab === 'inventory') { loadInventoryBalances(); }
  if (tab === 'users') loadAdminUsers();
}

function capitalize(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// -----------------------------------------------------------------------------
// 1. DASHBOARD
// -----------------------------------------------------------------------------

async function loadDashboardData() {
  try {
    const res = await fetch("/api/v1/reports/dashboard");
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById("kpiRevenue").innerText = formatCurrency(data.total_delivered_revenue);
    document.getElementById("kpiProfit").innerText = formatCurrency(data.total_delivered_profit);
    document.getElementById("kpiLowStock").innerText = data.low_stock_items.length;
    document.getElementById("kpiCatalog").innerText = `${data.total_products} / ${data.total_suppliers}`;

    // Status distribution
    const statusBox = document.getElementById("statusDistribution");
    const statuses = Object.entries(data.orders_by_status);
    if (statuses.length === 0) {
      statusBox.innerHTML = `<div class="text-xs text-slate-400">Chưa có đơn hàng nào trong hệ thống.</div>`;
    } else {
      statusBox.innerHTML = statuses.map(([st, count]) => `
        <div class="flex items-center justify-between text-xs p-2 bg-slate-50 rounded-lg">
          <span class="font-semibold text-slate-700">${st}</span>
          <span class="font-extrabold px-2 py-0.5 bg-white border rounded text-slate-900">${count} đơn</span>
        </div>
      `).join("");
    }

    // Top selling
    const topBox = document.getElementById("topSellingList");
    if (data.top_selling_products.length === 0) {
      topBox.innerHTML = `<div class="text-xs text-slate-400">Chưa có dữ liệu bán hàng đã giao.</div>`;
    } else {
      topBox.innerHTML = data.top_selling_products.map((p, idx) => `
        <div class="flex items-center justify-between p-2 bg-slate-50 rounded-lg">
          <div class="flex items-center gap-2">
            <span class="w-5 h-5 rounded-full bg-sky-100 text-sky-700 font-bold flex items-center justify-center text-[10px]">${idx + 1}</span>
            <span class="font-bold text-slate-800">${p.name}</span>
          </div>
          <div class="text-right">
            <span class="font-bold text-slate-900">${p.quantity_sold} cái</span>
            <span class="text-[10px] text-slate-500 block">${formatCurrency(p.revenue)}</span>
          </div>
        </div>
      `).join("");
    }

    lucide.createIcons();
  } catch (err) {}
}

// -----------------------------------------------------------------------------
// 2. ORDERS MANAGEMENT
// -----------------------------------------------------------------------------

async function loadAdminOrders() {
  const tbody = document.getElementById("adminOrdersTableBody");
  const filter = document.getElementById("adminOrderFilterStatus").value;
  let url = "/api/v1/orders";
  if (filter) url += `?status=${encodeURIComponent(filter)}`;

  try {
    const res = await fetch(url);
    const orders = await res.json();

    if (orders.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="p-6 text-center text-slate-400">Không có đơn hàng nào.</td></tr>`;
      return;
    }

    tbody.innerHTML = orders.map(o => `
      <tr class="border-b hover:bg-slate-50">
        <td class="p-3 font-mono font-bold text-sky-700">${o.code}</td>
        <td class="p-3">
          <span class="font-bold block">${o.recipient_name}</span>
          <span class="text-slate-500 text-[11px]">${o.recipient_phone}</span>
        </td>
        <td class="p-3">
          <span class="px-2 py-0.5 rounded-full font-bold text-[10px] ${getStatusBadge(o.status)}">${o.status}</span>
        </td>
        <td class="p-3">
          <span class="font-semibold block">${o.payment_method}</span>
          <span class="text-[10px] text-slate-500">${o.payment_status}</span>
        </td>
        <td class="p-3">
          ${o.tracking_code ? `<span class="font-mono text-emerald-700 font-bold">${o.tracking_code}</span>` : '<span class="text-slate-400">Chưa tạo</span>'}
        </td>
        <td class="p-3 font-extrabold text-slate-900">${formatCurrency(o.total_amount)}</td>
        <td class="p-3 text-right">
          ${o.status === "Chưa xử lý" ? `
            <button onclick="confirmAdminOrder(${o.id})" class="px-2.5 py-1 bg-sky-600 hover:bg-sky-700 text-white font-bold rounded text-[11px] transition">
              Xác Nhận Đơn
            </button>
          ` : '<span class="text-slate-400">-</span>'}
        </td>
      </tr>
    `).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="p-6 text-center text-rose-500">Lỗi khi tải danh sách đơn hàng.</td></tr>`;
  }
}

async function confirmAdminOrder(orderId) {
  try {
    const res = await fetch(`/api/v1/orders/${orderId}/confirm`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "Không thể xác nhận đơn.");
      return;
    }
    alert(data.message);
    loadAdminOrders();
    loadDashboardData();
  } catch (err) {
    alert("Lỗi khi kết nối đến máy chủ.");
  }
}

// -----------------------------------------------------------------------------
// 3. REFUNDS MANAGEMENT
// -----------------------------------------------------------------------------

async function loadAdminRefunds() {
  const tbody = document.getElementById("adminRefundsTableBody");
  try {
    const res = await fetch("/api/v1/orders/refunds/pending");
    const refunds = await res.json();

    if (refunds.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="p-6 text-center text-slate-400">Không có đơn hàng nào đang chờ hoàn tiền.</td></tr>`;
      return;
    }

    tbody.innerHTML = refunds.map(r => `
      <tr class="border-b hover:bg-slate-50">
        <td class="p-3 font-mono font-bold text-sky-700">${r.code}</td>
        <td class="p-3 font-bold">${r.customer_name}</td>
        <td class="p-3 font-mono text-slate-600">${r.customer_phone}</td>
        <td class="p-3 font-extrabold text-rose-600">${formatCurrency(r.refund_amount)}</td>
        <td class="p-3 text-slate-500">${new Date(r.placed_at).toLocaleDateString('vi-VN')}</td>
        <td class="p-3 text-right">
          <button onclick="markAdminRefund(${r.id})" class="px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded text-[11px] transition">
            Đã Chuyển Khoản Hoàn Tiền
          </button>
        </td>
      </tr>
    `).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="p-6 text-center text-rose-500">Lỗi tải danh sách hoàn tiền.</td></tr>`;
  }
}

async function markAdminRefund(orderId) {
  if (!(await confirmDialog("Bạn xác nhận đã chuyển khoản hoàn tiền thành công cho khách hàng ngoài hệ thống?"))) return;
  try {
    const res = await fetch(`/api/v1/orders/${orderId}/refund`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: "Quản lý xác nhận đã chuyển khoản ngân hàng hoàn tiền thành công." })
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "Không thể cập nhật hoàn tiền.");
      return;
    }
    alert(data.message);
    loadAdminRefunds();
    loadDashboardData();
  } catch (err) {
    alert("Lỗi khi kết nối.");
  }
}

// -----------------------------------------------------------------------------
// 4. GOODS RECEIPTS & INVENTORY
// -----------------------------------------------------------------------------

async function loadSuppliers() {
  const sel = document.getElementById("receiptSupplierSelect");
  if (!sel) return;
  try {
    const res = await fetch("/api/v1/inventory/suppliers");
    const sups = await res.json();
    allSuppliers = sups;
    sel.innerHTML = sups.map(s => `<option value="${s.id}">${s.name} (${s.code})</option>`).join("");
  } catch (err) {}
}

async function loadVariantsForReceipt() {
  try {
    const res = await fetch("/api/v1/inventory/balances");
    if (res.ok) {
      allVariants = await res.json();
      if (document.getElementById("receiptItemsContainer").children.length === 0) {
        addReceiptRow();
      }
    }
  } catch (err) {}
}

function addReceiptRow() {
  const container = document.getElementById("receiptItemsContainer");
  const rowId = Date.now();
  const row = document.createElement("div");
  row.className = "flex items-center gap-2 bg-slate-50 p-2 rounded-lg border";
  row.id = `receiptRow-${rowId}`;

  const options = allVariants.map(v => `<option value="${v.variant_id}">${v.product_name} - ${v.size_name} (${v.color_name}) [Tồn hiện tại: ${v.available_quantity}]</option>`).join("");

  row.innerHTML = `
    <select class="receipt-variant-select flex-1 text-xs p-1.5 border rounded bg-white outline-none">
      ${options}
    </select>
    <input type="number" min="1" value="10" placeholder="Số lượng" class="receipt-qty-input w-24 text-xs p-1.5 border rounded text-center font-bold">
    <input type="number" min="0" value="120000" placeholder="Đơn giá nhập" class="receipt-cost-input w-32 text-xs p-1.5 border rounded text-right font-bold">
    <button onclick="document.getElementById('receiptRow-${rowId}').remove()" class="p-1.5 text-rose-500 hover:text-rose-700">
      <i data-lucide="trash-2" class="w-4 h-4"></i>
    </button>
  `;
  container.appendChild(row);
  lucide.createIcons();
}

async function submitGoodsReceipt() {
  const supplierId = parseInt(document.getElementById("receiptSupplierSelect").value);
  const note = document.getElementById("receiptNoteInput").value;
  const container = document.getElementById("receiptItemsContainer");
  const rows = container.getElementsByClassName("flex");

  const items = [];
  for (const r of rows) {
    const vId = parseInt(r.querySelector(".receipt-variant-select").value);
    const qty = parseInt(r.querySelector(".receipt-qty-input").value);
    const cost = parseFloat(r.querySelector(".receipt-cost-input").value);
    if (vId && qty > 0 && cost >= 0) {
      items.push({ variant_id: vId, quantity: qty, unit_cost: cost });
    }
  }

  if (items.length === 0) {
    alert("Vui lòng thêm ít nhất một mặt hàng nhập hợp lệ.");
    return;
  }

  try {
    const res = await fetch("/api/v1/inventory/receipts/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ supplier_id: supplierId, note: note, items: items })
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "Không thể xác nhận phiếu nhập.");
      return;
    }
    alert(data.message);
    document.getElementById("receiptNoteInput").value = "";
    loadInventoryBalances();
    loadDashboardData();
  } catch (err) {
    alert("Lỗi khi kết nối.");
  }
}

async function loadInventoryBalances() {
  const tbody = document.getElementById("inventoryBalancesTableBody");
  try {
    const res = await fetch("/api/v1/inventory/balances");
    const balances = await res.json();
    allVariants = balances;

    tbody.innerHTML = balances.map(b => `
      <tr class="border-b hover:bg-slate-50 ${b.is_low_stock ? 'bg-rose-50/50' : ''}">
        <td class="p-3 font-mono font-bold">${b.sku}</td>
        <td class="p-3 font-bold">${b.product_name}</td>
        <td class="p-3 text-slate-600">${b.size_name} - ${b.color_name}</td>
        <td class="p-3 font-extrabold ${b.is_low_stock ? 'text-rose-600' : 'text-slate-900'}">${b.available_quantity} chiếc ${b.is_low_stock ? '<span class="text-[10px] bg-rose-100 text-rose-700 px-1 rounded ml-1 font-bold">TỒN THẤP</span>' : ''}</td>
        <td class="p-3 font-bold text-sky-700">${formatCurrency(b.weighted_unit_cost)}</td>
        <td class="p-3 font-extrabold text-slate-900">${formatCurrency(b.inventory_value)}</td>
      </tr>
    `).join("");
  } catch (err) {}
}

// -----------------------------------------------------------------------------
// 5. USER MANAGEMENT (RBAC)
// -----------------------------------------------------------------------------

async function loadAdminUsers() {
  const tbody = document.getElementById("adminUsersTableBody");
  try {
    const res = await fetch("/api/v1/admin/users");
    const users = await res.json();

    tbody.innerHTML = users.map(u => `
      <tr class="border-b hover:bg-slate-50">
        <td class="p-3 font-mono">${u.id}</td>
        <td class="p-3 font-bold">${u.full_name}</td>
        <td class="p-3 text-slate-600">${u.email}</td>
        <td class="p-3 text-slate-600 font-mono">${u.phone || '-'}</td>
        <td class="p-3"><span class="px-2 py-0.5 rounded font-bold text-[10px] bg-slate-100 border">${u.role}</span></td>
        <td class="p-3">${u.is_email_verified ? '<span class="text-emerald-600 font-bold">✓ Đã xác minh</span>' : '<span class="text-slate-400">Chưa</span>'}</td>
        <td class="p-3">${u.is_locked ? '<span class="text-rose-600 font-bold bg-rose-50 px-2 py-0.5 rounded">ĐÃ KHÓA</span>' : '<span class="text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded">Hoạt động</span>'}</td>
        <td class="p-3 text-right">
          ${u.is_locked ? `
            <button onclick="unlockUser(${u.id})" class="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-[11px] font-bold">Mở Khóa</button>
          ` : `
            <button onclick="lockUser(${u.id})" class="px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded text-[11px] font-bold">Khóa Tài Khoản</button>
          `}
        </td>
      </tr>
    `).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" class="p-6 text-center text-rose-500">Lỗi tải danh sách người dùng.</td></tr>`;
  }
}

async function lockUser(userId) {
  if (!(await confirmDialog("Bạn có chắc chắn muốn khóa tài khoản này?"))) return;
  try {
    const res = await fetch(`/api/v1/admin/users/${userId}/lock`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "Không thể khóa tài khoản.");
      return;
    }
    alert(data.message);
    loadAdminUsers();
  } catch (err) {
    alert("Lỗi khi kết nối.");
  }
}

async function unlockUser(userId) {
  try {
    const res = await fetch(`/api/v1/admin/users/${userId}/unlock`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "Không thể mở khóa.");
      return;
    }
    alert(data.message);
    loadAdminUsers();
  } catch (err) {
    alert("Lỗi khi kết nối.");
  }
}

function getStatusBadge(status) {
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
  return new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND" }).format(val);
}
