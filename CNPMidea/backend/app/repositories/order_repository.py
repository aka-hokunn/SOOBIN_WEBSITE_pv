from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, and_, or_, desc
from app.models.entities import (
    ProductionOrder, ProductionOrderItem, ProductionOrderDiscountOption,
    ProductionOrderHistory, ProductionPayment, ProductionShipment,
    ProductionInvoice, ProductionInvoiceItem, ProductionIntegrationEvent,
    ProductionVoucherUsage
)

class OrderRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, order_id: int) -> Optional[ProductionOrder]:
        return self.db.query(ProductionOrder).options(
            joinedload(ProductionOrder.items).joinedload(ProductionOrderItem.variant),
            joinedload(ProductionOrder.discount_options),
            joinedload(ProductionOrder.payment),
            joinedload(ProductionOrder.shipment),
            joinedload(ProductionOrder.invoice).joinedload(ProductionInvoice.items),
            joinedload(ProductionOrder.history)
        ).filter(ProductionOrder.id == order_id).first()

    def get_by_code(self, code: str) -> Optional[ProductionOrder]:
        return self.db.query(ProductionOrder).options(
            joinedload(ProductionOrder.items).joinedload(ProductionOrderItem.variant),
            joinedload(ProductionOrder.discount_options),
            joinedload(ProductionOrder.payment),
            joinedload(ProductionOrder.shipment),
            joinedload(ProductionOrder.invoice).joinedload(ProductionInvoice.items),
            joinedload(ProductionOrder.history)
        ).filter(ProductionOrder.code == code.strip()).first()

    def list_orders(
        self,
        account_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[ProductionOrder]:
        query = self.db.query(ProductionOrder).options(
            joinedload(ProductionOrder.items),
            joinedload(ProductionOrder.payment),
            joinedload(ProductionOrder.shipment),
            joinedload(ProductionOrder.invoice)
        )
        if account_id:
            query = query.filter(ProductionOrder.account_id == account_id)
        if status:
            query = query.filter(ProductionOrder.status == status)

        return query.order_by(desc(ProductionOrder.placed_at)).offset(offset).limit(limit).all()

    def create_order(self, order: ProductionOrder) -> ProductionOrder:
        self.db.add(order)
        self.db.flush()
        return order

    def add_history(self, order_id: int, from_status: Optional[str], to_status: str, event_type: str, reason: Optional[str] = None, actor_id: Optional[int] = None) -> ProductionOrderHistory:
        hist = ProductionOrderHistory(
            order_id=order_id,
            actor_account_id=actor_id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            occurred_at=datetime.now(timezone.utc)
        )
        self.db.add(hist)
        self.db.flush()
        return hist

    def create_invoice(self, invoice: ProductionInvoice) -> ProductionInvoice:
        self.db.add(invoice)
        self.db.flush()
        return invoice

    def get_invoice_by_order_id(self, order_id: int) -> Optional[ProductionInvoice]:
        return self.db.query(ProductionInvoice).options(
            joinedload(ProductionInvoice.items),
            joinedload(ProductionInvoice.order)
        ).filter(ProductionInvoice.order_id == order_id).first()

    def list_invoices(self, account_id: Optional[int] = None) -> List[ProductionInvoice]:
        query = self.db.query(ProductionInvoice).options(
            joinedload(ProductionInvoice.items),
            joinedload(ProductionInvoice.order)
        ).join(ProductionOrder)
        if account_id is not None:
            query = query.filter(ProductionOrder.account_id == account_id)
        return query.order_by(desc(ProductionInvoice.issued_at)).all()

    def get_invoice_by_code_or_id(self, code_or_id: str) -> Optional[ProductionInvoice]:
        query = self.db.query(ProductionInvoice).options(
            joinedload(ProductionInvoice.items),
            joinedload(ProductionInvoice.order)
        )
        if code_or_id.isdigit():
            return query.filter(
                or_(ProductionInvoice.id == int(code_or_id), ProductionInvoice.order_id == int(code_or_id))
            ).first()
        return query.filter(ProductionInvoice.code == code_or_id.strip()).first()

    def get_pending_refunds(self) -> List[ProductionOrder]:
        return self.db.query(ProductionOrder).options(
            joinedload(ProductionOrder.payment),
            joinedload(ProductionOrder.items)
        ).filter(
            ProductionOrder.status == "Chờ hoàn tiền"
        ).order_by(desc(ProductionOrder.placed_at)).all()

    def get_expired_unpaid_vietqr_orders(self, older_than_hours: int = 24) -> List[ProductionOrder]:
        """Find pending VietQR orders that are unpaid and exceeded 24 hours."""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
        return self.db.query(ProductionOrder).join(ProductionPayment).filter(
            ProductionOrder.status == "Chưa xử lý",
            ProductionOrder.payment_method == "VietQR",
            ProductionPayment.status == "PENDING",
            ProductionOrder.placed_at <= cutoff
        ).all()

    def record_integration_event(self, source: str, external_event_id: str, event_type: str, payload: Dict[str, Any], order_id: Optional[int] = None) -> ProductionIntegrationEvent:
        event = ProductionIntegrationEvent(
            source=source,
            external_event_id=external_event_id,
            event_type=event_type,
            payload=payload,
            order_id=order_id,
            processing_status="PROCESSED",
            received_at=datetime.now(timezone.utc),
            processed_at=datetime.now(timezone.utc)
        )
        self.db.add(event)
        self.db.flush()
        return event

    def get_integration_event(self, source: str, external_event_id: str) -> Optional[ProductionIntegrationEvent]:
        return self.db.query(ProductionIntegrationEvent).filter(
            ProductionIntegrationEvent.source == source,
            ProductionIntegrationEvent.external_event_id == external_event_id
        ).first()
