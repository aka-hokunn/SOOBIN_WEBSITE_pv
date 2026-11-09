"""
Lucky Wheel (Vòng quay may mắn) service.

Quy tắc nghiệp vụ:
- Cấu hình vòng quay lưu ở production_site_setting (key = "lucky_wheel_config").
- Mỗi ô có tỷ lệ ra (win_weight, %). Xác suất thực = weight / tổng weight các ô đang bật.
- Ô chỉ "có thưởng" khi có voucher mẫu VÀ có số lượng > 0. Không nhập → ô không trúng thưởng.
- Ô có thưởng nhưng đã hết số lượng trong chu kỳ → kết quả chuyển sang một ô không trúng.
- Mỗi khách có `spins_per_period` lượt / chu kỳ `reset_interval_minutes`. Hết chu kỳ thì lượt
  được hồi lại; nếu `restock_on_reset` thì số lượng voucher của từng ô cũng được nạp lại.
- Điểm danh Vỏ Sò (experience_service): cứ 3 Vỏ Sò = +1 lượt quay thưởng, chỉ cộng vào chu kỳ hiện tại.
- Khi trúng: sinh voucher riêng (mã SPIN-XXXXXX) từ voucher mẫu, usage_limit = 1,
  eligible_customer_ids = [account_id], hiệu lực `voucher_valid_days` ngày.
"""
import math
import random
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.entities import (
    ProductionDailyCheckin,
    ProductionLuckyWheelSlot,
    ProductionLuckyWheelSpin,
    ProductionPromotion,
    ProductionSiteSetting,
    UserAccount,
)

CONFIG_KEY = "lucky_wheel_config"
PERSONAL_CODE_PREFIX = "SPIN-"
MIN_ACTIVE_SLOTS = 2
MAX_ACTIVE_SLOTS = 12

DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "title": "Vòng Quay Đại Dương",
    "subtitle": "Quay là trúng — voucher riêng chỉ dành cho bạn!",
    "spins_per_period": 1,
    "reset_interval_minutes": 24 * 60,
    "restock_on_reset": True,
    "voucher_valid_days": 7,
    "period_anchor": None,          # ISO datetime — mốc bắt đầu tính chu kỳ
    "last_restock_period": None,    # số thứ tự chu kỳ đã nạp lại voucher gần nhất
}

SLOT_PALETTE = ["#0ea5e9", "#f43f5e", "#14b8a6", "#f59e0b", "#6366f1", "#06b6d4", "#ec4899", "#22c55e",
                "#0284c7", "#fb923c", "#8b5cf6", "#10b981"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


class LuckyWheelService:
    def __init__(self, db: Session):
        self.db = db
        self._rng = random.SystemRandom()

    # ------------------------------------------------------------------ config
    def get_config(self, for_update: bool = False) -> Tuple[Dict[str, Any], ProductionSiteSetting]:
        q = self.db.query(ProductionSiteSetting).filter(ProductionSiteSetting.key == CONFIG_KEY)
        if for_update:
            q = q.with_for_update()
        row = q.first()
        if not row:
            cfg = dict(DEFAULT_CONFIG)
            cfg["period_anchor"] = _utcnow().replace(minute=0, second=0, microsecond=0).isoformat()
            cfg["last_restock_period"] = 0
            row = ProductionSiteSetting(key=CONFIG_KEY, value=cfg)
            self.db.add(row)
            self.db.flush()
        cfg = {**DEFAULT_CONFIG, **(row.value or {})}
        if not _parse_dt(cfg.get("period_anchor")):
            cfg["period_anchor"] = _utcnow().replace(minute=0, second=0, microsecond=0).isoformat()
        return cfg, row

    def _save_config(self, row: ProductionSiteSetting, cfg: Dict[str, Any]) -> None:
        row.value = dict(cfg)  # new object so SQLAlchemy detects the JSONB change
        self.db.flush()

    def update_config(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        cfg, row = self.get_config(for_update=True)
        if "enabled" in changes and changes["enabled"] is not None:
            cfg["enabled"] = bool(changes["enabled"])
        for key in ("title", "subtitle"):
            if changes.get(key) is not None:
                val = str(changes[key]).strip()
                if key == "title" and not val:
                    raise HTTPException(status_code=400, detail="Tên vòng quay không được để trống.")
                cfg[key] = val[:120]
        if changes.get("spins_per_period") is not None:
            spins = int(changes["spins_per_period"])
            if not 1 <= spins <= 50:
                raise HTTPException(status_code=400, detail="Số lượt quay mỗi chu kỳ phải từ 1 đến 50.")
            cfg["spins_per_period"] = spins
        if changes.get("reset_interval_minutes") is not None:
            minutes = int(changes["reset_interval_minutes"])
            if not 5 <= minutes <= 60 * 24 * 60:
                raise HTTPException(status_code=400, detail="Thời gian reset phải từ 5 phút đến 60 ngày.")
            if minutes != cfg["reset_interval_minutes"]:
                # Interval changed → start a fresh cycle from now
                cfg["reset_interval_minutes"] = minutes
                cfg["period_anchor"] = _utcnow().isoformat()
                cfg["last_restock_period"] = 0
        if changes.get("restock_on_reset") is not None:
            cfg["restock_on_reset"] = bool(changes["restock_on_reset"])
        if changes.get("voucher_valid_days") is not None:
            days = int(changes["voucher_valid_days"])
            if not 1 <= days <= 365:
                raise HTTPException(status_code=400, detail="Hạn dùng voucher trúng thưởng phải từ 1 đến 365 ngày.")
            cfg["voucher_valid_days"] = days
        self._save_config(row, cfg)
        return cfg

    # ------------------------------------------------------------------ cycle
    def current_period(self, cfg: Dict[str, Any], now: Optional[datetime] = None) -> Tuple[int, datetime, datetime]:
        now = now or _utcnow()
        anchor = _parse_dt(cfg.get("period_anchor")) or now
        interval = timedelta(minutes=int(cfg.get("reset_interval_minutes") or 1440))
        if now < anchor:
            return 0, anchor, anchor + interval
        idx = math.floor((now - anchor) / interval)
        start = anchor + interval * idx
        return idx, start, start + interval

    def _maybe_restock(self, cfg: Dict[str, Any], row: ProductionSiteSetting, period_idx: int) -> bool:
        if not cfg.get("restock_on_reset"):
            return False
        last = cfg.get("last_restock_period")
        if last is not None and int(last) >= period_idx:
            return False
        for slot in self.db.query(ProductionLuckyWheelSlot).with_for_update().all():
            if slot.quantity_total is not None:
                slot.quantity_remaining = slot.quantity_total
        cfg["last_restock_period"] = period_idx
        self._save_config(row, cfg)
        return True

    def reset_now(self) -> Dict[str, Any]:
        """Bắt đầu chu kỳ mới ngay lập tức: hồi lượt quay cho mọi khách + nạp lại số lượng voucher."""
        cfg, row = self.get_config(for_update=True)
        cfg["period_anchor"] = _utcnow().isoformat()
        cfg["last_restock_period"] = 0
        for slot in self.db.query(ProductionLuckyWheelSlot).with_for_update().all():
            if slot.quantity_total is not None:
                slot.quantity_remaining = slot.quantity_total
        self._save_config(row, cfg)
        return cfg

    def spins_used(self, account_id: int, period_start: datetime) -> int:
        return self.db.query(func.count(ProductionLuckyWheelSpin.id)).filter(
            ProductionLuckyWheelSpin.account_id == account_id,
            ProductionLuckyWheelSpin.created_at >= period_start,
        ).scalar() or 0

    def bonus_spins(self, account_id: int, period_start: datetime) -> int:
        """Lượt quay thưởng từ điểm danh Vỏ Sò (3 Vỏ Sò = +1 lượt) — chỉ tính trong chu kỳ hiện tại."""
        try:
            with self.db.begin_nested():
                return int(self.db.query(func.coalesce(func.sum(ProductionDailyCheckin.bonus_spins), 0)).filter(
                    ProductionDailyCheckin.account_id == account_id,
                    ProductionDailyCheckin.created_at >= period_start,
                ).scalar() or 0)
        except Exception:  # bảng điểm danh chưa được tạo (DB cũ) → không có lượt thưởng
            return 0

    # ------------------------------------------------------------------ slots
    def active_slots(self, for_update: bool = False) -> List[ProductionLuckyWheelSlot]:
        q = self.db.query(ProductionLuckyWheelSlot).filter(ProductionLuckyWheelSlot.is_active == True)  # noqa: E712
        q = q.order_by(ProductionLuckyWheelSlot.sort_order.asc(), ProductionLuckyWheelSlot.id.asc())
        if for_update:
            q = q.with_for_update()
        return q.all()

    @staticmethod
    def slot_is_prize_configured(slot: ProductionLuckyWheelSlot) -> bool:
        return bool(slot.promotion_id) and slot.quantity_total is not None and slot.quantity_total > 0

    @classmethod
    def slot_has_stock(cls, slot: ProductionLuckyWheelSlot) -> bool:
        return cls.slot_is_prize_configured(slot) and (slot.quantity_remaining or 0) > 0

    @staticmethod
    def default_label(slot: ProductionLuckyWheelSlot) -> str:
        if slot.promotion and slot.quantity_total:
            return f"Giảm {float(slot.promotion.discount_percent):g}%"
        return "Chúc may mắn"

    def _validate_slot_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if "promotion_id" in data:
            pid = data.get("promotion_id")
            if pid in ("", 0):
                pid = None
            if pid is not None:
                promo = self.db.query(ProductionPromotion).filter(ProductionPromotion.id == int(pid)).first()
                if not promo or promo.promotion_type != "VOUCHER":
                    raise HTTPException(status_code=400, detail="Voucher được chọn không tồn tại hoặc không phải loại VOUCHER.")
                if promo.code.startswith(PERSONAL_CODE_PREFIX):
                    raise HTTPException(status_code=400, detail="Không thể dùng voucher cá nhân (SPIN-) làm phần thưởng.")
                pid = promo.id
            out["promotion_id"] = pid
        if "win_weight" in data and data["win_weight"] is not None:
            w = float(data["win_weight"])
            if w < 0 or w > 100:
                raise HTTPException(status_code=400, detail="Tỷ lệ ra của mỗi ô phải từ 0% đến 100%.")
            out["win_weight"] = round(w, 3)
        if "quantity_total" in data:
            q = data.get("quantity_total")
            if q in ("",):
                q = None
            if q is not None:
                q = int(q)
                if q < 0 or q > 1_000_000:
                    raise HTTPException(status_code=400, detail="Số lượng voucher phải từ 0 đến 1.000.000.")
                if q == 0:
                    q = None
            out["quantity_total"] = q
        if "label" in data and data["label"] is not None:
            out["label"] = str(data["label"]).strip()[:80]
        if "color" in data and data["color"]:
            color = str(data["color"]).strip()
            if not (color.startswith("#") and len(color) in (4, 7)):
                raise HTTPException(status_code=400, detail="Màu ô phải ở dạng mã HEX (VD: #0ea5e9).")
            out["color"] = color
        if "sort_order" in data and data["sort_order"] is not None:
            out["sort_order"] = int(data["sort_order"])
        if "is_active" in data and data["is_active"] is not None:
            out["is_active"] = bool(data["is_active"])
        return out

    def _ensure_active_count(self, exclude_id: Optional[int] = None, adding: int = 0) -> None:
        q = self.db.query(func.count(ProductionLuckyWheelSlot.id)).filter(ProductionLuckyWheelSlot.is_active == True)  # noqa: E712
        if exclude_id:
            q = q.filter(ProductionLuckyWheelSlot.id != exclude_id)
        count = (q.scalar() or 0) + adding
        if count > MAX_ACTIVE_SLOTS:
            raise HTTPException(status_code=400, detail=f"Vòng quay tối đa {MAX_ACTIVE_SLOTS} ô đang bật.")
        if count < MIN_ACTIVE_SLOTS:
            raise HTTPException(status_code=400, detail=f"Vòng quay cần ít nhất {MIN_ACTIVE_SLOTS} ô đang bật.")

    def create_slot(self, data: Dict[str, Any]) -> ProductionLuckyWheelSlot:
        payload = self._validate_slot_payload(data)
        if payload.get("is_active", True):
            q = self.db.query(func.count(ProductionLuckyWheelSlot.id)).filter(ProductionLuckyWheelSlot.is_active == True)  # noqa: E712
            if (q.scalar() or 0) + 1 > MAX_ACTIVE_SLOTS:
                raise HTTPException(status_code=400, detail=f"Vòng quay tối đa {MAX_ACTIVE_SLOTS} ô đang bật.")
        max_sort = self.db.query(func.max(ProductionLuckyWheelSlot.sort_order)).scalar() or 0
        count = self.db.query(func.count(ProductionLuckyWheelSlot.id)).scalar() or 0
        slot = ProductionLuckyWheelSlot(
            label=payload.get("label") or "",
            promotion_id=payload.get("promotion_id"),
            win_weight=payload.get("win_weight", 10),
            quantity_total=payload.get("quantity_total"),
            quantity_remaining=payload.get("quantity_total"),
            color=payload.get("color") or SLOT_PALETTE[count % len(SLOT_PALETTE)],
            sort_order=payload.get("sort_order", max_sort + 1),
            is_active=payload.get("is_active", True),
        )
        self.db.add(slot)
        self.db.flush()
        self.db.refresh(slot)
        if not slot.label:
            slot.label = self.default_label(slot)
        self.db.flush()
        return slot

    def update_slot(self, slot_id: int, data: Dict[str, Any]) -> ProductionLuckyWheelSlot:
        slot = self.db.query(ProductionLuckyWheelSlot).filter(ProductionLuckyWheelSlot.id == slot_id).with_for_update().first()
        if not slot:
            raise HTTPException(status_code=404, detail="Không tìm thấy ô vòng quay.")
        payload = self._validate_slot_payload(data)
        if payload.get("is_active") is False and slot.is_active:
            self._ensure_active_count(exclude_id=slot.id)
        if payload.get("is_active") is True and not slot.is_active:
            self._ensure_active_count(exclude_id=slot.id, adding=1)
        for key, val in payload.items():
            if key == "quantity_total":
                old_total = slot.quantity_total
                slot.quantity_total = val
                if val is None:
                    slot.quantity_remaining = None
                elif old_total is None or slot.quantity_remaining is None:
                    slot.quantity_remaining = val
                else:
                    # Keep what was already handed out in this cycle
                    used = max(0, old_total - slot.quantity_remaining)
                    slot.quantity_remaining = max(0, val - used)
            else:
                setattr(slot, key, val)
        if "quantity_remaining" in data and data["quantity_remaining"] not in (None, "") and slot.quantity_total:
            slot.quantity_remaining = max(0, min(int(data["quantity_remaining"]), slot.quantity_total))
        self.db.flush()
        self.db.refresh(slot)
        if not slot.label:
            slot.label = self.default_label(slot)
            self.db.flush()
        return slot

    def delete_slot(self, slot_id: int) -> None:
        slot = self.db.query(ProductionLuckyWheelSlot).filter(ProductionLuckyWheelSlot.id == slot_id).first()
        if not slot:
            raise HTTPException(status_code=404, detail="Không tìm thấy ô vòng quay.")
        if slot.is_active:
            self._ensure_active_count(exclude_id=slot.id)
        self.db.delete(slot)
        self.db.flush()

    # ------------------------------------------------------------------ spin
    def _weighted_pick(self, slots: List[ProductionLuckyWheelSlot]) -> ProductionLuckyWheelSlot:
        weights = [max(0.0, float(s.win_weight or 0)) for s in slots]
        total = sum(weights)
        if total <= 0:
            return self._rng.choice(slots)
        r = self._rng.uniform(0, total)
        acc = 0.0
        for slot, w in zip(slots, weights):
            acc += w
            if r < acc and w > 0:
                return slot
        return next(s for s, w in zip(reversed(slots), reversed(weights)) if w > 0)

    def _generate_personal_code(self) -> str:
        alphabet = string.ascii_uppercase + string.digits
        for _ in range(20):
            code = PERSONAL_CODE_PREFIX + "".join(secrets.choice(alphabet) for _ in range(7))
            exists = self.db.query(ProductionPromotion.id).filter(ProductionPromotion.code == code).first()
            if not exists:
                return code
        raise HTTPException(status_code=500, detail="Không thể sinh mã voucher, vui lòng thử lại.")

    def _issue_personal_voucher(self, template: ProductionPromotion, user: UserAccount, valid_days: int) -> ProductionPromotion:
        now = _utcnow()
        promo = ProductionPromotion(
            code=self._generate_personal_code(),
            name=f"🎡 Vòng quay may mắn — {template.name}"[:255],
            promotion_type="VOUCHER",
            discount_percent=template.discount_percent,
            minimum_order_amount=template.minimum_order_amount,
            usage_limit=1,
            used_count=0,
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(days=valid_days),
            is_active=True,
            eligible_customer_ids=[int(user.id)],
        )
        self.db.add(promo)
        self.db.flush()
        return promo

    def spin(self, user: UserAccount) -> Dict[str, Any]:
        cfg, row = self.get_config(for_update=True)
        if not cfg.get("enabled"):
            raise HTTPException(status_code=400, detail="Vòng quay may mắn đang tạm dừng. Hẹn bạn quay lại sau nhé!")
        period_idx, period_start, next_reset = self.current_period(cfg)
        self._maybe_restock(cfg, row, period_idx)

        limit = int(cfg.get("spins_per_period") or 1)
        bonus = self.bonus_spins(user.id, period_start)
        allowed = limit + bonus
        used = self.spins_used(user.id, period_start)
        if used >= allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Bạn đã dùng hết {allowed} lượt quay của chu kỳ này. Lượt mới sẽ mở lúc "
                       f"{next_reset.astimezone(timezone(timedelta(hours=7))).strftime('%H:%M %d/%m/%Y')}.",
            )

        slots = self.active_slots(for_update=True)
        if len(slots) < MIN_ACTIVE_SLOTS:
            raise HTTPException(status_code=400, detail="Vòng quay chưa được cấu hình đủ ô.")

        picked = self._weighted_pick(slots)
        landed = picked
        sold_out = False
        if self.slot_is_prize_configured(picked) and not self.slot_has_stock(picked):
            # Prize exhausted this cycle → land on a real "no prize" slot instead
            sold_out = True
            misses = [s for s in slots if not self.slot_is_prize_configured(s)]
            if not misses:
                misses = [s for s in slots if not self.slot_has_stock(s) and s.id != picked.id]
            landed = self._weighted_pick(misses) if misses else picked

        is_win = self.slot_has_stock(landed) and landed.promotion is not None
        voucher = None
        if is_win:
            landed.quantity_remaining = (landed.quantity_remaining or 0) - 1
            voucher = self._issue_personal_voucher(landed.promotion, user, int(cfg.get("voucher_valid_days") or 7))

        spin = ProductionLuckyWheelSpin(
            account_id=user.id,
            slot_id=landed.id,
            slot_label=landed.label,
            is_win=is_win,
            issued_promotion_id=voucher.id if voucher else None,
            voucher_code=voucher.code if voucher else None,
        )
        self.db.add(spin)
        self.db.flush()

        spins_left = max(0, allowed - used - 1)
        if is_win:
            message = (f"Chúc mừng {user.full_name}! Bạn trúng voucher giảm "
                       f"{float(voucher.discount_percent):g}% — mã riêng của bạn là {voucher.code}.")
        elif sold_out:
            message = "Tiếc quá! Phần quà bạn quay trúng vừa hết trong chu kỳ này. Chúc bạn may mắn lần sau nhé!"
        else:
            message = "Tiếc quá, lần này chưa trúng rồi! Chúc bạn may mắn lần sau nhé!"

        return {
            "slot_id": landed.id,
            "slot_index": next(i for i, s in enumerate(slots) if s.id == landed.id),
            "slot_label": landed.label,
            "is_win": is_win,
            "message": message,
            "voucher": self.serialize_voucher(voucher) if voucher else None,
            "spins_left": spins_left,
            "spins_per_period": limit,
            "bonus_spins": bonus,
            "next_reset_at": next_reset.isoformat(),
        }

    # ------------------------------------------------------------------ views
    @staticmethod
    def serialize_voucher(p: ProductionPromotion) -> Dict[str, Any]:
        now = _utcnow()
        used = p.usage_limit is not None and p.used_count >= p.usage_limit
        expired = p.ends_at < now
        return {
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "discount_percent": float(p.discount_percent),
            "minimum_order_amount": float(p.minimum_order_amount),
            "ends_at": p.ends_at.isoformat(),
            "is_used": used,
            "is_expired": expired,
            "status": "USED" if used else ("EXPIRED" if expired else ("LOCKED" if not p.is_active else "AVAILABLE")),
        }

    def public_state(self, user: Optional[UserAccount]) -> Dict[str, Any]:
        cfg, row = self.get_config(for_update=True)
        period_idx, period_start, next_reset = self.current_period(cfg)
        self._maybe_restock(cfg, row, period_idx)
        slots = self.active_slots()
        data: Dict[str, Any] = {
            "enabled": bool(cfg.get("enabled")) and len(slots) >= MIN_ACTIVE_SLOTS,
            "title": cfg.get("title"),
            "subtitle": cfg.get("subtitle"),
            "spins_per_period": int(cfg.get("spins_per_period") or 1),
            "reset_interval_minutes": int(cfg.get("reset_interval_minutes") or 1440),
            "voucher_valid_days": int(cfg.get("voucher_valid_days") or 7),
            "next_reset_at": next_reset.isoformat(),
            "slots": [
                {
                    "id": s.id,
                    "label": s.label,
                    "color": s.color,
                    "is_prize": self.slot_is_prize_configured(s),
                    "in_stock": self.slot_has_stock(s),
                    "discount_percent": float(s.promotion.discount_percent) if (s.promotion and self.slot_is_prize_configured(s)) else None,
                }
                for s in slots
            ],
            "logged_in": user is not None,
            "can_spin": False,
            "spins_left": None,
            "bonus_spins": 0,
        }
        if user is not None and user.role and user.role.code == "CUSTOMER":
            used = self.spins_used(user.id, period_start)
            bonus = self.bonus_spins(user.id, period_start)
            data["bonus_spins"] = bonus
            data["spins_left"] = max(0, data["spins_per_period"] + bonus - used)
            data["can_spin"] = data["enabled"] and data["spins_left"] > 0
        return data

    def my_vouchers(self, user: UserAccount) -> List[Dict[str, Any]]:
        spins = (
            self.db.query(ProductionLuckyWheelSpin)
            .filter(ProductionLuckyWheelSpin.account_id == user.id, ProductionLuckyWheelSpin.is_win == True)  # noqa: E712
            .order_by(ProductionLuckyWheelSpin.created_at.desc())
            .limit(50)
            .all()
        )
        out = []
        for sp in spins:
            if sp.issued_promotion:
                item = self.serialize_voucher(sp.issued_promotion)
                item["won_at"] = sp.created_at.isoformat()
                out.append(item)
        return out

    def manage_state(self) -> Dict[str, Any]:
        cfg, row = self.get_config(for_update=True)
        period_idx, period_start, next_reset = self.current_period(cfg)
        self._maybe_restock(cfg, row, period_idx)
        slots = (
            self.db.query(ProductionLuckyWheelSlot)
            .order_by(ProductionLuckyWheelSlot.sort_order.asc(), ProductionLuckyWheelSlot.id.asc())
            .all()
        )
        active_weight = sum(float(s.win_weight or 0) for s in slots if s.is_active)
        win_counts = dict(
            self.db.query(ProductionLuckyWheelSpin.slot_id, func.count(ProductionLuckyWheelSpin.id))
            .filter(ProductionLuckyWheelSpin.is_win == True)  # noqa: E712
            .group_by(ProductionLuckyWheelSpin.slot_id)
            .all()
        )
        total_spins = self.db.query(func.count(ProductionLuckyWheelSpin.id)).scalar() or 0
        total_wins = self.db.query(func.count(ProductionLuckyWheelSpin.id)).filter(ProductionLuckyWheelSpin.is_win == True).scalar() or 0  # noqa: E712
        period_spins = self.db.query(func.count(ProductionLuckyWheelSpin.id)).filter(ProductionLuckyWheelSpin.created_at >= period_start).scalar() or 0
        redeemed = (
            self.db.query(func.count(ProductionPromotion.id))
            .filter(ProductionPromotion.code.like(f"{PERSONAL_CODE_PREFIX}%"), ProductionPromotion.used_count > 0)
            .scalar() or 0
        )
        recent = (
            self.db.query(ProductionLuckyWheelSpin)
            .order_by(ProductionLuckyWheelSpin.created_at.desc())
            .limit(30)
            .all()
        )
        return {
            "config": {k: cfg.get(k) for k in DEFAULT_CONFIG.keys()},
            "current_period_start": period_start.isoformat(),
            "next_reset_at": next_reset.isoformat(),
            "active_weight_total": round(active_weight, 3),
            "slots": [
                {
                    "id": s.id,
                    "label": s.label,
                    "promotion_id": s.promotion_id,
                    "promotion_code": s.promotion.code if s.promotion else None,
                    "promotion_name": s.promotion.name if s.promotion else None,
                    "discount_percent": float(s.promotion.discount_percent) if s.promotion else None,
                    "win_weight": float(s.win_weight or 0),
                    "probability_percent": round(float(s.win_weight or 0) / active_weight * 100, 2) if (s.is_active and active_weight > 0) else 0,
                    "quantity_total": s.quantity_total,
                    "quantity_remaining": s.quantity_remaining,
                    "is_prize": self.slot_is_prize_configured(s),
                    "color": s.color,
                    "sort_order": s.sort_order,
                    "is_active": s.is_active,
                    "win_count": int(win_counts.get(s.id, 0)),
                }
                for s in slots
            ],
            "stats": {
                "total_spins": int(total_spins),
                "total_wins": int(total_wins),
                "win_rate_percent": round(total_wins / total_spins * 100, 1) if total_spins else 0,
                "period_spins": int(period_spins),
                "vouchers_redeemed": int(redeemed),
            },
            "recent_spins": [
                {
                    "id": sp.id,
                    "customer": sp.account.full_name if sp.account else "—",
                    "email": sp.account.email if sp.account else "",
                    "slot_label": sp.slot_label,
                    "is_win": sp.is_win,
                    "voucher_code": sp.voucher_code,
                    "created_at": sp.created_at.isoformat(),
                }
                for sp in recent
            ],
        }

    # ------------------------------------------------------------------ seed
    def seed_defaults_if_empty(self) -> None:
        if self.db.query(ProductionLuckyWheelSlot.id).first():
            self.get_config()
            return
        self.get_config()
        now = _utcnow()
        templates = {}
        for pct, min_order in ((5, 0), (10, 300000), (15, 500000), (25, 800000), (50, 1000000)):
            code = f"WHEEL-TPL-{pct}"
            promo = self.db.query(ProductionPromotion).filter(ProductionPromotion.code == code).first()
            if not promo:
                promo = ProductionPromotion(
                    code=code,
                    name=f"Quà vòng quay giảm {pct}%",
                    promotion_type="VOUCHER",
                    discount_percent=pct,
                    minimum_order_amount=min_order,
                    usage_limit=None,
                    used_count=0,
                    starts_at=now,
                    ends_at=now + timedelta(days=3650),
                    # Template only: customers receive personal SPIN- codes cloned from it
                    is_active=False,
                    eligible_customer_ids=None,
                )
                self.db.add(promo)
                self.db.flush()
            templates[pct] = promo
        layout = [
            ("Giảm 5%", 5, 100, 24),
            ("Chúc may mắn", None, None, 20),
            ("Giảm 10%", 10, 50, 18),
            ("Thêm chút may mắn", None, None, 14),
            ("Giảm 15%", 15, 20, 12),
            ("Hẹn lần sau", None, None, 7),
            ("Giảm 25%", 25, 5, 4),
            ("JACKPOT -50%", 50, 1, 1),
        ]
        for idx, (label, pct, qty, weight) in enumerate(layout):
            self.db.add(ProductionLuckyWheelSlot(
                label=label,
                promotion_id=templates[pct].id if pct else None,
                win_weight=weight,
                quantity_total=qty,
                quantity_remaining=qty,
                color=SLOT_PALETTE[idx % len(SLOT_PALETTE)],
                sort_order=idx + 1,
                is_active=True,
            ))
        self.db.flush()
