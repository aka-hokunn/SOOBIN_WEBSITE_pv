import time
import logging
from datetime import datetime
from app.core.database import SessionLocal
from app.services.order_service import OrderService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("order_expiry_job")

def run_expiry_cycle():
    db = SessionLocal()
    try:
        svc = OrderService(db)
        expired_count = svc.expire_unpaid_vietqr_orders()
        if expired_count > 0:
            logger.info(f"Đã tự động hủy {expired_count} đơn hàng VietQR quá hạn 24 giờ và hoàn trả tồn kho/voucher.")
    except Exception as e:
        logger.error(f"Lỗi khi thực thi job quét đơn quá hạn: {e}")
    finally:
        db.close()

def main():
    logger.info("Khởi động tiến trình nền quét đơn VietQR quá hạn 24 giờ...")
    while True:
        run_expiry_cycle()
        time.sleep(60) # Scan every 60 seconds

if __name__ == "__main__":
    main()
