from datetime import datetime, timezone
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.entities import ProductionSiteSetting, ProductionFeedback, UserAccount
from app.schemas.all_schemas import (
    StorefrontThemeConfig, FeedbackCreateRequest, FeedbackUpdateRequest,
    AfterSalesPolicyConfig, BankAccountConfig
)

router = APIRouter(prefix="/site-settings", tags=["Site Settings"])
DEFAULT_BANNER = "🔥 Chào Hè 2026: Nhập mã SOOBIN15 giảm ngay 15% | Đơn từ 500k giảm 10% tự động"

DEFAULT_THEME_CONFIG = {
    "theme": "ocean-luxury",
    "morph_enabled": True,
    "tilt_3d_enabled": True,
    "hero_badge": "RUNWAY RESORT COLLECTION 2026",
    "hero_title": "Tôn Vinh Đường Nét & Chuyển Động 3D",
    "flash_sale_title": "⚡ FLASH SALE ATELIER — ƯU ĐÃI ĐẶC QUYỀN"
}

DEFAULT_AFTER_SALES_POLICY = {
    "return_window_days": 7,
    "exchange_size_window_days": 15,
    "warranty_window_days": 90,
    "vietqr_payment_timeout_hours": 24,
    "enforce_time_limit": True,
    "warranty_terms": "Đổi size miễn phí khi còn nguyên tem mác; Bảo hành miễn phí đường chỉ, khóa kéo và phụ kiện kim loại chống muối biển.",
    "receiving_workflow": [
        {
            "role": "SALES",
            "title": "Bộ phận CSKH & Tư vấn Bán hàng (Cổng /sales)",
            "responsibility": "Người tiếp nhận đầu tiên mọi yêu cầu Đổi size / Bảo hành / Phản hồi đơn hàng của khách, kiểm tra hạn bảo hành và liên hệ xác nhận với khách."
        },
        {
            "role": "MANAGER / ADMIN",
            "title": "Chủ cửa hàng & Quản lý (Cổng /manager & /admin)",
            "responsibility": "Cấu hình thời hạn trả hàng/bảo hành/đổi size, phê duyệt phương án đổi trả hoặc hoàn tiền chuyển khoản cho khách."
        },
        {
            "role": "WAREHOUSE",
            "title": "Bộ phận Kho vận & Kiểm định (Cổng /warehouse)",
            "responsibility": "Tiếp nhận sản phẩm khách gửi về bảo hành/đổi trả, kiểm tra chất lượng và xuất sản phẩm size mới hoặc hàng bảo hành."
        }
    ]
}

DEFAULT_BANK_ACCOUNT_CONFIG = {
    "bank_code": "MB",
    "bank_name": settings.BANK_NAME or "MBBank (Ngân hàng Quân Đội)",
    "account_no": settings.BANK_ACCOUNT_NO or "0389998888",
    "account_name": settings.BANK_ACCOUNT_NAME or "SOOBIN SWIMWEAR ATELIER",
    "bank_branch": "Chi nhánh TP. Hồ Chí Minh",
    "transfer_prefix": "SOOBIN",
    "qr_template": "compact2"
}


def get_after_sales_policy_dict(db: Session) -> dict:
    setting = db.query(ProductionSiteSetting).filter(ProductionSiteSetting.key == "after_sales_policy").first()
    payload = setting.value if setting and isinstance(setting.value, dict) else {}
    return {**DEFAULT_AFTER_SALES_POLICY, **payload}


def get_bank_account_config_dict(db: Session) -> dict:
    setting = db.query(ProductionSiteSetting).filter(ProductionSiteSetting.key == "store_bank_account").first()
    payload = setting.value if setting and isinstance(setting.value, dict) else {}
    return {**DEFAULT_BANK_ACCOUNT_CONFIG, **payload}


def build_vietqr_payment_instruction(db: Session, order_code: str, amount: float) -> dict:
    bank = get_bank_account_config_dict(db)
    bank_code = (bank.get("bank_code") or "MB").strip().upper()
    account_no = (bank.get("account_no") or settings.BANK_ACCOUNT_NO).strip()
    account_name = (bank.get("account_name") or settings.BANK_ACCOUNT_NAME).strip().upper()
    prefix = (bank.get("transfer_prefix") or "SOOBIN").strip().upper()
    template = (bank.get("qr_template") or "compact2").strip()
    int_amount = max(0, int(round(float(amount or 0))))
    transfer_content = f"{prefix} {order_code}" if prefix and not order_code.upper().startswith(prefix) else order_code
    qr_url = (
        f"https://img.vietqr.io/image/{quote(bank_code)}-{quote(account_no)}-{quote(template)}.png"
        f"?amount={int_amount}&addInfo={quote(transfer_content)}&accountName={quote(account_name)}"
    )
    return {
        "bank_code": bank_code,
        "bank_name": bank.get("bank_name") or bank_code,
        "account_no": account_no,
        "account_name": account_name,
        "bank_branch": bank.get("bank_branch") or "",
        "amount": float(amount or 0),
        "transfer_content": transfer_content,
        "qr_template": template,
        "qr_url": qr_url
    }



class BannerUpdate(BaseModel):
    text: str = Field(..., min_length=1, max_length=300)


@router.get("/banner")
def get_banner(db: Session = Depends(get_db)):
    setting = db.query(ProductionSiteSetting).filter(ProductionSiteSetting.key == "storefront_banner").first()
    payload = setting.value if setting else None
    text = payload.get("text") if isinstance(payload, dict) else None
    return {"text": text or DEFAULT_BANNER}


@router.put("/banner")
def update_banner(
    req: BannerUpdate,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db)
):
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Nội dung băng rôn không được để trống.")
    setting = db.query(ProductionSiteSetting).filter(ProductionSiteSetting.key == "storefront_banner").first()
    if setting:
        setting.value = {"text": text}
    else:
        db.add(ProductionSiteSetting(key="storefront_banner", value={"text": text}))
    db.commit()
    return {"message": "Đã cập nhật băng rôn.", "text": text}


@router.get("/theme")
def get_storefront_theme(db: Session = Depends(get_db)):
    setting = db.query(ProductionSiteSetting).filter(ProductionSiteSetting.key == "storefront_theme").first()
    payload = setting.value if setting and isinstance(setting.value, dict) else {}
    merged = {**DEFAULT_THEME_CONFIG, **payload}
    return merged


@router.put("/theme")
def update_storefront_theme(
    req: StorefrontThemeConfig,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db)
):
    valid_themes = {"ocean-luxury", "sunset-ibiza", "midnight-vogue", "minimal-atelier"}
    if req.theme not in valid_themes:
        raise HTTPException(status_code=400, detail="Theme không hợp lệ.")
    val = req.model_dump()
    setting = db.query(ProductionSiteSetting).filter(ProductionSiteSetting.key == "storefront_theme").first()
    if setting:
        setting.value = val
    else:
        db.add(ProductionSiteSetting(key="storefront_theme", value=val))
    db.commit()
    return {"message": f"Đã cập nhật giao diện thương hiệu sang '{req.theme}'.", **val}


@router.post("/feedbacks", status_code=201)
def submit_customer_feedback(
    req: FeedbackCreateRequest,
    db: Session = Depends(get_db)
):
    s_name = (req.sender_name or req.full_name or "Khách hàng Soobin").strip()
    s_email = (req.sender_email or req.email or "guest@soobin.vn").strip()
    prefix = f"[{req.subject.strip()}] " if req.subject else ""
    fb = ProductionFeedback(
        account_id=None,
        sender_name=s_name,
        sender_email=s_email,
        message=f"{prefix}{req.message.strip()}",
        status="NEW"
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    ticket_obj = {
        "id": fb.id,
        "sender_name": fb.sender_name,
        "full_name": fb.sender_name,
        "sender_email": fb.sender_email,
        "email": fb.sender_email,
        "phone": req.phone or "",
        "subject": req.subject or "Tư vấn Stylist & CSKH",
        "message": fb.message,
        "status": fb.status,
        "created_at": fb.created_at.isoformat()
    }
    return {
        **ticket_obj,
        "ticket": ticket_obj,
        "message": "Cảm ơn bạn! Yêu cầu tư vấn / góp ý đã được gửi tới đội ngũ Stylist & CSKH Soobin."
    }


@router.get("/feedbacks")
def list_customer_feedbacks(
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "SALES", "WAREHOUSE"])),
    db: Session = Depends(get_db)
):
    items = db.query(ProductionFeedback).order_by(ProductionFeedback.created_at.desc()).limit(100).all()
    res = []
    for f in items:
        msg = f.message or ""
        subject = "Tư vấn Stylist & CSKH"
        if msg.startswith("[") and "]" in msg:
            end_idx = msg.find("]")
            subject = msg[1:end_idx].strip()
        res.append({
            "id": f.id,
            "account_id": f.account_id,
            "sender_name": f.sender_name,
            "full_name": f.sender_name,
            "sender_email": f.sender_email,
            "email": f.sender_email,
            "subject": subject,
            "message": msg,
            "status": f.status,
            "handled_by": f.handled_by,
            "handled_at": f.handled_at.isoformat() if f.handled_at else None,
            "created_at": f.created_at.isoformat()
        })
    return res


@router.put("/feedbacks/{feedback_id}")
def update_feedback_status(
    feedback_id: int,
    req: FeedbackUpdateRequest,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "SALES", "WAREHOUSE"])),
    db: Session = Depends(get_db)
):
    fb = db.query(ProductionFeedback).filter(ProductionFeedback.id == feedback_id).first()
    if not fb:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu phản hồi.")
    fb.status = req.status
    fb.handled_by = user.id
    fb.handled_at = datetime.now(timezone.utc)
    db.commit()
    return {"id": fb.id, "status": fb.status, "message": f"Đã cập nhật trạng thái phiếu #{feedback_id} sang {req.status}."}


@router.get("/after-sales-policy")
def get_after_sales_policy(db: Session = Depends(get_db)):
    return get_after_sales_policy_dict(db)


@router.put("/after-sales-policy")
def update_after_sales_policy(
    req: AfterSalesPolicyConfig,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db)
):
    val = req.model_dump()
    setting = db.query(ProductionSiteSetting).filter(ProductionSiteSetting.key == "after_sales_policy").first()
    if setting:
        setting.value = {**get_after_sales_policy_dict(db), **val}
    else:
        db.add(ProductionSiteSetting(key="after_sales_policy", value={**DEFAULT_AFTER_SALES_POLICY, **val}))
    db.commit()
    return {
        "message": (
            f"Đã lưu chính sách hậu mãi: Trả hàng {req.return_window_days} ngày, "
            f"Đổi size {req.exchange_size_window_days} ngày, Bảo hành {req.warranty_window_days} ngày."
        ),
        **get_after_sales_policy_dict(db)
    }


@router.get("/bank-account")
def get_store_bank_account(db: Session = Depends(get_db)):
    cfg = get_bank_account_config_dict(db)
    sample_qr = build_vietqr_payment_instruction(db, "SOOBIN-DEMO", 500000)
    return {
        **cfg,
        "sample_qr_url": sample_qr["qr_url"]
    }


@router.put("/bank-account")
def update_store_bank_account(
    req: BankAccountConfig,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db)
):
    val = {
        "bank_code": req.bank_code.strip().upper(),
        "bank_name": req.bank_name.strip(),
        "account_no": req.account_no.strip(),
        "account_name": req.account_name.strip().upper(),
        "bank_branch": (req.bank_branch or "").strip(),
        "transfer_prefix": req.transfer_prefix.strip().upper(),
        "qr_template": req.qr_template.strip() or "compact2"
    }
    setting = db.query(ProductionSiteSetting).filter(ProductionSiteSetting.key == "store_bank_account").first()
    if setting:
        setting.value = val
    else:
        db.add(ProductionSiteSetting(key="store_bank_account", value=val))
    db.commit()
    sample_qr = build_vietqr_payment_instruction(db, "SOOBIN-DEMO", 500000)
    return {
        "message": f"Đã cập nhật tài khoản nhận tiền chuyển khoản: {val['bank_name']} - STK {val['account_no']} ({val['account_name']}).",
        **val,
        "sample_qr_url": sample_qr["qr_url"]
    }

