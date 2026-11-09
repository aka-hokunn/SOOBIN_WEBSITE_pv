from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid
from sqlalchemy.orm import Session
from app.repositories.order_repository import OrderRepository
from app.core.config import settings
from app.models.entities import ProductionInvoice, ProductionInvoiceItem

class ShippingService:
    def __init__(self, db: Session):
        self.db = db
        self.order_repo = OrderRepository(db)

    def get_shipping_fee(self) -> float:
        return settings.MOCK_SHIPPING_FEE

    def process_carrier_webhook(
        self,
        tracking_code: str,
        delivery_status: str, # IN_TRANSIT, DELIVERED, FAILED
        event_id: Optional[str] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handles shipping webhook with idempotency protection (E2E-07).
        Updates order status and generates invoice on DELIVERED.
        """
        # Idempotency check
        ext_id = event_id or f"EVT-SHIP-{tracking_code}-{delivery_status}"
        existing_evt = self.order_repo.get_integration_event("SHIPPING_GHTK", ext_id)
        if existing_evt:
            return {"status": "ALREADY_PROCESSED", "message": "Sự kiện webhook này đã được xử lý trước đó."}

        # Find order with this tracking code
        order = self.db.query(self.order_repo.get_by_id(1).__class__).filter(
            self.order_repo.get_by_id(1).__class__.shipment.has(tracking_code=tracking_code)
        ).first()

        if not order:
            raise ValueError(f"Không tìm thấy đơn hàng với mã vận đơn '{tracking_code}'.")

        shipment = order.shipment
        from_status = order.status

        if delivery_status == "IN_TRANSIT":
            if order.status == "Đã xử lý":
                order.status = "Đang vận chuyển"
                shipment.delivery_status = "IN_TRANSIT"
                self.order_repo.add_history(
                    order_id=order.id,
                    from_status=from_status,
                    to_status="Đang vận chuyển",
                    event_type="SHIPMENT_IN_TRANSIT",
                    reason="Đơn vị vận chuyển GHTK đã lấy hàng và đang giao"
                )

        elif delivery_status == "DELIVERED":
            if order.status == "Đang vận chuyển":
                order.status = "Đã giao"
                shipment.delivery_status = "DELIVERED"
                shipment.delivered_at = datetime.now(timezone.utc)

                # For COD, record payment received
                if order.payment_method == "COD" and order.payment:
                    order.payment.status = "PAID"
                    order.payment.received_amount = order.total_amount
                    order.payment.paid_at = datetime.now(timezone.utc)

                # Generate invoice (PRD Section 11: Exactly one invoice per delivered order)
                existing_invoice = self.order_repo.get_invoice_by_order_id(order.id)
                if not existing_invoice:
                    from app.controllers.site_settings_controller import (
                        build_vietqr_payment_instruction, get_after_sales_policy_dict
                    )
                    store_snap = dict(order.store_snapshot or {})
                    store_snap["bank_account"] = build_vietqr_payment_instruction(self.db, order.code, float(order.total_amount))
                    store_snap["after_sales_policy"] = get_after_sales_policy_dict(self.db)
                    order.store_snapshot = store_snap

                    inv_code = f"HD-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
                    invoice = ProductionInvoice(
                        order_id=order.id,
                        code=inv_code,
                        issued_at=datetime.now(timezone.utc),
                        subtotal=order.subtotal,
                        discount_amount=order.discount_amount,
                        shipping_fee=order.shipping_fee,
                        total_amount=order.total_amount,
                        customer_snapshot=order.recipient_snapshot,
                        store_snapshot=store_snap
                    )
                    self.db.add(invoice)
                    self.db.flush()

                    for itm in order.items:
                        inv_item = ProductionInvoiceItem(
                            invoice_id=invoice.id,
                            order_item_id=itm.id,
                            quantity=itm.quantity,
                            unit_price=itm.unit_price,
                            discount_amount=itm.allocated_discount_amount,
                            line_total=itm.line_total,
                            unit_cost_snapshot=itm.unit_cost_snapshot,
                            product_snapshot=itm.product_snapshot,
                            promotion_snapshot=itm.promotion_snapshot
                        )
                        self.db.add(inv_item)

                self.order_repo.add_history(
                    order_id=order.id,
                    from_status=from_status,
                    to_status="Đã giao",
                    event_type="SHIPMENT_DELIVERED",
                    reason="Khách hàng đã nhận hàng thành công, hệ thống đã xuất hóa đơn"
                )

        elif delivery_status == "FAILED":
            if order.status == "Đang vận chuyển":
                shipment.delivery_status = "FAILED"
                # PRD rule:
                # If COD -> moves to 'Giao không thành công' (no restock, no refund)
                # If VietQR and paid -> moves to 'Chờ hoàn tiền' (refund = subtotal - discount, no restock)
                if order.payment_method == "VietQR" and order.payment and order.payment.status == "PAID":
                    order.status = "Chờ hoàn tiền"
                    order.refund_amount = float(order.subtotal - order.discount_amount)
                    self.order_repo.add_history(
                        order_id=order.id,
                        from_status=from_status,
                        to_status="Chờ hoàn tiền",
                        event_type="SHIPMENT_FAILED_REFUND_PENDING",
                        reason=reason or "Giao hàng thất bại đối với đơn VietQR đã trả tiền, chuyển sang Chờ hoàn tiền"
                    )
                else:
                    order.status = "Giao không thành công"
                    self.order_repo.add_history(
                        order_id=order.id,
                        from_status=from_status,
                        to_status="Giao không thành công",
                        event_type="SHIPMENT_FAILED",
                        reason=reason or "Giao hàng thất bại, khách không nhận hàng hoặc không liên lạc được"
                    )

        # Log integration event for idempotency
        self.order_repo.record_integration_event(
            source="SHIPPING_GHTK",
            external_event_id=ext_id,
            event_type=f"GHTK_{delivery_status}",
            payload={"tracking_code": tracking_code, "delivery_status": delivery_status, "reason": reason},
            order_id=order.id
        )

        self.db.commit()
        return {
            "status": "SUCCESS",
            "order_code": order.code,
            "order_status": order.status,
            "delivery_status": shipment.delivery_status
        }
