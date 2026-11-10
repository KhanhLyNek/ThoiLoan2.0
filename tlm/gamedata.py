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

# Nhóm danh sách trong BuildingInfo theo tiền tố tên (chỉ nhóm đã xác nhận định dạng qua readData).
CATEGORY = {"TOW": "townhall", "BAR": "barrack", "AMC": "armycamp", "LAB": "lab", "RES": "resources",
            "STO": "storage", "DEF": "defense", "BDH": "builderhut", "TRA": "trap"}
SINGLE = {"townhall", "lab"}


def build_time(btype, level):
    return int(BUILD_TIME.get(btype, {}).get(str(level), 0) or 0)


def cost_of(btype, level):
    return COST.get(btype, {}).get(str(level), [0, 0, 0, 0])


def display_level(btype, level):
    """Cấp dùng để hiển thị: cấp thật nếu có ảnh, nếu không thì cấp có ảnh gần nhất."""
    levels = IMAGE_LEVELS.get(btype, [])
    if not levels or level in levels:
        return level
    above = [l for l in levels if l >= level]
    return min(above) if above else max(levels)
