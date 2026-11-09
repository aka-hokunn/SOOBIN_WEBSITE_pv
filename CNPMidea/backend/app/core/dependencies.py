from typing import Optional, List
from fastapi import Depends, HTTPException, status, Header, Cookie
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.auth_service import AuthService
from app.models.entities import UserAccount

def get_session_token(
    authorization: Optional[str] = Header(None),
    session_token: Optional[str] = Cookie(None)
) -> Optional[str]:
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        return authorization
    if session_token:
        return session_token
    return None

def get_current_user(
    token: Optional[str] = Depends(get_session_token),
    db: Session = Depends(get_db)
) -> UserAccount:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yêu cầu đăng nhập để thực hiện thao tác này."
        )

    auth_service = AuthService(db)
    user = auth_service.validate_session(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên làm việc đã hết hạn hoặc tài khoản đã bị khóa."
        )
    return user

def get_optional_current_user(
    token: Optional[str] = Depends(get_session_token),
    db: Session = Depends(get_db)
) -> Optional[UserAccount]:
    if not token:
        return None
    auth_service = AuthService(db)
    return auth_service.validate_session(token)

def require_role(allowed_roles: List[str]):
    def role_checker(user: UserAccount = Depends(get_current_user)) -> UserAccount:
        if not user.role or user.role.code not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Quyền truy cập bị từ chối. Thao tác này chỉ dành cho vai trò: {', '.join(allowed_roles)}"
            )
        return user
    return role_checker

def require_permission(permission_code: str):
    def permission_checker(user: UserAccount = Depends(get_current_user)) -> UserAccount:
        if not user.role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền truy cập.")
        
        # Admin has all permissions
        if user.role.code == "ADMIN":
            return user

        user_perms = [p.code for p in user.role.permissions]
        if permission_code not in user_perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Quyền truy cập bị từ chối. Bạn thiếu quyền '{permission_code}'."
            )
        return user
    return permission_checker
