"""Trạng thái người chơi (lưu state.json trong thư mục dữ liệu).

Cấu trúc state.json:
  player     : tên, cấp, kinh nghiệm, vàng, dầu, dầu đen, G, tutorial_step
  buildings  : [{id, type, x, y, level, (collected_at)}]
  obstacles  : [{id, type, x, y}]
Sửa tay được (tắt server trước), xoá file = làng về ban đầu.
"""
import json
import os
import threading

from . import config, gamedata

_lock = threading.RLock()

# tutorial_step: tiến độ hướng dẫn (ô @0x110 của GetPlayerInfo). > 68 = đã xong. 69 = bỏ qua.
DEFAULT_PLAYER = {"name": "Khach", "level": 1, "exp": 0,
                  "gold": 5000, "elixir": 5000, "dark_elixir": 0, "coin": 1000,
                  "tutorial_step": 69}
DEFAULT_BUILDINGS = [
    {"id": 1, "type": "TOW_1", "x": 20, "y": 19, "level": 1 if config.USE_OBB else 10},
    {"id": 2, "type": "AMC_1", "x": 20, "y": 24, "level": 1},
    {"id": 3, "type": "RES_1", "x": 25, "y": 19, "level": 1},
]
DEFAULT_BUILDER_HUT = {"id": 4, "type": "BDH_1", "x": 18, "y": 21, "level": 1}


def _path():
    return config.data_path("state.json")


def save(st):
    with _lock:
        tmp = _path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=1)
        os.replace(tmp, _path())


def load():
    """Đọc state.json; tạo mới hoặc bổ sung các khoá thiếu (tương thích state cũ)."""
    with _lock:
        st = None
        try:
            with open(_path(), "r", encoding="utf-8") as f:
                st = json.load(f)
            if not st.get("buildings"):
                st = None
        except (FileNotFoundError, ValueError):
            st = None
        changed = st is None
        if st is None:
            st = {"buildings": [dict(b) for b in DEFAULT_BUILDINGS]}
        st.setdefault("player", {})
        for k, v in DEFAULT_PLAYER.items():
            if k not in st["player"]:
                st["player"][k] = v
                changed = True
        if config.USE_OBB:
            if not any(b["type"].startswith("BDH") for b in st["buildings"]):
                hut = dict(DEFAULT_BUILDER_HUT)
                hut["id"] = next_id(st)
                st["buildings"].append(hut)
                changed = True
            if "obstacles" not in st:
                st["obstacles"] = [dict(o) for o in gamedata.INIT_OBSTACLES]
                changed = True
        if changed:
            save(st)
        return st


def next_id(st):
    return max([b["id"] for b in st["buildings"]] or [0]) + 1


def find_building(st, bid):
    return next((b for b in st["buildings"] if b["id"] == bid), None)


def capacities(st=None):
    """Sức chứa (vàng, dầu, dầu đen) = nhà chính + các kho."""
    st = st or load()
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
