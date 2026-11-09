from typing import Dict, Any, Optional
from datetime import datetime, timezone
import re
import uuid
from sqlalchemy.orm import Session
from app.repositories.order_repository import OrderRepository
from app.models.entities import ProductionPayment, ProductionOrder

class PaymentService:
    def __init__(self, db: Session):
        self.db = db
        self.order_repo = OrderRepository(db)

    def process_vietqr_payment(
        self,
        order_code: str,
        transfer_amount: float,
        transaction_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Simulate or process receipt of VietQR bank transfer (E2E-02, E2E-07).
        """
        ext_id = transaction_id or f"TXN-MB-{order_code}-{int(transfer_amount)}"

        # Idempotency check
        existing_evt = self.order_repo.get_integration_event("PAYMENT_VIETQR", ext_id)
        if existing_evt:
            return {"status": "ALREADY_PROCESSED", "message": "Giao dịch thanh toán này đã được ghi nhận trước đó."}

        order = self.order_repo.get_by_code(order_code)
        if not order:
            raise ValueError(f"Không tìm thấy đơn hàng với mã '{order_code}'.")

        payment = order.payment
        if not payment:
            raise ValueError(f"Đơn hàng '{order_code}' không có thông tin thanh toán.")

        if payment.status == "PAID":
            return {"status": "ALREADY_PAID", "message": "Đơn hàng này đã được thanh toán trước đó."}

        # Check amount
        if transfer_amount < float(payment.expected_amount):
            raise ValueError(f"Số tiền chuyển khoản ({transfer_amount:,.0f}đ) không đủ so với tổng đơn ({float(payment.expected_amount):,.0f}đ).")

        payment.status = "PAID"
        payment.received_amount = transfer_amount
        payment.paid_at = datetime.now(timezone.utc)
        payment.external_transaction_id = ext_id

        self.order_repo.add_history(
            order_id=order.id,
            from_status=order.status,
            to_status=order.status,
            event_type="PAYMENT_RECEIVED",
            reason=f"Hệ thống đã nhận được chuyển khoản ngân hàng {transfer_amount:,.0f}đ qua VietQR (Mã GD: {ext_id})"
        )

        self.order_repo.record_integration_event(
            source="PAYMENT_VIETQR",
            external_event_id=ext_id,
            event_type="VIETQR_CREDIT_NOTIFICATION",
            payload={"order_code": order_code, "amount": transfer_amount, "transaction_id": ext_id},
            order_id=order.id
        )

        self.db.commit()

        return {
            "status": "SUCCESS",
            "order_id": order.id,
            "order_code": order.code,
            "order_status": order.status,
            "payment_status": payment.status,
            "transaction_id": ext_id,
            "amount_received": transfer_amount,
            "message": f"Đã xác nhận thanh toán chuyển khoản thành công cho đơn {order.code}!"
        }

    def process_real_bank_webhook(
        self,
        content: str,
        transfer_amount: float,
        transaction_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Automatically extract order_code (e.g., SOOBIN-YYYYMMDD-XXXXXX or POS-YYYYMMDD-XXXXXX)
        from bank transfer memo/content (SePay / Casso / VietQR Webhook) and mark order as PAID.
        """
        raw = (content or "").upper()
        match = re.search(r"((?:SOOBIN|POS)-\d{8}-[A-Z0-9]{4,10})", raw)
        matched_code = match.group(1) if match else None

        if not matched_code:
            # Also try normalized alphanumeric match (some banks strip hyphens in transfer descriptions)
            compact = re.sub(r"[^A-Z0-9]", "", raw)
            recent_orders = self.db.query(ProductionOrder).order_by(ProductionOrder.id.desc()).limit(200).all()
            for o in recent_orders:
                norm_code = re.sub(r"[^A-Z0-9]", "", (o.code or "").upper())
                if norm_code and norm_code in compact:
                    matched_code = o.code
                    break

        if not matched_code:
            raise ValueError(f"Không tìm thấy mã đơn hàng hợp lệ trong nội dung chuyển khoản: '{content}'.")

        tx_id = (transaction_id or "").strip() or f"WEBHOOK-{uuid.uuid4().hex[:8].upper()}"
        if matched_code not in tx_id:
            tx_id = f"{tx_id}-{matched_code}"

        return self.process_vietqr_payment(
            order_code=matched_code,
            transfer_amount=transfer_amount,
            transaction_id=tx_id
        )

