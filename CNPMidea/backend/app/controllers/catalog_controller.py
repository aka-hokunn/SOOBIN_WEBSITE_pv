from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import re
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.services.catalog_service import CatalogService
from app.schemas.all_schemas import (
    ProductCreateRequest, ProductUpdateRequest,
    ReviewCreateRequest, ReviewModerateRequest, AIChatRequest,
    ProductSalePriceUpdateRequest, BulkSaleUpdateRequest
)
from app.models.entities import ProductionProduct, ProductionVariant, ProductionInventory, ProductionProductImage, UserAccount

router = APIRouter(prefix="/catalog", tags=["Catalog"])

@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    svc = CatalogService(db)
    return svc.list_categories()

@router.get("/sizes")
def get_sizes(db: Session = Depends(get_db)):
    svc = CatalogService(db)
    return svc.list_sizes()

@router.get("/colors")
def get_colors(db: Session = Depends(get_db)):
    svc = CatalogService(db)
    return svc.list_colors()

@router.get("/showcase")
def get_storefront_showcase(
    per_rail: int = Query(10, ge=3, le=16),
    db: Session = Depends(get_db)
):
    """Trang bìa Storefront: sản phẩm Hot (bán chạy), Trending (đang được săn) và Giảm giá sâu."""
    svc = CatalogService(db)
    return svc.get_storefront_showcase(per_rail=per_rail)

@router.get("/products")
def list_products(
    category: Optional[str] = None,
    audience: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    q: Optional[str] = None,
    size_id: Optional[int] = None,
    color_id: Optional[int] = None,
    on_sale: Optional[bool] = None,
    sort_by: str = "newest",
    limit: int = Query(20, ge=1, le=20),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    svc = CatalogService(db)
    return svc.search_products(
        category_slug=category,
        target_audience=audience,
        min_price=min_price,
        max_price=max_price,
        keyword=q,
        size_id=size_id,
        color_id=color_id,
        on_sale=on_sale,
        sort_by=sort_by,
        limit=limit,
        offset=offset
    )

@router.get("/products/manage")
def list_products_for_management(
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db)
):
    svc = CatalogService(db)
    products = svc.catalog_repo.list_products_for_management()
    disc_map = svc._get_product_discount_map([p.id for p in products])
    res = []
    for p in products:
        base_p = float(p.base_price)
        pct = disc_map.get(p.id, 0.0)
        sale_p = round(base_p * (1.0 - pct / 100.0)) if pct > 0 else base_p
        total_qty = sum((v.inventory.available_quantity if v.inventory else 0) for v in p.variants)
        total_val = sum((float(v.inventory.inventory_value) if v.inventory else 0.0) for v in p.variants)
        avg_cost = round(total_val / total_qty, 2) if total_qty > 0 else round(base_p * 0.55, 2)
        margin_pct = round(((sale_p - avg_cost) / sale_p) * 100.0, 1) if sale_p > 0 else 0.0

        res.append({
            "id": p.id, "category_id": p.category_id, "category_name": p.category.name if p.category else "",
            "code": p.code, "slug": p.slug, "name": p.name,
            "base_price": base_p,
            "sale_price": sale_p,
            "discount_percent": pct,
            "on_sale": pct > 0,
            "avg_unit_cost": avg_cost,
            "gross_margin_percent": margin_pct,
            "target_audience": p.target_audience, "description": p.description, "status": p.status, "archived": p.deleted_at is not None,
            "image_url": p.images[0].file_path if p.images else "/static/images/placeholder.webp",
            "variants": [{"id": v.id, "size_id": v.size_id, "size_name": v.size.name if v.size else "",
                "color_id": v.color_id, "color_name": v.color.name if v.color else "", "sku": v.sku,
                "available_quantity": v.inventory.available_quantity if v.inventory else 0,
                "is_active": v.is_active} for v in p.variants]
        })
    return res

@router.put("/products/{product_id}/sale-price")
def update_product_sale_price(
    product_id: int,
    req: ProductSalePriceUpdateRequest,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db)
):
    svc = CatalogService(db)
    try:
        effective_on_sale = False if req.clear_sale else req.is_on_sale
        return svc.set_product_sale_price(
            product_id=product_id,
            base_price=req.base_price,
            sale_price=req.sale_price,
            discount_percent=req.discount_percent,
            is_on_sale=effective_on_sale
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/products/bulk-sale")
def bulk_update_product_sale(
    req: BulkSaleUpdateRequest,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db)
):
    svc = CatalogService(db)
    effective_pct = 0.0 if req.clear_sale else req.discount_percent
    return svc.bulk_set_sale_price(
        discount_percent=effective_pct,
        category_id=req.category_id,
        target_audience=req.target_audience
    )

@router.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(
    req: ProductCreateRequest,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db)
):
    slug_base = re.sub(r"[^a-z0-9]+", "-", req.name.lower()).strip("-") or req.code.lower()
    slug = f"{slug_base}-{req.code.lower()}"
    product = ProductionProduct(
        category_id=req.category_id, product_line_id=req.product_line_id, code=req.code.strip(), slug=slug,
        name=req.name.strip(), base_price=req.base_price, target_audience=req.target_audience,
        skill_level=req.skill_level, description=req.description, care_instructions=req.care_instructions,
        specifications=req.specifications or {}, size_chart=req.size_chart or {}, tags=req.tags or [], status="Selling"
    )
    try:
        if not req.variants:
            raise ValueError("Sản phẩm cần ít nhất một biến thể size và màu sắc.")
        db.add(product)
        db.flush()
        for spec in req.variants:
            variant = ProductionVariant(product_id=product.id, size_id=spec.size_id, color_id=spec.color_id, sku=spec.sku.strip())
            db.add(variant)
            db.flush()
            db.add(ProductionInventory(variant_id=variant.id, available_quantity=0, inventory_value=0, low_stock_threshold=5))
        if req.image_url:
            db.add(ProductionProductImage(product_id=product.id, file_path=req.image_url.strip(), alt_text=product.name, sort_order=0))
        db.commit()
        return {"id": product.id, "slug": product.slug, "message": "Đã tạo sản phẩm và các biến thể."}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Không thể lưu sản phẩm. Hãy kiểm tra mã sản phẩm, SKU, size và màu có bị trùng hoặc không hợp lệ.")

@router.put("/products/{product_id}")
def update_product(
    product_id: int,
    req: ProductUpdateRequest,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db)
):
    product = CatalogService(db).catalog_repo.update_product(product_id, req.model_dump(exclude_unset=True))
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm.")
    db.commit()
    return {"message": "Đã lưu thay đổi sản phẩm."}

@router.get("/lookbook-bundles")
def get_lookbook_bundles(db: Session = Depends(get_db)):
    svc = CatalogService(db)
    return svc.get_lookbook_bundles()

@router.get("/compare")
def compare_products(
    ids: str = Query(..., description="Comma-separated product IDs, e.g., 1,2,3"),
    db: Session = Depends(get_db)
):
    svc = CatalogService(db)
    parsed_ids = []
    for part in ids.split(","):
        part = part.strip()
        if part.isdigit():
            parsed_ids.append(int(part))
    return svc.compare_products(parsed_ids)

@router.get("/products/{slug_or_id}/spatial-3d")
def get_product_spatial_3d(slug_or_id: str, db: Session = Depends(get_db)):
    svc = CatalogService(db)
    res = svc.get_product_spatial_3d(slug_or_id)
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cấu hình 3D cho sản phẩm.")
    return res

@router.get("/products/{slug_or_id}")
def get_product(slug_or_id: str, db: Session = Depends(get_db)):
    svc = CatalogService(db)
    prod = svc.get_product_detail(slug_or_id)
    if not prod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy sản phẩm.")
    return prod

@router.get("/outlet")
def list_outlet_products(db: Session = Depends(get_db)):
    svc = CatalogService(db)
    return svc.search_products(on_sale=True)

@router.delete("/products/{product_id}")
def delete_product(product_id: int, user: UserAccount = Depends(require_role(["ADMIN", "MANAGER"])), db: Session = Depends(get_db)):
    svc = CatalogService(db)
    product = svc.catalog_repo.get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm.")
    svc.catalog_repo.soft_delete_product(product_id)
    db.commit()
    return {"message": "Đã chuyển sản phẩm sang trạng thái ngừng kinh doanh (Soft Delete)."}

@router.post("/products/{product_id}/restore")
def restore_product(product_id: int, user: UserAccount = Depends(require_role(["ADMIN", "MANAGER"])), db: Session = Depends(get_db)):
    product = db.query(ProductionProduct).filter(ProductionProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm.")
    product.deleted_at = None
    product.status = "Selling"
    db.commit()
    return {"message": "Đã khôi phục sản phẩm."}

# -----------------------------------------------------------------------------
# REVIEWS & RATINGS ENDPOINTS
# -----------------------------------------------------------------------------

@router.get("/products/{product_id}/reviews")
def get_product_reviews(product_id: int, db: Session = Depends(get_db)):
    svc = CatalogService(db)
    return svc.list_product_reviews(product_id)

@router.post("/products/{product_id}/reviews", status_code=status.HTTP_201_CREATED)
def submit_product_review(
    product_id: int,
    req: ReviewCreateRequest,
    user: UserAccount = Depends(require_role(["CUSTOMER"])),
    db: Session = Depends(get_db)
):
    svc = CatalogService(db)
    try:
        return svc.create_product_review(
            account_id=user.id,
            product_id=product_id,
            order_id=req.order_id,
            rating=req.rating,
            content=req.content
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/reviews/manage")
def list_all_reviews_for_admin(
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db)
):
    svc = CatalogService(db)
    return svc.list_all_reviews_for_admin()

@router.put("/reviews/{review_id}/moderate")
def moderate_review(
    review_id: int,
    req: ReviewModerateRequest,
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db)
):
    svc = CatalogService(db)
    try:
        return svc.moderate_review(review_id=review_id, moderator_id=user.id, status=req.status)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# -----------------------------------------------------------------------------
# AI CHATBOX & SIZE ADVISOR ENDPOINT
# -----------------------------------------------------------------------------

@router.post("/ai-advisor")
def ai_swimwear_advisor(req: AIChatRequest, db: Session = Depends(get_db)):
    svc = CatalogService(db)
    return svc.ai_advisor(
        message=req.message,
        height_cm=req.height_cm,
        weight_kg=req.weight_kg,
        bust_cm=req.bust_cm,
        waist_cm=req.waist_cm,
        hips_cm=req.hips_cm,
        gender=req.gender
    )

