import pytest

def test_catalog_categories_and_products(client):
    cat_res = client.get("/api/v1/catalog/categories")
    assert cat_res.status_code == 200
    cats = cat_res.json()
    assert len(cats) >= 4

    prod_res = client.get("/api/v1/catalog/products")
    assert prod_res.status_code == 200
    prods = prod_res.json()
    assert len(prods) >= 6

def test_catalog_filter_by_audience(client):
    res_nu = client.get("/api/v1/catalog/products?audience=Nữ")
    assert res_nu.status_code == 200
    for p in res_nu.json():
        assert p["target_audience"] == "Nữ"

    res_nam = client.get("/api/v1/catalog/products?audience=Nam")
    assert res_nam.status_code == 200
    for p in res_nam.json():
        assert p["target_audience"] == "Nam"

def test_catalog_outlet_on_sale(client):
    res = client.get("/api/v1/catalog/outlet")
    assert res.status_code == 200
    outlet_prods = res.json()
    # Product 1 is linked to SUMMER30 promo
    assert len(outlet_prods) >= 1
    assert any("Elegance" in p["name"] for p in outlet_prods)

def test_cart_operations(client):
    # Login customer
    login_res = client.post("/api/v1/auth/login", json={
        "email_or_phone": "customer@soobin.vn",
        "password": "Password123@"
    })
    token = login_res.json()["session_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Add item
    add_res = client.post("/api/v1/cart/items", headers=headers, json={"variant_id": 1, "quantity": 2})
    assert add_res.status_code == 200
    cart = add_res.json()
    assert cart["total_items"] >= 2

    # Update item
    update_res = client.put("/api/v1/cart/items/1", headers=headers, json={"quantity": 3})
    assert update_res.status_code == 200
    item = next(i for i in update_res.json()["items"] if i["variant_id"] == 1)
    assert item["quantity"] == 3

    # Delete item
    del_res = client.delete("/api/v1/cart/items/1", headers=headers)
    assert del_res.status_code == 200
    assert not any(i["variant_id"] == 1 for i in del_res.json()["items"])

def test_ac_br_prd_cart_guest_merge_and_stock_adjustment(client):
    """AC-BR-PRD-CART-02/03: Gộp giỏ khách vãng lai sau đăng nhập; điều chỉnh nếu vượt tồn."""
    # Login customer
    login_res = client.post("/api/v1/auth/login", json={
        "email_or_phone": "customer@soobin.vn",
        "password": "Password123@"
    })
    token = login_res.json()["session_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Clear current cart
    client.delete("/api/v1/cart/items/1", headers=headers)

    # Merge guest cart with an excessive quantity (e.g., 9999 units of variant 6 which only has 10)
    merge_res = client.post("/api/v1/cart/merge", headers=headers, json={
        "items": [
            {"variant_id": 6, "quantity": 9999}
        ]
    })
    assert merge_res.status_code == 200
    merged = merge_res.json()
    item = next(i for i in merged["items"] if i["variant_id"] == 6)
    # Must be adjusted down to available quantity!
    assert item["quantity"] <= 10
    assert len(merged["adjustments"]) > 0
    assert "tối đa" in merged["adjustments"][0]
