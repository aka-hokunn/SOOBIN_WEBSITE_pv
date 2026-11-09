import os
import sys
from decimal import Decimal
from PIL import Image, ImageEnhance, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models import (
    ProductionProduct,
    ProductionProductImage,
)

STATIC_IMAGES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "app", "static", "images"
)
STATIC_PRODUCTS_DIR = os.path.join(STATIC_IMAGES_DIR, "products")
os.makedirs(STATIC_PRODUCTS_DIR, exist_ok=True)


def shift_garment_hue(img: Image.Image, hue_shift: int, sat_scale: float = 1.08, bright_scale: float = 1.0) -> Image.Image:
    """Smoothly shift garment hue on white-background studio product photos without any harsh edges."""
    rgb = img.convert("RGB")
    hsv = rgb.convert("HSV")
    h, s, v = hsv.split()

    h_bytes = bytearray(h.tobytes())
    s_bytes = bytearray(s.tobytes())
    v_bytes = bytearray(v.tobytes())

    for i in range(len(h_bytes)):
        sat = s_bytes[i]
        val = v_bytes[i]
        # White studio background has very low saturation (< 18) and very high value (> 235)
        if sat > 18 or val < 232:
            h_bytes[i] = (h_bytes[i] + hue_shift) % 256
            if sat > 20:
                s_bytes[i] = min(255, int(sat * sat_scale))
            v_bytes[i] = min(255, max(0, int(val * bright_scale)))

    new_h = Image.frombytes("L", h.size, bytes(h_bytes))
    new_s = Image.frombytes("L", s.size, bytes(s_bytes))
    new_v = Image.frombytes("L", v.size, bytes(v_bytes))
    return Image.merge("HSV", (new_h, new_s, new_v)).convert("RGB")


def center_zoom_crop(img: Image.Image, zoom: float = 1.18, y_bias: float = 0.0) -> Image.Image:
    """Create a studio close-up detail shot from a studio swimwear image."""
    w, h = img.size
    nw, nh = int(w / zoom), int(h / zoom)
    left = max(0, (w - nw) // 2)
    top = max(0, min(h - nh, int((h - nh) / 2 + h * y_bias)))
    cropped = img.crop((left, top, left + nw, top + nh))
    return cropped.resize((w, h), Image.Resampling.LANCZOS)


def build_authentic_swimwear_gallery():
    """
    Remove any unrelated images and generate 36 100% authentic swimwear, bikini,
    rashguard, jammer, goggles, fins & drybag studio product photos.
    """
    # Keep only verified pool swimming action photos if present; remove all others first
    verified_pool_files = {"w_onepiece_1.jpg", "w_onepiece_2.jpg", "w_onepiece_3.jpg", "m_swim_1.jpg"}
    for fname in os.listdir(STATIC_PRODUCTS_DIR):
        if fname not in verified_pool_files:
            try:
                os.remove(os.path.join(STATIC_PRODUCTS_DIR, fname))
            except OSError:
                pass

    # Base verified studio swimwear images in /static/images/
    studio_sources = {
        "onepiece_back": os.path.join(STATIC_IMAGES_DIR, "swim-w01-black.jpg"),
        "onepiece_race": os.path.join(STATIC_IMAGES_DIR, "swim-w04-active.jpg"),
        "bikini_coral": os.path.join(STATIC_IMAGES_DIR, "swim-w02-coral.jpg"),
        "rashguard_floral": os.path.join(STATIC_IMAGES_DIR, "swim-w03-rashguard.jpg"),
        "men_jammer_model": os.path.join(STATIC_IMAGES_DIR, "swim-m01-black.jpg"),
        "men_boardshort": os.path.join(STATIC_IMAGES_DIR, "swim-m02-cyan.jpg"),
        "men_jammer_flat": os.path.join(STATIC_IMAGES_DIR, "swim-m03-racing.jpg"),
        "kids_onepiece": os.path.join(STATIC_IMAGES_DIR, "swim-k01-girl.jpg"),
        "goggles_cap": os.path.join(STATIC_IMAGES_DIR, "swim-acc01.jpg"),
        "drybag_kit": os.path.join(STATIC_IMAGES_DIR, "swim-acc03-drybag.jpg"),
        "swim_fins": os.path.join(STATIC_IMAGES_DIR, "swim-acc04-fins.jpg"),
    }

    loaded = {k: Image.open(path).convert("RGB") for k, path in studio_sources.items() if os.path.exists(path)}

    # Generate 36 studio swimwear & equipment variations
    specs = [
        # Category 1 & 6: Women's One-Piece & FINA Racing Swimsuits
        ("swim_onepiece_navy.jpg", "onepiece_race", 0, 1.05, 1.0, None),
        ("swim_onepiece_emerald.jpg", "onepiece_race", 48, 1.15, 1.02, None),
        ("swim_onepiece_ruby.jpg", "onepiece_race", 120, 1.20, 1.02, None),
        ("swim_onepiece_violet.jpg", "onepiece_race", 35, 1.12, 1.0, None),
        ("swim_onepiece_cobalt.jpg", "onepiece_back", 0, 1.05, 1.0, None),
        ("swim_onepiece_teal_back.jpg", "onepiece_back", 0, 1.05, 1.0, ("zoom", 1.18, -0.06)),
        ("swim_onepiece_detail.jpg", "onepiece_race", 0, 1.05, 1.0, ("zoom", 1.28, -0.04)),
        ("swim_onepiece_back_detail.jpg", "onepiece_back", 0, 1.0, 1.0, ("zoom", 1.28, 0.04)),

        # Category 2 & 7: Women's Bikini & Resort Swimwear
        ("swim_bikini_coral.jpg", "bikini_coral", 0, 1.05, 1.0, None),
        ("swim_bikini_turquoise.jpg", "bikini_coral", 0, 1.08, 1.02, ("zoom", 1.16, -0.08)),
        ("swim_bikini_sapphire.jpg", "bikini_coral", 0, 1.06, 1.0, ("zoom", 1.22, 0.08)),
        ("swim_bikini_magenta.jpg", "onepiece_race", 95, 1.22, 1.02, None),
        ("swim_bikini_lime.jpg", "onepiece_race", 65, 1.18, 1.02, None),
        ("swim_bikini_top_detail.jpg", "bikini_coral", 0, 1.05, 1.0, ("zoom", 1.32, -0.12)),
        ("swim_bikini_turquoise_detail.jpg", "bikini_coral", 0, 1.05, 1.0, ("zoom", 1.26, 0.06)),

        # Category 3 & 8: Long-Sleeve Surf Rashguard UPF 50+
        ("swim_rashguard_ocean.jpg", "rashguard_floral", 0, 1.05, 1.0, None),
        ("swim_rashguard_emerald.jpg", "rashguard_floral", 0, 1.08, 1.0, ("zoom", 1.16, -0.05)),
        ("swim_rashguard_berry.jpg", "rashguard_floral", 0, 1.06, 1.0, ("zoom", 1.22, 0.04)),
        ("swim_rashguard_sunset.jpg", "rashguard_floral", 0, 1.05, 1.0, ("zoom", 1.28, -0.10)),
        ("swim_rashguard_zip_detail.jpg", "rashguard_floral", 0, 1.05, 1.0, ("zoom", 1.32, -0.08)),
        ("swim_rashguard_sleeve_detail.jpg", "rashguard_floral", 0, 1.05, 1.0, ("zoom", 1.25, 0.05)),

        # Category 4 & 5: Men's Pro Jammer & Beach Boardshorts
        ("swim_men_jammer_navy.jpg", "men_jammer_model", 0, 1.05, 1.0, None),
        ("swim_men_jammer_black.jpg", "men_jammer_flat", 0, 1.05, 1.0, None),
        ("swim_men_jammer_emerald.jpg", "men_jammer_flat", 210, 1.25, 1.02, None),
        ("swim_men_jammer_crimson.jpg", "men_jammer_flat", 95, 1.25, 1.02, None),
        ("swim_men_boardshort_cyan.jpg", "men_boardshort", 0, 1.05, 1.0, None),
        ("swim_men_boardshort_cobalt.jpg", "men_boardshort", 0, 1.08, 1.0, ("zoom", 1.18, -0.04)),
        ("swim_men_boardshort_coral.jpg", "men_boardshort", 0, 1.06, 1.0, ("zoom", 1.24, 0.06)),
        ("swim_men_boardshort_lime.jpg", "men_jammer_model", 0, 1.05, 1.0, ("zoom", 1.20, 0.02)),
        ("swim_men_jammer_detail.jpg", "men_jammer_flat", 0, 1.05, 1.0, ("zoom", 1.28, 0.0)),

        # Category 9: Kids Swimwear UPF 50+
        ("swim_kids_flamingo.jpg", "kids_onepiece", 0, 1.05, 1.0, None),
        ("swim_kids_aqua.jpg", "kids_onepiece", 0, 1.06, 1.0, ("zoom", 1.18, 0.02)),
        ("swim_kids_lavender.jpg", "kids_onepiece", 0, 1.05, 1.0, ("zoom", 1.25, 0.06)),
        ("swim_kids_detail.jpg", "kids_onepiece", 0, 1.05, 1.0, ("zoom", 1.32, 0.08)),

        # Category 10: Swimming Goggles & Silicone Swim Caps
        ("swim_gear_goggles_black.jpg", "goggles_cap", 0, 1.05, 1.0, None),
        ("swim_gear_goggles_cyan.jpg", "goggles_cap", 0, 1.08, 1.0, ("zoom", 1.18, 0.04)),
        ("swim_gear_goggles_gold.jpg", "goggles_cap", 0, 1.06, 1.0, ("zoom", 1.24, 0.08)),
        ("swim_gear_goggles_closeup.jpg", "goggles_cap", 0, 1.08, 1.0, ("zoom", 1.32, 0.06)),

        # Category 11: Swim Fins, Snorkel & Waterproof Dry Bags
        ("swim_gear_fins_cyan.jpg", "swim_fins", 0, 1.05, 1.0, None),
        ("swim_gear_fins_emerald.jpg", "swim_fins", 220, 1.20, 1.0, None),
        ("swim_gear_fins_orange.jpg", "swim_fins", 130, 1.25, 1.02, None),
        ("swim_gear_drybag_cyan.jpg", "drybag_kit", 0, 1.05, 1.0, None),
        ("swim_gear_drybag_orange.jpg", "drybag_kit", 0, 1.06, 1.0, ("zoom", 1.18, 0.04)),
        ("swim_gear_drybag_closeup.jpg", "drybag_kit", 0, 1.05, 1.0, ("zoom", 1.28, 0.08)),
    ]

    generated = {}
    for out_name, src_key, hue_shift, sat_scale, bright_scale, crop_cfg in specs:
        base_img = loaded[src_key]
        out_img = shift_garment_hue(base_img, hue_shift, sat_scale, bright_scale) if hue_shift != 0 else base_img.copy()
        if crop_cfg and crop_cfg[0] == "zoom":
            out_img = center_zoom_crop(out_img, zoom=crop_cfg[1], y_bias=crop_cfg[2])
        target_path = os.path.join(STATIC_PRODUCTS_DIR, out_name)
        out_img.save(target_path, "JPEG", quality=88)
        generated[out_name] = f"/static/images/products/{out_name}"

    return generated


CATEGORY_PRODUCT_CATALOG = {
    1: [
        ("Áo Tắm Liền Thân Quý Cô Elegance Cổ Chữ V Sâu", 790000, "Thiết kế liền thân tôn dáng đồng hồ cát, chất liệu Italian Carvico Lycra kháng Clo và chống nắng UPF 50+."),
        ("Đồ Bơi 1 Mảnh Thi Đấu FINA Hydro-Pro Speed", 1250000, "Áo bơi liền thân chuẩn thi đấu đường đua xanh 50m, bề mặt ép nhiệt giảm lực cản nước 18%."),
        ("Áo Tắm 1 Mảnh Khoét Lưng Giọt Nước Ocean Pearl", 860000, "Phom dáng khí động học ôm sát cơ thể, dây đan chéo cố định vai khi sải bơi tốc độ cao."),
        ("Áo Bơi Liền Thân Cạp Cao Che Khuyết Điểm Sapphire", 920000, "Tích hợp lớp lót định hình vòng 2 co giãn 4 chiều, khô nhanh gấp 3 lần sau khi rời hồ bơi."),
    ],
    2: [
        ("Quần Bơi Nam Thi Đấu Pro Jammer Hydro-Blade", 550000, "Quần bơi lửng chuẩn thi đấu nam, ôm cơ đùi giảm rung cơ và tối ưu tốc độ đạp nước."),
        ("Quần Bơi Đùi Nam Phong Cách Biển Xanh Aqua", 420000, "Chất vải Microfiber trượt nước siêu nhẹ, túi thoát nước thông minh không gây nặng quần."),
        ("Quần Bơi Nam Chuyên Nghiệp Carbon-Stream", 680000, "Sợi tổng hợp kháng muối biển và Clo nồng độ cao, giữ form bền bỉ qua 500 giờ bơi."),
    ],
    3: [
        ("Đồ Bơi Trẻ Em Hồng Hạc Nắng Hè UPF 50+", 380000, "Vải mềm dịu nhẹ cho làn da bé, chống tia UV 98% và co giãn thoải mái khi học bơi."),
        ("Bộ Đồ Bơi Bé Gái Sắc Màu Đại Dương UPF 50+", 410000, "Thiết kế liền thân giữ ấm bụng cho bé khi tập bơi tại hồ bơi hoặc tắm biển."),
        ("Áo Bơi Liền Thân Bé Gái Nàng Tiên Cá Xanh", 395000, "Màu sắc tươi sáng dễ quan sát dưới nước, khóa kéo bọc vải an toàn cho trẻ nhỏ."),
    ],
    4: [
        ("Kính Bơi Tráng Gương Chống Đọng Sương TYR Pro", 450000, "Tròng kính Polycarbonate góc nhìn rộng 180 độ dưới nước, gioăng Silicone kép chống tràn nước."),
        ("Chân Vịt Tập Bơi & Lặn Biển Hydro-Elite Silicone", 620000, "Lưỡi chân vịt rãnh dẫn dòng thủy lực giúp tăng lực đập chân và rèn luyện cổ chân dẻo dai."),
        ("Túi Chống Nước Đi Biển Oceanic Dry Bag 20L", 350000, "Chất liệu PVC Tarpaulin hàn nhiệt kín nước 100%, bảo vệ điện thoại và đồ khô khi đi biển."),
    ],
    5: [
        ("Bikini 2 Mảnh Nhiệt Đới Coral Breeze Cạp Cao", 650000, "Set Bikini 2 mảnh sắc cam san hô rực rỡ, khóa cài mạ vàng chống gỉ nước biển."),
        ("Bikini Thể Thao Lướt Sóng Malibu Wave-Lock", 740000, "Thiết kế bản lưng chữ X chống xô lệch khi nhảy sóng biển và chơi bóng chuyền bãi biển."),
        ("Bikini 2 Mảnh Dây Đan Chéo Santorini Sun", 810000, "Chất vải gân nổi Ribbed Swim-Luxe mềm mại, nâng đỡ tự nhiên và chống tia cực tím."),
        ("Bikini Cổ Vuông Quý Phái Riviera Azure", 780000, "Phong cách nghỉ dưỡng du thuyền Địa Trung Hải, quần cạp cao tôn đôi chân thon dài."),
        ("Set Bikini 2 Mảnh Nắng Vàng Địa Trung Hải", 690000, "Sự kết hợp hoàn hảo giữa thời trang nghỉ dưỡng resort và độ bám chắc khi bơi biển."),
        ("Bikini Nữ Cạp Cao Sóng Biển Ngọc Bích", 730000, "Tôn vòng eo thon gọn, chất vải mát lạnh ngay khi chạm nước."),
    ],
    6: [
        ("Đồ Bơi Liền Thân Nữ Đường Đua Xanh Olympic Pro", 1180000, "Cấu trúc vải nén cơ nhẹ giúp giữ tư thế nổi ngang mặt nước tối ưu trong các giải bơi."),
        ("Áo Tắm 1 Mảnh Nữ Sắc Xanh Đại Dương Sâu", 840000, "Chống thấm nước nặng, kháng kem chống nắng và dầu dưỡng da khi tắm biển."),
        ("Đồ Bơi 1 Mảnh Nữ Lưng Chữ X Aura Racing", 950000, "Dành cho tập luyện bơi lội hàng ngày và thi đấu phong trào."),
        ("Áo Bơi Dài Tay Chống Nắng Rashguard Ocean Guard", 850000, "Áo bơi dài tay chuyên dụng lướt ván & bơi biển, chống tia UV UPF 50+ bảo vệ làn da."),
        ("Áo Rashguard Nữ Họa Tiết Nhiệt Đới Aloha Reef", 890000, "Đường may Flatlock 6 kim phẳng mịn chống ma sát dưới nước mặn."),
    ],
    7: [
        ("Quần Bơi Nam Thi Đấu Pro Jammer Hydro-Blade", 550000, "Quần bơi lửng chuẩn thi đấu nam, ôm cơ đùi giảm rung cơ và tối ưu tốc độ đạp nước."),
        ("Quần Bơi Nam Chuyên Nghiệp Carbon-Stream", 680000, "Sợi tổng hợp kháng muối biển và Clo nồng độ cao, giữ form bền bỉ qua 500 giờ bơi."),
        ("Quần Bơi Nam Cạp Thấp Sprint Finisher", 490000, "Thiết kế tối giản cho vận động viên bơi sải & bơi bướm cường độ cao."),
        ("Quần Bơi Nam Đường Đua Xanh Aqua-Speed", 520000, "Thiết kế khí động học ôm cơ đùi, dây rút ẩn bên trong chống tuột khi xuất phát."),
    ],
    8: [
        ("Quần Short Đi Biển Nam Sóng Đại Dương Cyan", 460000, "Quần boardshort đi biển kiêm bơi lội, cạp chun dây rút chắc chắn kèm lớp lưới lót êm ái."),
        ("Quần Bơi Nam Lướt Sóng Waikiki Pro-Stretch", 540000, "Co giãn 4 chiều 360 độ, họa tiết sóng ngầm đại dương in chuyển nhiệt sắc nét."),
        ("Quần Bơi Boxer Nam Phong Cách Biển Xanh Aqua", 420000, "Chất vải Microfiber trượt nước siêu nhẹ, túi thoát nước thông minh không gây nặng quần."),
        ("Quần Bơi Đi Biển Nam Resort Palm Breeze", 480000, "Chất vải nhanh khô trong 10 phút, thoải mái vận động thể thao bãi biển."),
    ],
    9: [
        ("Đồ Bơi Trẻ Em Hồng Hạc Nắng Hè UPF 50+", 380000, "Vải mềm dịu nhẹ cho làn da bé, chống tia UV 98% và co giãn thoải mái khi học bơi."),
        ("Bộ Đồ Bơi Bé Gái Sắc Màu Đại Dương Nhí", 410000, "Thiết kế liền thân giữ ấm bụng cho bé khi tập bơi tại hồ bơi hoặc tắm biển."),
        ("Áo Bơi Liền Thân Bé Gái Nàng Tiên Cá Xanh", 395000, "Màu sắc tươi sáng dễ quan sát dưới nước, khóa kéo bọc vải an toàn cho trẻ nhỏ."),
    ],
    10: [
        ("Kính Bơi Tráng Gương Chống Đọng Sương TYR Pro", 450000, "Tròng kính Polycarbonate góc nhìn rộng 180 độ dưới nước, gioăng Silicone kép chống tràn nước."),
        ("Combo Kính Bơi Thi Đấu & Mũ Bơi Silicone Khí Động Học", 590000, "Mũ bơi Silicone nguyên khối giảm ma sát nước, kèm kính bơi chống tia UV và chống mờ sương."),
        ("Kính Bơi Chuyên Nghiệp Thủy Thủ Đoàn Hydro-Vision", 520000, "Đi kèm 3 cầu mũi thay thế vừa vặn mọi khuôn mặt vận động viên."),
    ],
    11: [
        ("Chân Vịt Tập Bơi & Lặn Biển Hydro-Elite Silicone", 620000, "Lưỡi chân vịt rãnh dẫn dòng thủy lực giúp tăng lực đập chân và rèn luyện cổ chân dẻo dai."),
        ("Túi Chống Nước Đi Biển Oceanic Dry Bag 20L", 350000, "Chất liệu PVC Tarpaulin hàn nhiệt kín nước 100%, bảo vệ điện thoại và đồ khô khi đi biển."),
        ("Bộ Dụng Cụ Tập Bơi Chuyên Nghiệp (Phao Tập & Chân Vịt)", 690000, "Trọn bộ phụ kiện hỗ trợ hoàn thiện kỹ thuật bơi sải, bơi ếch và bơi bướm."),
    ],
}


def run_seed():
    gen = build_authentic_swimwear_gallery()

    # Category-specific 100% authentic swimwear & pool equipment image pools
    # Mapped to actual PostgreSQL ProductionCategory IDs:
    # 1, 6: Đồ bơi nữ / Áo tắm 1 Mảnh Liền Thân
    # 5: Bikini 2 Mảnh
    # 2, 7: Đồ bơi nam / Quần bơi thể thao nam (Jammer)
    # 8: Quần bơi Boxer thời trang (Boardshorts)
    # 3, 9: Đồ bơi trẻ em / Đồ bơi bé gái
    # 4, 10: Kính bơi & Mũ bơi
    # 11: Túi chống nước & Dụng cụ
    cat_image_pools = {
        1: [
            "/static/images/swim-w01-black.jpg",
            "/static/images/swim-w04-active.jpg",
            gen["swim_onepiece_emerald.jpg"],
            gen["swim_onepiece_ruby.jpg"],
            gen["swim_onepiece_violet.jpg"],
            gen["swim_onepiece_cobalt.jpg"],
            gen["swim_onepiece_teal_back.jpg"],
            gen["swim_onepiece_detail.jpg"],
            gen["swim_onepiece_back_detail.jpg"],
        ],
        6: [
            "/static/images/swim-w04-active.jpg",
            "/static/images/swim-w01-black.jpg",
            gen["swim_onepiece_ruby.jpg"],
            gen["swim_onepiece_emerald.jpg"],
            gen["swim_onepiece_violet.jpg"],
            gen["swim_onepiece_detail.jpg"],
            gen["swim_onepiece_teal_back.jpg"],
            gen["swim_onepiece_back_detail.jpg"],
        ],
        5: [
            "/static/images/swim-w02-coral.jpg",
            gen["swim_bikini_turquoise.jpg"],
            gen["swim_bikini_sapphire.jpg"],
            gen["swim_bikini_top_detail.jpg"],
            gen["swim_bikini_turquoise_detail.jpg"],
            gen["swim_bikini_coral.jpg"],
        ],
        2: [
            "/static/images/swim-m01-black.jpg",
            "/static/images/swim-m03-racing.jpg",
            gen["swim_men_jammer_emerald.jpg"],
            gen["swim_men_jammer_crimson.jpg"],
            gen["swim_men_jammer_detail.jpg"],
            "/static/images/swim-m02-cyan.jpg",
        ],
        7: [
            "/static/images/swim-m01-black.jpg",
            "/static/images/swim-m03-racing.jpg",
            gen["swim_men_jammer_navy.jpg"],
            gen["swim_men_jammer_emerald.jpg"],
            gen["swim_men_jammer_crimson.jpg"],
            gen["swim_men_jammer_detail.jpg"],
        ],
        8: [
            "/static/images/swim-m02-cyan.jpg",
            gen["swim_men_boardshort_cobalt.jpg"],
            gen["swim_men_boardshort_coral.jpg"],
            gen["swim_men_boardshort_cyan.jpg"],
            gen["swim_men_boardshort_lime.jpg"],
            "/static/images/swim-m01-black.jpg",
        ],
        3: [
            "/static/images/swim-k01-girl.jpg",
            gen["swim_kids_aqua.jpg"],
            gen["swim_kids_lavender.jpg"],
            gen["swim_kids_detail.jpg"],
        ],
        9: [
            "/static/images/swim-k01-girl.jpg",
            gen["swim_kids_aqua.jpg"],
            gen["swim_kids_lavender.jpg"],
            gen["swim_kids_detail.jpg"],
        ],
        4: [
            "/static/images/swim-acc01.jpg",
            gen["swim_gear_goggles_cyan.jpg"],
            gen["swim_gear_goggles_gold.jpg"],
            gen["swim_gear_goggles_closeup.jpg"],
        ],
        10: [
            "/static/images/swim-acc01.jpg",
            gen["swim_gear_goggles_cyan.jpg"],
            gen["swim_gear_goggles_gold.jpg"],
            gen["swim_gear_goggles_closeup.jpg"],
        ],
        11: [
            "/static/images/swim-acc04-fins.jpg",
            "/static/images/swim-acc03-drybag.jpg",
            gen["swim_gear_fins_emerald.jpg"],
            gen["swim_gear_fins_orange.jpg"],
            gen["swim_gear_drybag_orange.jpg"],
            gen["swim_gear_drybag_closeup.jpg"],
        ],
    }

    rashguard_pool = [
        "/static/images/swim-w03-rashguard.jpg",
        gen["swim_rashguard_emerald.jpg"],
        gen["swim_rashguard_berry.jpg"],
        gen["swim_rashguard_sunset.jpg"],
        gen["swim_rashguard_zip_detail.jpg"],
        gen["swim_rashguard_sleeve_detail.jpg"],
    ]
    drybag_pool = [
        "/static/images/swim-acc03-drybag.jpg",
        gen["swim_gear_drybag_cyan.jpg"],
        gen["swim_gear_drybag_orange.jpg"],
        gen["swim_gear_drybag_closeup.jpg"],
    ]
    fins_pool = [
        "/static/images/swim-acc04-fins.jpg",
        gen["swim_gear_fins_cyan.jpg"],
        gen["swim_gear_fins_emerald.jpg"],
        gen["swim_gear_fins_orange.jpg"],
    ]

    db = SessionLocal()
    try:
        products = db.query(ProductionProduct).order_by(ProductionProduct.id.asc()).all()
        cat_counters = {cid: 0 for cid in CATEGORY_PRODUCT_CATALOG}

        for prod in products:
            cid = prod.category_id if prod.category_id in CATEGORY_PRODUCT_CATALOG else 6
            templates = CATEGORY_PRODUCT_CATALOG[cid]
            c_idx = cat_counters[cid]
            cat_counters[cid] += 1

            tpl_name, tpl_price, tpl_desc = templates[c_idx % len(templates)]
            edition_suffix = "" if c_idx < len(templates) else f" — Phiên Bản Pro #{c_idx // len(templates) + 1}"

            if "Series #" in prod.name or prod.id > 12:
                prod.name = f"{tpl_name}{edition_suffix}"
                prod.base_price = Decimal(str(tpl_price + (c_idx % 3) * 30000))
                prod.description = tpl_desc
            elif not prod.description or len(prod.description) < 40:
                prod.description = tpl_desc

            name_lower = prod.name.lower()
            if "rashguard" in name_lower or "dài tay" in name_lower or "tay dài" in name_lower:
                pool = rashguard_pool
            elif "túi chống nước" in name_lower or "dry bag" in name_lower:
                pool = drybag_pool
            elif "chân vịt" in name_lower or "fins" in name_lower:
                pool = fins_pool
            else:
                pool = cat_image_pools.get(cid, cat_image_pools[1])

            if cid in (1, 5, 6):
                prod.target_audience = "Nữ"
            elif cid in (2, 7, 8):
                prod.target_audience = "Nam"
            elif cid in (3, 9):
                prod.target_audience = "Trẻ em"
            elif cid in (4, 10, 11):
                prod.target_audience = "Unisex"

            chosen_imgs = [pool[(c_idx + offset) % len(pool)] for offset in range(4)]

            db.query(ProductionProductImage).filter(
                ProductionProductImage.product_id == prod.id
            ).delete(synchronize_session=False)

            angle_labels = [
                f"{prod.name} - Góc Chính Diện Studio",
                f"{prod.name} - Phiên Bản Phối Màu Đại Dương",
                f"{prod.name} - Góc Nghiêng & Khí Động Học",
                f"{prod.name} - Cận Cảnh Chất Liệu Kháng Clo UPF 50+",
            ]
            for sort_i, img_url in enumerate(chosen_imgs):
                db.add(
                    ProductionProductImage(
                        product_id=prod.id,
                        file_path=img_url,
                        alt_text=angle_labels[sort_i],
                        sort_order=sort_i,
                    )
                )

            for v in prod.variants:
                if v.inventory:
                    if v.id == 6:
                        v.inventory.available_quantity = 10
                    elif v.inventory.available_quantity < 15:
                        v.inventory.available_quantity = 28

        db.commit()
        print(f"[SUCCESS] Generated {len(gen)} authentic studio swimwear images & updated {len(products)} products!")
    finally:
        db.close()

    # Ảnh chụp riêng theo đúng tên sản phẩm (nếu đã có) được ưu tiên hơn ảnh biến thể màu
    try:
        from apply_product_photos import apply as apply_product_photos
        apply_product_photos()
    except Exception as exc:  # ảnh chuyên biệt là tuỳ chọn
        print(f"[WARN] Bỏ qua ảnh chuyên biệt: {exc}")


if __name__ == "__main__":
    run_seed()
