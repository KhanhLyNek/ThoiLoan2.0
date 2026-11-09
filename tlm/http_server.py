"""Tầng HTTP: /info (cấu hình server), /login (đăng nhập theo nút + máy), /mail (hộp thư), /admin (quản trị)."""
import json
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import admin, config
from .data import load_table
from .logger import log


def default_info():
    """JSON /info. Kiểu dữ liệu đối chiếu với PreloadScreen::checkVersion (sai kiểu = sập)."""
    info = dict(load_table("info_default.json"))
    ip, http = config.PUBLIC_IP, config.HTTP_PORT
    info.update({"server_ip": ip, "server_port": config.GAME_PORT, "chat_ip": ip, "chat_port": config.CHAT_PORT,
                 "client_ip": ip, "mail_api": "http://%s:%d/mail?country=" % (ip, http),
                 "login_url": "http://%s:%d/login" % (ip, http), "json_url": "http://%s:%d/json/" % (ip, http)})
    return info


class HttpHandler(BaseHTTPRequestHandler):
    server_version = "ThoiLoanServer/" + config.VERSION

    def log_message(self, fmt, *args):
        pass

    def _handle(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        log("HTTP %s %s từ %s" % (method, self.path, self.client_address[0]))
        if body:
            log("    body (%d byte): %s" % (len(body), body.decode("utf-8", "replace")[:400]))
        if self.path.startswith("/login"):
            # TokenMgr::parseDataLogin chỉ cần {"error": 0, "sessionKey": "..."}
            form = urllib.parse.parse_qs(body.decode("utf-8", "replace"))
            dev = (form.get("deviceId") or ["guest"])[0]
            social = (form.get("social") or ["guest"])[0]
            # mỗi nút đăng nhập (google/facebook/zalo) trên mỗi máy = một tài khoản riêng
            session = re.sub(r"[^A-Za-z0-9_.@-]", "_", "%s-%s" % (social, dev))[:120]
            payload = json.dumps({"error": 0, "sessionKey": session}).encode("utf-8")
            log("    -> ĐĂNG NHẬP (nút %s): tài khoản %s" % (social, session))
        elif self.path.startswith("/admin"):
            if self.client_address[0] not in ("127.0.0.1", "::1") and not config.ADMIN_REMOTE:
                payload, ctype, status = b"Chi truy cap tu chinh may nay (127.0.0.1).", "text/plain; charset=utf-8", 403
            else:
                status, ctype, payload, location = admin.handle(method, self.path, body)
                if location:
                    self.send_response(303)
                    self.send_header("Location", location)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Connection", "close")
            self.end_headers()
            if method != "HEAD":
                self.wfile.write(payload)
            return
        elif self.path.startswith("/mail"):
            # CityMgr::finishGetListMessage đọc thẳng doc["data"] (thiếu -> sập)
            payload = json.dumps({"data": []}).encode("utf-8")
            log("    -> trả /mail: danh sách thư rỗng")
        elif self.path.startswith("/info"):
            try:
                with open(config.data_path("info.json"), "rb") as f:
                    payload, src = f.read(), "file info.json"
            except FileNotFoundError:
                payload, src = json.dumps(default_info()).encode("utf-8"), "mặc định"
            log("    -> trả /info %d byte (%s)" % (len(payload), src))
        else:
            payload = b"{}"
            log("    (đường dẫn lạ, trả {})")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.end_headers()
        if method != "HEAD":
            self.wfile.write(payload)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_HEAD(self):
        self._handle("HEAD")


def create_server():
    return ThreadingHTTPServer((config.BIND_HOST, config.HTTP_PORT), HttpHandler)
