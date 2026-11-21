"""Kho bang hội dùng chung cho mọi tài khoản: file clans.json trong thư mục dữ liệu.

{"next_id": 1001, "next_uid": 2, "uids": {tài khoản: uid},
 "clans": {"1001": {"id", "name", "icon", "type", "min_trophy", "desc", "level", "created",
                    "members": [{"uid", "account", "name", "role", "level", "trophy", "donated", "received"}],
                    "chat": [{"uid", "msg", "t"}]}}}
role: 1 bang chủ, 2 phó bang chủ, 3 thành viên (CLAN_TITLE_1..3).
Thành viên có "account" = người chơi thật; không có = thành viên máy (bang máy có sẵn để vào thử).
"""
import json
import os
import threading
import time

from . import config

_lock = threading.RLock()
_cache = None
CHAT_KEEP = 50

BOT_CLANS = [
    ("Rồng Lửa", 3, 0, "Bang vui vẻ, ai cũng vào được!", ["Hắc Long", "Bạch Hổ", "Thanh Phong", "Mộc Lan"]),
    ("Thiên Hạ Đệ Nhất", 7, 0, "Chiến hết mình, xin quân thả ga", ["Kiếm Thánh", "Đao Vương", "Tiểu Long"]),
    ("Làng Bình Yên", 12, 0, "Bang cho người mới", ["Nông Dân", "Bé Na", "Ông Ba", "Cô Tư", "Anh Năm"]),
]


def _path():
    return config.data_path("clans.json")


def _seed(db):
    uid = 900001
    for name, icon, ctype, desc, mems in BOT_CLANS:
        cid = db["next_id"]; db["next_id"] += 1
        members = []
        for i, mn in enumerate(mems):
            members.append({"uid": uid, "name": mn, "role": 1 if i == 0 else (2 if i == 1 else 3),
                            "level": 20 + 7 * i % 30, "trophy": 1500 - 150 * i, "donated": 50 * (5 - i),
                            "received": 30 * i})
            uid += 1
        db["clans"][str(cid)] = {"id": cid, "name": name, "icon": icon, "type": ctype, "min_trophy": 0,
                                 "desc": desc, "level": 1, "created": int(time.time()), "members": members,
                                 "chat": []}


def db():
    global _cache
    with _lock:
        if _cache is None:
            try:
                with open(_path(), "r", encoding="utf-8") as f:
                    _cache = json.load(f)
            except (OSError, ValueError):
                _cache = {"next_id": 1001, "next_uid": 1, "uids": {}, "clans": {}}
                _seed(_cache)
                save()
        return _cache


def save():
    with _lock:
        if _cache is None:
            return
        tmp = _path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, _path())


def uid_of(account):
    """userId của tài khoản (tài khoản đầu tiên = 1 như trước)."""
    with _lock:
        d = db()
        if account not in d["uids"]:
            d["uids"][account] = d["next_uid"]
            d["next_uid"] += 1
            save()
        return d["uids"][account]


def account_of_uid(uid):
    """Ngược lại của uid_of: userId -> tài khoản (None nếu không có / là người máy)."""
    for acc, u in db()["uids"].items():
        if int(u) == int(uid):
            return acc
    return None


def get(cid):
    return db()["clans"].get(str(int(cid)))


def clan_of(account):
    for c in db()["clans"].values():
        if any(m.get("account") == account for m in c["members"]):
            return c
    return None


def clan_id_of(account):
    c = clan_of(account)
    return c["id"] if c else 0


def member(c, account=None, uid=None):
    for m in c["members"]:
        if (account is not None and m.get("account") == account) or (uid is not None and m["uid"] == uid):
            return m
    return None


def create(account, uid, pname, plevel, trophy, name, icon, ctype, min_trophy, desc):
    with _lock:
        d = db()
        leave(account)
        cid = d["next_id"]; d["next_id"] += 1
        c = {"id": cid, "name": name, "icon": icon, "type": ctype, "min_trophy": min_trophy, "desc": desc,
             "level": 1, "created": int(time.time()), "chat": [],
             "members": [{"uid": uid, "account": account, "name": pname, "role": 1, "level": plevel,
                          "trophy": trophy, "donated": 0, "received": 0}]}
        d["clans"][str(cid)] = c
        save()
        return c


def join(account, uid, pname, plevel, trophy, cid):
    with _lock:
        c = get(cid)
        if c is None:
            return None
        leave(account)
        c["members"].append({"uid": uid, "account": account, "name": pname, "role": 3, "level": plevel,
                             "trophy": trophy, "donated": 0, "received": 0})
        save()
        return c


def leave(account):
    """Rời bang. Bang chủ rời -> người có chức cao nhất còn lại lên thay; bang trống (không còn ai) -> xoá."""
    with _lock:
        c = clan_of(account)
        if c is None:
            return None
        m = member(c, account=account)
        c["members"].remove(m)
        if not c["members"]:
            del db()["clans"][str(c["id"])]
        elif m["role"] == 1 and not any(x["role"] == 1 for x in c["members"]):
            min(c["members"], key=lambda x: (x["role"], -x["trophy"]))["role"] = 1
        save()
        return c


def search(text):
    text = (text or "").strip().lower()
    out = []
    for c in db()["clans"].values():
        if not text or text in c["name"].lower() or text == str(c["id"]):
            out.append(c)
    return out[:50]


def refresh_member(account, pname, plevel, trophy):
    """Cập nhật tên/cấp/cúp của người chơi trong bang (gọi lúc tải người chơi)."""
    with _lock:
        c = clan_of(account)
        if c is None:
            return
        m = member(c, account=account)
        if (m["name"], m["level"], m["trophy"]) != (pname, plevel, trophy):
            m["name"], m["level"], m["trophy"] = pname, plevel, trophy
            save()
