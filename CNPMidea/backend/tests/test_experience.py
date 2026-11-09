import io
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.models.entities import (
    ProductionCategory,
    ProductionDailyCheckin,
    ProductionFitProfile,
    ProductionInventory,
    ProductionOrder,
    ProductionOrderItem,
    ProductionProduct,
    ProductionVariant,
    UserAccount,
)
from app.services import experience_service as exp
from app.services.experience_service import (
    display_first_name,
    palette_distance,
    parse_province,
    recommend_size,
    vn_today,
)


def _login(client, email, password="Password123@"):
    res = client.post("/api/v1/auth/login", json={"email_or_phone": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['session_token']}"}


def _fresh_customer(client):
    email = f"exp_{uuid.uuid4().hex[:10]}@example.com"
    reg = client.post("/api/v1/auth/register", json={
        "email": email, "full_name": "Khách Trải Nghiệm", "password": "Password123@",
        "phone": f"09{uuid.uuid4().int % 100000000:08d}",
    })
    assert reg.status_code == 200, reg.text
    assert client.post("/api/v1/auth/verify-email", json={"token": reg.json()["verification_token"]}).status_code == 200
    return email, _login(client, email)


def _png(color=(230, 90, 60), size=(160, 160)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


# ----------------------------------------------------------------------------- 1. fit
def test_fit_recommendation_product_chart_defaults_and_profile(client, db_session):
    chart = {"S": {"chest": "80-84cm", "waist": "62-66cm"}, "M": {"chest": "85-89cm", "waist": "67-71cm"},
             "L": {"chest": "90-94cm", "waist": "72-76cm"}}
    woman = {"gender": "Nữ", "height_cm": 160, "weight_kg": 50, "bust_cm": 86, "waist_cm": 68}
    rec = recommend_size(woman, "Nữ", chart, ["S", "M", "L"], ["S", "M", "L"])
    assert rec["status"] == "ok" and rec["size"] == "M" and rec["basis"] == "product_chart"
    assert rec["confidence"] >= 80 and rec["level"] == "high" and rec["in_stock"] is True

    # Larger measurements move up the chart; out-of-stock recommendation is flagged
    big = recommend_size({**woman, "bust_cm": 93, "waist_cm": 75}, "Nữ", chart, ["S", "M", "L"], ["S", "M"])
    assert big["size"] == "L" and big["in_stock"] is False

    # Kids chart only has ages → falls back to the standard kids chart (height/weight)
    kid = recommend_size({"gender": "Trẻ em", "height_cm": 105, "weight_kg": 17}, "Trẻ em",
                         {"XS": {"age": "2-3 tuổi"}, "S": {"age": "4-5 tuổi"}, "M": {"age": "6-7 tuổi"}}, ["XS", "S", "M"])
    assert kid["status"] == "ok" and kid["size"] == "S" and kid["basis"] == "standard_chart"

    # Men's product without chart → standard men chart
    man = recommend_size({"gender": "Nam", "height_cm": 175, "weight_kg": 70}, "Nam", {}, ["M", "L", "XL"])
    assert man["size"] == "L"

    # Accessories & other audiences → no badge
    assert recommend_size(woman, "Unisex", {"FREESIZE": {"info": "x"}}, ["FREESIZE"])["status"] == "one_size"
    assert recommend_size(woman, "Nam", {}, ["M", "L"])["status"] == "other_audience"
    assert recommend_size(None, "Nữ", chart, ["M"])["status"] == "no_profile"

    # Endpoint: sizes for quick-add + fit per product (real catalog)
    women = (db_session.query(ProductionProduct)
             .join(ProductionCategory, ProductionProduct.category_id == ProductionCategory.id)
             .filter(ProductionProduct.target_audience == "Nữ", ProductionProduct.deleted_at == None,  # noqa: E711
                     ProductionProduct.status == "Selling")
             .limit(3).all())
    acc = db_session.query(ProductionProduct).filter(ProductionProduct.target_audience == "Unisex",
                                                    ProductionProduct.status == "Selling").first()
    ids = [p.id for p in women] + ([acc.id] if acc else [])
    res = client.post("/api/v1/experience/fit/recommend", json={"product_ids": ids, "profile": woman})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["profile_source"] == "request"
    for p in women:
        item = body["items"][str(p.id)]
        assert item["sizes"] and all({"size_code", "variant_id", "in_stock", "available"} <= set(s) for s in item["sizes"])
        assert item["fit"]["status"] in ("ok", "insufficient")
    if acc:
        assert body["items"][str(acc.id)]["fit"]["status"] == "one_size"

    # Persisted profile for a logged-in customer is used when no profile is sent
    other = TestClient(app)
    email, headers = _fresh_customer(other)
    try:
        assert other.get("/api/v1/experience/fit-profile", headers=headers).json()["profile"] is None
        bad = other.put("/api/v1/experience/fit-profile", headers=headers, json={"gender": "Nữ", "height_cm": 999})
        assert bad.status_code == 400
        saved = other.put("/api/v1/experience/fit-profile", headers=headers, json=woman)
        assert saved.status_code == 200, saved.text
        assert saved.json()["profile"]["bust_cm"] == 86
        via_account = other.post("/api/v1/experience/fit/recommend", headers=headers,
                                 json={"product_ids": [women[0].id]}).json()
        assert via_account["profile_source"] == "account"
        assert TestClient(app).put("/api/v1/experience/fit-profile", json=woman).status_code == 401
    finally:
        uid = db_session.query(UserAccount.id).filter(UserAccount.email == email).scalar()
        db_session.query(ProductionFitProfile).filter(ProductionFitProfile.account_id == uid).delete()
        db_session.commit()


# ----------------------------------------------------------------------------- 3. social proof
def test_recent_purchases_are_real_and_anonymized(client, db_session):
    assert display_first_name("Nguyễn Thị Lan") == "Lan"
    assert display_first_name("Khách 1") is None and display_first_name("Test User") is None
    assert parse_province("12 Trần Phú, Hải Châu, Đà Nẵng") == "Đà Nẵng"
    assert parse_province("45 Lê Duẩn, Q1, TP.HCM") == "TP.HCM"
    assert parse_province("Phường 5, Thành phố Hồ Chí Minh") == "TP.HCM"
    assert parse_province("Bãi Trường, Phú Quốc") == "Kiên Giang"
    assert parse_province("Địa chỉ 1") is None

    cust_id = db_session.query(UserAccount.id).filter(UserAccount.email == "customer@soobin.vn").scalar()
    variant = (db_session.query(ProductionVariant).join(ProductionProduct)
               .filter(ProductionProduct.deleted_at == None, ProductionProduct.status == "Selling")  # noqa: E711
               .first())
    tag = uuid.uuid4().hex[:8].upper()
    orders = []
    for status, name, addr in (("Chưa xử lý", "Nguyễn Thị Lan", "12 Trần Phú, Hải Châu, Đà Nẵng"),
                               ("Đã hủy", "Trần Văn Hủy", "1 Lê Lợi, Huế")):
        o = ProductionOrder(
            code=f"TEST-EXP-{tag}-{len(orders)}", account_id=cust_id, status=status, payment_method="COD",
            subtotal=100000, total_amount=130000, shipping_fee=30000,
            recipient_snapshot={"name": name, "phone": "0909123456", "address": addr},
            store_snapshot={}, placed_at=datetime.now(timezone.utc) - timedelta(minutes=3),
        )
        o.items.append(ProductionOrderItem(
            variant_id=variant.id, quantity=1, unit_price=100000, unit_cost_snapshot=50000, line_total=100000,
            product_snapshot={"id": variant.product_id, "name": "snapshot"},
        ))
        db_session.add(o)
        orders.append(o)
    db_session.commit()
    try:
        exp._recent_cache.update({"at": 0.0, "key": None, "data": None})
        res = client.get("/api/v1/experience/recent-purchases?limit=30")
        assert res.status_code == 200, res.text
        items = res.json()["items"]
        raw = res.text
        assert "0909123456" not in raw and "Trần Phú" not in raw and "Nguyễn Thị" not in raw and "TEST-EXP" not in raw
        lan = [i for i in items if i["buyer"] == "Lan" and i["province"] == "Đà Nẵng"]
        assert lan, items[:3]
        assert lan[0]["product_id"] == variant.product_id and lan[0]["minutes_ago"] <= 5
        assert lan[0]["image_url"].startswith("/static/") and lan[0]["time_label"].endswith("trước")
        assert not any(i["buyer"] == "Hủy" for i in items)          # cancelled orders never shown
        for i in items:
            assert set(i) == {"key", "buyer", "province", "product_id", "product_slug", "product_name", "image_url",
                              "quantity", "minutes_ago", "time_label"}
            assert i["minutes_ago"] <= 7 * 24 * 60
            assert " " not in i["buyer"] or i["buyer"] == "Một khách hàng"
    finally:
        for o in orders:
            db_session.delete(o)
        db_session.commit()
        exp._recent_cache.update({"at": 0.0, "key": None, "data": None})


def test_presence_counter_is_real_with_ttl(client):
    tracker = exp.PresenceTracker(ttl_seconds=10)
    assert tracker.heartbeat(7, "viewer-aaaa", now=100.0) == 1
    assert tracker.heartbeat(7, "viewer-bbbb", now=101.0) == 2
    assert tracker.heartbeat(7, "viewer-aaaa", now=105.0) == 2          # same viewer counted once
    assert tracker.count(7, now=112.0) == 1                               # bbbb expired after TTL
    assert tracker.leave(7, "viewer-aaaa") == 0

    pid = 900000 + uuid.uuid4().int % 99999
    a = client.post("/api/v1/experience/presence", json={"product_id": pid, "viewer_id": "tab-" + uuid.uuid4().hex[:12]})
    assert a.status_code == 200 and a.json()["viewers"] == 1
    vb = "tab-" + uuid.uuid4().hex[:12]
    assert client.post("/api/v1/experience/presence", json={"product_id": pid, "viewer_id": vb}).json()["viewers"] == 2
    assert client.post("/api/v1/experience/presence/leave", json={"product_id": pid, "viewer_id": vb}).json()["viewers"] == 1
    assert client.post("/api/v1/experience/presence", json={"product_id": pid, "viewer_id": "<script>"}).status_code == 400


# ----------------------------------------------------------------------------- 4. trip stylist
def test_trip_stylist_returns_in_stock_curated_set(client, db_session):
    for trip, gender in (("bien", "Nữ"), ("thi-dau", "Nam"), ("ho-boi", "Trẻ em"), ("resort", "Nữ")):
        res = client.post("/api/v1/experience/trip-stylist", json={
            "trip_type": trip, "days": 4, "gender": gender, "style": "nang-dong"})
        assert res.status_code == 200, res.text
        data = res.json()
        roles = [i["role"] for i in data["items"]]
        assert roles and roles[0] == "main", data
        assert "eyewear" in roles
        if trip in ("bien", "resort"):
            assert "bag" in roles
        assert len({i["product_id"] for i in data["items"]}) == len(data["items"])
        assert abs(data["total_price"] - sum(i["unit_price"] for i in data["items"])) < 1
        for item in data["items"]:
            inv = db_session.query(ProductionInventory).filter(ProductionInventory.variant_id == item["variant_id"]).first()
            var = db_session.query(ProductionVariant).filter(ProductionVariant.id == item["variant_id"]).first()
            assert inv and inv.available_quantity > 0 and var.product_id == item["product_id"]
            assert item["reason"] and item["unit_price"] <= item["base_price"]
        main = data["items"][0]
        prod = db_session.query(ProductionProduct).filter(ProductionProduct.id == main["product_id"]).first()
        assert prod.target_audience == gender

    # Budget is respected (or flagged) and the fit profile picks the size when in stock
    res = client.post("/api/v1/experience/trip-stylist", json={
        "trip_type": "bien", "days": 2, "gender": "Nữ", "style": "kin-dao", "budget": 900000,
        "profile": {"gender": "Nữ", "height_cm": 160, "weight_kg": 50, "bust_cm": 86, "waist_cm": 68}})
    data = res.json()
    assert res.status_code == 200 and data["used_fit_profile"] is True
    assert data["within_budget"] == (data["total_price"] <= 900000)
    assert client.post("/api/v1/experience/trip-stylist", json={"trip_type": "space"}).status_code == 400
    assert client.post("/api/v1/experience/trip-stylist", json={"trip_type": "bien", "days": 99}).status_code == 400


# ----------------------------------------------------------------------------- 5. visual search
def test_visual_search_palette_ranking_and_validation(client, db_session):
    red = [((230, 40, 40), 0.7), ((250, 250, 250), 0.3)]
    blue = [((20, 60, 200), 0.8), ((240, 240, 240), 0.2)]
    assert palette_distance(red, red) < 1e-6 < palette_distance(red, blue)

    res = client.post("/api/v1/experience/visual-search",
                      files={"image": ("sea.png", _png((14, 116, 144)), "image/png")})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["palette"] and data["palette"][0]["hex"].startswith("#")
    sims = [r["similarity"] for r in data["results"]]
    assert data["results"] and sims == sorted(sims, reverse=True) and all(0 <= s <= 100 for s in sims)
    assert {"id", "slug", "image_url", "discounted_price", "palette"} <= set(data["results"][0])
    assert exp._palette_cache  # product palettes cached in memory (keyed by image path + mtime)

    # Category hint restricts the candidates
    women_ids = {c.id for c in db_session.query(ProductionCategory).filter(
        (ProductionCategory.slug == "do-boi-nu") | ProductionCategory.parent.has(ProductionCategory.slug == "do-boi-nu"))}
    res = client.post("/api/v1/experience/visual-search", data={"category": "do-boi-nu"},
                      files={"image": ("coral.jpg", _png((249, 115, 22)), "image/jpeg")})
    assert res.status_code == 200, res.text
    assert all(r["category_id"] in women_ids for r in res.json()["results"])

    # Validation: type, content, size
    assert client.post("/api/v1/experience/visual-search",
                       files={"image": ("a.txt", b"hello", "text/plain")}).status_code == 415
    assert client.post("/api/v1/experience/visual-search",
                       files={"image": ("a.png", b"not-an-image", "image/png")}).status_code == 400
    big = b"\x89PNG" + b"0" * (6 * 1024 * 1024 + 10)
    assert client.post("/api/v1/experience/visual-search",
                       files={"image": ("big.png", big, "image/png")}).status_code == 413
    gif = io.BytesIO()
    Image.new("RGB", (40, 40), (1, 2, 3)).save(gif, "GIF")
    assert client.post("/api/v1/experience/visual-search",
                       files={"image": ("x.png", gif.getvalue(), "image/png")}).status_code == 415


# ----------------------------------------------------------------------------- 6. check-in
def test_checkin_streak_shells_and_bonus_spin(db_session):
    other = TestClient(app)
    assert other.get("/api/v1/experience/checkin").status_code == 401
    email, headers = _fresh_customer(other)
    uid = db_session.query(UserAccount.id).filter(UserAccount.email == email).scalar()
    try:
        state = other.get("/api/v1/experience/checkin", headers=headers).json()
        assert state["checked_in_today"] is False and state["streak"] == 0 and state["next_reward"] == 1
        assert [d["status"] for d in state["days"]][:2] == ["today", "upcoming"]
        wheel_before = other.get("/api/v1/lucky-wheel", headers=headers).json()
        assert wheel_before["bonus_spins"] == 0

        # Two previous consecutive days (backdated) → today is day 3 of the streak
        today = vn_today()
        long_ago = datetime.now(timezone.utc) - timedelta(days=3)
        for offset, day in ((2, 1), (1, 2)):
            db_session.add(ProductionDailyCheckin(account_id=uid, checkin_date=today - timedelta(days=offset),
                                                  streak_day=day, shells_awarded=1, bonus_spins=0, created_at=long_ago))
        db_session.commit()

        res = other.post("/api/v1/experience/checkin", headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["checked_in_today"] is True and data["streak"] == 3
        assert data["awarded_shells"] == 1 and data["total_shells"] == 3 and data["shells_progress"] == 0
        assert data["bonus_spins_awarded"] == 1 and data["bonus_spins_this_cycle"] == 1
        assert [d["status"] for d in data["days"]][:4] == ["done", "done", "done", "upcoming"]
        assert other.post("/api/v1/experience/checkin", headers=headers).status_code == 409

        # +1 bonus spin in the current lucky-wheel cycle
        wheel = other.get("/api/v1/lucky-wheel", headers=headers).json()
        assert wheel["bonus_spins"] == 1
        assert wheel["spins_left"] == wheel_before["spins_left"] + 1
        assert wheel["can_spin"] is wheel["enabled"]

        # Missed days reset the streak; a finished 7-day week starts a new one
        db_session.query(ProductionDailyCheckin).filter(ProductionDailyCheckin.account_id == uid).delete()
        db_session.add(ProductionDailyCheckin(account_id=uid, checkin_date=today - timedelta(days=3),
                                              streak_day=5, shells_awarded=1, bonus_spins=0, created_at=long_ago))
        db_session.commit()
        state = other.get("/api/v1/experience/checkin", headers=headers).json()
        assert state["streak"] == 0 and state["next_reward"] == 1 and state["bonus_spins_this_cycle"] == 0
        db_session.query(ProductionDailyCheckin).filter(ProductionDailyCheckin.account_id == uid).delete()
        db_session.add(ProductionDailyCheckin(account_id=uid, checkin_date=today - timedelta(days=1),
                                              streak_day=6, shells_awarded=1, bonus_spins=0, created_at=long_ago))
        db_session.commit()
        state = other.get("/api/v1/experience/checkin", headers=headers).json()
        assert state["streak"] == 6 and state["next_reward"] == 3       # day 7 = big reward
        assert other.get("/api/v1/lucky-wheel", headers=headers).json()["bonus_spins"] == 0

        # Staff cannot check in
        mgr = _login(other, "manager@soobin.vn")
        assert other.post("/api/v1/experience/checkin", headers=mgr).status_code == 403
    finally:
        db_session.query(ProductionDailyCheckin).filter(ProductionDailyCheckin.account_id == uid).delete()
        db_session.commit()


def test_storefront_wires_plus_assets(client):
    home = client.get("/").text
    for marker in ("storefront-plus.js", "storefront-plus.css", "data-visual-search", "soobinPlus.openTripStylist",
                   "soobinPlus.openFitProfile"):
        assert marker in home
    js = client.get("/static/js/storefront-plus.js")
    assert js.status_code == 200 and "interceptLoadProducts" in js.text and "onGridRendered" in js.text
    assert "data-lw-tab=\"checkin\"" in client.get("/static/js/lucky-wheel.js").text
    app_js = client.get("/static/js/app.js").text
    assert "soobinPlus.onGridRendered" in app_js and "soobinPlus.onProductModalOpen" in app_js
