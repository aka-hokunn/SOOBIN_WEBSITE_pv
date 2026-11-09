from typing import Dict, Any, List
import io
import csv
from sqlalchemy.orm import Session, joinedload
from app.repositories.report_repository import ReportRepository
from app.models.entities import (
    ProductionOrder, ProductionOrderItem, ProductionVariant,
    ProductionProduct, ProductionInventory
)

class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self.report_repo = ReportRepository(db)

    def get_dashboard_data(self) -> Dict[str, Any]:
        return self.report_repo.get_dashboard_summary()

    def get_advanced_analytics(self) -> Dict[str, Any]:
        orders = self.db.query(ProductionOrder).options(
            joinedload(ProductionOrder.items)
        ).order_by(ProductionOrder.placed_at.desc()).all()

        variants = self.db.query(ProductionVariant).options(
            joinedload(ProductionVariant.product).joinedload(ProductionProduct.category),
            joinedload(ProductionVariant.size),
            joinedload(ProductionVariant.color),
            joinedload(ProductionVariant.inventory)
        ).all()

        variant_map = {v.id: v for v in variants}
        cat_stats: Dict[str, Dict[str, Any]] = {}
        payment_stats: Dict[str, Dict[str, Any]] = {}
        sold_by_variant: Dict[int, int] = {}

        for o in orders:
            pm = o.payment_method or "COD"
            if pm not in payment_stats:
                payment_stats[pm] = {"payment_method": pm, "order_count": 0, "revenue": 0.0}
            payment_stats[pm]["order_count"] += 1
            if o.status == "Đã giao":
                payment_stats[pm]["revenue"] += float(o.total_amount)

            for it in o.items:
                sold_by_variant[it.variant_id] = sold_by_variant.get(it.variant_id, 0) + it.quantity
                if o.status == "Đã giao":
                    v = variant_map.get(it.variant_id)
                    cat_name = v.product.category.name if (v and v.product and v.product.category) else "Đồ bơi & Phụ kiện"
                    if cat_name not in cat_stats:
                        cat_stats[cat_name] = {"category_name": cat_name, "units_sold": 0, "revenue": 0.0, "profit": 0.0}
                    rev = float(it.line_total)
                    cost = float(it.unit_cost_snapshot) * it.quantity
                    cat_stats[cat_name]["units_sold"] += it.quantity
                    cat_stats[cat_name]["revenue"] += rev
                    cat_stats[cat_name]["profit"] += (rev - cost)

        replenishment_list = []
        total_restock_budget = 0.0
        for v in variants:
            if not v.is_active or not v.product or v.product.deleted_at is not None:
                continue
            inv = v.inventory
            avail = inv.available_quantity if inv else 0
            thresh = inv.low_stock_threshold if inv else 5
            sold_qty = sold_by_variant.get(v.id, 0)
            unit_cost = round(float(inv.inventory_value) / avail, 2) if (inv and avail > 0) else round(float(v.product.base_price) * 0.55, 2)

            target_stock = max(thresh * 3, sold_qty * 2, 15)
            if avail == 0:
                urgency = "CRITICAL"
                rec_qty = max(20, target_stock)
            elif avail <= thresh:
                urgency = "HIGH"
                rec_qty = max(12, target_stock - avail)
            elif avail < target_stock and sold_qty > 0:
                urgency = "MEDIUM"
                rec_qty = max(6, target_stock - avail)
            else:
                urgency = "NORMAL"
                rec_qty = 0

            est_cost = round(rec_qty * unit_cost, 2)
            if urgency in ("CRITICAL", "HIGH", "MEDIUM"):
                total_restock_budget += est_cost

            replenishment_list.append({
                "variant_id": v.id,
                "sku": v.sku,
                "product_id": v.product_id,
                "product_name": v.product.name,
                "size_name": v.size.name if v.size else "",
                "color_name": v.color.name if v.color else "",
                "available_quantity": avail,
                "low_stock_threshold": thresh,
                "historical_sold": sold_qty,
                "unit_cost_estimate": unit_cost,
                "urgency": urgency,
                "recommended_order_qty": rec_qty,
                "estimated_restock_cost": est_cost
            })

        urgency_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "NORMAL": 3}
        replenishment_list.sort(key=lambda x: (urgency_rank.get(x["urgency"], 9), x["available_quantity"], -x["historical_sold"]))

        return {
            "revenue_by_category": list(cat_stats.values()),
            "payment_method_breakdown": list(payment_stats.values()),
            "replenishment_recommendations": replenishment_list,
            "urgent_restock_count": sum(1 for r in replenishment_list if r["urgency"] in ("CRITICAL", "HIGH")),
            "estimated_total_restock_budget": round(total_restock_budget, 2)
        }

    def export_csv_report(self, report_type: str = "orders") -> str:
        output = io.StringIO()
        output.write("\ufeff")  # UTF-8 BOM for Excel
        writer = csv.writer(output)

        if report_type == "inventory":
            writer.writerow(["Mã SKU", "Tên Sản Phẩm", "Size", "Màu Sắc", "Tồn Khả Dụng", "Ngưỡng Cảnh Báo", "Giá Trị Tồn Kho (VNĐ)", "Giá Vốn Bình Quân (VNĐ)"])
            variants = self.db.query(ProductionVariant).options(
                joinedload(ProductionVariant.product),
                joinedload(ProductionVariant.size),
                joinedload(ProductionVariant.color),
                joinedload(ProductionVariant.inventory)
            ).all()
            for v in variants:
                inv = v.inventory
                avail = inv.available_quantity if inv else 0
                val = float(inv.inventory_value) if inv else 0.0
                avg_c = round(val / avail, 2) if avail > 0 else 0.0
                writer.writerow([
                    v.sku,
                    v.product.name if v.product else "",
                    v.size.name if v.size else "",
                    v.color.name if v.color else "",
                    avail,
                    inv.low_stock_threshold if inv else 5,
                    int(val),
                    int(avg_c)
                ])
        elif report_type == "replenishment":
            analytics = self.get_advanced_analytics()
            writer.writerow(["Mã SKU", "Tên Sản Phẩm", "Size", "Màu", "Tồn Hiện Tại", "Đã Bán", "Mức Độ Ưu Tiên", "Đề Xuất Nhập Thêm", "Chi Phí Dự Kiến (VNĐ)"])
            for r in analytics["replenishment_recommendations"]:
                writer.writerow([
                    r["sku"],
                    r["product_name"],
                    r["size_name"],
                    r["color_name"],
                    r["available_quantity"],
                    r["historical_sold"],
                    r["urgency"],
                    r["recommended_order_qty"],
                    int(r["estimated_restock_cost"])
                ])
        else:
            writer.writerow(["Mã Đơn Hàng", "Khách Hàng", "Số Điện Thoại", "Trạng Thái", "Phương Thức TT", "Tạm Tính (VNĐ)", "Giảm Giá (VNĐ)", "Phí Ship (VNĐ)", "Tổng Thanh Toán (VNĐ)", "Ngày Đặt"])
            orders = self.db.query(ProductionOrder).order_by(ProductionOrder.placed_at.desc()).all()
            for o in orders:
                rec = o.recipient_snapshot or {}
                writer.writerow([
                    o.code,
                    rec.get("name", ""),
                    rec.get("phone", ""),
                    o.status,
                    o.payment_method,
                    int(float(o.subtotal)),
                    int(float(o.discount_amount)),
                    int(float(o.shipping_fee)),
                    int(float(o.total_amount)),
                    o.placed_at.strftime("%Y-%m-%d %H:%M") if o.placed_at else ""
                ])

        return output.getvalue()

