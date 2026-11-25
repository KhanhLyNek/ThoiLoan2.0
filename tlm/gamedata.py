"""Dữ liệu game tĩnh: ảnh có sẵn, giá, sản lượng mỏ, sức chứa, chướng ngại khởi đầu."""
from . import config
from .data import load_table

IMAGE_LEVELS = {k: v for k, v in load_table("image_levels_all.json" if config.USE_OBB else "image_levels_apk.json").items()}
COST = load_table("cost.json")                     # loại -> cấp -> [vàng, dầu, dầu đen, G]
RES_INFO = load_table("resources.json")            # mỏ -> cấp -> [loại, sản lượng/giờ, sức chứa]
_cap = load_table("capacity.json")
CAP_TOWNHALL = {int(k): v for k, v in _cap["townhall"].items()}
CAP_STORAGE = {t: {int(k): v for k, v in lv.items()} for t, lv in _cap["storage"].items()}
INIT_OBSTACLES = load_table("init_obstacles.json")
OBSTACLE_EXP = load_table("obstacle_exp.json")       # chướng ngại -> kinh nghiệm khi dọn
BUILD_TIME = load_table("build_time.json")           # loại -> cấp -> giây xây/nâng cấp/dọn
RES_KEY = {"gold": "gold", "elixir": "elixir", "darkElixir": "dark_elixir"}
DECO = load_table("decoration.json")                # DEC_x -> coin (G), costExpire, time (giây hiệu lực), buff
ITEMS = load_table("items.json")                    # loại vật phẩm -> cấp -> value
_KQB = load_table("kqb.json")
HERO_HP = _KQB["hero_hp"]                            # KQB_x -> cấp -> máu anh hùng
for _t, _lv in _KQB["dark"].items():                # giá nhà anh hùng (dầu đen) bổ sung vào bảng giá
    COST.setdefault(_t, {k: [0, 0, v, 0] for k, v in _lv.items()})
ITEM_RES = {"1": "gold", "2": "elixir", "3": "dark_elixir", "16": "gold", "17": "elixir", "18": "dark_elixir"}   # túi tài nguyên trong kho đồ

# Nhóm danh sách trong BuildingInfo theo tiền tố tên (chỉ nhóm đã xác nhận định dạng qua readData).
CATEGORY = {"TOW": "townhall", "BAR": "barrack", "AMC": "armycamp", "LAB": "lab", "RES": "resources",
            "STO": "storage", "DEF": "defense", "CLC": "clancastle", "BDH": "builderhut", "TRA": "trap",
            "DEC": "decoration", "KQB": "kqbarrack", "WAL": "wall", "SPF": "spellfactory"}
SINGLE = {"townhall", "lab", "clancastle", "spellfactory"}
SINGLE_TYPE = {"kqbarrack"}                        # mỗi LOẠI chỉ 1 (KQB_1..KQB_5 mỗi cái 1 nhà)


def build_time(btype, level):
    return int(BUILD_TIME.get(btype, {}).get(str(level), 0) or 0)


def cost_of(btype, level):
    return COST.get(btype, {}).get(str(level), [0, 0, 0, 0])


IMAGE_MAP = load_table("image_map.json")


def _image_for(m, level):
    """Ảnh game chọn cho cấp này: JsonMgr::getImageName thử cấp, cấp-1, ... tới khi ContentName3 có mục."""
    lv = [int(k) for k in m if int(k) <= level]
    return m[str(max(lv))] if lv else 1


def display_level(btype, level):
    """Cấp gửi cho game = CẤP THẬT, trừ khi ảnh game sẽ chọn cho cấp đó không có trong dữ liệu (OBB) -> hạ xuống
    cấp cao nhất có ảnh (hiện chỉ DEF_4 cấp 9+ thiếu ảnh DEF_4_5).
    Bản <= 7.7 hạ cấp mỗi khi ContentName3 không liệt kê đúng cấp đó (AMC_1 cấp 9, DEF_1 16-17, LAB_1 10...) dù
    getImageName tự lùi về ảnh cấp gần nhất -> game hiện cấp thấp hơn, cho nâng lại, server báo đã tối đa
    -> vào lại / đi đánh là "quay về cấp cũ"."""
    m = IMAGE_MAP.get(btype)
    have = set(IMAGE_LEVELS.get(btype, []))
    if not m:
        return level
    if not have or _image_for(m, level) in have:
        return level
    ok = [l for l in range(level, 0, -1) if _image_for(m, l) in have]
    return ok[0] if ok else level


def max_level(btype):
    """Cấp cao nhất nâng được: theo bảng giá, và không vượt cấp cao nhất game vẽ được."""
    lv = sorted(int(k) for k in COST.get(btype, {}))
    if not lv:
        return None
    top = lv[-1]
    while top > 1 and display_level(btype, top) != top:
        top -= 1
    return top
