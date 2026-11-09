from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.services.payment_service import PaymentService
from app.schemas.all_schemas import MockPaymentWebhook
from app.models.entities import ProductionOrder, ProductionPayment

router = APIRouter(prefix="/mock/payment", tags=["Payment Mock"])

@router.get("/pending-vietqr")
def list_pending_vietqr_orders(db: Session = Depends(get_db)):
    orders = db.query(ProductionOrder).join(ProductionPayment).filter(
        ProductionOrder.payment_method == "VietQR",
        ProductionPayment.status == "PENDING"
    ).order_by(ProductionOrder.placed_at.desc()).all()

    return [
        {
            "order_id": o.id,
            "order_code": o.code,
            "total_amount": float(o.total_amount),
            "customer_name": o.recipient_snapshot.get("name", ""),
            "payment_status": o.payment.status,
            "placed_at": o.placed_at.isoformat()
        }
        for o in orders
    ]

@router.post("/notify")
def simulate_vietqr_payment(req: MockPaymentWebhook, db: Session = Depends(get_db)):
    svc = PaymentService(db)
    try:
        res = svc.process_vietqr_payment(
            order_code=req.order_code,
            transfer_amount=req.transfer_amount,
            transaction_id=req.external_transaction_id
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
