from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_role
from app.services.inventory_service import InventoryService
from app.schemas.all_schemas import (
    GoodsReceiptCreate, GoodsReceiptAdjustmentRequest,
    SupplierCreateRequest, SupplierUpdateRequest, StocktakeRequest
)
from app.models.entities import UserAccount, ProductionSupplier


class QuickRestockRequest(BaseModel):
    variant_id: int
    quantity: int = 20
    unit_cost: Optional[float] = None
    supplier_id: Optional[int] = None
    note: Optional[str] = "Nhập bổ sung nhanh từ Bảng cảnh báo tồn kho"

router = APIRouter(prefix="/inventory", tags=["Inventory"])

@router.get("/suppliers")
def list_suppliers(db: Session = Depends(get_db)):
    svc = InventoryService(db)
    return svc.list_suppliers()

@router.post("/suppliers", status_code=status.HTTP_201_CREATED)
def create_supplier(
    req: SupplierCreateRequest,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "WAREHOUSE"])),
    db: Session = Depends(get_db)
):
    svc = InventoryService(db)
    try:
        return svc.create_supplier(
            code=req.code,
            name=req.name,
            phone=req.phone,
            email=req.email,
            address=req.address
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.put("/suppliers/{supplier_id}")
def update_supplier(
    supplier_id: int,
    req: SupplierUpdateRequest,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "WAREHOUSE"])),
    db: Session = Depends(get_db)
):
    svc = InventoryService(db)
    try:
        return svc.update_supplier(
            supplier_id=supplier_id,
            name=req.name,
            phone=req.phone,
            email=req.email,
            address=req.address,
            is_active=req.is_active
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/stocktake")
def perform_stocktake(
    req: StocktakeRequest,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "WAREHOUSE"])),
    db: Session = Depends(get_db)
):
    svc = InventoryService(db)
    try:
        return svc.perform_stocktake(
            variant_id=req.variant_id,
            actual_quantity=req.actual_quantity,
            actor_id=user.id,
            low_stock_threshold=req.low_stock_threshold,
            reason=req.reason
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/balances")
def list_inventory_balances(
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "WAREHOUSE", "SALES"])),
    db: Session = Depends(get_db)
):
    svc = InventoryService(db)
    return svc.list_inventory_balances()

@router.get("/receipts")
def list_goods_receipts(
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "WAREHOUSE"])),
    db: Session = Depends(get_db)
):
    svc = InventoryService(db)
    return svc.list_goods_receipts()

@router.post("/receipts/confirm")
def confirm_goods_receipt(
    req: GoodsReceiptCreate,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "WAREHOUSE"])),
    db: Session = Depends(get_db)
):
    svc = InventoryService(db)
    items_data = [
        {"variant_id": item.variant_id, "quantity": item.quantity, "unit_cost": item.unit_cost}
        for item in req.items
    ]
    try:
        receipt = svc.confirm_goods_receipt(
            supplier_id=req.supplier_id,
            confirmer_id=user.id,
            items_data=items_data,
            note=req.note
        )
        return {
            "message": "Xác nhận phiếu nhập hàng thành công. Tồn kho và giá vốn bình quân đã được cập nhật.",
            "receipt": receipt
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/receipts/{receipt_id}")
def get_goods_receipt_detail(
    receipt_id: int,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "WAREHOUSE"])),
    db: Session = Depends(get_db)
):
    svc = InventoryService(db)
    receipt = svc.get_goods_receipt(receipt_id)
    if not receipt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiếu nhập hàng.")
    return receipt

@router.put("/receipts/{receipt_id}")
def block_direct_edit_goods_receipt(
    receipt_id: int,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "WAREHOUSE"]))
):
    # AC-INV-03: Confirmed goods receipts cannot be modified directly.
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Phiếu nhập đã xác nhận bị khóa không cho phép sửa trực tiếp. Vui lòng tạo Phiếu điều chỉnh (POST /receipts/{id}/adjust)."
    )

@router.delete("/receipts/{receipt_id}")
def block_direct_delete_goods_receipt(
    receipt_id: int,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "WAREHOUSE"]))
):
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Phiếu nhập đã xác nhận không được phép xóa."
    )

@router.post("/receipts/{receipt_id}/adjust")
def adjust_confirmed_goods_receipt(
    receipt_id: int,
    req: GoodsReceiptAdjustmentRequest,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "WAREHOUSE"])),
    db: Session = Depends(get_db)
):
    svc = InventoryService(db)
    adjs = [
        {"item_id": item.item_id, "new_quantity": item.new_quantity, "reason": item.reason}
        for item in req.adjustments
    ]
    try:
        return svc.adjust_goods_receipt(
            receipt_id=receipt_id,
            adjuster_id=user.id,
            adjustments=adjs,
            note=req.note
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/movements")
def list_inventory_movements(
    limit: int = 50,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "WAREHOUSE"])),
    db: Session = Depends(get_db)
):
    svc = InventoryService(db)
    return svc.list_inventory_movements(limit=limit)


@router.get("/low-stock-alerts")
def get_low_stock_alerts(
    max_qty: int = 18,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "WAREHOUSE", "SALES"])),
    db: Session = Depends(get_db)
):
    svc = InventoryService(db)
    balances = svc.list_inventory_balances()
    alerts = []
    for b in balances:
        threshold = max(int(b.get("low_stock_threshold") or 5), max_qty)
        avail = int(b.get("available_quantity") or 0)
        if avail <= threshold:
            rec_qty = max(20, (threshold * 2) - avail)
            unit_cost = float(b.get("avg_unit_cost") or 180000.0)
            if unit_cost <= 0:
                unit_cost = round(float(b.get("base_price") or 400000.0) * 0.45)
            alerts.append({
                **b,
                "urgency": "OUT_OF_STOCK" if avail <= 0 else ("CRITICAL" if avail <= 5 else "LOW_STOCK"),
                "recommended_restock_qty": rec_qty,
                "suggested_unit_cost": round(unit_cost),
                "estimated_restock_cost": round(rec_qty * unit_cost),
            })
    alerts.sort(key=lambda x: (x["available_quantity"], x["variant_id"]))
    return {
        "total_alerts": len(alerts),
        "out_of_stock_count": sum(1 for a in alerts if a["available_quantity"] <= 0),
        "critical_count": sum(1 for a in alerts if 0 < a["available_quantity"] <= 5),
        "items": alerts[:40],
    }


@router.post("/quick-restock")
def quick_restock_variant(
    req: QuickRestockRequest,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "WAREHOUSE"])),
    db: Session = Depends(get_db)
):
    if req.quantity <= 0:
        raise HTTPException(status_code=400, detail="Số lượng nhập bổ sung phải lớn hơn 0.")
    svc = InventoryService(db)
    balances = svc.list_inventory_balances()
    target = next((b for b in balances if b["variant_id"] == req.variant_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy biến thể sản phẩm.")

    supplier_id = req.supplier_id
    if not supplier_id:
        sup = db.query(ProductionSupplier).filter(ProductionSupplier.is_active == True).first()
        if not sup:
            sup = db.query(ProductionSupplier).first()
        supplier_id = sup.id if sup else 1

    unit_cost = req.unit_cost
    if unit_cost is None or unit_cost <= 0:
        unit_cost = float(target.get("avg_unit_cost") or 0)
        if unit_cost <= 0:
            unit_cost = round(float(target.get("base_price") or 450000.0) * 0.45)

    receipt = svc.confirm_goods_receipt(
        supplier_id=supplier_id,
        confirmer_id=user.id,
        items_data=[{
            "variant_id": req.variant_id,
            "quantity": req.quantity,
            "unit_cost": unit_cost
        }],
        note=req.note or f"Nhập kho nhanh +{req.quantity} chiếc cho SKU {target.get('sku')}"
    )
    new_avail = int(target.get("available_quantity") or 0) + req.quantity
    return {
        "message": f"Đã nhập bổ sung nhanh +{req.quantity} chiếc cho {target.get('product_name')} ({target.get('size')}/{target.get('color')}).",
        "variant_id": req.variant_id,
        "sku": target.get("sku"),
        "added_quantity": req.quantity,
        "new_available_quantity": new_avail,
        "receipt": receipt
    }

