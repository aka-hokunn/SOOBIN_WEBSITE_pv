from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

# -----------------------------------------------------------------------------
# AUTH & USER SCHEMAS
# -----------------------------------------------------------------------------

class UserRegisterRequest(BaseModel):
    email: str = Field(..., min_length=5)
    phone: Optional[str] = None
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2)

class UserLoginRequest(BaseModel):
    email_or_phone: str
    password: str

class PortalLoginRequest(BaseModel):
    email_or_phone: str
    password: str
    portal: str = Field(..., description="ADMIN | MANAGER | WAREHOUSE | SALES | CUSTOMER")

class VerifyEmailRequest(BaseModel):
    token: str

class UserResponse(BaseModel):
    id: int
    role_id: int
    role_code: str
    email: str
    phone: Optional[str] = None
    full_name: str
    is_email_verified: bool
    is_locked: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SessionResponse(BaseModel):
    session_token: str
    user: UserResponse

class UserAddressCreate(BaseModel):
    recipient_name: str
    recipient_phone: str
    address_line: str
    province_code: Optional[str] = None
    district_code: Optional[str] = None
    ward_code: Optional[str] = None
    is_default: bool = False

class UserAddressResponse(BaseModel):
    id: int
    account_id: int
    recipient_name: str
    recipient_phone: str
    address_line: str
    is_default: bool

    model_config = ConfigDict(from_attributes=True)

# -----------------------------------------------------------------------------
# RBAC SCHEMAS
# -----------------------------------------------------------------------------

class RoleCreate(BaseModel):
    code: str
    name: str
    permission_ids: List[int] = []

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    permission_ids: Optional[List[int]] = None

class RoleResponse(BaseModel):
    id: int
    code: str
    name: str
    is_system: bool
    is_active: bool
    permissions: List[str] = []

    model_config = ConfigDict(from_attributes=True)

# -----------------------------------------------------------------------------
# CATALOG SCHEMAS
# -----------------------------------------------------------------------------

class CategoryResponse(BaseModel):
    id: int
    parent_id: Optional[int] = None
    name: str
    slug: str
    sort_order: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class VariantResponse(BaseModel):
    id: int
    product_id: int
    size_id: int
    size_name: str
    size_code: str
    color_id: int
    color_name: str
    color_hex: str
    sku: str
    available_quantity: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class ProductImageResponse(BaseModel):
    id: int
    color_id: Optional[int] = None
    file_path: str
    alt_text: Optional[str] = None
    sort_order: int

    model_config = ConfigDict(from_attributes=True)

class ProductListResponse(BaseModel):
    id: int
    category_id: int
    category_name: str
    code: str
    slug: str
    name: str
    base_price: float
    discounted_price: float
    discount_percent: float
    target_audience: str
    skill_level: Optional[str] = None
    status: str
    image_url: Optional[str] = None
    variants: List[VariantResponse] = []
    total_stock: int

class ProductDetailResponse(BaseModel):
    id: int
    category_id: int
    category_name: str
    product_line_id: Optional[int] = None
    code: str
    slug: str
    name: str
    base_price: float
    discounted_price: float
    discount_percent: float
    target_audience: str
    skill_level: Optional[str] = None
    description: Optional[str] = None
    care_instructions: Optional[str] = None
    specifications: Dict[str, Any] = {}
    size_chart: Dict[str, Any] = {}
    tags: List[str] = []
    status: str
    images: List[ProductImageResponse] = []
    variants: List[VariantResponse] = []

class ProductVariantCreateRequest(BaseModel):
    size_id: int
    color_id: int
    sku: str = Field(..., min_length=2, max_length=100)

class ProductCreateRequest(BaseModel):
    category_id: int
    product_line_id: Optional[int] = None
    code: str
    name: str
    base_price: float
    target_audience: str
    skill_level: Optional[str] = None
    description: Optional[str] = None
    care_instructions: Optional[str] = None
    specifications: Optional[Dict[str, Any]] = None
    size_chart: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    image_url: Optional[str] = None
    variants: List[ProductVariantCreateRequest] = []

class ProductUpdateRequest(BaseModel):
    category_id: Optional[int] = None
    product_line_id: Optional[int] = None
    name: Optional[str] = None
    base_price: Optional[float] = None
    target_audience: Optional[str] = None
    skill_level: Optional[str] = None
    description: Optional[str] = None
    care_instructions: Optional[str] = None
    specifications: Optional[Dict[str, Any]] = None
    size_chart: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None

# -----------------------------------------------------------------------------
# CART SCHEMAS
# -----------------------------------------------------------------------------

class CartItemAdd(BaseModel):
    variant_id: int
    quantity: int = Field(..., gt=0)

class CartItemUpdate(BaseModel):
    quantity: int = Field(..., gt=0)

class CartItemResponse(BaseModel):
    variant_id: int
    product_id: int
    product_name: str
    product_slug: str
    sku: str
    size_name: str
    color_name: str
    unit_price: float
    quantity: int
    available_stock: int
    is_valid_for_checkout: bool
    status_message: Optional[str] = None
    line_total: float
    image_url: Optional[str] = None

class CartResponse(BaseModel):
    items: List[CartItemResponse]
    subtotal: float
    total_items: int

class GuestCartItem(BaseModel):
    variant_id: int
    quantity: int

class CartMergeRequest(BaseModel):
    items: List[GuestCartItem]

# -----------------------------------------------------------------------------
# PROMOTIONS & DISCOUNT CALCULATION
# -----------------------------------------------------------------------------

class PromotionCreate(BaseModel):
    code: str
    name: str
    promotion_type: str # PRODUCT, ORDER, VOUCHER
    discount_percent: float = Field(..., gt=0, lt=100)
    minimum_order_amount: float = Field(0.0, ge=0)
    usage_limit: Optional[int] = Field(None, ge=1)
    starts_at: datetime
    ends_at: datetime
    product_ids: Optional[List[int]] = None
    eligible_customer_ids: Optional[List[int]] = None

class PromotionResponse(BaseModel):
    id: int
    code: str
    name: str
    promotion_type: str
    discount_percent: float
    minimum_order_amount: float
    usage_limit: Optional[int] = None
    used_count: int
    starts_at: datetime
    ends_at: datetime
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class DiscountOptionDetail(BaseModel):
    option_type: str # PRODUCT, ORDER, VOUCHER
    discount_amount: float
    is_eligible: bool
    reason: Optional[str] = None
    promotion_code: Optional[str] = None

class DiscountCalculationResult(BaseModel):
    original_subtotal: float
    shipping_fee: float
    product_discount: float
    order_discount: float
    voucher_discount: float
    selected_option_type: str # PRODUCT, ORDER, VOUCHER, NONE
    winning_discount_amount: float
    final_subtotal: float
    final_total: float
    applied_voucher_code: Optional[str] = None
    eligible_options: List[DiscountOptionDetail]

# -----------------------------------------------------------------------------
# ORDER & CHECKOUT SCHEMAS
# -----------------------------------------------------------------------------

class OrderCreateRequest(BaseModel):
    recipient_name: str
    recipient_phone: str
    shipping_address: str
    payment_method: str # COD, VietQR
    voucher_code: Optional[str] = None
    guest_items: Optional[List[GuestCartItem]] = None

class OrderItemResponse(BaseModel):
    id: int
    variant_id: int
    quantity: int
    unit_price: float
    allocated_discount_amount: float
    line_total: float
    product_snapshot: Dict[str, Any]

class OrderResponse(BaseModel):
    id: int
    code: str
    account_id: int
    status: str
    payment_method: str
    selected_discount_type: Optional[str] = None
    subtotal: float
    discount_amount: float
    shipping_fee: float
    total_amount: float
    refund_amount: Optional[float] = 0.0
    recipient_snapshot: Dict[str, Any]
    items: List[OrderItemResponse] = []
    payment: Optional[Dict[str, Any]] = None
    shipment: Optional[Dict[str, Any]] = None
    placed_at: datetime

class OrderStatusUpdateRequest(BaseModel):
    to_status: str
    reason: Optional[str] = None

class OrderCancelRequest(BaseModel):
    reason: str

class ManualRefundRequest(BaseModel):
    note: Optional[str] = "Hoàn tiền chuyển khoản thủ công cho khách hàng"

# -----------------------------------------------------------------------------
# INVENTORY & GOODS RECEIPTS SCHEMAS
# -----------------------------------------------------------------------------

class GoodsReceiptItemCreate(BaseModel):
    variant_id: int
    quantity: int = Field(..., gt=0)
    unit_cost: float = Field(..., ge=0)

class GoodsReceiptCreate(BaseModel):
    supplier_id: int
    note: Optional[str] = None
    items: List[GoodsReceiptItemCreate] = Field(..., min_length=1)

class GoodsReceiptResponse(BaseModel):
    id: int
    code: str
    supplier_id: int
    supplier_name: str
    confirmed_by_name: str
    confirmed_at: datetime
    total_quantity: int
    total_cost: float
    note: Optional[str] = None
    items: List[Dict[str, Any]]

class InventoryBalanceResponse(BaseModel):
    variant_id: int
    sku: str
    product_name: str
    size_name: str
    color_name: str
    available_quantity: int
    inventory_value: float
    weighted_unit_cost: float
    low_stock_threshold: int
    is_low_stock: bool

# -----------------------------------------------------------------------------
# SHIPPING MOCK & PAYMENT MOCK
# -----------------------------------------------------------------------------

class MockShippingWebhook(BaseModel):
    carrier: str = "GHTK"
    carrier_request_key: str
    tracking_code: str
    delivery_status: str # WAITING_FOR_PICKUP, IN_TRANSIT, DELIVERED, FAILED
    reason: Optional[str] = None

class MockPaymentWebhook(BaseModel):
    order_code: str
    transfer_amount: float
    external_transaction_id: str

# -----------------------------------------------------------------------------
# DASHBOARD REPORTS
# -----------------------------------------------------------------------------

class DashboardReportResponse(BaseModel):
    total_delivered_revenue: float
    total_delivered_profit: float
    orders_by_status: Dict[str, int]
    low_stock_items: List[Dict[str, Any]]
    top_selling_products: List[Dict[str, Any]]
    total_suppliers: int
    total_products: int

# -----------------------------------------------------------------------------
# USER & STAFF MANAGEMENT BY ADMIN
# -----------------------------------------------------------------------------

class UserCreateAdminRequest(BaseModel):
    email: str = Field(..., min_length=5)
    full_name: str = Field(..., min_length=2)
    password: str = Field(..., min_length=6)
    phone: Optional[str] = None
    role_id: int

class UserUpdateAdminRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role_id: Optional[int] = None
    is_locked: Optional[bool] = None

# -----------------------------------------------------------------------------
# GOODS RECEIPT ADJUSTMENT
# -----------------------------------------------------------------------------

class GoodsReceiptAdjustmentItem(BaseModel):
    item_id: int
    new_quantity: int = Field(..., ge=0)
    reason: Optional[str] = None

class GoodsReceiptAdjustmentRequest(BaseModel):
    adjustments: List[GoodsReceiptAdjustmentItem]
    note: Optional[str] = None

# -----------------------------------------------------------------------------
# WISHLIST
# -----------------------------------------------------------------------------

class WishlistItemResponse(BaseModel):
    product_id: int
    name: str
    code: str
    slug: str
    base_price: float
    sale_price: Optional[float] = None
    image_url: str
    is_in_stock: bool
    added_at: str

class WishlistToggleResponse(BaseModel):
    product_id: int
    is_in_wishlist: bool
    message: str

# -----------------------------------------------------------------------------
# REVIEWS & RATINGS
# -----------------------------------------------------------------------------

class ReviewCreateRequest(BaseModel):
    order_id: int
    rating: int = Field(..., ge=1, le=5)
    content: str = Field(..., min_length=3, max_length=1000)

class ReviewResponse(BaseModel):
    id: int
    product_id: int
    account_id: int
    customer_name: str
    rating: int
    content: str
    moderation_status: str
    created_at: str

class ReviewModerateRequest(BaseModel):
    status: str = Field(..., description="APPROVED | HIDDEN")

# -----------------------------------------------------------------------------
# INVOICE SCHEMAS
# -----------------------------------------------------------------------------

class InvoiceItemDetail(BaseModel):
    id: int
    product_name: str
    sku: str
    size: str
    color: str
    quantity: int
    unit_price: float
    discount_amount: float
    line_total: float

class InvoiceDetailResponse(BaseModel):
    id: int
    code: str
    order_id: int
    order_code: str
    issued_at: str
    subtotal: float
    discount_amount: float
    shipping_fee: float
    total_amount: float
    customer_snapshot: Dict[str, Any]
    store_snapshot: Dict[str, Any]
    items: List[InvoiceItemDetail]

# -----------------------------------------------------------------------------
# AI CHAT & SIZE ADVISOR
# -----------------------------------------------------------------------------

class AIChatRequest(BaseModel):
    message: str
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    bust_cm: Optional[float] = None
    waist_cm: Optional[float] = None
    hips_cm: Optional[float] = None
    gender: Optional[str] = None

class AIChatResponse(BaseModel):
    reply: str
    recommended_size: Optional[str] = None
    size_advice: Optional[str] = None
    suggested_products: List[Dict[str, Any]] = []

# -----------------------------------------------------------------------------
# ENTERPRISE FASHION MERCHANDISING, SALE PRICING, POS, WMS & THEMES
# -----------------------------------------------------------------------------

class ProductSalePriceUpdateRequest(BaseModel):
    base_price: Optional[float] = Field(None, gt=0)
    sale_price: Optional[float] = Field(None, ge=0)
    discount_percent: Optional[float] = Field(None, ge=0, le=95)
    is_on_sale: bool = True
    clear_sale: Optional[bool] = False

class BulkSaleUpdateRequest(BaseModel):
    category_id: Optional[int] = None
    target_audience: Optional[str] = None
    discount_percent: float = Field(0.0, ge=0, le=90)
    clear_sale: Optional[bool] = False

class SupplierCreateRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=255)
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None

class SupplierUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None

class StocktakeRequest(BaseModel):
    variant_id: int
    actual_quantity: int = Field(..., ge=0)
    low_stock_threshold: Optional[int] = Field(None, ge=0)
    reason: str = Field("Kiểm kê kho thực tế định kỳ", min_length=2)

class POSOrderItemInput(BaseModel):
    variant_id: int
    quantity: int = Field(..., gt=0)

class POSOrderCreateRequest(BaseModel):
    recipient_name: Optional[str] = None
    recipient_phone: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    shipping_address: str = "Mua trực tiếp tại cửa hàng Flagship Soobin"
    payment_method: str = "CASH" # CASH, VietQR, COD
    fulfillment_type: str = "INSTORE_PICKUP" # INSTORE_PICKUP, GHTK
    voucher_code: Optional[str] = None
    items: List[POSOrderItemInput]

class StorefrontThemeConfig(BaseModel):
    theme: str = "ocean-luxury" # ocean-luxury, sunset-ibiza, midnight-vogue, minimal-atelier
    morph_enabled: bool = True
    enable_3d_morph: Optional[bool] = True
    tilt_3d_enabled: bool = True
    hero_badge: Optional[str] = "RUNWAY RESORT COLLECTION 2026"
    hero_title: Optional[str] = "Tôn Vinh Đường Nét & Chuyển Động 3D"
    hero_headline: Optional[str] = None
    hero_subtitle: Optional[str] = None
    flash_sale_title: Optional[str] = "⚡ FLASH SALE ATELIER — ƯU ĐÃI ĐẶC QUYỀN"

class FeedbackCreateRequest(BaseModel):
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    subject: Optional[str] = None
    message: str = Field(..., min_length=5, max_length=2000)

class FeedbackUpdateRequest(BaseModel):
    status: str = Field(..., description="NEW | IN_PROGRESS | RESOLVED")

class CartBundleAddRequest(BaseModel):
    bundle_name: Optional[str] = "Set Phối Đồ 3D Soobin"
    items: List[CartItemAdd] = Field(..., min_length=1)

class OrderExchangeRequest(BaseModel):
    target_size: Optional[str] = "L"
    reason: str = Field(..., min_length=3, max_length=1000)
    preferred_resolution: str = Field("EXCHANGE_SIZE", description="EXCHANGE_SIZE | WARRANTY_REPAIR | RETURN_REFUND | REFUND_CONSULT")


class AfterSalesPolicyConfig(BaseModel):
    return_window_days: int = Field(7, ge=0, le=365, description="Thời hạn trả hàng / hoàn tiền (ngày)")
    exchange_size_window_days: int = Field(15, ge=0, le=365, description="Thời hạn đổi size / đổi mẫu (ngày)")
    warranty_window_days: int = Field(90, ge=0, le=1095, description="Thời hạn bảo hành đường may / phụ kiện (ngày)")
    vietqr_payment_timeout_hours: int = Field(24, ge=1, le=168, description="Thời hạn thanh toán chuyển khoản VietQR (giờ)")
    enforce_time_limit: bool = Field(True, description="Chặn yêu cầu khi đơn hàng đã quá thời hạn")
    warranty_terms: str = Field(
        "Đổi size miễn phí khi còn nguyên tem mác; Bảo hành miễn phí đường chỉ, khóa kéo và phụ kiện kim loại chống muối biển.",
        max_length=1000
    )


class BankAccountConfig(BaseModel):
    bank_code: str = Field("MB", min_length=2, max_length=20, description="Mã ngân hàng VietQR (MB, VCB, TCB, ICB, BIDV, ACB, VPB, TPB...)")
    bank_name: str = Field("MBBank (Ngân hàng Quân Đội)", min_length=2, max_length=150)
    account_no: str = Field("0389998888", min_length=4, max_length=40, description="Số tài khoản ngân hàng nhận tiền của chủ shop")
    account_name: str = Field("SOOBIN SWIMWEAR ATELIER", min_length=2, max_length=120, description="Tên chủ tài khoản")
    bank_branch: Optional[str] = Field("Chi nhánh TP. Hồ Chí Minh", max_length=150)
    transfer_prefix: str = Field("SOOBIN", min_length=1, max_length=30)
    qr_template: str = Field("compact2", description="compact2 | compact | qr_only | print")
    auto_confirm_webhook: Optional[bool] = True


class BankTransferConfirmRequest(BaseModel):
    transaction_id: Optional[str] = None
    transaction_ref: Optional[str] = None
    received_amount: Optional[float] = None
    transfer_amount: Optional[float] = None
    note: Optional[str] = "Chủ cửa hàng / Quản lý xác nhận đã nhận tiền chuyển khoản thành công"


class CustomerReportTransferRequest(BaseModel):
    transaction_ref: Optional[str] = None
    note: Optional[str] = "Khách hàng xác nhận đã chuyển khoản qua QR ngân hàng"
    transfer_note: Optional[str] = None
    auto_verify_webhook: bool = False
    auto_verify: Optional[bool] = None


class RealBankWebhookPayload(BaseModel):
    gateway: Optional[str] = "VIETQR_WEBHOOK"
    content: str = Field(..., min_length=3, description="Nội dung chuyển khoản ngân hàng (chứa mã đơn hàng SOOBIN-... hoặc POS-...)")
    transfer_amount: float = Field(..., gt=0)
    transaction_id: Optional[str] = None
    bank_code: Optional[str] = None
    account_no: Optional[str] = None
    account_number: Optional[str] = None


class RMATicketUpdateRequest(BaseModel):
    status: str = Field(..., description="NEW | RECEIVED_BY_SALES | APPROVED | RECEIVED_AT_WAREHOUSE | COMPLETED | REJECTED")
    staff_note: Optional[str] = None
    resolution_note: Optional[str] = None




