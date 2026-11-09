from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.services.shipping_service import ShippingService
from app.models.entities import ProductionShipment, ProductionOrder
from app.schemas.all_schemas import MockShippingWebhook

router = APIRouter(prefix="/mock/shipping", tags=["Shipping Mock Carrier"])

@router.get("/fee")
def get_shipping_fee(db: Session = Depends(get_db)):
    svc = ShippingService(db)
    return {"carrier": "GHTK", "shipping_fee": svc.get_shipping_fee(), "estimated_days": "2 - 4 ngày"}

@router.get("/shipments")
def list_shipments(db: Session = Depends(get_db)):
    shipments = db.query(ProductionShipment).options(
        joinedload(ProductionShipment.order)
    ).order_by(ProductionShipment.created_at.desc()).all()

    return [
        {
            "id": s.id,
            "order_id": s.order_id,
            "order_code": s.order.code if s.order else "",
            "recipient_name": s.order.recipient_snapshot.get("name", "") if s.order else "",
            "recipient_phone": s.order.recipient_snapshot.get("phone", "") if s.order else "",
            "shipping_address": s.order.recipient_snapshot.get("address", "") if s.order else "",
            "carrier": s.carrier,
            "tracking_code": s.tracking_code,
            "delivery_status": s.delivery_status,
            "shipping_fee": float(s.shipping_fee_snapshot),
            "created_at": s.created_at.isoformat()
        }
        for s in shipments
    ]

@router.post("/webhook")
def shipping_webhook(req: MockShippingWebhook, db: Session = Depends(get_db)):
    svc = ShippingService(db)
    try:
        res = svc.process_carrier_webhook(
            tracking_code=req.tracking_code,
            delivery_status=req.delivery_status,
            reason=req.reason
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
