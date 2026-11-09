from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
import uuid
from sqlalchemy.orm import Session
from app.repositories.order_repository import OrderRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.catalog_repository import CatalogRepository
from app.repositories.promotion_repository import PromotionRepository
from app.repositories.user_repository import UserRepository
from app.repositories.cart_repository import CartRepository
from app.services.promotion_service import PromotionService
from app.core.config import settings
from app.models.entities import (
    ProductionOrder, ProductionOrderItem, ProductionOrderDiscountOption,
    ProductionOrderHistory, ProductionPayment, ProductionShipment,
    ProductionInvoice, ProductionInvoiceItem, UserAccount
)

class OrderService:
    def __init__(self, db: Session):
        self.db = db
        self.order_repo = OrderRepository(db)
        self.inv_repo = InventoryRepository(db)
        self.catalog_repo = CatalogRepository(db)
        self.promo_repo = PromotionRepository(db)
        self.user_repo = UserRepository(db)
        self.cart_repo = CartRepository(db)
        self.promo_service = PromotionService(db)

    def create_order(
        self,
        account_id: int,
        recipient_name: str,
        recipient_phone: str,
        shipping_address: str,
        payment_method: str, # COD, VietQR
        voucher_code: Optional[str] = None,
        guest_items: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Creates order atomically (AC-AUTH-05, AC-CHK-01, AC-CHK-03, AC-INV-06).
        Deducts stock immediately and locks inventory rows to prevent race conditions.
        """
        user = self.user_repo.get_by_id(account_id)
        if not user:
            raise ValueError("Không tìm thấy tài khoản người dùng.")

        # AC-AUTH-05: Check email verification
        if not user.email_verified_at:
            raise ValueError("Tài khoản chưa xác minh email. Vui lòng xác minh email trước khi tiến hành đặt hàng.")

        if user.is_locked:
            raise ValueError("Tài khoản của bạn đã bị khóa.")

        # Collect items from account cart or guest items
        items_to_order = []
        if guest_items and len(guest_items) > 0:
            for gi in guest_items:
                items_to_order.append({"variant_id": gi["variant_id"], "quantity": gi["quantity"]})
        else:
            cart_items = self.cart_repo.get_cart_items(account_id)
            if not cart_items:
                raise ValueError("Giỏ hàng của bạn đang trống.")
            for ci in cart_items:
                items_to_order.append({"variant_id": ci.variant_id, "quantity": ci.quantity})

        # Lock inventory rows and fetch variant prices
        enriched_items = []
        for itm in items_to_order:
            v_id = itm["variant_id"]
            qty = itm["quantity"]
            if qty <= 0:
                continue

            variant = self.catalog_repo.get_variant_by_id(v_id)
            if not variant or not variant.is_active or variant.product.deleted_at is not None or variant.product.status != "Selling":
                raise ValueError(f"Sản phẩm {variant.product.name if variant else ''} đã ngừng kinh doanh.")

            # AC-CHK-01: Lock inventory row
            inv = self.inv_repo.get_inventory_for_update(v_id)
            if not inv or inv.available_quantity < qty:
                raise ValueError(f"Sản phẩm '{variant.product.name} ({variant.size.name})' chỉ còn {inv.available_quantity if inv else 0} chiếc, không đủ số lượng bạn đặt ({qty}).")

            unit_cost = (float(inv.inventory_value) / inv.available_quantity) if inv.available_quantity > 0 else 0.0
            enriched_items.append({
                "variant": variant,
                "variant_id": v_id,
                "product_id": variant.product_id,
                "unit_price": float(variant.product.base_price),
                "unit_cost": round(unit_cost, 2),
                "quantity": qty
            })

        if not enriched_items:
            raise ValueError("Không có sản phẩm hợp lệ để đặt hàng.")

        # Calculate discounts via PromotionService
        calc_res = self.promo_service.calculate_discounts(
            items=[
                {
                    "variant_id": e["variant_id"],
                    "product_id": e["product_id"],
                    "unit_price": e["unit_price"],
                    "quantity": e["quantity"]
                }
                for e in enriched_items
            ],
            voucher_code=voucher_code,
            account_id=account_id
        )

        subtotal = calc_res["original_subtotal"]
        discount_amount = calc_res["winning_discount_amount"]
        selected_discount_type = calc_res["selected_option_type"]
        shipping_fee = settings.MOCK_SHIPPING_FEE
        total_amount = max(0.0, subtotal - discount_amount) + shipping_fee

        order_code = f"SOOBIN-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        from app.controllers.site_settings_controller import (
            build_vietqr_payment_instruction, get_after_sales_policy_dict
        )
        vietqr_info = build_vietqr_payment_instruction(self.db, order_code, total_amount)
        after_sales_policy = get_after_sales_policy_dict(self.db)

        recipient_snapshot = {
            "name": recipient_name.strip(),
            "phone": recipient_phone.strip(),
            "address": shipping_address.strip()
        }
        store_snapshot = {
            "name": settings.PROJECT_NAME,
            "hotline": "1900 8866",
            "address": "Tầng 3, Tòa nhà Soobin Ocean, 45 Lê Duẩn, Quận 1, TP. Hồ Chí Minh",
            "bank_account": vietqr_info,
            "after_sales_policy": after_sales_policy
        }

        timeout_hours = int(after_sales_policy.get("vietqr_payment_timeout_hours") or 24)
        payment_due_at = (datetime.now(timezone.utc) + timedelta(hours=timeout_hours)) if payment_method == "VietQR" else None

        order = ProductionOrder(
            code=order_code,
            account_id=account_id,
            status="Chưa xử lý",
            payment_method=payment_method,
            selected_discount_type=selected_discount_type,
            subtotal=subtotal,
            discount_amount=discount_amount,
            shipping_fee=shipping_fee,
            total_amount=total_amount,
            refund_amount=0.0,
            recipient_snapshot=recipient_snapshot,
            store_snapshot=store_snapshot,
            payment_due_at=payment_due_at,
            placed_at=datetime.now(timezone.utc)
        )
        self.order_repo.create_order(order)
        self.db.flush()

        # Deduct stock and create order items
        allocated_map = {a["variant_id"]: a for a in calc_res.get("allocated_items", [])}

        for e in enriched_items:
            v_id = e["variant_id"]
            qty = e["quantity"]
            alloc_info = allocated_map.get(v_id, {})
            alloc_disc = alloc_info.get("allocated_discount", 0.0)
            promo_id = alloc_info.get("promotion_id")
            line_total = max(0.0, (qty * e["unit_price"]) - alloc_disc)

            prod_snapshot = {
                "id": e["variant"].product_id,
                "name": e["variant"].product.name,
                "sku": e["variant"].sku,
                "size": e["variant"].size.name,
                "color": e["variant"].color.name,
                "base_price": e["unit_price"]
            }

            order_item = ProductionOrderItem(
                order_id=order.id,
                variant_id=v_id,
                promotion_id=promo_id,
                quantity=qty,
                unit_price=e["unit_price"],
                unit_cost_snapshot=e["unit_cost"],
                allocated_discount_amount=alloc_disc,
                line_total=line_total,
                product_snapshot=prod_snapshot,
                promotion_snapshot={"code": alloc_info.get("promotion_code")} if promo_id else None
            )
            self.db.add(order_item)
            self.db.flush()

            # Deduct inventory atomically
            self.inv_repo.deduct_stock(
                variant_id=v_id,
                quantity=qty,
                unit_cost=e["unit_cost"],
                order_item_id=order_item.id,
                event_key=f"ORD-OUT-{order.id}-{v_id}"
            )

        # Record discount options snapshot
        for opt in calc_res.get("eligible_options", []):
            disc_opt = ProductionOrderDiscountOption(
                order_id=order.id,
                option_type=opt["option_type"],
                is_eligible=opt["is_eligible"],
                discount_amount=opt["discount_amount"],
                is_selected=opt["is_selected"],
                calculation_snapshot=opt
            )
            self.db.add(disc_opt)

        # If voucher was selected and won, record usage and increment count
        if selected_discount_type == "VOUCHER" and calc_res.get("applied_voucher"):
            vc = calc_res["applied_voucher"]
            self.promo_repo.record_voucher_usage(order.id, vc.id)
            self.promo_repo.increment_voucher_usage(vc.id)

        # Create payment record with store owner's configured bank account & order price
        payment_instruction = vietqr_info

        payment = ProductionPayment(
            order_id=order.id,
            method=payment_method,
            status="PENDING",
            expected_amount=total_amount,
            received_amount=0.0,
            payment_instruction_snapshot=payment_instruction,
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(payment)

        # Order history initial event
        self.order_repo.add_history(
            order_id=order.id,
            from_status=None,
            to_status="Chưa xử lý",
            event_type="ORDER_PLACED",
            reason=f"Khách hàng đặt hàng phương thức {payment_method}",
            actor_id=account_id
        )

        # Clear cart for user
        self.cart_repo.clear_cart(account_id)

        self.db.commit()

        return {
            "order_id": order.id,
            "order_code": order.code,
            "status": order.status,
            "payment_method": order.payment_method,
            "total_amount": float(order.total_amount),
            "payment_instruction": payment_instruction,
            "bank_account": payment_instruction,
            "payment_qr_url": payment_instruction.get("qr_url"),
            "transfer_content": payment_instruction.get("transfer_content"),
            "after_sales_policy": after_sales_policy
        }

    def cancel_order(self, order_id: int, actor_id: int, reason: str) -> ProductionOrder:
        """
        Cancel order (only allowed in 'Chưa xử lý').
        Restores inventory and voucher usage exactly once (AC-INV-06, E2E-03).
        If VietQR was paid, moves to 'Chờ hoàn tiền' instead of 'Đã hủy'.
        """
        order = self.order_repo.get_by_id(order_id)
        if not order:
            raise ValueError("Đơn hàng không tồn tại.")

        if order.status != "Chưa xử lý":
            raise ValueError(f"Không thể hủy đơn hàng ở trạng thái '{order.status}'. Chỉ hủy được khi 'Chưa xử lý'.")

        from_status = order.status
        is_vietqr_paid = (order.payment_method == "VietQR" and order.payment and order.payment.status == "PAID")

        target_status = "Chờ hoàn tiền" if is_vietqr_paid else "Đã hủy"
        if is_vietqr_paid:
            order.refund_amount = float(order.subtotal - order.discount_amount)

        order.status = target_status

        # 1. Restore inventory
        for item in order.items:
            self.inv_repo.restore_stock(
                variant_id=item.variant_id,
                quantity=item.quantity,
                unit_cost=float(item.unit_cost_snapshot),
                order_item_id=item.id,
                event_key=f"CANCEL-RESTORE-{order.id}-{item.variant_id}"
            )

        # 2. Restore voucher if used
        if order.selected_discount_type == "VOUCHER":
            self.promo_repo.mark_voucher_restored(order.id)

        # 3. Add order history
        self.order_repo.add_history(
            order_id=order.id,
            from_status=from_status,
            to_status=target_status,
            event_type="ORDER_CANCELLED",
            reason=reason,
            actor_id=actor_id
        )

        self.db.commit()
        return order

    def confirm_order(self, order_id: int, manager_id: int) -> ProductionOrder:
        """
        Store Manager confirms order from 'Chưa xử lý' -> 'Đã xử lý'.
        Creates shipment with GHTK mock carrier.
        """
        order = self.order_repo.get_by_id(order_id)
        if not order:
            raise ValueError("Đơn hàng không tồn tại.")

        if order.status != "Chưa xử lý":
            raise ValueError(f"Không thể xác nhận đơn ở trạng thái '{order.status}'.")

        # VietQR must be paid first
        if order.payment_method == "VietQR":
            if not order.payment or order.payment.status != "PAID":
                raise ValueError("Đơn hàng VietQR chưa được thanh toán hoặc chưa nhận được tiền chuyển khoản.")

        order.status = "Đã xử lý"

        # Create shipment on GHTK mock
        tracking_code = f"GHTK{datetime.now().strftime('%m%d%H%M')}{uuid.uuid4().hex[:4].upper()}"
        carrier_key = f"REQ-GHTK-{order.id}-{uuid.uuid4().hex[:6]}"
        shipment = ProductionShipment(
            order_id=order.id,
            carrier="GHTK",
            tracking_code=tracking_code,
            creation_status="CREATED",
            delivery_status="WAITING_FOR_PICKUP",
            shipping_fee_snapshot=order.shipping_fee,
            carrier_request_key=carrier_key,
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(shipment)

        self.order_repo.add_history(
            order_id=order.id,
            from_status="Chưa xử lý",
            to_status="Đã xử lý",
            event_type="ORDER_CONFIRMED",
            reason="Quản lý đã xác nhận đơn hàng và tạo vận đơn vận chuyển",
            actor_id=manager_id
        )

        self.db.commit()
        return order

    def mark_manual_refund_done(self, order_id: int, manager_id: int, note: Optional[str] = None) -> ProductionOrder:
        """
        Manager marks manual refund completed for orders in 'Chờ hoàn tiền' -> 'Đã hoàn tiền' (PRD Section 10).
        """
        order = self.order_repo.get_by_id(order_id)
        if not order:
            raise ValueError("Đơn hàng không tồn tại.")

        if order.status != "Chờ hoàn tiền":
            raise ValueError(f"Đơn hàng hiện không ở trạng thái 'Chờ hoàn tiền' (trạng thái: {order.status}).")

        order.status = "Đã hoàn tiền"
        if order.payment:
            order.payment.status = "REFUNDED"

        self.order_repo.add_history(
            order_id=order.id,
            from_status="Chờ hoàn tiền",
            to_status="Đã hoàn tiền",
            event_type="REFUND_COMPLETED",
            reason=note or "Quản lý đã hoàn tiền thủ công cho khách hàng ngoài hệ thống",
            actor_id=manager_id
        )

        self.db.commit()
        return order

    def expire_unpaid_vietqr_orders(self) -> int:
        """
        Find and expire unpaid VietQR orders that exceeded 24h.
        Restores stock and vouchers (E2E-03).
        """
        expired_orders = self.order_repo.get_expired_unpaid_vietqr_orders(older_than_hours=24)
        count = 0
        for ord_obj in expired_orders:
            try:
                self.cancel_order(
                    order_id=ord_obj.id,
                    actor_id=ord_obj.account_id,
                    reason="Tự động hủy do quá thời hạn 24 giờ chưa thanh toán VietQR"
                )
                count += 1
            except Exception:
                pass
        return count

    def create_pos_order(
        self,
        staff_id: int,
        recipient_name: str,
        recipient_phone: str,
        shipping_address: str,
        payment_method: str,
        fulfillment_type: str,
        items_input: List[Dict[str, Any]],
        voucher_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        POS Counter / Phone Order creation by Sales/Manager/Admin.
        Supports instant In-Store Pickup (marks Delivered + Paid + Issues E-Invoice) or GHTK delivery.
        """
        if not items_input:
            raise ValueError("Đơn hàng POS cần có ít nhất 1 sản phẩm.")

        # Match customer account by phone if exists, otherwise link to staff or default customer
        matched_user = self.db.query(UserAccount).filter(UserAccount.phone == recipient_phone.strip()).first()
        target_account_id = matched_user.id if matched_user else staff_id

        enriched_items = []
        for itm in items_input:
            v_id = int(itm["variant_id"])
            qty = int(itm["quantity"])
            if qty <= 0:
                continue
            variant = self.catalog_repo.get_variant_by_id(v_id)
            if not variant or not variant.is_active:
                raise ValueError(f"Biến thể #{v_id} không khả dụng.")
            inv = self.inv_repo.get_inventory_for_update(v_id)
            if not inv or inv.available_quantity < qty:
                raise ValueError(f"SKU {variant.sku} chỉ còn {inv.available_quantity if inv else 0} chiếc, không đủ {qty} chiếc.")
            unit_cost = (float(inv.inventory_value) / inv.available_quantity) if inv.available_quantity > 0 else 0.0
            enriched_items.append({
                "variant": variant,
                "variant_id": v_id,
                "product_id": variant.product_id,
                "unit_price": float(variant.product.base_price),
                "unit_cost": round(unit_cost, 2),
                "quantity": qty
            })

        calc_res = self.promo_service.calculate_discounts(
            items=[
                {
                    "variant_id": e["variant_id"],
                    "product_id": e["product_id"],
                    "unit_price": e["unit_price"],
                    "quantity": e["quantity"]
                }
                for e in enriched_items
            ],
            voucher_code=voucher_code,
            account_id=target_account_id
        )

        is_instore = (fulfillment_type == "INSTORE_PICKUP")
        subtotal = calc_res["original_subtotal"]
        discount_amount = calc_res["winning_discount_amount"]
        selected_discount_type = calc_res["selected_option_type"]
        shipping_fee = 0.0 if is_instore else settings.MOCK_SHIPPING_FEE
        total_amount = max(0.0, subtotal - discount_amount) + shipping_fee

        order_code = f"POS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        from app.controllers.site_settings_controller import (
            build_vietqr_payment_instruction, get_after_sales_policy_dict
        )
        vietqr_info = build_vietqr_payment_instruction(self.db, order_code, total_amount)
        after_sales_policy = get_after_sales_policy_dict(self.db)

        recipient_snapshot = {
            "name": recipient_name.strip(),
            "phone": recipient_phone.strip(),
            "address": "Nhận trực tiếp tại Quầy Flagship Soobin" if is_instore else shipping_address.strip()
        }
        store_snapshot = {
            "name": settings.PROJECT_NAME,
            "hotline": "1900 8866",
            "address": "Tầng 3, Tòa nhà Soobin Ocean, 45 Lê Duẩn, Quận 1, TP. Hồ Chí Minh",
            "bank_account": vietqr_info,
            "after_sales_policy": after_sales_policy
        }

        order = ProductionOrder(
            code=order_code,
            account_id=target_account_id,
            status="Đã giao" if is_instore else "Chưa xử lý",
            payment_method=payment_method,
            selected_discount_type=selected_discount_type,
            subtotal=subtotal,
            discount_amount=discount_amount,
            shipping_fee=shipping_fee,
            total_amount=total_amount,
            recipient_snapshot=recipient_snapshot,
            store_snapshot=store_snapshot
        )
        self.db.add(order)
        self.db.flush()

        alloc_map = {a["variant_id"]: a for a in calc_res["allocated_items"]}
        created_order_items = []
        for e in enriched_items:
            v_id = e["variant_id"]
            qty = e["quantity"]
            alloc = alloc_map.get(v_id, {"allocated_discount": 0.0, "promotion_id": None, "promotion_code": None})
            line_disc = alloc["allocated_discount"]
            line_tot = max(0.0, (qty * e["unit_price"]) - line_disc)

            prod_snapshot = {
                "id": e["variant"].product_id,
                "code": e["variant"].product.code,
                "name": e["variant"].product.name,
                "sku": e["variant"].sku,
                "size": e["variant"].size.name if e["variant"].size else "",
                "color": e["variant"].color.name if e["variant"].color else ""
            }
            oi = ProductionOrderItem(
                order_id=order.id,
                variant_id=v_id,
                promotion_id=alloc["promotion_id"],
                quantity=qty,
                unit_price=e["unit_price"],
                unit_cost_snapshot=e["unit_cost"],
                allocated_discount_amount=line_disc,
                line_total=line_tot,
                product_snapshot=prod_snapshot
            )
            self.db.add(oi)
            self.db.flush()
            created_order_items.append(oi)

            self.inv_repo.deduct_stock(
                variant_id=v_id,
                quantity=qty,
                unit_cost=e["unit_cost"],
                order_item_id=oi.id,
                event_key=f"POS-OUT-{order.id}-{v_id}"
            )

        payment = ProductionPayment(
            order_id=order.id,
            method=payment_method,
            status="PAID" if is_instore else "PENDING",
            expected_amount=total_amount,
            received_amount=total_amount if is_instore else 0.0,
            paid_at=datetime.now(timezone.utc) if is_instore else None,
            payment_instruction_snapshot={
                "channel": "POS_COUNTER",
                "staff_id": staff_id,
                **vietqr_info
            }
        )
        self.db.add(payment)

        invoice_code = None
        if is_instore:
            inv_code = f"INV-{datetime.now().strftime('%Y%m%d')}-{order.id:05d}"
            invoice = ProductionInvoice(
                order_id=order.id,
                code=inv_code,
                issued_at=datetime.now(timezone.utc),
                subtotal=subtotal,
                discount_amount=discount_amount,
                shipping_fee=shipping_fee,
                total_amount=total_amount,
                customer_snapshot=recipient_snapshot,
                store_snapshot=store_snapshot
            )
            self.db.add(invoice)
            self.db.flush()
            for oi in created_order_items:
                self.db.add(ProductionInvoiceItem(
                    invoice_id=invoice.id,
                    order_item_id=oi.id,
                    quantity=oi.quantity,
                    unit_price=oi.unit_price,
                    discount_amount=oi.allocated_discount_amount,
                    line_total=oi.line_total,
                    unit_cost_snapshot=oi.unit_cost_snapshot,
                    product_snapshot=oi.product_snapshot
                ))
            invoice_code = inv_code

        self.order_repo.add_history(
            order_id=order.id,
            from_status=None,
            to_status=order.status,
            event_type="POS_ORDER_CREATED",
            reason="Tạo đơn hàng trực tiếp tại quầy POS" if is_instore else "Tạo đơn hàng qua điện thoại/quầy gửi GHTK",
            actor_id=staff_id
        )
        self.db.commit()

        summary_obj = {
            "id": order.id,
            "order_id": order.id,
            "code": order.code,
            "order_code": order.code,
            "status": order.status,
            "payment_status": payment.status,
            "payment_method": payment_method,
            "recipient_name": recipient_name.strip(),
            "recipient_phone": recipient_phone.strip(),
            "subtotal_amount": subtotal,
            "discount_amount": discount_amount,
            "shipping_fee": shipping_fee,
            "total_amount": total_amount,
            "applied_promotion_code": selected_discount_type if discount_amount > 0 else None,
            "invoice_code": invoice_code,
            "payment_instruction": vietqr_info
        }
        return {
            **summary_obj,
            "order": summary_obj,
            "message": f"Tạo đơn POS {order.code} thành công!" + (f" Mã hóa đơn: {invoice_code}" if invoice_code else "")
        }

    def list_crm_customers(self, q: Optional[str] = None) -> List[Dict[str, Any]]:
        customers = self.db.query(UserAccount).order_by(UserAccount.id).all()
        all_orders = self.order_repo.list_orders()
        orders_by_acc: Dict[int, List[ProductionOrder]] = {}
        for o in all_orders:
            orders_by_acc.setdefault(o.account_id, []).append(o)

        res = []
        q_low = q.strip().lower() if q else ""
        for u in customers:
            if u.role and u.role.code != "CUSTOMER":
                continue
            if q_low and q_low not in (u.full_name or "").lower() and q_low not in (u.email or "").lower() and q_low not in (u.phone or "").lower():
                continue
            u_orders = orders_by_acc.get(u.id, [])
            delivered = [o for o in u_orders if o.status == "Đã giao"]
            total_spend = sum(float(o.total_amount) for o in delivered)
            sizes_bought = set()
            for o in u_orders:
                for it in o.items:
                    sz = it.product_snapshot.get("size")
                    if sz:
                        sizes_bought.add(sz)

            if total_spend >= 5000000:
                tier = "DIAMOND"
            elif total_spend >= 2000000:
                tier = "GOLD"
            elif total_spend >= 500000:
                tier = "SILVER"
            else:
                tier = "MEMBER"

            res.append({
                "id": u.id,
                "full_name": u.full_name,
                "email": u.email,
                "phone": u.phone or "—",
                "order_count": len(u_orders),
                "total_orders": len(u_orders),
                "delivered_orders": len(delivered),
                "total_spend": total_spend,
                "vip_tier": tier,
                "preferred_sizes": sorted(list(sizes_bought)),
                "last_order_at": u_orders[0].placed_at.isoformat() if u_orders else None
            })
        res.sort(key=lambda x: x["total_spend"], reverse=True)
        return res

    def get_loyalty_summary(self, account_id: int) -> Dict[str, Any]:
        u_orders = self.order_repo.list_orders(account_id=account_id)
        delivered = [o for o in u_orders if o.status == "Đã giao"]
        active_orders = [o for o in u_orders if o.status not in ("Đã hủy", "Đã hoàn tiền")]
        total_spend = sum(float(o.total_amount) for o in (delivered if delivered else active_orders))
        points = int(total_spend // 10000)

        if total_spend >= 5000000:
            tier = "PLATINUM OCEAN VIP"
            next_tier = "MAX TIER"
            progress = 100
            perk = "Ưu tiên giảm giá VIP & Quà tặng Resort Collection"
        elif total_spend >= 2000000:
            tier = "GOLD ATELIER"
            next_tier = "PLATINUM OCEAN VIP"
            progress = min(100, int((total_spend / 5000000) * 100))
            perk = "Tích điểm x1.5 & Ưu đãi sinh nhật 20%"
        elif total_spend >= 500000:
            tier = "SILVER WAVE"
            next_tier = "GOLD ATELIER"
            progress = min(100, int((total_spend / 2000000) * 100))
            perk = "Ưu đãi thành viên thân thiết Soobin"
        else:
            tier = "OCEAN MEMBER"
            next_tier = "SILVER WAVE"
            progress = min(100, int((total_spend / 500000) * 100))
            perk = "Nhập SOOBIN15 giảm 15% cho đơn hàng mới"

        return {
            "account_id": account_id,
            "total_spend": total_spend,
            "points": points,
            "order_count": len(u_orders),
            "delivered_count": len(delivered),
            "tier": tier,
            "current_tier": tier,
            "next_tier": next_tier,
            "progress_percent": progress,
            "perk": perk
        }

    def reorder_into_cart(self, order_id: int, account_id: int) -> Dict[str, Any]:
        order = self.order_repo.get_by_id(order_id)
        if not order:
            raise ValueError("Không tìm thấy đơn hàng.")
        if order.account_id != account_id:
            raise ValueError("Bạn không có quyền mua lại đơn hàng của tài khoản khác.")

        added_items = []
        skipped_items = []
        for oi in order.items:
            variant = self.catalog_repo.get_variant_by_id(oi.variant_id)
            inv = self.inv_repo.get_inventory(oi.variant_id) if variant else None
            avail = inv.available_quantity if inv else 0
            if not variant or not variant.is_active or avail <= 0:
                skipped_items.append(oi.product_snapshot.get("name", f"Biến thể #{oi.variant_id}"))
                continue
            curr = self.cart_repo.get_cart_item(account_id, oi.variant_id)
            curr_qty = curr.quantity if curr else 0
            qty_to_add = min(oi.quantity, max(0, avail - curr_qty))
            if qty_to_add > 0:
                self.cart_repo.add_or_update_item(account_id, oi.variant_id, qty_to_add)
                added_items.append({
                    "variant_id": oi.variant_id,
                    "product_name": oi.product_snapshot.get("name", ""),
                    "quantity": qty_to_add
                })
            else:
                skipped_items.append(oi.product_snapshot.get("name", f"Biến thể #{oi.variant_id}"))

        if not added_items:
            raise ValueError("Các sản phẩm trong đơn hàng này hiện đã hết hàng hoặc đã đạt tối đa trong giỏ của bạn.")

        self.db.commit()
        return {
            "order_id": order.id,
            "order_code": order.code,
            "added_count": sum(i["quantity"] for i in added_items),
            "added_items": added_items,
            "skipped_items": skipped_items,
            "message": f"Đã thêm lại {sum(i['quantity'] for i in added_items)} sản phẩm từ đơn {order.code} vào giỏ hàng!"
        }

    def ensure_invoice_for_order(self, order: ProductionOrder) -> ProductionInvoice:
        from app.controllers.site_settings_controller import (
            build_vietqr_payment_instruction, get_after_sales_policy_dict
        )
        vietqr_info = build_vietqr_payment_instruction(self.db, order.code, float(order.total_amount))
        after_sales_policy = get_after_sales_policy_dict(self.db)

        store_snap = dict(order.store_snapshot or {})
        store_snap["bank_account"] = vietqr_info
        store_snap["after_sales_policy"] = after_sales_policy
        order.store_snapshot = store_snap

        existing_inv = self.order_repo.get_invoice_by_order_id(order.id)
        if existing_inv:
            inv_store = dict(existing_inv.store_snapshot or {})
            inv_store["bank_account"] = vietqr_info
            inv_store["after_sales_policy"] = after_sales_policy
            existing_inv.store_snapshot = inv_store
            self.db.flush()
            return existing_inv

        inv_code = f"INV-{datetime.now().strftime('%Y%m%d')}-{order.id:05d}"
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
        for oi in order.items:
            self.db.add(ProductionInvoiceItem(
                invoice_id=invoice.id,
                order_item_id=oi.id,
                quantity=oi.quantity,
                unit_price=oi.unit_price,
                discount_amount=oi.allocated_discount_amount,
                line_total=oi.line_total,
                unit_cost_snapshot=oi.unit_cost_snapshot,
                product_snapshot=oi.product_snapshot,
                promotion_snapshot=oi.promotion_snapshot
            ))
        self.db.flush()
        return invoice

    def confirm_bank_transfer_payment(
        self,
        order_id: int,
        actor_id: int,
        transaction_id: Optional[str] = None,
        received_amount: Optional[float] = None,
        note: Optional[str] = None
    ) -> Dict[str, Any]:
        order = self.order_repo.get_by_id(order_id)
        if not order:
            raise ValueError("Không tìm thấy đơn hàng.")
        if not order.payment:
            raise ValueError("Đơn hàng chưa có bản ghi thanh toán.")
        if order.payment.status == "PAID":
            inv = self.ensure_invoice_for_order(order)
            self.db.commit()
            return {
                "order_id": order.id,
                "order_code": order.code,
                "payment_status": "PAID",
                "invoice_code": inv.code,
                "message": f"Đơn hàng {order.code} đã được xác nhận thanh toán trước đó."
            }

        amt = float(received_amount) if received_amount is not None else float(order.total_amount)
        if amt < float(order.total_amount):
            raise ValueError(f"Số tiền nhận ({amt:,.0f}đ) nhỏ hơn tổng đơn hàng ({float(order.total_amount):,.0f}đ).")

        ext_id = (transaction_id or "").strip() or f"BANK-CONF-{order.code}-{uuid.uuid4().hex[:6].upper()}"
        dup = (
            self.db.query(ProductionPayment)
            .filter(
                ProductionPayment.external_transaction_id == ext_id,
                ProductionPayment.id != order.payment.id
            )
            .first()
        )
        if dup:
            ext_id = f"{ext_id}-{order.id}-{uuid.uuid4().hex[:4].upper()}"
        order.payment.status = "PAID"
        order.payment.received_amount = amt
        order.payment.paid_at = datetime.now(timezone.utc)
        order.payment.external_transaction_id = ext_id

        snap = dict(order.payment.payment_instruction_snapshot or {})
        snap["confirmed_by_staff_id"] = actor_id
        snap["confirmed_at"] = datetime.now(timezone.utc).isoformat()
        snap["transaction_id"] = ext_id
        order.payment.payment_instruction_snapshot = snap

        self.order_repo.add_history(
            order_id=order.id,
            from_status=order.status,
            to_status=order.status,
            event_type="PAYMENT_CONFIRMED_BY_STAFF",
            reason=note or f"Xác nhận đã nhận chuyển khoản ngân hàng {amt:,.0f}đ (Mã GD: {ext_id})",
            actor_id=actor_id
        )
        self.db.commit()
        return {
            "order_id": order.id,
            "order_code": order.code,
            "payment_status": order.payment.status,
            "received_amount": amt,
            "transaction_id": ext_id,
            "message": f"Đã xác nhận đơn hàng {order.code} thanh toán chuyển khoản thành công ({amt:,.0f}đ)!"
        }

    def customer_report_bank_transfer(
        self,
        order_id: int,
        account_id: int,
        transaction_ref: Optional[str] = None,
        note: Optional[str] = None,
        auto_verify_webhook: bool = False
    ) -> Dict[str, Any]:
        order = self.order_repo.get_by_id(order_id)
        if not order:
            raise ValueError("Không tìm thấy đơn hàng.")
        if order.account_id != account_id:
            raise ValueError("Bạn không có quyền thao tác trên đơn hàng của người khác.")
        if not order.payment:
            raise ValueError("Đơn hàng không có thông tin thanh toán.")

        ref = (transaction_ref or "").strip() or f"CUST-CK-{order.code[-6:]}"
        snap = dict(order.payment.payment_instruction_snapshot or {})
        snap["customer_reported_transfer"] = True
        snap["customer_reported_ref"] = ref
        snap["customer_reported_at"] = datetime.now(timezone.utc).isoformat()
        order.payment.payment_instruction_snapshot = snap

        self.order_repo.add_history(
            order_id=order.id,
            from_status=order.status,
            to_status=order.status,
            event_type="CUSTOMER_REPORTED_TRANSFER",
            reason=f"Khách hàng báo đã chuyển khoản ngân hàng (Mã tham chiếu: {ref}). {note or ''}".strip(),
            actor_id=account_id
        )
        self.db.commit()

        if auto_verify_webhook:
            from app.services.payment_service import PaymentService
            pay_res = PaymentService(self.db).process_vietqr_payment(
                order_code=order.code,
                transfer_amount=float(order.total_amount),
                transaction_id=ref
            )
            return {
                **pay_res,
                "customer_reported": True,
                "message": f"Webhook ngân hàng đã tự động đối soát khớp số tiền {float(order.total_amount):,.0f}đ và xác nhận đơn {order.code} ĐÃ THANH TOÁN!"
            }

        return {
            "order_id": order.id,
            "order_code": order.code,
            "payment_status": "PENDING_VERIFICATION" if order.payment.status == "PENDING" else order.payment.status,
            "customer_reported": True,
            "transaction_ref": ref,
            "message": f"Đã gửi thông báo chuyển khoản (Mã: {ref}) cho đơn {order.code}. Bộ phận Thu ngân / Quản lý sẽ xác nhận ngay!"
        }

    def request_order_exchange(
        self,
        order_id: int,
        account_id: int,
        target_size: Optional[str],
        reason: str,
        preferred_resolution: str = "EXCHANGE_SIZE"
    ) -> Dict[str, Any]:
        from app.models.entities import ProductionOutboxEvent, ProductionFeedback
        from app.controllers.site_settings_controller import get_after_sales_policy_dict

        order = self.order_repo.get_by_id(order_id)
        if not order:
            raise ValueError("Không tìm thấy đơn hàng.")
        if order.account_id != account_id:
            raise ValueError("Bạn không có quyền gửi yêu cầu trên đơn hàng của tài khoản khác.")

        policy = get_after_sales_policy_dict(self.db)
        res_upper = (preferred_resolution or "EXCHANGE_SIZE").strip().upper()
        if res_upper in ("RETURN_REFUND", "REFUND_CONSULT"):
            window_days = int(policy.get("return_window_days", 7))
            label_vn = "Trả hàng / Hoàn tiền"
        elif res_upper in ("WARRANTY_REPAIR", "WARRANTY"):
            window_days = int(policy.get("warranty_window_days", 90))
            label_vn = "Bảo hành sản phẩm"
        else:
            window_days = int(policy.get("exchange_size_window_days", 15))
            label_vn = "Đổi Size / Đổi mẫu"

        ref_time = (
            order.shipment.delivered_at
            if (order.shipment and order.shipment.delivered_at)
            else order.placed_at
        )
        now_utc = datetime.now(timezone.utc)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)
        elapsed_days = max(0, (now_utc - ref_time).days)

        if policy.get("enforce_time_limit", True) and elapsed_days > window_days:
            raise ValueError(
                f"Đơn hàng {order.code} đã quá thời hạn {label_vn} "
                f"(Đã qua {elapsed_days} ngày, vượt quá hạn quy định {window_days} ngày của cửa hàng)."
            )

        self.order_repo.add_history(
            order_id=order.id,
            from_status=order.status,
            to_status=order.status,
            event_type="EXCHANGE_REQUESTED",
            reason=f"[{label_vn} ({res_upper}) - Size mong muốn: {target_size or 'Tư vấn'}] {reason.strip()}",
            actor_id=account_id
        )

        ticket_key = f"RMA-{order.id}-{uuid.uuid4().hex[:6].upper()}"
        rec = order.recipient_snapshot or {}
        subject_str = f"[{label_vn}] Đơn {order.code} (Size: {target_size or 'Giữ nguyên'})"
        full_msg = f"[{subject_str}] {reason.strip()}"

        # 1. Save into ProductionFeedback so SALES, MANAGER, ADMIN, WAREHOUSE see it in Feedback/CSKH Inbox
        fb = ProductionFeedback(
            account_id=account_id,
            sender_name=rec.get("name", "Khách hàng"),
            sender_email=f"order.{order.code.lower()}@soobin.vn",
            message=full_msg,
            status="NEW"
        )
        self.db.add(fb)
        self.db.flush()

        # 2. Save structured RMA record in ProductionOutboxEvent
        ticket = ProductionOutboxEvent(
            event_type="CUSTOMER_FEEDBACK_TICKET",
            event_key=ticket_key,
            payload={
                "ticket_code": ticket_key,
                "feedback_id": fb.id,
                "order_id": order.id,
                "order_code": order.code,
                "sender_name": rec.get("name", "Khách hàng"),
                "full_name": rec.get("name", "Khách hàng"),
                "sender_email": f"order.{order.code.lower()}@soobin.vn",
                "phone": rec.get("phone", ""),
                "resolution_type": res_upper,
                "resolution_label": label_vn,
                "target_size": target_size or "Tư vấn",
                "window_days": window_days,
                "elapsed_days": elapsed_days,
                "remaining_days": max(0, window_days - elapsed_days),
                "receiving_roles": ["SALES", "MANAGER", "ADMIN", "WAREHOUSE"],
                "subject": subject_str,
                "message": full_msg,
                "reason": reason.strip(),
                "ticket_status": "NEW"
            },
            status="PUBLISHED",
            created_at=now_utc
        )
        self.db.add(ticket)
        self.db.commit()
        return {
            "ticket_id": ticket.id,
            "feedback_id": fb.id,
            "ticket_code": ticket_key,
            "order_id": order.id,
            "order_code": order.code,
            "target_size": target_size,
            "preferred_resolution": res_upper,
            "resolution_label": label_vn,
            "window_days": window_days,
            "allowed_window_days": window_days,
            "elapsed_days": elapsed_days,
            "days_since_order": elapsed_days,
            "remaining_days": max(0, window_days - elapsed_days),
            "receiving_roles": ["SALES", "MANAGER", "ADMIN", "WAREHOUSE"],
            "receiving_departments": ["SALES (CSKH & Tư vấn)", "MANAGER / ADMIN (Quản lý & Chủ shop)", "WAREHOUSE (Kho kiểm định)"],
            "message": (
                f"Đã gửi yêu cầu {label_vn} ({ticket_key}) cho đơn {order.code} "
                f"(Còn hạn {max(0, window_days - elapsed_days)}/{window_days} ngày). "
                f"Trung tâm Chăm sóc khách hàng Soobin Swimwear đã tiếp nhận phiếu hỗ trợ của quý khách!"
            )
        }

    def list_rma_requests(self) -> List[Dict[str, Any]]:
        from app.models.entities import ProductionOutboxEvent
        events = (
            self.db.query(ProductionOutboxEvent)
            .filter(ProductionOutboxEvent.event_type == "CUSTOMER_FEEDBACK_TICKET")
            .order_by(ProductionOutboxEvent.created_at.desc())
            .limit(100)
            .all()
        )
        res = []
        for ev in events:
            p = ev.payload if isinstance(ev.payload, dict) else {}
            t_code = p.get("ticket_code") or ev.event_key
            res.append({
                "id": ev.id,
                "ticket_id": t_code,
                "ticket_code": t_code,
                "feedback_id": p.get("feedback_id"),
                "order_id": p.get("order_id"),
                "order_code": p.get("order_code", ""),
                "customer_name": p.get("full_name") or p.get("sender_name") or "Khách hàng",
                "phone": p.get("phone", ""),
                "customer_phone": p.get("phone", ""),
                "resolution_type": p.get("resolution_type", "EXCHANGE_SIZE"),
                "request_type": p.get("resolution_type", "EXCHANGE_SIZE"),
                "resolution_label": p.get("resolution_label", "Đổi Size / Bảo hành"),
                "target_size": p.get("target_size", "Tư vấn"),
                "preferred_size": p.get("target_size", "Tư vấn"),
                "window_days": p.get("window_days", 15),
                "allowed_window_days": p.get("window_days", 15),
                "elapsed_days": p.get("elapsed_days", 0),
                "days_since_order": p.get("elapsed_days", 0),
                "remaining_days": p.get("remaining_days", 15),
                "receiving_roles": p.get("receiving_roles", ["SALES", "MANAGER", "ADMIN", "WAREHOUSE"]),
                "assigned_roles": p.get("receiving_roles", ["SALES", "MANAGER", "ADMIN", "WAREHOUSE"]),
                "subject": p.get("subject", "Yêu cầu Đổi Size / Bảo hành"),
                "reason": p.get("reason") or p.get("message", ""),
                "status": p.get("ticket_status", "NEW"),
                "staff_note": p.get("staff_note", ""),
                "resolution_note": p.get("staff_note", ""),
                "handled_by": p.get("handled_by_name", ""),
                "handled_by_name": p.get("handled_by_name", ""),
                "handled_by_role": p.get("handled_by_role", ""),
                "updated_at": p.get("updated_at"),
                "created_at": ev.created_at.isoformat() if ev.created_at else None
            })
        return res

    def update_rma_request(
        self,
        ticket_id: str,
        status: str,
        staff_note: Optional[str],
        actor: UserAccount
    ) -> Dict[str, Any]:
        from app.models.entities import ProductionOutboxEvent, ProductionFeedback
        ev = None
        if str(ticket_id).isdigit():
            ev = (
                self.db.query(ProductionOutboxEvent)
                .filter(ProductionOutboxEvent.id == int(ticket_id))
                .first()
            )
        if not ev:
            ev = (
                self.db.query(ProductionOutboxEvent)
                .filter(ProductionOutboxEvent.event_key == str(ticket_id))
                .first()
            )
        if not ev:
            raise ValueError("Không tìm thấy phiếu yêu cầu Bảo hành / Đổi trả.")

        p = dict(ev.payload or {})
        p["ticket_status"] = status
        if staff_note is not None:
            p["staff_note"] = staff_note.strip()
        p["handled_by_id"] = actor.id
        p["handled_by_name"] = actor.full_name
        p["handled_by_role"] = actor.role.code if actor.role else "STAFF"
        p["updated_at"] = datetime.now(timezone.utc).isoformat()
        ev.payload = p

        # Sync with ProductionFeedback if linked
        fb_id = p.get("feedback_id")
        if fb_id:
            fb = self.db.query(ProductionFeedback).filter(ProductionFeedback.id == fb_id).first()
            if fb:
                fb.status = "RESOLVED" if status in ("COMPLETED", "REJECTED") else "IN_PROGRESS"
                fb.handled_by = actor.id
                fb.handled_at = datetime.now(timezone.utc)

        # Also add order history log so customer sees the update in their order timeline
        ord_id = p.get("order_id")
        if ord_id:
            order = self.order_repo.get_by_id(int(ord_id))
            if order:
                self.order_repo.add_history(
                    order_id=order.id,
                    from_status=order.status,
                    to_status=order.status,
                    event_type=f"RMA_{status}",
                    reason=f"[{actor.role.code if actor.role else 'STAFF'} - {actor.full_name}] Cập nhật phiếu {p.get('ticket_code')}: {status}. {staff_note or ''}".strip(),
                    actor_id=actor.id
                )

        self.db.commit()
        ticket_summary = {
            "id": ev.id,
            "ticket_id": p.get("ticket_code") or ev.event_key,
            "ticket_code": p.get("ticket_code") or ev.event_key,
            "status": status,
            "staff_note": p.get("staff_note", ""),
            "resolution_note": p.get("staff_note", ""),
            "handled_by": actor.full_name,
            "handled_by_name": actor.full_name,
            "handled_by_role": actor.role.code if actor.role else "STAFF",
        }
        return {
            **ticket_summary,
            "ticket": ticket_summary,
            "message": f"Đã cập nhật phiếu {p.get('ticket_code') or ev.id} sang trạng thái '{status}'."
        }



