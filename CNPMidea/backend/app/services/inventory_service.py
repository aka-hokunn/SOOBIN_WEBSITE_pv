from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import uuid
from sqlalchemy.orm import Session
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.catalog_repository import CatalogRepository
from app.models.entities import (
    ProductionGoodsReceipt, ProductionGoodsReceiptItem,
    ProductionInventoryMovement, ProductionSupplier, UserAccount
)

class InventoryService:
    def __init__(self, db: Session):
        self.db = db
        self.inv_repo = InventoryRepository(db)
        self.catalog_repo = CatalogRepository(db)

    def list_suppliers(self) -> List[Dict[str, Any]]:
        sups = self.inv_repo.list_suppliers()
        return [
            {
                "id": s.id,
                "code": s.code,
                "name": s.name,
                "phone": s.phone,
                "email": s.email,
                "address": s.address,
                "is_active": s.is_active
            }
            for s in sups
        ]

    def list_inventory_balances(self) -> List[Dict[str, Any]]:
        from app.services.catalog_service import CatalogService
        balances = self.inv_repo.list_inventory_balances()
        prod_ids = list({inv.variant.product_id for inv in balances if inv.variant and inv.variant.product_id})
        disc_map = CatalogService(self.db)._get_product_discount_map(prod_ids) if prod_ids else {}
        res = []
        for inv in balances:
            v = inv.variant
            p = v.product if v else None
            unit_cost = (float(inv.inventory_value) / inv.available_quantity) if inv.available_quantity > 0 else 0.0
            base_p = float(p.base_price) if p else 0.0
            disc_pct = disc_map.get(p.id, 0.0) if p else 0.0
            sale_p = round(base_p * (1.0 - disc_pct / 100.0)) if disc_pct > 0 else base_p
            img_url = p.images[0].file_path if (p and p.images) else "/static/images/placeholder.webp"
            res.append({
                "variant_id": inv.variant_id,
                "product_id": p.id if p else None,
                "sku": v.sku if v else "",
                "product_name": p.name if p else "",
                "category_name": p.category.name if (p and p.category) else "",
                "image_url": img_url,
                "base_price": base_p,
                "discounted_price": sale_p,
                "discount_percent": disc_pct,
                "size_name": v.size.name if v and v.size else "",
                "color_name": v.color.name if v and v.color else "",
                "available_quantity": inv.available_quantity,
                "inventory_value": float(inv.inventory_value),
                "weighted_unit_cost": round(unit_cost, 2),
                "low_stock_threshold": inv.low_stock_threshold,
                "is_low_stock": inv.available_quantity <= inv.low_stock_threshold
            })
        return res

    def confirm_goods_receipt(
        self,
        supplier_id: int,
        confirmer_id: int,
        items_data: List[Dict[str, Any]], # list of {variant_id, quantity, unit_cost}
        note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates and confirms a goods receipt atomically (AC-INV-01, AC-INV-02, AC-INV-05).
        Updates weighted average unit cost and inventory balances.
        """
        supplier = self.inv_repo.get_supplier_by_id(supplier_id)
        if not supplier:
            raise ValueError("Nhà cung cấp không tồn tại.")

        if not items_data:
            raise ValueError("Phiếu nhập phải có ít nhất một dòng sản phẩm.")

        receipt_code = f"PN-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        supplier_snapshot = {
            "id": supplier.id,
            "code": supplier.code,
            "name": supplier.name,
            "phone": supplier.phone,
            "address": supplier.address
        }

        receipt = ProductionGoodsReceipt(
            code=receipt_code,
            supplier_id=supplier_id,
            confirmed_by=confirmer_id,
            confirmed_at=datetime.now(timezone.utc),
            supplier_snapshot=supplier_snapshot,
            note=note
        )
        self.db.add(receipt)
        self.db.flush()

        total_qty = 0
        total_cost = 0.0

        for item in items_data:
            v_id = item["variant_id"]
            qty = int(item["quantity"])
            cost = float(item["unit_cost"])
            if qty <= 0:
                raise ValueError("Số lượng nhập phải lớn hơn 0.")
            if cost < 0:
                raise ValueError("Đơn giá nhập không thể âm.")

            variant = self.catalog_repo.get_variant_by_id(v_id)
            if not variant:
                raise ValueError(f"Không tìm thấy biến thể #{v_id}.")

            inv = self.inv_repo.get_inventory_for_update(v_id)
            old_qty = inv.available_quantity if inv else 0
            old_val = float(inv.inventory_value) if inv else 0.0
            old_unit_cost = (old_val / old_qty) if old_qty > 0 else cost

            # Weighted average cost formula (PRD Section 8):
            # new_cost = (old_qty * old_unit_cost + qty * cost) / (old_qty + qty)
            new_qty = old_qty + qty
            new_val = old_val + (qty * cost)

            inv.available_quantity = new_qty
            inv.inventory_value = new_val

            variant_snapshot = {
                "sku": variant.sku,
                "product_name": variant.product.name,
                "size": variant.size.name if variant.size else "",
                "color": variant.color.name if variant.color else ""
            }

            receipt_item = ProductionGoodsReceiptItem(
                receipt_id=receipt.id,
                variant_id=v_id,
                quantity=qty,
                unit_cost=cost,
                variant_snapshot=variant_snapshot
            )
            self.db.add(receipt_item)
            self.db.flush()

            # Record inventory movement
            movement = ProductionInventoryMovement(
                variant_id=v_id,
                receipt_item_id=receipt_item.id,
                movement_type="RECEIPT",
                quantity_delta=qty,
                value_delta=qty * cost,
                event_key=f"RCPT-{receipt.id}-{receipt_item.id}",
                occurred_at=datetime.now(timezone.utc)
            )
            self.db.add(movement)

            total_qty += qty
            total_cost += qty * cost

        self.db.commit()

        return {
            "id": receipt.id,
            "code": receipt.code,
            "supplier_name": supplier.name,
            "total_quantity": total_qty,
            "total_cost": total_cost,
            "confirmed_at": receipt.confirmed_at.isoformat()
        }

    def list_goods_receipts(self) -> List[Dict[str, Any]]:
        receipts = self.inv_repo.list_goods_receipts()
        res = []
        for r in receipts:
            t_qty = sum(i.quantity for i in r.items)
            t_cost = sum(i.quantity * float(i.unit_cost) for i in r.items)
            res.append({
                "id": r.id,
                "code": r.code,
                "supplier_name": r.supplier.name if r.supplier else "",
                "confirmed_by_name": r.confirmer.full_name if r.confirmer else "",
                "confirmed_at": r.confirmed_at.isoformat(),
                "note": r.note,
                "total_quantity": t_qty,
                "total_cost": t_cost,
                "items": [
                    {
                        "id": item.id,
                        "variant_id": item.variant_id,
                        "sku": item.variant_snapshot.get("sku", ""),
                        "name": item.variant_snapshot.get("product_name", ""),
                        "quantity": item.quantity,
                        "unit_cost": float(item.unit_cost)
                    }
                    for item in r.items
                ]
            })
        return res

    def get_goods_receipt(self, receipt_id: int) -> Optional[Dict[str, Any]]:
        r = self.inv_repo.get_goods_receipt_by_id(receipt_id)
        if not r:
            return None
        t_qty = sum(i.quantity for i in r.items)
        t_cost = sum(i.quantity * float(i.unit_cost) for i in r.items)
        return {
            "id": r.id,
            "code": r.code,
            "supplier_id": r.supplier_id,
            "supplier_name": r.supplier.name if r.supplier else "",
            "confirmed_by_name": r.confirmer.full_name if r.confirmer else "",
            "confirmed_at": r.confirmed_at.isoformat(),
            "note": r.note,
            "total_quantity": t_qty,
            "total_cost": t_cost,
            "items": [
                {
                    "id": item.id,
                    "variant_id": item.variant_id,
                    "sku": item.variant_snapshot.get("sku", ""),
                    "name": item.variant_snapshot.get("product_name", ""),
                    "size": item.variant_snapshot.get("size", ""),
                    "color": item.variant_snapshot.get("color", ""),
                    "quantity": item.quantity,
                    "unit_cost": float(item.unit_cost),
                    "line_cost": item.quantity * float(item.unit_cost)
                }
                for item in r.items
            ]
        }

    def adjust_goods_receipt(
        self,
        receipt_id: int,
        adjuster_id: int,
        adjustments: List[Dict[str, Any]],
        note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Adjusts an already confirmed goods receipt (PRD & Flowchart in mo_ta_cnpm).
        Updates inventory quantity, inventory value (weighted avg cost), and writes audit movements.
        """
        receipt = self.inv_repo.get_goods_receipt_by_id(receipt_id)
        if not receipt:
            raise ValueError("Phiếu nhập không tồn tại.")

        if not adjustments:
            raise ValueError("Vui lòng cung cấp ít nhất một dòng cần điều chỉnh.")

        adjuster = self.db.query(UserAccount).filter(UserAccount.id == adjuster_id).first()
        adjuster_name = adjuster.full_name if adjuster else f"User #{adjuster_id}"

        item_map = {item.id: item for item in receipt.items}
        changed_count = 0
        details_log = []

        for adj in adjustments:
            item_id = adj.get("item_id")
            new_qty = adj.get("new_quantity")
            reason = adj.get("reason") or "Kiểm kê điều chỉnh"

            if item_id not in item_map:
                raise ValueError(f"Dòng sản phẩm #{item_id} không thuộc phiếu nhập này.")
            if new_qty < 0:
                raise ValueError("Số lượng điều chỉnh không thể âm.")

            item = item_map[item_id]
            old_qty = item.quantity
            delta_qty = new_qty - old_qty
            if delta_qty == 0:
                continue

            unit_cost = float(item.unit_cost)
            # Lock inventory row
            inv = self.inv_repo.get_inventory_for_update(item.variant_id)
            if not inv:
                raise ValueError(f"Không tìm thấy bản ghi tồn kho của biến thể #{item.variant_id}.")

            if delta_qty < 0:
                if inv.available_quantity + delta_qty < 0:
                    prod_name = item.variant_snapshot.get("product_name", f"Biến thể #{item.variant_id}")
                    raise ValueError(
                        f"Không thể giảm {abs(delta_qty)} sản phẩm '{prod_name}' vì tồn kho chỉ còn {inv.available_quantity} (đã bán)."
                    )

            # Update inventory
            inv.available_quantity += delta_qty
            delta_val = delta_qty * unit_cost
            inv.inventory_value = max(0.0, float(inv.inventory_value) + delta_val)
            if inv.available_quantity == 0:
                inv.inventory_value = 0.0

            # Record inventory movement
            movement_key = f"ADJ-{receipt.id}-{item.id}-{uuid.uuid4().hex[:8]}"
            movement = ProductionInventoryMovement(
                variant_id=item.variant_id,
                receipt_item_id=item.id,
                movement_type="RECEIPT_ADJUSTMENT",
                quantity_delta=delta_qty,
                value_delta=delta_val,
                event_key=movement_key,
                occurred_at=datetime.now(timezone.utc)
            )
            self.db.add(movement)

            # Update receipt item quantity
            item.quantity = new_qty
            changed_count += 1
            details_log.append(f"Dòng #{item.id} ({item.variant_snapshot.get('sku')}): {old_qty} -> {new_qty} (Lệch {delta_qty:+d}). Lý do: {reason}")

        if changed_count == 0:
            return {"message": "Không có dòng nào thay đổi số lượng.", "receipt_id": receipt.id}

        timestamp_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        log_text = f"\n[Phiếu điều chỉnh {timestamp_str} bởi {adjuster_name}]: " + "; ".join(details_log)
        if note:
            log_text += f". Ghi chú: {note}"
        receipt.note = (receipt.note or "") + log_text

        self.db.commit()

        return {
            "message": f"Điều chỉnh phiếu nhập thành công ({changed_count} dòng được cập nhật).",
            "receipt_id": receipt.id,
            "receipt_code": receipt.code,
            "details": details_log
        }

    def list_inventory_movements(self, limit: int = 50) -> List[Dict[str, Any]]:
        movements = self.inv_repo.list_inventory_movements(limit=limit)
        res = []
        for m in movements:
            v = m.variant
            p = v.product if v else None
            res.append({
                "id": m.id,
                "variant_id": m.variant_id,
                "sku": v.sku if v else "",
                "product_name": p.name if p else "",
                "movement_type": m.movement_type,
                "quantity_delta": m.quantity_delta,
                "value_delta": float(m.value_delta),
                "event_key": m.event_key,
                "occurred_at": m.occurred_at.isoformat()
            })
        return res

    def create_supplier(
        self,
        code: str,
        name: str,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        address: Optional[str] = None
    ) -> Dict[str, Any]:
        clean_code = code.strip().upper()
        existing = self.db.query(ProductionSupplier).filter(ProductionSupplier.code == clean_code).first()
        if existing:
            raise ValueError(f"Mã nhà cung cấp '{clean_code}' đã tồn tại.")
        sup = ProductionSupplier(
            code=clean_code,
            name=name.strip(),
            phone=phone.strip() if phone else None,
            email=email.strip() if email else None,
            address=address.strip() if address else None,
            is_active=True
        )
        self.db.add(sup)
        self.db.commit()
        self.db.refresh(sup)
        sup_obj = {
            "id": sup.id,
            "code": sup.code,
            "name": sup.name,
            "phone": sup.phone,
            "email": sup.email,
            "address": sup.address,
            "is_active": sup.is_active,
        }
        return {
            **sup_obj,
            "supplier": sup_obj,
            "message": f"Đã thêm nhà cung cấp {sup.name} ({sup.code})."
        }

    def update_supplier(
        self,
        supplier_id: int,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        address: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        sup = self.inv_repo.get_supplier_by_id(supplier_id)
        if not sup:
            raise ValueError("Không tìm thấy nhà cung cấp.")
        if name is not None:
            sup.name = name.strip()
        if phone is not None:
            sup.phone = phone.strip()
        if email is not None:
            sup.email = email.strip()
        if address is not None:
            sup.address = address.strip()
        if is_active is not None:
            sup.is_active = is_active
        self.db.commit()
        return {"message": f"Đã cập nhật nhà cung cấp {sup.name}.", "id": sup.id}

    def perform_stocktake(
        self,
        variant_id: int,
        actual_quantity: int,
        actor_id: int,
        low_stock_threshold: Optional[int] = None,
        reason: str = "Kiểm kê kho thực tế"
    ) -> Dict[str, Any]:
        if actual_quantity < 0:
            raise ValueError("Số lượng kiểm kê thực tế không thể âm.")
        inv = self.inv_repo.get_inventory_for_update(variant_id)
        if not inv:
            raise ValueError("Không tìm thấy dữ liệu tồn kho cho biến thể này.")

        old_qty = inv.available_quantity
        old_val = float(inv.inventory_value)
        unit_cost = (old_val / old_qty) if old_qty > 0 else (float(inv.variant.product.base_price) * 0.55 if inv.variant and inv.variant.product else 150000.0)
        delta_qty = actual_quantity - old_qty
        delta_val = round(delta_qty * unit_cost, 2)

        inv.available_quantity = actual_quantity
        inv.inventory_value = max(0.0, round(actual_quantity * unit_cost, 2))
        if low_stock_threshold is not None and low_stock_threshold >= 0:
            inv.low_stock_threshold = low_stock_threshold

        if delta_qty != 0:
            movement = ProductionInventoryMovement(
                variant_id=variant_id,
                movement_type="STOCKTAKE",
                quantity_delta=delta_qty,
                value_delta=delta_val,
                event_key=f"STKTK-{variant_id}-{uuid.uuid4().hex[:8]}",
                occurred_at=datetime.now(timezone.utc)
            )
            self.db.add(movement)

        self.db.commit()
        sku = inv.variant.sku if inv.variant else f"VAR-{variant_id}"
        st_obj = {
            "variant_id": variant_id,
            "sku": sku,
            "previous_quantity": old_qty,
            "actual_quantity": actual_quantity,
            "quantity_delta": delta_qty,
            "low_stock_threshold": inv.low_stock_threshold,
        }
        return {
            **st_obj,
            "stocktake": st_obj,
            "message": f"Kiểm kê SKU {sku} hoàn tất: Tồn hệ thống {old_qty} -> Thực tế {actual_quantity} (Chênh lệch {delta_qty:+d})."
        }


