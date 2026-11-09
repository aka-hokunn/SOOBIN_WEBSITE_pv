from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService
from app.services.promotion_service import PromotionService
from app.controllers.site_settings_controller import (
    build_vietqr_payment_instruction, get_after_sales_policy_dict
)
from app.schemas.all_schemas import (
    OrderCreateRequest, OrderCancelRequest, ManualRefundRequest, POSOrderCreateRequest,
    OrderExchangeRequest, BankTransferConfirmRequest, CustomerReportTransferRequest,
    RealBankWebhookPayload, RMATicketUpdateRequest
)
from app.models.entities import UserAccount

router = APIRouter(prefix="/orders", tags=["Orders"])

@router.post("/calculate-discount")
def calculate_discount_preview(
    voucher_code: Optional[str] = None,
    user: UserAccount = Depends(require_role(["CUSTOMER"])),
    db: Session = Depends(get_db)
):
    ord_service = OrderService(db)
    cart_items = ord_service.cart_repo.get_cart_items(user.id)
    items_data = [
        {
            "variant_id": ci.variant_id,
            "product_id": ci.variant.product_id,
            "unit_price": float(ci.variant.product.base_price),
            "quantity": ci.quantity
        }
        for ci in cart_items if ci.variant and ci.variant.product
    ]
    promo_service = PromotionService(db)
    return promo_service.calculate_discounts(items=items_data, voucher_code=voucher_code, account_id=user.id)

@router.post("")
def create_order(
    req: OrderCreateRequest,
    user: UserAccount = Depends(require_role(["CUSTOMER"])),
    db: Session = Depends(get_db)
):
    ord_service = OrderService(db)
    try:
        guest_items = None
        if req.guest_items:
            guest_items = [{"variant_id": gi.variant_id, "quantity": gi.quantity} for gi in req.guest_items]

        result = ord_service.create_order(
            account_id=user.id,
            recipient_name=req.recipient_name,
            recipient_phone=req.recipient_phone,
            shipping_address=req.shipping_address,
            payment_method=req.payment_method,
            voucher_code=req.voucher_code,
            guest_items=guest_items
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("")
def list_orders(
    status: Optional[str] = None,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ord_service = OrderService(db)
    # If customer, only view their own orders (AC-AUTH-01)
    if user.role.code == "CUSTOMER":
        orders = ord_service.order_repo.list_orders(account_id=user.id, status=status)
    else:
        # Admin or Manager can view all orders
        orders = ord_service.order_repo.list_orders(account_id=None, status=status)

    res = []
    for o in orders:
        pay_snap = (o.payment.payment_instruction_snapshot or {}) if o.payment else {}
        vietqr_info = build_vietqr_payment_instruction(db, o.code, float(o.total_amount))
        res.append({
            "id": o.id,
            "code": o.code,
            "account_id": o.account_id,
            "status": o.status,
            "payment_method": o.payment_method,
            "subtotal": float(o.subtotal),
            "discount_amount": float(o.discount_amount),
            "shipping_fee": float(o.shipping_fee),
            "total_amount": float(o.total_amount),
            "refund_amount": float(o.refund_amount or 0.0),
            "recipient_name": o.recipient_snapshot.get("name", ""),
            "recipient_phone": o.recipient_snapshot.get("phone", ""),
            "shipping_address": o.recipient_snapshot.get("address", ""),
            "payment_status": o.payment.status if o.payment else "UNKNOWN",
            "customer_reported_transfer": bool(pay_snap.get("customer_reported_transfer")),
            "customer_reported_ref": pay_snap.get("customer_reported_ref"),
            "customer_transfer_ref": pay_snap.get("customer_reported_ref"),
            "payment_instruction": vietqr_info,
            "bank_account": vietqr_info,
            "payment_qr_url": vietqr_info.get("qr_url"),
            "transfer_content": vietqr_info.get("transfer_content"),
            "shipment_status": o.shipment.delivery_status if o.shipment else None,
            "tracking_code": o.shipment.tracking_code if o.shipment else None,
            "invoice_code": o.invoice.code if o.invoice else None,
            "placed_at": o.placed_at.isoformat(),
            "items_summary": [
                {
                    "product_id": itm.product_snapshot.get("id") or itm.product_snapshot.get("product_id"),
                    "variant_id": itm.variant_id,
                    "product_name": itm.product_snapshot.get("name", "Sản phẩm"),
                    "sku": itm.product_snapshot.get("sku", ""),
                    "size": itm.product_snapshot.get("size", ""),
                    "color": itm.product_snapshot.get("color", ""),
                    "quantity": itm.quantity,
                    "unit_price": float(itm.unit_price),
                    "line_total": float(itm.line_total)
                }
                for itm in o.items
            ]
        })
    return res

@router.get("/invoices")
def list_invoices(
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ord_service = OrderService(db)
    if user.role.code == "CUSTOMER":
        invoices = ord_service.order_repo.list_invoices(account_id=user.id)
    else:
        invoices = ord_service.order_repo.list_invoices(account_id=None)

    return [
        {
            "id": inv.id,
            "code": inv.code,
            "order_id": inv.order_id,
            "order_code": inv.order.code if inv.order else "",
            "issued_at": inv.issued_at.isoformat(),
            "subtotal": float(inv.subtotal),
            "discount_amount": float(inv.discount_amount),
            "shipping_fee": float(inv.shipping_fee),
            "total_amount": float(inv.total_amount),
            "customer_name": inv.customer_snapshot.get("name", ""),
            "customer_phone": inv.customer_snapshot.get("phone", ""),
            "customer_address": inv.customer_snapshot.get("address", ""),
            "store_name": inv.store_snapshot.get("name", "Soobin Swimwear"),
            "bank_account": build_vietqr_payment_instruction(
                db,
                inv.order.code if inv.order else inv.code,
                float(inv.total_amount)
            ),
            "items_count": sum(i.quantity for i in inv.items)
        }
        for inv in invoices
    ]

@router.get("/invoices/{code_or_id}")
def get_invoice_detail(
    code_or_id: str,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ord_service = OrderService(db)
    inv = ord_service.order_repo.get_invoice_by_code_or_id(code_or_id)
    if not inv:
        # Also allow opening/generating an invoice directly by order_id or order_code
        order_match = None
        if code_or_id.isdigit():
            order_match = ord_service.order_repo.get_by_id(int(code_or_id))
        if not order_match:
            order_match = ord_service.order_repo.get_by_code(code_or_id)
        if order_match:
            if user.role.code == "CUSTOMER" and order_match.account_id != user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền xem hóa đơn của đơn hàng khác.")
            inv = ord_service.ensure_invoice_for_order(order_match)
            db.commit()

    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy hóa đơn.")

    # Ownership check for CUSTOMER
    if user.role.code == "CUSTOMER" and inv.order and inv.order.account_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền xem hóa đơn của đơn hàng khác.")

    order_code_str = inv.order.code if inv.order else inv.code
    bank_qr = build_vietqr_payment_instruction(db, order_code_str, float(inv.total_amount))
    after_sales = get_after_sales_policy_dict(db)
    enriched_store = {
        **(inv.store_snapshot or {}),
        "bank_account": bank_qr,
        "after_sales_policy": after_sales
    }

    return {
        "id": inv.id,
        "code": inv.code,
        "invoice_code": inv.code,
        "order_id": inv.order_id,
        "order_code": order_code_str,
        "payment_method": inv.order.payment_method if inv.order else "COD",
        "payment_status": inv.order.payment.status if inv.order and inv.order.payment else "PAID",
        "customer_name": inv.customer_snapshot.get("name", ""),
        "customer_phone": inv.customer_snapshot.get("phone", ""),
        "shipping_address": inv.customer_snapshot.get("address", ""),
        "issued_at": inv.issued_at.isoformat(),
        "subtotal": float(inv.subtotal),
        "discount_amount": float(inv.discount_amount),
        "shipping_fee": float(inv.shipping_fee),
        "total_amount": float(inv.total_amount),
        "customer_snapshot": inv.customer_snapshot,
        "store_snapshot": enriched_store,
        "bank_account": bank_qr,
        "payment_qr_url": bank_qr.get("qr_url"),
        "transfer_content": bank_qr.get("transfer_content"),
        "after_sales_policy": after_sales,
        "items": [
            {
                "id": itm.id,
                "product_name": itm.product_snapshot.get("name", "Sản phẩm"),
                "sku": itm.product_snapshot.get("sku", ""),
                "size": itm.product_snapshot.get("size", ""),
                "color": itm.product_snapshot.get("color", ""),
                "quantity": itm.quantity,
                "unit_price": float(itm.unit_price),
                "discount_amount": float(itm.discount_amount),
                "line_total": float(itm.line_total)
            }
            for itm in inv.items
        ]
    }

@router.post("/pos", status_code=status.HTTP_201_CREATED)
def create_pos_order(
    req: POSOrderCreateRequest,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "SALES"])),
    db: Session = Depends(get_db)
):
    ord_service = OrderService(db)
    try:
        items_input = [{"variant_id": i.variant_id, "quantity": i.quantity} for i in req.items]
        r_name = (req.recipient_name or req.customer_name or "Khách Mua Tại Quầy").strip()
        r_phone = (req.recipient_phone or req.customer_phone or "0900000000").strip()
        res = ord_service.create_pos_order(
            staff_id=user.id,
            recipient_name=r_name,
            recipient_phone=r_phone,
            shipping_address=req.shipping_address,
            payment_method=req.payment_method,
            fulfillment_type=req.fulfillment_type,
            items_input=items_input,
            voucher_code=req.voucher_code
        )
        if isinstance(res, dict) and "order" in res and isinstance(res["order"], dict):
            ord_obj = res["order"]
            ord_code = ord_obj.get("code") or ord_obj.get("order_code") or "POS"
            ord_total = float(ord_obj.get("total_amount") or 0.0)
            bank_qr = build_vietqr_payment_instruction(db, ord_code, ord_total)
            ord_obj["bank_account"] = bank_qr
            ord_obj["payment_qr_url"] = bank_qr.get("qr_url")
            ord_obj["transfer_content"] = bank_qr.get("transfer_content")
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/crm/customers")
def list_crm_customers(
    q: Optional[str] = None,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "SALES"])),
    db: Session = Depends(get_db)
):
    ord_service = OrderService(db)
    return ord_service.list_crm_customers(q=q)

@router.get("/loyalty-summary")
def get_customer_loyalty_summary(
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ord_service = OrderService(db)
    return ord_service.get_loyalty_summary(user.id)


@router.get("/pos-shift-summary")
def get_pos_shift_summary(
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "SALES"])),
    db: Session = Depends(get_db)
):
    from app.models.entities import ProductionOrder, ProductionPromotion
    all_orders = db.query(ProductionOrder).order_by(ProductionOrder.placed_at.desc()).all()
    pos_orders = [o for o in all_orders if float(o.shipping_fee or 0) == 0.0 or "POS" in (o.code or "") or o.payment_method == "CASH"]
    pending_online = [o for o in all_orders if o.status == "Chưa xử lý"]

    cash_rev = sum(float(o.total_amount or 0) for o in pos_orders if (o.payment_method or "").upper() == "CASH" and o.status != "Đã hủy")
    qr_rev = sum(float(o.total_amount or 0) for o in pos_orders if (o.payment_method or "").upper() in ("VIETQR", "BANK_TRANSFER") and o.status != "Đã hủy")
    total_pos_rev = sum(float(o.total_amount or 0) for o in pos_orders if o.status != "Đã hủy")

    active_vouchers = db.query(ProductionPromotion).filter(
        ProductionPromotion.promotion_type == "VOUCHER",
        ProductionPromotion.is_active == True
    ).all()

    return {
        "pos_order_count": len(pos_orders),
        "pos_orders_count": len(pos_orders),
        "total_revenue": round(total_pos_rev),
        "total_pos_revenue": round(total_pos_rev),
        "cash_revenue": round(cash_rev),
        "vietqr_revenue": round(qr_rev),
        "pending_online_orders_count": len(pending_online),
        "active_vouchers": [
            {
                "code": v.code,
                "name": v.name,
                "discount_type": "PERCENT",
                "discount_value": float(v.discount_percent),
                "discount_percent": float(v.discount_percent),
                "minimum_order_amount": float(v.minimum_order_amount),
            }
            for v in active_vouchers
        ],
    }

@router.get("/{order_id}")
def get_order_detail(
    order_id: int,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ord_service = OrderService(db)
    order = ord_service.order_repo.get_by_id(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đơn hàng.")

    # AC-AUTH-01: Ownership check
    if user.role.code == "CUSTOMER" and order.account_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền xem đơn hàng của người khác.")

    items_data = [
        {
            "id": itm.id,
            "variant_id": itm.variant_id,
            "product_name": itm.product_snapshot.get("name", "Sản phẩm"),
            "sku": itm.product_snapshot.get("sku", ""),
            "size": itm.product_snapshot.get("size", ""),
            "color": itm.product_snapshot.get("color", ""),
            "quantity": itm.quantity,
            "unit_price": float(itm.unit_price),
            "allocated_discount": float(itm.allocated_discount_amount),
            "line_total": float(itm.line_total)
        }
        for itm in order.items
    ]

    history_data = [
        {
            "event_type": h.event_type,
            "from_status": h.from_status,
            "to_status": h.to_status,
            "reason": h.reason,
            "occurred_at": h.occurred_at.isoformat()
        }
        for h in order.history
    ]

    payment_info = None
    if order.payment:
        payment_info = {
            "method": order.payment.method,
            "status": order.payment.status,
            "expected_amount": float(order.payment.expected_amount),
            "received_amount": float(order.payment.received_amount),
            "instruction": order.payment.payment_instruction_snapshot
        }

    shipment_info = None
    if order.shipment:
        shipment_info = {
            "carrier": order.shipment.carrier,
            "tracking_code": order.shipment.tracking_code,
            "delivery_status": order.shipment.delivery_status,
            "delivered_at": order.shipment.delivered_at.isoformat() if order.shipment.delivered_at else None
        }

    invoice_info = None
    if order.invoice:
        invoice_info = {
            "code": order.invoice.code,
            "issued_at": order.invoice.issued_at.isoformat(),
            "total_amount": float(order.invoice.total_amount)
        }

    return {
        "id": order.id,
        "code": order.code,
        "account_id": order.account_id,
        "status": order.status,
        "payment_method": order.payment_method,
        "selected_discount_type": order.selected_discount_type,
        "subtotal": float(order.subtotal),
        "discount_amount": float(order.discount_amount),
        "shipping_fee": float(order.shipping_fee),
        "total_amount": float(order.total_amount),
        "refund_amount": float(order.refund_amount or 0.0),
        "recipient_snapshot": order.recipient_snapshot,
        "store_snapshot": order.store_snapshot,
        "items": items_data,
        "history": history_data,
        "payment": payment_info,
        "shipment": shipment_info,
        "invoice": invoice_info,
        "placed_at": order.placed_at.isoformat()
    }

@router.post("/{order_id}/cancel")
def cancel_order(
    order_id: int,
    req: OrderCancelRequest,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ord_service = OrderService(db)
    order = ord_service.order_repo.get_by_id(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đơn hàng.")

    # AC-AUTH-01: Ownership check
    if user.role.code == "CUSTOMER" and order.account_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không thể hủy đơn hàng của người khác.")

    try:
        updated = ord_service.cancel_order(order_id, actor_id=user.id, reason=req.reason)
        return {
            "message": f"Hủy đơn hàng thành công. Trạng thái hiện tại: {updated.status}",
            "order_id": updated.id,
            "order_code": updated.code,
            "status": updated.status,
            "refund_amount": float(updated.refund_amount or 0.0)
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{order_id}/confirm")
def confirm_order(
    order_id: int,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "SALES"])),
    db: Session = Depends(get_db)
):
    ord_service = OrderService(db)
    try:
        updated = ord_service.confirm_order(order_id, manager_id=user.id)
        return {
            "message": "Xác nhận đơn hàng thành công và đã tạo vận đơn GHTK.",
            "order_id": updated.id,
            "status": updated.status,
            "tracking_code": updated.shipment.tracking_code if updated.shipment else None
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{order_id}/refund")
def mark_manual_refund(
    order_id: int,
    req: ManualRefundRequest,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db)
):
    ord_service = OrderService(db)
    try:
        updated = ord_service.mark_manual_refund_done(order_id, manager_id=user.id, note=req.note)
        return {
            "message": "Đã ghi nhận hoàn tất chuyển khoản hoàn tiền.",
            "order_id": updated.id,
            "status": updated.status
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/refunds/pending")
def list_pending_refunds(
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db)
):
    ord_service = OrderService(db)
    refunds = ord_service.order_repo.get_pending_refunds()
    return [
        {
            "id": r.id,
            "code": r.code,
            "customer_name": r.recipient_snapshot.get("name", ""),
            "customer_phone": r.recipient_snapshot.get("phone", ""),
            "payment_method": r.payment_method,
            "refund_amount": float(r.refund_amount or (r.subtotal - r.discount_amount)),
            "placed_at": r.placed_at.isoformat()
        }
        for r in refunds
    ]

@router.post("/{order_id}/reorder")
def reorder_past_order(
    order_id: int,
    user: UserAccount = Depends(require_role(["CUSTOMER"])),
    db: Session = Depends(get_db)
):
    ord_service = OrderService(db)
    try:
        return ord_service.reorder_into_cart(order_id=order_id, account_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{order_id}/exchange-request")
def create_order_exchange_request(
    order_id: int,
    req: OrderExchangeRequest,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ord_service = OrderService(db)
    try:
        return ord_service.request_order_exchange(
            order_id=order_id,
            account_id=user.id,
            target_size=req.target_size,
            reason=req.reason,
            preferred_resolution=req.preferred_resolution
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/trigger-expiry-job")
def trigger_expiry_job(db: Session = Depends(get_db)):
    ord_service = OrderService(db)
    count = ord_service.expire_unpaid_vietqr_orders()
    return {"message": f"Job quét đơn quá hạn đã chạy hoàn tất. Đã tự động hủy {count} đơn VietQR quá hạn."}


@router.get("/rma/requests")
def list_rma_warranty_exchange_requests(
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "SALES", "WAREHOUSE"])),
    db: Session = Depends(get_db)
):
    ord_service = OrderService(db)
    return ord_service.list_rma_requests()


@router.put("/rma/requests/{ticket_id}")
def update_rma_warranty_exchange_request(
    ticket_id: str,
    req: RMATicketUpdateRequest,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "SALES", "WAREHOUSE"])),
    db: Session = Depends(get_db)
):
    ord_service = OrderService(db)
    try:
        return ord_service.update_rma_request(
            ticket_id=ticket_id,
            status=req.status,
            staff_note=req.staff_note if req.staff_note is not None else req.resolution_note,
            actor=user
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/payments/bank-webhook")
def process_real_bank_transfer_webhook(
    req: RealBankWebhookPayload,
    db: Session = Depends(get_db)
):
    """
    Webhook tự động nhận biến động số dư ngân hàng (SePay / Casso / VietQR API).
    Tự động bóc tách mã đơn hàng từ nội dung chuyển khoản và xác nhận PAID.
    """
    pay_service = PaymentService(db)
    try:
        return pay_service.process_real_bank_webhook(
            content=req.content,
            transfer_amount=req.transfer_amount,
            transaction_id=req.transaction_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{order_id}/confirm-payment")
def confirm_order_bank_transfer_payment(
    order_id: int,
    req: BankTransferConfirmRequest,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "SALES"])),
    db: Session = Depends(get_db)
):
    """
    Chủ cửa hàng (ADMIN), Quản lý (MANAGER) hoặc Thu ngân/Sales (SALES)
    xác nhận đơn hàng đã nhận tiền chuyển khoản thành công.
    """
    ord_service = OrderService(db)
    try:
        return ord_service.confirm_bank_transfer_payment(
            order_id=order_id,
            actor_id=user.id,
            transaction_id=req.transaction_id or req.transaction_ref,
            received_amount=req.received_amount if req.received_amount is not None else req.transfer_amount,
            note=req.note
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{order_id}/customer-report-transfer")
def customer_report_order_bank_transfer(
    order_id: int,
    req: CustomerReportTransferRequest,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Khách hàng bấm 'Tôi đã chuyển khoản' kèm mã tham chiếu ngân hàng
    (hoặc kích hoạt giả lập đối soát Webhook tự động).
    """
    ord_service = OrderService(db)
    try:
        return ord_service.customer_report_bank_transfer(
            order_id=order_id,
            account_id=user.id,
            transaction_ref=req.transaction_ref,
            note=req.transfer_note or req.note,
            auto_verify_webhook=bool(req.auto_verify_webhook or req.auto_verify)
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

