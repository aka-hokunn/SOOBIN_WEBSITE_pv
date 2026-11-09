from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.entities import UserAccount
from app.services.insights_service import InsightsService

router = APIRouter(prefix="/insights", tags=["Insights & Growth"])

INSIGHT_ROLES = ["ADMIN", "MANAGER"]


class CareVoucherRequest(BaseModel):
    account_ids: Optional[List[int]] = None
    segment: Optional[str] = None
    discount_percent: float = Field(10, ge=1, le=90)
    valid_days: int = Field(14, ge=1, le=365)
    minimum_order_amount: float = Field(0, ge=0)


@router.get("/kpis")
def insights_kpis(user: UserAccount = Depends(require_role(INSIGHT_ROLES)), db: Session = Depends(get_db)):
    return InsightsService(db).kpis()


@router.get("/restock-forecast")
def restock_forecast(
    days: int = Query(30, ge=1, le=365),
    cover_days: int = Query(30, ge=1, le=180),
    safety_days: int = Query(7, ge=0, le=90),
    user: UserAccount = Depends(require_role(INSIGHT_ROLES)),
    db: Session = Depends(get_db),
):
    return InsightsService(db).restock_forecast(days=days, cover_days=cover_days, safety_days=safety_days)


@router.get("/rfm")
def rfm_segments(
    segment: Optional[str] = None,
    q: Optional[str] = None,
    user: UserAccount = Depends(require_role(INSIGHT_ROLES)),
    db: Session = Depends(get_db),
):
    return InsightsService(db).rfm(segment=segment, q=q)


@router.post("/rfm/vouchers", status_code=201)
def send_care_vouchers(req: CareVoucherRequest, user: UserAccount = Depends(require_role(INSIGHT_ROLES)),
                       db: Session = Depends(get_db)):
    try:
        result = InsightsService(db).send_care_vouchers(
            account_ids=req.account_ids,
            segment=req.segment,
            discount_percent=req.discount_percent,
            valid_days=req.valid_days,
            minimum_order_amount=req.minimum_order_amount,
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Không thể gửi voucher chăm sóc. Vui lòng thử lại.")
    return result


@router.get("/wheel-performance")
def wheel_performance(user: UserAccount = Depends(require_role(INSIGHT_ROLES)), db: Session = Depends(get_db)):
    return InsightsService(db).wheel_performance()


@router.get("/audit-logs")
def audit_logs(
    q: Optional[str] = None,
    method: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: UserAccount = Depends(require_role(INSIGHT_ROLES)),
    db: Session = Depends(get_db),
):
    return InsightsService(db).audit_logs(q=q, method=method, limit=limit, offset=offset)
