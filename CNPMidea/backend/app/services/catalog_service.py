from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
import re
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from app.repositories.catalog_repository import CatalogRepository
from app.repositories.promotion_repository import PromotionRepository
from app.models.entities import (
    ProductionProduct, ProductionVariant, ProductionProductImage,
    ProductionInventory, ProductionReview, ProductionOrder, ProductionOrderItem,
    ProductionPromotion, ProductionPromotionProduct, UserAccount
)

class CatalogService:
    def __init__(self, db: Session):
        self.db = db
        self.catalog_repo = CatalogRepository(db)
        self.promo_repo = PromotionRepository(db)

    def _get_product_discount_map(self, product_ids: List[int]) -> Dict[int, float]:
        if not product_ids:
            return {}
        active_promos = self.promo_repo.get_active_product_promotions(product_ids)
        if not active_promos:
            return {}
        promo_pct_map = {p.id: float(p.discount_percent) for p in active_promos}
        links = self.db.query(ProductionPromotionProduct).filter(
            ProductionPromotionProduct.product_id.in_(product_ids)
        ).all()
        best_map: Dict[int, float] = {}
        for link in links:
            if link.promotion_id in promo_pct_map:
                pct = promo_pct_map[link.promotion_id]
                if pct > best_map.get(link.product_id, 0.0):
                    best_map[link.product_id] = pct
        return best_map

    def list_categories(self) -> List[Dict[str, Any]]:
        cats = self.catalog_repo.list_categories()
        return [
            {
                "id": c.id,
                "parent_id": c.parent_id,
                "name": c.name,
                "slug": c.slug,
                "sort_order": c.sort_order,
                "is_active": c.is_active
            }
            for c in cats
        ]

    def list_sizes(self) -> List[Dict[str, Any]]:
        sizes = self.catalog_repo.list_sizes()
        return [{"id": s.id, "code": s.code, "name": s.name} for s in sizes]

    def list_colors(self) -> List[Dict[str, Any]]:
        colors = self.catalog_repo.list_colors()
        return [{"id": c.id, "code": c.code, "name": c.name, "hex_code": c.hex_code} for c in colors]

    def get_product_detail(self, slug_or_id: str) -> Optional[Dict[str, Any]]:
        if slug_or_id.isdigit():
            prod = self.catalog_repo.get_product_by_id(int(slug_or_id))
        else:
            prod = self.catalog_repo.get_product_by_slug(slug_or_id)

        if not prod:
            return None

        variants = []
        for v in prod.variants:
            if v.is_active:
                avail = v.inventory.available_quantity if v.inventory else 0
                variants.append({
                    "id": v.id,
                    "product_id": v.product_id,
                    "size_id": v.size_id,
                    "size_name": v.size.name if v.size else "",
                    "size_code": v.size.code if v.size else "",
                    "color_id": v.color_id,
                    "color_name": v.color.name if v.color else "",
                    "color_hex": v.color.hex_code if v.color else "",
                    "sku": v.sku,
                    "available_quantity": avail,
                    "is_active": v.is_active
                })

        images = [
            {
                "id": img.id,
                "color_id": img.color_id,
                "file_path": img.file_path,
                "alt_text": img.alt_text,
                "sort_order": img.sort_order
            }
            for img in prod.images
        ]

        disc_map = self._get_product_discount_map([prod.id])
        disc_pct = disc_map.get(prod.id, 0.0)
        base_p = float(prod.base_price)
        disc_p = round(base_p * (1.0 - disc_pct / 100.0)) if disc_pct > 0 else base_p

        reviews_info = self.list_product_reviews(prod.id)
        spatial_3d = self.build_spatial_3d_metadata(prod, variants, images)

        return {
            "id": prod.id,
            "category_id": prod.category_id,
            "category_name": prod.category.name if prod.category else "",
            "product_line_id": prod.product_line_id,
            "code": prod.code,
            "slug": prod.slug,
            "name": prod.name,
            "base_price": base_p,
            "discounted_price": disc_p,
            "discount_percent": disc_pct,
            "target_audience": prod.target_audience,
            "skill_level": prod.skill_level,
            "description": prod.description,
            "care_instructions": prod.care_instructions,
            "specifications": prod.specifications or {},
            "size_chart": prod.size_chart or {},
            "tags": prod.tags or [],
            "status": prod.status,
            "images": images,
            "variants": variants,
            "avg_rating": reviews_info["avg_rating"],
            "review_count": reviews_info["review_count"],
            "reviews": reviews_info["reviews"],
            "spatial_3d": spatial_3d
        }

    def search_products(
        self,
        category_slug: Optional[str] = None,
        target_audience: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        keyword: Optional[str] = None,
        size_id: Optional[int] = None,
        color_id: Optional[int] = None,
        on_sale: Optional[bool] = None,
        sort_by: str = "newest",
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        prods = self.catalog_repo.search_products(
            category_slug=category_slug,
            target_audience=target_audience,
            min_price=min_price,
            max_price=max_price,
            keyword=keyword,
            size_id=size_id,
            color_id=color_id,
            on_sale=on_sale,
            sort_by=sort_by,
            limit=limit,
            offset=offset
        )

        prod_ids = [p.id for p in prods]
        disc_map = self._get_product_discount_map(prod_ids)
        return [self._serialize_list_item(p, disc_map) for p in prods]

    def _serialize_list_item(self, p: ProductionProduct, disc_map: Dict[int, float]) -> Dict[str, Any]:
        total_stock = sum((v.inventory.available_quantity if v.inventory else 0) for v in p.variants)
        sorted_imgs = [img.file_path for img in sorted(p.images, key=lambda x: x.sort_order)] if p.images else ["/static/images/placeholder.webp"]
        first_img = sorted_imgs[0]
        base_p = float(p.base_price)
        disc_pct = disc_map.get(p.id, 0.0)
        disc_p = round(base_p * (1.0 - disc_pct / 100.0)) if disc_pct > 0 else base_p
        return {
            "id": p.id,
            "category_id": p.category_id,
            "category_name": p.category.name if p.category else "",
            "code": p.code,
            "slug": p.slug,
            "name": p.name,
            "base_price": base_p,
            "discounted_price": disc_p,
            "discount_percent": disc_pct,
            "target_audience": p.target_audience,
            "skill_level": p.skill_level,
            "status": p.status,
            "image_url": first_img,
            "gallery_images": sorted_imgs,
            "total_stock": total_stock,
            "variants_count": len(p.variants)
        }

    # -------------------------------------------------------------------------
    # STOREFRONT COVER SHOWCASE (HOT / TRENDING / SALE) — REAL SALES DATA
    # -------------------------------------------------------------------------
    def get_storefront_showcase(self, per_rail: int = 10) -> Dict[str, Any]:
        prods = self.catalog_repo.search_products(limit=500, offset=0)
        if not prods:
            return {"hot": [], "trending": [], "sale": [], "stats": {}, "sale_ends_at": None}

        prod_ids = [p.id for p in prods]
        disc_map = self._get_product_discount_map(prod_ids)

        # Units sold per product (all non-cancelled orders) and in the last 30 days
        valid_status = ProductionOrder.status.notin_(["Đã hủy", "Đã hoàn tiền"])
        sold_rows = self.db.query(
            ProductionVariant.product_id, func.coalesce(func.sum(ProductionOrderItem.quantity), 0)
        ).join(ProductionOrderItem, ProductionOrderItem.variant_id == ProductionVariant.id
        ).join(ProductionOrder, ProductionOrder.id == ProductionOrderItem.order_id
        ).filter(valid_status, ProductionVariant.product_id.in_(prod_ids)
        ).group_by(ProductionVariant.product_id).all()
        sold_map = {int(pid): int(q or 0) for pid, q in sold_rows}

        since = datetime.now(timezone.utc) - timedelta(days=30)
        recent_rows = self.db.query(
            ProductionVariant.product_id, func.coalesce(func.sum(ProductionOrderItem.quantity), 0)
        ).join(ProductionOrderItem, ProductionOrderItem.variant_id == ProductionVariant.id
        ).join(ProductionOrder, ProductionOrder.id == ProductionOrderItem.order_id
        ).filter(valid_status, ProductionOrder.placed_at >= since, ProductionVariant.product_id.in_(prod_ids)
        ).group_by(ProductionVariant.product_id).all()
        recent_map = {int(pid): int(q or 0) for pid, q in recent_rows}

        review_rows = self.db.query(
            ProductionReview.product_id, func.avg(ProductionReview.rating), func.count(ProductionReview.id)
        ).filter(
            ProductionReview.moderation_status == "APPROVED",
            ProductionReview.product_id.in_(prod_ids)
        ).group_by(ProductionReview.product_id).all()
        review_map = {int(pid): (round(float(avg or 0), 1), int(cnt or 0)) for pid, avg, cnt in review_rows}

        items: List[Dict[str, Any]] = []
        created_map: Dict[int, datetime] = {}
        for p in prods:
            d = self._serialize_list_item(p, disc_map)
            avg, cnt = review_map.get(p.id, (0.0, 0))
            d["sold_count"] = sold_map.get(p.id, 0)
            d["recent_sold"] = recent_map.get(p.id, 0)
            d["avg_rating"] = avg
            d["review_count"] = cnt
            items.append(d)
            created_map[p.id] = p.created_at

        in_stock = [x for x in items if x["total_stock"] > 0] or items

        hot = sorted(in_stock, key=lambda x: (x["sold_count"], x["total_stock"]), reverse=True)[:per_rail]

        hot_ids = {x["id"] for x in hot[:4]}
        def trend_score(x: Dict[str, Any]) -> tuple:
            score = x["recent_sold"] * 3 + x["review_count"] * 2 + x["avg_rating"]
            created = created_map.get(x["id"])
            return (score, created.timestamp() if created else 0)
        trending = sorted(
            [x for x in in_stock if x["id"] not in hot_ids] or in_stock,
            key=trend_score, reverse=True
        )[:per_rail]

        sale = sorted(
            [x for x in in_stock if x["discount_percent"] > 0],
            key=lambda x: (x["discount_percent"], x["sold_count"]), reverse=True
        )[:per_rail]

        sale_ends_at = None
        active_promos = self.promo_repo.get_active_product_promotions(prod_ids)
        if active_promos:
            nearest = min(active_promos, key=lambda pr: pr.ends_at)
            sale_ends_at = nearest.ends_at.isoformat() if nearest.ends_at else None

        stats = {
            "total_products": len(items),
            "total_sold": sum(x["sold_count"] for x in items),
            "on_sale_count": sum(1 for x in items if x["discount_percent"] > 0),
            "max_discount_percent": max((x["discount_percent"] for x in items), default=0),
            "avg_rating": round(
                sum(a for a, c in review_map.values() if c) / max(1, sum(1 for a, c in review_map.values() if c)), 1
            ) if review_map else 0,
        }
        return {"hot": hot, "trending": trending, "sale": sale, "stats": stats, "sale_ends_at": sale_ends_at}

    # -------------------------------------------------------------------------
    # REVIEWS & RATINGS (PRD SECTION 12)
    # -------------------------------------------------------------------------

    def list_product_reviews(self, product_id: int) -> Dict[str, Any]:
        reviews = self.db.query(ProductionReview).options(
            joinedload(ProductionReview.account)
        ).filter(
            ProductionReview.product_id == product_id,
            ProductionReview.moderation_status == "APPROVED"
        ).order_by(ProductionReview.created_at.desc()).all()

        if not reviews:
            return {"avg_rating": 5.0, "review_count": 0, "reviews": []}

        avg = round(sum(r.rating for r in reviews) / len(reviews), 1)
        items = [
            {
                "id": r.id,
                "product_id": r.product_id,
                "account_id": r.account_id,
                "customer_name": r.account.full_name if r.account else "Khách hàng",
                "rating": r.rating,
                "content": r.content,
                "moderation_status": r.moderation_status,
                "created_at": r.created_at.isoformat()
            }
            for r in reviews
        ]
        return {"avg_rating": avg, "review_count": len(reviews), "reviews": items}

    def create_product_review(
        self,
        account_id: int,
        product_id: int,
        order_id: int,
        rating: int,
        content: str
    ) -> Dict[str, Any]:
        if rating < 1 or rating > 5:
            raise ValueError("Số sao đánh giá phải từ 1 đến 5.")

        prod = self.catalog_repo.get_product_by_id(product_id)
        if not prod:
            raise ValueError("Sản phẩm không tồn tại.")

        # Verify order belongs to customer, is DELIVERED ("Đã giao"), and contains this product
        order = self.db.query(ProductionOrder).options(
            joinedload(ProductionOrder.items).joinedload(ProductionOrderItem.variant)
        ).filter(
            ProductionOrder.id == order_id,
            ProductionOrder.account_id == account_id
        ).first()

        if not order:
            raise ValueError("Đơn hàng không tồn tại hoặc không thuộc tài khoản của bạn.")

        if order.status != "Đã giao":
            raise ValueError("Chỉ được đánh giá sản phẩm sau khi đơn hàng đã được giao thành công (Đã giao).")

        matched_order_item = None
        for oi in order.items:
            if oi.variant and oi.variant.product_id == product_id:
                matched_order_item = oi
                break
            if oi.product_snapshot and (oi.product_snapshot.get("product_id") == product_id or oi.product_snapshot.get("id") == product_id):
                matched_order_item = oi
                break

        if not matched_order_item:
            raise ValueError("Sản phẩm này không nằm trong đơn hàng đã chọn.")

        # Check if already reviewed for this order_item
        existing = self.db.query(ProductionReview).filter(
            ProductionReview.account_id == account_id,
            ProductionReview.product_id == product_id,
            ProductionReview.order_item_id == matched_order_item.id
        ).first()

        if existing:
            existing.rating = rating
            existing.content = content.strip()
            existing.created_at = datetime.now(timezone.utc)
            self.db.commit()
            return {
                "message": "Đã cập nhật đánh giá sản phẩm thành công.",
                "review_id": existing.id,
                "rating": existing.rating
            }

        review = ProductionReview(
            account_id=account_id,
            product_id=product_id,
            order_item_id=matched_order_item.id,
            rating=rating,
            content=content.strip(),
            moderation_status="APPROVED",
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(review)
        self.db.commit()
        return {
            "message": "Cảm ơn bạn đã gửi đánh giá sản phẩm!",
            "review_id": review.id,
            "rating": review.rating
        }

    def list_all_reviews_for_admin(self) -> List[Dict[str, Any]]:
        reviews = self.db.query(ProductionReview).options(
            joinedload(ProductionReview.account),
            joinedload(ProductionReview.product)
        ).order_by(ProductionReview.created_at.desc()).all()
        return [
            {
                "id": r.id,
                "product_id": r.product_id,
                "product_name": r.product.name if r.product else "",
                "account_id": r.account_id,
                "customer_name": r.account.full_name if r.account else "",
                "rating": r.rating,
                "content": r.content,
                "moderation_status": r.moderation_status,
                "created_at": r.created_at.isoformat()
            }
            for r in reviews
        ]

    def moderate_review(self, review_id: int, moderator_id: int, status: str) -> Dict[str, Any]:
        status_clean = status.upper().strip()
        if status_clean not in ("APPROVED", "HIDDEN"):
            raise ValueError("Trạng thái kiểm duyệt chỉ nhận APPROVED hoặc HIDDEN.")
        review = self.db.query(ProductionReview).filter(ProductionReview.id == review_id).first()
        if not review:
            raise ValueError("Không tìm thấy đánh giá.")
        review.moderation_status = status_clean
        review.moderated_by = moderator_id
        self.db.commit()
        return {
            "message": f"Đã cập nhật trạng thái đánh giá thành {status_clean}.",
            "review_id": review.id,
            "moderation_status": review.moderation_status
        }

    # -------------------------------------------------------------------------
    # AI CHATBOT & SIZE ADVISOR (MO_TA_CNPM SECTION 7)
    # -------------------------------------------------------------------------

    def ai_advisor(
        self,
        message: str,
        height_cm: Optional[float] = None,
        weight_kg: Optional[float] = None,
        bust_cm: Optional[float] = None,
        waist_cm: Optional[float] = None,
        hips_cm: Optional[float] = None,
        gender: Optional[str] = None
    ) -> Dict[str, Any]:
        msg_lower = (message or "").lower()

        # 1. Extract height & weight from text if not explicitly provided
        if height_cm is None:
            # Match patterns like "1m65", "1m6", "165cm", "cao 165"
            m_meter = re.search(r"1\s*m\s*(\d{1,2})", msg_lower)
            if m_meter:
                dec = m_meter.group(1)
                height_cm = 100.0 + (float(dec) * 10 if len(dec) == 1 else float(dec))
            else:
                m_cm = re.search(r"(?:cao\s*)?(\d{3})\s*(?:cm)?", msg_lower)
                if m_cm and 130 <= int(m_cm.group(1)) <= 200:
                    height_cm = float(m_cm.group(1))

        if weight_kg is None:
            m_kg = re.search(r"(\d{2,3}(?:\.\d+)?)\s*(?:kg|ký|cân)", msg_lower)
            if m_kg and 30 <= float(m_kg.group(1)) <= 130:
                weight_kg = float(m_kg.group(1))

        if bust_cm is None:
            m_bust = re.search(r"(?:ngực|vòng\s*1)\s*(\d{2,3})", msg_lower)
            if m_bust:
                bust_cm = float(m_bust.group(1))

        if waist_cm is None:
            m_waist = re.search(r"(?:eo|vòng\s*2)\s*(\d{2,3})", msg_lower)
            if m_waist:
                waist_cm = float(m_waist.group(1))

        # 2. Detect gender / audience
        detected_audience = gender
        if not detected_audience:
            if any(k in msg_lower for k in ["nam", "quần bơi nam", "jammer", "boxer"]):
                detected_audience = "Nam"
            elif any(k in msg_lower for k in ["nữ", "bikini", "một mảnh", "váy bơi", "monokini"]):
                detected_audience = "Nữ"
            elif any(k in msg_lower for k in ["bé", "trẻ em", "kid"]):
                detected_audience = "Trẻ em"

        # 3. Calculate recommended size if weight or height or bust is available
        recommended_size = None
        size_advice = None

        if weight_kg is not None or height_cm is not None or bust_cm is not None:
            w = weight_kg or 52.0
            h = height_cm or 160.0
            is_male = (detected_audience == "Nam")

            if is_male:
                if w < 55 and h < 165:
                    recommended_size = "S"
                elif w <= 65 and h <= 172:
                    recommended_size = "M"
                elif w <= 75 and h <= 178:
                    recommended_size = "L"
                elif w <= 85:
                    recommended_size = "XL"
                else:
                    recommended_size = "2XL"
            else:
                if (w < 45 and h < 156) or (bust_cm and bust_cm < 80):
                    recommended_size = "S"
                elif (w <= 53 and h <= 163) or (bust_cm and 80 <= bust_cm <= 86):
                    recommended_size = "M"
                elif (w <= 60 and h <= 168) or (bust_cm and 87 <= bust_cm <= 92):
                    recommended_size = "L"
                elif w <= 68 or (bust_cm and bust_cm > 92):
                    recommended_size = "XL"
                else:
                    recommended_size = "2XL"

            meas_parts = []
            if height_cm:
                meas_parts.append(f"chiều cao {int(height_cm)}cm")
            if weight_kg:
                meas_parts.append(f"cân nặng {weight_kg:g}kg")
            if bust_cm:
                meas_parts.append(f"vòng ngực {int(bust_cm)}cm")
            if waist_cm:
                meas_parts.append(f"vòng eo {int(waist_cm)}cm")
            meas_str = ", ".join(meas_parts)

            size_advice = (
                f"Dựa trên số đo ({meas_str}), AI Soobin khuyên bạn chọn **Size {recommended_size}** "
                f"để ôm vừa vặn tôn dáng và tối ưu thủy động học. Nếu bạn thích mặc thoải mái hơn khi đi dạo biển, có thể cân nhắc nhích lên 1 size."
            )

        # 4. Suggest matching products from catalog
        category_slug = None
        on_sale_filter = None
        kw_search = None

        if any(k in msg_lower for k in ["kính", "mũ", "nón", "túi", "chân vịt", "phụ kiện"]):
            category_slug = "phu-kien-boi-loi"
        elif detected_audience == "Nam":
            category_slug = "do-boi-nam"
        elif detected_audience == "Nữ":
            category_slug = "do-boi-nu"

        if any(k in msg_lower for k in ["sale", "giảm giá", "khuyến mãi", "outlet", "rẻ"]):
            on_sale_filter = True

        for term in ["tay dài", "rashguard", "chống nắng", "một mảnh", "bikini", "kính bơi", "thi đấu", "jammer"]:
            if term in msg_lower:
                kw_search = term
                break

        suggested = self.search_products(
            category_slug=category_slug,
            target_audience=detected_audience if not category_slug else None,
            keyword=kw_search,
            on_sale=on_sale_filter,
            limit=4
        )
        if not suggested:
            suggested = self.search_products(limit=4)

        # 5. Compose helpful conversational response
        reply_parts = []
        if size_advice:
            reply_parts.append(size_advice)

        if any(k in msg_lower for k in ["đổi trả", "bảo hành", "chính sách"]):
            reply_parts.append(
                "Chính sách Soobin Swimwear: Hỗ trợ tư vấn size chuẩn trước khi đặt, kiểm tra hàng khi nhận. "
                "Đơn VietQR được hoàn tiền nhanh chóng nếu hủy trước khi xác nhận xử lý."
            )
        elif any(k in msg_lower for k in ["ship", "vận chuyển", "giao hàng"]):
            reply_parts.append(
                "Soobin hợp tác cùng đơn vị vận chuyển GHTK với phí ship cố định 30.000đ toàn quốc, thời gian giao từ 2 - 4 ngày."
            )
        elif not size_advice:
            if detected_audience:
                reply_parts.append(
                    f"Chào bạn! Soobin xin gợi ý các mẫu đồ bơi **{detected_audience}** chất liệu chống tia UV UPF 50+ và kháng Clo cao cấp đang được yêu thích nhất:"
                )
            elif on_sale_filter:
                reply_parts.append(
                    "Hiện tại Soobin đang có chương trình ưu đãi hấp dẫn! Bạn cũng có thể nhập mã **SOOBIN15** giảm 15% hoặc tự động giảm 10% cho đơn từ 500K. Dưới đây là các sản phẩm nổi bật:"
                )
            else:
                reply_parts.append(
                    "Xin chào! Mình là **Trợ lý AI Soobin Swimwear**. Mình có thể giúp bạn **chọn size chuẩn** (hãy cho mình biết chiều cao, cân nặng hoặc số đo 3 vòng) và **đề xuất mẫu đồ bơi** phù hợp nhất với nhu cầu của bạn!"
                )

        return {
            "reply": " ".join(reply_parts),
            "recommended_size": recommended_size,
            "size_advice": size_advice,
            "suggested_products": suggested[:4]
        }

    # -------------------------------------------------------------------------
    # DIRECT SALE PRICE & BULK MARKDOWN ENGINE
    # -------------------------------------------------------------------------

    def set_product_sale_price(
        self,
        product_id: int,
        base_price: Optional[float] = None,
        sale_price: Optional[float] = None,
        discount_percent: Optional[float] = None,
        is_on_sale: bool = True
    ) -> Dict[str, Any]:
        prod = self.db.query(ProductionProduct).filter(ProductionProduct.id == product_id).first()
        if not prod:
            raise ValueError("Không tìm thấy sản phẩm.")

        if base_price is not None and base_price > 0:
            prod.base_price = base_price

        current_base = float(prod.base_price)

        if not is_on_sale or (discount_percent is not None and discount_percent <= 0 and sale_price is None):
            final_pct = 0.0
            final_sale_price = current_base
        elif sale_price is not None and sale_price > 0:
            if sale_price >= current_base:
                final_pct = 0.0
                final_sale_price = current_base
            else:
                final_pct = round(((current_base - sale_price) / current_base) * 100.0, 2)
                final_sale_price = round(sale_price)
        elif discount_percent is not None and discount_percent > 0:
            final_pct = round(min(95.0, max(0.0, float(discount_percent))), 2)
            final_sale_price = round(current_base * (1.0 - final_pct / 100.0))
        else:
            final_pct = 0.0
            final_sale_price = current_base

        specs = dict(prod.specifications or {})
        specs["sale_price"] = final_sale_price
        specs["discount_percent"] = final_pct
        prod.specifications = specs

        promo_code = f"DIRECT-SALE-{prod.id}"
        promo = self.promo_repo.get_by_code(promo_code)
        now = datetime.now(timezone.utc)

        if final_pct > 0:
            if not promo:
                promo = ProductionPromotion(
                    code=promo_code,
                    name=f"Ưu đãi trực tiếp SP {prod.code}",
                    promotion_type="PRODUCT",
                    discount_percent=final_pct,
                    minimum_order_amount=0,
                    starts_at=now - timedelta(days=1),
                    ends_at=now + timedelta(days=365),
                    is_active=True
                )
                self.db.add(promo)
                self.db.flush()
            else:
                promo.discount_percent = final_pct
                promo.starts_at = now - timedelta(days=1)
                promo.ends_at = now + timedelta(days=365)
                promo.is_active = True

            link = self.db.query(ProductionPromotionProduct).filter(
                ProductionPromotionProduct.promotion_id == promo.id,
                ProductionPromotionProduct.product_id == prod.id
            ).first()
            if not link:
                self.db.add(ProductionPromotionProduct(promotion_id=promo.id, product_id=prod.id))
        else:
            if promo:
                promo.is_active = False

        self.db.commit()
        prod_summary = {
            "id": prod.id,
            "product_id": prod.id,
            "code": prod.code,
            "name": prod.name,
            "base_price": current_base,
            "sale_price": final_sale_price,
            "discount_percent": final_pct,
            "on_sale": final_pct > 0,
        }
        return {
            **prod_summary,
            "product": prod_summary,
            "message": f"Đã cập nhật giá bán sản phẩm {prod.code}: {final_sale_price:,.0f}đ (-{final_pct}%)" if final_pct > 0 else f"Đã đưa sản phẩm {prod.code} về giá gốc {current_base:,.0f}đ."
        }

    def bulk_set_sale_price(
        self,
        discount_percent: float,
        category_id: Optional[int] = None,
        target_audience: Optional[str] = None
    ) -> Dict[str, Any]:
        query = self.db.query(ProductionProduct).filter(ProductionProduct.deleted_at == None)
        if category_id:
            query = query.filter(ProductionProduct.category_id == category_id)
        if target_audience:
            query = query.filter(ProductionProduct.target_audience == target_audience)
        products = query.all()
        for p in products:
            self.set_product_sale_price(
                product_id=p.id,
                discount_percent=discount_percent,
                is_on_sale=(discount_percent > 0)
            )
        return {
            "updated_count": len(products),
            "discount_percent": discount_percent,
            "message": f"Đã áp dụng mức giảm {discount_percent}% cho {len(products)} sản phẩm." if discount_percent > 0 else f"Đã gỡ giảm giá cho {len(products)} sản phẩm."
        }

    # -------------------------------------------------------------------------
    # 3D SPATIAL SHOWROOM METADATA, COMPARISON MATRIX & LOOKBOOK BUNDLES
    # -------------------------------------------------------------------------

    def build_spatial_3d_metadata(
        self,
        prod: ProductionProduct,
        variants: List[Dict[str, Any]],
        images: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        name_low = (prod.name or "").lower()
        cat_name_low = (prod.category.name if prod.category else "").lower()

        if any(k in name_low or k in cat_name_low for k in ["kính", "mũ", "nón", "túi", "phao", "phụ kiện"]):
            geometry_type = "goggles_3d"
        elif any(k in name_low for k in ["bikini", "2 mảnh", "hai mảnh"]):
            geometry_type = "bikini_3d"
        elif any(k in name_low for k in ["tay dài", "rashguard", "chống nắng", "khoác"]):
            geometry_type = "rashguard_3d"
        elif (prod.target_audience or "").lower() == "nam" or any(k in name_low for k in ["jammer", "quần bơi", "trunk", "boxer"]):
            geometry_type = "jammer_3d"
        else:
            geometry_type = "onepiece_3d"

        color_map: Dict[int, Dict[str, Any]] = {}
        for v in variants:
            cid = v["color_id"]
            if cid not in color_map:
                color_map[cid] = {
                    "color_id": cid,
                    "color_name": v["color_name"],
                    "color_hex": v["color_hex"] or "#0284c7",
                    "available_quantity": 0
                }
            color_map[cid]["available_quantity"] += v["available_quantity"]

        color_palettes = list(color_map.values())
        if not color_palettes:
            color_palettes = [{"color_id": 1, "color_name": "Xanh Đại Dương", "color_hex": "#0284c7", "available_quantity": 10}]

        specs = prod.specifications or {}
        hotspots = [
            {
                "id": "hs-uv",
                "title": "Chống Tia Cực Tím UPF 50+",
                "detail": "Cấu trúc sợi dệt mật độ cao ngăn chặn 98% tia UVA/UVB dưới nắng biển gắt.",
                "position": [0.55, 0.65, 0.35],
                "badge": "UPF 50+"
            },
            {
                "id": "hs-chlorine",
                "title": "Sợi Kháng Clo XtraLife™",
                "detail": "Chống giãn nhão trong môi trường nước hồ bơi xử lý Clo suốt hơn 300 giờ bơi liên tục.",
                "position": [-0.55, 0.25, 0.40],
                "badge": "300h Clo-Proof"
            },
            {
                "id": "hs-seam",
                "title": "Đường May Flatlock 4 Chiều",
                "detail": "Đường may phẳng ôm sát cơ thể, triệt tiêu ma sát nước và chống hằn da khi vận động mạnh.",
                "position": [0.48, -0.35, 0.38],
                "badge": "4-Way Stretch"
            },
            {
                "id": "hs-hydro",
                "title": "Thiết Kế Thủy Động Học Hydro-Fit",
                "detail": "Giảm hệ số cản nước xuống 0.18, giúp lướt nhẹ và khô nhanh gấp 3 lần vải thông thường.",
                "position": [-0.45, -0.55, 0.32],
                "badge": "Hydro-Fit 3D"
            }
        ]

        return {
            "product_id": prod.id,
            "product_code": prod.code,
            "product_name": prod.name,
            "geometry_type": geometry_type,
            "primary_texture_url": images[0]["file_path"] if images else "/static/images/placeholder.webp",
            "color_palettes": color_palettes,
            "material_physics": {
                "fabric": specs.get("Chất liệu", "80% Polyamide Recycled, 20% Elastane Carvico Ý"),
                "stretch_factor": 1.38,
                "uv_protection": "UPF 50+",
                "chlorine_resistance_hours": 300,
                "hydro_drag_coeff": 0.18,
                "roughness": 0.32,
                "metalness": 0.14
            },
            "spatial_hotspots": hotspots,
            "lighting_presets": [
                {"id": "ocean-daylight", "name": "Nắng Biển Địa Trung Hải", "ambient": "#e0f2fe", "directional": "#38bdf8", "intensity": 1.15},
                {"id": "ibiza-sunset", "name": "Hoàng Hôn Ibiza", "ambient": "#ffedd5", "directional": "#fb923c", "intensity": 1.25},
                {"id": "neon-runway", "name": "Sàn Diễn Đêm Neon", "ambient": "#312e81", "directional": "#c084fc", "intensity": 1.35},
                {"id": "studio-pure", "name": "Ánh Sáng Studio Chuẩn Màu", "ambient": "#ffffff", "directional": "#f8fafc", "intensity": 1.05}
            ],
            "fit_simulation": {
                "default_height_cm": 165 if prod.target_audience != "Nam" else 173,
                "default_weight_kg": 52 if prod.target_audience != "Nam" else 68,
                "sizes": ["S", "M", "L", "XL", "2XL"]
            }
        }

    def get_product_spatial_3d(self, slug_or_id: str) -> Optional[Dict[str, Any]]:
        detail = self.get_product_detail(slug_or_id)
        if not detail:
            return None
        return detail["spatial_3d"]

    def compare_products(self, product_ids: List[int]) -> List[Dict[str, Any]]:
        results = []
        for pid in product_ids[:4]:
            detail = self.get_product_detail(str(pid))
            if not detail:
                continue
            total_stock = sum(v["available_quantity"] for v in detail["variants"])
            sizes = sorted(list({v["size_name"] for v in detail["variants"] if v.get("size_name")}))
            colors = sorted(list({v["color_name"] for v in detail["variants"] if v.get("color_name")}))
            results.append({
                "id": detail["id"],
                "code": detail["code"],
                "slug": detail["slug"],
                "name": detail["name"],
                "category_name": detail["category_name"],
                "target_audience": detail["target_audience"],
                "skill_level": detail["skill_level"] or "Đa năng / Resort & Tập luyện",
                "base_price": detail["base_price"],
                "discounted_price": detail["discounted_price"],
                "discount_percent": detail["discount_percent"],
                "avg_rating": detail["avg_rating"],
                "review_count": detail["review_count"],
                "total_stock": total_stock,
                "sizes": sizes,
                "colors": colors,
                "image_url": detail["images"][0]["file_path"] if detail["images"] else "/static/images/placeholder.webp",
                "material_physics": detail["spatial_3d"]["material_physics"],
                "geometry_type": detail["spatial_3d"]["geometry_type"],
                "default_variant_id": next((v["id"] for v in detail["variants"] if v["available_quantity"] > 0), detail["variants"][0]["id"] if detail["variants"] else None)
            })
        return results

    def get_lookbook_bundles(self) -> List[Dict[str, Any]]:
        all_prods = self.search_products(limit=20)
        if not all_prods:
            return []

        detailed_prods = []
        for p in all_prods[:12]:
            d = self.get_product_detail(str(p["id"]))
            if d and d["variants"]:
                in_stock_var = next((v for v in d["variants"] if v["available_quantity"] > 0), d["variants"][0])
                d["chosen_variant"] = in_stock_var
                detailed_prods.append(d)

        women_items = [d for d in detailed_prods if d["target_audience"] == "Nữ"]
        men_items = [d for d in detailed_prods if d["target_audience"] == "Nam"]
        acc_items = [d for d in detailed_prods if "phụ kiện" in (d["category_name"] or "").lower() or d["spatial_3d"]["geometry_type"] == "goggles_3d"]

        def _fmt_bundle_item(d: Dict[str, Any]) -> Dict[str, Any]:
            v = d["chosen_variant"]
            return {
                "product_id": d["id"],
                "variant_id": v["id"],
                "name": d["name"],
                "code": d["code"],
                "size_name": v["size_name"],
                "color_name": v["color_name"],
                "color_hex": v["color_hex"],
                "base_price": d["base_price"],
                "discounted_price": d["discounted_price"],
                "image_url": d["images"][0]["file_path"] if d["images"] else "/static/images/placeholder.webp",
                "geometry_type": d["spatial_3d"]["geometry_type"]
            }

        bundles = []
        set1_raw = (women_items[:2] + acc_items[:1]) or detailed_prods[:2]
        if set1_raw:
            items1 = [_fmt_bundle_item(x) for x in set1_raw]
            bundles.append({
                "id": "bundle-resort-queen",
                "name": "Set Đi Biển Resort & Chống Nắng UV Toàn Diện",
                "badge": "LOOKBOOK 3D NỔI BẬT",
                "description": "Sự kết hợp hoàn hảo giữa đồ bơi tôn dáng cao cấp và phụ kiện chống tia cực tím UPF 50+ cho kỳ nghỉ dưỡng sang trọng.",
                "theme_gradient": "from-sky-500 via-cyan-500 to-teal-500",
                "items": items1,
                "total_base_price": sum(i["base_price"] for i in items1),
                "total_bundle_price": sum(i["discounted_price"] for i in items1)
            })

        set2_raw = (men_items[:2] + acc_items[:1]) or detailed_prods[1:3] or detailed_prods[:2]
        if set2_raw:
            items2 = [_fmt_bundle_item(x) for x in set2_raw]
            bundles.append({
                "id": "bundle-pro-hydro",
                "name": "Set Thi Đấu Thủy Động Học Pro-Hydro",
                "badge": "CHUẨN VẬN ĐỘNG VIÊN",
                "description": "Bộ trang bị tối ưu hệ số cản nước Hydro-Fit 0.18 kết hợp phụ kiện bơi chuyên nghiệp kháng Clo 300 giờ.",
                "theme_gradient": "from-indigo-600 via-sky-600 to-cyan-500",
                "items": items2,
                "total_base_price": sum(i["base_price"] for i in items2),
                "total_bundle_price": sum(i["discounted_price"] for i in items2)
            })

        return bundles



