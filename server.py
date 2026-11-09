#!/usr/bin/env python3
"""ThoiLoanServer - server giả Thời Loạn Mobile chạy localhost (Termux).

Chạy:   python server.py              (dừng: Ctrl+C)
Tuỳ chọn:
  --no-auto   tắt tự trả lời các lệnh chưa có handler
  --empty     tự trả lời với dữ liệu rỗng thay vì đệm số 0
  --no-push   không tự đẩy dữ liệu làng sau getUserInfo / về nhà
  --no-obb    chưa đặt OBB: chỉ dùng ảnh có trong APK
  --admin-remote  cho máy khác trong mạng mở trang quản trị /admin
Biến môi trường: TLM_HOME (thư mục dữ liệu), TLM_IP, TLM_HTTP_PORT, TLM_GAME_PORT, TLM_CHAT_PORT
"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tlm import config  # noqa: E402

config.init_data_dir()

from tlm import logger, state, storage  # noqa: E402
from tlm.logger import log  # noqa: E402


def main():
    logger.init()
    old = logger.archive_old_log()
    logger.start()
    if old:
        log("Đã nén log cũ -> %s" % old)
    if not config.SHARED_OK:
        log("!! Chưa có quyền bộ nhớ chung, dữ liệu ở %s. Chạy 'termux-setup-storage' rồi chạy lại." % config.DATA_DIR)
    log("ThoiLoanServer v%s | dữ liệu: %s" % (config.VERSION, config.DATA_DIR))

    from tlm.handlers import load_all
    from tlm import game_server, http_server
    handlers = load_all()
    log("Đã nạp %d handler: %s" % (len(handlers), ", ".join(str(c) for c in sorted(handlers))))
    store = storage.open_storage()
    log("Kho lưu: %s | %d tài khoản | tuỳ chọn: tự trả lời=%s, đẩy làng=%s, OBB=%s"
        % (store.kind, len(store.keys()), config.AUTO_REPLY, config.PUSH_ENABLED, config.USE_OBB))
    try:
        http = http_server.create_server()
        game, chat = game_server.create_servers()
    except OSError as e:
        log("Không mở được cổng (%s). Có bản server khác đang chạy? Tắt nó (Ctrl+C) rồi chạy lại." % e)
        sys.exit(1)
    for srv, name in ((http, "HTTP"), (game, "GAME"), (chat, "CHAT")):
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        log("Đang lắng nghe %s trên cổng %d" % (name, srv.server_address[1]))
    log("Trang quản trị: http://127.0.0.1:%d/admin" % config.HTTP_PORT)
    log("Sẵn sàng. Mở game đi. Ctrl+C để dừng.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("Đã dừng.")


if __name__ == "__main__":
    main()
