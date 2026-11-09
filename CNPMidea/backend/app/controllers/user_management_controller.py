from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_role
from app.services.auth_service import AuthService
from app.repositories.user_repository import UserRepository
from app.schemas.all_schemas import (
    UserCreateAdminRequest, UserUpdateAdminRequest, RoleCreate, RoleUpdate
)
from app.models.entities import (
    UserAccount, ProductionOrderHistory, ProductionInventoryMovement, ProductionOutboxEvent
)

router = APIRouter(prefix="/admin", tags=["Admin User Management"])

@router.get("/users")
def list_users(
    user: UserAccount = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db)
):
    users = db.query(UserAccount).order_by(UserAccount.id).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "phone": u.phone,
            "role_id": u.role_id,
            "role": u.role.name if u.role else "",
            "role_code": u.role.code if u.role else "",
            "is_email_verified": bool(u.email_verified_at),
            "is_locked": u.is_locked,
            "created_at": u.created_at.isoformat()
        }
        for u in users
    ]

@router.post("/users/{account_id}/lock")
def lock_user(
    account_id: int,
    user: UserAccount = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db)
):
    svc = AuthService(db)
    try:
        svc.lock_user(account_id, current_admin_id=user.id)
        return {"message": "Đã khóa tài khoản thành công."}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/users/{account_id}/unlock")
def unlock_user(
    account_id: int,
    user: UserAccount = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db)
):
    svc = AuthService(db)
    try:
        svc.unlock_user(account_id)
        return {"message": "Đã mở khóa tài khoản thành công."}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/roles")
def list_roles(
    user: UserAccount = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db)
):
    repo = UserRepository(db)
    roles = repo.list_roles()
    return [
        {
            "id": r.id,
            "code": r.code,
            "name": r.name,
            "is_system": r.is_system,
            "is_active": r.is_active,
            "permissions": [p.code for p in r.permissions]
        }
        for r in roles
    ]

@router.get("/permissions")
def list_permissions(
    user: UserAccount = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db)
):
    repo = UserRepository(db)
    perms = repo.list_permissions()
    return [{"id": p.id, "code": p.code, "description": p.description} for p in perms]

@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user_by_admin(
    req: UserCreateAdminRequest,
    user: UserAccount = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db)
):
    svc = AuthService(db)
    try:
        new_user = svc.create_user_by_admin(
            email=req.email,
            full_name=req.full_name,
            password=req.password,
            role_id=req.role_id,
            phone=req.phone
        )
        return {
            "message": "Tạo tài khoản thành công.",
            "user": {
                "id": new_user.id,
                "email": new_user.email,
                "full_name": new_user.full_name,
                "role": new_user.role.name if new_user.role else "",
                "role_code": new_user.role.code if new_user.role else ""
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.put("/users/{account_id}")
def update_user_by_admin(
    account_id: int,
    req: UserUpdateAdminRequest,
    user: UserAccount = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db)
):
    svc = AuthService(db)
    try:
        updated = svc.update_user_by_admin(
            account_id=account_id,
            current_admin_id=user.id,
            full_name=req.full_name,
            phone=req.phone,
            role_id=req.role_id,
            is_locked=req.is_locked
        )
        return {
            "message": "Cập nhật thông tin tài khoản thành công.",
            "user": {
                "id": updated.id,
                "email": updated.email,
                "full_name": updated.full_name,
                "role": updated.role.name if updated.role else "",
                "is_locked": updated.is_locked
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/roles", status_code=status.HTTP_201_CREATED)
def create_role(
    req: RoleCreate,
    user: UserAccount = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db)
):
    svc = AuthService(db)
    try:
        role = svc.create_role(code=req.code, name=req.name, permission_ids=req.permission_ids)
        return {
            "message": "Tạo vai trò thành công.",
            "role": {
                "id": role.id,
                "code": role.code,
                "name": role.name,
                "permissions": [p.code for p in role.permissions]
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.put("/roles/{role_id}")
def update_role(
    role_id: int,
    req: RoleUpdate,
    user: UserAccount = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db)
):
    svc = AuthService(db)
    try:
        role = svc.update_role(
            role_id=role_id,
            name=req.name,
            is_active=req.is_active,
            permission_ids=req.permission_ids
        )
        return {
            "message": "Cập nhật vai trò thành công.",
            "role": {
                "id": role.id,
                "code": role.code,
                "name": role.name,
                "is_active": role.is_active,
                "permissions": [p.code for p in role.permissions]
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/audit-logs")
def get_enterprise_audit_logs(
    limit: int = 50,
    user: UserAccount = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db)
):
    order_logs = db.query(ProductionOrderHistory).order_by(ProductionOrderHistory.occurred_at.desc()).limit(limit).all()
    inv_logs = db.query(ProductionInventoryMovement).order_by(ProductionInventoryMovement.occurred_at.desc()).limit(limit).all()
    outbox_logs = db.query(ProductionOutboxEvent).order_by(ProductionOutboxEvent.created_at.desc()).limit(limit).all()

    events = []
    for ol in order_logs:
        events.append({
            "category": "ORDER_FLOW",
            "title": f"Đơn #{ol.order_id}: {ol.from_status or 'Mới'} → {ol.to_status}",
            "detail": ol.reason or ol.event_type,
            "timestamp": ol.occurred_at.isoformat()
        })
    for il in inv_logs:
        events.append({
            "category": "INVENTORY",
            "title": f"Biến động kho ({il.movement_type}): {il.quantity_delta:+d} chiếc",
            "detail": f"Biến thể #{il.variant_id} • Key: {il.event_key}",
            "timestamp": il.occurred_at.isoformat()
        })
    for ob in outbox_logs:
        events.append({
            "category": "OUTBOX_AUTOMATION",
            "title": f"Sự kiện {ob.event_type} ({ob.status})",
            "detail": f"Key: {ob.event_key}",
            "timestamp": ob.created_at.isoformat()
        })

    events.sort(key=lambda x: x["timestamp"], reverse=True)
    return events[:limit]


@router.get("/system-overview")
def get_admin_system_overview(
    user: UserAccount = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db)
):
    from app.models.entities import (
        UserSession, ProductionProduct, ProductionOrder, ProductionInventory
    )
    users = db.query(UserAccount).all()
    role_counts = {}
    locked_count = 0
    unverified_count = 0
    for u in users:
        rc = u.role.code if u.role else "UNKNOWN"
        role_counts[rc] = role_counts.get(rc, 0) + 1
        if u.is_locked:
            locked_count += 1
        if not u.email_verified_at:
            unverified_count += 1

    active_sessions = db.query(UserSession).filter(UserSession.revoked_at.is_(None)).count()
    total_products = db.query(ProductionProduct).count()
    total_orders = db.query(ProductionOrder).count()
    invs = db.query(ProductionInventory).all()
    total_stock_units = sum(int(i.available_quantity or 0) for i in invs)

    audit_count = (
        db.query(ProductionOrderHistory).count()
        + db.query(ProductionInventoryMovement).count()
        + db.query(ProductionOutboxEvent).count()
    )

    return {
        "database_status": "ONLINE",
        "total_accounts": len(users),
        "total_users": len(users),
        "locked_accounts": locked_count,
        "locked_users": locked_count,
        "unverified_users": unverified_count,
        "active_sessions": active_sessions,
        "accounts_by_role": role_counts,
        "role_breakdown": role_counts,
        "audit_events_count": audit_count,
        "total_products": total_products,
        "total_orders": total_orders,
        "total_stock_units": total_stock_units,
    }


@router.post("/users/{account_id}/revoke-sessions")
def revoke_user_sessions(
    account_id: int,
    user: UserAccount = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db)
):
    from datetime import datetime, timezone
    from app.models.entities import UserSession
    target = db.query(UserAccount).filter(UserAccount.id == account_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
    sessions = db.query(UserSession).filter(
        UserSession.account_id == account_id,
        UserSession.revoked_at.is_(None)
    ).all()
    now = datetime.now(timezone.utc)
    for s in sessions:
        s.revoked_at = now
    db.commit()
    return {
        "message": f"Đã thu hồi {len(sessions)} phiên đăng nhập đang hoạt động của {target.email}.",
        "revoked_count": len(sessions)
    }
