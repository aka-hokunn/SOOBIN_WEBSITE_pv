import pytest
import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal, get_db
from app.models.entities import ProductionInventory

@pytest.fixture(autouse=True)
def ensure_test_inventory_balances():
    db = SessionLocal()
    try:
        for vid in (1, 2, 3, 4, 5):
            inv = db.query(ProductionInventory).filter_by(variant_id=vid).first()
            if inv and inv.available_quantity < 50:
                inv.available_quantity = 100
        inv6 = db.query(ProductionInventory).filter_by(variant_id=6).first()
        if inv6 and inv6.available_quantity != 10:
            inv6.available_quantity = 10
        db.commit()
    finally:
        db.close()

@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="function")
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
