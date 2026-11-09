"""Tầng HTTP: /info (cấu hình server), /login (đăng nhập khách), /mail (hộp thư)."""
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import config
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
            session = "guest-" + dev
            payload = json.dumps({"error": 0, "sessionKey": session}).encode("utf-8")
            log("    -> ĐĂNG NHẬP KHÁCH (social=%s): sessionKey=%s" % ((form.get("social") or ["?"])[0], session))
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
