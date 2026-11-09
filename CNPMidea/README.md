# Soobin Swimwear - Nền Tảng Thương Mại Điện Tử Đồ Bơi (Mô Hình MVC Python)

Dự án đồ án môn Công Nghệ Phần Mềm (CNPM) triển khai website thương mại điện tử chuyên đồ bơi **Soobin Swimwear** theo kiến trúc **MVC (Model - View - Controller)** và **3-layer (`Controller -> Service -> Repository`)** bằng ngôn ngữ **Python** và cơ sở dữ liệu **PostgreSQL** (database: `cnpm`).

---

## 1. Công Nghệ & Kiến Trúc MVC

- **Ngôn ngữ**: Python 3.11 / 3.12
- **Mô hình kiến trúc**: MVC (Model - View - Controller) & 3-layer:
  - **Model (`app/models/`, `app/repositories/`)**:
    - ORM Entities SQLAlchemy ánh xạ toàn diện 45 bảng cơ sở dữ liệu từ file `soobin_data_model.mmd`.
    - Data Access Object (Repository) xử lý đọc/ghi, row-level locking (`with_for_update()`), snapshot dữ liệu bất biến.
  - **View (`app/views/`, `app/static/`)**:
    - Giao diện người dùng Web responsive, phong cách sang trọng hiện đại (Ocean gradient, glassmorphism, Tailwind, Lucide icons, Modals).
    - **Storefront (`index.html`, `app.js`)**: Trang chủ, Mega menu, tìm kiếm, lọc theo giới tính/giá/outlet, bảng đo kích thước (size chart), giỏ hàng vãng lai/tài khoản, Danh sách yêu thích (Wishlist) kèm thông báo giảm giá, Sổ địa chỉ giao hàng, Đánh giá & nhận xét sản phẩm (1-5 sao), Xuất & In Hóa đơn điện tử, và **AI Chatbot tư vấn chọn size & đồ bơi thông minh**.
    - **Admin Portal (`admin.html`)**: Quản lý tài khoản nhân sự & người dùng, tạo Role tùy chỉnh & gán quyền RBAC, quản lý khuyến mãi (`PRODUCT`, `ORDER`, `VOUCHER`), kích hoạt tự động nhắc giỏ hàng bỏ quên quá 24h.
    - **Manager Portal (`manager.html`)**: Dashboard KPI tài chính (doanh thu, lợi nhuận gộp snapshot COGS), xử lý đơn hàng, xuất hóa đơn điện tử, danh sách chờ hoàn tiền, quản lý danh mục sản phẩm, kiểm duyệt đánh giá sản phẩm (`APPROVED`/`HIDDEN`), quản lý băng rôn cửa hàng.
    - **Warehouse Portal (`warehouse.html`)**: Quản lý tồn kho 248 biến thể, lập & xác nhận phiếu nhập hàng (tự động tính giá vốn bình quân gia quyền), lập **Phiếu điều chỉnh phiếu nhập** cho phiếu đã chốt (AC-INV-03), và xem nhật ký biến động kho (`Movements`).
    - **GHTK Mock Carrier Portal (`ghtk.html`)**: Website riêng tại cổng 8001, giả lập đối tác vận chuyển GHTK và phát webhook lấy hàng/giao hàng.
    - **VietQR Mock Payment Portal (`mock_payment.html`)**: Giả lập ngân hàng MBBank báo có tiền chuyển khoản 1-click.
  - **Controller (`app/controllers/`)**:
    - Router FastAPI tiếp nhận HTTP request, xác thực session cookie & token header, phân quyền RBAC, điều phối business logic tầng Service và trả về HTML View hoặc JSON API.
  - **Business Logic Layer (`app/services/`)**:
    - Quản lý ranh giới giao dịch (Transaction boundary), thuật toán so sánh 3 phương án khuyến mãi (PRD Mục 7), tính giá vốn bình quân gia quyền & phiếu điều chỉnh (PRD Mục 8), trạng thái đơn hàng & hóa đơn điện tử (PRD Mục 9), AI Size Advisor, Wishlist & Abandoned Cart Reminder, idempotency webhook.

---

## 2. Cấu Trúc Cơ Sở Dữ Liệu PostgreSQL (`cnpm`)

Cơ sở dữ liệu gồm 45 bảng chuẩn hóa theo `soobin_data_model.mmd` và PRD v0.2:
1. **Identity & Access**: `user_account`, `user_role`, `user_permission`, `user_role_permission`, `user_identity`, `user_session`, `user_action_token`, `user_address`.
2. **Catalog**: `production_category`, `production_product_line`, `production_size`, `production_color`, `production_material`, `production_product`, `production_variant`, `production_product_material`, `production_collection`, `production_product_collection`, `production_product_image`.
3. **Inventory & Procurement**: `production_supplier`, `production_goods_receipt`, `production_goods_receipt_item`, `production_inventory`, `production_inventory_movement`.
4. **Commerce**: `production_cart_item`, `production_wishlist_item`, `production_promotion`, `production_promotion_product`, `production_order`, `production_order_item`, `production_order_discount_option`, `production_voucher_usage`, `production_order_history`, `production_review`.
5. **Payment, Shipping, Invoices & Reliability**: `production_payment`, `production_shipment`, `production_invoice`, `production_invoice_item`, `production_integration_event`, `production_outbox_event`, `production_idempotency_request`.
6. **Content & Settings**: `production_content`, `production_content_block`, `production_site_setting`, `production_feedback`.

---

## 3. Tài Khoản Demo Sẵn Có

Mật khẩu mặc định cho toàn bộ tài khoản demo: `Password123@`

| Vai trò | Email đăng nhập | Số điện thoại | Quyền hạn |
| :--- | :--- | :--- | :--- |
| **Quản trị viên (Admin)** | `admin@soobin.vn` | `0901234567` | Toàn quyền hệ thống, quản lý nhân sự, tạo Role & phân quyền RBAC, khuyến mãi |
| **Quản lý cửa hàng (Manager)** | `manager@soobin.vn` | `0902345678` | Vận hành sản phẩm, xử lý đơn, xuất hóa đơn, hoàn tiền, kiểm duyệt đánh giá, KPI |
| **Thủ kho (Warehouse)** | `warehouse@soobin.vn` | `0905678901` | Quản lý tồn kho, lập phiếu nhập hàng, lập phiếu điều chỉnh, theo dõi biến động kho |
| **Nhân viên bán hàng (Sales)** | `sales@soobin.vn` | `0906789012` | Xử lý đơn hàng, hỗ trợ khách hàng |
| **Khách hàng (Customer)** | `customer@soobin.vn` | `0903456789` | Mua hàng COD/VietQR, Wishlist, Sổ địa chỉ, Đánh giá SP, Xem & In hóa đơn điện tử |
| **Khách chưa xác minh** | `customer2@soobin.vn` | `0904567890` | Chưa xác minh email (kiểm thử chặn đặt hàng AC-AUTH-05) |

---

## 4. Hướng Dẫn Khởi Chạy Ứng Dụng

### Khởi chạy Server
```bash
# Sử dụng môi trường ảo Python đã thiết lập
& "backend\.venv-runtime\Scripts\python.exe" run.py
```

### Các đường dẫn truy cập:
- **Trang chủ Storefront**: `http://localhost:8000/`
- **Trang Quản trị Hệ thống (ADMIN)**: `http://localhost:8000/admin`
- **Trang Quản lý Cửa hàng (MANAGER)**: `http://localhost:8000/manager`
- **Trang Thủ kho (WAREHOUSE)**: `http://localhost:8000/warehouse`
- **Trang Bán hàng (SALES)**: `http://localhost:8000/sales`
- **Cổng GHTK riêng**: `http://localhost:8001/`
- **Cổng Giả Lập Thanh Toán VietQR**: `http://localhost:8000/mock-payment`
- **Tài liệu API Swagger**: `http://localhost:8000/docs`

---

## 5. Kết Quả Kiểm Thử Tự Động (30/30 Test Cases Passed)

Bộ kiểm thử tự động gồm **30/30 test case đạt 100% (Passed)** bao phủ toàn bộ các tiêu chí nghiệm thu trong PRD và các tính năng nâng cao:

```text
backend/tests/test_ai_advisor_and_cart_reminders.py::test_ai_size_advisor_explicit_and_natural_language PASSED
backend/tests/test_ai_advisor_and_cart_reminders.py::test_abandoned_cart_reminder_over_24h PASSED
backend/tests/test_auth_and_rbac.py::test_auth_login_success PASSED
backend/tests/test_auth_and_rbac.py::test_auth_login_invalid_password PASSED
backend/tests/test_auth_and_rbac.py::test_auth_register_and_verify PASSED
backend/tests/test_auth_and_rbac.py::test_ac_auth_05_unverified_email_cannot_place_order PASSED
backend/tests/test_auth_and_rbac.py::test_ac_auth_02_locked_account_takes_immediate_effect PASSED
backend/tests/test_auth_and_rbac.py::test_protect_last_active_admin PASSED
backend/tests/test_catalog_and_cart.py::test_catalog_categories_and_products PASSED
backend/tests/test_catalog_and_cart.py::test_catalog_filter_by_audience PASSED
backend/tests/test_catalog_and_cart.py::test_catalog_outlet_on_sale PASSED
backend/tests/test_catalog_and_cart.py::test_cart_operations PASSED
backend/tests/test_catalog_and_cart.py::test_ac_br_prd_cart_guest_merge_and_stock_adjustment PASSED
backend/tests/test_goods_receipt_adjustment.py::test_ac_inv_03_block_direct_modify_or_delete_confirmed_receipt PASSED
backend/tests/test_goods_receipt_adjustment.py::test_goods_receipt_adjustment_flow_and_prevent_negative_stock PASSED
backend/tests/test_inventory_receipts.py::test_ac_inv_05_weighted_average_cost_calculation PASSED
backend/tests/test_inventory_receipts.py::test_goods_receipts_confirmed_locked_and_viewable PASSED
backend/tests/test_orders_and_concurrency.py::test_order_creation_and_stock_deduction PASSED
backend/tests/test_orders_and_concurrency.py::test_ac_auth_01_customer_cannot_view_or_cancel_other_order PASSED
backend/tests/test_orders_and_concurrency.py::test_ac_chk_01_e2e_06_concurrency_race_condition PASSED
backend/tests/test_promotions.py::test_prd_section_7_exact_promotion_example PASSED
backend/tests/test_promotions.py::test_promotion_tie_breaker_product_over_order_over_voucher PASSED
backend/tests/test_promotions.py::test_rounding_to_dong PASSED
backend/tests/test_rbac_staff_and_addresses.py::test_admin_create_and_update_staff_account PASSED
backend/tests/test_rbac_staff_and_addresses.py::test_admin_create_and_update_custom_role_and_protect_system_role PASSED
backend/tests/test_rbac_staff_and_addresses.py::test_customer_address_book_crud PASSED
backend/tests/test_shipping_and_payment_mocks.py::test_full_vietqr_flow_to_delivery_and_invoice PASSED
backend/tests/test_shipping_and_payment_mocks.py::test_paid_vietqr_delivery_failed_triggers_refund_pending PASSED
backend/tests/test_wishlist_reviews_and_invoices.py::test_wishlist_toggle_and_discount_notification PASSED
backend/tests/test_wishlist_reviews_and_invoices.py::test_reviews_and_invoices_full_lifecycle PASSED

======================= 30 passed in 10.81s ========================
```

Để chạy lại toàn bộ test:
```bash
& "backend\.venv-runtime\Scripts\pytest.exe" -v backend/tests
```
