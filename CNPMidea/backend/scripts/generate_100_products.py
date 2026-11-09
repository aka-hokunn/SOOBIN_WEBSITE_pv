import os
import sys
import json
import random

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seed.sql")

# Base Products 1 to 12 (PRESERVED EXACTLY FOR EXISTING TESTS)
base_products = [
    {
        "id": 1, "cat": 6, "line": 2, "code": "SWIM-W01", "slug": "ao-tam-1-manh-soobin-elegance",
        "name": "Áo Tắm 1 Mảnh Liền Thân Soobin Elegance Khoét Lưng", "price": 520000.0,
        "aud": "Nữ", "skill": "Bơi lội thể thao",
        "desc": "Áo tắm liền thân thiết kế tôn dáng cực kỳ quyến rũ với phần lưng khoét chữ U thanh lịch, đệm mút cao cấp nâng đỡ tự nhiên.",
        "care": "Giặt tay bằng nước lạnh, không dùng chất tẩy mạnh.",
        "specs": {"fabric": "82% Polyamide, 18% Spandex", "padding": "Có đệm mút tháo rời", "uv_protection": "UPF 50+"},
        "size_chart": {"S": {"chest": "80-84cm", "waist": "62-66cm", "hips": "86-90cm"}, "M": {"chest": "85-89cm", "waist": "67-71cm", "hips": "91-95cm"}, "L": {"chest": "90-94cm", "waist": "72-76cm", "hips": "96-100cm"}},
        "tags": ["do-boi-nu", "ao-tam-1-manh", "chong-nang", "resort"],
        "variants": [
            {"id": 1, "size": 2, "color": 1, "sku": "SWIM-W01-BLK-S", "stock": 25, "val": 6250000.0, "img": "/static/images/swim-w01-black.jpg"},
            {"id": 2, "size": 3, "color": 1, "sku": "SWIM-W01-BLK-M", "stock": 30, "val": 7500000.0, "img": "/static/images/swim-w01-black.jpg"},
            {"id": 3, "size": 4, "color": 1, "sku": "SWIM-W01-BLK-L", "stock": 15, "val": 3750000.0, "img": "/static/images/swim-w01-black.jpg"},
            {"id": 4, "size": 2, "color": 3, "sku": "SWIM-W01-NVY-S", "stock": 20, "val": 5000000.0, "img": "/static/images/swim-w01-navy.jpg"},
            {"id": 5, "size": 3, "color": 3, "sku": "SWIM-W01-NVY-M", "stock": 25, "val": 6250000.0, "img": "/static/images/swim-w01-navy.jpg"},
            {"id": 6, "size": 4, "color": 3, "sku": "SWIM-W01-NVY-L", "stock": 10, "val": 2500000.0, "img": "/static/images/swim-w01-navy.jpg"},
        ]
    },
    {
        "id": 2, "cat": 5, "line": 2, "code": "SWIM-W02", "slug": "bikini-2-manh-soobin-coral-beach",
        "name": "Bộ Bikini 2 Mảnh Soobin Coral Beach Cạp Cao", "price": 480000.0,
        "aud": "Nữ", "skill": "Nghỉ dưỡng",
        "desc": "Bikini hai mảnh cạp cao phong cách hiện đại giúp khéo léo che khuyết điểm vòng 2, gam màu san hô rực rỡ dưới ánh nắng hè.",
        "care": "Xả sạch với nước sau khi tắm biển, phơi nơi thoáng gió.",
        "specs": {"fabric": "Chống Clo, co giãn 4 chiều", "lining": "2 lớp vải lót kháng khuẩn"},
        "size_chart": {"S": {"chest": "78-83cm", "waist": "60-65cm"}, "M": {"chest": "84-88cm", "waist": "66-70cm"}},
        "tags": ["bikini", "cap-cao", "do-boi-nu"],
        "variants": [
            {"id": 7, "size": 2, "color": 4, "sku": "SWIM-W02-COR-S", "stock": 18, "val": 3960000.0, "img": "/static/images/swim-w02-coral.jpg"},
            {"id": 8, "size": 3, "color": 4, "sku": "SWIM-W02-COR-M", "stock": 22, "val": 4840000.0, "img": "/static/images/swim-w02-coral.jpg"},
        ]
    },
    {
        "id": 3, "cat": 7, "line": 1, "code": "SWIM-M01", "slug": "quan-boi-nam-soobin-speed-pro",
        "name": "Quần Bơi Nam Soobin Speed Pro Ôm Sát Chuyên Nghiệp", "price": 350000.0,
        "aud": "Nam", "skill": "Chuyên nghiệp",
        "desc": "Quần bơi nam thiết kế lướt nước tối ưu cho các buổi tập luyện và thi đấu thể thao, giảm tối đa ma sát trong nước.",
        "care": "Không giặt máy sấy khô, không ngâm xà phòng quá 30 phút.",
        "specs": {"drying": "Công nghệ QuickDry mau khô trong 15 phút", "waist": "Dây rút co giãn chắc chắn"},
        "size_chart": {"M": {"waist": "74-78cm", "weight": "55-65kg"}, "L": {"waist": "79-84cm", "weight": "65-75kg"}, "XL": {"waist": "85-90cm", "weight": "75-85kg"}},
        "tags": ["quan-boi-nam", "the-thao", "chuyen-nghiep"],
        "variants": [
            {"id": 9, "size": 3, "color": 1, "sku": "SWIM-M01-BLK-M", "stock": 35, "val": 6300000.0, "img": "/static/images/swim-m01-black.jpg"},
            {"id": 10, "size": 4, "color": 1, "sku": "SWIM-M01-BLK-L", "stock": 40, "val": 7200000.0, "img": "/static/images/swim-m01-black.jpg"},
            {"id": 11, "size": 5, "color": 1, "sku": "SWIM-M01-BLK-XL", "stock": 20, "val": 3600000.0, "img": "/static/images/swim-m01-black.jpg"},
            {"id": 12, "size": 3, "color": 3, "sku": "SWIM-M01-NVY-M", "stock": 15, "val": 2700000.0, "img": "/static/images/swim-m01-black.jpg"},
            {"id": 13, "size": 4, "color": 3, "sku": "SWIM-M01-NVY-L", "stock": 12, "val": 2160000.0, "img": "/static/images/swim-m01-black.jpg"},
        ]
    },
    {
        "id": 4, "cat": 8, "line": 2, "code": "SWIM-M02", "slug": "quan-boi-boxer-nam-soobin-ocean-wave",
        "name": "Quần Bơi Boxer Nam Đi Biển Họa Tiết Sóng Biển", "price": 320000.0,
        "aud": "Nam", "skill": "Nghỉ dưỡng",
        "desc": "Quần short bơi dáng boxer trẻ trung, năng động với túi sau tiện lợi, có thể mặc bơi hoặc dạo biển du lịch.",
        "care": "Giặt ở chế độ nhẹ, tránh phơi trực tiếp dưới nắng gắt.",
        "specs": {"pockets": "2 túi bên + 1 túi khóa dán", "mesh": "Lót lưới mềm bên trong"},
        "size_chart": {"M": {"waist": "72-78cm"}, "L": {"waist": "78-84cm"}, "XL": {"waist": "84-92cm"}},
        "tags": ["quan-boi-boxer", "di-bien", "nam"],
        "variants": [
            {"id": 14, "size": 3, "color": 5, "sku": "SWIM-M02-CYA-M", "stock": 28, "val": 4480000.0, "img": "/static/images/swim-m02-cyan.jpg"},
            {"id": 15, "size": 4, "color": 5, "sku": "SWIM-M02-CYA-L", "stock": 20, "val": 3200000.0, "img": "/static/images/swim-m02-cyan.jpg"},
        ]
    },
    {
        "id": 5, "cat": 10, "line": 1, "code": "SWIM-ACC01", "slug": "kinh-boi-soobin-anti-fog-wide-view",
        "name": "Kính Bơi Chống Đọng Sương Góc Rộng Soobin Pro", "price": 220000.0,
        "aud": "Unisex", "skill": "Mới tập bơi",
        "desc": "Kính bơi tráng gương bảo vệ mắt khỏi tia UV, tròng kính tráng nano chống đọng sương (anti-fog) cho tầm nhìn siêu trong.",
        "care": "Tránh chạm tay vào mặt trong kính để giữ lớp chống mờ.",
        "specs": {"lens": "Polycarbonate chống trầy xước", "strap": "Silicone mềm tùy chỉnh"},
        "size_chart": {"FREESIZE": {"info": "3 cầu mũi thay thế vừa vặn mọi khuôn mặt"}},
        "tags": ["kinh-boi", "phu-kien", "chong-tia-uv"],
        "variants": [
            {"id": 16, "size": 6, "color": 1, "sku": "SWIM-ACC01-BLK-FS", "stock": 50, "val": 5500000.0, "img": "/static/images/swim-acc01.jpg"}
        ]
    },
    {
        "id": 6, "cat": 10, "line": 1, "code": "SWIM-ACC02", "slug": "mu-boi-silicone-soobin-hydrodynamic",
        "name": "Mũ Bơi Silicone Soobin Hydrodynamic Ôm Đầu Không Đau", "price": 110000.0,
        "aud": "Unisex", "skill": "Bơi lội thể thao",
        "desc": "Mũ bơi chất liệu 100% silicone cao cấp chống rách, bảo vệ tóc và da đầu khỏi hóa chất hồ bơi clo.",
        "care": "Rắc phấn rôm khi cất giữ để tránh dính mũ.",
        "specs": {"material": "Silicone siêu dẻo không độc hại"},
        "size_chart": {"FREESIZE": {"info": "Co giãn tốt cho cả tóc ngắn và tóc dài"}},
        "tags": ["mu-boi", "phu-kien", "silicone"],
        "variants": [
            {"id": 17, "size": 6, "color": 3, "sku": "SWIM-ACC02-NVY-FS", "stock": 60, "val": 3600000.0, "img": "/static/images/swim-acc02.jpg"}
        ]
    },
    {
        "id": 7, "cat": 6, "line": 4, "code": "SWIM-W03", "slug": "ao-boi-chong-nang-tay-dai-soobin-uv-pro",
        "name": "Áo Bơi Chống Nắng Nữ Tay Dài Soobin UV-Pro Khóa Kéo", "price": 590000.0,
        "aud": "Nữ", "skill": "Vận động ngoài trời",
        "desc": "Áo bơi rashguard tay dài khóa kéo trước ngực tiện lợi, vải dệt UPF 50+ ngăn chặn 98% tia UVA/UVB khi lướt sóng và tắm biển.",
        "care": "Giặt tay nhẹ nhàng, phơi trong bóng râm.",
        "specs": {"sun_protection": "UPF 50+ UV Block", "zip": "Khóa kéo YKK chống kẹt"},
        "size_chart": {"S": {"chest": "80-85cm", "height": "150-160cm"}, "M": {"chest": "86-90cm", "height": "158-168cm"}, "L": {"chest": "91-96cm", "height": "165-175cm"}},
        "tags": ["ao-boi-tay-dai", "rashguard", "chong-nang", "do-boi-nu"],
        "variants": [
            {"id": 18, "size": 2, "color": 3, "sku": "SWIM-W03-NVY-S", "stock": 14, "val": 4200000.0, "img": "/static/images/swim-w03-rashguard.jpg"},
            {"id": 19, "size": 3, "color": 3, "sku": "SWIM-W03-NVY-M", "stock": 18, "val": 5400000.0, "img": "/static/images/swim-w03-rashguard.jpg"},
            {"id": 20, "size": 4, "color": 3, "sku": "SWIM-W03-NVY-L", "stock": 8, "val": 2400000.0, "img": "/static/images/swim-w03-rashguard.jpg"}, # Variant 20 for concurrency test!
        ]
    },
    {
        "id": 8, "cat": 9, "line": 3, "code": "SWIM-K01", "slug": "bo-do-boi-be-gai-cau-vong-soobin-kids",
        "name": "Bộ Đồ Bơi Bé Gái Cầu Vồng Soobin Kids Đáng Yêu", "price": 290000.0,
        "aud": "Trẻ em", "skill": "Mới tập bơi",
        "desc": "Đồ bơi 1 mảnh dành cho bé gái với họa tiết cầu vồng và hồng hạc rực rỡ, chất vải mềm mại không gây ngứa hay kích ứng làn da nhạy cảm.",
        "care": "Giặt riêng bằng nước lạnh.",
        "specs": {"safety": "Không chứa formaldehyt, viền may êm ái", "fabric": "Co giãn 4 chiều mềm mịn"},
        "size_chart": {"XS": {"age": "2-3 tuổi", "weight": "11-15kg"}, "S": {"age": "4-5 tuổi", "weight": "16-20kg"}, "M": {"age": "6-7 tuổi", "weight": "21-26kg"}},
        "tags": ["do-boi-tre-em", "be-gai", "cau-vong"],
        "variants": [
            {"id": 21, "size": 1, "color": 4, "sku": "SWIM-K01-COR-XS", "stock": 16, "val": 2400000.0, "img": "/static/images/swim-k01-girl.jpg"},
            {"id": 22, "size": 2, "color": 4, "sku": "SWIM-K01-COR-S", "stock": 25, "val": 3750000.0, "img": "/static/images/swim-k01-girl.jpg"},
            {"id": 23, "size": 3, "color": 4, "sku": "SWIM-K01-COR-M", "stock": 12, "val": 1800000.0, "img": "/static/images/swim-k01-girl.jpg"},
        ]
    },
    {
        "id": 9, "cat": 11, "line": 4, "code": "SWIM-ACC03", "slug": "tui-chong-nuoc-di-bien-soobin-dry-bag-20l",
        "name": "Túi Chống Nước Đa Năng Đi Biển Soobin Dry Bag 20L", "price": 260000.0,
        "aud": "Unisex", "skill": "Nghỉ dưỡng",
        "desc": "Túi khô chống nước tuyệt đối 20L chuyên dụng đi bơi, đi biển, chèo SUP hoặc lướt sóng, bảo vệ điện thoại ví tiền an toàn 100%.",
        "care": "Lau khô sau khi sử dụng, tránh vật nhọn đâm thủng.",
        "specs": {"capacity": "20 Lít", "waterproof": "IPX6 chống ngập nước", "strap": "Có quai đeo vai tháo rời"},
        "size_chart": {"FREESIZE": {"dimensions": "Đường kính 24cm, cao 60cm khi mở"}},
        "tags": ["tui-chong-nuoc", "dry-bag", "phu-kien-bien"],
        "variants": [
            {"id": 24, "size": 6, "color": 5, "sku": "SWIM-ACC03-CYA-FS", "stock": 30, "val": 4200000.0, "img": "/static/images/swim-acc03-drybag.jpg"}
        ]
    },
    {
        "id": 10, "cat": 6, "line": 1, "code": "SWIM-W04", "slug": "ao-tam-the-thao-soobin-active-dynamic",
        "name": "Bộ Áo Tắm Liền Thân Thể Thao Soobin Active Dynamic", "price": 490000.0,
        "aud": "Nữ", "skill": "Bơi lội thể thao",
        "desc": "Dòng áo tắm thể thao chuyên sâu với đường cắt khí động học ôm sát cơ thể, giảm lực cản của nước, dây đai lưng chéo chữ X chắc chắn.",
        "care": "Không giặt với chất làm mềm vải.",
        "specs": {"chlorine_resistant": "Kháng Clo gấp 10 lần vải thông thường", "support": "Lớp lót ngực nâng đỡ thể thao"},
        "size_chart": {"S": {"chest": "78-83cm"}, "M": {"chest": "84-89cm"}, "L": {"chest": "90-95cm"}},
        "tags": ["do-boi-the-thao", "lien-than", "nu"],
        "variants": [
            {"id": 25, "size": 2, "color": 1, "sku": "SWIM-W04-BLK-S", "stock": 20, "val": 4800000.0, "img": "/static/images/swim-w04-active.jpg"},
            {"id": 26, "size": 3, "color": 1, "sku": "SWIM-W04-BLK-M", "stock": 24, "val": 5760000.0, "img": "/static/images/swim-w04-active.jpg"},
            {"id": 27, "size": 4, "color": 1, "sku": "SWIM-W04-BLK-L", "stock": 10, "val": 2400000.0, "img": "/static/images/swim-w04-active.jpg"},
        ]
    },
    {
        "id": 11, "cat": 7, "line": 1, "code": "SWIM-M03", "slug": "quan-boi-nam-dai-ngang-goi-soobin-racing-pro",
        "name": "Quần Bơi Nam Dài Ngang Gối Soobin Racing Pro", "price": 380000.0,
        "aud": "Nam", "skill": "Chuyên nghiệp",
        "desc": "Quần bơi jammer dài ngang gối đạt chuẩn thi đấu, hỗ trợ nâng đỡ cơ bắp đùi, chống mỏi cơ khi bơi cự ly dài.",
        "care": "Tráng lại nước máy sau khi bơi hồ.",
        "specs": {"fabric": "Vải ép nhiệt không đường chỉ may viền đùi", "fit": "Compression fit ôm cơ"},
        "size_chart": {"M": {"waist": "74-80cm"}, "L": {"waist": "81-87cm"}, "XL": {"waist": "88-94cm"}},
        "tags": ["quan-boi-nam", "thi-dau", "jammer"],
        "variants": [
            {"id": 28, "size": 3, "color": 1, "sku": "SWIM-M03-BLK-M", "stock": 15, "val": 3000000.0, "img": "/static/images/swim-m03-racing.jpg"},
            {"id": 29, "size": 4, "color": 1, "sku": "SWIM-M03-BLK-L", "stock": 20, "val": 4000000.0, "img": "/static/images/swim-m03-racing.jpg"},
            {"id": 30, "size": 5, "color": 1, "sku": "SWIM-M03-BLK-XL", "stock": 8, "val": 1600000.0, "img": "/static/images/swim-m03-racing.jpg"},
        ]
    },
    {
        "id": 12, "cat": 11, "line": 1, "code": "SWIM-ACC04", "slug": "chan-vit-tap-boi-chuyen-dung-soobin-power-fins",
        "name": "Chân Vịt Tập Bơi Chuyên Dụng Soobin Power Fins", "price": 340000.0,
        "aud": "Unisex", "skill": "Chuyên nghiệp",
        "desc": "Chân vịt ngắn làm từ cao su tự nhiên cao cấp giúp tăng cường lực đạp chân và hoàn thiện kỹ thuật bơi sải, bơi bướm.",
        "care": "Rửa sạch cát biển sau khi tập luyện.",
        "specs": {"blade": "Lưỡi ngắn trợ lực linh hoạt", "foot_pocket": "Khoang chân cao su êm ái"},
        "size_chart": {"S": {"size": "36-38"}, "M": {"size": "39-41"}, "L": {"size": "42-44"}},
        "tags": ["chan-vit", "tap-boi", "phu-kien"],
        "variants": [
            {"id": 31, "size": 2, "color": 5, "sku": "SWIM-ACC04-CYA-S", "stock": 15, "val": 2700000.0, "img": "/static/images/swim-acc04-fins.jpg"},
            {"id": 32, "size": 3, "color": 5, "sku": "SWIM-ACC04-CYA-M", "stock": 18, "val": 3240000.0, "img": "/static/images/swim-acc04-fins.jpg"},
        ]
    }
]

# Generators for Products 13 to 100
# Categories:
# 5: Bikini 2 Mảnh (aud: Nữ)
# 6: Áo tắm 1 Mảnh Liền Thân (aud: Nữ)
# 7: Quần bơi thể thao nam (aud: Nam)
# 8: Quần bơi Boxer thời trang (aud: Nam)
# 9: Đồ bơi bé gái (aud: Trẻ em)
# 10: Kính bơi & Mũ bơi (aud: Unisex)
# 11: Túi chống nước & Dụng cụ (aud: Unisex)

women_bikini_templates = [
    ("Bộ Bikini 2 Mảnh Cúp Ngực Soobin Vintage Polka", "bikini-2-manh-cup-nguc-soobin-vintage-polka", 460000, "Vải dệt họa tiết chấm bi cổ điển, cúp ngực có gọng tôn dáng gợi cảm.", "/static/images/swim-w02-coral.jpg"),
    ("Bộ Bikini 2 Mảnh Buộc Dây Cổ Điển Soobin Sunset", "bikini-2-manh-buoc-day-soobin-sunset", 420000, "Bikini tam giác dây buộc cổ linh hoạt, sắc cam hoàng hôn tôn làn da rám nắng.", "/static/images/swim-w02-coral.jpg"),
    ("Bộ Bikini Cạp Cao Xếp Nếp Soobin Retro Glow", "bikini-cap-cao-xep-nep-soobin-retro-glow", 490000, "Thiết kế quần cạp cao giấu bụng tinh tế, chất liệu gân tăm co giãn cao cấp.", "/static/images/swim-w02-coral.jpg"),
    ("Bikini Hai Mảnh Tay Phồng Nữ Tính Soobin Romantic", "bikini-hai-manh-tay-phong-soobin-romantic", 510000, "Thiết kế tay bồng tiểu thư điệu đà, dễ dàng phối đồ dạo phố biển du lịch.", "/static/images/swim-w02-coral.jpg"),
    ("Bộ Bikini Thể Thao Croptop Soobin Active Wave", "bikini-the-thao-croptop-soobin-active-wave", 470000, "Dáng áo croptop thể thao năng động, nâng đỡ chắc chắn cho các hoạt động chèo SUP.", "/static/images/swim-w04-active.jpg"),
    ("Bikini 2 Mảnh Cắt Xẻ Gợi Cảm Soobin Cutout Chic", "bikini-2-manh-cat-xe-soobin-cutout-chic", 530000, "Đường cắt xẻ eo táo bạo khoe trọn đường cong quyến rũ dưới nắng biển.", "/static/images/swim-w02-coral.jpg"),
    ("Bộ Bikini Gọng Nâng Ngực Soobin PushUp Glamour", "bikini-gong-nang-nguc-soobin-pushup-glamour", 540000, "Cúp ngực nâng đẩy định hình tự nhiên, quai vai bản vừa êm ái chống hằn da.", "/static/images/swim-w02-coral.jpg"),
    ("Bikini 2 Mảnh Nhún Bèo Phong Cách Pháp Soobin Riviera", "bikini-2-manh-nhun-beo-soobin-riviera", 480000, "Chi tiết nhún bèo mềm mại phong cách bờ biển Pháp lãng mạn.", "/static/images/swim-w02-coral.jpg"),
]

women_onepiece_templates = [
    ("Áo Tắm 1 Mảnh Cổ V Sâu Thanh Lịch Soobin Plunge Luxe", "ao-tam-1-manh-co-v-sau-soobin-plunge-luxe", 550000, "Đường xẻ cổ chữ V sâu quyến rũ kết hợp đai eo bản to thon gọn vòng 2.", "/static/images/swim-w01-black.jpg"),
    ("Áo Tắm 1 Mảnh Liền Thân Dây Chéo Lưng Soobin CrossBack", "ao-tam-1-manh-day-cheo-lung-soobin-crossback", 520000, "Dây lưng đan chéo thanh mảnh khoe trọn lưng trần thon thả, vải kháng clo cao cấp.", "/static/images/swim-w01-navy.jpg"),
    ("Áo Bơi 1 Mảnh Khóa Kéo Thể Thao Soobin Pro Zip", "ao-boi-1-manh-khoa-keo-the-thao-soobin-pro-zip", 580000, "Thiết kế thể thao khỏe khoắn với khóa kéo trước ngực, vải UPF50+ kháng tia cực tím.", "/static/images/swim-w04-active.jpg"),
    ("Áo Tắm 1 Mảnh Phối Lưới Xuyên Thấu Soobin Sheer Elegance", "ao-tam-1-manh-phoi-luoi-soobin-sheer-elegance", 590000, "Các dải lưới vi tính cao cấp tạo điểm nhấn thị giác thon gọn cơ thể.", "/static/images/swim-w01-black.jpg"),
    ("Áo Bơi Nữ Tay Dài Chống Nắng Lướt Sóng Soobin Surf Pro", "ao-boi-nu-tay-dai-chong-nang-soobin-surf-pro", 620000, "Chống nắng UPF 50+, co giãn 4 chiều mềm mịn hỗ trợ lướt sóng và lặn ngắm san hô.", "/static/images/swim-w03-rashguard.jpg"),
    ("Áo Tắm Monokini Khoét Eo Tôn Dáng Soobin Cutout Goddess", "ao-tam-monokini-khoet-eo-soobin-cutout-goddess", 540000, "Thiết kế khoét eo điêu khắc đường cong đồng hồ cát hoàn hảo.", "/static/images/swim-w01-navy.jpg"),
    ("Áo Tắm 1 Mảnh Lệch Vai Sang Trọng Soobin One Shoulder", "ao-tam-1-manh-lech-vai-sang-trong-soobin-one-shoulder", 560000, "Thiết kế một bên vai thời thượng tôn vinh bờ vai thon và xương quai xanh.", "/static/images/swim-w01-black.jpg"),
    ("Áo Tắm Liền Thân Xếp Ly Che Khuyết Điểm Soobin Ruched Slim", "ao-tam-lien-than-xep-ly-soobin-ruched-slim", 530000, "Kỹ thuật xếp ly ngang vùng bụng giúp che giấu khuyết điểm hoàn hảo cho phái đẹp.", "/static/images/swim-w01-navy.jpg"),
]

men_sports_templates = [
    ("Quần Bơi Nam Dáng Brief Tam Giác Soobin Speed Brief", "quan-boi-nam-dang-brief-soobin-speed-brief", 290000, "Quần bơi tam giác ôm gọn lướt nước nhẹ nhàng, dây rút thắt lưng chắc chắn.", "/static/images/swim-m01-black.jpg"),
    ("Quần Bơi Nam Dáng Trunk Ngắn Thể Thao Soobin Aqua Trunk", "quan-boi-nam-dang-trunk-ngan-soobin-aqua-trunk", 330000, "Thiết kế dáng đùi ngắn thể thao năng động, vải kháng clo mau khô.", "/static/images/swim-m01-black.jpg"),
    ("Quần Bơi Nam Jammer Ép Cơ Chống Mỏi Soobin Compression", "quan-boi-nam-jammer-ep-co-soobin-compression", 410000, "Công nghệ ép cơ hydrodynamic nâng đỡ cơ bắp đùi, tối ưu tốc độ chặng dài.", "/static/images/swim-m03-racing.jpg"),
    ("Quần Bơi Nam Thi Đấu Sợi Carbon Soobin Carbon Core", "quan-boi-nam-thi-dau-soobin-carbon-core", 450000, "Vải dệt tích hợp sợi chống ma sát, đạt chuẩn tập luyện bơi lội đỉnh cao.", "/static/images/swim-m03-racing.jpg"),
    ("Quần Bơi Thể Thao Nam Phối Sọc Neon Soobin Neon Sprint", "quan-boi-the-thao-nam-phoi-soc-neon-soobin-neon-sprint", 340000, "Dải viền phản quang thể thao trẻ trung, đường may êm ái chống ma sát đùi.", "/static/images/swim-m01-black.jpg"),
]

men_boxer_templates = [
    ("Quần Short Bơi Nam Đi Biển Họa Tiết Tropical Soobin Palms", "quan-short-boi-nam-soobin-palms", 310000, "Họa tiết cành dừa nhiệt đới trẻ trung, vải mau khô tích hợp túi sau tiện ích.", "/static/images/swim-m02-cyan.jpg"),
    ("Quần Bơi Boxer Nam Thể Thao Phối Màu Soobin Duo Color", "quan-boi-boxer-nam-soobin-duo-color", 320000, "Thiết kế phối 2 khối màu cá tính, lót lưới mềm mại thoáng khí bên trong.", "/static/images/swim-m02-cyan.jpg"),
    ("Quần Bơi Đi Biển Nam Lưng Thun Dây Rút Soobin Island Chill", "quan-boi-di-bien-nam-lung-thun-soobin-island-chill", 330000, "Dáng quần vừa vặn, lưng thun co giãn thoải mái cho ngày dài dạo biển và bơi lội.", "/static/images/swim-m02-cyan.jpg"),
    ("Quần Short Đi Biển Nam Mau Khô Chống Nắng Soobin SunShield", "quan-short-di-bien-nam-mau-kho-soobin-sunshield", 350000, "Chất liệu microfiber chống thấm bề mặt, chống bám cát và mau khô trong 10 phút.", "/static/images/swim-m02-cyan.jpg"),
]

kids_templates = [
    ("Bộ Đồ Bơi Bé Gái Hồng Hạc Dễ Thương Soobin Pink Flamingo", "bo-do-boi-be-gai-hong-hac-soobin-pink-flamingo", 280000, "Họa tiết hồng hạc nữ tính, tay áo nhún bèo xếp tầng xinh xắn.", "/static/images/swim-k01-girl.jpg"),
    ("Áo Bơi Chống Nắng Bé Gái Tay Dài UPF 50+ Soobin Mini SunSafe", "ao-boi-chong-nang-be-gai-soobin-mini-sunsafe", 320000, "Bảo vệ làn da mỏng manh của bé khỏi 98% tia tử ngoại khi đi biển.", "/static/images/swim-k01-girl.jpg"),
    ("Đồ Bơi Bé Gái Nàng Tiên Cá Lấp Lánh Soobin Mermaid Dream", "do-boi-be-gai-nang-tien-ca-soobin-mermaid-dream", 295000, "Họa tiết vảy cá tiên ánh nhũ lung linh bé nào cũng yêu thích.", "/static/images/swim-k01-girl.jpg"),
    ("Quần Bơi Bé Trai Họa Tiết Cá Mập Năng Động Soobin Shark Attack", "quan-boi-be-trai-hoa-tiet-ca-map-soobin-shark-attack", 260000, "Họa tiết cá mập ngộ nghĩnh, lưng thun co giãn êm ái không cấn bụng bé.", "/static/images/swim-m02-cyan.jpg"),
    ("Bộ Bơi Bé Trai Liền Thân Chống Lạnh Hồ Bơi Soobin Polar Bear", "bo-boi-be-trai-lien-than-chong-lanh-soobin-polar-bear", 340000, "Chất vải giữ nhiệt hỗ trợ bé tập bơi hồ nước ấm hoặc mùa lạnh.", "/static/images/swim-w03-rashguard.jpg"),
    ("Bộ Đồ Bơi Bé Gái Chấm Bi Vàng Rực Rỡ Soobin Sunny Girl", "do-boi-be-gai-cham-bi-vang-soobin-sunny-girl", 270000, "Gam màu vàng nắng hè tươi sáng kèm nơ cài đáng yêu.", "/static/images/swim-k01-girl.jpg"),
]

accessories_templates = [
    ("Kính Bơi Thi Đấu Tráng Gương Chống UV Soobin Mirror Racing", "kinh-boi-thi-dau-trang-guong-soobin-mirror-racing", 280000, "Tròng tráng gương bạc chống chói lóa ngoài trời, đệm mắt silicone êm ái.", "/static/images/swim-acc01.jpg"),
    ("Kính Bơi Cận Thị Góc Nhìn Rộng Soobin Optical Vision (-2.0 đến -6.0)", "kinh-boi-can-thi-goc-nhin-rong-soobin-optical-vision", 320000, "Kính bơi độ cận quang học chuẩn xác, tráng nano chống sương mờ trong nước.", "/static/images/swim-acc01.jpg"),
    ("Kính Bơi Trẻ Em Chống Nước Chống Mờ Soobin Junior Goggles", "kinh-boi-tre-em-chong-nuoc-soobin-junior-goggles", 180000, "Thiết kế vành mắt mềm mại ôm khít khuôn mặt bé, không để nước tràn vào mắt.", "/static/images/swim-acc01.jpg"),
    ("Mũ Bơi Silicone Bảo Vệ Tóc Dày Soobin Pro Long Hair", "mu-boi-silicone-bao-ve-toc-day-soobin-pro-long-hair", 140000, "Khoang chứa tóc phía sau rộng rãi, không kéo đứt hay gãy rụng tóc nữ.", "/static/images/swim-acc02.jpg"),
    ("Mũ Bơi Vải Dệt Co Giãn Thoáng Khí Soobin Fabric Cap", "mu-boi-vai-det-co-gian-soobin-fabric-cap", 95000, "Chất vải thun co giãn không gây cảm giác bó siết đầu cho người mới tập bơi.", "/static/images/swim-acc02.jpg"),
    ("Túi Khô Chống Nước Đi Biển Siêu Nhẹ 10L Soobin Dry 10L", "tui-kho-chong-nuoc-10l-soobin-dry-10l", 190000, "Dung tích 10L nhỏ gọn vừa vặn để điện thoại, khăn tắm, kính bơi khi chèo SUP.", "/static/images/swim-acc03-drybag.jpg"),
    ("Túi Chống Nước Thể Thao Biển Siêu Lớn 30L Soobin Dry Expedition", "tui-chong-nuoc-30l-soobin-dry-expedition", 320000, "Túi 30L chống ngập nước chuyên dụng cho các chuyến phượt biển và lặn sâu.", "/static/images/swim-acc03-drybag.jpg"),
    ("Bộ Kẹp Mũi & Nút Tai Silicone Chống Tràn Nước Soobin Ear Nose Pro", "bo-kep-mui-nut-tai-silicone-soobin-ear-nose-pro", 85000, "Silicone y tế cao cấp kháng khuẩn, ngăn ngừa viêm tai giữa khi tập bơi.", "/static/images/swim-acc01.jpg"),
    ("Phao Lưng Tập Bơi Thể Thao 4 Tầng Soobin Back Float", "phao-lung-tap-boi-4-tang-soobin-back-float", 160000, "Xốp EVA nén mật độ cao, 4 tầng phao có thể tháo rời tùy chỉnh độ nổi theo trình độ.", "/static/images/swim-acc04-fins.jpg"),
    ("Phao Tim Cầm Tay Tập Chân Soobin Kickboard Pro", "phao-tim-cam-tay-tap-chan-soobin-kickboard-pro", 150000, "Thiết kế khí động học bo tròn mép cầm giúp nâng cao sức mạnh cơ chân.", "/static/images/swim-acc04-fins.jpg"),
    ("Chân Vịt Lặn Biển Trợ Lực Tự Nhiên Soobin Marine Diver", "chan-vit-lan-bien-tro-luc-soobin-marine-diver", 420000, "Lưỡi chân vịt dài tạo lực đẩy cực mạnh cho môn lặn biển ngắm rạn san hô.", "/static/images/swim-acc04-fins.jpg"),
]

# Generate items up to 100
all_products = list(base_products)
current_prod_id = 13
current_var_id = 33

categories_pool = [
    (5, "Nữ", "Nghỉ dưỡng", women_bikini_templates, 2), # cat, aud, skill, pool, product_line
    (6, "Nữ", "Bơi lội thể thao", women_onepiece_templates, 1),
    (7, "Nam", "Chuyên nghiệp", men_sports_templates, 1),
    (8, "Nam", "Nghỉ dưỡng", men_boxer_templates, 2),
    (9, "Trẻ em", "Mới tập bơi", kids_templates, 3),
    (10, "Unisex", "Bơi lội thể thao", accessories_templates[:5], 1),
    (11, "Unisex", "Nghỉ dưỡng", accessories_templates[5:], 4),
]

while current_prod_id <= 100:
    for cat_id, aud, skill, pool, pline in categories_pool:
        if current_prod_id > 100:
            break
        tmpl_idx = (current_prod_id - 13) % len(pool)
        name, slug_prefix, base_price, desc, img_path = pool[tmpl_idx]
        
        # Unique code & slug
        code = f"SWIM-P{current_prod_id:03d}"
        slug = f"{slug_prefix}-{current_prod_id}"
        full_name = f"{name} (Series #{current_prod_id})"

        # Specs and Size chart based on category
        if cat_id in (5, 6):
            specs = {"fabric": "82% Polyamide, 18% Elastane kháng Clo", "padding": "Đệm mút tháo rời", "uv_protection": "UPF 50+"}
            size_chart = {"S": {"chest": "80-84cm", "waist": "62-66cm"}, "M": {"chest": "85-89cm", "waist": "67-71cm"}, "L": {"chest": "90-94cm", "waist": "72-76cm"}}
            tags = ["do-boi-nu", "thoi-trang", "chong-nang"]
            var_specs = [(2, 1, "BLK-S"), (3, 1, "BLK-M"), (4, 1, "BLK-L")]
        elif cat_id in (7, 8):
            specs = {"fabric": "Polyamide QuickDry kháng Clo", "waist": "Dây rút đàn hồi"}
            size_chart = {"M": {"waist": "72-78cm"}, "L": {"waist": "79-85cm"}, "XL": {"waist": "86-92cm"}}
            tags = ["quan-boi-nam", "the-thao", "mau-kho"]
            var_specs = [(3, 1, "BLK-M"), (4, 1, "BLK-L"), (5, 3, "NVY-XL")]
        elif cat_id == 9:
            specs = {"fabric": "Vải dệt an toàn trẻ em không kích ứng", "stretch": "Co giãn 4 chiều"}
            size_chart = {"XS": {"age": "2-3 tuổi"}, "S": {"age": "4-5 tuổi"}, "M": {"age": "6-7 tuổi"}}
            tags = ["do-boi-tre-em", "an-toan", "be-gai"]
            var_specs = [(1, 4, "COR-XS"), (2, 4, "COR-S"), (3, 4, "COR-M")]
        else: # Accessories
            specs = {"material": "Silicone / Nhựa Polycarbonate y tế", "standard": "Chuẩn thi đấu thể thao"}
            size_chart = {"FREESIZE": {"info": "Dễ dàng tùy chỉnh theo kích cỡ đầu & mắt"}}
            tags = ["phu-kien-boi", "chuyen-dung"]
            var_specs = [(6, 6, "NOCOL-FS")]

        prod_variants = []
        for s_id, c_id, sku_suffix in var_specs:
            sku = f"{code}-{sku_suffix}"
            stock = random.randint(15, 60)
            cost = base_price * 0.5
            val = round(stock * cost, 2)
            prod_variants.append({
                "id": current_var_id,
                "size": s_id,
                "color": c_id,
                "sku": sku,
                "stock": stock,
                "val": val,
                "img": img_path
            })
            current_var_id += 1

        all_products.append({
            "id": current_prod_id,
            "cat": cat_id,
            "line": pline,
            "code": code,
            "slug": slug,
            "name": full_name,
            "price": float(base_price),
            "aud": aud,
            "skill": skill,
            "desc": desc,
            "care": "Giặt tay nhẹ nhàng bằng nước mát, phơi trong bóng râm.",
            "specs": specs,
            "size_chart": size_chart,
            "tags": tags,
            "variants": prod_variants
        })
        current_prod_id += 1

print(f"[*] Generated total {len(all_products)} products with {current_var_id - 1} variants.")

# Now build the full SQL script
sql_lines = []
sql_lines.append("-- =============================================================================")
sql_lines.append("-- Soobin Swimwear - Rich Seed Data SQL (100 Products, Complete Roles & Portals)")
sql_lines.append("-- =============================================================================\n")

# 1. ROLES & PERMISSIONS
sql_lines.append("""-- 1. ROLES & PERMISSIONS
INSERT INTO user_role (id, code, name, is_system, is_active) VALUES
(1, 'ADMIN', 'Quản trị viên hệ thống', TRUE, TRUE),
(2, 'MANAGER', 'Quản lý cửa hàng', TRUE, TRUE),
(3, 'CUSTOMER', 'Khách hàng', TRUE, TRUE),
(4, 'WAREHOUSE', 'Quản lý kho & Thủ kho', TRUE, TRUE),
(5, 'SALES', 'Nhân viên bán hàng & CSKH', TRUE, TRUE)
ON CONFLICT (code) DO NOTHING;

INSERT INTO user_permission (id, code, description) VALUES
(1, 'users.manage', 'Quản lý tài khoản người dùng và khóa tài khoản'),
(2, 'roles.manage', 'Quản lý phân quyền và vai trò tùy chỉnh'),
(3, 'catalog.manage', 'Thêm sửa xóa thông tin sản phẩm và danh mục'),
(4, 'inventory.manage', 'Tạo và xác nhận phiếu nhập hàng, quản lý tồn kho'),
(5, 'orders.manage', 'Xác nhận xử lý đơn hàng và theo dõi vận chuyển'),
(6, 'refunds.manage', 'Quản lý và chuyển trạng thái hoàn tiền thủ công'),
(7, 'promotions.manage', 'Quản lý chương trình khuyến mãi và voucher'),
(8, 'reports.view', 'Xem dashboard thống kê doanh thu và lợi nhuận'),
(9, 'content.manage', 'Quản lý nội dung, banner, bài viết và kiểm duyệt')
ON CONFLICT (code) DO NOTHING;

INSERT INTO user_role_permission (role_id, permission_id) VALUES
(1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9),
(2, 3), (2, 5), (2, 6), (2, 7), (2, 8),
(4, 4), (4, 8),
(5, 3), (5, 5)
ON CONFLICT DO NOTHING;
""")

# 2. INITIAL USERS (Password: Password123@)
sql_lines.append("""-- 2. INITIAL USERS (Password: Password123@)
INSERT INTO user_account (id, role_id, email, phone, password_hash, full_name, email_verified_at, is_locked) VALUES
(1, 1, 'admin@soobin.vn', '0901234567', '$2b$12$POaRI843Nxn9YQgsLAjRkucEUchkLgiUyKygIQrEoh6Tv5y7dFo7C', 'Võ Hoài Nam (Admin Cấp Cao)', NOW(), FALSE),
(2, 2, 'manager@soobin.vn', '0902345678', '$2b$12$POaRI843Nxn9YQgsLAjRkucEUchkLgiUyKygIQrEoh6Tv5y7dFo7C', 'Lê Thu Trang (Quản Lý Kinh Doanh)', NOW(), FALSE),
(3, 4, 'warehouse@soobin.vn', '0903334444', '$2b$12$POaRI843Nxn9YQgsLAjRkucEUchkLgiUyKygIQrEoh6Tv5y7dFo7C', 'Phạm Quốc Huy (Thủ Kho Chính)', NOW(), FALSE),
(4, 5, 'sales@soobin.vn', '0905556666', '$2b$12$POaRI843Nxn9YQgsLAjRkucEUchkLgiUyKygIQrEoh6Tv5y7dFo7C', 'Vũ Hoàng Yến (Tư Vấn Bán Hàng)', NOW(), FALSE),
(5, 3, 'customer@soobin.vn', '0903456789', '$2b$12$POaRI843Nxn9YQgsLAjRkucEUchkLgiUyKygIQrEoh6Tv5y7dFo7C', 'Nguyễn Minh Anh (Khách Hàng)', NOW(), FALSE),
(6, 3, 'customer2@soobin.vn', '0904567890', '$2b$12$POaRI843Nxn9YQgsLAjRkucEUchkLgiUyKygIQrEoh6Tv5y7dFo7C', 'Trần Bảo Ngọc (Chưa verify email)', NULL, FALSE),
(7, 3, 'hoang.nam@gmail.com', '0912345678', '$2b$12$POaRI843Nxn9YQgsLAjRkucEUchkLgiUyKygIQrEoh6Tv5y7dFo7C', 'Hoàng Nhật Nam', NOW(), FALSE),
(8, 3, 'thuy.tien@gmail.com', '0923456789', '$2b$12$POaRI843Nxn9YQgsLAjRkucEUchkLgiUyKygIQrEoh6Tv5y7dFo7C', 'Đặng Thủy Tiên', NOW(), FALSE)
ON CONFLICT (email) DO NOTHING;

INSERT INTO user_address (account_id, recipient_name, recipient_phone, address_line, province_code, district_code, ward_code, is_default) VALUES
(5, 'Nguyễn Minh Anh', '0903456789', 'Số 123 Đường Nguyễn Huệ, Phường Bến Nghé, Quận 1, TP.HCM', '79', '760', '26734', TRUE),
(7, 'Hoàng Nhật Nam', '0912345678', 'Tòa Landmark 81, 720A Điện Biên Phủ, Phường 22, Bình Thạnh, TP.HCM', '79', '765', '26880', TRUE),
(8, 'Đặng Thủy Tiên', '0923456789', '45 Hoàng Diệu, Phường 5, Quận 4, TP.HCM', '79', '763', '26790', TRUE)
ON CONFLICT DO NOTHING;
""")

# 3. SIZES, COLORS, MATERIALS, PRODUCT LINES, CATEGORIES
sql_lines.append("""-- 3. SIZES, COLORS, MATERIALS, PRODUCT LINES, CATEGORIES
INSERT INTO production_size (id, code, name, sort_order) VALUES
(1, 'XS', 'Size XS', 1),
(2, 'S', 'Size S', 2),
(3, 'M', 'Size M', 3),
(4, 'L', 'Size L', 4),
(5, 'XL', 'Size XL', 5),
(6, 'FREESIZE', 'Freesize linh hoạt', 6)
ON CONFLICT (code) DO NOTHING;

INSERT INTO production_color (id, code, name, hex_code) VALUES
(1, 'BLK', 'Đen Quyền Lực', '#0F172A'),
(2, 'WHT', 'Trắng Tinh Khôi', '#FFFFFF'),
(3, 'NVY', 'Xanh Navy Đại Dương', '#0369A1'),
(4, 'COR', 'Cam San Hô', '#F97316'),
(5, 'CYAN', 'Xanh Ngọc Aqua', '#06B6D4'),
(6, 'NO_COLOR', 'Không phân màu', '#9CA3AF'),
(7, 'YELLOW', 'Vàng Nắng Hè', '#EAB308')
ON CONFLICT (code) DO NOTHING;

INSERT INTO production_material (id, code, name) VALUES
(1, 'POLY_ELASTANE', '82% Polyamide, 18% Elastane co giãn 4 chiều kháng Clo'),
(2, 'NEOPRENE', 'Vải Neoprene cách nhiệt chống lạnh cao cấp'),
(3, 'SILICONE', 'Silicone y tế dẻo dai chống tràn nước'),
(4, 'UPF50_NYLON', 'Vải dệt mật độ cao chống nắng tuyệt đối UPF 50+')
ON CONFLICT (code) DO NOTHING;

INSERT INTO production_product_line (id, code, name, is_active) VALUES
(1, 'LINE_PRO', 'Soobin Pro Swim - Dòng thể thao bơi lội chuyên nghiệp', TRUE),
(2, 'LINE_RESORT', 'Soobin Resort - Dòng áo tắm nghỉ dưỡng & du lịch', TRUE),
(3, 'LINE_KIDS', 'Soobin Junior - Dòng đồ bơi an toàn cho trẻ em', TRUE),
(4, 'LINE_ACTIVE', 'Soobin Active - Dòng đồ bơi vận động ngoài trời', TRUE)
ON CONFLICT (code) DO NOTHING;

INSERT INTO production_category (id, parent_id, name, slug, sort_order, is_active) VALUES
(1, NULL, 'Đồ bơi nữ', 'do-boi-nu', 1, TRUE),
(2, NULL, 'Đồ bơi nam', 'do-boi-nam', 2, TRUE),
(3, NULL, 'Đồ bơi trẻ em', 'do-boi-tre-em', 3, TRUE),
(4, NULL, 'Phụ kiện bơi lội', 'phu-kien-boi-loi', 4, TRUE),
(5, 1, 'Bikini 2 Mảnh', 'bikini-2-manh', 1, TRUE),
(6, 1, 'Áo tắm 1 Mảnh Liền Thân', 'ao-tam-1-manh', 2, TRUE),
(7, 2, 'Quần bơi thể thao nam', 'quan-boi-the-thao-nam', 1, TRUE),
(8, 2, 'Quần bơi Boxer thời trang', 'quan-boi-boxer-nam', 2, TRUE),
(9, 3, 'Đồ bơi bé gái', 'do-boi-be-gai', 1, TRUE),
(10, 4, 'Kính bơi & Mũ bơi', 'kinh-mu-boi', 1, TRUE),
(11, 4, 'Túi chống nước & Dụng cụ', 'tui-dung-cu', 2, TRUE)
ON CONFLICT (slug) DO NOTHING;

-- 4. SUPPLIERS
INSERT INTO production_supplier (id, code, name, phone, email, address, is_active) VALUES
(1, 'SUP-HN-01', 'Tổng Công Ty Cổ Phần May Mặc Thể Thao Hà Nội', '0243888999', 'contact@hanoisportwear.vn', 'KCN Đài Tư, Long Biên, Hà Nội', TRUE),
(2, 'SUP-SG-02', 'Công Ty TNHH Sản Xuất Đồ Bơi & Phụ Kiện Sài Gòn', '0283999888', 'info@saigonswim.com', 'Khu Chế Xuất Tân Thuận, Quận 7, TP.HCM', TRUE),
(3, 'SUP-DN-03', 'Công Ty Dệt May Biển Xanh Đà Nẵng', '0236377788', 'sales@bienxanhswim.com', 'KCN Hòa Khánh, Liên Chiểu, Đà Nẵng', TRUE)
ON CONFLICT (code) DO NOTHING;
""")

# 5. PRODUCTS (100 Products)
sql_lines.append("-- 5. RICH CATALOG: 100 PRODUCTS")
sql_lines.append("INSERT INTO production_product (id, category_id, product_line_id, code, slug, name, base_price, target_audience, skill_level, description, care_instructions, specifications, size_chart, tags, status) VALUES")

prod_val_strs = []
for p in all_products:
    specs_json = json.dumps(p["specs"], ensure_ascii=False).replace("'", "''")
    size_json = json.dumps(p["size_chart"], ensure_ascii=False).replace("'", "''")
    tags_str = "ARRAY[" + ", ".join([f"'{t}'" for t in p["tags"]]) + "]"
    desc_clean = p["desc"].replace("'", "''")
    care_clean = p["care"].replace("'", "''")
    name_clean = p["name"].replace("'", "''")
    s = f"({p['id']}, {p['cat']}, {p['line']}, '{p['code']}', '{p['slug']}', '{name_clean}', {p['price']:.2f}, '{p['aud']}', '{p['skill']}', '{desc_clean}', '{care_clean}', '{specs_json}', '{size_json}', {tags_str}, 'Selling')"
    prod_val_strs.append(s)

sql_lines.append(",\n".join(prod_val_strs))
sql_lines.append("ON CONFLICT (code) DO NOTHING;\n")

# 6. VARIANTS
sql_lines.append("-- 6. VARIANTS FOR ALL 100 PRODUCTS")
sql_lines.append("INSERT INTO production_variant (id, product_id, size_id, color_id, sku, is_active) VALUES")
var_val_strs = []
for p in all_products:
    for v in p["variants"]:
        var_val_strs.append(f"({v['id']}, {p['id']}, {v['size']}, {v['color']}, '{v['sku']}', TRUE)")
sql_lines.append(",\n".join(var_val_strs))
sql_lines.append("ON CONFLICT (sku) DO NOTHING;\n")

# 7. PRODUCT IMAGES
sql_lines.append("-- 7. PRODUCT IMAGES")
sql_lines.append("INSERT INTO production_product_image (product_id, color_id, file_path, alt_text, sort_order) VALUES")
img_val_strs = []
for p in all_products:
    seen_imgs = set()
    sort_order = 1
    for v in p["variants"]:
        img_key = (v["color"], v["img"])
        if img_key not in seen_imgs:
            seen_imgs.add(img_key)
            alt = p['name'].replace("'", "''")
            img_val_strs.append(f"({p['id']}, {v['color']}, '{v['img']}', '{alt}', {sort_order})")
            sort_order += 1
sql_lines.append(",\n".join(img_val_strs))
sql_lines.append("ON CONFLICT DO NOTHING;\n")

# 8. INVENTORY FOR ALL VARIANTS
sql_lines.append("-- 8. INVENTORY FOR ALL VARIANTS")
sql_lines.append("INSERT INTO production_inventory (variant_id, available_quantity, inventory_value, low_stock_threshold) VALUES")
inv_val_strs = []
for p in all_products:
    for v in p["variants"]:
        inv_val_strs.append(f"({v['id']}, {v['stock']}, {v['val']:.2f}, 5)")
sql_lines.append(",\n".join(inv_val_strs))
sql_lines.append("""ON CONFLICT (variant_id) DO UPDATE SET
  available_quantity = EXCLUDED.available_quantity,
  inventory_value = EXCLUDED.inventory_value;
""")

# 9. GOODS RECEIPTS (CONFIRMED)
sql_lines.append("""-- 9. GOODS RECEIPTS (CONFIRMED)
INSERT INTO production_goods_receipt (id, code, supplier_id, confirmed_by, confirmed_at, supplier_snapshot, note) VALUES
(1, 'PN-2026-001', 1, 2, NOW(), '{"supplier_name": "Tổng Công Ty May Mặc Hà Nội", "code": "SUP-HN-01"}', 'Nhập lô hàng đồ bơi nữ Hè 2026 chính hãng'),
(2, 'PN-2026-002', 2, 2, NOW(), '{"supplier_name": "Công Ty Sản Xuất Đồ Bơi Sài Gòn", "code": "SUP-SG-02"}', 'Nhập lô phụ kiện kính bơi và mũ silicone'),
(3, 'PN-2026-003', 3, 2, NOW(), '{"supplier_name": "Công Ty Dệt May Biển Xanh Đà Nẵng", "code": "SUP-DN-03"}', 'Nhập bổ sung quần bơi nam Speed Pro và Boxer')
ON CONFLICT (code) DO NOTHING;

INSERT INTO production_goods_receipt_item (receipt_id, variant_id, quantity, unit_cost, variant_snapshot) VALUES
(1, 1, 50, 250000.00, '{"sku": "SWIM-W01-BLK-S", "size": "S", "color": "Đen"}'),
(1, 4, 50, 250000.00, '{"sku": "SWIM-W01-NVY-S", "size": "S", "color": "Xanh Navy"}'),
(1, 7, 50, 220000.00, '{"sku": "SWIM-W02-COR-S", "size": "S", "color": "Cam San Hô"}'),
(1, 18, 40, 300000.00, '{"sku": "SWIM-W03-NVY-S", "size": "S", "color": "Xanh Navy"}'),
(2, 16, 100, 110000.00, '{"sku": "SWIM-ACC01-BLK-FS", "size": "FREESIZE", "color": "Đen"}'),
(2, 17, 100, 60000.00, '{"sku": "SWIM-ACC02-NVY-FS", "size": "FREESIZE", "color": "Xanh Navy"}'),
(2, 24, 50, 140000.00, '{"sku": "SWIM-ACC03-CYA-FS", "size": "FREESIZE", "color": "Xanh Ngọc"}'),
(3, 9, 50, 180000.00, '{"sku": "SWIM-M01-BLK-M", "size": "M", "color": "Đen"}'),
(3, 14, 50, 160000.00, '{"sku": "SWIM-M02-CYA-M", "size": "M", "color": "Xanh Ngọc"}')
ON CONFLICT DO NOTHING;
""")

# 10. PROMOTIONS & VOUCHERS
sql_lines.append("""-- 10. PROMOTIONS & VOUCHERS
INSERT INTO production_promotion (id, code, name, promotion_type, discount_percent, minimum_order_amount, usage_limit, used_count, starts_at, ends_at, is_active) VALUES
(1, 'SUMMER30', 'Giảm 30% Áo Tắm Liền Thân', 'PRODUCT', 30.00, 0.00, 1000, 15, NOW() - INTERVAL '1 day', NOW() + INTERVAL '30 days', TRUE),
(2, 'ORDER10', 'Giảm 10% Hóa Đơn Từ 500K', 'ORDER', 10.00, 500000.00, 500, 24, NOW() - INTERVAL '1 day', NOW() + INTERVAL '30 days', TRUE),
(3, 'SOOBIN15', 'Voucher Chào Hè 15%', 'VOUCHER', 15.00, 300000.00, 200, 8, NOW() - INTERVAL '1 day', NOW() + INTERVAL '30 days', TRUE),
(4, 'OUTLET20', 'Giảm 20% Dòng Xả Kho Outlet', 'PRODUCT', 20.00, 0.00, 500, 5, NOW() - INTERVAL '1 day', NOW() + INTERVAL '30 days', TRUE)
ON CONFLICT (code) DO NOTHING;

INSERT INTO production_promotion_product (promotion_id, product_id) VALUES
(1, 1),
(4, 2),
(4, 7),
(4, 10)
ON CONFLICT DO NOTHING;
""")

# 11. SAMPLE ORDERS
sql_lines.append("""-- 11. SAMPLE ORDERS & TRACKING
INSERT INTO production_order (id, code, account_id, status, payment_method, selected_discount_type, subtotal, discount_amount, shipping_fee, total_amount, recipient_snapshot, store_snapshot, placed_at) VALUES
(1, 'ORD-2026-0001', 5, 'Đã giao', 'VietQR', 'ORDER', 520000.00, 50000.00, 30000.00, 500000.00, '{"name": "Nguyễn Minh Anh", "phone": "0903456789", "address": "Số 123 Nguyễn Huệ, Quận 1, TP.HCM"}', '{"store": "Soobin Swimwear Store", "tax_id": "0312345678"}', NOW() - INTERVAL '3 days'),
(2, 'ORD-2026-0002', 7, 'Đang vận chuyển', 'COD', 'VOUCHER', 480000.00, 72000.00, 30000.00, 438000.00, '{"name": "Hoàng Nhật Nam", "phone": "0912345678", "address": "Tòa Landmark 81, Bình Thạnh, TP.HCM"}', '{"store": "Soobin Swimwear Store"}', NOW() - INTERVAL '1 day'),
(3, 'ORD-2026-0003', 8, 'Chưa xử lý', 'VietQR', 'NONE', 350000.00, 0.00, 30000.00, 380000.00, '{"name": "Đặng Thủy Tiên", "phone": "0923456789", "address": "45 Hoàng Diệu, Quận 4, TP.HCM"}', '{"store": "Soobin Swimwear Store"}', NOW())
ON CONFLICT (code) DO NOTHING;

INSERT INTO production_order_item (order_id, variant_id, quantity, unit_price, unit_cost_snapshot, allocated_discount_amount, line_total, product_snapshot) VALUES
(1, 1, 1, 520000.00, 250000.00, 50000.00, 470000.00, '{"name": "Áo Tắm 1 Mảnh Liền Thân Soobin Elegance Khoét Lưng", "sku": "SWIM-W01-BLK-S", "size": "S", "color": "Đen"}'),
(2, 7, 1, 480000.00, 220000.00, 72000.00, 408000.00, '{"name": "Bộ Bikini 2 Mảnh Soobin Coral Beach Cạp Cao", "sku": "SWIM-W02-COR-S", "size": "S", "color": "Cam San Hô"}'),
(3, 9, 1, 350000.00, 180000.00, 0.00, 350000.00, '{"name": "Quần Bơi Nam Soobin Speed Pro Ôm Sát Chuyên Nghiệp", "sku": "SWIM-M01-BLK-M", "size": "M", "color": "Đen"}')
ON CONFLICT DO NOTHING;

INSERT INTO production_payment (order_id, method, status, expected_amount, received_amount, external_transaction_id, paid_at) VALUES
(1, 'VietQR', 'PAID', 500000.00, 500000.00, 'VQR-MB-99988811', NOW() - INTERVAL '3 days'),
(2, 'COD', 'PENDING', 438000.00, 0.00, NULL, NULL),
(3, 'VietQR', 'PAID', 380000.00, 380000.00, 'VQR-MB-99988822', NOW() - INTERVAL '2 hours')
ON CONFLICT (order_id) DO NOTHING;

INSERT INTO production_shipment (order_id, carrier, tracking_code, creation_status, delivery_status, shipping_fee_snapshot, carrier_request_key, delivered_at) VALUES
(1, 'GHTK', 'GHTK-SOOBIN-88991', 'CREATED', 'DELIVERED', 30000.00, 'REQ-SHIP-0001', NOW() - INTERVAL '1 day'),
(2, 'GHTK', 'GHTK-SOOBIN-88992', 'CREATED', 'IN_TRANSIT', 30000.00, 'REQ-SHIP-0002', NULL),
(3, 'GHTK', 'GHTK-SOOBIN-88993', 'CREATED', 'WAITING_FOR_PICKUP', 30000.00, 'REQ-SHIP-0003', NULL)
ON CONFLICT (order_id) DO NOTHING;

INSERT INTO production_invoice (order_id, code, issued_at, subtotal, discount_amount, shipping_fee, total_amount, customer_snapshot, store_snapshot) VALUES
(1, 'INV-2026-0001', NOW() - INTERVAL '1 day', 520000.00, 50000.00, 30000.00, 500000.00, '{"name": "Nguyễn Minh Anh", "phone": "0903456789"}', '{"store": "Soobin Swimwear"}')
ON CONFLICT (code) DO NOTHING;
""")

with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(sql_lines))

print(f"[+] Successfully wrote {output_path} with 100 products and full seed data!")
