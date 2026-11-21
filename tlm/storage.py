"""Tầng lưu trữ tài khoản: mỗi tài khoản là một "state" (dict) như state.json cũ.

Chọn kiểu lưu bằng file db.json trong thư mục dữ liệu (/sdcard/ThoiLoan2.0/db.json):
  {"type": "sqlite", "file": "thoiloan.db"}            MẶC ĐỊNH (từ v6.9): SQLite có sẵn trong Python, chế độ
                                                       WAL + synchronous=FULL -> mỗi thao tác ghi xong là nằm
                                                       chắc trên bộ nhớ, tắt game / tắt Termux / sập nguồn không mất
  {"type": "json"}                                     cũ: thư mục accounts/, mỗi tài khoản 1 file
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
# kho khoá-giá trị phụ (dữ liệu xem lại trận...): ns = nhóm, k = khoá
KV_SQL = ("CREATE TABLE IF NOT EXISTS kv ("
          "ns VARCHAR(32) NOT NULL, "
          "k VARCHAR(128) NOT NULL, "
          "data LONGTEXT NOT NULL, "
          "updated_at BIGINT NOT NULL, "
          "PRIMARY KEY (ns, k))")


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
                f.flush()
                os.fsync(f.fileno())               # ghi hẳn xuống bộ nhớ trước khi thay file cũ
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

    # --- kho phụ: thư mục <dữ liệu>/<ns>/<khoá>.json ---
    def _kv_path(self, ns, k):
        folder = os.path.join(os.path.dirname(self.folder), ns)
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, re.sub(r"[^A-Za-z0-9_.@-]", "_", str(k)) + ".json")

    def kv_get(self, ns, k):
        return self.get_file(self._kv_path(ns, k))

    def kv_put(self, ns, k, obj):
        with self.lock:
            path = self._kv_path(ns, k)
            with open(path + ".tmp", "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(path + ".tmp", path)

    def kv_delete(self, ns, k):
        try:
            os.remove(self._kv_path(ns, k))
        except FileNotFoundError:
            pass

    def kv_prune(self, ns, before):
        """Xoá mục cập nhật trước thời điểm `before` (giây). Trả về số mục đã xoá."""
        folder = os.path.dirname(self._kv_path(ns, "x"))
        n = 0
        for fn in os.listdir(folder):
            p = os.path.join(folder, fn)
            if fn.endswith(".json") and os.path.getmtime(p) < before:
                os.remove(p)
                n += 1
        return n


class SqlStorage:
    """Dùng chung cho SQLite và MySQL (chỉ khác kiểu tham số và câu upsert)."""

    def __init__(self, connect, dialect):
        self.connect, self.dialect = connect, dialect
        self.kind = dialect
        self.ph = "?" if dialect == "sqlite" else "%s"
        self.lock = threading.RLock()
        self._run(TABLE_SQL)
        self._run(KV_SQL)

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

    # --- kho phụ (bảng kv) ---
    def kv_get(self, ns, k):
        rows = self._run("SELECT data FROM kv WHERE ns=%s AND k=%s" % (self.ph, self.ph), (ns, str(k)), fetch=True)
        return json.loads(rows[0][0]) if rows else None

    def kv_put(self, ns, k, obj):
        data, now = json.dumps(obj, ensure_ascii=False), int(time.time())
        if self.dialect == "sqlite":
            sql = ("INSERT INTO kv(ns,k,data,updated_at) VALUES(?,?,?,?) ON CONFLICT(ns,k) DO UPDATE SET "
                   "data=excluded.data, updated_at=excluded.updated_at")
        else:
            sql = ("INSERT INTO kv(ns,k,data,updated_at) VALUES(%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
                   "data=VALUES(data), updated_at=VALUES(updated_at)")
        self._run(sql, (ns, str(k), data, now))

    def kv_delete(self, ns, k):
        self._run("DELETE FROM kv WHERE ns=%s AND k=%s" % (self.ph, self.ph), (ns, str(k)))

    def kv_prune(self, ns, before):
        n = len(self._run("SELECT k FROM kv WHERE ns=%s AND updated_at<%s" % (self.ph, self.ph), (ns, int(before)),
                          fetch=True))
        self._run("DELETE FROM kv WHERE ns=%s AND updated_at<%s" % (self.ph, self.ph), (ns, int(before)))
        return n


_store = None


def _read_cfg():
    try:
        with open(config.data_path("db.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"type": "sqlite", "file": "thoiloan.db"}
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

            def _connect():
                conn = sqlite3.connect(path, timeout=30)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=FULL")
                return conn
            _store = SqlStorage(_connect, "sqlite")
            _store.path = path
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


def backup(keep=7):
    """Sao lưu kho lưu vào thư mục backups/ (1 bản mỗi ngày, giữ `keep` bản mới nhất)."""
    st = open_storage()
    folder = config.data_path("backups")
    os.makedirs(folder, exist_ok=True)
    day = time.strftime("%Y%m%d")
    try:
        if getattr(st, "kind", "") == "sqlite":
            import sqlite3
            dst = os.path.join(folder, "thoiloan_%s.db" % day)
            src = sqlite3.connect(st.path)
            out = sqlite3.connect(dst)
            with out:
                src.backup(out)
            src.close(); out.close()
        else:
            dst = os.path.join(folder, "accounts_%s.json" % day)
            data = {k: st.get(k) for k in st.keys()}
            with open(dst, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        for extra in ("clans.json",):
            src = config.data_path(extra)
            if os.path.isfile(src):
                import shutil
                shutil.copyfile(src, os.path.join(folder, "%s_%s" % (day, extra)))
        files = sorted(f for f in os.listdir(folder) if f[:1] in "act0123456789")
        days = sorted({re.sub(r"\D", "", f)[:8] for f in files}, reverse=True)
        for f in files:
            if re.sub(r"\D", "", f)[:8] not in days[:keep]:
                os.remove(os.path.join(folder, f))
        log("Đã sao lưu dữ liệu vào %s" % folder)
    except Exception as e:
        log("!! sao lưu lỗi: %s" % e)


def backup_loop():
    """Chạy nền: sao lưu lúc khởi động rồi mỗi 6 giờ; dọn dữ liệu xem lại trận quá cũ."""
    while True:
        backup()
        try:
            from . import replays
            replays.prune()
        except Exception as e:
            log("!! dọn dữ liệu xem lại lỗi: %s" % e)
        time.sleep(6 * 3600)
