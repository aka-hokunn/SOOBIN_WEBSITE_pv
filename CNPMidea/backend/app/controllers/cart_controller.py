from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.dependencies import require_role
from app.services.cart_service import CartService
from app.schemas.all_schemas import CartItemAdd, CartItemUpdate, CartMergeRequest, CartBundleAddRequest
from app.models.entities import UserAccount

router = APIRouter(prefix="/cart", tags=["Cart"])

@router.get("")
def get_user_cart(user: UserAccount = Depends(require_role(["CUSTOMER"])), db: Session = Depends(get_db)):
    svc = CartService(db)
    return svc.get_cart(user.id)

@router.post("/items")
def add_cart_item(req: CartItemAdd, user: UserAccount = Depends(require_role(["CUSTOMER"])), db: Session = Depends(get_db)):
    svc = CartService(db)
    try:
        return svc.add_to_cart(user.id, req.variant_id, req.quantity)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/bundle")
def add_cart_bundle(req: CartBundleAddRequest, user: UserAccount = Depends(require_role(["CUSTOMER"])), db: Session = Depends(get_db)):
    svc = CartService(db)
    try:
        items_data = [{"variant_id": i.variant_id, "quantity": i.quantity} for i in req.items]
        return svc.add_bundle_to_cart(user.id, items_data, req.bundle_name)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.put("/items/{variant_id}")
def update_cart_item(variant_id: int, req: CartItemUpdate, user: UserAccount = Depends(require_role(["CUSTOMER"])), db: Session = Depends(get_db)):
    svc = CartService(db)
    try:
        return svc.update_cart_item(user.id, variant_id, req.quantity)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/items/{variant_id}")
def delete_cart_item(variant_id: int, user: UserAccount = Depends(require_role(["CUSTOMER"])), db: Session = Depends(get_db)):
    svc = CartService(db)
    return svc.remove_from_cart(user.id, variant_id)

@router.post("/merge")
def merge_guest_cart(req: CartMergeRequest, user: UserAccount = Depends(require_role(["CUSTOMER"])), db: Session = Depends(get_db)):
    svc = CartService(db)
    items_data = [{"variant_id": item.variant_id, "quantity": item.quantity} for item in req.items]
    return svc.merge_guest_cart(user.id, items_data)

# -----------------------------------------------------------------------------
# WISHLIST & ABANDONED CART REMINDER ENDPOINTS
# -----------------------------------------------------------------------------

@router.get("/wishlist")
def get_user_wishlist(user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)):
    svc = CartService(db)
    return svc.get_wishlist(user.id)

@router.post("/wishlist/toggle/{product_id}")
def toggle_user_wishlist(product_id: int, user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)):
    svc = CartService(db)
    try:
        return svc.toggle_wishlist(user.id, product_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.delete("/wishlist/{product_id}")
def delete_wishlist_item(product_id: int, user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)):
    svc = CartService(db)
    return svc.remove_from_wishlist(user.id, product_id)

@router.get("/wishlist/check-discounts")
def check_wishlist_discounts(user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)):
    svc = CartService(db)
    return svc.check_wishlist_discounts(user.id)

@router.post("/trigger-reminders")
def trigger_abandoned_cart_reminders(
    older_than_hours: int = 24,
    db: Session = Depends(get_db)
):
    svc = CartService(db)
    return svc.trigger_cart_reminders(older_than_hours=older_than_hours)

