-- =============================================================================
-- Soobin Swimwear - PostgreSQL Database Schema DDL
-- Database name: cnpm
-- Matches soobin_data_model.mmd and PRD v0.2
-- =============================================================================

-- Drop tables in reverse dependency order if re-initializing
DROP TABLE IF EXISTS production_feedback CASCADE;
DROP TABLE IF EXISTS production_site_setting CASCADE;
DROP TABLE IF EXISTS production_content_block CASCADE;
DROP TABLE IF EXISTS production_content CASCADE;
DROP TABLE IF EXISTS production_idempotency_request CASCADE;
DROP TABLE IF EXISTS production_outbox_event CASCADE;
DROP TABLE IF EXISTS production_integration_event CASCADE;
DROP TABLE IF EXISTS production_invoice_item CASCADE;
DROP TABLE IF EXISTS production_invoice CASCADE;
DROP TABLE IF EXISTS production_shipment CASCADE;
DROP TABLE IF EXISTS production_payment CASCADE;
DROP TABLE IF EXISTS production_review CASCADE;
DROP TABLE IF EXISTS production_order_history CASCADE;
DROP TABLE IF EXISTS production_voucher_usage CASCADE;
DROP TABLE IF EXISTS production_order_discount_option CASCADE;
DROP TABLE IF EXISTS production_order_item CASCADE;
DROP TABLE IF EXISTS production_order CASCADE;
DROP TABLE IF EXISTS production_promotion_product CASCADE;
DROP TABLE IF EXISTS production_promotion CASCADE;
DROP TABLE IF EXISTS production_wishlist_item CASCADE;
DROP TABLE IF EXISTS production_cart_item CASCADE;
DROP TABLE IF EXISTS production_inventory_movement CASCADE;
DROP TABLE IF EXISTS production_inventory CASCADE;
DROP TABLE IF EXISTS production_goods_receipt_item CASCADE;
DROP TABLE IF EXISTS production_goods_receipt CASCADE;
DROP TABLE IF EXISTS production_supplier CASCADE;
DROP TABLE IF EXISTS production_product_image CASCADE;
DROP TABLE IF EXISTS production_product_collection CASCADE;
DROP TABLE IF EXISTS production_collection CASCADE;
DROP TABLE IF EXISTS production_product_material CASCADE;
DROP TABLE IF EXISTS production_material CASCADE;
DROP TABLE IF EXISTS production_variant CASCADE;
DROP TABLE IF EXISTS production_product CASCADE;
DROP TABLE IF EXISTS production_color CASCADE;
DROP TABLE IF EXISTS production_size CASCADE;
DROP TABLE IF EXISTS production_product_line CASCADE;
DROP TABLE IF EXISTS production_category CASCADE;
DROP TABLE IF EXISTS user_address CASCADE;
DROP TABLE IF EXISTS user_action_token CASCADE;
DROP TABLE IF EXISTS user_session CASCADE;
DROP TABLE IF EXISTS user_identity CASCADE;
DROP TABLE IF EXISTS user_role_permission CASCADE;
DROP TABLE IF EXISTS user_permission CASCADE;
DROP TABLE IF EXISTS user_account CASCADE;
DROP TABLE IF EXISTS user_role CASCADE;

-- -----------------------------------------------------------------------------
-- 1. USER & ACCESS CONTROL
-- -----------------------------------------------------------------------------

CREATE TABLE user_role (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE user_account (
    id BIGSERIAL PRIMARY KEY,
    role_id BIGINT NOT NULL REFERENCES user_role(id),
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(30) UNIQUE,
    password_hash VARCHAR(255),
    full_name VARCHAR(150) NOT NULL,
    email_verified_at TIMESTAMPTZ,
    is_locked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE user_permission (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,
    description VARCHAR(255)
);

CREATE TABLE user_role_permission (
    role_id BIGINT NOT NULL REFERENCES user_role(id) ON DELETE CASCADE,
    permission_id BIGINT NOT NULL REFERENCES user_permission(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE user_identity (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    provider_subject VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_identity_provider UNIQUE (provider, provider_subject)
);

CREATE TABLE user_session (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    session_token_hash VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE user_action_token (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    purpose VARCHAR(50) NOT NULL, -- VERIFY_EMAIL, RESET_PASSWORD
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE user_address (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    recipient_name VARCHAR(150) NOT NULL,
    recipient_phone VARCHAR(30) NOT NULL,
    address_line TEXT NOT NULL,
    province_code VARCHAR(50),
    district_code VARCHAR(50),
    ward_code VARCHAR(50),
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 2. CATALOG
-- -----------------------------------------------------------------------------

CREATE TABLE production_category (
    id BIGSERIAL PRIMARY KEY,
    parent_id BIGINT REFERENCES production_category(id) ON DELETE SET NULL,
    name VARCHAR(150) NOT NULL,
    slug VARCHAR(150) UNIQUE NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE production_product_line (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(150) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE production_size (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(50) NOT NULL,
    sort_order INT NOT NULL DEFAULT 0
);

CREATE TABLE production_color (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(50) NOT NULL,
    hex_code VARCHAR(20) NOT NULL
);

CREATE TABLE production_material (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL
);

CREATE TABLE production_product (
    id BIGSERIAL PRIMARY KEY,
    category_id BIGINT NOT NULL REFERENCES production_category(id),
    product_line_id BIGINT REFERENCES production_product_line(id) ON DELETE SET NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    slug VARCHAR(150) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    base_price NUMERIC(12, 2) NOT NULL CHECK (base_price >= 0),
    target_audience VARCHAR(50) NOT NULL, -- Nam, Nữ, Trẻ em, Unisex
    skill_level VARCHAR(50), -- Mới tập bơi, Bơi lội thể thao, Chuyên nghiệp
    description TEXT,
    care_instructions TEXT,
    specifications JSONB DEFAULT '{}'::jsonb,
    size_chart JSONB DEFAULT '{}'::jsonb,
    tags TEXT[] DEFAULT '{}',
    status VARCHAR(50) NOT NULL DEFAULT 'Selling', -- Selling, Discontinued
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE production_variant (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES production_product(id) ON DELETE CASCADE,
    size_id BIGINT NOT NULL REFERENCES production_size(id),
    color_id BIGINT NOT NULL REFERENCES production_color(id),
    sku VARCHAR(100) UNIQUE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_product_size_color UNIQUE (product_id, size_id, color_id)
);

CREATE TABLE production_product_material (
    product_id BIGINT NOT NULL REFERENCES production_product(id) ON DELETE CASCADE,
    material_id BIGINT NOT NULL REFERENCES production_material(id) ON DELETE CASCADE,
    PRIMARY KEY (product_id, material_id)
);

CREATE TABLE production_collection (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    slug VARCHAR(150) UNIQUE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE production_product_collection (
    product_id BIGINT NOT NULL REFERENCES production_product(id) ON DELETE CASCADE,
    collection_id BIGINT NOT NULL REFERENCES production_collection(id) ON DELETE CASCADE,
    PRIMARY KEY (product_id, collection_id)
);

CREATE TABLE production_product_image (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES production_product(id) ON DELETE CASCADE,
    color_id BIGINT REFERENCES production_color(id) ON DELETE SET NULL,
    file_path VARCHAR(500) NOT NULL,
    alt_text VARCHAR(255),
    sort_order INT NOT NULL DEFAULT 0
);

-- -----------------------------------------------------------------------------
-- 3. INVENTORY & PROCUREMENT
-- -----------------------------------------------------------------------------

CREATE TABLE production_supplier (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(30),
    email VARCHAR(255),
    address TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE production_goods_receipt (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    supplier_id BIGINT NOT NULL REFERENCES production_supplier(id),
    confirmed_by BIGINT NOT NULL REFERENCES user_account(id),
    confirmed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    supplier_snapshot JSONB NOT NULL,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE production_goods_receipt_item (
    id BIGSERIAL PRIMARY KEY,
    receipt_id BIGINT NOT NULL REFERENCES production_goods_receipt(id) ON DELETE CASCADE,
    variant_id BIGINT NOT NULL REFERENCES production_variant(id),
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_cost NUMERIC(12, 2) NOT NULL CHECK (unit_cost >= 0),
    variant_snapshot JSONB NOT NULL
);

CREATE TABLE production_inventory (
    variant_id BIGINT PRIMARY KEY REFERENCES production_variant(id) ON DELETE CASCADE,
    available_quantity INT NOT NULL DEFAULT 0 CHECK (available_quantity >= 0),
    inventory_value NUMERIC(14, 2) NOT NULL DEFAULT 0 CHECK (inventory_value >= 0),
    low_stock_threshold INT NOT NULL DEFAULT 5,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE production_inventory_movement (
    id BIGSERIAL PRIMARY KEY,
    variant_id BIGINT NOT NULL REFERENCES production_variant(id),
    receipt_item_id BIGINT REFERENCES production_goods_receipt_item(id),
    order_item_id BIGINT,
    movement_type VARCHAR(50) NOT NULL, -- RECEIPT, ORDER_OUT, ORDER_CANCEL_RESTORE
    quantity_delta INT NOT NULL,
    value_delta NUMERIC(14, 2) NOT NULL,
    event_key VARCHAR(150) UNIQUE NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 4. COMMERCE (Cart, Wishlist, Promotions, Orders, Reviews)
-- -----------------------------------------------------------------------------

CREATE TABLE production_cart_item (
    account_id BIGINT NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    variant_id BIGINT NOT NULL REFERENCES production_variant(id) ON DELETE CASCADE,
    quantity INT NOT NULL CHECK (quantity > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (account_id, variant_id)
);

CREATE TABLE production_wishlist_item (
    account_id BIGINT NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES production_product(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (account_id, product_id)
);

CREATE TABLE production_promotion (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    promotion_type VARCHAR(50) NOT NULL, -- PRODUCT, ORDER, VOUCHER
    discount_percent NUMERIC(5, 2) NOT NULL CHECK (discount_percent >= 0 AND discount_percent < 100),
    minimum_order_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    usage_limit INT,
    used_count INT NOT NULL DEFAULT 0,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
  ALTER TABLE production_promotion ADD COLUMN IF NOT EXISTS eligible_customer_ids JSONB;

CREATE TABLE production_promotion_product (
    promotion_id BIGINT NOT NULL REFERENCES production_promotion(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES production_product(id) ON DELETE CASCADE,
    PRIMARY KEY (promotion_id, product_id)
);

CREATE TABLE production_order (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    account_id BIGINT NOT NULL REFERENCES user_account(id),
    status VARCHAR(50) NOT NULL, -- Chưa xử lý, Đã xử lý, Đang vận chuyển, Đã giao, Giao không thành công, Đã hủy, Chờ hoàn tiền, Đã hoàn tiền
    payment_method VARCHAR(50) NOT NULL, -- COD, VietQR
    selected_discount_type VARCHAR(50), -- PRODUCT, ORDER, VOUCHER, NONE
    subtotal NUMERIC(12, 2) NOT NULL CHECK (subtotal >= 0),
    discount_amount NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    shipping_fee NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (shipping_fee >= 0),
    total_amount NUMERIC(12, 2) NOT NULL CHECK (total_amount >= 0),
    refund_amount NUMERIC(12, 2) DEFAULT 0,
    recipient_snapshot JSONB NOT NULL,
    store_snapshot JSONB NOT NULL,
    payment_due_at TIMESTAMPTZ,
    placed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE production_order_item (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES production_order(id) ON DELETE CASCADE,
    variant_id BIGINT NOT NULL REFERENCES production_variant(id),
    promotion_id BIGINT REFERENCES production_promotion(id),
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
    unit_cost_snapshot NUMERIC(12, 2) NOT NULL CHECK (unit_cost_snapshot >= 0),
    allocated_discount_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    line_total NUMERIC(12, 2) NOT NULL CHECK (line_total >= 0),
    product_snapshot JSONB NOT NULL,
    promotion_snapshot JSONB
);

CREATE TABLE production_order_discount_option (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES production_order(id) ON DELETE CASCADE,
    promotion_id BIGINT REFERENCES production_promotion(id),
    option_type VARCHAR(50) NOT NULL, -- PRODUCT, ORDER, VOUCHER
    is_eligible BOOLEAN NOT NULL DEFAULT TRUE,
    discount_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    is_selected BOOLEAN NOT NULL DEFAULT FALSE,
    calculation_snapshot JSONB,
    CONSTRAINT uq_order_discount_option UNIQUE (order_id, option_type)
);

CREATE TABLE production_voucher_usage (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT UNIQUE NOT NULL REFERENCES production_order(id) ON DELETE CASCADE,
    promotion_id BIGINT NOT NULL REFERENCES production_promotion(id),
    consumed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    restored_at TIMESTAMPTZ
);

CREATE TABLE production_order_history (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES production_order(id) ON DELETE CASCADE,
    actor_account_id BIGINT REFERENCES user_account(id),
    event_type VARCHAR(50) NOT NULL,
    from_status VARCHAR(50),
    to_status VARCHAR(50) NOT NULL,
    reason TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE production_review (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES user_account(id),
    product_id BIGINT NOT NULL REFERENCES production_product(id) ON DELETE CASCADE,
    order_item_id BIGINT REFERENCES production_order_item(id),
    rating INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
    content TEXT NOT NULL,
    moderation_status VARCHAR(50) NOT NULL DEFAULT 'APPROVED', -- PENDING, APPROVED, REJECTED
    moderated_by BIGINT REFERENCES user_account(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 5. PAYMENT, SHIPPING, INVOICES, INTEGRATIONS
-- -----------------------------------------------------------------------------

CREATE TABLE production_payment (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT UNIQUE NOT NULL REFERENCES production_order(id) ON DELETE CASCADE,
    method VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL, -- PENDING, PAID, FAILED, REFUNDED
    expected_amount NUMERIC(12, 2) NOT NULL,
    received_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    external_transaction_id VARCHAR(100) UNIQUE,
    paid_at TIMESTAMPTZ,
    payment_instruction_snapshot JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE production_shipment (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT UNIQUE NOT NULL REFERENCES production_order(id) ON DELETE CASCADE,
    carrier VARCHAR(50) NOT NULL DEFAULT 'GHTK',
    tracking_code VARCHAR(100) UNIQUE,
    creation_status VARCHAR(50) NOT NULL DEFAULT 'CREATED', -- CREATED, CANCELLED
    delivery_status VARCHAR(50) NOT NULL DEFAULT 'WAITING_FOR_PICKUP', -- WAITING_FOR_PICKUP, IN_TRANSIT, DELIVERED, FAILED
    shipping_fee_snapshot NUMERIC(12, 2) NOT NULL,
    carrier_request_key VARCHAR(150) UNIQUE NOT NULL,
    delivered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE production_invoice (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT UNIQUE NOT NULL REFERENCES production_order(id) ON DELETE CASCADE,
    code VARCHAR(50) UNIQUE NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    subtotal NUMERIC(12, 2) NOT NULL,
    discount_amount NUMERIC(12, 2) NOT NULL,
    shipping_fee NUMERIC(12, 2) NOT NULL,
    total_amount NUMERIC(12, 2) NOT NULL,
    customer_snapshot JSONB NOT NULL,
    store_snapshot JSONB NOT NULL
);

CREATE TABLE production_invoice_item (
    id BIGSERIAL PRIMARY KEY,
    invoice_id BIGINT NOT NULL REFERENCES production_invoice(id) ON DELETE CASCADE,
    order_item_id BIGINT UNIQUE NOT NULL REFERENCES production_order_item(id),
    quantity INT NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL,
    discount_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    line_total NUMERIC(12, 2) NOT NULL,
    unit_cost_snapshot NUMERIC(12, 2) NOT NULL,
    product_snapshot JSONB NOT NULL,
    promotion_snapshot JSONB
);

CREATE TABLE production_integration_event (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT REFERENCES production_order(id) ON DELETE SET NULL,
    source VARCHAR(50) NOT NULL, -- SHIPPING_GHTK, PAYMENT_VIETQR
    external_event_id VARCHAR(150) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    processing_status VARCHAR(50) NOT NULL, -- PROCESSED, IGNORED, FAILED
    processing_result TEXT,
    attempt_count INT NOT NULL DEFAULT 1,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    CONSTRAINT uq_integration_source_event UNIQUE (source, external_event_id)
);

CREATE TABLE production_outbox_event (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT REFERENCES production_order(id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    event_key VARCHAR(150) UNIQUE NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    attempt_count INT NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE production_idempotency_request (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT REFERENCES user_account(id) ON DELETE SET NULL,
    operation VARCHAR(100) NOT NULL,
    idempotency_key VARCHAR(150) NOT NULL,
    request_hash VARCHAR(64) NOT NULL,
    status VARCHAR(50) NOT NULL, -- PENDING, SUCCESS, FAILED
    response_status INT,
    response_body JSONB,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_idempotency_op_key UNIQUE (operation, idempotency_key)
);

-- -----------------------------------------------------------------------------
-- 6. CONTENT, SETTINGS & FEEDBACK
-- -----------------------------------------------------------------------------

CREATE TABLE production_content (
    id BIGSERIAL PRIMARY KEY,
    author_id BIGINT REFERENCES user_account(id) ON DELETE SET NULL,
    content_type VARCHAR(50) NOT NULL, -- BLOG, STATIC_PAGE
    slug VARCHAR(150) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    cover_image_path VARCHAR(500),
    status VARCHAR(50) NOT NULL DEFAULT 'PUBLISHED',
    published_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE production_content_block (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,
    block_type VARCHAR(50) NOT NULL, -- banner, announcement, community, hot_keyword
    placement VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    starts_at TIMESTAMPTZ,
    ends_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE production_site_setting (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL
);

CREATE TABLE production_feedback (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT REFERENCES user_account(id) ON DELETE SET NULL,
    sender_name VARCHAR(150) NOT NULL,
    sender_email VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'NEW', -- NEW, RESOLVED
    handled_by BIGINT REFERENCES user_account(id) ON DELETE SET NULL,
    handled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
