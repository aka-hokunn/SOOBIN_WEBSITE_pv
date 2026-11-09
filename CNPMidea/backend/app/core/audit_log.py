"""
Nhật ký thao tác (audit log) cho nhân sự.

- Ghi lại các request POST/PUT/PATCH/DELETE thành công dưới /api/v1/ do tài khoản
  KHÔNG phải CUSTOMER thực hiện.
- Bỏ qua toàn bộ /auth/ (đăng nhập, đăng xuất, đăng ký...) và các endpoint chỉ tính toán.
- Không bao giờ đọc / lưu body của request — chỉ method, path và một mô tả ngắn
  tiếng Việt suy ra từ path (VD: "Cập nhật ô vòng quay #3").
- Ghi bằng DB session riêng, mọi lỗi đều bị nuốt để không ảnh hưởng request gốc.
"""
import logging
import re
from typing import List, Optional

from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Đường dẫn (sau /api/v1) không ghi nhật ký
EXCLUDED_PREFIXES = (
    "/auth/",
    "/mock/",
    "/orders/calculate-discount",
    "/orders/payments/bank-webhook",
    "/catalog/ai-advisor",
    "/cart/",
    "/lucky-wheel/spin",
)

_ID_RE = re.compile(r"^\d+$")

# (regex trên path đã bỏ prefix, method hoặc None = mọi method, mô tả; {id} = nhóm số đầu tiên)
_RULES = [
    (r"^/lucky-wheel/manage/slots$", "POST", "Thêm ô vòng quay"),
    (r"^/lucky-wheel/manage/slots/(\d+)$", "PUT", "Cập nhật ô vòng quay #{id}"),
    (r"^/lucky-wheel/manage/slots/(\d+)$", "DELETE", "Xoá ô vòng quay #{id}"),
    (r"^/lucky-wheel/manage/config$", None, "Cập nhật cấu hình vòng quay"),
    (r"^/lucky-wheel/manage/reset$", None, "Reset vòng quay may mắn"),
    (r"^/promotions$", "POST", "Tạo chương trình khuyến mãi"),
    (r"^/promotions/(\d+)/toggle$", None, "Bật/tắt khuyến mãi #{id}"),
    (r"^/promotions/quick-voucher$", None, "Tạo nhanh voucher"),
    (r"^/inventory/receipts/confirm$", None, "Xác nhận phiếu nhập kho"),
    (r"^/inventory/receipts/(\d+)/adjust$", None, "Điều chỉnh phiếu nhập #{id}"),
    (r"^/inventory/quick-restock$", None, "Nhập bổ sung nhanh tồn kho"),
    (r"^/inventory/stocktake$", None, "Kiểm kê tồn kho"),
    (r"^/inventory/suppliers$", "POST", "Thêm nhà cung cấp"),
    (r"^/inventory/suppliers/(\d+)$", None, "Cập nhật nhà cung cấp #{id}"),
    (r"^/orders/pos$", None, "Tạo đơn bán tại quầy (POS)"),
    (r"^/orders/(\d+)/cancel$", None, "Huỷ đơn hàng #{id}"),
    (r"^/orders/(\d+)/confirm$", None, "Xác nhận đơn hàng #{id}"),
    (r"^/orders/(\d+)/refund$", None, "Hoàn tiền đơn hàng #{id}"),
    (r"^/orders/(\d+)/confirm-payment$", None, "Xác nhận thanh toán đơn #{id}"),
    (r"^/orders/trigger-expiry-job$", None, "Quét huỷ đơn VietQR quá hạn"),
    (r"^/orders/rma/requests/(\d+)$", None, "Xử lý yêu cầu đổi trả #{id}"),
    (r"^/catalog/products$", "POST", "Thêm sản phẩm"),
    (r"^/catalog/products/(\d+)$", "PUT", "Cập nhật sản phẩm #{id}"),
    (r"^/catalog/products/(\d+)$", "DELETE", "Xoá sản phẩm #{id}"),
    (r"^/catalog/products/(\d+)/restore$", None, "Khôi phục sản phẩm #{id}"),
    (r"^/catalog/products/(\d+)/sale-price$", None, "Đổi giá sale sản phẩm #{id}"),
    (r"^/catalog/products/bulk-sale$", None, "Áp giá sale hàng loạt"),
    (r"^/catalog/reviews/(\d+)/moderate$", None, "Kiểm duyệt đánh giá #{id}"),
    (r"^/site-settings/banner$", None, "Cập nhật băng rôn cửa hàng"),
    (r"^/site-settings/theme$", None, "Cập nhật giao diện website"),
    (r"^/site-settings/after-sales-policy$", None, "Cập nhật chính sách hậu mãi"),
    (r"^/site-settings/bank-account$", None, "Cập nhật tài khoản ngân hàng"),
    (r"^/site-settings/feedbacks/(\d+)$", None, "Xử lý góp ý #{id}"),
    (r"^/admin/users$", "POST", "Tạo tài khoản nhân sự"),
    (r"^/admin/users/(\d+)$", None, "Cập nhật tài khoản #{id}"),
    (r"^/admin/users/(\d+)/lock$", None, "Khoá tài khoản #{id}"),
    (r"^/admin/users/(\d+)/unlock$", None, "Mở khoá tài khoản #{id}"),
    (r"^/admin/users/(\d+)/revoke-sessions$", None, "Thu hồi phiên đăng nhập của tài khoản #{id}"),
    (r"^/admin/roles$", "POST", "Tạo vai trò"),
    (r"^/admin/roles/(\d+)$", None, "Cập nhật vai trò #{id}"),
    (r"^/insights/rfm/vouchers$", None, "Gửi voucher chăm sóc khách hàng"),
]
_COMPILED = [(re.compile(p), m, s) for p, m, s in _RULES]

_RESOURCE_LABELS = {
    "orders": "đơn hàng", "catalog": "sản phẩm", "inventory": "kho hàng", "promotions": "khuyến mãi",
    "lucky-wheel": "vòng quay", "site-settings": "cấu hình website", "admin": "quản trị",
    "reports": "báo cáo", "insights": "phân tích",
}
_VERBS = {"POST": "Tạo / thao tác", "PUT": "Cập nhật", "PATCH": "Cập nhật", "DELETE": "Xoá"}


def strip_api_prefix(path: str, api_prefix: str) -> str:
    return path[len(api_prefix):] if path.startswith(api_prefix) else path


def should_audit(method: str, path: str, status_code: int, api_prefix: str = "/api/v1") -> bool:
    if method.upper() not in MUTATING_METHODS or status_code >= 400:
        return False
    if not path.startswith(api_prefix + "/"):
        return False
    rel = strip_api_prefix(path, api_prefix)
    if any(rel.startswith(p) for p in EXCLUDED_PREFIXES):
        return False
    # Insights: chỉ ghi các thao tác thay đổi dữ liệu (gửi voucher), bỏ qua phần đọc
    if rel.startswith("/insights/") and not rel.startswith("/insights/rfm/vouchers"):
        return False
    return True


def describe_action(method: str, path: str, api_prefix: str = "/api/v1") -> str:
    """Sinh mô tả ngắn tiếng Việt từ method + path (không dùng body)."""
    method = method.upper()
    rel = strip_api_prefix(path, api_prefix).rstrip("/") or "/"
    for rx, m, summary in _COMPILED:
        if m is not None and m != method:
            continue
        match = rx.match(rel)
        if match:
            return summary.replace("{id}", match.group(1) if match.groups() else "")
    parts: List[str] = [p for p in rel.split("/") if p]
    resource = _RESOURCE_LABELS.get(parts[0], parts[0]) if parts else "dữ liệu"
    ident = next((p for p in parts if _ID_RE.match(p)), None)
    tail = [p for p in parts[1:] if not _ID_RE.match(p)]
    text = f"{_VERBS.get(method, method)} {resource}"
    if tail:
        text += f" ({'/'.join(tail)})"
    if ident:
        text += f" #{ident}"
    return text[:255]


def _extract_token(request) -> Optional[str]:
    auth = request.headers.get("authorization")
    if auth:
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        return auth
    return request.cookies.get("session_token")


def _client_ip(request) -> Optional[str]:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return request.client.host[:64] if request.client and request.client.host else None


def _write_entry(token: str, method: str, path: str, status_code: int, ip: Optional[str], api_prefix: str) -> None:
    from app.core.database import SessionLocal
    from app.models.entities import ProductionAuditLog
    from app.services.auth_service import AuthService

    db = SessionLocal()
    try:
        user = AuthService(db).validate_session(token)
        if not user or not user.role or user.role.code == "CUSTOMER":
            return
        db.add(ProductionAuditLog(
            account_id=user.id,
            account_name=(user.full_name or user.email or "—")[:150],
            role_code=user.role.code[:50],
            method=method,
            path=path[:500],
            status_code=int(status_code),
            summary=describe_action(method, path, api_prefix),
            ip=ip,
        ))
        db.commit()
    except Exception:  # never break the original request
        db.rollback()
        logger.debug("audit log write failed", exc_info=True)
    finally:
        db.close()


async def record_if_needed(request, response, api_prefix: str = "/api/v1") -> None:
    try:
        method = request.method.upper()
        path = request.url.path
        if not should_audit(method, path, response.status_code, api_prefix):
            return
        token = _extract_token(request)
        if not token:
            return
        await run_in_threadpool(_write_entry, token, method, path, response.status_code, _client_ip(request), api_prefix)
    except Exception:
        logger.debug("audit log middleware failed", exc_info=True)
