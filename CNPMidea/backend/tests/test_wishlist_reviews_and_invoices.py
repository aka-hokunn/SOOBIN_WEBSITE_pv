def _customer_headers(client):
    res = client.post("/api/v1/auth/login", json={"email_or_phone": "customer@soobin.vn", "password": "Password123@"})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['session_token']}"}

def _manager_headers(client):
    res = client.post("/api/v1/auth/login", json={"email_or_phone": "manager@soobin.vn", "password": "Password123@"})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['session_token']}"}

def test_wishlist_toggle_and_discount_notification(client):
    headers = _customer_headers(client)

    # Ensure product 1 is added to wishlist
    w_list = client.get("/api/v1/cart/wishlist", headers=headers).json()
    if any(item["product_id"] == 1 for item in w_list):
        client.delete("/api/v1/cart/wishlist/1", headers=headers)

    # Toggle ON
    toggle_on = client.post("/api/v1/cart/wishlist/toggle/1", headers=headers)
    assert toggle_on.status_code == 200
    assert toggle_on.json()["is_in_wishlist"] is True

    # Check wishlist list and discount check
    w_after = client.get("/api/v1/cart/wishlist", headers=headers)
    assert w_after.status_code == 200
    assert any(item["product_id"] == 1 for item in w_after.json())

    disc_check = client.get("/api/v1/cart/wishlist/check-discounts", headers=headers)
    assert disc_check.status_code == 200
    assert "discounted_count" in disc_check.json()

    # Toggle OFF
    toggle_off = client.post("/api/v1/cart/wishlist/toggle/1", headers=headers)
    assert toggle_off.status_code == 200
    assert toggle_off.json()["is_in_wishlist"] is False

def test_reviews_and_invoices_full_lifecycle(client):
    cust_headers = _customer_headers(client)
    mgr_headers = _manager_headers(client)

    # 1. Create a COD order for variant 1 (belongs to product 1)
    order_res = client.post("/api/v1/orders", headers=cust_headers, json={
        "recipient_name": "Khách Hàng Review",
        "recipient_phone": "0903456789",
        "shipping_address": "88 Đồng Khởi, Quận 1, TP.HCM",
        "payment_method": "COD",
        "guest_items": [{"variant_id": 1, "quantity": 1}]
    })
    assert order_res.status_code == 200
    order_id = order_res.json()["order_id"]

    # 2. Attempt to review BEFORE order is delivered -> must be rejected (400)
    early_review = client.post("/api/v1/catalog/products/1/reviews", headers=cust_headers, json={
        "order_id": order_id,
        "rating": 5,
        "content": "Thử đánh giá khi đơn chưa giao"
    })
    assert early_review.status_code == 400

    # 3. Manager confirms order -> GHTK picks up -> GHTK delivers
    conf_res = client.post(f"/api/v1/orders/{order_id}/confirm", headers=mgr_headers)
    assert conf_res.status_code == 200
    tracking_code = conf_res.json()["tracking_code"]

    client.post("/api/v1/mock/shipping/webhook", json={
        "carrier": "GHTK",
        "carrier_request_key": f"PICK-{tracking_code}",
        "tracking_code": tracking_code,
        "delivery_status": "IN_TRANSIT"
    })
    deliv_res = client.post("/api/v1/mock/shipping/webhook", json={
        "carrier": "GHTK",
        "carrier_request_key": f"DELIV-{tracking_code}",
        "tracking_code": tracking_code,
        "delivery_status": "DELIVERED"
    })
    assert deliv_res.status_code == 200

    ord_detail = client.get(f"/api/v1/orders/{order_id}", headers=cust_headers)
    assert ord_detail.status_code == 200
    assert ord_detail.json()["status"] == "Đã giao"
    assert ord_detail.json()["invoice"] is not None
    invoice_code = ord_detail.json()["invoice"]["code"]

    # 4. Submit review AFTER order is delivered -> must succeed (201)
    ok_review = client.post("/api/v1/catalog/products/1/reviews", headers=cust_headers, json={
        "order_id": order_id,
        "rating": 5,
        "content": "Đồ bơi chất vải cực đẹp, co giãn 4 chiều rất thoải mái!"
    })
    assert ok_review.status_code == 201
    review_id = ok_review.json()["review_id"]

    # 5. Verify review appears in product reviews
    prod_reviews = client.get("/api/v1/catalog/products/1/reviews")
    assert prod_reviews.status_code == 200
    assert prod_reviews.json()["review_count"] >= 1

    # 6. Manager moderates review (hide & re-approve)
    mod_hide = client.put(f"/api/v1/catalog/reviews/{review_id}/moderate", headers=mgr_headers, json={"status": "HIDDEN"})
    assert mod_hide.status_code == 200
    mod_app = client.put(f"/api/v1/catalog/reviews/{review_id}/moderate", headers=mgr_headers, json={"status": "APPROVED"})
    assert mod_app.status_code == 200

    # 7. Verify Invoice endpoints
    inv_list = client.get("/api/v1/orders/invoices", headers=cust_headers)
    assert inv_list.status_code == 200
    assert any(inv["code"] == invoice_code for inv in inv_list.json())

    inv_detail = client.get(f"/api/v1/orders/invoices/{invoice_code}", headers=cust_headers)
    assert inv_detail.status_code == 200
    assert inv_detail.json()["code"] == invoice_code
    assert len(inv_detail.json()["items"]) == 1
