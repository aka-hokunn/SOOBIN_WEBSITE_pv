import pytest
import concurrent.futures
from app.services.order_service import OrderService
from app.core.database import SessionLocal
from app.models.entities import ProductionInventory

def test_order_creation_and_stock_deduction(client):
    login_res = client.post("/api/v1/auth/login", json={
        "email_or_phone": "customer@soobin.vn",
        "password": "Password123@"
    })
    token = login_res.json()["session_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Variant 1 stock before order
    prod_res = client.get("/api/v1/catalog/products/1")
    v1 = next(v for v in prod_res.json()["variants"] if v["id"] == 1)
    initial_stock = v1["available_quantity"]

    # Place order
    order_res = client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "recipient_name": "Nguyễn Minh Anh",
            "recipient_phone": "0903456789",
            "shipping_address": "45 Lê Duẩn, Q1, TP.HCM",
            "payment_method": "COD",
            "guest_items": [{"variant_id": 1, "quantity": 1}]
        }
    )
    assert order_res.status_code == 200, order_res.text
    order_data = order_res.json()
    order_id = order_data["order_id"]

    # Verify stock deducted immediately (PRD Section 8)
    prod_res_after = client.get("/api/v1/catalog/products/1")
    v1_after = next(v for v in prod_res_after.json()["variants"] if v["id"] == 1)
    assert v1_after["available_quantity"] == initial_stock - 1

    # Cancel order -> stock must be restored exactly once (AC-INV-06)
    cancel_res = client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers=headers,
        json={"reason": "Khách hàng đổi ý"}
    )
    assert cancel_res.status_code == 200

    prod_res_restored = client.get("/api/v1/catalog/products/1")
    v1_restored = next(v for v in prod_res_restored.json()["variants"] if v["id"] == 1)
    assert v1_restored["available_quantity"] == initial_stock

def test_ac_auth_01_customer_cannot_view_or_cancel_other_order(client):
    """AC-AUTH-01: Khách không đọc hoặc hủy đơn thuộc tài khoản khác bằng cách đổi ID."""
    # 1. Customer 1 places an order
    login1 = client.post("/api/v1/auth/login", json={
        "email_or_phone": "customer@soobin.vn",
        "password": "Password123@"
    })
    token1 = login1.json()["session_token"]
    ord_res = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {token1}"},
        json={
            "recipient_name": "Khách 1",
            "recipient_phone": "0903456789",
            "shipping_address": "Địa chỉ 1",
            "payment_method": "COD",
            "guest_items": [{"variant_id": 2, "quantity": 1}]
        }
    )
    order_id = ord_res.json()["order_id"]

    # 2. Register Customer 2
    import uuid
    email2 = f"other_{uuid.uuid4().hex[:6]}@example.com"
    client.post("/api/v1/auth/register", json={
        "email": email2,
        "full_name": "Khách 2",
        "password": "Password123@"
    })
    login2 = client.post("/api/v1/auth/login", json={"email_or_phone": email2, "password": "Password123@"})
    token2 = login2.json()["session_token"]

    # 3. Customer 2 tries to read Customer 1's order
    view_res = client.get(f"/api/v1/orders/{order_id}", headers={"Authorization": f"Bearer {token2}"})
    assert view_res.status_code == 403

    # 4. Customer 2 tries to cancel Customer 1's order
    cancel_res = client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers={"Authorization": f"Bearer {token2}"},
        json={"reason": "Cố tình hủy trộm"}
    )
    assert cancel_res.status_code == 403

def test_ac_chk_01_e2e_06_concurrency_race_condition():
    """
    E2E-06 & AC-CHK-01: Hai khách đồng thời mua biến thể còn một đơn vị
    -> Tối đa một đơn được tạo thành công; tồn không âm!
    """
    # 1. Set variant 8 available quantity to exactly 1
    db = SessionLocal()
    inv = db.query(ProductionInventory).filter(ProductionInventory.variant_id == 8).first()
    inv.available_quantity = 1
    inv.inventory_value = 220000.0
    db.commit()
    db.close()

    successes = []
    failures = []

    def place_order(user_id):
        session = SessionLocal()
        try:
            svc = OrderService(session)
            res = svc.create_order(
                account_id=user_id,
                recipient_name="Khách Hàng Đua Tồn",
                recipient_phone="0901112223",
                shipping_address="Hồ Chí Minh",
                payment_method="COD",
                guest_items=[{"variant_id": 8, "quantity": 1}]
            )
            successes.append(res)
        except Exception as e:
            failures.append(str(e))
        finally:
            session.close()

    # Run 2 concurrent order placement threads simultaneously
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(place_order, 3)
        f2 = executor.submit(place_order, 3)
        concurrent.futures.wait([f1, f2])

    # Exactly 1 must succeed, 1 must fail due to stock depletion
    assert len(successes) == 1, f"Expected 1 success, got {len(successes)}"
    assert len(failures) == 1, f"Expected 1 failure, got {len(failures)}"

    # Check database stock: must be exactly 0, never negative!
    check_db = SessionLocal()
    final_inv = check_db.query(ProductionInventory).filter(ProductionInventory.variant_id == 8).first()
    assert final_inv.available_quantity == 0
    check_db.close()
