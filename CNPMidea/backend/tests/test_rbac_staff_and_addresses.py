import uuid
from app.core.database import SessionLocal
from app.models.entities import UserRole

def _admin_headers(client):
    res = client.post("/api/v1/auth/login", json={"email_or_phone": "admin@soobin.vn", "password": "Password123@"})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['session_token']}"}

def _customer_headers(client):
    res = client.post("/api/v1/auth/login", json={"email_or_phone": "customer@soobin.vn", "password": "Password123@"})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['session_token']}"}

def test_admin_create_and_update_staff_account(client):
    headers = _admin_headers(client)
    roles_res = client.get("/api/v1/admin/roles", headers=headers)
    assert roles_res.status_code == 200
    roles = roles_res.json()
    sales_role = next((r for r in roles if r["code"] == "SALES"), roles[0])

    unique_suffix = uuid.uuid4().hex[:6]
    email = f"sales_{unique_suffix}@soobin.vn"
    phone = f"098{uuid.uuid4().int % 10000000:07d}"

    create_res = client.post("/api/v1/admin/users", headers=headers, json={
        "email": email,
        "full_name": "Nhân Viên Bán Hàng Mới",
        "password": "Password123@",
        "phone": phone,
        "role_id": sales_role["id"]
    })
    assert create_res.status_code == 201
    user_id = create_res.json()["user"]["id"]

    # Update staff full_name
    upd_res = client.put(f"/api/v1/admin/users/{user_id}", headers=headers, json={
        "full_name": "Nhân Viên Bán Hàng Senior"
    })
    assert upd_res.status_code == 200
    assert upd_res.json()["user"]["full_name"] == "Nhân Viên Bán Hàng Senior"

    # Login with newly created staff account
    login_staff = client.post("/api/v1/auth/login", json={"email_or_phone": email, "password": "Password123@"})
    assert login_staff.status_code == 200
    assert login_staff.json()["user"]["is_email_verified"] is True

def test_admin_create_and_update_custom_role_and_protect_system_role(client):
    headers = _admin_headers(client)
    perms_res = client.get("/api/v1/admin/permissions", headers=headers)
    assert perms_res.status_code == 200
    perms = perms_res.json()
    perm_ids = [p["id"] for p in perms[:2]] if perms else []

    role_code = f"SUPPORT_{uuid.uuid4().hex[:4].upper()}"
    create_res = client.post("/api/v1/admin/roles", headers=headers, json={
        "code": role_code,
        "name": "Chăm Sóc Khách Hàng",
        "permission_ids": perm_ids
    })
    assert create_res.status_code == 201
    role_id = create_res.json()["role"]["id"]

    # Update custom role
    upd_res = client.put(f"/api/v1/admin/roles/{role_id}", headers=headers, json={
        "name": "CSKH Cao Cấp",
        "is_active": True
    })
    assert upd_res.status_code == 200
    assert upd_res.json()["role"]["name"] == "CSKH Cao Cấp"

    # Attempt to deactivate system role (ADMIN) must be blocked
    roles = client.get("/api/v1/admin/roles", headers=headers).json()
    admin_role = next(r for r in roles if r["code"] == "ADMIN")
    block_res = client.put(f"/api/v1/admin/roles/{admin_role['id']}", headers=headers, json={
        "is_active": False
    })
    assert block_res.status_code == 400

def test_customer_address_book_crud(client):
    headers = _customer_headers(client)

    # 1. Create address
    add_res = client.post("/api/v1/auth/addresses", headers=headers, json={
        "recipient_name": "Nguyễn Văn A",
        "recipient_phone": "0912345678",
        "address_line": "123 Nguyễn Huệ, Quận 1, TP.HCM",
        "is_default": True
    })
    assert add_res.status_code == 201
    addr_id = add_res.json()["address"]["id"]

    # 2. List addresses
    list_res = client.get("/api/v1/auth/addresses", headers=headers)
    assert list_res.status_code == 200
    addrs = list_res.json()
    assert any(a["id"] == addr_id and a["is_default"] is True for a in addrs)

    # 3. Update address
    upd_res = client.put(f"/api/v1/auth/addresses/{addr_id}", headers=headers, json={
        "recipient_name": "Nguyễn Văn A (Đã sửa)",
        "recipient_phone": "0912345678",
        "address_line": "456 Lê Lợi, Quận 1, TP.HCM",
        "is_default": True
    })
    assert upd_res.status_code == 200

    # 4. Delete address
    del_res = client.delete(f"/api/v1/auth/addresses/{addr_id}", headers=headers)
    assert del_res.status_code == 200

