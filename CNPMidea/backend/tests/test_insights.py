import uuid

from app.core.audit_log import describe_action, should_audit
from app.models.entities import ProductionAuditLog, ProductionPromotion
from app.services.insights_service import (
    FORECAST_STATUS_RANK,
    classify_segment,
    compute_forecast_row,
)


def _login(client, email):
    res = client.post("/api/v1/auth/login", json={"email_or_phone": email, "password": "Password123@"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['session_token']}"}


READ_ENDPOINTS = (
    "/api/v1/insights/kpis",
    "/api/v1/insights/restock-forecast",
    "/api/v1/insights/rfm",
    "/api/v1/insights/wheel-performance",
    "/api/v1/insights/audit-logs",
)


def test_insights_rbac_and_portal_wiring(client):
    adm = _login(client, "admin@soobin.vn")
    mgr = _login(client, "manager@soobin.vn")
    cust = _login(client, "customer@soobin.vn")
    sales = _login(client, "sales@soobin.vn")

    for path in READ_ENDPOINTS:
        for headers in (adm, mgr):
            res = client.get(path, headers=headers)
            assert res.status_code == 200, (path, res.text)
        assert client.get(path, headers=cust).status_code == 403
        assert client.get(path, headers=sales).status_code == 403
    assert client.post("/api/v1/insights/rfm/vouchers", headers=cust, json={"account_ids": [1]}).status_code == 403

    kpis = client.get("/api/v1/insights/kpis", headers=mgr).json()
    assert {"revenue_today", "orders_today", "low_stock_variants", "customers_at_risk"} <= set(kpis)

    rfm = client.get("/api/v1/insights/rfm", headers=adm).json()
    assert len(rfm["segments"]) == 7
    assert sum(s["count"] for s in rfm["segments"]) == rfm["total_customers"]

    wheel = client.get("/api/v1/insights/wheel-performance", headers=adm).json()
    assert len(wheel["daily"]) == 14
    assert {"total_spins", "vouchers_issued", "vouchers_used", "usage_rate_percent", "revenue"} <= set(wheel["totals"])

    for portal in ("/admin", "/manager"):
        page = client.get(portal).text
        assert 'id="insightsAdminRoot"' in page and "insights-admin.js" in page and "switchTab('insights')" in page
    assert client.get("/static/js/insights-admin.js").status_code == 200
    assert client.get("/static/css/insights.css").status_code == 200


def test_restock_forecast_math_and_sorting(client):
    # 30 units in 30 days → 1/day; 10 on hand → 10 days left; cover 30 + safety 7 − 10 = 27
    row = compute_forecast_row(available=10, units_sold=30, window_days=30)
    assert row["daily_velocity"] == 1.0 and row["days_to_stockout"] == 10.0
    assert row["suggested_qty"] == 27 and row["status"] == "WARNING"

    row = compute_forecast_row(available=3, units_sold=60, window_days=30)  # 2/day → 1.5 days
    assert row["status"] == "CRITICAL" and row["suggested_qty"] == 71

    row = compute_forecast_row(available=0, units_sold=15, window_days=30)  # out of stock
    assert row["status"] == "CRITICAL" and row["days_to_stockout"] == 0 and row["suggested_qty"] == 19

    row = compute_forecast_row(available=500, units_sold=30, window_days=30)
    assert row["status"] == "OK" and row["suggested_qty"] == 0

    row = compute_forecast_row(available=8, units_sold=0, window_days=30)
    assert row["status"] == "NO_SALES" and row["days_to_stockout"] is None and row["suggested_qty"] == 0

    mgr = _login(client, "manager@soobin.vn")
    data = client.get("/api/v1/insights/restock-forecast?days=30", headers=mgr).json()
    ranks = [FORECAST_STATUS_RANK[i["status"]] for i in data["items"]]
    assert ranks == sorted(ranks)
    for item in data["items"]:
        assert item["suggested_qty"] >= 0
        expected = compute_forecast_row(item["available_quantity"], item["units_sold"], 30)
        assert item["status"] == expected["status"] and item["suggested_qty"] == expected["suggested_qty"]


def test_rfm_segments_and_personal_care_vouchers(client, db_session):
    assert classify_segment(5, 5, 5) == "CHAMPIONS"
    assert classify_segment(5, 1, 1) == "NEW"
    assert classify_segment(3, 3, 2) == "LOYAL"
    assert classify_segment(3, 2, 1) == "POTENTIAL"
    assert classify_segment(2, 4, 2) == "AT_RISK"
    assert classify_segment(2, 1, 1) == "NEED_ATTENTION"
    assert classify_segment(1, 1, 1) == "HIBERNATING"

    mgr = _login(client, "manager@soobin.vn")
    cust = _login(client, "customer@soobin.vn")
    cust_id = client.get("/api/v1/auth/me", headers=cust).json()["id"]
    mgr_id = client.get("/api/v1/auth/me", headers=mgr).json()["id"]

    # Staff accounts can never receive customer care vouchers
    res = client.post("/api/v1/insights/rfm/vouchers", headers=mgr, json={"account_ids": [mgr_id]})
    assert res.status_code == 400
    assert client.post("/api/v1/insights/rfm/vouchers", headers=mgr, json={"account_ids": []}).status_code == 400
    assert client.post("/api/v1/insights/rfm/vouchers", headers=mgr,
                       json={"account_ids": [cust_id], "discount_percent": 95}).status_code == 422

    res = client.post("/api/v1/insights/rfm/vouchers", headers=mgr, json={
        "account_ids": [cust_id, mgr_id], "discount_percent": 12, "valid_days": 9, "minimum_order_amount": 150000})
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["created"] == 1 and body["skipped"] == 1
    code = body["vouchers"][0]["code"]
    assert code.startswith("CARE-") and len(code) == len("CARE-") + 6

    promo_ids = []
    try:
        promo = db_session.query(ProductionPromotion).filter(ProductionPromotion.code == code).one()
        promo_ids.append(promo.id)
        assert promo.promotion_type == "VOUCHER" and promo.is_active
        assert promo.usage_limit == 1 and promo.used_count == 0
        assert promo.eligible_customer_ids == [cust_id]
        assert float(promo.discount_percent) == 12 and float(promo.minimum_order_amount) == 150000
        assert 8 <= (promo.ends_at - promo.starts_at).days <= 9

        # Whole-segment sending targets exactly the members of that segment
        rfm = client.get("/api/v1/insights/rfm", headers=mgr).json()
        seg = next(c["segment"] for c in rfm["customers"] if c["account_id"] == cust_id)
        members = {c["account_id"] for c in rfm["customers"] if c["segment"] == seg}
        res = client.post("/api/v1/insights/rfm/vouchers", headers=mgr, json={"segment": seg, "discount_percent": 5})
        assert res.status_code == 201, res.text
        issued = res.json()["vouchers"]
        promo_ids += [v["promotion_id"] for v in issued]
        assert {v["account_id"] for v in issued} <= members and cust_id in {v["account_id"] for v in issued}
        db_session.expire_all()
        for v in issued:
            p = db_session.get(ProductionPromotion, v["promotion_id"])
            assert p.eligible_customer_ids == [v["account_id"]] and p.usage_limit == 1

        # The send action is recorded in the audit log
        logs = client.get("/api/v1/insights/audit-logs", headers=mgr, params={"q": "voucher chăm sóc"}).json()
        assert any(i["path"] == "/api/v1/insights/rfm/vouchers" and i["role_code"] == "MANAGER" for i in logs["items"])
    finally:
        db_session.rollback()
        for pid in promo_ids:
            p = db_session.get(ProductionPromotion, pid)
            if p:
                db_session.delete(p)
        db_session.commit()


def test_audit_log_records_staff_mutations_only(client, db_session):
    assert should_audit("PUT", "/api/v1/lucky-wheel/manage/slots/3", 200)
    assert not should_audit("GET", "/api/v1/lucky-wheel/manage", 200)
    assert not should_audit("POST", "/api/v1/auth/login", 200)
    assert not should_audit("POST", "/api/v1/auth/logout", 200)
    assert not should_audit("PUT", "/api/v1/lucky-wheel/manage/config", 400)
    assert not should_audit("POST", "/api/v1/orders/calculate-discount", 200)
    assert describe_action("PUT", "/api/v1/lucky-wheel/manage/slots/3") == "Cập nhật ô vòng quay #3"
    assert describe_action("DELETE", "/api/v1/lucky-wheel/manage/slots/7") == "Xoá ô vòng quay #7"
    assert describe_action("POST", "/api/v1/orders/42/cancel") == "Huỷ đơn hàng #42"

    adm = _login(client, "admin@soobin.vn")
    mgr = _login(client, "manager@soobin.vn")
    cust = _login(client, "customer@soobin.vn")
    before = db_session.query(ProductionAuditLog.id).order_by(ProductionAuditLog.id.desc()).first()
    last_id = before[0] if before else 0

    title = client.get("/api/v1/lucky-wheel/manage", headers=adm).json()["config"]["title"]
    res = client.put("/api/v1/lucky-wheel/manage/config", headers=adm, json={"title": title})
    assert res.status_code == 200, res.text

    # Failed and customer requests are not logged
    assert client.put("/api/v1/lucky-wheel/manage/config", headers=adm, json={"spins_per_period": 0}).status_code == 400
    address = client.post("/api/v1/auth/addresses", headers=cust, json={
        "recipient_name": f"Audit {uuid.uuid4().hex[:4]}", "recipient_phone": "0900000000", "address_line": "1 Test"})
    if address.status_code < 400 and address.json().get("id"):
        client.delete(f"/api/v1/auth/addresses/{address.json()['id']}", headers=cust)

    db_session.expire_all()
    new_rows = (
        db_session.query(ProductionAuditLog)
        .filter(ProductionAuditLog.id > last_id,
                ProductionAuditLog.path.in_(["/api/v1/lucky-wheel/manage/config", "/api/v1/auth/addresses"])
                | ProductionAuditLog.path.like("/api/v1/auth/addresses/%"))
        .all()
    )
    assert len(new_rows) == 1, [(r.method, r.path, r.status_code) for r in new_rows]
    row = new_rows[0]
    assert row.method == "PUT" and row.path == "/api/v1/lucky-wheel/manage/config"
    assert row.role_code == "ADMIN" and row.status_code == 200
    assert row.summary == "Cập nhật cấu hình vòng quay"

    # Visible to both ADMIN and MANAGER, with filters
    for headers in (adm, mgr):
        data = client.get("/api/v1/insights/audit-logs", headers=headers, params={"method": "PUT", "limit": 5}).json()
        assert data["items"] and all(i["method"] == "PUT" for i in data["items"])
        assert any(i["id"] == row.id for i in data["items"])
    data = client.get("/api/v1/insights/audit-logs", headers=mgr, params={"q": "cấu hình vòng quay", "limit": 200}).json()
    assert any(i["id"] == row.id for i in data["items"])
