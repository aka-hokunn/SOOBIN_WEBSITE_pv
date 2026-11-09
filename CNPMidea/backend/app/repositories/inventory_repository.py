from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, and_
from app.models.entities import (
    ProductionInventory, ProductionGoodsReceipt, ProductionGoodsReceiptItem,
    ProductionInventoryMovement, ProductionSupplier, ProductionVariant
)

class InventoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_inventory(self, variant_id: int) -> Optional[ProductionInventory]:
        return self.db.query(ProductionInventory).filter(ProductionInventory.variant_id == variant_id).first()

    def get_inventory_for_update(self, variant_id: int) -> Optional[ProductionInventory]:
        """Row-level lock on inventory record to prevent race conditions during order placement."""
        return self.db.query(ProductionInventory).populate_existing().filter(
            ProductionInventory.variant_id == variant_id
        ).with_for_update().first()

    def deduct_stock(self, variant_id: int, quantity: int, unit_cost: float, order_item_id: Optional[int] = None, event_key: Optional[str] = None) -> ProductionInventory:
        inv = self.get_inventory_for_update(variant_id)
        if not inv or inv.available_quantity < quantity:
            raise ValueError(f"Biến thể #{variant_id} không đủ tồn kho (còn {inv.available_quantity if inv else 0}, yêu cầu {quantity})")

        inv.available_quantity -= quantity
        value_reduction = quantity * unit_cost
        inv.inventory_value = max(0.0, float(inv.inventory_value) - value_reduction)
        if inv.available_quantity == 0:
            inv.inventory_value = 0.0

        # Record movement
        if event_key:
            movement = ProductionInventoryMovement(
                variant_id=variant_id,
                order_item_id=order_item_id,
                movement_type="ORDER_OUT",
                quantity_delta=-quantity,
                value_delta=-value_reduction,
                event_key=event_key,
                occurred_at=datetime.now(timezone.utc)
            )
            self.db.add(movement)

        self.db.flush()
        return inv

    def restore_stock(self, variant_id: int, quantity: int, unit_cost: float, order_item_id: Optional[int] = None, event_key: Optional[str] = None) -> ProductionInventory:
        inv = self.get_inventory_for_update(variant_id)
        if not inv:
            raise ValueError(f"Không tìm thấy biến thể #{variant_id} để hoàn kho")

        inv.available_quantity += quantity
        value_addition = quantity * unit_cost
        inv.inventory_value = float(inv.inventory_value) + value_addition

        if event_key:
            movement = ProductionInventoryMovement(
                variant_id=variant_id,
                order_item_id=order_item_id,
                movement_type="ORDER_CANCEL_RESTORE",
                quantity_delta=quantity,
                value_delta=value_addition,
                event_key=event_key,
                occurred_at=datetime.now(timezone.utc)
            )
            self.db.add(movement)

        self.db.flush()
        return inv

    def list_suppliers(self, active_only: bool = True) -> List[ProductionSupplier]:
        query = self.db.query(ProductionSupplier)
        if active_only:
            query = query.filter(ProductionSupplier.is_active == True)
        return query.order_by(ProductionSupplier.id).all()

    def get_supplier_by_id(self, supplier_id: int) -> Optional[ProductionSupplier]:
        return self.db.query(ProductionSupplier).filter(ProductionSupplier.id == supplier_id).first()

    def list_goods_receipts(self) -> List[ProductionGoodsReceipt]:
        return self.db.query(ProductionGoodsReceipt).options(
            joinedload(ProductionGoodsReceipt.supplier),
            joinedload(ProductionGoodsReceipt.confirmer),
            joinedload(ProductionGoodsReceipt.items).joinedload(ProductionGoodsReceiptItem.variant)
        ).order_by(ProductionGoodsReceipt.confirmed_at.desc()).all()

    def get_goods_receipt_by_id(self, receipt_id: int) -> Optional[ProductionGoodsReceipt]:
        return self.db.query(ProductionGoodsReceipt).options(
            joinedload(ProductionGoodsReceipt.supplier),
            joinedload(ProductionGoodsReceipt.confirmer),
            joinedload(ProductionGoodsReceipt.items).joinedload(ProductionGoodsReceiptItem.variant)
        ).filter(ProductionGoodsReceipt.id == receipt_id).first()

    def create_goods_receipt(self, receipt: ProductionGoodsReceipt) -> ProductionGoodsReceipt:
        self.db.add(receipt)
        self.db.flush()
        return receipt

    def list_inventory_balances(self) -> List[ProductionInventory]:
        return self.db.query(ProductionInventory).options(
            joinedload(ProductionInventory.variant).joinedload(ProductionVariant.product),
            joinedload(ProductionInventory.variant).joinedload(ProductionVariant.size),
            joinedload(ProductionInventory.variant).joinedload(ProductionVariant.color)
        ).join(ProductionVariant).order_by(ProductionVariant.id).all()

    def list_inventory_movements(self, limit: int = 100) -> List[ProductionInventoryMovement]:
        return self.db.query(ProductionInventoryMovement).options(
            joinedload(ProductionInventoryMovement.variant).joinedload(ProductionVariant.product),
            joinedload(ProductionInventoryMovement.variant).joinedload(ProductionVariant.size),
            joinedload(ProductionInventoryMovement.variant).joinedload(ProductionVariant.color)
        ).order_by(ProductionInventoryMovement.occurred_at.desc()).limit(limit).all()

