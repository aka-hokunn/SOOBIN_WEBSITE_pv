import pytest
import uuid

def test_full_vietqr_flow_to_delivery_and_invoice(client):
    # 1. Login customer
    login_c = client.post("/api/v1/auth/login", json={"email_or_phone": "customer@soobin.vn", "password": "Password123@"})
    token_c = login_c.json()["session_token"]

    # 2. Login manager
    login_m = client.post("/api/v1/auth/login", json={"email_or_phone": "manager@soobin.vn", "password": "Password123@"})
    token_m = login_m.json()["session_token"]

    # 3. Customer places VietQR order
    order_res = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {token_c}"},
        json={
            "recipient_name": "Nguyễn Minh Anh",
            "recipient_phone": "0903456789",
            "shipping_address": "45 Lê Duẩn, Q1, TP.HCM",
            "payment_method": "VietQR",
            "guest_items": [{"variant_id": 3, "quantity": 1}]
        }
    )
    assert order_res.status_code == 200
    order_data = order_res.json()
    order_id = order_data["order_id"]
    order_code = order_data["order_code"]
    total_amount = order_data["total_amount"]

    # 4. Manager cannot confirm unpaid VietQR order yet
    conf_unpaid = client.post(f"/api/v1/orders/{order_id}/confirm", headers={"Authorization": f"Bearer {token_m}"})
    assert conf_unpaid.status_code == 400
    assert "chưa được thanh toán" in conf_unpaid.json()["detail"]

    # 5. VietQR payment simulation (bank transfer received)
    pay_res = client.post("/api/v1/mock/payment/notify", json={
        "order_code": order_code,
        "transfer_amount": total_amount,
        "external_transaction_id": f"TXN-{uuid.uuid4().hex[:8]}"
    })
    assert pay_res.status_code == 200
    assert pay_res.json()["payment_status"] == "PAID"

    # 6. Manager confirms order -> creates shipment
    conf_paid = client.post(f"/api/v1/orders/{order_id}/confirm", headers={"Authorization": f"Bearer {token_m}"})
    assert conf_paid.status_code == 200
    tracking_code = conf_paid.json()["tracking_code"]
    assert tracking_code is not None

    # 7. GHTK webhook: IN_TRANSIT
    wh_transit = client.post("/api/v1/mock/shipping/webhook", json={
        "carrier": "GHTK",
        "carrier_request_key": f"REQ-{uuid.uuid4().hex[:6]}",
        "tracking_code": tracking_code,
        "delivery_status": "IN_TRANSIT"
    })
    assert wh_transit.status_code == 200

    # Verify status is 'Đang vận chuyển'
    ord_check = client.get(f"/api/v1/orders/{order_id}", headers={"Authorization": f"Bearer {token_m}"})
    assert ord_check.json()["status"] == "Đang vận chuyển"

    # 8. GHTK webhook: DELIVERED -> must issue invoice!
    wh_deliv = client.post("/api/v1/mock/shipping/webhook", json={
        "carrier": "GHTK",
        "carrier_request_key": f"REQ-{uuid.uuid4().hex[:6]}",
        "tracking_code": tracking_code,
        "delivery_status": "DELIVERED"
    })
    assert wh_deliv.status_code == 200

    # Verify order is 'Đã giao' and has invoice
    ord_check_deliv = client.get(f"/api/v1/orders/{order_id}", headers={"Authorization": f"Bearer {token_m}"})
    assert ord_check_deliv.json()["status"] == "Đã giao"
    assert ord_check_deliv.json()["invoice"] is not None

    # 9. Webhook Idempotency test (E2E-07): repeating duplicate webhook does not duplicate actions
    wh_repeat = client.post("/api/v1/mock/shipping/webhook", json={
        "carrier": "GHTK",
        "carrier_request_key": f"REQ-{uuid.uuid4().hex[:6]}",
        "tracking_code": tracking_code,
        "delivery_status": "DELIVERED"
    })
    assert wh_repeat.status_code == 200
    assert wh_repeat.json()["status"] in ("SUCCESS", "ALREADY_PROCESSED")

def test_paid_vietqr_delivery_failed_triggers_refund_pending(client):
    """
    PRD Section 8 & 9: VietQR đã trả tiền, giao thất bại -> Chuyển 'Chờ hoàn tiền',
    không cộng kho. Quản lý hoàn tiền ngoài hệ thống -> Đã hoàn tiền.
    """
    login_c = client.post("/api/v1/auth/login", json={"email_or_phone": "customer@soobin.vn", "password": "Password123@"})
    token_c = login_c.json()["session_token"]
    login_m = client.post("/api/v1/auth/login", json={"email_or_phone": "manager@soobin.vn", "password": "Password123@"})
    token_m = login_m.json()["session_token"]

    # 1. Place VietQR order
    ord_res = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {token_c}"},
        json={
            "recipient_name": "Khách Hoàn Tiền",
            "recipient_phone": "0903456789",
            "shipping_address": "Quận 1, TP.HCM",
            "payment_method": "VietQR",
            "guest_items": [{"variant_id": 4, "quantity": 1}]
        }
    )
    order_id = ord_res.json()["order_id"]
    order_code = ord_res.json()["order_code"]
    total_amount = ord_res.json()["total_amount"]

    # 2. Pay VietQR
    client.post("/api/v1/mock/payment/notify", json={
        "order_code": order_code,
        "transfer_amount": total_amount,
        "external_transaction_id": f"TXN-{uuid.uuid4().hex[:8]}"
    })

    # 3. Manager confirms order
    conf = client.post(f"/api/v1/orders/{order_id}/confirm", headers={"Authorization": f"Bearer {token_m}"})
    tracking_code = conf.json()["tracking_code"]

    # 4. GHTK takes parcel
    client.post("/api/v1/mock/shipping/webhook", json={
        "carrier": "GHTK",
        "carrier_request_key": f"REQ-{uuid.uuid4().hex[:6]}",
        "tracking_code": tracking_code,
        "delivery_status": "IN_TRANSIT"
    })

    # 5. GHTK reports FAILED
    wh_fail = client.post("/api/v1/mock/shipping/webhook", json={
        "carrier": "GHTK",
        "carrier_request_key": f"REQ-{uuid.uuid4().hex[:6]}",
        "tracking_code": tracking_code,
        "delivery_status": "FAILED",
        "reason": "Khách từ chối nhận hàng"
    })
    assert wh_fail.status_code == 200

    # 6. Verify order is in 'Chờ hoàn tiền'
    chk = client.get(f"/api/v1/orders/{order_id}", headers={"Authorization": f"Bearer {token_m}"})
    assert chk.json()["status"] == "Chờ hoàn tiền"
    # Refund amount = subtotal - discount (NO ship fee refund per PRD Section 10!)
    assert chk.json()["refund_amount"] == chk.json()["subtotal"] - chk.json()["discount_amount"]

    # 7. Manager marks manual refund completed
    refund_res = client.post(
        f"/api/v1/orders/{order_id}/refund",
        headers={"Authorization": f"Bearer {token_m}"},
        json={"note": "Đã chuyển khoản hoàn tiền cho khách qua STK MBBank"}
    )
    assert refund_res.status_code == 200
    assert refund_res.json()["status"] == "Đã hoàn tiền"
