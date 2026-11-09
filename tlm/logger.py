"""Ghi log ra màn hình + log.txt; nén log cũ thành old_logs/log_<lúc tạo>.zip."""
import os
import re
import sys
import threading
import time
import zipfile

from . import config

_lock = threading.Lock()
LOG_FILE = OLD_DIR = BIN_DIR = None


def init():
    global LOG_FILE, OLD_DIR, BIN_DIR
    LOG_FILE = config.data_path("log.txt")
    OLD_DIR = config.data_path("old_logs")
    BIN_DIR = config.data_path("bin")
    os.makedirs(BIN_DIR, exist_ok=True)


def archive_old_log():
    bins = sorted(os.listdir(BIN_DIR)) if os.path.isdir(BIN_DIR) else []
    has_log = os.path.isfile(LOG_FILE) and os.path.getsize(LOG_FILE) > 0
    if not has_log and not bins:
        return None
    mtime = os.path.getmtime(LOG_FILE) if has_log else time.time()
    created = None
    if has_log:
        try:
            with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
                m = re.search(r"(\d{4}-\d\d-\d\d) (\d\d):(\d\d):(\d\d)", f.readline())
            if m:
                created = "%s_%s-%s-%s" % m.groups()
        except OSError:
            pass
    if not created:
        created = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(mtime))
    pretty = created.replace("_", " ", 1)
    pretty = pretty[:11] + pretty[11:].replace("-", ":")
    ended = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
    os.makedirs(OLD_DIR, exist_ok=True)
    path = os.path.join(OLD_DIR, "log_%s.zip" % created)
    n = 2
    while os.path.exists(path):
        path = os.path.join(OLD_DIR, "log_%s_%d.zip" % (created, n))
        n += 1
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        if has_log:
            z.write(LOG_FILE, "log.txt")
        for fn in bins:
            z.write(os.path.join(BIN_DIR, fn), "bin/" + fn)
        z.writestr("THONG_TIN.txt", "Log tạo lúc : %s\nKết thúc    : %s\nSố file bin : %d\n" % (pretty, ended, len(bins)))
    if has_log:
        os.remove(LOG_FILE)
    for fn in bins:
        try:
            os.remove(os.path.join(BIN_DIR, fn))
        except OSError:
            pass
    return path


def start():
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("# Log tạo lúc: %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        f.write("# ThoiLoanServer v%s | Python %s | dữ liệu %s | tự trả lời: %s\n"
                % (config.VERSION, sys.version.split()[0], config.DATA_DIR, "BẬT" if config.AUTO_REPLY else "TẮT"))


def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    with _lock:
        print(line, flush=True)
        if LOG_FILE:
            try:
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except OSError:
                pass


def hexdump(data, limit=config.HEXDUMP_LIMIT):
    shown = data[:limit]
    lines = []
    for off in range(0, len(shown), 16):
        chunk = shown[off:off + 16]
        hx = " ".join("%02x" % b for b in chunk)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append("    %04x  %-47s  %s" % (off, hx, asc))
    if len(data) > limit:
        lines.append("    ... (còn %d byte, xem file bin)" % (len(data) - limit))
    return "\n".join(lines)
