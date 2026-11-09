"""
Customer Experience service — các tiện ích mua sắm cao cấp cho Storefront.

1. Hồ sơ size thông minh: lưu số đo (localStorage + bảng production_fit_profile nếu đã đăng nhập),
   tính size phù hợp cho từng sản phẩm từ `size_chart` của sản phẩm; thiếu số liệu thì dùng bảng
   size chuẩn theo đối tượng (Nữ / Nam / Trẻ em). Phụ kiện (Freesize) → không gợi ý size.
2. Thêm nhanh 1 chạm: danh sách size còn hàng (biến thể tồn nhiều nhất của mỗi size).
3. Bằng chứng xã hội thật: đơn hàng thật trong 7 ngày (ẩn danh: chỉ tên gọi + tỉnh/thành) và bộ đếm
   "đang xem" trong bộ nhớ (heartbeat + TTL) — không có số liệu giả.
4. Stylist chuyến đi: phối set từ catalog thật, chỉ lấy hàng còn tồn, tính giá sau giảm hiện hành.
5. Tìm kiếm bằng hình ảnh: trích bảng màu chủ đạo bằng Pillow, xếp hạng sản phẩm theo độ tương đồng
   bảng màu ảnh chính (cache theo đường dẫn ảnh + mtime để tự làm mới khi ảnh thay đổi).
6. Điểm danh nhận Vỏ Sò: chuỗi 7 ngày, cứ 3 Vỏ Sò = +1 lượt quay thưởng trong chu kỳ vòng quay hiện tại.
"""
import io
import math
import os
import re
import threading
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.entities import (
    ProductionCategory,
    ProductionDailyCheckin,
    ProductionFitProfile,
    ProductionOrder,
    ProductionOrderItem,
    ProductionProduct,
    ProductionVariant,
    UserAccount,
)
from app.services.catalog_service import CatalogService

VN_TZ = timezone(timedelta(hours=7))
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _plain(text: Any) -> str:
    """Lowercase + strip Vietnamese accents (đ → d) for keyword matching."""
    s = unicodedata.normalize("NFD", str(text or "")).replace("đ", "d").replace("Đ", "D")
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", s.lower()).strip()


# =============================================================================
# 1. FIT PROFILE & SIZE RECOMMENDATION
# =============================================================================
AUDIENCES = ("Nữ", "Nam", "Trẻ em")
SIZE_SEQUENCE = ["XS", "S", "M", "L", "XL", "XXL", "2XL", "3XL"]
ONE_SIZE_CODES = {"FREESIZE", "FREE", "ONESIZE"}

PROFILE_LIMITS = {
    "height_cm": (60.0, 220.0),
    "weight_kg": (10.0, 180.0),
    "bust_cm": (45.0, 170.0),
    "waist_cm": (35.0, 160.0),
    "hip_cm": (45.0, 180.0),
}
PROFILE_TO_DIM = {"bust_cm": "bust", "waist_cm": "waist", "hip_cm": "hip", "height_cm": "height", "weight_kg": "weight"}
DIM_WEIGHTS = {"bust": 1.0, "waist": 1.0, "hip": 0.8, "weight": 0.7, "height": 0.45}
DIM_ALIASES = {
    "bust": {"chest", "bust", "nguc", "vong nguc", "vong 1", "vong1"},
    "waist": {"waist", "eo", "vong eo", "vong 2", "vong2"},
    "hip": {"hip", "hips", "mong", "vong mong", "vong 3", "vong3"},
    "height": {"height", "cao", "chieu cao"},
    "weight": {"weight", "can nang", "nang", "can"},
    "age": {"age", "tuoi", "do tuoi"},
}

# Bảng size chuẩn (cm / kg) dùng khi sản phẩm không khai báo đủ số đo.
DEFAULT_CHARTS: Dict[str, Dict[str, Dict[str, Tuple[float, float]]]] = {
    "Nữ": {
        "XS": {"bust": (76, 80), "waist": (58, 62), "hip": (82, 86), "height": (145, 153), "weight": (38, 44)},
        "S": {"bust": (80, 84), "waist": (62, 66), "hip": (86, 90), "height": (150, 158), "weight": (43, 49)},
        "M": {"bust": (85, 89), "waist": (67, 71), "hip": (90, 94), "height": (155, 163), "weight": (48, 55)},
        "L": {"bust": (90, 94), "waist": (72, 76), "hip": (95, 99), "height": (158, 167), "weight": (54, 61)},
        "XL": {"bust": (95, 100), "waist": (77, 82), "hip": (100, 105), "height": (160, 170), "weight": (60, 68)},
    },
    "Nam": {
        "S": {"bust": (84, 89), "waist": (68, 73), "hip": (86, 91), "height": (158, 166), "weight": (50, 57)},
        "M": {"bust": (90, 95), "waist": (72, 78), "hip": (92, 97), "height": (164, 172), "weight": (56, 65)},
        "L": {"bust": (96, 101), "waist": (79, 85), "hip": (98, 103), "height": (170, 177), "weight": (65, 75)},
        "XL": {"bust": (102, 108), "waist": (86, 92), "hip": (104, 110), "height": (174, 183), "weight": (75, 86)},
    },
    "Trẻ em": {
        "XS": {"height": (85, 100), "weight": (12, 16), "age": (2, 3)},
        "S": {"height": (100, 112), "weight": (15, 20), "age": (4, 5)},
        "M": {"height": (112, 124), "weight": (19, 25), "age": (6, 7)},
        "L": {"height": (124, 136), "weight": (24, 31), "age": (8, 9)},
        "XL": {"height": (136, 148), "weight": (30, 38), "age": (10, 11)},
    },
}

_RANGE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:-|–|—|~|đến|to)\s*(\d+(?:[.,]\d+)?)")
_NUM_RE = re.compile(r"(\d+(?:[.,]\d+)?)")


def _size_rank(code: str) -> int:
    code = (code or "").upper()
    return SIZE_SEQUENCE.index(code) if code in SIZE_SEQUENCE else 50


def _parse_range(value: Any) -> Optional[Tuple[float, float]]:
    if isinstance(value, (int, float)):
        v = float(value)
        return (v - 2, v + 2)
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            lo, hi = float(value[0]), float(value[1])
            return (min(lo, hi), max(lo, hi))
        except (TypeError, ValueError):
            return None
    text = str(value or "")
    m = _RANGE_RE.search(text)
    if m:
        lo, hi = float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))
        return (min(lo, hi), max(lo, hi))
    m = _NUM_RE.search(text)
    if m:
        v = float(m.group(1).replace(",", "."))
        return (v - 2, v + 2)
    return None


def _dim_key(raw_key: str) -> Optional[str]:
    key = _plain(raw_key).replace("_", " ")
    for dim, aliases in DIM_ALIASES.items():
        if key in aliases:
            return dim
    return None


def parse_size_chart(chart: Any) -> Dict[str, Dict[str, Tuple[float, float]]]:
    """{"M": {"chest": "85-89cm", "waist": "67-71cm"}} → {"M": {"bust": (85, 89), "waist": (67, 71)}}"""
    out: Dict[str, Dict[str, Tuple[float, float]]] = {}
    if not isinstance(chart, dict):
        return out
    for size_code, specs in chart.items():
        if not isinstance(specs, dict):
            continue
        code = str(size_code).strip().upper()
        dims: Dict[str, Tuple[float, float]] = {}
        for k, v in specs.items():
            dim = _dim_key(k)
            rng = _parse_range(v) if dim else None
            if dim and rng:
                dims[dim] = rng
        if dims:
            out[code] = dims
    return out


def normalize_profile(raw: Optional[Dict[str, Any]], strict: bool = False) -> Optional[Dict[str, Any]]:
    """Validate a fit profile. strict=True → raise 400 on out-of-range values (when saving)."""
    if not raw or not isinstance(raw, dict):
        return None
    gender = str(raw.get("gender") or "Nữ").strip()
    if gender not in AUDIENCES:
        if strict:
            raise HTTPException(status_code=400, detail="Giới tính hồ sơ size phải là Nữ, Nam hoặc Trẻ em.")
        gender = "Nữ"
    out: Dict[str, Any] = {"gender": gender}
    labels = {"height_cm": "Chiều cao", "weight_kg": "Cân nặng", "bust_cm": "Vòng ngực",
              "waist_cm": "Vòng eo", "hip_cm": "Vòng mông"}
    for key, (lo, hi) in PROFILE_LIMITS.items():
        val = raw.get(key)
        if val in (None, ""):
            out[key] = None
            continue
        try:
            num = float(val)
        except (TypeError, ValueError):
            num = None
        if num is None or not (lo <= num <= hi):
            if strict:
                raise HTTPException(status_code=400, detail=f"{labels[key]} phải trong khoảng {lo:g}–{hi:g}.")
            out[key] = None
        else:
            out[key] = round(num, 1)
    if not any(out[k] is not None for k in PROFILE_LIMITS):
        if strict:
            raise HTTPException(status_code=400, detail="Vui lòng nhập ít nhất chiều cao hoặc cân nặng.")
        return None
    return out


def _dim_distance(value: float, rng: Tuple[float, float]) -> float:
    lo, hi = rng
    width = max(hi - lo, 3.0)
    if lo <= value <= hi:
        # Inside the range: tiny tie-breaker so the most centred size wins
        return 0.04 * abs(value - (lo + hi) / 2) / width
    gap = (lo - value) if value < lo else (value - hi)
    return gap / width


def recommend_size(profile: Optional[Dict[str, Any]], audience: str, size_chart: Any,
                   size_codes: Iterable[str], in_stock_codes: Iterable[str] = ()) -> Dict[str, Any]:
    if not profile:
        return {"status": "no_profile"}
    codes = sorted({str(c).upper() for c in size_codes if c}, key=_size_rank)
    sized = [c for c in codes if c not in ONE_SIZE_CODES]
    if not sized:
        return {"status": "one_size"}
    gender = profile.get("gender") or "Nữ"
    if audience in AUDIENCES and audience != gender:
        return {"status": "other_audience"}
    base_chart = DEFAULT_CHARTS.get(gender if audience not in AUDIENCES else audience, DEFAULT_CHARTS["Nữ"])
    own_chart = parse_size_chart(size_chart)
    measures = {PROFILE_TO_DIM[k]: float(profile[k]) for k in PROFILE_TO_DIM if profile.get(k) is not None}

    scored = []
    for code in sized:
        ranges = dict(base_chart.get(code, {}))
        own = own_chart.get(code, {})
        ranges.update(own)
        ranges.pop("age", None)
        dims = [d for d in measures if d in ranges]
        if not dims:
            continue
        total_w = sum(DIM_WEIGHTS[d] for d in dims)
        dist = sum(DIM_WEIGHTS[d] * _dim_distance(measures[d], ranges[d]) for d in dims) / total_w
        scored.append((dist, code, len(dims), sum(1 for d in dims if d in own)))
    if not scored:
        return {"status": "insufficient"}
    scored.sort(key=lambda x: (x[0], _size_rank(x[1])))
    best_dist, best_code, n_dims, own_dims = scored[0]
    second = scored[1] if len(scored) > 1 else None

    conf = 0.96 - min(0.5, best_dist * 0.45)
    if own_dims == 0:
        conf -= 0.08
    if n_dims == 1:
        conf -= 0.1
    if second and (second[0] - best_dist) < 0.12:
        conf -= 0.07
    conf = max(0.4, min(0.97, conf))
    pct = int(round(conf * 100))
    stock = {str(c).upper() for c in in_stock_codes}
    alt = second[1] if (second and second[0] - best_dist < 0.3) else None
    return {
        "status": "ok",
        "size": best_code,
        "confidence": pct,
        "level": "high" if pct >= 80 else ("medium" if pct >= 62 else "low"),
        "alt_size": alt,
        "in_stock": best_code in stock if stock else True,
        "basis": "product_chart" if own_dims else "standard_chart",
    }


# =============================================================================
# 3. SOCIAL PROOF HELPERS
# =============================================================================
EXCLUDED_ORDER_STATUSES = ("Đã hủy", "Chờ hoàn tiền", "Đã hoàn tiền", "Giao không thành công")
GENERIC_NAME_HINTS = ("khach", "test", "demo", "user", "admin", "nhan vien", "review", "customer", "guest")

PROVINCES: List[Tuple[str, Tuple[str, ...]]] = [
    ("TP.HCM", ("tp.hcm", "tp hcm", "tphcm", "hcm", "ho chi minh", "sai gon", "saigon")),
    ("Hà Nội", ("ha noi", "hanoi")), ("Đà Nẵng", ("da nang",)), ("Hải Phòng", ("hai phong",)),
    ("Cần Thơ", ("can tho",)), ("An Giang", ("an giang",)), ("Bà Rịa - Vũng Tàu", ("vung tau", "ba ria")),
    ("Bắc Giang", ("bac giang",)), ("Bắc Kạn", ("bac kan", "bac can")), ("Bạc Liêu", ("bac lieu",)),
    ("Bắc Ninh", ("bac ninh",)), ("Bến Tre", ("ben tre",)), ("Bình Định", ("binh dinh", "quy nhon")),
    ("Bình Dương", ("binh duong", "thu dau mot")), ("Bình Phước", ("binh phuoc",)),
    ("Bình Thuận", ("binh thuan", "phan thiet", "mui ne")), ("Cà Mau", ("ca mau",)), ("Cao Bằng", ("cao bang",)),
    ("Đắk Lắk", ("dak lak", "dac lac", "buon ma thuot")), ("Đắk Nông", ("dak nong",)), ("Điện Biên", ("dien bien",)),
    ("Đồng Nai", ("dong nai", "bien hoa")), ("Đồng Tháp", ("dong thap",)), ("Gia Lai", ("gia lai", "pleiku")),
    ("Hà Giang", ("ha giang",)), ("Hà Nam", ("ha nam",)), ("Hà Tĩnh", ("ha tinh",)), ("Hải Dương", ("hai duong",)),
    ("Hậu Giang", ("hau giang",)), ("Hòa Bình", ("hoa binh",)), ("Hưng Yên", ("hung yen",)),
    ("Khánh Hòa", ("khanh hoa", "nha trang", "cam ranh")), ("Kiên Giang", ("kien giang", "phu quoc", "rach gia")),
    ("Kon Tum", ("kon tum",)), ("Lai Châu", ("lai chau",)), ("Lâm Đồng", ("lam dong", "da lat")),
    ("Lạng Sơn", ("lang son",)), ("Lào Cai", ("lao cai", "sa pa", "sapa")), ("Long An", ("long an",)),
    ("Nam Định", ("nam dinh",)), ("Nghệ An", ("nghe an", "vinh city")), ("Ninh Bình", ("ninh binh",)),
    ("Ninh Thuận", ("ninh thuan", "phan rang")), ("Phú Thọ", ("phu tho", "viet tri")), ("Phú Yên", ("phu yen", "tuy hoa")),
    ("Quảng Bình", ("quang binh", "dong hoi")), ("Quảng Nam", ("quang nam", "hoi an")), ("Quảng Ngãi", ("quang ngai",)),
    ("Quảng Ninh", ("quang ninh", "ha long")), ("Quảng Trị", ("quang tri",)), ("Sóc Trăng", ("soc trang",)),
    ("Sơn La", ("son la",)), ("Tây Ninh", ("tay ninh",)), ("Thái Bình", ("thai binh",)),
    ("Thái Nguyên", ("thai nguyen",)), ("Thanh Hóa", ("thanh hoa", "sam son")), ("Thừa Thiên Huế", ("thua thien", "hue")),
    ("Tiền Giang", ("tien giang", "my tho")), ("Trà Vinh", ("tra vinh",)), ("Tuyên Quang", ("tuyen quang",)),
    ("Vĩnh Long", ("vinh long",)), ("Vĩnh Phúc", ("vinh phuc",)), ("Yên Bái", ("yen bai",)),
]
_PROVINCE_PATTERNS = sorted(
    ((re.compile(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])"), name, len(alias))
     for name, aliases in PROVINCES for alias in aliases),
    key=lambda t: -t[2],
)


def parse_province(address: Any) -> Optional[str]:
    """Return the province/city name found in a free-text Vietnamese address (last segments first)."""
    text = _plain(address)
    if not text:
        return None
    segments = [s.strip() for s in re.split(r"[,;\n]", text) if s.strip()]
    for seg in reversed(segments):
        for pattern, name, _ in _PROVINCE_PATTERNS:
            if pattern.search(seg):
                return name
    return None


def display_first_name(full_name: Any) -> Optional[str]:
    """'Nguyễn Thị Lan' → 'Lan'. Generic/test names → None (shown as 'Một khách hàng')."""
    raw = str(full_name or "").strip()
    plain = _plain(raw)
    if not raw or any(h in plain for h in GENERIC_NAME_HINTS):
        return None
    tokens = [t for t in re.split(r"\s+", raw) if t]
    if not tokens:
        return None
    given = tokens[-1].strip(".,-")
    if not given or any(ch.isdigit() for ch in given) or len(given) > 14 or not given[0].isalpha():
        return None
    return given[:1].upper() + given[1:].lower()


def time_ago_label(minutes: int) -> str:
    if minutes < 2:
        return "vừa xong"
    if minutes < 60:
        return f"{minutes} phút trước"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} giờ trước"
    return f"{hours // 24} ngày trước"


class PresenceTracker:
    """In-memory 'đang xem' counter: viewers send a heartbeat; entries expire after TTL seconds."""

    def __init__(self, ttl_seconds: float = 45.0, max_products: int = 5000, max_viewers: int = 500):
        self.ttl = ttl_seconds
        self.max_products = max_products
        self.max_viewers = max_viewers
        self._data: Dict[int, Dict[str, float]] = {}
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        for pid in list(self._data.keys()):
            viewers = self._data[pid]
            for vid in [v for v, ts in viewers.items() if now - ts > self.ttl]:
                viewers.pop(vid, None)
            if not viewers:
                self._data.pop(pid, None)

    def heartbeat(self, product_id: int, viewer_id: str, now: Optional[float] = None) -> int:
        now = now if now is not None else time.monotonic()
        with self._lock:
            self._prune(now)
            viewers = self._data.get(product_id)
            if viewers is None:
                if len(self._data) >= self.max_products:
                    return 0
                viewers = self._data[product_id] = {}
            if viewer_id in viewers or len(viewers) < self.max_viewers:
                viewers[viewer_id] = now
            return len(viewers)

    def leave(self, product_id: int, viewer_id: str) -> int:
        with self._lock:
            viewers = self._data.get(product_id) or {}
            viewers.pop(viewer_id, None)
            if not viewers:
                self._data.pop(product_id, None)
            return len(viewers)

    def count(self, product_id: int, now: Optional[float] = None) -> int:
        now = now if now is not None else time.monotonic()
        with self._lock:
            self._prune(now)
            return len(self._data.get(product_id) or {})


presence_tracker = PresenceTracker()
_recent_cache: Dict[str, Any] = {"at": 0.0, "key": None, "data": None}
_recent_lock = threading.Lock()


# =============================================================================
# 5. VISUAL SEARCH (colour palette)
# =============================================================================
MAX_UPLOAD_BYTES = 6 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_IMAGE_PIXELS = 40_000_000
_palette_cache: Dict[str, Tuple[int, int, List[Tuple[Tuple[int, int, int], float]]]] = {}
_palette_lock = threading.Lock()


def _srgb_to_lab(rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
    def lin(c: float) -> float:
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(float(v)) for v in rgb)
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = (r * 0.2126 + g * 0.7152 + b * 0.0722)
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _hex(rgb: Tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def extract_palette(img, colors: int = 6) -> List[Tuple[Tuple[int, int, int], float]]:
    """Dominant colours (rgb, weight) of a PIL image; ignores flat white studio background."""
    from PIL import Image

    img = img.convert("RGB")
    w, h = img.size
    if w > 8 and h > 8:
        img = img.crop((int(w * 0.1), int(h * 0.06), int(w * 0.9), int(h * 0.94)))
    img.thumbnail((96, 96))
    pixels = list(img.getdata())
    kept = [p for p in pixels if not (min(p) > 226 and max(p) - min(p) < 22)]
    if len(kept) < max(16, len(pixels) * 0.12):
        kept = pixels
    strip = Image.new("RGB", (len(kept), 1))
    strip.putdata(kept)
    quant = strip.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    pal = quant.getpalette() or []
    counts = quant.getcolors() or []
    total = float(sum(c for c, _ in counts)) or 1.0
    out = []
    for count, idx in counts:
        rgb = tuple(pal[idx * 3: idx * 3 + 3])
        if len(rgb) == 3:
            out.append((rgb, count / total))
    out.sort(key=lambda x: -x[1])
    return [c for c in out if c[1] >= 0.03][:colors] or out[:1]


def palette_distance(query: List[Tuple[Tuple[int, int, int], float]],
                     target: List[Tuple[Tuple[int, int, int], float]]) -> float:
    if not query or not target:
        return 999.0
    q_lab = [(_srgb_to_lab(c), w) for c, w in query]
    t_lab = [(_srgb_to_lab(c), w) for c, w in target]

    def de(a, b) -> float:
        return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)
    forward = sum(w * min(de(c, t) for t, _ in t_lab) for c, w in q_lab)
    backward = sum(w * min(de(t, c) for c, _ in q_lab) for t, w in t_lab)
    return 0.62 * forward + 0.38 * backward


def static_file_path(url_path: str) -> Optional[str]:
    if not url_path or not url_path.startswith("/static/"):
        return None
    rel = url_path[len("/static/"):].split("?")[0]
    full = os.path.normpath(os.path.join(STATIC_DIR, rel))
    if not full.startswith(os.path.normpath(STATIC_DIR)):
        return None
    return full


def product_image_palette(url_path: str) -> Optional[List[Tuple[Tuple[int, int, int], float]]]:
    """Palette of a static product image, cached by path and refreshed when mtime/size changes."""
    from PIL import Image

    full = static_file_path(url_path)
    if not full or not os.path.isfile(full):
        return None
    try:
        st = os.stat(full)
    except OSError:
        return None
    with _palette_lock:
        hit = _palette_cache.get(full)
        if hit and hit[0] == st.st_mtime_ns and hit[1] == st.st_size:
            return hit[2]
    try:
        with Image.open(full) as im:
            im.draft("RGB", (192, 192))
            palette = extract_palette(im)
    except Exception:
        return None
    with _palette_lock:
        _palette_cache[full] = (st.st_mtime_ns, st.st_size, palette)
    return palette


# =============================================================================
# 4. TRIP STYLIST CONFIG
# =============================================================================
TRIP_TYPES = {
    "bien": "Biển",
    "ho-boi": "Hồ bơi",
    "thi-dau": "Thi đấu",
    "resort": "Resort",
}
STYLES = {
    "nang-dong": "Năng động",
    "thanh-lich": "Thanh lịch",
    "kin-dao": "Kín đáo",
    "noi-bat": "Nổi bật",
}
MAIN_CATEGORIES = {
    "Nữ": ("bikini-2-manh", "ao-tam-1-manh"),
    "Nam": ("quan-boi-the-thao-nam", "quan-boi-boxer-nam"),
    "Trẻ em": ("do-boi-be-gai",),
}
TRIP_KEYWORDS = {
    "thi-dau": ("thi dau", "racing", "speed", "jammer", "the thao", "olympic", "duong dua", "chuyen nghiep",
                "hydro", "carbon", "active", "aura"),
    "ho-boi": ("the thao", "lien than", "active", "chuyen nghiep", "khang clo", "1 manh", "mot manh"),
    "bien": ("bien", "song", "beach", "luot song", "coral", "nhiet doi", "malibu", "waikiki", "aloha",
             "ocean", "dai duong", "san ho"),
    "resort": ("resort", "santorini", "riviera", "dia trung hai", "quy phai", "palm", "cap cao", "co vuong",
               "nang vang", "breeze"),
}
TRIP_CATEGORY_BONUS = {
    "thi-dau": {"ao-tam-1-manh": 2.2, "quan-boi-the-thao-nam": 2.4, "bikini-2-manh": -1.5, "quan-boi-boxer-nam": -1.5},
    "ho-boi": {"ao-tam-1-manh": 1.5, "quan-boi-the-thao-nam": 1.5},
    "bien": {"bikini-2-manh": 1.5, "quan-boi-boxer-nam": 2.0},
    "resort": {"bikini-2-manh": 1.2, "ao-tam-1-manh": 0.5, "quan-boi-boxer-nam": 2.0},
}
STYLE_KEYWORDS = {
    "nang-dong": ("the thao", "active", "luot song", "song", "wave", "dynamic", "speed"),
    "thanh-lich": ("elegance", "thanh lich", "quy phai", "co vuong", "riviera", "lien than", "navy", "den"),
    "kin-dao": ("lien than", "1 manh", "mot manh", "cap cao", "tay dai", "kin"),
    "noi-bat": ("coral", "nhiet doi", "sac mau", "cau vong", "hong", "day dan cheo", "santorini", "sunset",
                "cam", "aloha", "ngoc bich"),
}
MAIN_REASONS = {
    "thi-dau": "Form ôm sát, giảm lực cản — hợp thi đấu & tập cường độ cao",
    "ho-boi": "Vải kháng Clo, giữ form sau nhiều giờ bơi hồ",
    "bien": "Nhanh khô, màu biển nổi bật — lên hình đẹp ngoài bãi cát",
    "resort": "Thiết kế sang, dễ phối khi dạo resort & hồ bơi vô cực",
}


# =============================================================================
# 6. DAILY CHECK-IN
# =============================================================================
CHECKIN_REWARDS = [1, 1, 1, 1, 1, 1, 3]
SHELLS_PER_SPIN = 3


def vn_today():
    return datetime.now(VN_TZ).date()


class ExperienceService:
    def __init__(self, db: Session):
        self.db = db
        self.catalog = CatalogService(db)

    # ------------------------------------------------------------------ products
    def _product_query(self):
        return self.db.query(ProductionProduct).options(
            joinedload(ProductionProduct.category).joinedload(ProductionCategory.parent),
            selectinload(ProductionProduct.variants).joinedload(ProductionVariant.size),
            selectinload(ProductionProduct.variants).joinedload(ProductionVariant.color),
            selectinload(ProductionProduct.variants).joinedload(ProductionVariant.inventory),
            selectinload(ProductionProduct.images),
        ).filter(ProductionProduct.deleted_at == None, ProductionProduct.status == "Selling")  # noqa: E711

    @staticmethod
    def _main_image(p: ProductionProduct) -> str:
        imgs = sorted(p.images or [], key=lambda i: (i.sort_order, i.id))
        return imgs[0].file_path if imgs else "/static/images/placeholder.webp"

    @staticmethod
    def _category_slugs(p: ProductionProduct) -> Tuple[str, str]:
        cat = p.category
        if not cat:
            return "", ""
        return cat.slug, (cat.parent.slug if cat.parent else cat.slug)

    @staticmethod
    def quick_sizes(p: ProductionProduct) -> List[Dict[str, Any]]:
        """One chip per size: the best-stocked active variant of that size."""
        by_size: Dict[str, Dict[str, Any]] = {}
        for v in p.variants or []:
            if not v.is_active or not v.size:
                continue
            qty = v.inventory.available_quantity if v.inventory else 0
            code = (v.size.code or "").upper()
            cur = by_size.get(code)
            if cur is None:
                by_size[code] = cur = {
                    "size_code": code,
                    "size_label": "Free" if code in ONE_SIZE_CODES else code,
                    "sort": v.size.sort_order,
                    "variant_id": None, "color_name": None, "color_hex": None,
                    "available": 0, "_best": -1,
                }
            cur["available"] += max(0, qty)
            if qty > cur["_best"]:
                cur["_best"] = qty
                cur["variant_id"] = v.id
                cur["color_name"] = v.color.name if v.color else ""
                cur["color_hex"] = v.color.hex_code if v.color else ""
        out = []
        for item in sorted(by_size.values(), key=lambda x: (x["sort"], _size_rank(x["size_code"]))):
            item["in_stock"] = item["available"] > 0
            item.pop("_best", None)
            item.pop("sort", None)
            out.append(item)
        return out

    def fit_for_product(self, p: ProductionProduct, profile: Optional[Dict[str, Any]],
                        sizes: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        sizes = sizes if sizes is not None else self.quick_sizes(p)
        return recommend_size(
            profile, p.target_audience, p.size_chart or {},
            [s["size_code"] for s in sizes], [s["size_code"] for s in sizes if s["in_stock"]],
        )

    # ------------------------------------------------------------------ fit profile
    def get_profile(self, user: UserAccount) -> Optional[Dict[str, Any]]:
        row = self.db.query(ProductionFitProfile).filter(ProductionFitProfile.account_id == user.id).first()
        if not row:
            return None
        return {
            "gender": row.gender,
            "height_cm": float(row.height_cm) if row.height_cm is not None else None,
            "weight_kg": float(row.weight_kg) if row.weight_kg is not None else None,
            "bust_cm": float(row.bust_cm) if row.bust_cm is not None else None,
            "waist_cm": float(row.waist_cm) if row.waist_cm is not None else None,
            "hip_cm": float(row.hip_cm) if row.hip_cm is not None else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    def save_profile(self, user: UserAccount, raw: Dict[str, Any]) -> Dict[str, Any]:
        data = normalize_profile(raw, strict=True)
        row = self.db.query(ProductionFitProfile).filter(ProductionFitProfile.account_id == user.id).first()
        if not row:
            row = ProductionFitProfile(account_id=user.id)
            self.db.add(row)
        for key in ("gender",) + tuple(PROFILE_LIMITS.keys()):
            setattr(row, key, data.get(key))
        row.updated_at = _utcnow()
        self.db.flush()
        return self.get_profile(user)

    def delete_profile(self, user: UserAccount) -> None:
        self.db.query(ProductionFitProfile).filter(ProductionFitProfile.account_id == user.id).delete()
        self.db.flush()

    def resolve_profile(self, raw: Optional[Dict[str, Any]], user: Optional[UserAccount]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        prof = normalize_profile(raw) if raw else None
        if prof:
            return prof, "request"
        if user is not None and user.role and user.role.code == "CUSTOMER":
            stored = self.get_profile(user)
            if stored:
                return normalize_profile(stored), "account"
        return None, None

    def recommend_for_products(self, product_ids: List[int], profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        ids = list(dict.fromkeys(int(i) for i in product_ids if i))[:40]
        if not ids:
            return {}
        out: Dict[str, Any] = {}
        for p in self._product_query().filter(ProductionProduct.id.in_(ids)).all():
            sizes = self.quick_sizes(p)
            out[str(p.id)] = {"sizes": sizes, "fit": self.fit_for_product(p, profile, sizes)}
        return out

    # ------------------------------------------------------------------ social proof
    def recent_purchases(self, limit: int = 12) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit or 12), 30))
        key = f"recent:{limit}"
        with _recent_lock:
            if _recent_cache["key"] == key and time.monotonic() - _recent_cache["at"] < 30:
                return _recent_cache["data"]
        now = _utcnow()
        since = now - timedelta(days=7)
        orders = (
            self.db.query(ProductionOrder)
            .options(
                selectinload(ProductionOrder.items)
                .joinedload(ProductionOrderItem.variant)
                .joinedload(ProductionVariant.product)
                .selectinload(ProductionProduct.images)
            )
            .filter(ProductionOrder.placed_at >= since, ~ProductionOrder.status.in_(EXCLUDED_ORDER_STATUSES))
            .order_by(ProductionOrder.placed_at.desc())
            .limit(limit * 4)
            .all()
        )
        out: List[Dict[str, Any]] = []
        for o in orders:
            item = next((it for it in o.items if it.variant and it.variant.product
                         and it.variant.product.deleted_at is None), None)
            if not item:
                continue
            prod = item.variant.product
            snap = o.recipient_snapshot or {}
            imgs = sorted(prod.images or [], key=lambda i: (i.sort_order, i.id))
            img = next((i.file_path for i in imgs if i.color_id and i.color_id == item.variant.color_id), None)
            img = img or (imgs[0].file_path if imgs else "/static/images/placeholder.webp")
            placed = o.placed_at if o.placed_at.tzinfo else o.placed_at.replace(tzinfo=timezone.utc)
            minutes = max(0, int((now - placed).total_seconds() // 60))
            first = display_first_name(snap.get("name"))
            out.append({
                "key": f"{int(placed.timestamp())}-{item.id}",
                "buyer": first or "Một khách hàng",
                "province": parse_province(snap.get("address")),
                "product_id": prod.id,
                "product_slug": prod.slug,
                "product_name": prod.name,
                "image_url": img,
                "quantity": int(sum(it.quantity for it in o.items)),
                "minutes_ago": minutes,
                "time_label": time_ago_label(minutes),
            })
            if len(out) >= limit:
                break
        with _recent_lock:
            _recent_cache.update({"at": time.monotonic(), "key": key, "data": out})
        return out

    # ------------------------------------------------------------------ trip stylist
    @staticmethod
    def _effective_price(p: ProductionProduct, disc_map: Dict[int, float]) -> Tuple[float, float, float]:
        base = float(p.base_price)
        pct = float(disc_map.get(p.id, 0.0))
        price = round(base * (1.0 - pct / 100.0)) if pct > 0 else base
        return price, base, pct

    @staticmethod
    def _pick_variant(sizes: List[Dict[str, Any]], preferred: Optional[str]) -> Optional[Dict[str, Any]]:
        stocked = [s for s in sizes if s["in_stock"] and s["variant_id"]]
        if not stocked:
            return None
        if preferred:
            hit = next((s for s in stocked if s["size_code"] == preferred), None)
            if hit:
                return {**hit, "from_profile": True}
        return {**max(stocked, key=lambda s: s["available"]), "from_profile": False}

    def trip_stylist(self, payload: Dict[str, Any], profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        trip = str(payload.get("trip_type") or "bien")
        if trip not in TRIP_TYPES:
            raise HTTPException(status_code=400, detail="Loại chuyến đi không hợp lệ.")
        style = str(payload.get("style") or "nang-dong")
        if style not in STYLES:
            raise HTTPException(status_code=400, detail="Phong cách không hợp lệ.")
        gender = str(payload.get("gender") or (profile or {}).get("gender") or "Nữ")
        if gender not in AUDIENCES:
            raise HTTPException(status_code=400, detail="Giới tính phải là Nữ, Nam hoặc Trẻ em.")
        try:
            days = int(payload.get("days") or 2)
        except (TypeError, ValueError):
            days = 2
        if not 1 <= days <= 30:
            raise HTTPException(status_code=400, detail="Số ngày phải từ 1 đến 30.")
        budget = payload.get("budget")
        try:
            budget = float(budget) if budget not in (None, "", 0, "0") else None
        except (TypeError, ValueError):
            budget = None
        if budget is not None and not 100_000 <= budget <= 50_000_000:
            raise HTTPException(status_code=400, detail="Ngân sách phải từ 100.000đ đến 50.000.000đ.")
        if profile and profile.get("gender") != gender:
            profile = None  # hồ sơ size của người khác giới / trẻ em không áp dụng

        products = self._product_query().all()
        disc_map = self.catalog._get_product_discount_map([p.id for p in products])
        entries = []
        for p in products:
            sizes = self.quick_sizes(p)
            if not any(s["in_stock"] for s in sizes):
                continue
            slug, parent = self._category_slugs(p)
            price, base, pct = self._effective_price(p, disc_map)
            text = _plain(f"{p.name} {' '.join(p.tags or [])}")
            entries.append({"p": p, "sizes": sizes, "slug": slug, "parent": parent, "text": text,
                            "price": price, "base": base, "pct": pct,
                            "stock": sum(s["available"] for s in sizes)})

        def kw_score(text: str, words: Iterable[str]) -> float:
            return float(sum(1 for w in words if w in text))

        def is_cover(e) -> bool:
            return any(k in e["text"] for k in ("rashguard", "tay dai", "ao boi chong nang", "ao-boi-tay-dai"))

        # --- main swimwear candidates
        mains = []
        for e in entries:
            if e["slug"] not in MAIN_CATEGORIES[gender] or e["p"].target_audience not in (gender, "Unisex"):
                continue
            if is_cover(e):
                continue
            score = kw_score(e["text"], TRIP_KEYWORDS[trip]) * 1.2
            score += TRIP_CATEGORY_BONUS.get(trip, {}).get(e["slug"], 0.0)
            score += kw_score(e["text"], STYLE_KEYWORDS[style])
            if style == "kin-dao":
                score += 1.5 if e["slug"] == "ao-tam-1-manh" else (-1.0 if e["slug"] == "bikini-2-manh" else 0)
            if style == "noi-bat" and e["slug"] == "bikini-2-manh":
                score += 0.8
            fit = self.fit_for_product(e["p"], profile, e["sizes"]) if profile else {"status": "no_profile"}
            if fit.get("status") == "ok" and fit.get("in_stock"):
                score += 1.0
            score += 0.4 if e["pct"] > 0 else 0
            score += 0.3 if e["stock"] > 10 else 0
            mains.append((score, e, fit))
        mains.sort(key=lambda x: (-x[0], x[1]["price"], x[1]["p"].id))

        covers = []
        if gender != "Trẻ em":
            for e in entries:
                if is_cover(e) and e["p"].target_audience in (gender, "Unisex"):
                    sc = kw_score(e["text"], STYLE_KEYWORDS[style]) + (0.4 if e["pct"] > 0 else 0) + (0.3 if e["stock"] > 10 else 0)
                    fit = self.fit_for_product(e["p"], profile, e["sizes"]) if profile else {"status": "no_profile"}
                    covers.append((sc, e, fit))
            covers.sort(key=lambda x: (-x[0], x[1]["price"], x[1]["p"].id))

        def acc(pred, bonus_words: Iterable[str]) -> List[Tuple[float, Dict[str, Any], Dict[str, Any]]]:
            out = []
            for e in entries:
                if e["parent"] != "phu-kien-boi-loi" or not pred(e):
                    continue
                sc = kw_score(e["text"], bonus_words) + (0.4 if e["pct"] > 0 else 0) + (0.2 if e["stock"] > 10 else 0)
                out.append((sc, e, {"status": "one_size"}))
            out.sort(key=lambda x: (-x[0], x[1]["price"], x[1]["p"].id))
            return out

        goggle_words = ("thi dau", "goc rong", "chong dong suong", "chuyen nghiep") if trip in ("thi-dau", "ho-boi") \
            else ("trang guong", "uv", "chong dong suong", "goc rong")
        if trip == "thi-dau":
            eyewear = acc(lambda e: "combo" in e["text"] and "kinh" in e["text"], goggle_words) \
                or acc(lambda e: e["text"].startswith("kinh"), goggle_words)
        else:
            eyewear = acc(lambda e: e["text"].startswith("kinh"), goggle_words) \
                or acc(lambda e: "kinh" in e["text"], goggle_words)
        caps = acc(lambda e: e["text"].startswith("mu boi") or e["text"].startswith("mu "), ("silicone", "hydrodynamic"))
        bags = acc(lambda e: "tui" in e["text"] and "chong nuoc" in e["text"], ("dry bag", "20l", "da nang"))

        slots: List[Tuple[str, str, List, bool]] = [("main", "Đồ bơi chính", mains, True)]
        if covers and (trip in ("bien", "resort") or style == "kin-dao"):
            slots.append(("cover", "Áo chống nắng", covers, False))
        slots.append(("eyewear", "Kính bơi", eyewear, False))
        if trip in ("thi-dau", "ho-boi") and caps:
            slots.append(("cap", "Mũ bơi", caps, False))
        if trip in ("bien", "resort") or days >= 2:
            slots.append(("bag", "Túi chống nước", bags, False))
        if days >= 3 and len(mains) > 1:
            slots.append(("main2", "Bộ thay phiên", mains, False))

        chosen: List[Dict[str, Any]] = []
        used_ids = set()
        used_names = set()
        remaining = budget

        def base_name(e) -> str:
            # Catalog has re-editions ("… — Phiên Bản Pro #2"): treat them as the same design
            return _plain(e["p"].name.split(" — ")[0])

        for role, label, pool, required in slots:
            pool = [c for c in pool if c[1]["p"].id not in used_ids and base_name(c[1]) not in used_names]
            if role == "cap" and any(c["role"] == "eyewear" and "mu boi" in _plain(c["name"]) for c in chosen):
                continue  # combo kính + mũ đã có mũ bơi
            if not pool:
                continue
            pick = None
            if remaining is None:
                pick = pool[0]
            else:
                cap = remaining * (0.62 if role == "main" and len(slots) > 1 else 1.0)
                pick = next((c for c in pool if c[1]["price"] <= cap), None)
                if pick is None and required:
                    pick = min(pool, key=lambda c: c[1]["price"])
            if pick is None:
                continue
            _, e, fit = pick
            preferred = fit.get("size") if fit.get("status") == "ok" else None
            variant = self._pick_variant(e["sizes"], preferred)
            if not variant:
                continue
            used_ids.add(e["p"].id)
            used_names.add(base_name(e))
            if remaining is not None:
                remaining -= e["price"]
            chosen.append(self._trip_item(role, label, e, fit, variant, trip, style, days))

        total = sum(i["unit_price"] for i in chosen)
        total_base = sum(i["base_price"] for i in chosen)
        return {
            "title": f"Set {TRIP_TYPES[trip]} {days} ngày",
            "subtitle": f"{gender} · {STYLES[style]}" + (f" · ngân sách {int(budget):,}đ".replace(",", ".") if budget else ""),
            "trip_type": trip, "style": style, "gender": gender, "days": days,
            "budget": budget,
            "items": chosen,
            "total_price": total,
            "total_base_price": total_base,
            "savings": max(0.0, total_base - total),
            "within_budget": (budget is None) or total <= budget,
            "used_fit_profile": bool(profile),
        }

    def _trip_item(self, role, label, e, fit, variant, trip, style, days) -> Dict[str, Any]:
        p = e["p"]
        if role == "main":
            reason = MAIN_REASONS[trip]
            if style == "kin-dao":
                reason += ", kín đáo mà vẫn tôn dáng"
            elif style == "noi-bat":
                reason += ", màu sắc nổi bật"
            elif style == "thanh-lich":
                reason += ", đường cắt thanh lịch"
        elif role == "main2":
            reason = f"Đi {days} ngày — thêm một bộ để luân phiên, luôn có đồ khô"
        elif role == "cover":
            reason = "Che nắng UPF 50+ cho giờ nắng gắt, hạn chế cháy da"
        elif role == "eyewear":
            reason = "Kính góc rộng, chống đọng sương cho tầm nhìn rõ" if trip in ("thi-dau", "ho-boi") \
                else "Chống UV & đọng sương, bảo vệ mắt khi bơi ngoài trời"
        elif role == "cap":
            reason = "Giảm lực cản, bảo vệ tóc khỏi nước Clo"
        else:
            reason = "Giữ điện thoại & đồ khô ráo, tách riêng đồ ướt"
        size_note = None
        if variant["size_code"] not in ONE_SIZE_CODES:
            size_note = (f"Size {variant['size_code']} theo hồ sơ của bạn" if variant.get("from_profile")
                         else f"Size {variant['size_code']} còn nhiều hàng nhất")
        return {
            "role": role,
            "role_label": label,
            "product_id": p.id,
            "slug": p.slug,
            "name": p.name,
            "image_url": self._main_image(p),
            "reason": reason,
            "size_note": size_note,
            "variant_id": variant["variant_id"],
            "size_code": variant["size_code"],
            "size_label": variant["size_label"],
            "color_name": variant["color_name"],
            "unit_price": e["price"],
            "base_price": e["base"],
            "discount_percent": e["pct"],
            "fit": fit,
        }

    # ------------------------------------------------------------------ visual search
    def visual_search(self, image_bytes: bytes, category: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
        from PIL import Image, ImageOps, UnidentifiedImageError

        try:
            probe = Image.open(io.BytesIO(image_bytes))
            fmt = probe.format
            w, h = probe.size
            probe.verify()
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
            raise HTTPException(status_code=400, detail="Tệp tải lên không phải ảnh hợp lệ.")
        if fmt not in ALLOWED_IMAGE_FORMATS:
            raise HTTPException(status_code=415, detail="Chỉ hỗ trợ ảnh JPG, PNG hoặc WEBP.")
        if w * h > MAX_IMAGE_PIXELS or w < 16 or h < 16:
            raise HTTPException(status_code=400, detail="Kích thước ảnh không phù hợp (tối thiểu 16px, tối đa 40MP).")
        try:
            img = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes)))
            query_palette = extract_palette(img)
        except Exception:
            raise HTTPException(status_code=400, detail="Không đọc được màu sắc từ ảnh này.")

        q = self._product_query()
        cat = (category or "").strip()
        if cat:
            q = q.join(ProductionCategory, ProductionProduct.category_id == ProductionCategory.id).filter(
                (ProductionCategory.slug == cat) | ProductionCategory.parent.has(ProductionCategory.slug == cat)
            )
        products = q.all()
        scored = []
        for p in products:
            pal = product_image_palette(self._main_image(p))
            if not pal:
                continue
            dist = palette_distance(query_palette, pal)
            scored.append((dist, p, pal))
        scored.sort(key=lambda x: (x[0], x[1].id))
        top = scored[: max(1, min(int(limit or 20), 20))]
        disc_map = self.catalog._get_product_discount_map([p.id for _, p, _ in top])
        results = []
        for dist, p, pal in top:
            item = self.catalog._serialize_list_item(p, disc_map)
            item["similarity"] = int(round(100 * math.exp(-dist / 42.0)))
            item["palette"] = [_hex(c) for c, _ in pal[:4]]
            results.append(item)
        return {
            "palette": [{"hex": _hex(c), "weight": round(wt, 3)} for c, wt in query_palette],
            "category": cat or None,
            "count": len(results),
            "results": results,
        }

    # ------------------------------------------------------------------ daily check-in
    def _total_shells(self, account_id: int) -> int:
        return int(self.db.query(func.coalesce(func.sum(ProductionDailyCheckin.shells_awarded), 0))
                   .filter(ProductionDailyCheckin.account_id == account_id).scalar() or 0)

    def checkin_state(self, user: UserAccount) -> Dict[str, Any]:
        from app.services.lucky_wheel_service import LuckyWheelService

        today = vn_today()
        last = (self.db.query(ProductionDailyCheckin)
                .filter(ProductionDailyCheckin.account_id == user.id)
                .order_by(ProductionDailyCheckin.checkin_date.desc())
                .first())
        checked_today = bool(last and last.checkin_date == today)
        if checked_today:
            current = last.streak_day
        elif last and last.checkin_date == today - timedelta(days=1) and last.streak_day < 7:
            current = last.streak_day
        else:
            current = 0
        next_day = None if checked_today else current + 1
        days = []
        for i in range(1, 8):
            status = "done" if i <= current else ("today" if next_day == i else "upcoming")
            days.append({"day": i, "shells": CHECKIN_REWARDS[i - 1], "status": status})
        total = self._total_shells(user.id)
        wheel = LuckyWheelService(self.db)
        cfg, _row = wheel.get_config()
        _idx, period_start, next_reset = wheel.current_period(cfg)
        return {
            "checked_in_today": checked_today,
            "streak": current,
            "next_reward": CHECKIN_REWARDS[next_day - 1] if next_day else None,
            "days": days,
            "total_shells": total,
            "shells_per_spin": SHELLS_PER_SPIN,
            "shells_progress": total % SHELLS_PER_SPIN,
            "bonus_spins_this_cycle": wheel.bonus_spins(user.id, period_start),
            "next_reset_at": next_reset.isoformat(),
            "today": today.isoformat(),
        }

    def checkin(self, user: UserAccount) -> Dict[str, Any]:
        state = self.checkin_state(user)
        if state["checked_in_today"]:
            raise HTTPException(status_code=409, detail="Hôm nay bạn đã điểm danh rồi — hẹn bạn ngày mai nhé!")
        streak_day = state["streak"] + 1
        award = CHECKIN_REWARDS[streak_day - 1]
        before = state["total_shells"]
        bonus = (before + award) // SHELLS_PER_SPIN - before // SHELLS_PER_SPIN
        row = ProductionDailyCheckin(
            account_id=user.id, checkin_date=vn_today(), streak_day=streak_day,
            shells_awarded=award, bonus_spins=bonus,
        )
        self.db.add(row)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(status_code=409, detail="Hôm nay bạn đã điểm danh rồi — hẹn bạn ngày mai nhé!")
        out = self.checkin_state(user)
        out["awarded_shells"] = award
        out["bonus_spins_awarded"] = bonus
        if bonus:
            out["message"] = f"+{award} Vỏ Sò · đổi được {bonus} lượt quay thưởng!"
        else:
            need = SHELLS_PER_SPIN - out["shells_progress"]
            out["message"] = f"+{award} Vỏ Sò · còn {need} Vỏ Sò nữa để nhận lượt quay."
        return out
