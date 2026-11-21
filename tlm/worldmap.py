"""CỔNG THẾ GIỚI (bản đồ đảo): chủ đảo + thu hoạch uranium. Gói tin xem tlm/handlers/worldmap.py.

Lưu trong kho phụ (bảng kv, nhóm "world", khoá "islands"):
  {"<id đảo>": {"acc", "uid", "name", "clan_id", "clan_name", "clan_icon", "since", "harvest"}}
Đảo id 0 = đảo nhà (bang mình, game tự vẽ), đảo 1..N = IslandMap.json theo thứ tự.
N = numIsland theo cấp bang (WorldMap.json "clan"), game tạo đúng N+1 đảo nên KHÔNG được gửi nhiều hơn
(WorldMapMgr::updateWorldMap ghép theo thứ tự, vượt quá -> vector::_M_range_check -> sập).

Uranium: đảo sản xuất config.production (120) / giờ, tối đa config.capacity (480) (IslandObject::loop, chờ 5 giây đầu).
Người thu hoạch được percentUranium % (KQB_3 = Kho uranium, KingQueenBuilding.json), phần còn lại vào quỹ bang;
tổng uranium của người chơi không vượt maxCapUranium của KQB_3.
"""
import threading
import time

from . import clans, state, storage
from .data import load_table

CFG = load_table("world_map.json")
_lock = threading.Lock()


def _kv():
    return storage.open_storage()


def load():
    return _kv().kv_get("world", "islands") or {}


def save(isl):
    _kv().kv_put("world", "islands", isl)


def clan_level(account):
    c = clans.clan_of(account)
    return max(1, min(len(CFG["clan"]), int(c.get("level", 1)) if c else 1))


def num_islands(account):
    return int(CFG["clan"][clan_level(account) - 1]["numIsland"])


def max_owner(account):
    return int(CFG["clan"][clan_level(account) - 1]["maxIslandOwner"])


def kqb3(st):
    """(% chia cho người thu hoạch, sức chứa uranium) theo cấp Kho uranium; (0, 0) nếu chưa xây."""
    lvl = max([b["level"] for b in st["buildings"] if b["type"] == "KQB_3"] or [0])
    if not lvl:
        return 0, 0
    pct, cap = CFG["kqb3"].get(str(min(lvl, len(CFG["kqb3"]))), (0, 0))
    return int(pct), int(cap)


def produced(rec, now=None):
    """Uranium đảo đã sản xuất từ lần thu hoạch trước (giống IslandObject::loop)."""
    el = int((now or time.time()) - float(rec.get("harvest", rec.get("since", 0))))
    if el <= 5:
        return 0
    c = CFG["config"]
    return int(min(c["capacity"], (el - 5) * c["production"] / 3600.0))


def owner_entry(account, st):
    c = clans.clan_of(account)
    return {"acc": account, "uid": clans.uid_of(account), "name": str(st["player"].get("name", account)),
            "clan_id": int(c["id"]) if c else 0, "clan_name": c["name"] if c else "",
            "clan_icon": int(c.get("icon", 1)) if c else 0}


def capture(account, st, iid):
    """Người chơi chiếm đảo iid. Vượt quá maxIslandOwner -> bỏ đảo chiếm lâu nhất. Trả về (chủ cũ, đảo bị bỏ)."""
    now = int(time.time())
    with _lock:
        isl = load()
        old = isl.get(str(iid), {}).get("name")
        e = owner_entry(account, st)
        e.update(since=now, harvest=now)
        isl[str(iid)] = e
        mine = sorted((int(k) for k, v in isl.items() if v.get("acc") == account and int(k) != iid),
                      key=lambda k: isl[str(k)].get("since", 0))
        dropped = []
        while len(mine) + 1 > max_owner(account):
            k = mine.pop(0)
            dropped.append(k)
            isl.pop(str(k), None)
        save(isl)
    return old, dropped


def harvest(account, st, iid):
    """Thu hoạch đảo iid -> (uranium nhận, tổng uranium, giờ thu hoạch) hoặc None nếu không phải đảo của mình."""
    now = int(time.time())
    with _lock:
        isl = load()
        rec = isl.get(str(iid))
        if not rec or rec.get("acc") != account:
            return None
        amount = produced(rec, now)
        rec["harvest"] = now
        save(isl)
    pct, cap = kqb3(st)
    p = st["player"]
    cur = int(p.get("uranium", 0))
    gain = max(0, min(amount * pct // 100, cap - cur))
    p["uranium"] = cur + gain
    c = clans.clan_of(account)
    if c is not None and amount - gain > 0:
        with clans._lock:
            c["uranium"] = int(c.get("uranium", 0)) + amount - amount * pct // 100
            clans.save()
    return gain, p["uranium"], now, amount


def refresh_names(account, st):
    """Đổi tên / bang -> cập nhật trên các đảo đang giữ."""
    with _lock:
        isl = load()
        e = owner_entry(account, st)
        changed = False
        for v in isl.values():
            if v.get("acc") == account and any(v.get(k) != e[k] for k in e):
                v.update(e)
                changed = True
        if changed:
            save(isl)
