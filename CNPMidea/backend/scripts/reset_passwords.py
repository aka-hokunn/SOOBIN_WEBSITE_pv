import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.entities import UserAccount
from app.core.security import hash_password

db = SessionLocal()
pwd_hash = hash_password("Password123@")
print("New valid hash:", pwd_hash)

users = db.query(UserAccount).all()
for u in users:
    u.password_hash = pwd_hash

db.commit()
print(f"Updated {len(users)} users successfully with valid password hash!")
db.close()
