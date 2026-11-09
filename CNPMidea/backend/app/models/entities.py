from datetime import datetime, timezone
from sqlalchemy import (
    Column, BigInteger, Integer, String, Text, Boolean, 
    Numeric, DateTime, ForeignKey, Table, UniqueConstraint, CheckConstraint
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship
from app.core.database import Base

# -----------------------------------------------------------------------------
# 1. USER & ACCESS CONTROL
# -----------------------------------------------------------------------------

class UserRolePermission(Base):
    __tablename__ = "user_role_permission"
    
    role_id = Column(BigInteger, ForeignKey("user_role.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column(BigInteger, ForeignKey("user_permission.id", ondelete="CASCADE"), primary_key=True)

class UserRole(Base):
    __tablename__ = "user_role"

    id = Column(BigInteger, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    users = relationship("UserAccount", back_populates="role")
    permissions = relationship("UserPermission", secondary="user_role_permission", back_populates="roles")

class UserPermission(Base):
    __tablename__ = "user_permission"

    id = Column(BigInteger, primary_key=True, index=True)
    code = Column(String(100), unique=True, nullable=False)
    description = Column(String(255))

    roles = relationship("UserRole", secondary="user_role_permission", back_populates="permissions")

class UserAccount(Base):
    __tablename__ = "user_account"

    id = Column(BigInteger, primary_key=True, index=True)
    role_id = Column(BigInteger, ForeignKey("user_role.id"), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(30), unique=True)
    password_hash = Column(String(255))
    full_name = Column(String(150), nullable=False)
    email_verified_at = Column(DateTime(timezone=True))
    is_locked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    role = relationship("UserRole", back_populates="users")
    addresses = relationship("UserAddress", back_populates="account", cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="account", cascade="all, delete-orphan")
    action_tokens = relationship("UserActionToken", back_populates="account", cascade="all, delete-orphan")
    cart_items = relationship("ProductionCartItem", back_populates="account", cascade="all, delete-orphan")
    orders = relationship("ProductionOrder", back_populates="account")

class UserIdentity(Base):
    __tablename__ = "user_identity"

    id = Column(BigInteger, primary_key=True, index=True)
    account_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)
    provider_subject = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (UniqueConstraint("provider", "provider_subject", name="uq_user_identity_provider"),)

class UserSession(Base):
    __tablename__ = "user_session"

    id = Column(BigInteger, primary_key=True, index=True)
    account_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False)
    session_token_hash = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    account = relationship("UserAccount", back_populates="sessions")

class UserActionToken(Base):
    __tablename__ = "user_action_token"

    id = Column(BigInteger, primary_key=True, index=True)
    account_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False)
    purpose = Column(String(50), nullable=False)
    token_hash = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    account = relationship("UserAccount", back_populates="action_tokens")

class UserAddress(Base):
    __tablename__ = "user_address"

    id = Column(BigInteger, primary_key=True, index=True)
    account_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False)
    recipient_name = Column(String(150), nullable=False)
    recipient_phone = Column(String(30), nullable=False)
    address_line = Column(Text, nullable=False)
    province_code = Column(String(50))
    district_code = Column(String(50))
    ward_code = Column(String(50))
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    account = relationship("UserAccount", back_populates="addresses")

# -----------------------------------------------------------------------------
# 2. CATALOG
# -----------------------------------------------------------------------------

class ProductionCategory(Base):
    __tablename__ = "production_category"

    id = Column(BigInteger, primary_key=True, index=True)
    parent_id = Column(BigInteger, ForeignKey("production_category.id", ondelete="SET NULL"))
    name = Column(String(150), nullable=False)
    slug = Column(String(150), unique=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    parent = relationship("ProductionCategory", remote_side=[id], backref="children")
    products = relationship("ProductionProduct", back_populates="category")

class ProductionProductLine(Base):
    __tablename__ = "production_product_line"

    id = Column(BigInteger, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(150), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    products = relationship("ProductionProduct", back_populates="product_line")

class ProductionSize(Base):
    __tablename__ = "production_size"

    id = Column(BigInteger, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(50), nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)

class ProductionColor(Base):
    __tablename__ = "production_color"

    id = Column(BigInteger, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(50), nullable=False)
    hex_code = Column(String(20), nullable=False)

class ProductionMaterial(Base):
    __tablename__ = "production_material"

    id = Column(BigInteger, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)

class ProductionProductMaterial(Base):
    __tablename__ = "production_product_material"

    product_id = Column(BigInteger, ForeignKey("production_product.id", ondelete="CASCADE"), primary_key=True)
    material_id = Column(BigInteger, ForeignKey("production_material.id", ondelete="CASCADE"), primary_key=True)

class ProductionCollection(Base):
    __tablename__ = "production_collection"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    slug = Column(String(150), unique=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class ProductionProductCollection(Base):
    __tablename__ = "production_product_collection"

    product_id = Column(BigInteger, ForeignKey("production_product.id", ondelete="CASCADE"), primary_key=True)
    collection_id = Column(BigInteger, ForeignKey("production_collection.id", ondelete="CASCADE"), primary_key=True)

class ProductionProduct(Base):
    __tablename__ = "production_product"

    id = Column(BigInteger, primary_key=True, index=True)
    category_id = Column(BigInteger, ForeignKey("production_category.id"), nullable=False)
    product_line_id = Column(BigInteger, ForeignKey("production_product_line.id", ondelete="SET NULL"))
    code = Column(String(50), unique=True, nullable=False)
    slug = Column(String(150), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    base_price = Column(Numeric(12, 2), nullable=False)
    target_audience = Column(String(50), nullable=False)
    skill_level = Column(String(50))
    description = Column(Text)
    care_instructions = Column(Text)
    specifications = Column(JSONB, default=dict)
    size_chart = Column(JSONB, default=dict)
    tags = Column(ARRAY(Text), default=list)
    status = Column(String(50), default="Selling", nullable=False)
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    category = relationship("ProductionCategory", back_populates="products")
    product_line = relationship("ProductionProductLine", back_populates="products")
    variants = relationship("ProductionVariant", back_populates="product", cascade="all, delete-orphan")
    images = relationship("ProductionProductImage", back_populates="product", cascade="all, delete-orphan")
    materials = relationship("ProductionMaterial", secondary="production_product_material")
    collections = relationship("ProductionCollection", secondary="production_product_collection")

class ProductionVariant(Base):
    __tablename__ = "production_variant"

    id = Column(BigInteger, primary_key=True, index=True)
    product_id = Column(BigInteger, ForeignKey("production_product.id", ondelete="CASCADE"), nullable=False)
    size_id = Column(BigInteger, ForeignKey("production_size.id"), nullable=False)
    color_id = Column(BigInteger, ForeignKey("production_color.id"), nullable=False)
    sku = Column(String(100), unique=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    product = relationship("ProductionProduct", back_populates="variants")
    size = relationship("ProductionSize")
    color = relationship("ProductionColor")
    inventory = relationship("ProductionInventory", uselist=False, back_populates="variant", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("product_id", "size_id", "color_id", name="uq_product_size_color"),)

class ProductionProductImage(Base):
    __tablename__ = "production_product_image"

    id = Column(BigInteger, primary_key=True, index=True)
    product_id = Column(BigInteger, ForeignKey("production_product.id", ondelete="CASCADE"), nullable=False)
    color_id = Column(BigInteger, ForeignKey("production_color.id", ondelete="SET NULL"))
    file_path = Column(String(500), nullable=False)
    alt_text = Column(String(255))
    sort_order = Column(Integer, default=0, nullable=False)

    product = relationship("ProductionProduct", back_populates="images")
    color = relationship("ProductionColor")

# -----------------------------------------------------------------------------
# 3. INVENTORY & PROCUREMENT
# -----------------------------------------------------------------------------

class ProductionSupplier(Base):
    __tablename__ = "production_supplier"

    id = Column(BigInteger, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    phone = Column(String(30))
    email = Column(String(255))
    address = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class ProductionGoodsReceipt(Base):
    __tablename__ = "production_goods_receipt"

    id = Column(BigInteger, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    supplier_id = Column(BigInteger, ForeignKey("production_supplier.id"), nullable=False)
    confirmed_by = Column(BigInteger, ForeignKey("user_account.id"), nullable=False)
    confirmed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    supplier_snapshot = Column(JSONB, nullable=False)
    note = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    supplier = relationship("ProductionSupplier")
    confirmer = relationship("UserAccount")
    items = relationship("ProductionGoodsReceiptItem", back_populates="receipt", cascade="all, delete-orphan")

class ProductionGoodsReceiptItem(Base):
    __tablename__ = "production_goods_receipt_item"

    id = Column(BigInteger, primary_key=True, index=True)
    receipt_id = Column(BigInteger, ForeignKey("production_goods_receipt.id", ondelete="CASCADE"), nullable=False)
    variant_id = Column(BigInteger, ForeignKey("production_variant.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_cost = Column(Numeric(12, 2), nullable=False)
    variant_snapshot = Column(JSONB, nullable=False)

    receipt = relationship("ProductionGoodsReceipt", back_populates="items")
    variant = relationship("ProductionVariant")

class ProductionInventory(Base):
    __tablename__ = "production_inventory"

    variant_id = Column(BigInteger, ForeignKey("production_variant.id", ondelete="CASCADE"), primary_key=True)
    available_quantity = Column(Integer, default=0, nullable=False)
    inventory_value = Column(Numeric(14, 2), default=0, nullable=False)
    low_stock_threshold = Column(Integer, default=5, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    variant = relationship("ProductionVariant", back_populates="inventory")

class ProductionInventoryMovement(Base):
    __tablename__ = "production_inventory_movement"

    id = Column(BigInteger, primary_key=True, index=True)
    variant_id = Column(BigInteger, ForeignKey("production_variant.id"), nullable=False)
    receipt_item_id = Column(BigInteger, ForeignKey("production_goods_receipt_item.id"))
    order_item_id = Column(BigInteger)
    movement_type = Column(String(50), nullable=False) # RECEIPT, ORDER_OUT, ORDER_CANCEL_RESTORE
    quantity_delta = Column(Integer, nullable=False)
    value_delta = Column(Numeric(14, 2), nullable=False)
    event_key = Column(String(150), unique=True, nullable=False)
    occurred_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    variant = relationship("ProductionVariant")

# -----------------------------------------------------------------------------
# 4. COMMERCE (Cart, Wishlist, Promotions, Orders, Reviews)
# -----------------------------------------------------------------------------

class ProductionCartItem(Base):
    __tablename__ = "production_cart_item"

    account_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="CASCADE"), primary_key=True)
    variant_id = Column(BigInteger, ForeignKey("production_variant.id", ondelete="CASCADE"), primary_key=True)
    quantity = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    account = relationship("UserAccount", back_populates="cart_items")
    variant = relationship("ProductionVariant")

class ProductionWishlistItem(Base):
    __tablename__ = "production_wishlist_item"

    account_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="CASCADE"), primary_key=True)
    product_id = Column(BigInteger, ForeignKey("production_product.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class ProductionPromotion(Base):
    __tablename__ = "production_promotion"

    id = Column(BigInteger, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    promotion_type = Column(String(50), nullable=False) # PRODUCT, ORDER, VOUCHER
    discount_percent = Column(Numeric(5, 2), nullable=False)
    minimum_order_amount = Column(Numeric(12, 2), default=0, nullable=False)
    usage_limit = Column(Integer)
    used_count = Column(Integer, default=0, nullable=False)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    eligible_customer_ids = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    products = relationship("ProductionProduct", secondary="production_promotion_product")

class ProductionPromotionProduct(Base):
    __tablename__ = "production_promotion_product"

    promotion_id = Column(BigInteger, ForeignKey("production_promotion.id", ondelete="CASCADE"), primary_key=True)
    product_id = Column(BigInteger, ForeignKey("production_product.id", ondelete="CASCADE"), primary_key=True)

class ProductionOrder(Base):
    __tablename__ = "production_order"

    id = Column(BigInteger, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    account_id = Column(BigInteger, ForeignKey("user_account.id"), nullable=False)
    status = Column(String(50), nullable=False) # Chưa xử lý, Đã xử lý, Đang vận chuyển, Đã giao, Giao không thành công, Đã hủy, Chờ hoàn tiền, Đã hoàn tiền
    payment_method = Column(String(50), nullable=False) # COD, VietQR
    selected_discount_type = Column(String(50)) # PRODUCT, ORDER, VOUCHER, NONE
    subtotal = Column(Numeric(12, 2), nullable=False)
    discount_amount = Column(Numeric(12, 2), default=0, nullable=False)
    shipping_fee = Column(Numeric(12, 2), default=0, nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    refund_amount = Column(Numeric(12, 2), default=0)
    recipient_snapshot = Column(JSONB, nullable=False)
    store_snapshot = Column(JSONB, nullable=False)
    payment_due_at = Column(DateTime(timezone=True))
    placed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    account = relationship("UserAccount", back_populates="orders")
    items = relationship("ProductionOrderItem", back_populates="order", cascade="all, delete-orphan")
    history = relationship("ProductionOrderHistory", back_populates="order", cascade="all, delete-orphan")
    discount_options = relationship("ProductionOrderDiscountOption", back_populates="order", cascade="all, delete-orphan")
    payment = relationship("ProductionPayment", uselist=False, back_populates="order", cascade="all, delete-orphan")
    shipment = relationship("ProductionShipment", uselist=False, back_populates="order", cascade="all, delete-orphan")
    invoice = relationship("ProductionInvoice", uselist=False, back_populates="order", cascade="all, delete-orphan")

class ProductionOrderItem(Base):
    __tablename__ = "production_order_item"

    id = Column(BigInteger, primary_key=True, index=True)
    order_id = Column(BigInteger, ForeignKey("production_order.id", ondelete="CASCADE"), nullable=False)
    variant_id = Column(BigInteger, ForeignKey("production_variant.id"), nullable=False)
    promotion_id = Column(BigInteger, ForeignKey("production_promotion.id"))
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    unit_cost_snapshot = Column(Numeric(12, 2), nullable=False)
    allocated_discount_amount = Column(Numeric(12, 2), default=0, nullable=False)
    line_total = Column(Numeric(12, 2), nullable=False)
    product_snapshot = Column(JSONB, nullable=False)
    promotion_snapshot = Column(JSONB)

    order = relationship("ProductionOrder", back_populates="items")
    variant = relationship("ProductionVariant")

class ProductionOrderDiscountOption(Base):
    __tablename__ = "production_order_discount_option"

    id = Column(BigInteger, primary_key=True, index=True)
    order_id = Column(BigInteger, ForeignKey("production_order.id", ondelete="CASCADE"), nullable=False)
    promotion_id = Column(BigInteger, ForeignKey("production_promotion.id"))
    option_type = Column(String(50), nullable=False)
    is_eligible = Column(Boolean, default=True, nullable=False)
    discount_amount = Column(Numeric(12, 2), default=0, nullable=False)
    is_selected = Column(Boolean, default=False, nullable=False)
    calculation_snapshot = Column(JSONB)

    order = relationship("ProductionOrder", back_populates="discount_options")

    __table_args__ = (UniqueConstraint("order_id", "option_type", name="uq_order_discount_option"),)

class ProductionVoucherUsage(Base):
    __tablename__ = "production_voucher_usage"

    id = Column(BigInteger, primary_key=True, index=True)
    order_id = Column(BigInteger, ForeignKey("production_order.id", ondelete="CASCADE"), unique=True, nullable=False)
    promotion_id = Column(BigInteger, ForeignKey("production_promotion.id"), nullable=False)
    consumed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    restored_at = Column(DateTime(timezone=True))

class ProductionOrderHistory(Base):
    __tablename__ = "production_order_history"

    id = Column(BigInteger, primary_key=True, index=True)
    order_id = Column(BigInteger, ForeignKey("production_order.id", ondelete="CASCADE"), nullable=False)
    actor_account_id = Column(BigInteger, ForeignKey("user_account.id"))
    event_type = Column(String(50), nullable=False)
    from_status = Column(String(50))
    to_status = Column(String(50), nullable=False)
    reason = Column(Text)
    occurred_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    order = relationship("ProductionOrder", back_populates="history")
    actor = relationship("UserAccount")

class ProductionReview(Base):
    __tablename__ = "production_review"

    id = Column(BigInteger, primary_key=True, index=True)
    account_id = Column(BigInteger, ForeignKey("user_account.id"), nullable=False)
    product_id = Column(BigInteger, ForeignKey("production_product.id", ondelete="CASCADE"), nullable=False)
    order_item_id = Column(BigInteger, ForeignKey("production_order_item.id"))
    rating = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    moderation_status = Column(String(50), default="APPROVED", nullable=False)
    moderated_by = Column(BigInteger, ForeignKey("user_account.id"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    account = relationship("UserAccount", foreign_keys=[account_id])
    product = relationship("ProductionProduct")

# -----------------------------------------------------------------------------
# 5. PAYMENT, SHIPPING, INVOICES, INTEGRATIONS
# -----------------------------------------------------------------------------

class ProductionPayment(Base):
    __tablename__ = "production_payment"

    id = Column(BigInteger, primary_key=True, index=True)
    order_id = Column(BigInteger, ForeignKey("production_order.id", ondelete="CASCADE"), unique=True, nullable=False)
    method = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False) # PENDING, PAID, FAILED, REFUNDED
    expected_amount = Column(Numeric(12, 2), nullable=False)
    received_amount = Column(Numeric(12, 2), default=0, nullable=False)
    external_transaction_id = Column(String(100), unique=True)
    paid_at = Column(DateTime(timezone=True))
    payment_instruction_snapshot = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    order = relationship("ProductionOrder", back_populates="payment")

class ProductionShipment(Base):
    __tablename__ = "production_shipment"

    id = Column(BigInteger, primary_key=True, index=True)
    order_id = Column(BigInteger, ForeignKey("production_order.id", ondelete="CASCADE"), unique=True, nullable=False)
    carrier = Column(String(50), default="GHTK", nullable=False)
    tracking_code = Column(String(100), unique=True)
    creation_status = Column(String(50), default="CREATED", nullable=False)
    delivery_status = Column(String(50), default="WAITING_FOR_PICKUP", nullable=False)
    shipping_fee_snapshot = Column(Numeric(12, 2), nullable=False)
    carrier_request_key = Column(String(150), unique=True, nullable=False)
    delivered_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    order = relationship("ProductionOrder", back_populates="shipment")

class ProductionInvoice(Base):
    __tablename__ = "production_invoice"

    id = Column(BigInteger, primary_key=True, index=True)
    order_id = Column(BigInteger, ForeignKey("production_order.id", ondelete="CASCADE"), unique=True, nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    issued_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    subtotal = Column(Numeric(12, 2), nullable=False)
    discount_amount = Column(Numeric(12, 2), nullable=False)
    shipping_fee = Column(Numeric(12, 2), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    customer_snapshot = Column(JSONB, nullable=False)
    store_snapshot = Column(JSONB, nullable=False)

    order = relationship("ProductionOrder", back_populates="invoice")
    items = relationship("ProductionInvoiceItem", back_populates="invoice", cascade="all, delete-orphan")

class ProductionInvoiceItem(Base):
    __tablename__ = "production_invoice_item"

    id = Column(BigInteger, primary_key=True, index=True)
    invoice_id = Column(BigInteger, ForeignKey("production_invoice.id", ondelete="CASCADE"), nullable=False)
    order_item_id = Column(BigInteger, ForeignKey("production_order_item.id"), unique=True, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    discount_amount = Column(Numeric(12, 2), default=0, nullable=False)
    line_total = Column(Numeric(12, 2), nullable=False)
    unit_cost_snapshot = Column(Numeric(12, 2), nullable=False)
    product_snapshot = Column(JSONB, nullable=False)
    promotion_snapshot = Column(JSONB)

    invoice = relationship("ProductionInvoice", back_populates="items")

class ProductionIntegrationEvent(Base):
    __tablename__ = "production_integration_event"

    id = Column(BigInteger, primary_key=True, index=True)
    order_id = Column(BigInteger, ForeignKey("production_order.id", ondelete="SET NULL"))
    source = Column(String(50), nullable=False)
    external_event_id = Column(String(150), nullable=False)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSONB, nullable=False)
    processing_status = Column(String(50), nullable=False)
    processing_result = Column(Text)
    attempt_count = Column(Integer, default=1, nullable=False)
    received_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    processed_at = Column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("source", "external_event_id", name="uq_integration_source_event"),)

class ProductionOutboxEvent(Base):
    __tablename__ = "production_outbox_event"

    id = Column(BigInteger, primary_key=True, index=True)
    order_id = Column(BigInteger, ForeignKey("production_order.id", ondelete="CASCADE"))
    event_type = Column(String(100), nullable=False)
    event_key = Column(String(150), unique=True, nullable=False)
    payload = Column(JSONB, nullable=False)
    status = Column(String(50), default="PENDING", nullable=False)
    attempt_count = Column(Integer, default=0, nullable=False)
    next_attempt_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class ProductionIdempotencyRequest(Base):
    __tablename__ = "production_idempotency_request"

    id = Column(BigInteger, primary_key=True, index=True)
    account_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="SET NULL"))
    operation = Column(String(100), nullable=False)
    idempotency_key = Column(String(150), nullable=False)
    request_hash = Column(String(64), nullable=False)
    status = Column(String(50), nullable=False)
    response_status = Column(Integer)
    response_body = Column(JSONB)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (UniqueConstraint("operation", "idempotency_key", name="uq_idempotency_op_key"),)

# -----------------------------------------------------------------------------
# 6. CONTENT, SETTINGS & FEEDBACK
# -----------------------------------------------------------------------------

class ProductionContent(Base):
    __tablename__ = "production_content"

    id = Column(BigInteger, primary_key=True, index=True)
    author_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="SET NULL"))
    content_type = Column(String(50), nullable=False) # BLOG, STATIC_PAGE
    slug = Column(String(150), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    cover_image_path = Column(String(500))
    status = Column(String(50), default="PUBLISHED", nullable=False)
    published_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class ProductionContentBlock(Base):
    __tablename__ = "production_content_block"

    id = Column(BigInteger, primary_key=True, index=True)
    code = Column(String(100), unique=True, nullable=False)
    block_type = Column(String(50), nullable=False) # banner, announcement, community, hot_keyword
    placement = Column(String(100), nullable=False)
    payload = Column(JSONB, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    starts_at = Column(DateTime(timezone=True))
    ends_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class ProductionSiteSetting(Base):
    __tablename__ = "production_site_setting"

    key = Column(String(100), primary_key=True)
    value = Column(JSONB, nullable=False)

# -----------------------------------------------------------------------------
# LUCKY WHEEL (VÒNG QUAY MAY MẮN) — ô quay + lịch sử lượt quay
# -----------------------------------------------------------------------------

class ProductionLuckyWheelSlot(Base):
    """
    Một ô trên vòng quay. Ô chỉ là "có thưởng" khi có voucher mẫu (promotion_id)
    VÀ có nhập số lượng (quantity_total > 0); nếu bỏ trống thì mặc định là
    ô "không trúng thưởng". Khi trúng, khách nhận một mã voucher riêng sinh ra
    từ voucher mẫu (dùng 1 lần, chỉ tài khoản đó dùng được).
    """
    __tablename__ = "production_lucky_wheel_slot"

    id = Column(BigInteger, primary_key=True, index=True)
    label = Column(String(80), nullable=False)
    promotion_id = Column(BigInteger, ForeignKey("production_promotion.id", ondelete="SET NULL"), nullable=True)
    win_weight = Column(Numeric(7, 3), default=0, nullable=False)  # tỷ lệ ra (%)
    quantity_total = Column(Integer, nullable=True)                 # số voucher trong vòng quay / mỗi chu kỳ
    quantity_remaining = Column(Integer, nullable=True)
    color = Column(String(20), default="#0ea5e9", nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    promotion = relationship("ProductionPromotion")

class ProductionLuckyWheelSpin(Base):
    __tablename__ = "production_lucky_wheel_spin"

    id = Column(BigInteger, primary_key=True, index=True)
    account_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True)
    slot_id = Column(BigInteger, ForeignKey("production_lucky_wheel_slot.id", ondelete="SET NULL"), nullable=True)
    slot_label = Column(String(80), nullable=False)
    is_win = Column(Boolean, default=False, nullable=False)
    issued_promotion_id = Column(BigInteger, ForeignKey("production_promotion.id", ondelete="SET NULL"), nullable=True)
    voucher_code = Column(String(50))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    account = relationship("UserAccount")
    issued_promotion = relationship("ProductionPromotion", foreign_keys=[issued_promotion_id])

class ProductionFeedback(Base):
    __tablename__ = "production_feedback"

    id = Column(BigInteger, primary_key=True, index=True)
    account_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="SET NULL"))
    sender_name = Column(String(150), nullable=False)
    sender_email = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(50), default="NEW", nullable=False)
    handled_by = Column(BigInteger, ForeignKey("user_account.id", ondelete="SET NULL"))
    handled_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


# -----------------------------------------------------------------------------
# AUDIT LOG (NHẬT KÝ THAO TÁC) — ghi lại thao tác thay đổi dữ liệu của nhân sự
# -----------------------------------------------------------------------------

class ProductionAuditLog(Base):
    """
    Một thao tác POST/PUT/PATCH/DELETE thành công của tài khoản nhân sự (không phải CUSTOMER).
    Không bao giờ lưu nội dung request (mật khẩu, dữ liệu cá nhân) — chỉ method, đường dẫn
    và mô tả ngắn bằng tiếng Việt suy ra từ đường dẫn.
    """
    __tablename__ = "production_audit_log"

    id = Column(BigInteger, primary_key=True, index=True)
    account_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="SET NULL"), nullable=True, index=True)
    account_name = Column(String(150), nullable=False)
    role_code = Column(String(50), nullable=False)
    method = Column(String(10), nullable=False)
    path = Column(String(500), nullable=False)
    status_code = Column(Integer, nullable=False)
    summary = Column(String(255), nullable=False)
    ip = Column(String(64))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)



# -----------------------------------------------------------------------------
# CUSTOMER EXPERIENCE — hồ sơ size thông minh + điểm danh nhận Vỏ Sò
# -----------------------------------------------------------------------------
from sqlalchemy import Date  # noqa: E402  (chỉ dùng cho bảng điểm danh bên dưới)


class ProductionFitProfile(Base):
    """Số đo cơ thể khách lưu để gợi ý size (mỗi tài khoản một hồ sơ)."""
    __tablename__ = "production_fit_profile"

    account_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="CASCADE"), primary_key=True)
    gender = Column(String(20), nullable=False, default="Nữ")   # Nữ | Nam | Trẻ em
    height_cm = Column(Numeric(5, 1))
    weight_kg = Column(Numeric(5, 1))
    bust_cm = Column(Numeric(5, 1))
    waist_cm = Column(Numeric(5, 1))
    hip_cm = Column(Numeric(5, 1))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class ProductionDailyCheckin(Base):
    """
    Một lần điểm danh trong ngày (theo giờ Việt Nam). Mỗi lần nhận `shells_awarded` Vỏ Sò;
    cứ đủ 3 Vỏ Sò tích luỹ thì `bonus_spins` = +1 lượt quay thưởng trong chu kỳ vòng quay hiện tại.
    """
    __tablename__ = "production_daily_checkin"

    id = Column(BigInteger, primary_key=True, index=True)
    account_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True)
    checkin_date = Column(Date, nullable=False)
    streak_day = Column(Integer, nullable=False, default=1)      # vị trí 1..7 trong chuỗi 7 ngày
    shells_awarded = Column(Integer, nullable=False, default=1)
    bonus_spins = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (UniqueConstraint("account_id", "checkin_date", name="uq_checkin_account_date"),)
