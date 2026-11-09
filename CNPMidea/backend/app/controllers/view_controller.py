import os
from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse

router = APIRouter(tags=["Views"])

VIEWS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "views")

# 1. Customer Storefront & Login
@router.get("/")
def view_index():
    return FileResponse(os.path.join(VIEWS_DIR, "index.html"))

@router.get("/catalog")
def view_catalog():
    return FileResponse(os.path.join(VIEWS_DIR, "index.html"))

@router.get("/login")
def view_customer_login():
    return FileResponse(os.path.join(VIEWS_DIR, "customer_login.html"))

@router.get("/staff/login")
def view_staff_login():
    return FileResponse(os.path.join(VIEWS_DIR, "staff_login.html"))

# 2. Admin Portal & Login
@router.get("/admin/login")
def view_admin_login():
    return RedirectResponse("/staff/login?role=ADMIN", status_code=303)

@router.get("/admin")
def view_admin():
    return FileResponse(os.path.join(VIEWS_DIR, "admin.html"))

# 3. Manager Portal & Login
@router.get("/manager/login")
def view_manager_login():
    return RedirectResponse("/staff/login?role=MANAGER", status_code=303)

@router.get("/manager")
def view_manager():
    return FileResponse(os.path.join(VIEWS_DIR, "manager.html"))

# 4. Warehouse Portal & Login
@router.get("/warehouse/login")
def view_warehouse_login():
    return RedirectResponse("/staff/login?role=WAREHOUSE", status_code=303)

@router.get("/warehouse")
def view_warehouse():
    return FileResponse(os.path.join(VIEWS_DIR, "warehouse.html"))

# 5. Sales Staff Portal & Login
@router.get("/sales/login")
def view_sales_login():
    return RedirectResponse("/staff/login?role=SALES", status_code=303)

@router.get("/sales")
def view_sales():
    return FileResponse(os.path.join(VIEWS_DIR, "sales.html"))

# 6. Mocks (GHTK & VietQR)
@router.get("/mock-shipping")
def view_mock_shipping():
    return FileResponse(os.path.join(VIEWS_DIR, "shipping_mock.html"))

@router.get("/mock-payment")
def view_mock_payment():
    return FileResponse(os.path.join(VIEWS_DIR, "payment_mock.html"))
