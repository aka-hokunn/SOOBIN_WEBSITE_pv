import uuid


def _login(client, email):
    res = client.post(
        "/api/v1/auth/login",
        json={"email_or_phone": email, "password": "Password123@"},
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['session_token']}"}


def test_direct_sale_price_and_bulk_markdown(client):
    mgr_headers = _login(client, "manager@soobin.vn")

    # 1. Fetch product 1 initial state
    manage_res = client.get("/api/v1/catalog/products/manage", headers=mgr_headers)
    assert manage_res.status_code == 200
    prod1 = next(p for p in manage_res.json() if p["id"] == 1)
    orig_base = prod1["base_price"]

    # 2. Set direct sale price (e.g., 20% off orig_base)
    target_sale = round(orig_base * 0.8)
    sale_res = client.put(
        "/api/v1/catalog/products/1/sale-price",
        headers=mgr_headers,
        json={"base_price": orig_base, "sale_price": target_sale, "clear_sale": False},
    )
    assert sale_res.status_code == 200, sale_res.text
    sale_data = sale_res.json()["product"]
    assert sale_data["on_sale"] is True
    assert sale_data["discount_percent"] > 0
    assert abs(sale_data["sale_price"] - target_sale) <= 100

    # 3. Verify manage endpoint includes gross_margin_percent and sale_price
    manage_after = client.get("/api/v1/catalog/products/manage", headers=mgr_headers).json()
    p1_after = next(p for p in manage_after if p["id"] == 1)
    assert p1_after["on_sale"] is True
    assert "gross_margin_percent" in p1_after
    assert "avg_unit_cost" in p1_after

    # 4. Run Bulk Markdown campaign on category 1
    bulk_res = client.post(
        "/api/v1/catalog/products/bulk-sale",
        headers=mgr_headers,
        json={
            "category_id": prod1["category_id"],
            "discount_percent": 15.0,
            "clear_sale": False,
        },
    )
    assert bulk_res.status_code == 200, bulk_res.text
    assert bulk_res.json()["updated_count"] >= 1

    # 5. Clear sale on category and product 1
    client.post(
        "/api/v1/catalog/products/bulk-sale",
        headers=mgr_headers,
        json={
            "category_id": prod1["category_id"],
            "discount_percent": 0.0,
            "clear_sale": True,
        },
    )
    clear_res = client.put(
        "/api/v1/catalog/products/1/sale-price",
        headers=mgr_headers,
        json={"clear_sale": True},
    )
    assert clear_res.status_code == 200
    assert clear_res.json()["product"]["on_sale"] is False


def test_sales_pos_counter_and_crm_360_and_loyalty(client):
    sales_headers = _login(client, "sales@soobin.vn")
    cust_headers = _login(client, "customer@soobin.vn")

    # 1. Create In-Store POS Order (INSTORE_PICKUP -> auto delivered + invoice issued)
    pos_res = client.post(
        "/api/v1/orders/pos",
        headers=sales_headers,
        json={
            "customer_name": "Khách VIP Tại Quầy POS",
            "customer_phone": "0918889999",
            "shipping_address": "Nhận trực tiếp tại Showroom Soobin Swimwear",
            "payment_method": "CASH",
            "fulfillment_type": "INSTORE_PICKUP",
            "items": [{"variant_id": 1, "quantity": 1}],
        },
    )
    assert pos_res.status_code == 201, pos_res.text
    pos_order = pos_res.json()["order"]
    assert pos_order["status"] == "Đã giao"
    assert pos_order["payment_status"] == "PAID"
    assert pos_order["invoice_code"] is not None

    # 2. Query 360 Clienteling CRM
    crm_res = client.get("/api/v1/orders/crm/customers", headers=sales_headers)
    assert crm_res.status_code == 200
    customers = crm_res.json()
    assert len(customers) >= 1
    assert "vip_tier" in customers[0]
    assert "total_spend" in customers[0]

    # 3. Query Customer VIP Loyalty Summary
    loy_res = client.get("/api/v1/orders/loyalty-summary", headers=cust_headers)
    assert loy_res.status_code == 200
    loy_data = loy_res.json()
    assert "current_tier" in loy_data
    assert "progress_percent" in loy_data


def test_warehouse_stocktake_and_supplier_crud(client):
    wh_headers = _login(client, "warehouse@soobin.vn")

    # 1. Create a new supplier
    sup_code = f"SUP-{uuid.uuid4().hex[:6].upper()}"
    sup_res = client.post(
        "/api/v1/inventory/suppliers",
        headers=wh_headers,
        json={
            "code": sup_code,
            "name": "Công Ty Dệt Kim Lycra Quốc Tế",
            "phone": "0901112233",
            "email": f"{sup_code.lower()}@lycra.vn",
            "address": "KCN Tân Bình, TP.HCM",
        },
    )
    assert sup_res.status_code == 201, sup_res.text
    sup_id = sup_res.json()["supplier"]["id"]

    # 2. Update supplier
    upd_sup = client.put(
        f"/api/v1/inventory/suppliers/{sup_id}",
        headers=wh_headers,
        json={"name": "Công Ty Dệt Kim Lycra Quốc Tế (Updated)", "status": "ACTIVE"},
    )
    assert upd_sup.status_code == 200

    # 3. Execute Cycle Count / Stocktake on variant 2
    balances = client.get("/api/v1/inventory/balances", headers=wh_headers).json()
    v2 = next(b for b in balances if b["variant_id"] == 2)
    cur_qty = v2["available_quantity"]

    st_res = client.post(
        "/api/v1/inventory/stocktake",
        headers=wh_headers,
        json={
            "variant_id": 2,
            "actual_quantity": cur_qty + 3,
            "low_stock_threshold": 6,
            "reason": "Kiểm kê định kỳ phát hiện thừa 3 sản phẩm trên kệ B2",
        },
    )
    assert st_res.status_code == 200, st_res.text
    st_data = st_res.json()["stocktake"]
    assert st_data["actual_quantity"] == cur_qty + 3
    assert st_data["quantity_delta"] == 3


def test_storefront_theme_feedbacks_and_admin_audit_logs(client):
    mgr_headers = _login(client, "manager@soobin.vn")
    sales_headers = _login(client, "sales@soobin.vn")
    admin_headers = _login(client, "admin@soobin.vn")

    # 1. Update & get Storefront 3D Theme
    put_theme = client.put(
        "/api/v1/site-settings/theme",
        headers=mgr_headers,
        json={
            "theme": "sunset-ibiza",
            "enable_3d_morph": True,
            "hero_headline": "Bộ Sưu Tập Hoàng Hôn Ibiza 2026",
            "hero_subtitle": "Chuyển động 3D Morphing đẳng cấp",
        },
    )
    assert put_theme.status_code == 200

    get_theme = client.get("/api/v1/site-settings/theme")
    assert get_theme.status_code == 200
    assert get_theme.json()["theme"] == "sunset-ibiza"

    # Restore default ocean-luxury theme
    client.put(
        "/api/v1/site-settings/theme",
        headers=mgr_headers,
        json={"theme": "ocean-luxury", "enable_3d_morph": True},
    )

    # 2. Customer submits Stylist consultation feedback & Sales resolves it
    fb_res = client.post(
        "/api/v1/site-settings/feedbacks",
        json={
            "full_name": "Trần Bảo Ngọc",
            "email": "baongoc@example.com",
            "phone": "0988776655",
            "subject": "Tư vấn chọn size Bikini 1 mảnh",
            "message": "Mình cao 1m65 nặng 52kg nhờ Stylist tư vấn mẫu tôn dáng.",
        },
    )
    assert fb_res.status_code == 201, fb_res.text
    ticket_id = fb_res.json()["ticket"]["id"]

    fb_list = client.get("/api/v1/site-settings/feedbacks", headers=sales_headers)
    assert fb_list.status_code == 200
    assert any(t["id"] == ticket_id for t in fb_list.json())

    fb_upd = client.put(
        f"/api/v1/site-settings/feedbacks/{ticket_id}",
        headers=sales_headers,
        json={"status": "RESOLVED"},
    )
    assert fb_upd.status_code == 200
    assert fb_upd.json()["status"] == "RESOLVED"

    # 3. Admin queries Enterprise Audit Trail
    audit_res = client.get("/api/v1/admin/audit-logs?limit=30", headers=admin_headers)
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert isinstance(logs, list)
    assert len(logs) >= 1
    assert "category" in logs[0]
    assert "title" in logs[0]


def test_spatial_3d_viewer_lookbook_bundles_and_compare(client):
    cust_headers = _login(client, "customer@soobin.vn")

    # 1. Verify Product Detail & Dedicated 3D Spatial Showroom Endpoint
    detail_res = client.get("/api/v1/catalog/products/1")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert "spatial_3d" in detail
    assert detail["spatial_3d"]["geometry_type"] in (
        "onepiece_3d",
        "bikini_3d",
        "jammer_3d",
        "rashguard_3d",
        "goggles_3d",
    )

    sp_res = client.get("/api/v1/catalog/products/1/spatial-3d")
    assert sp_res.status_code == 200
    sp_data = sp_res.json()
    assert len(sp_data["spatial_hotspots"]) >= 3
    assert len(sp_data["lighting_presets"]) >= 4
    assert "material_physics" in sp_data
    assert sp_data["material_physics"]["uv_protection"] == "UPF 50+"

    # 2. Verify 3D Product Comparison Matrix API
    cmp_res = client.get("/api/v1/catalog/compare?ids=1,2")
    assert cmp_res.status_code == 200
    cmp_items = cmp_res.json()
    assert len(cmp_items) == 2
    assert "material_physics" in cmp_items[0]
    assert "geometry_type" in cmp_items[0]

    # 3. Verify Mix & Match 3D Lookbook Bundles & 1-Click Add Bundle to Cart
    bundles_res = client.get("/api/v1/catalog/lookbook-bundles")
    assert bundles_res.status_code == 200
    bundles = bundles_res.json()
    assert len(bundles) >= 1
    first_bundle = bundles[0]
    assert len(first_bundle["items"]) >= 1

    add_bundle_res = client.post(
        "/api/v1/cart/bundle",
        headers=cust_headers,
        json={
            "bundle_name": first_bundle["name"],
            "items": [
                {"variant_id": it["variant_id"], "quantity": 1}
                for it in first_bundle["items"]
            ],
        },
    )
    assert add_bundle_res.status_code == 200, add_bundle_res.text
    bundle_cart = add_bundle_res.json()
    assert bundle_cart["added_bundle_items"] >= 1
    assert "discounted_subtotal" in bundle_cart


def test_order_reorder_exchange_and_ai_replenishment_reports(client):
    cust_headers = _login(client, "customer@soobin.vn")
    mgr_headers = _login(client, "manager@soobin.vn")
    wh_headers = _login(client, "warehouse@soobin.vn")

    # 1. Create an order for customer, then test 1-click Reorder & Size Exchange Request
    ord_res = client.post(
        "/api/v1/orders",
        headers=cust_headers,
        json={
            "recipient_name": "Khách Hàng Test Reorder 3D",
            "recipient_phone": "0903456789",
            "shipping_address": "123 Nguyễn Huệ, Quận 1, TP.HCM",
            "payment_method": "COD",
            "guest_items": [{"variant_id": 1, "quantity": 1}],
        },
    )
    assert ord_res.status_code == 200, ord_res.text
    order_id = ord_res.json()["order_id"]

    reorder_res = client.post(
        f"/api/v1/orders/{order_id}/reorder",
        headers=cust_headers,
    )
    assert reorder_res.status_code == 200, reorder_res.text
    assert reorder_res.json()["added_count"] >= 1

    exch_res = client.post(
        f"/api/v1/orders/{order_id}/exchange-request",
        headers=cust_headers,
        json={
            "target_size": "XL",
            "preferred_resolution": "EXCHANGE_SIZE",
            "reason": "Mình mặc size hiện tại hơi ôm phần vai, mong muốn đổi lên size XL.",
        },
    )
    assert exch_res.status_code == 200, exch_res.text
    assert "ticket_code" in exch_res.json()

    # 2. Verify Advanced Analytics & AI Smart Inventory Replenishment Advisor
    analytics_res = client.get("/api/v1/reports/analytics", headers=mgr_headers)
    assert analytics_res.status_code == 200, analytics_res.text
    analytics = analytics_res.json()
    assert "revenue_by_category" in analytics
    assert "payment_method_breakdown" in analytics
    assert "replenishment_recommendations" in analytics
    assert len(analytics["replenishment_recommendations"]) >= 1

    # 3. Verify CSV Export for Orders, Inventory, and Replenishment
    for rtype in ("orders", "inventory", "replenishment"):
        csv_res = client.get(
            f"/api/v1/reports/export-csv?report_type={rtype}",
            headers=wh_headers,
        )
        assert csv_res.status_code == 200
        assert "text/csv" in csv_res.headers.get("content-type", "")
        assert len(csv_res.text) > 20


def test_bank_account_invoice_qr_payment_confirmation_and_after_sales_policy(client):
    mgr_headers = _login(client, "manager@soobin.vn")
    sales_headers = _login(client, "sales@soobin.vn")
    cust_headers = _login(client, "customer@soobin.vn")

    # 1. Manager configures Shop Owner Bank Account
    put_bank = client.put(
        "/api/v1/site-settings/bank-account",
        headers=mgr_headers,
        json={
            "bank_code": "VCB",
            "bank_name": "Vietcombank (Ngân hàng Ngoại Thương)",
            "account_no": "9988776655",
            "account_name": "NGUYEN SOOBIN OWNER",
            "bank_branch": "Chi nhánh Quận 1, TP.HCM",
            "transfer_prefix": "SOOBINPAY",
            "qr_template": "compact2",
            "auto_confirm_webhook": True,
        },
    )
    assert put_bank.status_code == 200, put_bank.text
    bank_cfg = put_bank.json()
    assert bank_cfg["account_no"] == "9988776655"
    assert bank_cfg["bank_code"] == "VCB"

    # 2. Customer creates an order -> Verify Order & Electronic Invoice automatically take Owner's Bank Account + Order Price
    ord1_res = client.post(
        "/api/v1/orders",
        headers=cust_headers,
        json={
            "recipient_name": "Khách Chuyển Khoản QR 1",
            "recipient_phone": "0912345678",
            "shipping_address": "88 Đồng Khởi, Quận 1, TP.HCM",
            "payment_method": "VIETQR",
            "guest_items": [{"variant_id": 1, "quantity": 1}],
        },
    )
    assert ord1_res.status_code == 200, ord1_res.text
    ord1 = ord1_res.json()
    ord1_id = ord1["order_id"]
    ord1_code = ord1["order_code"]
    ord1_amount = int(round(ord1["total_amount"]))

    assert ord1["bank_account"]["account_no"] == "9988776655"
    assert ord1["bank_account"]["account_name"] == "NGUYEN SOOBIN OWNER"
    assert f"amount={ord1_amount}" in ord1["payment_qr_url"]
    assert "VCB-9988776655" in ord1["payment_qr_url"]
    assert ord1_code in ord1["transfer_content"]

    # Open Invoice by order_id even before GHTK delivery -> verify invoice has Owner's Bank Account + Order Total QR
    inv_res = client.get(f"/api/v1/orders/invoices/{ord1_id}", headers=mgr_headers)
    assert inv_res.status_code == 200, inv_res.text
    inv = inv_res.json()
    assert inv["order_code"] == ord1_code
    assert inv["bank_account"]["account_no"] == "9988776655"
    assert f"amount={ord1_amount}" in inv["payment_qr_url"]

    # 3. Payment Confirmation Method A: Customer reports transfer -> Manager/Sales confirms 1-click
    rep_res = client.post(
        f"/api/v1/orders/{ord1_id}/customer-report-transfer",
        headers=cust_headers,
        json={
            "transaction_ref": "FT261102998877",
            "transfer_note": "Em đã chuyển khoản đủ qua VCB",
            "auto_verify": False,
        },
    )
    assert rep_res.status_code == 200, rep_res.text
    assert rep_res.json()["payment_status"] == "PENDING_VERIFICATION"

    cfm_res = client.post(
        f"/api/v1/orders/{ord1_id}/confirm-payment",
        headers=sales_headers,
        json={
            "transaction_ref": "FT261102998877",
            "transfer_amount": ord1_amount,
            "note": "Sales đã kiểm tra sao kê VCB nhận đủ tiền",
        },
    )
    assert cfm_res.status_code == 200, cfm_res.text
    assert cfm_res.json()["payment_status"] == "PAID"

    # 4. Payment Confirmation Method B: Real Bank Webhook (SePay / Casso / VietQR) auto-matches order code & amount
    ord2_res = client.post(
        "/api/v1/orders",
        headers=cust_headers,
        json={
            "recipient_name": "Khách Webhook Tự Động",
            "recipient_phone": "0987654321",
            "shipping_address": "99 Lê Lợi, Quận 1, TP.HCM",
            "payment_method": "VIETQR",
            "guest_items": [{"variant_id": 2, "quantity": 1}],
        },
    )
    assert ord2_res.status_code == 200, ord2_res.text
    ord2 = ord2_res.json()
    ord2_code = ord2["order_code"]
    ord2_amount = ord2["total_amount"]

    wh_res = client.post(
        "/api/v1/orders/payments/bank-webhook",
        json={
            "gateway": "SEPAY_VCB",
            "content": f"MBVCB.991122.SOOBINPAY {ord2_code} chuyen tien mua do boi",
            "transfer_amount": ord2_amount,
            "transaction_id": "VCB-AUTO-991122",
            "account_number": "9988776655",
        },
    )
    assert wh_res.status_code == 200, wh_res.text
    assert wh_res.json()["payment_status"] == "PAID"
    assert wh_res.json()["order_code"] == ord2_code

    # 5. Manager sets up Return / Size Exchange / Warranty Windows & tests RMA Routing + Time Limit Enforcement
    put_policy = client.put(
        "/api/v1/site-settings/after-sales-policy",
        headers=mgr_headers,
        json={
            "return_window_days": 10,
            "exchange_size_window_days": 20,
            "warranty_window_days": 45,
            "vietqr_payment_timeout_hours": 24,
            "enforce_time_limit": True,
            "allow_Completed_statuses": ["Đã giao", "Đã xử lý", "Đang vận chuyển"],
            "receiving_roles": ["SALES", "MANAGER", "ADMIN", "WAREHOUSE"],
            "warranty_terms": "Đổi size 20 ngày, bảo hành đường may 45 ngày, trả hàng hoàn tiền 10 ngày.",
        },
    )
    assert put_policy.status_code == 200, put_policy.text
    assert put_policy.json()["warranty_window_days"] == 45

    # Customer submits a WARRANTY request within the 45-day window
    war_res = client.post(
        f"/api/v1/orders/{ord1_id}/exchange-request",
        headers=cust_headers,
        json={
            "target_size": "M",
            "preferred_resolution": "WARRANTY",
            "reason": "Khóa kéo sau lưng hơi rít, nhờ shop bảo hành giúp mình.",
        },
    )
    assert war_res.status_code == 200, war_res.text
    war_data = war_res.json()
    ticket_code = war_data["ticket_code"]
    assert war_data["allowed_window_days"] == 45
    assert "SALES" in war_data["receiving_roles"]
    assert "MANAGER" in war_data["receiving_roles"]

    # Both Sales and Manager can view and process the RMA request
    rma_list_sales = client.get("/api/v1/orders/rma/requests", headers=sales_headers)
    assert rma_list_sales.status_code == 200
    assert any(r["ticket_id"] == ticket_code for r in rma_list_sales.json())

    upd_rma_sales = client.put(
        f"/api/v1/orders/rma/requests/{ticket_code}",
        headers=sales_headers,
        json={
            "status": "RECEIVED_BY_SALES",
            "resolution_note": "Sales đã liên hệ khách hướng dẫn gửi hàng về kho bảo hành",
        },
    )
    assert upd_rma_sales.status_code == 200
    assert upd_rma_sales.json()["ticket"]["status"] == "RECEIVED_BY_SALES"

    upd_rma_mgr = client.put(
        f"/api/v1/orders/rma/requests/{ticket_code}",
        headers=mgr_headers,
        json={
            "status": "APPROVED",
            "resolution_note": "Quản lý phê duyệt bảo hành miễn phí khóa kéo",
        },
    )
    assert upd_rma_mgr.status_code == 200
    assert upd_rma_mgr.json()["ticket"]["status"] == "APPROVED"


def test_creative_frontend_tech_stack_and_aceternity_ui(client):
    # 1. Verify vendor bundles & creative engine static assets
    for asset_path in (
        "/static/vendor/lenis.min.js",
        "/static/vendor/gsap.min.js",
        "/static/vendor/ScrollTrigger.min.js",
        "/static/vendor/Flip.min.js",
        "/static/vendor/split-type.min.js",
        "/static/css/creative-ui.css",
        "/static/js/creative-engine.js",
    ):
        res = client.get(asset_path)
        assert res.status_code == 200, f"Missing creative asset: {asset_path}"
        assert len(res.text) > 100

    # 2. Verify all 5 web portals include the Creative Tech Stack & Aquatic Ocean Theme
    for route in ("/", "/manager", "/sales", "/warehouse", "/admin"):
        page = client.get(route)
        assert page.status_code == 200
        assert "lenis.min.js" in page.text
        assert "gsap.min.js" in page.text
        assert "ScrollTrigger.min.js" in page.text
        assert "creative-engine.js" in page.text

    # 3. Verify Home Storefront has NO Intro / NO Curtain, NO admin/management links, Cool Aqua Theme, quick price filters, and celebration audio
    home_html = client.get("/").text
    app_js = client.get("/static/js/app.js").text
    assert "soobinCinematicIntro" not in home_html
    assert "soobinTransitionCurtain" not in home_html
    assert 'href="/login"' in home_html
    assert 'href="/staff/login"' not in home_html
    assert 'href="/admin"' not in home_html
    assert 'href="/manager"' not in home_html
    assert 'href="/warehouse"' not in home_html
    assert 'href="/sales"' not in home_html
    assert "Cổng Quản Trị Nội Bộ" not in home_html
    assert "Cổng Nội Bộ" not in home_html
    assert "sfxToggleBtn" in home_html
    assert "applyQuickPriceRange" in home_html
    assert "handleBuyNowFromModal" in app_js
    assert "getCustomerAuthHeaders" in app_js
    assert "successThankYouCustomerMsg" in home_html
    assert "soobinBentoShowcase" not in home_html
    assert "soobinCmdkModal" not in home_html
    assert "authModal" not in home_html
    assert "swimwear3d.js" not in home_html

    for audio_path in (
        "/static/audio/water_select.wav",
        "/static/audio/order_celebration.wav",
    ):
        audio_res = client.get(audio_path)
        assert audio_res.status_code == 200, f"Missing audio asset: {audio_path}"
        assert len(audio_res.content) > 10000


def test_aquatic_login_pages_diverse_multi_image_catalog_and_upgraded_pos(client):
    sales_headers = _login(client, "sales@soobin.vn")

    # 1. Verify separated Customer Login (/login) & Staff Login (/staff/login) pages with zero management references on customer login
    cust_login_page = client.get("/login")
    assert cust_login_page.status_code == 200
    assert "creative-engine.js" in cust_login_page.text
    assert 'href="/staff/login"' not in cust_login_page.text
    assert "Cổng Quản Lý / Nhân Sự" not in cust_login_page.text

    for staff_route in ("/staff/login", "/sales/login", "/manager/login", "/warehouse/login", "/admin/login"):
        staff_res = client.get(staff_route)
        assert staff_res.status_code == 200
        assert "creative-engine.js" in staff_res.text

    # Customer login succeeds on CUSTOMER portal and is blocked on staff portals
    c_ok = client.post(
        "/api/v1/auth/portal-login",
        json={"email_or_phone": "customer@soobin.vn", "password": "Password123@", "portal": "CUSTOMER"},
    )
    assert c_ok.status_code == 200
    assert c_ok.json()["user"]["role_code"] == "CUSTOMER"
    assert c_ok.json()["redirect_url"] == "/"

    c_blocked = client.post(
        "/api/v1/auth/portal-login",
        json={"email_or_phone": "customer@soobin.vn", "password": "Password123@", "portal": "MANAGER"},
    )
    assert c_blocked.status_code == 403

    # Staff roles succeed on their staff portals and are strictly blocked on the CUSTOMER portal (/login)
    for email, expected_role, expected_redirect in (
        ("manager@soobin.vn", "MANAGER", "/manager"),
        ("sales@soobin.vn", "SALES", "/sales"),
        ("warehouse@soobin.vn", "WAREHOUSE", "/warehouse"),
        ("admin@soobin.vn", "ADMIN", "/admin"),
    ):
        p_login = client.post(
            "/api/v1/auth/portal-login",
            json={"email_or_phone": email, "password": "Password123@", "portal": expected_role},
        )
        assert p_login.status_code == 200
        p_data = p_login.json()
        assert p_data["user"]["role_code"] == expected_role
        assert p_data["user"]["role"]["code"] == expected_role
        assert p_data["redirect_url"] == expected_redirect

        # Attempting to use a staff account on Customer portal (/login) must be rejected with 403
        cross_blocked = client.post(
            "/api/v1/auth/portal-login",
            json={"email_or_phone": email, "password": "Password123@", "portal": "CUSTOMER"},
        )
        assert cross_blocked.status_code == 403

    # 2. Verify diverse product catalog & multi-angle gallery images (100% authentic swimwear studio images, >= 4 gallery images)
    items = []
    for off in (0, 20, 40, 60, 80):
        page_res = client.get(f"/api/v1/catalog/products?limit=20&offset={off}")
        assert page_res.status_code == 200
        items.extend(page_res.json())
    assert len(items) == 100
    distinct_primary_images = {p["image_url"] for p in items}
    assert len(distinct_primary_images) >= 10
    valid_img_prefixes = ("/static/images/swim-", "/static/images/products/swim_", "/static/images/products/gen/")
    for p in items:
        assert p["image_url"].startswith(valid_img_prefixes), f"Invalid image URL: {p['image_url']}"
        assert "unsplash.com" not in p["image_url"]
        assert "gallery_images" in p
        assert len(p["gallery_images"]) >= 4
        for g_img in p["gallery_images"]:
            g_url = g_img["image_url"] if isinstance(g_img, dict) else g_img
            assert g_url.startswith(valid_img_prefixes), f"Invalid gallery URL: {g_url}"
            assert "unsplash.com" not in g_url

    # Spot-check that the generated studio swimwear image files are served with HTTP 200
    img_res = client.get(items[0]["image_url"])
    assert img_res.status_code == 200
    assert len(img_res.content) > 5000

    # Verify product detail also returns >= 4 images
    det_res = client.get(f"/api/v1/catalog/products/{items[0]['id']}")
    assert det_res.status_code == 200
    assert len(det_res.json()["images"]) >= 4

    # 3. Verify Inventory Balances for Sales POS include pricing & image fields
    bal_res = client.get("/api/v1/inventory/balances", headers=sales_headers)
    assert bal_res.status_code == 200
    balances = bal_res.json()
    assert len(balances) >= 50
    sample_bal = balances[0]
    assert "image_url" in sample_bal
    assert "base_price" in sample_bal
    assert "discounted_price" in sample_bal
    assert "category_name" in sample_bal

    # 4. Verify Sales POS UI includes live pricing calculator, cash tendered change calculator, and live VietQR counter preview
    sales_html = client.get("/sales").text
    assert "posLiveCalculatorBox" in sales_html
    assert "posCashCalculatorPanel" in sales_html
    assert "posVietqrPreviewPanel" in sales_html
    assert "aquatic-ocean-header" in sales_html

    # 5. Test POS Checkout with Voucher & VietQR payment method
    avail_var = next(b for b in balances if b["available_quantity"] >= 2)
    pos_qr_res = client.post(
        "/api/v1/orders/pos",
        headers=sales_headers,
        json={
            "customer_name": "Khách POS VietQR Bơi Lội",
            "customer_phone": "0905123456",
            "shipping_address": "Nhận trực tiếp tại Showroom Soobin Swimwear",
            "payment_method": "VIETQR",
            "fulfillment_type": "INSTORE_PICKUP",
            "items": [{"variant_id": avail_var["variant_id"], "quantity": 1}],
        },
    )
    assert pos_qr_res.status_code == 201, pos_qr_res.text
    pos_qr_order = pos_qr_res.json()["order"]
    assert pos_qr_order["payment_method"] == "VIETQR"
    assert "payment_qr_url" in pos_qr_order
    assert pos_qr_order["total_amount"] > 0


def test_expanded_management_role_features(client):
    mgr_headers = _login(client, "manager@soobin.vn")
    sales_headers = _login(client, "sales@soobin.vn")
    wh_headers = _login(client, "warehouse@soobin.vn")
    admin_headers = _login(client, "admin@soobin.vn")

    # 1. Manager: Executive KPI endpoint
    kpi_res = client.get("/api/v1/reports/executive-kpi", headers=mgr_headers)
    assert kpi_res.status_code == 200, kpi_res.text
    kpi = kpi_res.json()
    assert "average_order_value" in kpi
    assert "fulfillment_rate_percent" in kpi
    assert "total_inventory_cost_value" in kpi
    assert "low_stock_variants_count" in kpi

    # 2. Manager: 1-Click Quick Voucher Creation
    v_code = f"AQUA{uuid.uuid4().hex[:4].upper()}"
    qv_res = client.post(
        "/api/v1/promotions/quick-voucher",
        headers=mgr_headers,
        json={
            "code": v_code,
            "name": "Ưu Đãi Mùa Bơi Mát Lạnh",
            "discount_type": "PERCENT",
            "discount_value": 18.0,
            "min_order_amount": 200000.0,
        },
    )
    assert qv_res.status_code == 200, qv_res.text
    assert qv_res.json()["voucher"]["code"] == v_code

    # 3. Sales: POS Shift Summary & Active Vouchers
    shift_res = client.get("/api/v1/orders/pos-shift-summary", headers=sales_headers)
    assert shift_res.status_code == 200, shift_res.text
    shift = shift_res.json()
    assert "pos_order_count" in shift
    assert "cash_revenue" in shift
    assert "vietqr_revenue" in shift
    assert "active_vouchers" in shift
    assert any(v["code"] == v_code for v in shift["active_vouchers"])

    # 4. Warehouse & Manager: Low-Stock Alerts & 1-Click Quick Restock
    alerts_res = client.get("/api/v1/inventory/low-stock-alerts", headers=wh_headers)
    assert alerts_res.status_code == 200, alerts_res.text
    alerts_data = alerts_res.json()
    assert "items" in alerts_data and isinstance(alerts_data["items"], list)

    restock_res = client.post(
        "/api/v1/inventory/quick-restock",
        headers=wh_headers,
        json={
            "variant_id": 1,
            "quantity": 10,
            "note": "Thủ kho nhập bổ sung nhanh từ bảng cảnh báo",
        },
    )
    assert restock_res.status_code == 200, restock_res.text
    assert restock_res.json()["added_quantity"] == 10
    assert restock_res.json()["new_available_quantity"] >= 10

    # 5. Admin: System Overview & Revoke User Sessions
    sys_res = client.get("/api/v1/admin/system-overview", headers=admin_headers)
    assert sys_res.status_code == 200, sys_res.text
    sys_data = sys_res.json()
    assert "total_accounts" in sys_data
    assert "active_sessions" in sys_data
    assert "accounts_by_role" in sys_data

    # Create a temporary customer session and revoke it via Admin endpoint
    cust_login = client.post(
        "/api/v1/auth/login",
        json={"email_or_phone": "customer@soobin.vn", "password": "Password123@"},
    )
    assert cust_login.status_code == 200
    cust_id = cust_login.json()["user"]["id"]

    revoke_res = client.post(
        f"/api/v1/admin/users/{cust_id}/revoke-sessions",
        headers=admin_headers,
    )
    assert revoke_res.status_code == 200, revoke_res.text
    assert revoke_res.json()["revoked_count"] >= 1

    # 6. Verify User Storefront has no top wave hero space and Role Portals have enhanced actions
    home_res = client.get("/")
    assert home_res.status_code == 200
    assert 'id="heroStageSection"' not in home_res.text
    assert 'id="heroThreeAtmosphereCanvas"' not in home_res.text

    sales_page = client.get("/sales")
    assert sales_page.status_code == 200
    assert "bulkConfirmEligibleSalesOrders" in sales_page.text
    assert "updateGhtkShipmentStatus" in sales_page.text
    assert "bulkDeliverActiveShipments" in sales_page.text

    mgr_page = client.get("/manager")
    assert mgr_page.status_code == 200
    assert "bulkApproveAiReplenishment" in mgr_page.text
    assert "bulkConfirmManagerOrders" in mgr_page.text
    assert "bulkApproveAllRefunds" in mgr_page.text

    wh_page = client.get("/warehouse")
    assert wh_page.status_code == 200
    assert "bulkQuickRestockAllLowStock" in wh_page.text
    assert "renderInventoryMovementsTable" in wh_page.text

    adm_page = client.get("/admin")
    assert adm_page.status_code == 200
    assert "renderAdminUsersTable" in adm_page.text
    assert "triggerExpiredVietqrOrdersAdmin" in adm_page.text


def test_storefront_cover_showcase_hot_trending_sale(client):
    # Public endpoint, no auth required
    res = client.get("/api/v1/catalog/showcase?per_rail=8")
    assert res.status_code == 200, res.text
    data = res.json()
    for key in ("hot", "trending", "sale", "stats", "sale_ends_at"):
        assert key in data
    assert 0 < len(data["hot"]) <= 8
    assert len(data["trending"]) <= 8
    assert data["stats"]["total_products"] >= len(data["hot"])

    for item in data["hot"] + data["trending"] + data["sale"]:
        for field in ("id", "slug", "name", "image_url", "base_price", "discounted_price",
                      "discount_percent", "total_stock", "sold_count", "avg_rating", "review_count"):
            assert field in item

    # Hot rail is ordered by units sold (desc)
    sold = [p["sold_count"] for p in data["hot"]]
    assert sold == sorted(sold, reverse=True)

    # Sale rail contains only discounted products ordered by discount (desc)
    pcts = [p["discount_percent"] for p in data["sale"]]
    assert all(p > 0 for p in pcts)
    assert pcts == sorted(pcts, reverse=True)

    # Hot items in top-4 are not duplicated in Trending
    top_hot_ids = {p["id"] for p in data["hot"][:4]}
    assert not top_hot_ids.intersection({p["id"] for p in data["trending"]}) or len(data["trending"]) <= 4

    # Storefront page is wired with cover, pinned showcase, flash sale and motion engine
    home = client.get("/")
    assert home.status_code == 200
    for marker in ('id="storeCover"', 'id="showcaseHot"', 'id="showcaseTrack"', 'id="flashSaleSection"',
                   'id="saleRail"', "data-zoom-reveal", "storefront-motion.js", "storefront-motion.css"):
        assert marker in home.text

    js = client.get("/static/js/storefront-motion.js")
    assert js.status_code == 200
    for fn in ("revealCards", "setupShowcaseMotion", "containerAnimation", "initZoomReveal", "bindDragRail"):
        assert fn in js.text


def test_storefront_home_showcase_and_shop_view_are_separated(client):
    """Trang chủ chỉ trình diễn (zoom/Three.js), lưới sản phẩm chỉ nằm trong view danh mục."""
    html = client.get("/").text

    # Two views: showcase home + category shop; product grid only lives in the shop view
    home_at, shop_at = html.index('id="homeView"'), html.index('id="shopView"')
    assert home_at < shop_at
    assert html.index('id="productGrid"') > shop_at
    assert html.index('id="catalogGrid"') > shop_at
    home_markup = html[home_at:shop_at]
    assert "productGrid" not in home_markup
    for marker in ('id="storeCover"', 'id="oceanCanvas"', 'id="beachZoom"', 'id="homeCategories"', "data-zoom-reveal"):
        assert marker in home_markup
    # Shop view has no zoom-reveal hooks
    assert "data-zoom-reveal" not in html[shop_at:html.index('id="productPagination"')]

    # Category entry points route to the shop view
    for route in ("#/shop/do-boi-nu", "#/shop/do-boi-nam", "#/shop/phu-kien-boi-loi", "#/shop/sale"):
        assert f'href="{route}"' in html

    # Three.js ocean stage + motion view switching are wired
    assert "three.min.js" in html and "ocean-stage.js" in html
    ocean = client.get("/static/js/ocean-stage.js")
    assert ocean.status_code == 200 and "WebGLRenderer" in ocean.text and "setDive" in ocean.text
    motion = client.get("/static/js/storefront-motion.js").text
    for fn in ("setView", "initCoverScroll", "initBeachZoom", "initCategoryZoom", "disableAllTriggers"):
        assert fn in motion
    app_js = client.get("/static/js/app.js").text
    for fn in ("initStorefrontRouter", "applyStorefrontRoute", "SHOP_ROUTES"):
        assert fn in app_js

    # Swimming & beach illustrations are served
    for name in ("sun", "cloud", "seagulls", "palm", "buoy", "goggles", "umbrella", "starfish",
                 "shell", "beachball", "swimmer", "pool-lanes", "surfboard", "medal", "fish"):
        res = client.get(f"/static/images/illustrations/{name}.svg")
        assert res.status_code == 200, name
        assert "<svg" in res.text







