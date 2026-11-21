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
ITEM_RES = {"1": "gold", "2": "elixir", "3": "dark_elixir"}   # túi tài nguyên trong kho đồ

# Nhóm danh sách trong BuildingInfo theo tiền tố tên (chỉ nhóm đã xác nhận định dạng qua readData).
CATEGORY = {"TOW": "townhall", "BAR": "barrack", "AMC": "armycamp", "LAB": "lab", "RES": "resources",
            "STO": "storage", "DEF": "defense", "CLC": "clancastle", "BDH": "builderhut", "TRA": "trap",
            "DEC": "decoration", "KQB": "kqbarrack", "WAL": "wall"}
SINGLE = {"townhall", "lab", "clancastle"}
SINGLE_TYPE = {"kqbarrack"}                        # mỗi LOẠI chỉ 1 (KQB_1..KQB_5 mỗi cái 1 nhà)


def build_time(btype, level):
    return int(BUILD_TIME.get(btype, {}).get(str(level), 0) or 0)


def cost_of(btype, level):
    return COST.get(btype, {}).get(str(level), [0, 0, 0, 0])


IMAGE_MAP = load_table("image_map.json")


def display_level(btype, level):
    """Cấp gửi cho game. Game tự đổi cấp -> ảnh bằng ContentName3.json (JsonMgr::getImageName), nên được gửi
    CẤP THẬT nếu bảng có cấp đó VÀ ảnh nó trỏ tới có thật; không thì cấp hợp lệ cao nhất <= cấp thật.
    (Bản <= 7.3 so cấp với số ảnh: bệ anh hùng KQB chỉ có ảnh _1 nên luôn gửi cấp 1 -> anh hùng không lên cấp;
     DEF_2 có ảnh tới 9 nhưng game hỗ trợ tới 15...)"""
    m = IMAGE_MAP.get(btype)
    if m:
        have = set(IMAGE_LEVELS.get(btype, [])) or None
        ok = [int(l) for l, img in m.items() if have is None or img in have]
        if not ok:
            return level
        if level in ok:
            return level
        below = [l for l in ok if l <= level]
        return max(below) if below else min(ok)
    levels = IMAGE_LEVELS.get(btype, [])
    if not levels or level in levels:
        return level
    above = [l for l in levels if l >= level]
    return min(above) if above else max(levels)
