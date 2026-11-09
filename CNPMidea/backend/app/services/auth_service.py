from typing import Optional, Tuple
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.repositories.user_repository import UserRepository
from app.core.security import hash_password, verify_password, generate_token, hash_token
from app.core.config import settings
from app.models.entities import UserAccount

class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)

    def register(self, email: str, full_name: str, password: str, phone: Optional[str] = None) -> Tuple[UserAccount, str]:
        # Check if email exists
        if self.user_repo.get_by_email(email):
            raise ValueError("Email này đã được đăng ký tài khoản.")
        if phone and self.user_repo.get_by_phone(phone):
            raise ValueError("Số điện thoại này đã được sử dụng.")

        customer_role = self.user_repo.get_role_by_code("CUSTOMER")
        if not customer_role:
            raise ValueError("Không tìm thấy vai trò Khách hàng trong hệ thống.")

        pwd_hash = hash_password(password)
        user = self.user_repo.create_user(
            email=email,
            full_name=full_name,
            password_hash=pwd_hash,
            role_id=customer_role.id,
            phone=phone
        )

        # Generate email verification token
        raw_verify_token = generate_token()
        token_hash = hash_token(raw_verify_token)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.ACTION_TOKEN_EXPIRE_HOURS)
        self.user_repo.create_action_token(
            account_id=user.id,
            purpose="VERIFY_EMAIL",
            token_hash=token_hash,
            expires_at=expires_at
        )

        self.db.commit()
        return user, raw_verify_token

    def verify_email(self, raw_token: str) -> UserAccount:
        token_hash = hash_token(raw_token)
        action_token = self.user_repo.get_valid_action_token(token_hash, "VERIFY_EMAIL")
        if not action_token:
            raise ValueError("Mã xác minh email không hợp lệ hoặc đã hết hạn.")

        user = self.user_repo.get_by_id(action_token.account_id)
        if not user:
            raise ValueError("Không tìm thấy tài khoản người dùng.")

        user.email_verified_at = datetime.now(timezone.utc)
        action_token.consumed_at = datetime.now(timezone.utc)
        self.db.commit()
        return user

    def login(self, email_or_phone: str, password: str) -> Tuple[UserAccount, str]:
        user = self.user_repo.get_by_email(email_or_phone)
        if not user:
            user = self.user_repo.get_by_phone(email_or_phone)

        if not user:
            raise ValueError("Tài khoản hoặc mật khẩu không chính xác.")

        if user.is_locked:
            raise ValueError("Tài khoản của bạn đã bị khóa. Vui lòng liên hệ quản trị viên.")

        if not verify_password(password, user.password_hash):
            raise ValueError("Tài khoản hoặc mật khẩu không chính xác.")

        # Create session
        raw_session_token = generate_token(36)
        session_hash = hash_token(raw_session_token)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.SESSION_EXPIRE_HOURS)
        self.user_repo.create_session(user.id, session_hash, expires_at)
        self.db.commit()

        return user, raw_session_token

    def validate_session(self, raw_session_token: str) -> Optional[UserAccount]:
        session_hash = hash_token(raw_session_token)
        session = self.user_repo.get_active_session(session_hash)
        if not session:
            return None

        user = self.user_repo.get_by_id(session.account_id)
        if not user or user.is_locked:
            return None

        return user

    def logout(self, raw_session_token: str):
        session_hash = hash_token(raw_session_token)
        self.user_repo.revoke_session(session_hash)
        self.db.commit()

    def lock_user(self, account_id: int, current_admin_id: int):
        user = self.user_repo.get_by_id(account_id)
        if not user:
            raise ValueError("Người dùng không tồn tại.")

        # Protection: Cannot lock the last active Admin
        if user.role.code == "ADMIN":
            active_admins = self.user_repo.count_active_admins()
            if active_admins <= 1:
                raise ValueError("Không thể khóa tài khoản Quản trị viên (Admin) hoạt động cuối cùng của hệ thống.")

        user.is_locked = True
        self.db.commit()

    def unlock_user(self, account_id: int):
        user = self.user_repo.get_by_id(account_id)
        if not user:
            raise ValueError("Người dùng không tồn tại.")
        user.is_locked = False
        self.db.commit()

    def create_user_by_admin(self, email: str, full_name: str, password: str, role_id: int, phone: Optional[str] = None) -> UserAccount:
        if self.user_repo.get_by_email(email):
            raise ValueError("Email này đã được sử dụng.")
        if phone and self.user_repo.get_by_phone(phone):
            raise ValueError("Số điện thoại này đã được sử dụng.")
        role = self.user_repo.get_role_by_id(role_id)
        if not role:
            raise ValueError("Vai trò không tồn tại.")
        pwd_hash = hash_password(password)
        user = self.user_repo.create_user(
            email=email,
            full_name=full_name,
            password_hash=pwd_hash,
            role_id=role_id,
            phone=phone
        )
        # Accounts created by Admin are automatically verified
        user.email_verified_at = datetime.now(timezone.utc)
        self.db.commit()
        return user

    def update_user_by_admin(self, account_id: int, current_admin_id: int, full_name: Optional[str] = None, phone: Optional[str] = None, role_id: Optional[int] = None, is_locked: Optional[bool] = None) -> UserAccount:
        user = self.user_repo.get_by_id(account_id)
        if not user:
            raise ValueError("Người dùng không tồn tại.")
        if full_name:
            user.full_name = full_name.strip()
        if phone is not None:
            if phone.strip() and phone.strip() != user.phone:
                existing = self.user_repo.get_by_phone(phone.strip())
                if existing and existing.id != user.id:
                    raise ValueError("Số điện thoại đã thuộc tài khoản khác.")
            user.phone = phone.strip() if phone.strip() else None
        if role_id is not None and role_id != user.role_id:
            target_role = self.user_repo.get_role_by_id(role_id)
            if not target_role:
                raise ValueError("Vai trò không tồn tại.")
            # Check last active admin protection
            if user.role.code == "ADMIN" and target_role.code != "ADMIN":
                if self.user_repo.count_active_admins() <= 1:
                    raise ValueError("Không thể chuyển vai trò của Quản trị viên (Admin) duy nhất còn hoạt động.")
            user.role_id = role_id
        if is_locked is not None:
            if is_locked and user.role.code == "ADMIN":
                if self.user_repo.count_active_admins() <= 1:
                    raise ValueError("Không thể khóa Quản trị viên duy nhất còn hoạt động.")
            user.is_locked = is_locked
        self.db.commit()
        return user

    def create_role(self, code: str, name: str, permission_ids: list = []) -> any:
        code_clean = code.strip().upper()
        if self.user_repo.get_role_by_code(code_clean):
            raise ValueError(f"Mã vai trò '{code_clean}' đã tồn tại.")
        role = self.user_repo.create_role(code_clean, name, permission_ids)
        self.db.commit()
        return role

    def update_role(self, role_id: int, name: Optional[str] = None, is_active: Optional[bool] = None, permission_ids: Optional[list] = None) -> any:
        role = self.user_repo.update_role(role_id, name, is_active, permission_ids)
        if not role:
            raise ValueError("Vai trò không tồn tại.")
        self.db.commit()
        return role

    def list_user_addresses(self, account_id: int):
        return self.user_repo.list_addresses(account_id)

    def add_user_address(self, account_id: int, recipient_name: str, recipient_phone: str, address_line: str, province_code: Optional[str] = None, district_code: Optional[str] = None, ward_code: Optional[str] = None, is_default: bool = False):
        addr = self.user_repo.add_address(account_id, recipient_name, recipient_phone, address_line, province_code, district_code, ward_code, is_default)
        self.db.commit()
        return addr

    def update_user_address(self, account_id: int, address_id: int, recipient_name: Optional[str] = None, recipient_phone: Optional[str] = None, address_line: Optional[str] = None, is_default: Optional[bool] = None):
        addr = self.user_repo.update_address(address_id, account_id, recipient_name, recipient_phone, address_line, is_default)
        if not addr:
            raise ValueError("Địa chỉ không tồn tại hoặc không thuộc quyền sở hữu.")
        self.db.commit()
        return addr

    def delete_user_address(self, account_id: int, address_id: int):
        success = self.user_repo.delete_address(address_id, account_id)
        if not success:
            raise ValueError("Địa chỉ không tồn tại hoặc không thuộc quyền sở hữu.")
        self.db.commit()
        return True

