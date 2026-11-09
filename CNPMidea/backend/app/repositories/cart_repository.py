from typing import Optional, List
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session, joinedload
from app.models.entities import (
    ProductionCartItem, ProductionWishlistItem, ProductionVariant,
    ProductionInventory, ProductionProduct
)

class CartRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_cart_items(self, account_id: int) -> List[ProductionCartItem]:
        return self.db.query(ProductionCartItem).options(
            joinedload(ProductionCartItem.variant).joinedload(ProductionVariant.product),
            joinedload(ProductionCartItem.variant).joinedload(ProductionVariant.size),
            joinedload(ProductionCartItem.variant).joinedload(ProductionVariant.color),
            joinedload(ProductionCartItem.variant).joinedload(ProductionVariant.inventory)
        ).filter(ProductionCartItem.account_id == account_id).all()

    def get_cart_item(self, account_id: int, variant_id: int) -> Optional[ProductionCartItem]:
        return self.db.query(ProductionCartItem).filter(
            ProductionCartItem.account_id == account_id,
            ProductionCartItem.variant_id == variant_id
        ).first()

    def add_or_update_item(self, account_id: int, variant_id: int, quantity: int) -> ProductionCartItem:
        item = self.get_cart_item(account_id, variant_id)
        if item:
            item.quantity += quantity
            item.updated_at = datetime.now(timezone.utc)
        else:
            item = ProductionCartItem(
                account_id=account_id,
                variant_id=variant_id,
                quantity=quantity
            )
            self.db.add(item)
        self.db.flush()
        return item

    def update_quantity(self, account_id: int, variant_id: int, quantity: int) -> Optional[ProductionCartItem]:
        item = self.get_cart_item(account_id, variant_id)
        if item:
            item.quantity = quantity
            item.updated_at = datetime.now(timezone.utc)
            self.db.flush()
        return item

    def remove_item(self, account_id: int, variant_id: int):
        self.db.query(ProductionCartItem).filter(
            ProductionCartItem.account_id == account_id,
            ProductionCartItem.variant_id == variant_id
        ).delete()
        self.db.flush()

    def clear_cart(self, account_id: int):
        self.db.query(ProductionCartItem).filter(
            ProductionCartItem.account_id == account_id
        ).delete()
        self.db.flush()

    def get_abandoned_cart_items(self, older_than_hours: int = 24) -> List[ProductionCartItem]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
        return self.db.query(ProductionCartItem).options(
            joinedload(ProductionCartItem.account),
            joinedload(ProductionCartItem.variant).joinedload(ProductionVariant.product)
        ).filter(ProductionCartItem.updated_at <= cutoff).all()

    # -------------------------------------------------------------------------
    # WISHLIST METHODS
    # -------------------------------------------------------------------------

    def get_wishlist_items(self, account_id: int) -> List[ProductionWishlistItem]:
        return self.db.query(ProductionWishlistItem).filter(
            ProductionWishlistItem.account_id == account_id
        ).order_by(ProductionWishlistItem.created_at.desc()).all()

    def get_wishlist_item(self, account_id: int, product_id: int) -> Optional[ProductionWishlistItem]:
        return self.db.query(ProductionWishlistItem).filter(
            ProductionWishlistItem.account_id == account_id,
            ProductionWishlistItem.product_id == product_id
        ).first()

    def add_wishlist_item(self, account_id: int, product_id: int) -> ProductionWishlistItem:
        item = self.get_wishlist_item(account_id, product_id)
        if not item:
            item = ProductionWishlistItem(
                account_id=account_id,
                product_id=product_id,
                created_at=datetime.now(timezone.utc)
            )
            self.db.add(item)
            self.db.flush()
        return item

    def remove_wishlist_item(self, account_id: int, product_id: int) -> bool:
        deleted = self.db.query(ProductionWishlistItem).filter(
            ProductionWishlistItem.account_id == account_id,
            ProductionWishlistItem.product_id == product_id
        ).delete()
        self.db.flush()
        return deleted > 0

