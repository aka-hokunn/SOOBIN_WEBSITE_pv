"""
Gắn ảnh sản phẩm chuyên biệt (tạo riêng theo đúng tên sản phẩm) vào CSDL.

- Ảnh nguồn: thư mục chứa các file pNN_front.* / pNN_alt.* (NN = 01..40), mặc định
  backend/app/static/images/products/gen/  (có thể truyền thư mục khác làm tham số 1).
- Ảnh được chuẩn hoá về JPEG 4:5 (900x1125) và lưu vào static/images/products/gen/.
- Mỗi sản phẩm (kể cả các "Phiên Bản Pro #N") nhận gallery [front, alt] theo tên gốc.

Chạy:  backend\\.venv-runtime\\Scripts\\python.exe backend/apply_product_photos.py [thư_mục_nguồn]
"""
import os
import re
import sys
import glob

from PIL import Image, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal  # noqa: E402
from app.models import ProductionProduct, ProductionProductImage  # noqa: E402

GEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "static", "images", "products", "gen")
GEN_URL = "/static/images/products/gen"
TARGET_SIZE = (900, 1125)  # 4:5

# Thứ tự khớp với bảng mô tả ảnh (NN = vị trí trong danh sách, bắt đầu từ 01)
PRODUCT_PHOTO_INDEX = [
    "Áo Tắm 1 Mảnh Liền Thân Soobin Elegance Khoét Lưng",
    "Bộ Bikini 2 Mảnh Soobin Coral Beach Cạp Cao",
    "Quần Bơi Nam Soobin Speed Pro Ôm Sát Chuyên Nghiệp",
    "Quần Bơi Boxer Nam Đi Biển Họa Tiết Sóng Biển",
    "Kính Bơi Chống Đọng Sương Góc Rộng Soobin Pro",
    "Mũ Bơi Silicone Soobin Hydrodynamic Ôm Đầu Không Đau",
    "Áo Bơi Chống Nắng Nữ Tay Dài Soobin UV-Pro Khóa Kéo",
    "Bộ Đồ Bơi Bé Gái Cầu Vồng Soobin Kids Đáng Yêu",
    "Túi Chống Nước Đa Năng Đi Biển Soobin Dry Bag 20L",
    "Bộ Áo Tắm Liền Thân Thể Thao Soobin Active Dynamic",
    "Quần Bơi Nam Dài Ngang Gối Soobin Racing Pro",
    "Chân Vịt Tập Bơi Chuyên Dụng Soobin Power Fins",
    "Bikini Thể Thao Lướt Sóng Malibu Wave-Lock",
    "Áo Bơi Dài Tay Chống Nắng Rashguard Ocean Guard",
    "Quần Bơi Nam Cạp Thấp Sprint Finisher",
    "Quần Bơi Nam Lướt Sóng Waikiki Pro-Stretch",
    "Bộ Đồ Bơi Bé Gái Sắc Màu Đại Dương Nhí",
    "Kính Bơi Chuyên Nghiệp Thủy Thủ Đoàn Hydro-Vision",
    "Bộ Dụng Cụ Tập Bơi Chuyên Nghiệp (Phao Tập & Chân Vịt)",
    "Bikini 2 Mảnh Dây Đan Chéo Santorini Sun",
    "Áo Rashguard Nữ Họa Tiết Nhiệt Đới Aloha Reef",
    "Quần Bơi Nam Đường Đua Xanh Aqua-Speed",
    "Quần Bơi Boxer Nam Phong Cách Biển Xanh Aqua",
    "Áo Bơi Liền Thân Bé Gái Nàng Tiên Cá Xanh",
    "Kính Bơi Tráng Gương Chống Đọng Sương TYR Pro",
    "Chân Vịt Tập Bơi & Lặn Biển Hydro-Elite Silicone",
    "Bikini Cổ Vuông Quý Phái Riviera Azure",
    "Đồ Bơi Liền Thân Nữ Đường Đua Xanh Olympic Pro",
    "Quần Bơi Nam Thi Đấu Pro Jammer Hydro-Blade",
    "Quần Bơi Đi Biển Nam Resort Palm Breeze",
    "Đồ Bơi Trẻ Em Hồng Hạc Nắng Hè UPF 50+",
    "Combo Kính Bơi Thi Đấu & Mũ Bơi Silicone Khí Động Học",
    "Túi Chống Nước Đi Biển Oceanic Dry Bag 20L",
    "Set Bikini 2 Mảnh Nắng Vàng Địa Trung Hải",
    "Áo Tắm 1 Mảnh Nữ Sắc Xanh Đại Dương Sâu",
    "Quần Bơi Nam Chuyên Nghiệp Carbon-Stream",
    "Quần Short Đi Biển Nam Sóng Đại Dương Cyan",
    "Bikini Nữ Cạp Cao Sóng Biển Ngọc Bích",
    "Đồ Bơi 1 Mảnh Nữ Lưng Chữ X Aura Racing",
    "Bikini 2 Mảnh Nhiệt Đới Coral Breeze Cạp Cao",
]
EDITION_RE = re.compile(r"\s+—\s+Phiên Bản Pro #\d+$")


def base_name(name: str) -> str:
    return EDITION_RE.sub("", name or "").strip()


def find_source(src_dir: str, nn: int, kind: str):
    # Hỗ trợ cả tên gọn (p05_front.png) lẫn tên có hậu tố thời gian (p05_front_1794213018252.jpg);
    # nếu có nhiều bản, lấy bản mới nhất.
    for pattern in (f"p{nn:02d}_{kind}.*", f"p{nn:02d}_{kind}_*.*", f"p{nn}_{kind}.*", f"p{nn}_{kind}_*.*"):
        hits = [h for h in glob.glob(os.path.join(src_dir, pattern)) if h.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
        if hits:
            return max(hits, key=os.path.getmtime)
    return None


def normalize(src: str, dest: str):
    img = Image.open(src).convert("RGB")
    img = ImageOps.fit(img, TARGET_SIZE, Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    img.save(dest, "JPEG", quality=86, optimize=True, progressive=True)


def make_detail_crop(src: str, dest: str, focus_y: float = 0.42):
    """Tạo ảnh cận cảnh chất liệu / đường may từ đúng ảnh sản phẩm (zoom 1.4x)."""
    img = Image.open(src).convert("RGB")
    w, h = img.size
    crop_w, crop_h = int(w * 0.70), int(h * 0.70)
    left = max(0, (w - crop_w) // 2)
    top = max(0, min(h - crop_h, int(h * focus_y - crop_h / 2)))
    cropped = img.crop((left, top, left + crop_w, top + crop_h))
    cropped = ImageOps.fit(cropped, TARGET_SIZE, Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    cropped.save(dest, "JPEG", quality=86, optimize=True, progressive=True)


def prepare_photos(src_dir: str):
    """Chuẩn hoá ảnh nguồn → GEN_DIR; trả về {NN: [url_front, url_alt, url_detail1, url_detail2]}."""
    os.makedirs(GEN_DIR, exist_ok=True)
    photos = {}
    for nn in range(1, len(PRODUCT_PHOTO_INDEX) + 1):
        urls = []
        local_paths = {}
        for kind in ("front", "alt"):
            src = find_source(src_dir, nn, kind)
            if not src:
                src = find_source(GEN_DIR, nn, kind)
            if not src:
                continue
            dest_name = f"p{nn:02d}_{kind}.jpg"
            dest = os.path.join(GEN_DIR, dest_name)
            if os.path.abspath(src) != os.path.abspath(dest):
                normalize(src, dest)
            local_paths[kind] = dest
            urls.append(f"{GEN_URL}/{dest_name}")
        if "front" in local_paths:
            d1_name = f"p{nn:02d}_detail1.jpg"
            d1_path = os.path.join(GEN_DIR, d1_name)
            make_detail_crop(local_paths["front"], d1_path, focus_y=0.40)
            urls.append(f"{GEN_URL}/{d1_name}")
        if "alt" in local_paths:
            d2_name = f"p{nn:02d}_detail2.jpg"
            d2_path = os.path.join(GEN_DIR, d2_name)
            make_detail_crop(local_paths["alt"], d2_path, focus_y=0.52)
            urls.append(f"{GEN_URL}/{d2_name}")
        elif "front" in local_paths:
            d2_name = f"p{nn:02d}_detail2.jpg"
            d2_path = os.path.join(GEN_DIR, d2_name)
            make_detail_crop(local_paths["front"], d2_path, focus_y=0.60)
            urls.append(f"{GEN_URL}/{d2_name}")
        if urls:
            photos[nn] = urls
    return photos


def apply(src_dir: str = GEN_DIR) -> int:
    photos = prepare_photos(src_dir)
    index = {name: i + 1 for i, name in enumerate(PRODUCT_PHOTO_INDEX)}
    db = SessionLocal()
    updated = 0
    try:
        for prod in db.query(ProductionProduct).all():
            nn = index.get(base_name(prod.name))
            urls = photos.get(nn) if nn else None
            if not urls:
                continue
            db.query(ProductionProductImage).filter(
                ProductionProductImage.product_id == prod.id
            ).delete(synchronize_session=False)
            labels = [
                f"{prod.name} - Mặt trước",
                f"{prod.name} - Mặt sau / Góc nghiêng",
                f"{prod.name} - Cận cảnh chất liệu",
                f"{prod.name} - Chi tiết đường may",
            ]
            for i, url in enumerate(urls):
                label = labels[i] if i < len(labels) else f"{prod.name} - Ảnh {i + 1}"
                db.add(ProductionProductImage(product_id=prod.id, file_path=url, alt_text=label, sort_order=i))
            updated += 1
        db.commit()
    finally:
        db.close()
    print(f"[SUCCESS] Ảnh chuyên biệt: {len(photos)}/{len(PRODUCT_PHOTO_INDEX)} mẫu sẵn sàng, cập nhật {updated} sản phẩm.")
    return updated


if __name__ == "__main__":
    apply(sys.argv[1] if len(sys.argv) > 1 else GEN_DIR)

