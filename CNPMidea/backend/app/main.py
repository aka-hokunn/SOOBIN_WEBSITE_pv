import os
from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text
from app.core.database import engine
from app.core.realtime import realtime_hub

from app.core.config import settings
from app.controllers import (
    auth_controller, catalog_controller, cart_controller,
    order_controller, inventory_controller, promotion_controller,
    shipping_mock_controller, payment_mock_controller, report_controller,
    user_management_controller, view_controller, site_settings_controller,
    lucky_wheel_controller
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Soobin Swimwear E-Commerce Platform built with FastAPI, MVC Architecture, and PostgreSQL (cnpm)"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Assets
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Include API Routers under /api/v1
api_prefix = settings.API_V1_STR
app.include_router(auth_controller.router, prefix=api_prefix)
app.include_router(catalog_controller.router, prefix=api_prefix)
app.include_router(cart_controller.router, prefix=api_prefix)
app.include_router(order_controller.router, prefix=api_prefix)
app.include_router(inventory_controller.router, prefix=api_prefix)
app.include_router(promotion_controller.router, prefix=api_prefix)
app.include_router(shipping_mock_controller.router, prefix=api_prefix)
app.include_router(payment_mock_controller.router, prefix=api_prefix)
app.include_router(report_controller.router, prefix=api_prefix)
app.include_router(user_management_controller.router, prefix=api_prefix)
app.include_router(site_settings_controller.router, prefix=api_prefix)
app.include_router(lucky_wheel_controller.router, prefix=api_prefix)

# Include Web View Routers (MVC Views)
app.include_router(view_controller.router)

@app.middleware("http")
async def broadcast_live_data_changes(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.endswith(".js") or path.endswith(".css") or not path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    watched = ("/catalog", "/orders", "/inventory", "/promotions", "/mock/", "/site-settings", "/admin/", "/lucky-wheel/manage")
    if (path.startswith(api_prefix) and any(part in path for part in watched)
            and request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and response.status_code < 400):
        await realtime_hub.broadcast({
            "type": "data_changed",
            "path": path,
            "method": request.method,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    return response

@app.websocket("/ws/updates")
async def websocket_updates(socket: WebSocket):
    await realtime_hub.connect(socket)
    try:
        while True:
            await socket.receive_text()
    except WebSocketDisconnect:
        await realtime_hub.disconnect(socket)

@app.on_event("startup")
def ensure_promotion_customer_scope_column():
    # Backward-compatible migration for databases created before voucher targeting.
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as connection:
        if inspect(connection).has_table("production_promotion"):
            connection.execute(text(
                "ALTER TABLE production_promotion ADD COLUMN IF NOT EXISTS eligible_customer_ids JSONB"
            ))

@app.on_event("startup")
def ensure_lucky_wheel_tables():
    # Vòng quay may mắn: tạo bảng nếu chưa có + cấu hình mặc định lần đầu
    from app.core.database import SessionLocal
    from app.models.entities import ProductionLuckyWheelSlot, ProductionLuckyWheelSpin
    from app.services.lucky_wheel_service import LuckyWheelService

    ProductionLuckyWheelSlot.__table__.create(bind=engine, checkfirst=True)
    ProductionLuckyWheelSpin.__table__.create(bind=engine, checkfirst=True)
    db = SessionLocal()
    try:
        LuckyWheelService(db).seed_defaults_if_empty()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

# -----------------------------------------------------------------------------
# Phân Tích & Tăng Trưởng (Insights) + Nhật ký thao tác nhân sự
# -----------------------------------------------------------------------------
from app.controllers import insights_controller  # noqa: E402
from app.core.audit_log import record_if_needed as _record_audit_log  # noqa: E402

app.include_router(insights_controller.router, prefix=api_prefix)

@app.middleware("http")
async def record_staff_audit_log(request, call_next):
    response = await call_next(request)
    # Ghi nhật ký thao tác của nhân sự; lỗi ghi log không bao giờ làm hỏng request
    await _record_audit_log(request, response, api_prefix)
    return response

@app.on_event("startup")
def ensure_audit_log_table():
    from app.models.entities import ProductionAuditLog
    try:
        ProductionAuditLog.__table__.create(bind=engine, checkfirst=True)
    except Exception:
        pass

# -----------------------------------------------------------------------------
# Trải nghiệm khách hàng (hồ sơ size, stylist chuyến đi, tìm bằng ảnh, điểm danh Vỏ Sò)
# -----------------------------------------------------------------------------
from app.controllers import experience_controller  # noqa: E402

app.include_router(experience_controller.router, prefix=api_prefix)

@app.on_event("startup")
def ensure_experience_tables():
    from app.models.entities import ProductionDailyCheckin, ProductionFitProfile
    try:
        ProductionFitProfile.__table__.create(bind=engine, checkfirst=True)
        ProductionDailyCheckin.__table__.create(bind=engine, checkfirst=True)
    except Exception:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
