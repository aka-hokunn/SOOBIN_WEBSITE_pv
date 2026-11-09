from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.auth_service import AuthService
from app.schemas.all_schemas import (
    UserRegisterRequest, UserLoginRequest, PortalLoginRequest, VerifyEmailRequest,
    UserResponse, SessionResponse, UserAddressCreate
)
from app.models.entities import UserAccount

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register")
def register(req: UserRegisterRequest, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    try:
        user, verify_token = auth_service.register(
            email=req.email,
            full_name=req.full_name,
            password=req.password,
            phone=req.phone
        )
        return {
            "message": "Đăng ký tài khoản thành công. Vui lòng xác minh email để hoàn tất.",
            "user_id": user.id,
            "email": user.email,
            "verification_token": verify_token # Provided for easy testing & demo in Mailpit/localhost
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/verify-email")
def verify_email(req: VerifyEmailRequest, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    try:
        user = auth_service.verify_email(req.token)
        return {"message": "Xác minh email thành công. Bạn đã có thể đặt hàng.", "email": user.email}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/login")
def login(req: UserLoginRequest, response: Response, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    try:
        user, raw_token = auth_service.login(req.email_or_phone, req.password)
        role_code = user.role.code.upper() if user.role else "CUSTOMER"
        redirect_urls = {
            "ADMIN": "/admin",
            "MANAGER": "/manager",
            "WAREHOUSE": "/warehouse",
            "SALES": "/sales",
            "CUSTOMER": "/"
        }
        # Set HttpOnly session cookie
        response.set_cookie(
            key="session_token",
            value=raw_token,
            httponly=True,
            samesite="lax",
            max_age=72 * 3600
        )
        return {
            "session_token": raw_token,
            "redirect_url": redirect_urls.get(role_code, "/"),
            "user": {
                "id": user.id,
                "role_id": user.role_id,
                "role_code": role_code,
                "role": {
                    "id": user.role_id,
                    "code": role_code,
                    "name": user.role.name if user.role else role_code
                },
                "email": user.email,
                "phone": user.phone,
                "full_name": user.full_name,
                "is_email_verified": bool(user.email_verified_at),
                "is_locked": user.is_locked,
                "created_at": user.created_at
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

@router.post("/portal-login")
def portal_login(req: PortalLoginRequest, response: Response, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    try:
        user, raw_token = auth_service.login(req.email_or_phone, req.password)
        role_code = user.role.code.upper() if user.role else "CUSTOMER"
        target_portal = (req.portal or "CUSTOMER").upper()

        if target_portal == "CUSTOMER" and role_code != "CUSTOMER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Thông tin đăng nhập không hợp lệ đối với tài khoản Khách hàng mua sắm."
            )
        if target_portal != "CUSTOMER" and role_code == "CUSTOMER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản Khách hàng không có quyền truy cập Cổng Nội Bộ. Vui lòng đăng nhập tại /login."
            )

        # Set HttpOnly session cookie
        response.set_cookie(
            key="session_token",
            value=raw_token,
            httponly=True,
            samesite="lax",
            max_age=72 * 3600
        )

        redirect_urls = {
            "ADMIN": "/admin",
            "MANAGER": "/manager",
            "WAREHOUSE": "/warehouse",
            "SALES": "/sales",
            "CUSTOMER": "/"
        }

        return {
            "session_token": raw_token,
            "redirect_url": redirect_urls.get(role_code, "/"),
            "user": {
                "id": user.id,
                "role_id": user.role_id,
                "role_code": role_code,
                "role": {
                    "id": user.role_id,
                    "code": role_code,
                    "name": user.role.name if user.role else role_code
                },
                "email": user.email,
                "phone": user.phone,
                "full_name": user.full_name,
                "is_email_verified": bool(user.email_verified_at),
                "is_locked": user.is_locked,
                "created_at": user.created_at
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

@router.post("/logout")
def logout(response: Response, user: UserAccount = Depends(get_current_user)):
    response.delete_cookie("session_token")
    return {"message": "Đăng xuất thành công."}

@router.get("/me")
def get_current_user_profile(user: UserAccount = Depends(get_current_user)):
    permissions = [p.code for p in user.role.permissions] if user.role else []
    return {
        "id": user.id,
        "email": user.email,
        "phone": user.phone,
        "full_name": user.full_name,
        "role_code": user.role.code if user.role else "CUSTOMER",
        "role_name": user.role.name if user.role else "Khách hàng",
        "role": {
            "id": user.role.id,
            "code": user.role.code,
            "name": user.role.name,
            "permissions": permissions
        },
        "is_email_verified": bool(user.email_verified_at),
        "is_locked": user.is_locked
    }

# -----------------------------------------------------------------------------
# USER ADDRESS BOOK
# -----------------------------------------------------------------------------

@router.get("/addresses")
def list_addresses(user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)):
    svc = AuthService(db)
    addrs = svc.list_user_addresses(user.id)
    return [
        {
            "id": a.id,
            "recipient_name": a.recipient_name,
            "recipient_phone": a.recipient_phone,
            "address_line": a.address_line,
            "province_code": a.province_code,
            "district_code": a.district_code,
            "ward_code": a.ward_code,
            "is_default": a.is_default
        }
        for a in addrs
    ]

@router.post("/addresses", status_code=status.HTTP_201_CREATED)
def add_address(req: UserAddressCreate, user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)):
    svc = AuthService(db)
    try:
        addr = svc.add_user_address(
            account_id=user.id,
            recipient_name=req.recipient_name,
            recipient_phone=req.recipient_phone,
            address_line=req.address_line,
            province_code=req.province_code,
            district_code=req.district_code,
            ward_code=req.ward_code,
            is_default=req.is_default
        )
        return {
            "message": "Đã thêm địa chỉ thành công.",
            "address": {
                "id": addr.id,
                "recipient_name": addr.recipient_name,
                "recipient_phone": addr.recipient_phone,
                "address_line": addr.address_line,
                "is_default": addr.is_default
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.put("/addresses/{address_id}")
def update_address(address_id: int, req: UserAddressCreate, user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)):
    svc = AuthService(db)
    try:
        addr = svc.update_user_address(
            account_id=user.id,
            address_id=address_id,
            recipient_name=req.recipient_name,
            recipient_phone=req.recipient_phone,
            address_line=req.address_line,
            is_default=req.is_default
        )
        return {"message": "Cập nhật địa chỉ thành công.", "address_id": addr.id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/addresses/{address_id}")
def delete_address(address_id: int, user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)):
    svc = AuthService(db)
    try:
        svc.delete_user_address(user.id, address_id)
        return {"message": "Đã xóa địa chỉ thành công."}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

