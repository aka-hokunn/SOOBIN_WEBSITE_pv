from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_role
from app.services.report_service import ReportService
from app.models.entities import UserAccount

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.get("/dashboard")
def get_dashboard_metrics(
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db)
):
    svc = ReportService(db)
    return svc.get_dashboard_data()

@router.get("/analytics")
def get_advanced_analytics(
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "WAREHOUSE"])),
    db: Session = Depends(get_db)
):
    svc = ReportService(db)
    return svc.get_advanced_analytics()

@router.get("/export-csv")
def export_report_csv(
    report_type: str = Query("orders", description="orders | inventory | replenishment"),
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER", "WAREHOUSE"])),
    db: Session = Depends(get_db)
):
    svc = ReportService(db)
    csv_data = svc.export_csv_report(report_type=report_type)
    filename = f"soobin_{report_type}_report.csv"
    return Response(
        content=csv_data.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/executive-kpi")
def get_executive_kpi(
    user: UserAccount = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db)
):
    from app.models.entities import ProductionOrder, ProductionInventory, ProductionPromotion
    orders = db.query(ProductionOrder).all()
    valid_orders = [o for o in orders if o.status != "Đã hủy"]
    delivered_orders = [o for o in orders if o.status == "Đã giao"]
    pending_orders = [o for o in orders if o.status == "Chưa xử lý"]

    total_rev = sum(float(o.total_amount or 0) for o in valid_orders)
    aov = round(total_rev / len(valid_orders)) if valid_orders else 0
    fulfillment_rate = round((len(delivered_orders) / len(orders)) * 100, 1) if orders else 100.0

    invs = db.query(ProductionInventory).all()
    total_inv_value = sum(float(getattr(i, "inventory_value", 0) or (int(i.available_quantity or 0) * 180000)) for i in invs)
    low_stock_count = sum(1 for i in invs if int(i.available_quantity or 0) <= int(i.low_stock_threshold or 5))
    paid_orders_count = sum(1 for o in valid_orders if getattr(o, "payment_status", "") == "PAID")
    active_promos = db.query(ProductionPromotion).filter(ProductionPromotion.is_active == True).count()

    return {
        "total_orders": len(orders),
        "valid_orders_count": len(valid_orders),
        "delivered_orders_count": len(delivered_orders),
        "pending_orders_count": len(pending_orders),
        "paid_orders": paid_orders_count,
        "total_revenue": round(total_rev),
        "average_order_value": aov,
        "fulfillment_rate_percent": fulfillment_rate,
        "total_inventory_cost_value": round(total_inv_value),
        "low_stock_variants_count": low_stock_count,
        "active_promotions_count": active_promos,
    }

