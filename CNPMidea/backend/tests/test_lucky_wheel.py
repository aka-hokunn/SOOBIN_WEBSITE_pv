import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.models.entities import ProductionPromotion
from app.services.promotion_service import PromotionService


def _login(client, email):
    res = client.post("/api/v1/auth/login", json={"email_or_phone": email, "password": "Password123@"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['session_token']}"}


def test_lucky_wheel_permissions_and_public_state(client):
    mgr = _login(client, "manager@soobin.vn")
    adm = _login(client, "admin@soobin.vn")
    sales = _login(client, "sales@soobin.vn")
    cust = _login(client, "customer@soobin.vn")

    # Admin AND Manager can manage the wheel (and its vouchers); other roles cannot
    for headers in (adm, mgr):
        res = client.get("/api/v1/lucky-wheel/manage", headers=headers)
        assert res.status_code == 200, res.text
        body = res.json()
        assert {"config", "slots", "stats", "recent_spins", "next_reset_at"} <= set(body)
        assert client.get("/api/v1/lucky-wheel/manage/vouchers", headers=headers).status_code == 200
    assert client.get("/api/v1/lucky-wheel/manage", headers=sales).status_code == 403
    assert client.get("/api/v1/lucky-wheel/manage", headers=cust).status_code == 403
    assert client.post("/api/v1/lucky-wheel/manage/reset", headers=cust).status_code == 403

    # Public wheel never exposes weights / quantities (fresh client = no login cookie)
    public = TestClient(app).get("/api/v1/lucky-wheel").json()
    assert public["logged_in"] is False and public["can_spin"] is False
    assert len(public["slots"]) >= 2
    assert all("win_weight" not in s and "quantity_remaining" not in s for s in public["slots"])

    # Staff cannot spin (customers only)
    assert client.post("/api/v1/lucky-wheel/spin", headers=mgr).status_code == 403

    # Storefront + Admin + Manager portals are wired with the wheel & water cursor
    home = client.get("/").text
    for marker in ('id="luckyWheelTeaser"', "lucky-wheel.js", "lucky-wheel-core.js", "water-cursor.js", "lucky-wheel.css"):
        assert marker in home
    for portal in ("/admin", "/manager"):
        page = client.get(portal).text
        assert 'id="luckyWheelAdminRoot"' in page and "lucky-wheel-admin.js" in page and "switchTab('wheel')" in page
    for asset in ("lucky-wheel.js", "lucky-wheel-core.js", "lucky-wheel-admin.js", "water-cursor.js"):
        assert client.get(f"/static/js/{asset}").status_code == 200
    assert "fireworks" in client.get("/static/js/lucky-wheel.js").text
    assert "uRipples" in client.get("/static/js/ocean-stage.js").text


def test_lucky_wheel_spin_win_soldout_limit_reset_and_personal_voucher(client, db_session):
    mgr = _login(client, "manager@soobin.vn")
    cust = _login(client, "customer@soobin.vn")
    cust_id = client.get("/api/v1/auth/me", headers=cust).json()["id"]

    original = client.get("/api/v1/lucky-wheel/manage", headers=mgr).json()
    orig_cfg = original["config"]
    orig_active = [s["id"] for s in original["slots"] if s["is_active"]]
    created_ids = []

    # Template voucher created by the manager (manager can manage vouchers like admin)
    tpl_code = f"WTEST{uuid.uuid4().hex[:6].upper()}"
    now = datetime.now(timezone.utc)
    res = client.post("/api/v1/promotions", headers=mgr, json={
        "code": tpl_code, "name": "Mẫu test vòng quay", "promotion_type": "VOUCHER",
        "discount_percent": 20, "minimum_order_amount": 0, "usage_limit": None,
        "starts_at": (now - timedelta(minutes=5)).isoformat(), "ends_at": (now + timedelta(days=30)).isoformat(),
        "eligible_customer_ids": None,
    })
    assert res.status_code == 201, res.text
    tpl_id = res.json()["id"]

    try:
        # Prize slot (100% weight, only 1 voucher) + "no prize" slot (blank voucher/quantity)
        res = client.post("/api/v1/lucky-wheel/manage/slots", headers=mgr, json={
            "label": "TEST -20%", "promotion_id": tpl_id, "win_weight": 100, "quantity_total": 1})
        assert res.status_code == 201, res.text
        created_ids.append(res.json()["id"])
        res = client.post("/api/v1/lucky-wheel/manage/slots", headers=mgr, json={
            "label": "", "promotion_id": None, "win_weight": 0, "quantity_total": None})
        assert res.status_code == 201, res.text
        created_ids.append(res.json()["id"])

        for sid in orig_active:
            assert client.put(f"/api/v1/lucky-wheel/manage/slots/{sid}", headers=mgr, json={"is_active": False}).status_code == 200

        # Cannot drop below 2 active slots
        assert client.put(f"/api/v1/lucky-wheel/manage/slots/{created_ids[1]}", headers=mgr,
                          json={"is_active": False}).status_code == 400
        # Invalid rate rejected
        assert client.put(f"/api/v1/lucky-wheel/manage/slots/{created_ids[0]}", headers=mgr,
                          json={"win_weight": 150}).status_code == 400

        state = client.get("/api/v1/lucky-wheel/manage", headers=mgr).json()
        slots = {s["id"]: s for s in state["slots"]}
        assert slots[created_ids[0]]["is_prize"] is True
        assert slots[created_ids[0]]["probability_percent"] == 100
        assert slots[created_ids[1]]["is_prize"] is False          # blank → không trúng thưởng
        assert slots[created_ids[1]]["label"] == "Chúc may mắn"

        res = client.put("/api/v1/lucky-wheel/manage/config", headers=mgr, json={
            "enabled": True, "spins_per_period": 2, "reset_interval_minutes": 90, "voucher_valid_days": 5})
        assert res.status_code == 200, res.text
        assert client.post("/api/v1/lucky-wheel/manage/reset", headers=mgr).status_code == 200

        pub = client.get("/api/v1/lucky-wheel", headers=cust).json()
        assert pub["can_spin"] is True and pub["spins_left"] == 2
        assert [s["id"] for s in pub["slots"]] == created_ids

        # Spin 1 → guaranteed win with a personal voucher
        win = client.post("/api/v1/lucky-wheel/spin", headers=cust)
        assert win.status_code == 200, win.text
        win = win.json()
        assert win["is_win"] is True and win["slot_index"] == 0 and win["spins_left"] == 1
        code = win["voucher"]["code"]
        assert code.startswith("SPIN-") and win["voucher"]["discount_percent"] == 20

        # Spin 2 → prize sold out this cycle → lands on the "no prize" slot
        lose = client.post("/api/v1/lucky-wheel/spin", headers=cust).json()
        assert lose["is_win"] is False and lose["slot_id"] == created_ids[1] and lose["voucher"] is None
        assert "may mắn lần sau" in lose["message"]

        # Spin 3 → no spins left in this cycle
        assert client.post("/api/v1/lucky-wheel/spin", headers=cust).status_code == 429

        mine = client.get("/api/v1/lucky-wheel/my-vouchers", headers=cust).json()
        assert any(v["code"] == code and v["status"] == "AVAILABLE" for v in mine)

        # Personal voucher: single use, only valid for the winner
        items = [{"product_id": 1, "variant_id": 1, "unit_price": 500000.0, "quantity": 1}]
        svc = PromotionService(db_session)
        mine_calc = svc.calculate_discounts(items, voucher_code=code, account_id=cust_id)
        assert mine_calc["voucher_discount"] == 100000.0
        other_calc = svc.calculate_discounts(items, voucher_code=code, account_id=cust_id + 999999)
        assert other_calc["voucher_discount"] == 0.0
        assert client.get(f"/api/v1/promotions/check-voucher/{code}").json()["remaining_uses"] == 1

        stats = client.get("/api/v1/lucky-wheel/manage", headers=mgr).json()
        assert {s["id"]: s for s in stats["slots"]}[created_ids[0]]["quantity_remaining"] == 0
        assert any(r["voucher_code"] == code for r in stats["recent_spins"])

        # Reset → spins restored and voucher stock refilled
        assert client.post("/api/v1/lucky-wheel/manage/reset", headers=mgr).status_code == 200
        assert client.get("/api/v1/lucky-wheel", headers=cust).json()["spins_left"] == 2
        refilled = client.get("/api/v1/lucky-wheel/manage", headers=mgr).json()
        assert {s["id"]: s for s in refilled["slots"]}[created_ids[0]]["quantity_remaining"] == 1
    finally:
        for sid in orig_active:
            client.put(f"/api/v1/lucky-wheel/manage/slots/{sid}", headers=mgr, json={"is_active": True})
        for sid in created_ids:
            client.delete(f"/api/v1/lucky-wheel/manage/slots/{sid}", headers=mgr)
        client.put("/api/v1/lucky-wheel/manage/config", headers=mgr, json={
            k: orig_cfg[k] for k in ("enabled", "spins_per_period", "reset_interval_minutes",
                                     "restock_on_reset", "voucher_valid_days", "title", "subtitle")
        })
        client.post("/api/v1/lucky-wheel/manage/reset", headers=mgr)
        # Remove the temporary template voucher so it does not clutter the voucher store
        db_session.query(ProductionPromotion).filter(ProductionPromotion.code == tpl_code).delete()
        db_session.commit()
