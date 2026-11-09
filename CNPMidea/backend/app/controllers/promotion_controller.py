from typing import Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_role
from app.services.promotion_service import PromotionService
from app.repositories.promotion_repository import PromotionRepository
from app.models.entities import ProductionPromotion, ProductionPromotionProduct, UserAccount
from app.schemas.all_schemas import PromotionCreate


class QuickVoucherRequest(BaseModel):
    code: str
    name: Optional[str] = None
    discount_type: Optional[str] = "PERCENT"
    discount_value: Optional[float] = None
    discount_percent: float = 15.0
    minimum_order_amount: float = 0.0
    min_order_amount: Optional[float] = None
    usage_limit: Optional[int] = 100
    duration_days: int = 30

router = APIRouter(prefix="/promotions", tags=["Promotions"])

@router.get("/vouchers")
def list_vouchers(db: Session = Depends(get_db)):
    # Chỉ liệt kê voucher công khai — voucher cá nhân (SPIN-/CARE-, có eligible_customer_ids)
    # là mã riêng của từng khách nên không được lộ ra endpoint công khai.
    promos = [
        p for p in db.query(ProductionPromotion).filter(
            ProductionPromotion.promotion_type == "VOUCHER"
        ).order_by(ProductionPromotion.created_at.desc()).all()
        if p.eligible_customer_ids is None  # JSON null hoặc SQL NULL đều là None ở Python
    ]
    return [
        {
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "discount_type": "PERCENT",
            "discount_value": float(p.discount_percent),
            "discount_percent": float(p.discount_percent),
            "minimum_order_amount": float(p.minimum_order_amount),
            "is_active": p.is_active,
        }
        for p in promos
    ]

@router.get("")
def list_promotions(db: Session = Depends(get_db)):
    repo = PromotionRepository(db)
    promos = [p for p in repo.list_active_promotions() if p.eligible_customer_ids is None]
    return [
        {
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "type": p.promotion_type,
            "promotion_type": p.promotion_type,
            "discount_percent": float(p.discount_percent),
            "minimum_order_amount": float(p.minimum_order_amount),
            "usage_limit": p.usage_limit,
            "used_count": p.used_count,
            "starts_at": p.starts_at.isoformat(),
            "ends_at": p.ends_at.isoformat(),
            "is_active": p.is_active,
            "audience": "Tất cả khách hàng" if p.eligible_customer_ids is None else f"{len(p.eligible_customer_ids)} khách hàng được chọn"
        }
        for p in promos
    ]

@router.get("/manage")
def list_promotions_for_admin(
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db)
):
    promos = db.query(ProductionPromotion).order_by(ProductionPromotion.created_at.desc()).all()
    return [{
        "id": p.id, "code": p.code, "name": p.name, "type": p.promotion_type,
        "promotion_type": p.promotion_type, "discount_percent": float(p.discount_percent),
        "minimum_order_amount": float(p.minimum_order_amount), "usage_limit": p.usage_limit,
        "used_count": p.used_count, "starts_at": p.starts_at.isoformat(), "ends_at": p.ends_at.isoformat(),
        "is_active": p.is_active,
        "audience": "Tất cả khách hàng" if p.eligible_customer_ids is None else f"{len(p.eligible_customer_ids)} khách hàng được chọn"
    } for p in promos]

@router.post("", status_code=status.HTTP_201_CREATED)
def create_promotion(
    req: PromotionCreate,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db)
):
    promo_type = req.promotion_type.upper().strip()
    if promo_type not in ("VOUCHER", "ORDER", "PRODUCT"):
        raise HTTPException(status_code=400, detail="Loại khuyến mãi phải là VOUCHER, ORDER hoặc PRODUCT.")
    if req.starts_at >= req.ends_at:
        raise HTTPException(status_code=400, detail="Thời gian kết thúc phải sau thời gian bắt đầu.")
    code = req.code.strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="Mã chương trình không được để trống.")
    repo = PromotionRepository(db)
    if repo.get_by_code(code):
        raise HTTPException(status_code=409, detail="Mã khuyến mãi đã tồn tại.")
    eligible_ids = req.eligible_customer_ids
    if eligible_ids is not None:
        if not eligible_ids:
            raise HTTPException(status_code=400, detail="Hãy chọn ít nhất một khách hàng hoặc chọn áp dụng cho tất cả.")
        customers = db.query(UserAccount).filter(UserAccount.id.in_(eligible_ids)).all()
        if len(customers) != len(set(eligible_ids)) or any(c.role.code != "CUSTOMER" for c in customers):
            raise HTTPException(status_code=400, detail="Danh sách chỉ được chứa tài khoản khách hàng hợp lệ.")
    promo = ProductionPromotion(
        code=code, name=req.name.strip(), promotion_type=promo_type, discount_percent=req.discount_percent,
        minimum_order_amount=req.minimum_order_amount, usage_limit=req.usage_limit, used_count=0,
        starts_at=req.starts_at, ends_at=req.ends_at, is_active=True,
        eligible_customer_ids=eligible_ids
    )
    try:
        repo.create_promotion(promo)
        if promo_type == "PRODUCT" and req.product_ids:
            for pid in set(req.product_ids):
                db.add(ProductionPromotionProduct(promotion_id=promo.id, product_id=pid))
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Không thể tạo chương trình khuyến mãi. Vui lòng kiểm tra dữ liệu nhập.")
    return {"message": "Đã tạo chương trình khuyến mãi.", "id": promo.id, "code": promo.code, "type": promo.promotion_type}

@router.post("/{promo_id}/toggle")
def toggle_promotion_active(
    promo_id: int,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db)
):
    promo = db.query(ProductionPromotion).filter(ProductionPromotion.id == promo_id).first()
    if not promo:
        raise HTTPException(status_code=404, detail="Không tìm thấy chương trình khuyến mãi.")
    promo.is_active = not promo.is_active
    db.commit()
    return {
        "message": f"Đã {'kích hoạt' if promo.is_active else 'tạm dừng'} chương trình {promo.code}.",
        "id": promo.id,
        "is_active": promo.is_active
    }

@router.get("/check-voucher/{code}")
def check_voucher(code: str, db: Session = Depends(get_db)):
    repo = PromotionRepository(db)
    vc = repo.get_by_code(code)
    if not vc or vc.promotion_type != "VOUCHER":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mã voucher không tồn tại.")
    if not vc.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mã voucher đã bị tạm khóa.")
    if vc.usage_limit is not None and vc.used_count >= vc.usage_limit:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mã voucher đã hết lượt sử dụng.")

    return {
        "code": vc.code,
        "name": vc.name,
        "discount_percent": float(vc.discount_percent),
        "minimum_order_amount": float(vc.minimum_order_amount),
        "remaining_uses": (vc.usage_limit - vc.used_count) if vc.usage_limit else "Không giới hạn"
    }


@router.post("/quick-voucher")
def create_quick_voucher(
    req: QuickVoucherRequest,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db)
):
    code = (req.code or "").strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="Mã voucher không được để trống.")
    pct = float(req.discount_value if req.discount_value is not None else req.discount_percent)
    if req.discount_type == "FIXED" and pct > 90:
        pct = min(50.0, max(5.0, round((pct / 500000.0) * 100, 1)))
    if pct <= 0 or pct > 90:
        raise HTTPException(status_code=400, detail="Phần trăm giảm giá phải từ 1% đến 90%.")
    min_ord = float(req.min_order_amount if req.min_order_amount is not None else req.minimum_order_amount)

    now = datetime.now(timezone.utc)
    ends = now + timedelta(days=max(1, req.duration_days))
    name = (req.name or f"Voucher Ưu Đãi {code} (-{pct:.0f}%)").strip()

    existing = db.query(ProductionPromotion).filter(ProductionPromotion.code == code).first()
    if existing:
        existing.name = name
        existing.promotion_type = "VOUCHER"
        existing.discount_percent = pct
        existing.minimum_order_amount = min_ord
        existing.usage_limit = req.usage_limit
        existing.starts_at = now - timedelta(minutes=5)
        existing.ends_at = ends
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return {
            "message": f"Đã cập nhật & kích hoạt mã voucher {code} (-{pct:.0f}%).",
            "voucher": {
                "id": existing.id,
                "code": existing.code,
                "name": existing.name,
                "discount_type": "PERCENT",
                "discount_value": float(existing.discount_percent),
                "discount_percent": float(existing.discount_percent),
                "minimum_order_amount": float(existing.minimum_order_amount),
                "usage_limit": existing.usage_limit,
                "is_active": existing.is_active,
            }
        }

    promo = ProductionPromotion(
        code=code,
        name=name,
        promotion_type="VOUCHER",
        discount_percent=pct,
        minimum_order_amount=min_ord,
        usage_limit=req.usage_limit,
        used_count=0,
        starts_at=now - timedelta(minutes=5),
        ends_at=ends,
        is_active=True,
        eligible_customer_ids=None,
    )
    db.add(promo)
    db.commit()
    db.refresh(promo)
    return {
        "message": f"Đã phát hành mã voucher {code} giảm {pct:.0f}% thành công!",
        "voucher": {
            "id": promo.id,
            "code": promo.code,
            "name": promo.name,
            "discount_type": "PERCENT",
            "discount_value": float(promo.discount_percent),
            "discount_percent": float(promo.discount_percent),
            "minimum_order_amount": float(promo.minimum_order_amount),
            "usage_limit": promo.usage_limit,
            "is_active": promo.is_active,
        }
    }
