from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, and_
from app.models.entities import ProductionPromotion, ProductionPromotionProduct, ProductionVoucherUsage

class PromotionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_code(self, code: str) -> Optional[ProductionPromotion]:
        return self.db.query(ProductionPromotion).filter(
            ProductionPromotion.code == code.upper().strip()
        ).first()

    def get_by_id(self, promo_id: int) -> Optional[ProductionPromotion]:
        return self.db.query(ProductionPromotion).filter(
            ProductionPromotion.id == promo_id
        ).first()

    def list_active_promotions(self) -> List[ProductionPromotion]:
        now = datetime.now(timezone.utc)
        return self.db.query(ProductionPromotion).filter(
            ProductionPromotion.is_active == True,
            ProductionPromotion.starts_at <= now,
            ProductionPromotion.ends_at >= now
        ).all()

    def get_active_product_promotions(self, product_ids: List[int]) -> List[ProductionPromotion]:
        if not product_ids:
            return []
        now = datetime.now(timezone.utc)
        return self.db.query(ProductionPromotion).join(ProductionPromotionProduct).filter(
            ProductionPromotion.promotion_type == "PRODUCT",
            ProductionPromotion.is_active == True,
            ProductionPromotion.starts_at <= now,
            ProductionPromotion.ends_at >= now,
            ProductionPromotionProduct.product_id.in_(product_ids)
        ).all()

    def get_active_order_promotions(self) -> List[ProductionPromotion]:
        now = datetime.now(timezone.utc)
        return self.db.query(ProductionPromotion).filter(
            ProductionPromotion.promotion_type == "ORDER",
            ProductionPromotion.is_active == True,
            ProductionPromotion.starts_at <= now,
            ProductionPromotion.ends_at >= now
        ).all()

    def get_voucher_for_update(self, code: str) -> Optional[ProductionPromotion]:
        """Lock voucher record to safely increment used_count without exceeding usage_limit."""
        return self.db.query(ProductionPromotion).filter(
            ProductionPromotion.code == code.upper().strip(),
            ProductionPromotion.promotion_type == "VOUCHER"
        ).with_for_update().first()

    def increment_voucher_usage(self, promo_id: int):
        promo = self.db.query(ProductionPromotion).filter(ProductionPromotion.id == promo_id).with_for_update().first()
        if promo:
            promo.used_count += 1
            self.db.flush()

    def decrement_voucher_usage(self, promo_id: int):
        promo = self.db.query(ProductionPromotion).filter(ProductionPromotion.id == promo_id).with_for_update().first()
        if promo and promo.used_count > 0:
            promo.used_count -= 1
            self.db.flush()

    def record_voucher_usage(self, order_id: int, promo_id: int) -> ProductionVoucherUsage:
        usage = ProductionVoucherUsage(
            order_id=order_id,
            promotion_id=promo_id,
            consumed_at=datetime.now(timezone.utc)
        )
        self.db.add(usage)
        self.db.flush()
        return usage

    def mark_voucher_restored(self, order_id: int) -> Optional[ProductionVoucherUsage]:
        usage = self.db.query(ProductionVoucherUsage).filter(
            ProductionVoucherUsage.order_id == order_id,
            ProductionVoucherUsage.restored_at == None
        ).first()
        if usage:
            usage.restored_at = datetime.now(timezone.utc)
            self.decrement_voucher_usage(usage.promotion_id)
            self.db.flush()
        return usage

    def create_promotion(self, promo: ProductionPromotion) -> ProductionPromotion:
        self.db.add(promo)
        self.db.flush()
        return promo
