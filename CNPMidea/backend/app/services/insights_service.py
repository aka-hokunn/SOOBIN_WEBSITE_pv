"""
Phân Tích & Tăng Trưởng (Insights) — dịch vụ dùng chung cho cổng ADMIN và MANAGER.

1. Dự báo nhập hàng: tốc độ bán / ngày của từng biến thể → số ngày còn hàng → gợi ý nhập.
2. Phân khúc khách hàng RFM + gửi voucher chăm sóc cá nhân (mã CARE-XXXXXX).
3. Hiệu quả vòng quay may mắn (lượt quay, voucher SPIN- đã dùng, doanh thu mang lại).
4. Nhật ký thao tác nhân sự (ProductionAuditLog).
5. KPI tổng quan cho đầu module.

Đơn "hợp lệ" = mọi đơn trừ đơn đã huỷ / chờ hoàn tiền / đã hoàn tiền.
"""
import math
import secrets
import string
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.entities import (
    ProductionAuditLog,
    ProductionInventory,
    ProductionLuckyWheelSlot,
    ProductionLuckyWheelSpin,
    ProductionOrder,
    ProductionOrderItem,
    ProductionProduct,
    ProductionPromotion,
    ProductionVariant,
    ProductionVoucherUsage,
    UserAccount,
    UserRole,
)

INVALID_ORDER_STATUSES = ("Đã hủy", "Chờ hoàn tiền", "Đã hoàn tiền")
CARE_CODE_PREFIX = "CARE-"
SPIN_CODE_PREFIX = "SPIN-"
VN_TZ = timezone(timedelta(hours=7))
MAX_VOUCHER_BATCH = 500

FORECAST_STATUS_RANK = {"CRITICAL": 0, "WARNING": 1, "OK": 2, "NO_SALES": 3}

SEGMENTS: Dict[str, Dict[str, str]] = {
    "CHAMPIONS": {"label": "Champions", "color": "#8b5cf6", "hint": "Mua gần đây, thường xuyên, chi tiêu cao"},
    "LOYAL": {"label": "Trung thành", "color": "#0ea5e9", "hint": "Quay lại đều đặn"},
    "POTENTIAL": {"label": "Tiềm năng", "color": "#14b8a6", "hint": "Mới mua gần đây, có thể nâng hạng"},
    "NEW": {"label": "Khách mới", "color": "#22c55e", "hint": "Đơn đầu tiên gần đây"},
    "NEED_ATTENTION": {"label": "Cần chăm sóc", "color": "#f59e0b", "hint": "Bắt đầu thưa dần"},
    "AT_RISK": {"label": "Nguy cơ rời bỏ", "color": "#f43f5e", "hint": "Từng giá trị cao nhưng lâu chưa quay lại"},
    "HIBERNATING": {"label": "Đã ngủ đông", "color": "#64748b", "hint": "Rất lâu không mua"},
}
SEGMENT_ORDER = ["CHAMPIONS", "LOYAL", "POTENTIAL", "NEW", "NEED_ATTENTION", "AT_RISK", "HIBERNATING"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _valid_order_filter():
    return ~ProductionOrder.status.in_(INVALID_ORDER_STATUSES)


# ----------------------------------------------------------------------------- pure helpers (unit-tested)
def compute_forecast_row(available: int, units_sold: int, window_days: int,
                         cover_days: int = 30, safety_days: int = 7) -> Dict[str, Any]:
    """Toán dự báo cho một biến thể.

    velocity = đã bán / số ngày quan sát
    days_to_stockout = tồn hiện có / velocity
    gợi ý nhập = ceil(velocity × (cover + safety) − tồn), tối thiểu 0
    """
    window_days = max(1, int(window_days))
    available = int(available or 0)
    units_sold = max(0, int(units_sold or 0))
    velocity = units_sold / window_days
    on_hand = max(0, available)
    if velocity <= 0:
        return {"daily_velocity": 0.0, "days_to_stockout": None, "suggested_qty": 0, "status": "NO_SALES"}
    days_left = on_hand / velocity
    suggested = max(0, math.ceil(velocity * (cover_days + safety_days) - on_hand - 1e-9))
    if days_left < 7:
        status = "CRITICAL"
    elif days_left < 14:
        status = "WARNING"
    else:
        status = "OK"
    return {
        "daily_velocity": round(velocity, 3),
        "days_to_stockout": round(days_left, 1),
        "suggested_qty": suggested,
        "status": status,
    }


def score_recency(days: int) -> int:
    if days <= 14:
        return 5
    if days <= 30:
        return 4
    if days <= 60:
        return 3
    if days <= 120:
        return 2
    return 1


def score_frequency(orders: int) -> int:
    if orders >= 10:
        return 5
    if orders >= 6:
        return 4
    if orders >= 3:
        return 3
    if orders >= 2:
        return 2
    return 1


def score_monetary(amount: float) -> int:
    if amount >= 10_000_000:
        return 5
    if amount >= 5_000_000:
        return 4
    if amount >= 2_000_000:
        return 3
    if amount >= 800_000:
        return 2
    return 1


def classify_segment(r: int, f: int, m: int) -> str:
    if r >= 4 and f >= 4 and m >= 4:
        return "CHAMPIONS"
    if r >= 4 and f <= 1:
        return "NEW"
    if r >= 3 and f >= 3:
        return "LOYAL"
    if r >= 3:
        return "POTENTIAL"
    if f >= 3 or m >= 4:
        return "AT_RISK"
    if r == 2:
        return "NEED_ATTENTION"
    return "HIBERNATING"


# ----------------------------------------------------------------------------- service
class InsightsService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ forecast
    def restock_forecast(self, days: int = 30, cover_days: int = 30, safety_days: int = 7) -> Dict[str, Any]:
        days = max(1, min(int(days), 365))
        since = _utcnow() - timedelta(days=days)
        sold_rows = (
            self.db.query(ProductionOrderItem.variant_id, func.coalesce(func.sum(ProductionOrderItem.quantity), 0))
            .join(ProductionOrder, ProductionOrder.id == ProductionOrderItem.order_id)
            .filter(ProductionOrder.placed_at >= since, _valid_order_filter())
            .group_by(ProductionOrderItem.variant_id)
            .all()
        )
        sold = {int(vid): int(q or 0) for vid, q in sold_rows}

        variants = (
            self.db.query(ProductionVariant)
            .join(ProductionProduct, ProductionProduct.id == ProductionVariant.product_id)
            .options(
                joinedload(ProductionVariant.product).joinedload(ProductionProduct.images),
                joinedload(ProductionVariant.size),
                joinedload(ProductionVariant.color),
                joinedload(ProductionVariant.inventory),
            )
            .filter(ProductionVariant.is_active == True, ProductionProduct.deleted_at.is_(None))  # noqa: E712
            .all()
        )
        items: List[Dict[str, Any]] = []
        for v in variants:
            inv = v.inventory
            available = int(inv.available_quantity) if inv else 0
            calc = compute_forecast_row(available, sold.get(int(v.id), 0), days, cover_days, safety_days)
            p = v.product
            base_price = float(p.base_price) if p else 0.0
            unit_cost = (float(inv.inventory_value) / inv.available_quantity) if (inv and inv.available_quantity > 0) else 0.0
            if unit_cost <= 0:
                unit_cost = round(base_price * 0.45)
            items.append({
                "variant_id": int(v.id),
                "product_id": int(p.id) if p else None,
                "product_name": p.name if p else "",
                "sku": v.sku,
                "size": v.size.name if v.size else "",
                "color": v.color.name if v.color else "",
                "color_hex": v.color.hex_code if v.color else None,
                "image_url": p.images[0].file_path if (p and p.images) else None,
                "available_quantity": available,
                "low_stock_threshold": int(inv.low_stock_threshold) if inv else 5,
                "units_sold": sold.get(int(v.id), 0),
                "suggested_unit_cost": round(unit_cost),
                **calc,
            })
        items.sort(key=lambda x: (
            FORECAST_STATUS_RANK[x["status"]],
            x["days_to_stockout"] if x["days_to_stockout"] is not None else float("inf"),
            -x["daily_velocity"],
            x["available_quantity"],
        ))
        summary = {k.lower(): sum(1 for i in items if i["status"] == k) for k in FORECAST_STATUS_RANK}
        summary["total_suggested_units"] = sum(i["suggested_qty"] for i in items)
        summary["estimated_cost"] = round(sum(i["suggested_qty"] * i["suggested_unit_cost"] for i in items))
        return {
            "params": {"days": days, "cover_days": cover_days, "safety_days": safety_days},
            "summary": summary,
            "items": items,
        }

    # ------------------------------------------------------------------ RFM
    def _customer_rows(self) -> List[Dict[str, Any]]:
        now = _utcnow()
        rows = (
            self.db.query(
                UserAccount.id, UserAccount.full_name, UserAccount.email, UserAccount.phone,
                func.max(ProductionOrder.placed_at), func.count(ProductionOrder.id),
                func.coalesce(func.sum(ProductionOrder.total_amount), 0),
            )
            .join(UserRole, UserRole.id == UserAccount.role_id)
            .join(ProductionOrder, ProductionOrder.account_id == UserAccount.id)
            .filter(UserRole.code == "CUSTOMER", _valid_order_filter())
            .group_by(UserAccount.id, UserAccount.full_name, UserAccount.email, UserAccount.phone)
            .all()
        )
        out = []
        for acc_id, name, email, phone, last_at, orders, spend in rows:
            last_at = _aware(last_at)
            recency = max(0, (now - last_at).days) if last_at else 9999
            r, f, m = score_recency(recency), score_frequency(int(orders)), score_monetary(float(spend))
            seg = classify_segment(r, f, m)
            out.append({
                "account_id": int(acc_id),
                "name": name,
                "email": email,
                "phone": phone,
                "last_order_at": last_at.isoformat() if last_at else None,
                "recency_days": recency,
                "orders": int(orders),
                "spend": float(spend),
                "r": r, "f": f, "m": m,
                "segment": seg,
                "segment_label": SEGMENTS[seg]["label"],
            })
        out.sort(key=lambda c: (SEGMENT_ORDER.index(c["segment"]), -c["spend"]))
        return out

    def rfm(self, segment: Optional[str] = None, q: Optional[str] = None) -> Dict[str, Any]:
        customers = self._customer_rows()
        summary = []
        for code in SEGMENT_ORDER:
            members = [c for c in customers if c["segment"] == code]
            summary.append({
                "code": code,
                **SEGMENTS[code],
                "count": len(members),
                "total_spend": round(sum(c["spend"] for c in members)),
                "avg_recency_days": round(sum(c["recency_days"] for c in members) / len(members)) if members else None,
            })
        filtered = customers
        if segment:
            filtered = [c for c in filtered if c["segment"] == segment.upper()]
        if q:
            needle = q.strip().lower()
            filtered = [c for c in filtered if needle in (c["name"] or "").lower() or needle in (c["email"] or "").lower()
                        or needle in (c["phone"] or "")]
        return {"total_customers": len(customers), "segments": summary, "customers": filtered}

    def _generate_care_code(self) -> str:
        alphabet = string.ascii_uppercase + string.digits
        for _ in range(30):
            code = CARE_CODE_PREFIX + "".join(secrets.choice(alphabet) for _ in range(6))
            if not self.db.query(ProductionPromotion.id).filter(ProductionPromotion.code == code).first():
                return code
        raise HTTPException(status_code=500, detail="Không thể sinh mã voucher, vui lòng thử lại.")

    def send_care_vouchers(self, account_ids: Optional[Iterable[int]], segment: Optional[str],
                           discount_percent: float, valid_days: int, minimum_order_amount: float) -> Dict[str, Any]:
        if not 1 <= float(discount_percent) <= 90:
            raise HTTPException(status_code=400, detail="Mức giảm phải từ 1% đến 90%.")
        if not 1 <= int(valid_days) <= 365:
            raise HTTPException(status_code=400, detail="Hạn dùng phải từ 1 đến 365 ngày.")
        if float(minimum_order_amount) < 0:
            raise HTTPException(status_code=400, detail="Đơn tối thiểu không hợp lệ.")

        seg_code = segment.upper() if segment else None
        if seg_code and seg_code not in SEGMENTS:
            raise HTTPException(status_code=400, detail="Phân khúc khách hàng không hợp lệ.")

        ids = {int(i) for i in (account_ids or [])}
        if seg_code:
            ids |= {c["account_id"] for c in self._customer_rows() if c["segment"] == seg_code}
        if not ids:
            raise HTTPException(status_code=400, detail="Chưa chọn khách hàng nào để gửi voucher.")
        if len(ids) > MAX_VOUCHER_BATCH:
            raise HTTPException(status_code=400, detail=f"Mỗi lần gửi tối đa {MAX_VOUCHER_BATCH} khách hàng.")

        customers = (
            self.db.query(UserAccount)
            .join(UserRole, UserRole.id == UserAccount.role_id)
            .filter(UserAccount.id.in_(ids), UserRole.code == "CUSTOMER", UserAccount.is_locked == False)  # noqa: E712
            .all()
        )
        if not customers:
            raise HTTPException(status_code=400, detail="Không có khách hàng hợp lệ trong danh sách đã chọn.")

        label = SEGMENTS[seg_code]["label"] if seg_code else "Khách hàng thân thiết"
        now = _utcnow()
        issued = []
        for user in customers:
            promo = ProductionPromotion(
                code=self._generate_care_code(),
                name=f"💝 Ưu đãi chăm sóc — {label}"[:255],
                promotion_type="VOUCHER",
                discount_percent=round(float(discount_percent), 2),
                minimum_order_amount=round(float(minimum_order_amount), 2),
                usage_limit=1,
                used_count=0,
                starts_at=now - timedelta(minutes=1),
                ends_at=now + timedelta(days=int(valid_days)),
                is_active=True,
                eligible_customer_ids=[int(user.id)],
            )
            self.db.add(promo)
            self.db.flush()
            issued.append({"account_id": int(user.id), "name": user.full_name, "email": user.email,
                           "code": promo.code, "promotion_id": int(promo.id)})
        skipped = len(ids) - len(customers)
        return {
            "message": f"Đã gửi {len(issued)} voucher giảm {float(discount_percent):g}% (hạn {int(valid_days)} ngày)"
                       + (f", bỏ qua {skipped} tài khoản không hợp lệ." if skipped else "."),
            "created": len(issued),
            "skipped": skipped,
            "vouchers": issued,
        }

    # ------------------------------------------------------------------ lucky wheel performance
    def wheel_performance(self, chart_days: int = 14) -> Dict[str, Any]:
        total_spins = self.db.query(func.count(ProductionLuckyWheelSpin.id)).scalar() or 0
        total_wins = self.db.query(func.count(ProductionLuckyWheelSpin.id)).filter(ProductionLuckyWheelSpin.is_win == True).scalar() or 0  # noqa: E712
        issued = self.db.query(func.count(ProductionLuckyWheelSpin.id)).filter(ProductionLuckyWheelSpin.issued_promotion_id.isnot(None)).scalar() or 0

        # Đơn hợp lệ đã dùng voucher SPIN- (chưa được hoàn lại lượt dùng)
        used_rows = (
            self.db.query(ProductionVoucherUsage.promotion_id, ProductionOrder.total_amount, ProductionOrder.discount_amount)
            .join(ProductionPromotion, ProductionPromotion.id == ProductionVoucherUsage.promotion_id)
            .join(ProductionOrder, ProductionOrder.id == ProductionVoucherUsage.order_id)
            .filter(ProductionPromotion.code.like(f"{SPIN_CODE_PREFIX}%"),
                    ProductionVoucherUsage.restored_at.is_(None), _valid_order_filter())
            .all()
        )
        usage_by_promo: Dict[int, Dict[str, float]] = {}
        for pid, total, disc in used_rows:
            agg = usage_by_promo.setdefault(int(pid), {"orders": 0, "revenue": 0.0, "discount": 0.0})
            agg["orders"] += 1
            agg["revenue"] += float(total or 0)
            agg["discount"] += float(disc or 0)
        vouchers_used = len(usage_by_promo)
        revenue = sum(a["revenue"] for a in usage_by_promo.values())
        discount = sum(a["discount"] for a in usage_by_promo.values())

        slot_meta = {s.id: s for s in self.db.query(ProductionLuckyWheelSlot).all()}
        per_slot: Dict[Any, Dict[str, Any]] = {}
        spin_rows = self.db.query(
            ProductionLuckyWheelSpin.slot_id, ProductionLuckyWheelSpin.slot_label,
            ProductionLuckyWheelSpin.is_win, ProductionLuckyWheelSpin.issued_promotion_id,
        ).all()
        for slot_id, label, is_win, promo_id in spin_rows:
            key = slot_id if slot_id in slot_meta else f"deleted:{label}"
            row = per_slot.get(key)
            if row is None:
                meta = slot_meta.get(slot_id)
                row = per_slot[key] = {
                    "slot_id": slot_id if meta else None,
                    "label": meta.label if meta else f"{label} (đã xoá)",
                    "color": meta.color if meta else "#94a3b8",
                    "is_active": bool(meta.is_active) if meta else False,
                    "sort_order": meta.sort_order if meta else 9999,
                    "spins": 0, "wins": 0, "used": 0, "revenue": 0.0,
                }
            row["spins"] += 1
            if is_win:
                row["wins"] += 1
            if promo_id and int(promo_id) in usage_by_promo:
                row["used"] += 1
                row["revenue"] += usage_by_promo[int(promo_id)]["revenue"]
        for sid, meta in slot_meta.items():  # ô chưa có lượt quay nào
            if sid not in per_slot:
                per_slot[sid] = {"slot_id": sid, "label": meta.label, "color": meta.color, "is_active": bool(meta.is_active),
                                 "sort_order": meta.sort_order, "spins": 0, "wins": 0, "used": 0, "revenue": 0.0}
        slots = sorted(per_slot.values(), key=lambda r: (r["sort_order"], r["label"]))
        for r in slots:
            r["revenue"] = round(r["revenue"])
            r["share_percent"] = round(r["spins"] / total_spins * 100, 1) if total_spins else 0

        # Biểu đồ lượt quay N ngày gần nhất (theo giờ Việt Nam)
        chart_days = max(1, min(int(chart_days), 60))
        today_vn = _utcnow().astimezone(VN_TZ).date()
        start_vn = today_vn - timedelta(days=chart_days - 1)
        start_utc = datetime(start_vn.year, start_vn.month, start_vn.day, tzinfo=VN_TZ).astimezone(timezone.utc)
        buckets = {start_vn + timedelta(days=i): {"spins": 0, "wins": 0} for i in range(chart_days)}
        for created_at, is_win in (
            self.db.query(ProductionLuckyWheelSpin.created_at, ProductionLuckyWheelSpin.is_win)
            .filter(ProductionLuckyWheelSpin.created_at >= start_utc).all()
        ):
            d = _aware(created_at).astimezone(VN_TZ).date()
            if d in buckets:
                buckets[d]["spins"] += 1
                if is_win:
                    buckets[d]["wins"] += 1

        return {
            "totals": {
                "total_spins": int(total_spins),
                "total_wins": int(total_wins),
                "win_rate_percent": round(total_wins / total_spins * 100, 1) if total_spins else 0,
                "vouchers_issued": int(issued),
                "vouchers_used": int(vouchers_used),
                "usage_rate_percent": round(vouchers_used / issued * 100, 1) if issued else 0,
                "revenue": round(revenue),
                "discount": round(discount),
                "orders": int(sum(a["orders"] for a in usage_by_promo.values())),
            },
            "slots": slots,
            "daily": [{"date": d.isoformat(), **v} for d, v in buckets.items()],
        }

    # ------------------------------------------------------------------ audit log
    def audit_logs(self, q: Optional[str] = None, method: Optional[str] = None,
                   limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        query = self.db.query(ProductionAuditLog)
        if method:
            query = query.filter(ProductionAuditLog.method == method.upper())
        if q:
            like = f"%{q.strip()}%"
            query = query.filter(or_(
                ProductionAuditLog.account_name.ilike(like),
                ProductionAuditLog.summary.ilike(like),
                ProductionAuditLog.path.ilike(like),
                ProductionAuditLog.role_code.ilike(like),
            ))
        total = query.count()
        rows = query.order_by(ProductionAuditLog.created_at.desc(), ProductionAuditLog.id.desc()).offset(offset).limit(limit).all()
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [
                {
                    "id": r.id,
                    "account_id": r.account_id,
                    "account_name": r.account_name,
                    "role_code": r.role_code,
                    "method": r.method,
                    "path": r.path,
                    "status_code": r.status_code,
                    "summary": r.summary,
                    "ip": r.ip,
                    "created_at": _aware(r.created_at).isoformat(),
                }
                for r in rows
            ],
        }

    # ------------------------------------------------------------------ KPI strip
    def kpis(self) -> Dict[str, Any]:
        now = _utcnow()
        today_vn = now.astimezone(VN_TZ).date()
        start_utc = datetime(today_vn.year, today_vn.month, today_vn.day, tzinfo=VN_TZ).astimezone(timezone.utc)
        yesterday_utc = start_utc - timedelta(days=1)

        def day_stats(start: datetime, end: datetime):
            count, revenue = (
                self.db.query(func.count(ProductionOrder.id), func.coalesce(func.sum(ProductionOrder.total_amount), 0))
                .filter(ProductionOrder.placed_at >= start, ProductionOrder.placed_at < end, _valid_order_filter())
                .one()
            )
            return int(count or 0), float(revenue or 0)

        orders_today, revenue_today = day_stats(start_utc, now + timedelta(seconds=1))
        orders_yday, revenue_yday = day_stats(yesterday_utc, start_utc)

        low_stock = (
            self.db.query(func.count(ProductionInventory.variant_id))
            .join(ProductionVariant, ProductionVariant.id == ProductionInventory.variant_id)
            .join(ProductionProduct, ProductionProduct.id == ProductionVariant.product_id)
            .filter(ProductionVariant.is_active == True, ProductionProduct.deleted_at.is_(None),  # noqa: E712
                    ProductionInventory.available_quantity <= ProductionInventory.low_stock_threshold)
            .scalar() or 0
        )
        customers = self._customer_rows()
        at_risk = sum(1 for c in customers if c["segment"] == "AT_RISK")
        return {
            "revenue_today": round(revenue_today),
            "revenue_yesterday": round(revenue_yday),
            "orders_today": orders_today,
            "orders_yesterday": orders_yday,
            "low_stock_variants": int(low_stock),
            "customers_at_risk": at_risk,
            "customers_need_attention": sum(1 for c in customers if c["segment"] == "NEED_ATTENTION"),
            "generated_at": now.isoformat(),
        }
