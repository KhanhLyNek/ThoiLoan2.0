"""Trạng thái người chơi, MỖI TÀI KHOẢN MỘT BẢN (lưu qua tầng storage: JSON / SQLite / MySQL).

Tài khoản = sessionKey lúc đăng nhập: "<google|facebook|zalo>-<deviceId>".
state.json cũ (bản 3.x) được tự gán cho tài khoản ĐẦU TIÊN đăng nhập (đổi tên thành state.json.da_chuyen).

Cấu trúc một state:
  player     : tên, cấp, kinh nghiệm, vàng, dầu, dầu đen, G, tutorial_step
  buildings  : [{id, type, x, y, level, (collected_at)}]
               id đánh THEO NHÓM (3 chữ đầu của loại: RES, STO, DEF...), 1, 2, 3... giống game:
               game tự cấp id công trình mới = số công trình cùng nhóm + 1 (thấy trong log:
               STO_2 đầu tiên -> id 1, RES_2 khi đã có RES_1 -> id 2).
  obstacles  : [{id, type, x, y}]
Sửa qua trang quản trị http://127.0.0.1:8080/admin (hoặc sửa file khi server tắt).
"""
import json
import os
import threading

from . import config, gamedata, storage
from .logger import log

_lock = threading.RLock()
DEFAULT_ACCOUNT = "default"

# tutorial_step: tiến độ hướng dẫn (ô @0x110 của GetPlayerInfo). Game coi hướng dẫn CÒN ĐANG CHẠY khi
# <= 69 (TutorialMgr::isDoing) và khi đó khoá tab cửa hàng, hộp nâng cấp, luyện quân. 70 = đã xong.
TUTORIAL_DONE = 70
DEFAULT_PLAYER = {"name": "Khach", "level": 1, "exp": 0,
                  "gold": 5000, "elixir": 5000, "dark_elixir": 0, "coin": 1000,
                  "tutorial_step": TUTORIAL_DONE}
DEFAULT_BUILDINGS = [
    {"id": 1, "type": "TOW_1", "x": 20, "y": 19, "level": 1 if config.USE_OBB else 10},
    {"id": 2, "type": "AMC_1", "x": 20, "y": 24, "level": 1},
    {"id": 3, "type": "RES_1", "x": 25, "y": 19, "level": 1},
]
DEFAULT_BUILDER_HUT = {"id": 4, "type": "BDH_1", "x": 18, "y": 21, "level": 1}


def _legacy_path():
    return config.data_path("state.json")


def save(st, account=DEFAULT_ACCOUNT):
    with _lock:
        storage.open_storage().put(account, st)


def new_state():
    return {"buildings": [dict(b) for b in DEFAULT_BUILDINGS]}


def load(account=DEFAULT_ACCOUNT):
    """Đọc state của tài khoản; tạo mới (hoặc nhận làng cũ state.json) và bổ sung khoá thiếu."""
    with _lock:
        st = storage.open_storage().get(account)
        changed = False
        if not st or not st.get("buildings"):
            st, changed = None, True
            legacy = _legacy_path()
            if os.path.isfile(legacy):
                try:
                    with open(legacy, "r", encoding="utf-8") as f:
                        st = json.load(f)
                    os.replace(legacy, legacy + ".da_chuyen")
                    log("Đã chuyển làng cũ (state.json) sang tài khoản %s" % account)
                except (OSError, ValueError):
                    st = None
            if not st or not st.get("buildings"):
                st = new_state()
        st.setdefault("player", {})
        for k, v in DEFAULT_PLAYER.items():
            if k not in st["player"]:
                st["player"][k] = v
                changed = True
        if st["player"].get("tutorial_step") == 69:      # 69 = "bỏ qua" của bản cũ, thực ra vẫn đang chạy
            st["player"]["tutorial_step"] = TUTORIAL_DONE
            changed = True
        if st.get("id_scheme") != "per_category":     # state cũ đánh id chung -> đánh lại theo nhóm
            seen = {}
            for b in st["buildings"]:
                cat = b["type"][:3]
                seen[cat] = seen.get(cat, 0) + 1
                b["id"] = seen[cat]
            st["id_scheme"] = "per_category"
            changed = True
        if config.USE_OBB:
            if not any(b["type"].startswith("BDH") for b in st["buildings"]):
                hut = dict(DEFAULT_BUILDER_HUT)
                hut["id"] = next_id(st, hut["type"])
                st["buildings"].append(hut)
                changed = True
            if "obstacles" not in st:
                st["obstacles"] = [dict(o) for o in gamedata.INIT_OBSTACLES]
                changed = True
        if changed:
            save(st, account)
        return st


def list_accounts():
    return storage.open_storage().keys()


def next_id(st, btype):
    """id cho công trình mới = số công trình cùng nhóm + 1 (giống cách game tự cấp)."""
    cat = btype[:3]
    return max([b["id"] for b in st["buildings"] if b["type"][:3] == cat] or [0]) + 1


def find_building(st, bid, btype=None, category=None):
    """Tìm theo (nhóm, id). id chỉ duy nhất trong nhóm nên luôn cần loại hoặc nhóm."""
    cat = category or (btype[:3] if btype else None)
    return next((b for b in st["buildings"] if b["id"] == bid and (cat is None or b["type"][:3] == cat)), None)


def capacities(st):
    """Sức chứa (vàng, dầu, dầu đen) = nhà chính + các kho."""
    gold = elixir = dark = 0
    for b in st["buildings"]:
        if b["type"] == "TOW_1":
            g, e, d = gamedata.CAP_TOWNHALL.get(b["level"], [0, 0, 0])
            gold += g; elixir += e; dark += d
        elif b["type"] in gamedata.CAP_STORAGE:
            c = gamedata.CAP_STORAGE[b["type"]].get(b["level"], 0)
            if b["type"] == "STO_1":
                gold += c
            elif b["type"] == "STO_2":
                elixir += c
            else:
                dark += c
    return gold, elixir, dark


def effective_resources(st):
    """Số tài nguyên thực có = min(số lưu, sức chứa) (gửi quá sức chứa thì game hiện 0)."""
    p = st["player"]
    cg, ce, cd = capacities(st)
    return (min(int(p.get("gold", 0)), cg), min(int(p.get("elixir", 0)), ce),
            min(int(p.get("dark_elixir", 0)), cd), int(p.get("coin", 0)), (cg, ce, cd))


def pay(st, btype, level):
    """Trừ giá xây/nâng cấp theo bảng cost.json, trên số thực có."""
    c = gamedata.cost_of(btype, level)
    gold, elixir, dark, coin, _ = effective_resources(st)
    p = st["player"]
    p["gold"], p["elixir"], p["dark_elixir"], p["coin"] = (
        max(0, gold - c[0]), max(0, elixir - c[1]), max(0, dark - c[2]), max(0, coin - c[3]))
    return c


def add_resource(st, key, amount):
    gold, elixir, dark, coin, (cg, ce, cd) = effective_resources(st)
    cur = {"gold": gold, "elixir": elixir, "dark_elixir": dark}[key]
    limit = {"gold": cg, "elixir": ce, "dark_elixir": cd}[key]
    st["player"][key] = min(limit, cur + amount)
    return st["player"][key]
