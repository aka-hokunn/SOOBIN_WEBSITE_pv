from datetime import datetime, timedelta, timezone
from app.core.database import SessionLocal
from app.models.entities import ProductionCartItem

def test_ai_size_advisor_explicit_and_natural_language(client):
    # 1. Explicit measurements for Female
    res_f = client.post("/api/v1/catalog/ai-advisor", json={
        "message": "Tư vấn size giúp mình với",
        "height_cm": 160,
        "weight_kg": 50,
        "bust_cm": 84,
        "gender": "Nữ"
    })
    assert res_f.status_code == 200
    data_f = res_f.json()
    assert data_f["recommended_size"] == "M"
    assert len(data_f["suggested_products"]) > 0

    # 2. Natural language extraction for Male
    res_m = client.post("/api/v1/catalog/ai-advisor", json={
        "message": "Mình là nam cao 1m75 nặng 72kg muốn tìm đồ bơi nam"
    })
    assert res_m.status_code == 200
    data_m = res_m.json()
    assert data_m["recommended_size"] == "L"
    assert "Size L" in data_m["reply"]
    assert len(data_m["suggested_products"]) > 0

def test_abandoned_cart_reminder_over_24h(client):
    login = client.post("/api/v1/auth/login", json={"email_or_phone": "customer@soobin.vn", "password": "Password123@"})
    token = login.json()["session_token"]
    user_id = login.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    # Add an item to cart
    add_res = client.post("/api/v1/cart/items", headers=headers, json={"variant_id": 1, "quantity": 1})
    assert add_res.status_code == 200

    # Backdate updated_at to 30 hours ago in DB
    db = SessionLocal()
    ci = db.query(ProductionCartItem).filter(
        ProductionCartItem.account_id == user_id,
        ProductionCartItem.variant_id == 1
    ).first()
    assert ci is not None
    ci.updated_at = datetime.now(timezone.utc) - timedelta(hours=30)
    db.commit()
    db.close()

    # Trigger reminder job
    rem_res = client.post("/api/v1/cart/trigger-reminders?older_than_hours=24")
    assert rem_res.status_code == 200
    rem_data = rem_res.json()
    assert rem_data["notified_count"] >= 1
    assert any(u["account_id"] == user_id for u in rem_data["notified_users"])

