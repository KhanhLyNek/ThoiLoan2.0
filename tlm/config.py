"""Cấu hình chung: cổng, IP, tuỳ chọn dòng lệnh, thư mục dữ liệu."""
import os
import sys

VERSION = "4.5"
FOLDER_NAME = "ThoiLoan2.0"          # thư mục dữ liệu ngoài bộ nhớ chung (log, state.json...)

BIND_HOST = "0.0.0.0"
PUBLIC_IP = os.environ.get("TLM_IP", "127.0.0.1")   # IP game kết nối tới (cùng máy = 127.0.0.1)
HTTP_PORT = int(os.environ.get("TLM_HTTP_PORT", 8080))
GAME_PORT = int(os.environ.get("TLM_GAME_PORT", 9000))
CHAT_PORT = int(os.environ.get("TLM_CHAT_PORT", 9001))
HEXDUMP_LIMIT = 256

ARGS = sys.argv[1:]
AUTO_REPLY = "--no-auto" not in ARGS      # tự trả lời mọi lệnh game có handler
AUTO_PAD = 0 if "--empty" in ARGS else 512  # số byte 0 đệm cho phản hồi tự động
PUSH_ENABLED = "--no-push" not in ARGS    # tự đẩy dữ liệu làng sau getUserInfo / về nhà
USE_OBB = "--no-obb" not in ARGS          # đã đặt OBB main.1380 -> dùng ảnh APK + OBB
ADMIN_REMOTE = "--admin-remote" in ARGS   # cho máy khác trong mạng mở trang /admin (mặc định chỉ máy này)

DATA_DIR = None          # gán trong init_data_dir()
SHARED_OK = False


def init_data_dir():
    """Chọn thư mục dữ liệu: TLM_HOME, rồi /sdcard/ThoiLoan2.0, cuối cùng ~/ThoiLoan2.0."""
    global DATA_DIR, SHARED_OK
    env = os.environ.get("TLM_HOME")
    if env:
        os.makedirs(env, exist_ok=True)
        DATA_DIR, SHARED_OK = env, True
        return DATA_DIR
    for root in ("/storage/emulated/0", "/sdcard", os.path.expanduser("~/storage/shared")):
        if os.path.isdir(root) and os.access(root, os.W_OK):
            path = os.path.join(root, FOLDER_NAME)
            try:
                os.makedirs(path, exist_ok=True)
                DATA_DIR, SHARED_OK = path, True
                return DATA_DIR
            except OSError:
                continue
    DATA_DIR = os.path.join(os.path.expanduser("~"), FOLDER_NAME)
    os.makedirs(DATA_DIR, exist_ok=True)
    return DATA_DIR


def data_path(name):
    return os.path.join(DATA_DIR, name)
