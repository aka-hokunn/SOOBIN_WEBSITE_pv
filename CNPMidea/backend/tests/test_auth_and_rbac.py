import pytest
import uuid

def test_auth_login_success(client):
    res = client.post("/api/v1/auth/login", json={
        "email_or_phone": "customer@soobin.vn",
        "password": "Password123@"
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert "session_token" in data
    assert data["user"]["email"] == "customer@soobin.vn"
    assert data["user"]["is_email_verified"] is True

def test_auth_login_invalid_password(client):
    res = client.post("/api/v1/auth/login", json={
        "email_or_phone": "customer@soobin.vn",
        "password": "WrongPassword@"
    })
    assert res.status_code == 401

def test_auth_register_and_verify(client):
    unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    reg_res = client.post("/api/v1/auth/register", json={
        "email": unique_email,
        "full_name": "Test User",
        "password": "Password123@",
        "phone": f"09{uuid.uuid4().int % 100000000:08d}"
    })
    assert reg_res.status_code == 200, reg_res.text
    token = reg_res.json()["verification_token"]
    assert token is not None

    # Verify email
    ver_res = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert ver_res.status_code == 200
    assert "thành công" in ver_res.json()["message"]

def test_ac_auth_05_unverified_email_cannot_place_order(client):
    """AC-AUTH-05: Tài khoản chưa xác minh email không đặt được đơn."""
    # Login as unverified customer customer2@soobin.vn
    login_res = client.post("/api/v1/auth/login", json={
        "email_or_phone": "customer2@soobin.vn",
        "password": "Password123@"
    })
    assert login_res.status_code == 200
    token = login_res.json()["session_token"]

    # Attempt to place order
    order_res = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "recipient_name": "Trần Bảo Ngọc",
            "recipient_phone": "0904567890",
            "shipping_address": "Quận 3, TP.HCM",
            "payment_method": "COD",
            "guest_items": [{"variant_id": 1, "quantity": 1}]
        }
    )
    assert order_res.status_code == 400
    assert "chưa xác minh email" in order_res.json()["detail"]

def test_ac_auth_02_locked_account_takes_immediate_effect(client):
    """AC-AUTH-02: Khóa tài khoản có hiệu lực với yêu cầu tiếp theo, không cần chờ phiên hết hạn."""
    # 1. Login as customer
    login_res = client.post("/api/v1/auth/login", json={
        "email_or_phone": "customer@soobin.vn",
        "password": "Password123@"
    })
    token = login_res.json()["session_token"]
    user_id = login_res.json()["user"]["id"]

    # 2. Login as admin
    admin_login = client.post("/api/v1/auth/login", json={
        "email_or_phone": "admin@soobin.vn",
        "password": "Password123@"
    })
    admin_token = admin_login.json()["session_token"]

    # 3. Admin locks customer account
    lock_res = client.post(
        f"/api/v1/admin/users/{user_id}/lock",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert lock_res.status_code == 200

    # 4. Customer attempts to access with existing session token -> should be rejected immediately!
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 401

    # 5. Unlock account
    unlock_res = client.post(
        f"/api/v1/admin/users/{user_id}/unlock",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert unlock_res.status_code == 200

def test_protect_last_active_admin(client):
    """Bảo vệ tài khoản Quản trị viên hoạt động cuối cùng của hệ thống."""
    admin_login = client.post("/api/v1/auth/login", json={
        "email_or_phone": "admin@soobin.vn",
        "password": "Password123@"
    })
    admin_token = admin_login.json()["session_token"]
    admin_id = admin_login.json()["user"]["id"]

    # Attempt to lock self when only 1 active admin
    lock_res = client.post(
        f"/api/v1/admin/users/{admin_id}/lock",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert lock_res.status_code == 400
    assert "Quản trị viên" in lock_res.json()["detail"]
