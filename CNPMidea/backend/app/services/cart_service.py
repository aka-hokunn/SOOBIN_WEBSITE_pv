from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.repositories.cart_repository import CartRepository
from app.repositories.catalog_repository import CatalogRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.promotion_repository import PromotionRepository
from app.models.entities import ProductionOutboxEvent

class CartService:
    def __init__(self, db: Session):
        self.db = db
        self.cart_repo = CartRepository(db)
        self.catalog_repo = CatalogRepository(db)
        self.inv_repo = InventoryRepository(db)
        self.promo_repo = PromotionRepository(db)

    def get_cart(self, account_id: int) -> Dict[str, Any]:
        cart_items = self.cart_repo.get_cart_items(account_id)
        items_data = []
        subtotal = 0.0
        discounted_subtotal = 0.0

        product_ids = [ci.variant.product_id for ci in cart_items if ci.variant and ci.variant.product_id]
        best_discount_map: Dict[int, float] = {}
        if product_ids:
            active_promos = self.promo_repo.get_active_product_promotions(product_ids)
            from app.models.entities import ProductionPromotionProduct
            promo_links = self.db.query(ProductionPromotionProduct).filter(
                ProductionPromotionProduct.product_id.in_(product_ids)
            ).all()
            active_promo_dict = {p.id: float(p.discount_percent) for p in active_promos}
            for link in promo_links:
                if link.promotion_id in active_promo_dict:
                    pct = active_promo_dict[link.promotion_id]
                    if pct > best_discount_map.get(link.product_id, 0.0):
                        best_discount_map[link.product_id] = pct

        for ci in cart_items:
            variant = ci.variant
            product = variant.product if variant else None
            inv = variant.inventory if variant else None
            available = inv.available_quantity if inv else 0
            unit_price = float(product.base_price) if product else 0.0
            disc_pct = best_discount_map.get(product.id, 0.0) if product else 0.0
            sale_price = round(unit_price * (1.0 - disc_pct / 100.0)) if disc_pct > 0 else unit_price

            is_valid = True
            msg = None
            if not variant or not variant.is_active or not product or product.deleted_at is not None or product.status != "Selling":
                is_valid = False
                msg = "Sản phẩm đã ngừng kinh doanh."
            elif available <= 0:
                is_valid = False
                msg = "Sản phẩm hiện đang hết hàng."
            elif ci.quantity > available:
                is_valid = False
                msg = f"Số lượng trong giỏ ({ci.quantity}) vượt tồn kho ({available})."

            line_total = ci.quantity * unit_price
            discounted_line_total = ci.quantity * sale_price
            if is_valid:
                subtotal += line_total
                discounted_subtotal += discounted_line_total

            img_path = "/static/images/placeholder.webp"
            if product and product.images:
                img_path = product.images[0].file_path

            items_data.append({
                "variant_id": ci.variant_id,
                "product_id": product.id if product else 0,
                "product_name": product.name if product else "Sản phẩm",
                "product_slug": product.slug if product else "",
                "sku": variant.sku if variant else "",
                "size_name": variant.size.name if variant and variant.size else "",
                "color_name": variant.color.name if variant and variant.color else "",
                "unit_price": unit_price,
                "base_price": unit_price,
                "sale_price": sale_price,
                "discount_percent": disc_pct,
                "quantity": ci.quantity,
                "available_stock": available,
                "is_valid_for_checkout": is_valid,
                "status_message": msg,
                "line_total": line_total,
                "discounted_line_total": discounted_line_total,
                "image_url": img_path
            })

        return {
            "items": items_data,
            "subtotal": subtotal,
            "discounted_subtotal": discounted_subtotal,
            "product_discount_savings": max(0.0, subtotal - discounted_subtotal),
            "total_items": sum(i["quantity"] for i in items_data)
        }

    def add_bundle_to_cart(self, account_id: int, bundle_items: List[Dict[str, Any]], bundle_name: Optional[str] = None) -> Dict[str, Any]:
        if not bundle_items:
            raise ValueError("Set phối đồ không có sản phẩm nào.")
        added_count = 0
        skipped = []
        for item in bundle_items:
            v_id = int(item.get("variant_id", 0))
            qty = int(item.get("quantity", 1))
            if v_id <= 0 or qty <= 0:
                continue
            variant = self.catalog_repo.get_variant_by_id(v_id)
            inv = self.inv_repo.get_inventory(v_id) if variant else None
            avail = inv.available_quantity if inv else 0
            if not variant or not variant.is_active or avail <= 0:
                skipped.append(v_id)
                continue
            curr = self.cart_repo.get_cart_item(account_id, v_id)
            curr_qty = curr.quantity if curr else 0
            add_qty = min(qty, max(0, avail - curr_qty))
            if add_qty > 0:
                self.cart_repo.add_or_update_item(account_id, v_id, add_qty)
                added_count += add_qty
        if added_count == 0:
            raise ValueError("Các sản phẩm trong Set phối đồ hiện đã hết hàng hoặc vượt quá tồn kho.")
        self.db.commit()
        res = self.get_cart(account_id)
        res["bundle_name"] = bundle_name or "Set Phối Đồ 3D Soobin"
        res["added_bundle_items"] = added_count
        res["skipped_variants"] = skipped
        res["message"] = f"Đã thêm trọn bộ '{res['bundle_name']}' ({added_count} sản phẩm) vào giỏ hàng!"
        return res

    def add_to_cart(self, account_id: int, variant_id: int, quantity: int) -> Dict[str, Any]:
        variant = self.catalog_repo.get_variant_by_id(variant_id)
        if not variant or not variant.is_active:
            raise ValueError("Biến thể sản phẩm không tồn tại hoặc đã ngừng bán.")

        inv = self.inv_repo.get_inventory(variant_id)
        available = inv.available_quantity if inv else 0
        if available <= 0:
            raise ValueError("Biến thể này đã hết hàng.")

        curr_item = self.cart_repo.get_cart_item(account_id, variant_id)
        curr_qty = curr_item.quantity if curr_item else 0
        if curr_qty + quantity > available:
            raise ValueError(f"Không thể thêm. Tổng số lượng sẽ vượt quá tồn kho (còn {available} sản phẩm).")

        self.cart_repo.add_or_update_item(account_id, variant_id, quantity)
        self.db.commit()
        return self.get_cart(account_id)

    def update_cart_item(self, account_id: int, variant_id: int, quantity: int) -> Dict[str, Any]:
        if quantity <= 0:
            self.cart_repo.remove_item(account_id, variant_id)
        else:
            inv = self.inv_repo.get_inventory(variant_id)
            available = inv.available_quantity if inv else 0
            if quantity > available:
                raise ValueError(f"Số lượng yêu cầu ({quantity}) vượt tồn kho hiện có ({available}).")
            self.cart_repo.update_quantity(account_id, variant_id, quantity)

        self.db.commit()
        return self.get_cart(account_id)

    def remove_from_cart(self, account_id: int, variant_id: int) -> Dict[str, Any]:
        self.cart_repo.remove_item(account_id, variant_id)
        self.db.commit()
        return self.get_cart(account_id)

    def merge_guest_cart(self, account_id: int, guest_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge guest cart into user account cart (AC-BR-PRD-CART-01..03).
        If quantity exceeds available stock, adjust down to available stock.
        """
        adjustments = []
        for g_item in guest_items:
            v_id = g_item.get("variant_id")
            req_qty = g_item.get("quantity", 1)
            if not v_id or req_qty <= 0:
                continue

            inv = self.inv_repo.get_inventory(v_id)
            avail = inv.available_quantity if inv else 0
            if avail <= 0:
                adjustments.append(f"Biến thể #{v_id} đã hết hàng, không thể thêm vào giỏ.")
                continue

            curr_item = self.cart_repo.get_cart_item(account_id, v_id)
            total_target = (curr_item.quantity if curr_item else 0) + req_qty
            if total_target > avail:
                final_qty = avail
                adjustments.append(f"Biến thể #{v_id}: Số lượng được tự động điều chỉnh về tối đa {avail} sản phẩm có sẵn.")
            else:
                final_qty = total_target

            if curr_item:
                self.cart_repo.update_quantity(account_id, v_id, final_qty)
            else:
                self.cart_repo.add_or_update_item(account_id, v_id, final_qty)

        self.db.commit()
        res = self.get_cart(account_id)
        res["adjustments"] = adjustments
        return res

    # -------------------------------------------------------------------------
    # WISHLIST & DISCOUNT NOTIFICATIONS
    # -------------------------------------------------------------------------

    def get_wishlist(self, account_id: int) -> List[Dict[str, Any]]:
        w_items = self.cart_repo.get_wishlist_items(account_id)
        if not w_items:
            return []
        product_ids = [w.product_id for w in w_items]
        active_promos = self.promo_repo.get_active_product_promotions(product_ids)

        # Map best discount percent per product
        best_discount_map: Dict[int, float] = {}
        from app.models.entities import ProductionPromotionProduct
        promo_links = self.db.query(ProductionPromotionProduct).filter(
            ProductionPromotionProduct.product_id.in_(product_ids)
        ).all()
        active_promo_dict = {p.id: float(p.discount_percent) for p in active_promos}
        for link in promo_links:
            if link.promotion_id in active_promo_dict:
                pct = active_promo_dict[link.promotion_id]
                if pct > best_discount_map.get(link.product_id, 0.0):
                    best_discount_map[link.product_id] = pct

        res = []
        for w in w_items:
            prod = self.catalog_repo.get_product_by_id(w.product_id)
            if not prod:
                continue
            base_p = float(prod.base_price)
            disc_pct = best_discount_map.get(prod.id, 0.0)
            sale_p = round(base_p * (1.0 - disc_pct / 100.0)) if disc_pct > 0 else base_p
            total_stock = sum((v.inventory.available_quantity if v.inventory else 0) for v in prod.variants if v.is_active)
            img_url = prod.images[0].file_path if prod.images else "/static/images/placeholder.webp"
            res.append({
                "product_id": prod.id,
                "name": prod.name,
                "code": prod.code,
                "slug": prod.slug,
                "base_price": base_p,
                "sale_price": sale_p,
                "discount_percent": disc_pct,
                "is_on_sale": disc_pct > 0,
                "image_url": img_url,
                "is_in_stock": total_stock > 0,
                "total_stock": total_stock,
                "added_at": w.created_at.isoformat()
            })
        return res

    def toggle_wishlist(self, account_id: int, product_id: int) -> Dict[str, Any]:
        prod = self.catalog_repo.get_product_by_id(product_id)
        if not prod:
            raise ValueError("Sản phẩm không tồn tại.")

        existing = self.cart_repo.get_wishlist_item(account_id, product_id)
        if existing:
            self.cart_repo.remove_wishlist_item(account_id, product_id)
            self.db.commit()
            return {
                "product_id": product_id,
                "is_in_wishlist": False,
                "message": f"Đã xóa '{prod.name}' khỏi danh sách yêu thích."
            }
        else:
            self.cart_repo.add_wishlist_item(account_id, product_id)
            self.db.commit()
            return {
                "product_id": product_id,
                "is_in_wishlist": True,
                "message": f"Đã thêm '{prod.name}' vào danh sách yêu thích."
            }

    def remove_from_wishlist(self, account_id: int, product_id: int) -> Dict[str, Any]:
        self.cart_repo.remove_wishlist_item(account_id, product_id)
        self.db.commit()
        return {"message": "Đã xóa khỏi danh sách yêu thích.", "product_id": product_id}

    def check_wishlist_discounts(self, account_id: int) -> Dict[str, Any]:
        """
        Checks if any product in the user's wishlist is currently on sale and records an email notification event.
        """
        import uuid
        wishlist = self.get_wishlist(account_id)
        discounted = [item for item in wishlist if item.get("is_on_sale")]
        if discounted:
            event = ProductionOutboxEvent(
                event_type="WISHLIST_DISCOUNT_EMAIL",
                event_key=f"WL-DISC-{account_id}-{uuid.uuid4().hex[:8]}",
                payload={
                    "account_id": account_id,
                    "discounted_count": len(discounted),
                    "items": [{"product_id": d["product_id"], "name": d["name"], "discount_percent": d["discount_percent"], "sale_price": d["sale_price"]} for d in discounted]
                },
                status="PUBLISHED",
                created_at=datetime.now(timezone.utc)
            )
            self.db.add(event)
            self.db.commit()
        return {
            "discounted_count": len(discounted),
            "discounted_items": discounted,
            "notification_sent": len(discounted) > 0
        }

    # -------------------------------------------------------------------------
    # ABANDONED CART REMINDER (> 24 HOURS)
    # -------------------------------------------------------------------------

    def trigger_cart_reminders(self, older_than_hours: int = 24) -> Dict[str, Any]:
        """
        Mo_ta_cnpm Section 5: Automatically send email notification if items remain in cart > 1 day.
        """
        import uuid
        old_items = self.cart_repo.get_abandoned_cart_items(older_than_hours=older_than_hours)
        by_user: Dict[int, List[Any]] = {}
        for ci in old_items:
            by_user.setdefault(ci.account_id, []).append(ci)

        notified_users = []
        for acc_id, items in by_user.items():
            user = items[0].account
            if not user or user.is_locked:
                continue
            item_names = [
                f"{i.variant.product.name} (x{i.quantity})"
                for i in items if i.variant and i.variant.product
            ]
            outbox = ProductionOutboxEvent(
                event_type="ABANDONED_CART_REMINDER_EMAIL",
                event_key=f"CART-REM-{acc_id}-{uuid.uuid4().hex[:8]}",
                payload={
                    "account_id": acc_id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "items_count": len(items),
                    "items_summary": item_names,
                    "message": f"Xin chào {user.full_name}, bạn còn {len(items)} sản phẩm đồ bơi trong giỏ hàng hơn 24 giờ. Đặt hàng ngay hôm nay để nhận ưu đãi!"
                },
                status="PUBLISHED",
                created_at=datetime.now(timezone.utc)
            )
            self.db.add(outbox)
            notified_users.append({
                "account_id": acc_id,
                "email": user.email,
                "items_count": len(items),
                "items": item_names
            })

        self.db.commit()
        return {
            "message": f"Đã quét và gửi thông báo nhắc giỏ hàng cho {len(notified_users)} khách hàng.",
            "notified_count": len(notified_users),
            "notified_users": notified_users
        }

