from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_optional_current_user, require_role
from app.models.entities import ProductionPromotion, UserAccount
from app.services.lucky_wheel_service import PERSONAL_CODE_PREFIX, LuckyWheelService

router = APIRouter(prefix="/lucky-wheel", tags=["Lucky Wheel"])

WHEEL_MANAGERS = ["ADMIN", "MANAGER"]


class WheelConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    spins_per_period: Optional[int] = None
    reset_interval_minutes: Optional[int] = None
    restock_on_reset: Optional[bool] = None
    voucher_valid_days: Optional[int] = None


class WheelSlotPayload(BaseModel):
    label: Optional[str] = None
    promotion_id: Optional[int] = None
    win_weight: Optional[float] = None
    quantity_total: Optional[int] = None
    quantity_remaining: Optional[int] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


def _commit(db: Session):
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Không thể lưu thay đổi vòng quay. Vui lòng thử lại.")


# ----------------------------------------------------------------------------- public / customer
@router.get("")
def get_wheel(user: Optional[UserAccount] = Depends(get_optional_current_user), db: Session = Depends(get_db)):
    data = LuckyWheelService(db).public_state(user)
    _commit(db)
    return data


@router.post("/spin")
def spin_wheel(user: UserAccount = Depends(require_role(["CUSTOMER"])), db: Session = Depends(get_db)):
    service = LuckyWheelService(db)
    try:
        result = service.spin(user)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Vòng quay gặp sự cố, lượt quay của bạn chưa bị trừ. Vui lòng thử lại.")
    return result


@router.get("/my-vouchers")
def my_wheel_vouchers(user: UserAccount = Depends(require_role(["CUSTOMER"])), db: Session = Depends(get_db)):
    return LuckyWheelService(db).my_vouchers(user)


# ----------------------------------------------------------------------------- admin + manager
@router.get("/manage")
def manage_wheel(user: UserAccount = Depends(require_role(WHEEL_MANAGERS)), db: Session = Depends(get_db)):
    data = LuckyWheelService(db).manage_state()
    _commit(db)
    return data


@router.get("/manage/vouchers")
def wheel_voucher_options(user: UserAccount = Depends(require_role(WHEEL_MANAGERS)), db: Session = Depends(get_db)):
    """Voucher có thể gắn vào ô quay (loại trừ mã cá nhân SPIN- đã phát cho khách)."""
    promos = (
        db.query(ProductionPromotion)
        .filter(ProductionPromotion.promotion_type == "VOUCHER", ~ProductionPromotion.code.like(f"{PERSONAL_CODE_PREFIX}%"),
                ~ProductionPromotion.code.like("CARE-%"))  # mã chăm sóc cá nhân (module Phân Tích)
        .order_by(ProductionPromotion.created_at.desc())
        .all()
    )
    return [
        {
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "discount_percent": float(p.discount_percent),
            "minimum_order_amount": float(p.minimum_order_amount),
            "usage_limit": p.usage_limit,
            "used_count": p.used_count,
            "is_active": p.is_active,
            "ends_at": p.ends_at.isoformat(),
        }
        for p in promos
    ]


@router.put("/manage/config")
def update_wheel_config(req: WheelConfigUpdate, user: UserAccount = Depends(require_role(WHEEL_MANAGERS)), db: Session = Depends(get_db)):
    cfg = LuckyWheelService(db).update_config(req.model_dump(exclude_unset=True))
    _commit(db)
    return {"message": "Đã lưu cấu hình vòng quay may mắn.", "config": cfg}


@router.post("/manage/slots", status_code=201)
def create_wheel_slot(req: WheelSlotPayload, user: UserAccount = Depends(require_role(WHEEL_MANAGERS)), db: Session = Depends(get_db)):
    slot = LuckyWheelService(db).create_slot(req.model_dump(exclude_unset=True))
    _commit(db)
    return {"message": f"Đã thêm ô '{slot.label}' vào vòng quay.", "id": slot.id}


@router.put("/manage/slots/{slot_id}")
def update_wheel_slot(slot_id: int, req: WheelSlotPayload, user: UserAccount = Depends(require_role(WHEEL_MANAGERS)), db: Session = Depends(get_db)):
    slot = LuckyWheelService(db).update_slot(slot_id, req.model_dump(exclude_unset=True))
    _commit(db)
    return {"message": f"Đã cập nhật ô '{slot.label}'.", "id": slot.id}


@router.delete("/manage/slots/{slot_id}")
def delete_wheel_slot(slot_id: int, user: UserAccount = Depends(require_role(WHEEL_MANAGERS)), db: Session = Depends(get_db)):
    LuckyWheelService(db).delete_slot(slot_id)
    _commit(db)
    return {"message": "Đã xoá ô khỏi vòng quay."}


@router.post("/manage/reset")
def reset_wheel_now(user: UserAccount = Depends(require_role(WHEEL_MANAGERS)), db: Session = Depends(get_db)):
    LuckyWheelService(db).reset_now()
    _commit(db)
    return {"message": "Đã reset vòng quay: mọi khách hàng được hồi lượt quay và số lượng voucher đã được nạp lại."}

