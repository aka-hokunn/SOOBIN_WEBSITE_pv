"""
Customer Experience API (/api/v1/experience) — hồ sơ size, thêm nhanh, bằng chứng xã hội,
stylist chuyến đi, tìm kiếm bằng hình ảnh và điểm danh nhận Vỏ Sò.
"""
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_optional_current_user, require_role
from app.models.entities import UserAccount
from app.services.experience_service import (
    ALLOWED_IMAGE_TYPES,
    MAX_UPLOAD_BYTES,
    ExperienceService,
    presence_tracker,
)

router = APIRouter(prefix="/experience", tags=["Customer Experience"])

_VIEWER_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class FitProfilePayload(BaseModel):
    gender: str = "Nữ"
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    bust_cm: Optional[float] = None
    waist_cm: Optional[float] = None
    hip_cm: Optional[float] = None


class FitRecommendRequest(BaseModel):
    product_ids: List[int] = Field(default_factory=list, max_length=40)
    profile: Optional[FitProfilePayload] = None


class PresencePayload(BaseModel):
    product_id: int = Field(..., ge=1)
    viewer_id: str


class TripStylistRequest(BaseModel):
    trip_type: str = "bien"
    days: int = 2
    gender: Optional[str] = None
    style: str = "nang-dong"
    budget: Optional[float] = None
    profile: Optional[FitProfilePayload] = None


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Không thể lưu dữ liệu, vui lòng thử lại.")


# ----------------------------------------------------------------------------- fit profile
@router.get("/fit-profile")
def get_fit_profile(user: UserAccount = Depends(require_role(["CUSTOMER"])), db: Session = Depends(get_db)):
    return {"profile": ExperienceService(db).get_profile(user)}


@router.put("/fit-profile")
def save_fit_profile(req: FitProfilePayload, user: UserAccount = Depends(require_role(["CUSTOMER"])),
                     db: Session = Depends(get_db)):
    profile = ExperienceService(db).save_profile(user, req.model_dump())
    _commit(db)
    return {"profile": profile, "message": "Đã lưu hồ sơ size vào tài khoản."}


@router.delete("/fit-profile")
def delete_fit_profile(user: UserAccount = Depends(require_role(["CUSTOMER"])), db: Session = Depends(get_db)):
    ExperienceService(db).delete_profile(user)
    _commit(db)
    return {"profile": None}


@router.post("/fit/recommend")
def recommend_fit(req: FitRecommendRequest, user: Optional[UserAccount] = Depends(get_optional_current_user),
                  db: Session = Depends(get_db)):
    """Size phù hợp + danh sách size còn hàng (cho nút thêm nhanh) của nhiều sản phẩm cùng lúc."""
    svc = ExperienceService(db)
    profile, source = svc.resolve_profile(req.profile.model_dump() if req.profile else None, user)
    return {"profile_source": source, "items": svc.recommend_for_products(req.product_ids, profile)}


# ----------------------------------------------------------------------------- social proof
@router.get("/recent-purchases")
def recent_purchases(limit: int = Query(12, ge=1, le=30), db: Session = Depends(get_db)):
    return {"items": ExperienceService(db).recent_purchases(limit)}


@router.post("/presence")
def presence_heartbeat(req: PresencePayload):
    if not _VIEWER_RE.match(req.viewer_id or ""):
        raise HTTPException(status_code=400, detail="viewer_id không hợp lệ.")
    return {"product_id": req.product_id, "viewers": presence_tracker.heartbeat(req.product_id, req.viewer_id),
            "ttl_seconds": int(presence_tracker.ttl)}


@router.post("/presence/leave")
def presence_leave(req: PresencePayload):
    if not _VIEWER_RE.match(req.viewer_id or ""):
        raise HTTPException(status_code=400, detail="viewer_id không hợp lệ.")
    return {"product_id": req.product_id, "viewers": presence_tracker.leave(req.product_id, req.viewer_id)}


# ----------------------------------------------------------------------------- trip stylist
@router.post("/trip-stylist")
def trip_stylist(req: TripStylistRequest, user: Optional[UserAccount] = Depends(get_optional_current_user),
                 db: Session = Depends(get_db)):
    svc = ExperienceService(db)
    profile, _source = svc.resolve_profile(req.profile.model_dump() if req.profile else None, user)
    payload: Dict[str, Any] = req.model_dump(exclude={"profile"})
    return svc.trip_stylist(payload, profile)


# ----------------------------------------------------------------------------- visual search
@router.post("/visual-search")
def visual_search(image: UploadFile = File(...), category: Optional[str] = Form(None),
                  db: Session = Depends(get_db)):
    ctype = (image.content_type or "").lower()
    if ctype not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Chỉ hỗ trợ ảnh JPG, PNG hoặc WEBP.")
    data = image.file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Ảnh tải lên đang trống.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Ảnh quá lớn — tối đa 6MB.")
    if category and not re.match(r"^[a-z0-9-]{2,80}$", category):
        category = None
    return ExperienceService(db).visual_search(data, category=category)


# ----------------------------------------------------------------------------- daily check-in
@router.get("/checkin")
def get_checkin(user: UserAccount = Depends(require_role(["CUSTOMER"])), db: Session = Depends(get_db)):
    state = ExperienceService(db).checkin_state(user)
    _commit(db)
    return state


@router.post("/checkin")
def do_checkin(user: UserAccount = Depends(require_role(["CUSTOMER"])), db: Session = Depends(get_db)):
    svc = ExperienceService(db)
    try:
        result = svc.checkin(user)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Điểm danh gặp sự cố, vui lòng thử lại.")
    return result
