"""Tầng lưu trữ tài khoản: mỗi tài khoản là một "state" (dict) như state.json cũ.

Chọn kiểu lưu bằng file db.json trong thư mục dữ liệu (/sdcard/ThoiLoan2.0/db.json):
  {"type": "json"}                                     mặc định: thư mục accounts/, mỗi tài khoản 1 file
  {"type": "sqlite", "file": "thoiloan.db"}            SQLite có sẵn trong Python
  {"type": "mysql", "host": "127.0.0.1", "port": 3306,
   "user": "tlm", "password": "tlm123", "database": "thoiloan"}   cần: pip install pymysql
Khi chuyển sang SQLite/MySQL lần đầu (bảng rỗng), các tài khoản JSON có sẵn được tự chép sang.
"""
import json
import os
import re
import threading
import time

from . import config
from .logger import log

TABLE_SQL = ("CREATE TABLE IF NOT EXISTS accounts ("
             "account_key VARCHAR(128) PRIMARY KEY, "
             "name VARCHAR(64), "
             "data LONGTEXT NOT NULL, "
             "updated_at BIGINT NOT NULL)")


class JsonStorage:
    kind = "json"

    def __init__(self, folder):
        self.folder = folder
        os.makedirs(folder, exist_ok=True)
        self.lock = threading.RLock()

    def _path(self, key):
        return os.path.join(self.folder, re.sub(r"[^A-Za-z0-9_.@-]", "_", key) + ".json")

    def get(self, key):
        with self.lock:
            try:
                with open(self._path(key), "r", encoding="utf-8") as f:
                    return json.load(f)
            except (FileNotFoundError, ValueError):
                return None

    def put(self, key, st):
        with self.lock:
            st["_account"] = key
            tmp = self._path(key) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(st, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self._path(key))

    def keys(self):
        out = []
        for fn in sorted(os.listdir(self.folder)):
            if fn.endswith(".json"):
                st = self.get_file(os.path.join(self.folder, fn))
                if st:
                    out.append(st.get("_account") or fn[:-5])
        return out

    @staticmethod
    def get_file(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def delete(self, key):
        with self.lock:
            try:
                os.remove(self._path(key))
            except FileNotFoundError:
                pass


class SqlStorage:
    """Dùng chung cho SQLite và MySQL (chỉ khác kiểu tham số và câu upsert)."""

    def __init__(self, connect, dialect):
        self.connect, self.dialect = connect, dialect
        self.kind = dialect
        self.ph = "?" if dialect == "sqlite" else "%s"
        self.lock = threading.RLock()
        self._run(TABLE_SQL)

    def _run(self, sql, args=(), fetch=False):
        with self.lock:
            conn = self.connect()
            try:
                cur = conn.cursor()
                cur.execute(sql, args)
                rows = cur.fetchall() if fetch else None
                conn.commit()
                return rows
            finally:
                conn.close()

    def get(self, key):
        rows = self._run("SELECT data FROM accounts WHERE account_key=%s" % self.ph, (key,), fetch=True)
        return json.loads(rows[0][0]) if rows else None

    def put(self, key, st):
        st["_account"] = key
        data = json.dumps(st, ensure_ascii=False)
        name = str(st.get("player", {}).get("name", ""))[:64]
        now = int(time.time())
        if self.dialect == "sqlite":
            sql = ("INSERT INTO accounts(account_key,name,data,updated_at) VALUES(?,?,?,?) "
                   "ON CONFLICT(account_key) DO UPDATE SET name=excluded.name, data=excluded.data, "
                   "updated_at=excluded.updated_at")
        else:
            sql = ("INSERT INTO accounts(account_key,name,data,updated_at) VALUES(%s,%s,%s,%s) "
                   "ON DUPLICATE KEY UPDATE name=VALUES(name), data=VALUES(data), updated_at=VALUES(updated_at)")
        self._run(sql, (key, name, data, now))

    def keys(self):
        return [r[0] for r in self._run("SELECT account_key FROM accounts ORDER BY account_key", fetch=True)]

    def delete(self, key):
        self._run("DELETE FROM accounts WHERE account_key=%s" % self.ph, (key,))


_store = None


def _read_cfg():
    try:
        with open(config.data_path("db.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"type": "json"}
    except ValueError as e:
        log("!! db.json sai định dạng (%s), dùng lưu JSON." % e)
        return {"type": "json"}


def open_storage():
    """Mở kho lưu theo db.json. Không mở được SQLite/MySQL thì báo rõ và dừng server."""
    global _store
    if _store is not None:
        return _store
    cfg = _read_cfg()
    json_store = JsonStorage(config.data_path("accounts"))
    kind = cfg.get("type", "json")
    try:
        if kind == "sqlite":
            import sqlite3
            path = cfg.get("file", "thoiloan.db")
            path = path if os.path.isabs(path) else config.data_path(path)
            _store = SqlStorage(lambda: sqlite3.connect(path), "sqlite")
        elif kind == "mysql":
            try:
                import pymysql
            except ImportError:
                raise RuntimeError("chưa cài thư viện pymysql (chạy: pip install pymysql)")
            params = dict(host=cfg.get("host", "127.0.0.1"), port=int(cfg.get("port", 3306)),
                          user=cfg.get("user", "root"), password=cfg.get("password", ""),
                          database=cfg.get("database", "thoiloan"), charset="utf8mb4")
            _store = SqlStorage(lambda: pymysql.connect(**params), "mysql")
        else:
            _store = json_store
    except Exception as e:
        # Không tự dùng tạm JSON: dữ liệu thật đang nằm trong SQLite/MySQL, chơi trên bản JSON cũ sẽ lệch.
        log("!! KHÔNG MỞ ĐƯỢC KHO LƯU '%s': %s" % (kind, e))
        log("!! Kiểm tra MySQL đã chạy chưa và thông tin trong db.json, hoặc xoá db.json để dùng lưu JSON.")
        raise SystemExit(1)
    if _store is not json_store and not _store.keys():
        moved = 0
        for k in json_store.keys():
            st = json_store.get(k)
            if st:
                _store.put(k, st)
                moved += 1
        if moved:
            log("Đã chép %d tài khoản từ accounts/ (JSON) sang %s." % (moved, _store.kind))
    return _store
