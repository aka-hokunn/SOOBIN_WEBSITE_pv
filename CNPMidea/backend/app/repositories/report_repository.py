from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.models.entities import (
    ProductionOrder, ProductionInvoice, ProductionInvoiceItem,
    ProductionInventory, ProductionVariant, ProductionProduct,
    ProductionSupplier, ProductionGoodsReceipt
)

class ReportRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_dashboard_summary(self) -> Dict[str, Any]:
        # 1. Total revenue from delivered invoices
        rev_row = self.db.query(
            func.coalesce(func.sum(ProductionInvoice.subtotal - ProductionInvoice.discount_amount), 0.0)
        ).first()
        total_delivered_revenue = float(rev_row[0]) if rev_row else 0.0

        # 2. Profit calculation: revenue after discount - snapshot cost of goods sold
        profit_row = self.db.query(
            func.coalesce(
                func.sum(
                    ProductionInvoiceItem.line_total - (ProductionInvoiceItem.unit_cost_snapshot * ProductionInvoiceItem.quantity)
                ), 0.0
            )
        ).first()
        total_delivered_profit = float(profit_row[0]) if profit_row else 0.0

        # 3. Orders grouped by status
        status_counts = dict(
            self.db.query(ProductionOrder.status, func.count(ProductionOrder.id))
            .group_by(ProductionOrder.status).all()
        )

        # 4. Low stock variants
        low_stock_rows = self.db.query(ProductionInventory).join(ProductionVariant).join(ProductionProduct).filter(
            ProductionInventory.available_quantity <= ProductionInventory.low_stock_threshold
        ).all()
        low_stock_items = [
            {
                "variant_id": inv.variant_id,
                "sku": inv.variant.sku,
                "product_name": inv.variant.product.name,
                "available_quantity": inv.available_quantity,
                "low_stock_threshold": inv.low_stock_threshold
            }
            for inv in low_stock_rows
        ]

        # 5. Top selling items (delivered)
        top_items_rows = self.db.query(
            ProductionInvoiceItem.product_snapshot,
            func.sum(ProductionInvoiceItem.quantity).label("total_sold"),
            func.sum(ProductionInvoiceItem.line_total).label("total_sales")
        ).group_by(ProductionInvoiceItem.product_snapshot).order_by(desc("total_sold")).limit(5).all()

        top_selling = [
            {
                "name": item[0].get("name", "Sản phẩm"),
                "sku": item[0].get("sku", ""),
                "quantity_sold": int(item[1]),
                "revenue": float(item[2])
            }
            for item in top_items_rows
        ]

        total_suppliers = self.db.query(ProductionSupplier).count()
        total_products = self.db.query(ProductionProduct).filter(ProductionProduct.deleted_at == None).count()

        return {
            "total_delivered_revenue": total_delivered_revenue,
            "total_delivered_profit": total_delivered_profit,
            "orders_by_status": status_counts,
            "low_stock_items": low_stock_items,
            "top_selling_products": top_selling,
            "total_suppliers": total_suppliers,
            "total_products": total_products
        }
