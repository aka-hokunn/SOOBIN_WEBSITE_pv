from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from app.models.entities import (
    UserAccount, UserRole, UserPermission, UserRolePermission,
    UserSession, UserActionToken, UserAddress
)

class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, account_id: int) -> Optional[UserAccount]:
        return self.db.query(UserAccount).filter(UserAccount.id == account_id).first()

    def get_by_email(self, email: str) -> Optional[UserAccount]:
        return self.db.query(UserAccount).filter(UserAccount.email == email.lower().strip()).first()

    def get_by_phone(self, phone: str) -> Optional[UserAccount]:
        if not phone:
            return None
        return self.db.query(UserAccount).filter(UserAccount.phone == phone.strip()).first()

    def create_user(self, email: str, full_name: str, password_hash: str, role_id: int, phone: Optional[str] = None) -> UserAccount:
        user = UserAccount(
            email=email.lower().strip(),
            full_name=full_name.strip(),
            password_hash=password_hash,
            role_id=role_id,
            phone=phone.strip() if phone else None,
            is_locked=False
        )
        self.db.add(user)
        self.db.flush()
        return user

    def count_active_admins(self) -> int:
        return self.db.query(UserAccount).join(UserRole).filter(
            UserRole.code == "ADMIN",
            UserAccount.is_locked == False
        ).count()

    def get_role_by_code(self, code: str) -> Optional[UserRole]:
        return self.db.query(UserRole).filter(UserRole.code == code).first()

    def get_role_by_id(self, role_id: int) -> Optional[UserRole]:
        return self.db.query(UserRole).filter(UserRole.id == role_id).first()

    def list_roles(self) -> List[UserRole]:
        return self.db.query(UserRole).order_by(UserRole.id).all()

    def list_permissions(self) -> List[UserPermission]:
        return self.db.query(UserPermission).order_by(UserPermission.id).all()

    def create_role(self, code: str, name: str, permission_ids: List[int] = []) -> UserRole:
        role = UserRole(
            code=code.strip().upper(),
            name=name.strip(),
            is_system=False,
            is_active=True
        )
        if permission_ids:
            perms = self.db.query(UserPermission).filter(UserPermission.id.in_(permission_ids)).all()
            role.permissions = perms
        self.db.add(role)
        self.db.flush()
        return role

    def update_role(self, role_id: int, name: Optional[str] = None, is_active: Optional[bool] = None, permission_ids: Optional[List[int]] = None) -> Optional[UserRole]:
        role = self.get_role_by_id(role_id)
        if not role:
            return None
        if name is not None:
            role.name = name.strip()
        if is_active is not None:
            if role.is_system and not is_active:
                raise ValueError("Không thể vô hiệu hóa vai trò mặc định của hệ thống.")
            role.is_active = is_active
        if permission_ids is not None:
            perms = self.db.query(UserPermission).filter(UserPermission.id.in_(permission_ids)).all()
            role.permissions = perms
        self.db.flush()
        return role

    def create_session(self, account_id: int, session_token_hash: str, expires_at: datetime) -> UserSession:
        session = UserSession(
            account_id=account_id,
            session_token_hash=session_token_hash,
            expires_at=expires_at
        )
        self.db.add(session)
        self.db.flush()
        return session

    def get_active_session(self, session_token_hash: str) -> Optional[UserSession]:
        now = datetime.now(timezone.utc)
        return self.db.query(UserSession).filter(
            UserSession.session_token_hash == session_token_hash,
            UserSession.expires_at > now,
            UserSession.revoked_at == None
        ).first()

    def revoke_session(self, session_token_hash: str):
        session = self.get_active_session(session_token_hash)
        if session:
            session.revoked_at = datetime.now(timezone.utc)
            self.db.flush()

    def create_action_token(self, account_id: int, purpose: str, token_hash: str, expires_at: datetime) -> UserActionToken:
        token = UserActionToken(
            account_id=account_id,
            purpose=purpose,
            token_hash=token_hash,
            expires_at=expires_at
        )
        self.db.add(token)
        self.db.flush()
        return token

    def get_valid_action_token(self, token_hash: str, purpose: str) -> Optional[UserActionToken]:
        now = datetime.now(timezone.utc)
        return self.db.query(UserActionToken).filter(
            UserActionToken.token_hash == token_hash,
            UserActionToken.purpose == purpose,
            UserActionToken.expires_at > now,
            UserActionToken.consumed_at == None
        ).first()

    def list_addresses(self, account_id: int) -> List[UserAddress]:
        return self.db.query(UserAddress).filter(UserAddress.account_id == account_id).order_by(UserAddress.is_default.desc(), UserAddress.id.desc()).all()

    def get_address(self, address_id: int, account_id: int) -> Optional[UserAddress]:
        return self.db.query(UserAddress).filter(UserAddress.id == address_id, UserAddress.account_id == account_id).first()

    def add_address(self, account_id: int, recipient_name: str, recipient_phone: str, address_line: str, province_code: Optional[str] = None, district_code: Optional[str] = None, ward_code: Optional[str] = None, is_default: bool = False) -> UserAddress:
        if is_default:
            self.db.query(UserAddress).filter(UserAddress.account_id == account_id).update({"is_default": False})
        addr = UserAddress(
            account_id=account_id,
            recipient_name=recipient_name.strip(),
            recipient_phone=recipient_phone.strip(),
            address_line=address_line.strip(),
            province_code=province_code,
            district_code=district_code,
            ward_code=ward_code,
            is_default=is_default
        )
        self.db.add(addr)
        self.db.flush()
        return addr

    def update_address(self, address_id: int, account_id: int, recipient_name: Optional[str] = None, recipient_phone: Optional[str] = None, address_line: Optional[str] = None, is_default: Optional[bool] = None) -> Optional[UserAddress]:
        addr = self.get_address(address_id, account_id)
        if not addr:
            return None
        if is_default:
            self.db.query(UserAddress).filter(UserAddress.account_id == account_id).update({"is_default": False})
            addr.is_default = True
        elif is_default is False:
            addr.is_default = False
        if recipient_name:
            addr.recipient_name = recipient_name.strip()
        if recipient_phone:
            addr.recipient_phone = recipient_phone.strip()
        if address_line:
            addr.address_line = address_line.strip()
        self.db.flush()
        return addr

    def delete_address(self, address_id: int, account_id: int) -> bool:
        addr = self.get_address(address_id, account_id)
        if not addr:
            return False
        self.db.delete(addr)
        self.db.flush()
        return True

    def get_default_address(self, account_id: int) -> Optional[UserAddress]:
        addr = self.db.query(UserAddress).filter(UserAddress.account_id == account_id, UserAddress.is_default == True).first()
        if not addr:
            addr = self.db.query(UserAddress).filter(UserAddress.account_id == account_id).first()
        return addr
