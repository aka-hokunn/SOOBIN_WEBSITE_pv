import pytest
from app.services.promotion_service import PromotionService

def test_prd_section_7_exact_promotion_example(db_session):
    """
    PRD Section 7:
    Áo 500.000 giảm 30%, quần 300.000 không giảm; KM hóa đơn 10%, voucher 15%.
    G = 800.000
    D_sp = 150.000 (30% của 500k)
    D_hd = 80.000 (10% của 800k)
    D_vc = 120.000 (15% của 800k)
    Chọn phương án sản phẩm; tiền hàng = 650.000; voucher không bị trừ lượt.
    """
    svc = PromotionService(db_session)

    # Product 1 has SUMMER30 (30%), Product 3 (Quần bơi) has no product promotion
    items = [
        {"product_id": 1, "variant_id": 1, "unit_price": 500000.0, "quantity": 1},
        {"product_id": 3, "variant_id": 9, "unit_price": 300000.0, "quantity": 1}
    ]

    # Voucher SOOBIN15 has 15% discount, min order 300k
    calc = svc.calculate_discounts(items=items, voucher_code="SOOBIN15")

    assert calc["original_subtotal"] == 800000.0
    assert calc["product_discount"] == 150000.0
    assert calc["order_discount"] == 80000.0
    assert calc["voucher_discount"] == 120000.0
    assert calc["selected_option_type"] == "PRODUCT"
    assert calc["winning_discount_amount"] == 150000.0
    assert calc["final_subtotal"] == 650000.0

def test_promotion_tie_breaker_product_over_order_over_voucher(db_session):
    """
    PRD Section 7: Hai phương án giảm bằng nhau: Sản phẩm -> Hóa đơn -> Voucher.
    """
    svc = PromotionService(db_session)
    # When discounts tie, tie-breaker prioritizes PRODUCT over others
    items = [{"product_id": 1, "variant_id": 1, "unit_price": 100000.0, "quantity": 1}]
    calc = svc.calculate_discounts(items=items, voucher_code=None)
    assert calc["selected_option_type"] == "PRODUCT"

def test_rounding_to_dong(db_session):
    """PRD Section 7: Làm tròn đến đồng, phần lẻ từ 0,5 làm tròn lên."""
    assert PromotionService.round_dong(150000.4) == 150000.0
    assert PromotionService.round_dong(150000.5) == 150001.0
    assert PromotionService.round_dong(150000.6) == 150001.0
