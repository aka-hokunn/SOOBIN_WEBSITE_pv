from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.repositories.promotion_repository import PromotionRepository
from app.models.entities import ProductionPromotion

class PromotionService:
    def __init__(self, db: Session):
        self.db = db
        self.promo_repo = PromotionRepository(db)

    @staticmethod
    def round_dong(val: float) -> float:
        """Round to nearest VND (0.5 rounds up) per PRD Section 7."""
        d = Decimal(str(val))
        return float(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    def calculate_discounts(
        self,
        items: List[Dict[str, Any]], # list of {product_id, variant_id, unit_price, quantity}
        voucher_code: Optional[str] = None,
        account_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calculate non-cumulative discounts among:
        1. Product promotion (D_sp)
        2. Order promotion (D_hd)
        3. Voucher promotion (D_vc)
        Winner is max(D_sp, D_hd, D_vc) with tie-breaker: Product -> Order -> Voucher.
        """
        if not items:
            return {
                "original_subtotal": 0.0,
                "product_discount": 0.0,
                "order_discount": 0.0,
                "voucher_discount": 0.0,
                "selected_option_type": "NONE",
                "winning_discount_amount": 0.0,
                "final_subtotal": 0.0,
                "applied_voucher": None,
                "eligible_options": []
            }

        # Calculate G (total original amount)
        G = sum(item["quantity"] * item["unit_price"] for item in items)
        G = self.round_dong(G)

        # ---------------------------------------------------------------------
        # 1. Product Discount Option (D_sp)
        # ---------------------------------------------------------------------
        product_ids = list(set(item["product_id"] for item in items))
        product_promos = self.promo_repo.get_active_product_promotions(product_ids)
        
        # Map product_id to highest active discount percent
        product_discount_map: Dict[int, Tuple[float, Optional[ProductionPromotion]]] = {}
        for p in product_promos:
            rate = float(p.discount_percent) / 100.0
            for prod in p.products:
                if prod.id not in product_discount_map or rate > product_discount_map[prod.id][0]:
                    product_discount_map[prod.id] = (rate, p)

        D_sp_raw = 0.0
        item_line_discounts = []
        for item in items:
            p_id = item["product_id"]
            rate, p_obj = product_discount_map.get(p_id, (0.0, None))
            item_discount = self.round_dong(item["quantity"] * item["unit_price"] * rate)
            D_sp_raw += item_discount
            item_line_discounts.append({
                "variant_id": item["variant_id"],
                "allocated_discount": item_discount,
                "promotion_id": p_obj.id if p_obj else None,
                "promotion_code": p_obj.code if p_obj else None
            })

        D_sp = self.round_dong(D_sp_raw)

        # ---------------------------------------------------------------------
        # 2. Order Discount Option (D_hd)
        # ---------------------------------------------------------------------
        order_promos = self.promo_repo.get_active_order_promotions()
        best_order_promo: Optional[ProductionPromotion] = None
        best_order_rate = 0.0

        for op in order_promos:
            if G >= float(op.minimum_order_amount):
                rate = float(op.discount_percent) / 100.0
                if rate > best_order_rate:
                    best_order_rate = rate
                    best_order_promo = op

        D_hd = self.round_dong(G * best_order_rate) if best_order_promo else 0.0

        # ---------------------------------------------------------------------
        # 3. Voucher Discount Option (D_vc)
        # ---------------------------------------------------------------------
        D_vc = 0.0
        applied_voucher: Optional[ProductionPromotion] = None
        voucher_error: Optional[str] = None

        if voucher_code:
            vc = self.promo_repo.get_by_code(voucher_code)
            now = datetime.now(timezone.utc)
            if not vc or vc.promotion_type != "VOUCHER":
                voucher_error = "Mã voucher không tồn tại."
            elif not vc.is_active:
                voucher_error = "Mã voucher đã bị tạm khóa."
            elif vc.starts_at > now or vc.ends_at < now:
                voucher_error = "Mã voucher đã hết hạn hoặc chưa đến ngày áp dụng."
            elif vc.usage_limit is not None and vc.used_count >= vc.usage_limit:
                voucher_error = "Mã voucher đã hết lượt sử dụng."
            elif vc.eligible_customer_ids is not None and account_id not in vc.eligible_customer_ids:
                voucher_error = "Voucher này chỉ áp dụng cho nhóm khách hàng được chọn."
            elif G < float(vc.minimum_order_amount):
                voucher_error = f"Đơn hàng chưa đạt giá trị tối thiểu {float(vc.minimum_order_amount):,.0f}đ để dùng voucher này."
            else:
                applied_voucher = vc
                rate = float(vc.discount_percent) / 100.0
                D_vc = self.round_dong(G * rate)

        # ---------------------------------------------------------------------
        # Selection and Tie-Breaking: Product -> Order -> Voucher
        # ---------------------------------------------------------------------
        max_discount = max(D_sp, D_hd, D_vc)
        selected_option = "NONE"

        if max_discount > 0:
            if D_sp == max_discount:
                selected_option = "PRODUCT"
            elif D_hd == max_discount:
                selected_option = "ORDER"
            elif D_vc == max_discount:
                selected_option = "VOUCHER"

        winning_discount = max_discount
        final_subtotal = max(0.0, G - winning_discount)

        # Allocation per item line for order / voucher options proportionally
        allocated_items = []
        if selected_option == "PRODUCT":
            allocated_items = item_line_discounts
        elif selected_option in ("ORDER", "VOUCHER") and G > 0:
            accumulated_discount = 0.0
            for idx, itm in enumerate(items):
                line_val = itm["quantity"] * itm["unit_price"]
                if idx == len(items) - 1:
                    line_disc = winning_discount - accumulated_discount
                else:
                    line_disc = self.round_dong(winning_discount * (line_val / G))
                    accumulated_discount += line_disc

                allocated_items.append({
                    "variant_id": itm["variant_id"],
                    "allocated_discount": line_disc,
                    "promotion_id": best_order_promo.id if selected_option == "ORDER" else (applied_voucher.id if applied_voucher else None),
                    "promotion_code": best_order_promo.code if selected_option == "ORDER" else (applied_voucher.code if applied_voucher else None)
                })
        else:
            for itm in items:
                allocated_items.append({
                    "variant_id": itm["variant_id"],
                    "allocated_discount": 0.0,
                    "promotion_id": None,
                    "promotion_code": None
                })

        eligible_options = [
            {"option_type": "PRODUCT", "discount_amount": D_sp, "is_eligible": D_sp > 0, "is_selected": selected_option == "PRODUCT"},
            {"option_type": "ORDER", "discount_amount": D_hd, "is_eligible": D_hd > 0, "is_selected": selected_option == "ORDER", "promo_code": best_order_promo.code if best_order_promo else None},
            {"option_type": "VOUCHER", "discount_amount": D_vc, "is_eligible": D_vc > 0, "is_selected": selected_option == "VOUCHER", "promo_code": applied_voucher.code if applied_voucher else None, "error": voucher_error}
        ]

        return {
            "original_subtotal": G,
            "product_discount": D_sp,
            "order_discount": D_hd,
            "voucher_discount": D_vc,
            "selected_option_type": selected_option,
            "winning_discount_amount": winning_discount,
            "final_subtotal": final_subtotal,
            "applied_voucher": applied_voucher,
            "eligible_options": eligible_options,
            "allocated_items": allocated_items
        }
