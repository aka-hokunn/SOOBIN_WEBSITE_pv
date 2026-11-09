import pytest
from app.services.inventory_service import InventoryService
from app.core.database import SessionLocal
from app.models.entities import ProductionInventory

def test_ac_inv_05_weighted_average_cost_calculation(client):
    """
    AC-INV-05: Nhập 10 chiếc giá 100.000 và 10 chiếc giá 120.000,
    không phát sinh giao dịch xen giữa -> bình quân 110.000/chiếc.
    """
    db = SessionLocal()
    # Reset variant 15 (Quần boxer L) to 0 units
    inv = db.query(ProductionInventory).filter(ProductionInventory.variant_id == 15).first()
    inv.available_quantity = 0
    inv.inventory_value = 0.0
    db.commit()

    svc = InventoryService(db)

    # 1. Receipt 1: 10 units @ 100,000đ
    r1 = svc.confirm_goods_receipt(
        supplier_id=1,
        confirmer_id=2, # Manager
        items_data=[{"variant_id": 15, "quantity": 10, "unit_cost": 100000.0}],
        note="Lần nhập 1"
    )
    inv1 = db.query(ProductionInventory).filter(ProductionInventory.variant_id == 15).first()
    assert inv1.available_quantity == 10
    assert float(inv1.inventory_value) == 1000000.0
    assert (float(inv1.inventory_value) / inv1.available_quantity) == 100000.0

    # 2. Receipt 2: 10 units @ 120,000đ
    r2 = svc.confirm_goods_receipt(
        supplier_id=1,
        confirmer_id=2,
        items_data=[{"variant_id": 15, "quantity": 10, "unit_cost": 120000.0}],
        note="Lần nhập 2"
    )
    inv2 = db.query(ProductionInventory).filter(ProductionInventory.variant_id == 15).first()
    assert inv2.available_quantity == 20
    # Total value = 1,000,000 + 1,200,000 = 2,200,000đ
    assert float(inv2.inventory_value) == 2200000.0
    # Weighted average unit cost = 2,200,000 / 20 = 110,000đ/chiếc!
    avg_cost = float(inv2.inventory_value) / inv2.available_quantity
    assert avg_cost == 110000.0, f"Expected 110,000đ, got {avg_cost}"

    db.close()

def test_goods_receipts_confirmed_locked_and_viewable(client):
    login_m = client.post("/api/v1/auth/login", json={"email_or_phone": "manager@soobin.vn", "password": "Password123@"})
    token_m = login_m.json()["session_token"]
    headers = {"Authorization": f"Bearer {token_m}"}

    res = client.get("/api/v1/inventory/receipts", headers=headers)
    assert res.status_code == 200
    receipts = res.json()
    assert len(receipts) >= 1
    for r in receipts:
        assert r["code"].startswith("PN-")
        assert len(r["items"]) > 0
