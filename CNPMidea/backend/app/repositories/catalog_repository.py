from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, and_, or_, desc, asc
from app.models.entities import (
    ProductionCategory, ProductionProduct, ProductionVariant,
    ProductionProductImage, ProductionSize, ProductionColor,
    ProductionInventory, ProductionPromotion, ProductionPromotionProduct
)

class CatalogRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_categories(self, active_only: bool = True) -> List[ProductionCategory]:
        query = self.db.query(ProductionCategory)
        if active_only:
            query = query.filter(ProductionCategory.is_active == True)
        return query.order_by(ProductionCategory.sort_order, ProductionCategory.id).all()

    def get_category_by_id(self, category_id: int) -> Optional[ProductionCategory]:
        return self.db.query(ProductionCategory).filter(ProductionCategory.id == category_id).first()

    def get_category_by_slug(self, slug: str) -> Optional[ProductionCategory]:
        return self.db.query(ProductionCategory).filter(ProductionCategory.slug == slug).first()

    def list_sizes(self) -> List[ProductionSize]:
        return self.db.query(ProductionSize).order_by(ProductionSize.sort_order).all()

    def list_colors(self) -> List[ProductionColor]:
        return self.db.query(ProductionColor).order_by(ProductionColor.id).all()

    def get_variant_by_id(self, variant_id: int) -> Optional[ProductionVariant]:
        return self.db.query(ProductionVariant).options(
            joinedload(ProductionVariant.product),
            joinedload(ProductionVariant.size),
            joinedload(ProductionVariant.color),
            joinedload(ProductionVariant.inventory)
        ).filter(ProductionVariant.id == variant_id).first()

    def get_variant_by_sku(self, sku: str) -> Optional[ProductionVariant]:
        return self.db.query(ProductionVariant).filter(ProductionVariant.sku == sku).first()

    def get_product_by_id(self, product_id: int) -> Optional[ProductionProduct]:
        return self.db.query(ProductionProduct).options(
            joinedload(ProductionProduct.category),
            joinedload(ProductionProduct.variants).joinedload(ProductionVariant.size),
            joinedload(ProductionProduct.variants).joinedload(ProductionVariant.color),
            joinedload(ProductionProduct.variants).joinedload(ProductionVariant.inventory),
            joinedload(ProductionProduct.images)
        ).filter(ProductionProduct.id == product_id, ProductionProduct.deleted_at == None).first()

    def get_product_by_slug(self, slug: str) -> Optional[ProductionProduct]:
        return self.db.query(ProductionProduct).options(
            joinedload(ProductionProduct.category),
            joinedload(ProductionProduct.variants).joinedload(ProductionVariant.size),
            joinedload(ProductionProduct.variants).joinedload(ProductionVariant.color),
            joinedload(ProductionProduct.variants).joinedload(ProductionVariant.inventory),
            joinedload(ProductionProduct.images)
        ).filter(ProductionProduct.slug == slug, ProductionProduct.deleted_at == None).first()

    def search_products(
        self,
        category_slug: Optional[str] = None,
        target_audience: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        keyword: Optional[str] = None,
        size_id: Optional[int] = None,
        color_id: Optional[int] = None,
        on_sale: Optional[bool] = None,
        sort_by: str = "newest",
        limit: int = 20,
        offset: int = 0
    ) -> List[ProductionProduct]:
        query = self.db.query(ProductionProduct).filter(
            ProductionProduct.deleted_at == None,
            ProductionProduct.status == "Selling"
        )

        if category_slug:
            query = query.join(ProductionCategory).filter(
                or_(
                    ProductionCategory.slug == category_slug,
                    ProductionCategory.parent.has(ProductionCategory.slug == category_slug)
                )
            )

        if target_audience:
            query = query.filter(ProductionProduct.target_audience == target_audience)

        if min_price is not None:
            query = query.filter(ProductionProduct.base_price >= min_price)

        if max_price is not None:
            query = query.filter(ProductionProduct.base_price <= max_price)

        if keyword:
            kw = f"%{keyword.strip()}%"
            query = query.filter(
                or_(
                    ProductionProduct.name.ilike(kw),
                    ProductionProduct.description.ilike(kw),
                    ProductionProduct.code.ilike(kw)
                )
            )

        if size_id or color_id:
            query = query.join(ProductionVariant)
            if size_id:
                query = query.filter(ProductionVariant.size_id == size_id)
            if color_id:
                query = query.filter(ProductionVariant.color_id == color_id)

        if on_sale:
            now = datetime.now(timezone.utc)
            query = query.join(ProductionPromotionProduct).join(ProductionPromotion).filter(
                ProductionPromotion.promotion_type == "PRODUCT",
                ProductionPromotion.is_active == True,
                ProductionPromotion.starts_at <= now,
                ProductionPromotion.ends_at >= now
            )

        if sort_by == "price_asc":
            query = query.order_by(asc(ProductionProduct.base_price))
        elif sort_by == "price_desc":
            query = query.order_by(desc(ProductionProduct.base_price))
        elif sort_by == "name_asc":
            query = query.order_by(asc(ProductionProduct.name))
        else:
            query = query.order_by(desc(ProductionProduct.created_at))

        return query.distinct().options(
            joinedload(ProductionProduct.category),
            joinedload(ProductionProduct.variants).joinedload(ProductionVariant.inventory),
            joinedload(ProductionProduct.images)
        ).offset(offset).limit(limit).all()

    def create_product(self, product: ProductionProduct) -> ProductionProduct:
        self.db.add(product)
        self.db.flush()
        return product

    def list_products_for_management(self) -> List[ProductionProduct]:
        return self.db.query(ProductionProduct).options(
            joinedload(ProductionProduct.category),
            joinedload(ProductionProduct.variants).joinedload(ProductionVariant.size),
            joinedload(ProductionProduct.variants).joinedload(ProductionVariant.color),
            joinedload(ProductionProduct.variants).joinedload(ProductionVariant.inventory),
            joinedload(ProductionProduct.images)
        ).order_by(desc(ProductionProduct.created_at)).all()

    def update_product(self, product_id: int, values: Dict[str, Any]) -> Optional[ProductionProduct]:
        product = self.get_product_by_id(product_id)
        if not product:
            return None
        for key, value in values.items():
            if value is not None and hasattr(product, key):
                setattr(product, key, value)
        self.db.flush()
        return product

    def soft_delete_product(self, product_id: int):
        product = self.get_product_by_id(product_id)
        if product:
            product.deleted_at = datetime.now(timezone.utc)
            product.status = "Discontinued"
            self.db.flush()
