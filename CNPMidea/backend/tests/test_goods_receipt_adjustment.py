from app.core.database import SessionLocal
from app.models.entities import ProductionInventory

def _manager_headers(client):
    res = client.post("/api/v1/auth/login", json={"email_or_phone": "manager@soobin.vn", "password": "Password123@"})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['session_token']}"}

def test_ac_inv_03_block_direct_modify_or_delete_confirmed_receipt(client):
    headers = _manager_headers(client)
    receipts = client.get("/api/v1/inventory/receipts", headers=headers).json()
    assert len(receipts) > 0
    receipt_id = receipts[0]["id"]

    # Direct PUT and DELETE must be blocked
    put_res = client.put(f"/api/v1/inventory/receipts/{receipt_id}", headers=headers)
    assert put_res.status_code == 400

    del_res = client.delete(f"/api/v1/inventory/receipts/{receipt_id}", headers=headers)
    assert del_res.status_code == 400

def test_goods_receipt_adjustment_flow_and_prevent_negative_stock(client):
    headers = _manager_headers(client)

    db = SessionLocal()
    inv = db.query(ProductionInventory).filter(ProductionInventory.variant_id == 16).first()
    if inv:
        inv.available_quantity = 0
        inv.inventory_value = 0.0
        db.commit()
    db.close()

    # 1. Confirm a new receipt of 10 units @ 150,000đ for variant 16
    confirm_res = client.post("/api/v1/inventory/receipts/confirm", headers=headers, json={
        "supplier_id": 1,
        "note": "Phiếu nhập kiểm thử điều chỉnh",
        "items": [{"variant_id": 16, "quantity": 10, "unit_cost": 150000.0}]
    })
    assert confirm_res.status_code == 200
    receipt_id = confirm_res.json()["receipt"]["id"]

    # Get receipt detail to obtain item_id
    detail_res = client.get(f"/api/v1/inventory/receipts/{receipt_id}", headers=headers)
    assert detail_res.status_code == 200
    item_id = detail_res.json()["items"][0]["id"]

    # 2. Adjust item quantity from 10 -> 15 (+5 units)
    adj_res = client.post(f"/api/v1/inventory/receipts/{receipt_id}/adjust", headers=headers, json={
        "note": "Kiểm đếm thực tế thừa 5 chiếc",
        "adjustments": [
            {"item_id": item_id, "new_quantity": 15, "reason": "Nhà cung cấp giao dư 5 chiếc"}
        ]
    })
    assert adj_res.status_code == 200

    db = SessionLocal()
    inv_after = db.query(ProductionInventory).filter(ProductionInventory.variant_id == 16).first()
    assert inv_after.available_quantity == 15
    assert float(inv_after.inventory_value) == 15 * 150000.0
    # Simulate that 12 units were sold so only 3 remain in stock
    inv_after.available_quantity = 3
    db.commit()
    db.close()

    # 3. Attempt to adjust receipt quantity from 15 -> 5 (-10 units), which exceeds remaining stock (3) -> must fail!
    fail_adj = client.post(f"/api/v1/inventory/receipts/{receipt_id}/adjust", headers=headers, json={
        "note": "Thử giảm quá tồn kho",
        "adjustments": [
            {"item_id": item_id, "new_quantity": 5, "reason": "Test âm kho"}
        ]
    })
    assert fail_adj.status_code == 400

    # Restore stock to 15
    db = SessionLocal()
    inv_restore = db.query(ProductionInventory).filter(ProductionInventory.variant_id == 16).first()
    inv_restore.available_quantity = 15
    db.commit()
    db.close()

    # 4. Verify movements log includes RECEIPT_ADJUSTMENT
    mov_res = client.get("/api/v1/inventory/movements", headers=headers)
    assert mov_res.status_code == 200
    movements = mov_res.json()
    assert any(m["movement_type"] == "RECEIPT_ADJUSTMENT" and m["variant_id"] == 16 for m in movements)

