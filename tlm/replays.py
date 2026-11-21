"""Nhật ký trận đấu + dữ liệu XEM LẠI (giống game gốc: hộp thư "Báo cáo trận", nút Xem lại / Trả thù).

Mỗi trận chinh phạt (đánh làng máy hoặc người chơi thật) tạo:
  - 1 bản ghi xem lại trong kho phụ (bảng kv, nhóm "replay", khoá = số id):
      {"id", "t", "attacker", "att_name", "defender", "def_name", "th", "base": [công trình lúc đánh, kèm tài nguyên],
       "actions": [[lính, ô, cấp, nhịp]], "clan": {lính: [cấp, số]}, "end_tick", "stars", "percent", "loot": [v, d, dđ]}
  - 1 dòng trong st["attack_log"] của người đánh, và (nếu đánh người thật) 1 dòng trong st["defense_log"] người bị đánh:
      {"id", "t", "uid", "acc", "name", "clan_name", "clan_icon", "trophy", "tchange", "stars", "percent",
       "loot": [...], "troops": {lính: [cấp, số]}, "clan_troops": {...}, "replay": True, "revenged": False}
Nhịp (tick) = bộ đếm vòng lặp trận của game, 30 nhịp / giây (9012 gửi 300, 600, ... mỗi 10 giây).
Bản ghi xem lại cũ hơn KEEP_DAYS ngày tự xoá (storage.backup_loop -> prune).
"""
import threading
import time

from . import storage

KEEP_LOG = 30            # số dòng nhật ký giữ lại mỗi loại
KEEP_DAYS = 30
_lock = threading.Lock()


def _kv():
    return storage.open_storage()


def new_id():
    with _lock:
        meta = _kv().kv_get("meta", "replay") or {"next": 1}
        rid = int(meta["next"])
        meta["next"] = rid + 1
        _kv().kv_put("meta", "replay", meta)
        return rid


def save(rec):
    _kv().kv_put("replay", rec["id"], rec)


def get(rid):
    return _kv().kv_get("replay", int(rid))


def add_log(st, kind, entry):
    """kind = "attack_log" | "defense_log"; dòng mới nhất ở cuối, giữ KEEP_LOG dòng."""
    log = st.setdefault(kind, [])
    log.append(entry)
    del log[:-KEEP_LOG]


def prune():
    n = _kv().kv_prune("replay", time.time() - KEEP_DAYS * 86400)
    if n:
        from .logger import log
        log("Đã xoá %d bản ghi xem lại trận cũ hơn %d ngày" % (n, KEEP_DAYS))
