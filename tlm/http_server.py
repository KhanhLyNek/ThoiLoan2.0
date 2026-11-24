"""Tầng HTTP: /info (cấu hình server), /login (đăng nhập theo nút + máy), /mail (hộp thư), /admin (quản trị),
/obb (file OBB cho APK vá tự tải), /t.obb + /ts.obb (theme mùa đông: game tự tải khi bật Giao diện trong Cài đặt).

THEME (có sẵn trong game gốc, bản 2018): /info "enableTheme": true -> PreloadScreen::checkVersion bật cờ theme.
Người chơi vào Cài đặt > Giao diện (SettingGUI::doSwitchTheme đặt USE_THEME) -> chưa có theme.obb thì game tự tải
(DownloadScreen::downloadTheme) về /sdcard/Android/data/<gói>/theme.obb, báo khởi động lại. Lần mở sau:
PlatformUtil::addResourceToFirst(theme.obb) -> file trong theme đè file gốc (map/1..4.pvr.ccz, map/gird.png,
Content/new_map_obj.* có khung snow_1.png) và CityMap::loadMap tạo FallingView = TUYẾT RƠI.
Địa chỉ tải gốc (tlm.vcdn.vn) đã chết -> APK vá trỏ về /t.obb (HD) và /ts.obb (SD) của server (tools/patch_apk.py)."""
import json
import os
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import admin, config
from .data import load_table
from .logger import log

OBB_NAME = "main.1380.gsn.zps.thoiloan.obb"
THEME_NAME = "theme.obb"            # đặt file này vào thư mục dữ liệu để thay theme có sẵn
THEME_BUNDLED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "res", "theme_winter.obb")


def default_info():
    """JSON /info. Kiểu dữ liệu đối chiếu với PreloadScreen::checkVersion (sai kiểu = sập)."""
    info = dict(load_table("info_default.json"))
    ip, http = config.PUBLIC_IP, config.HTTP_PORT
    info["enableTheme"] = bool(config.ENABLE_THEME)
    info.update({"server_ip": ip, "server_port": config.GAME_PORT, "chat_ip": ip, "chat_port": config.CHAT_PORT,
                 "client_ip": ip, "mail_api": "http://%s:%d/mail?country=" % (ip, http),
                 "login_url": "http://%s:%d/login" % (ip, http), "json_url": "http://%s:%d/json/" % (ip, http)})
    return info


def patch_list():
    lines, size = [], None
    for path in (os.path.join(os.path.dirname(__file__), "res", "patches", "native.json"), config.data_path("native.json")):
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        size = doc.get("lib_size") or size
        for p in doc.get("patches", []):
            if p.get("off"):
                continue
            lines.append("%x %s %s" % (int(p["addr"]), p.get("old") or "-", p["new"]))
    return ("size %d\n" % size if size else "") + "".join(l + "\n" for l in lines)


class HttpHandler(BaseHTTPRequestHandler):
    server_version = "ThoiLoanServer/" + config.VERSION

    def log_message(self, fmt, *args):
        pass

    def _send_obb(self, method):
        """/obb: APK vá (màn hình ObbGate) tải OBB từ đây trước, không có thì tự tải Google Drive.
        Đặt file main.1380.gsn.zps.thoiloan.obb vào thư mục dữ liệu (/sdcard/ThoiLoan2.0) để tải nhanh qua máy."""
        path = config.data_path(OBB_NAME)
        if not os.path.isfile(path):
            log("    -> /obb: chưa có %s trong thư mục dữ liệu, game sẽ tải từ Google Drive" % OBB_NAME)
            self._send_404()
            return
        self._send_file(method, path)

    def _send_patches(self, method):
        """/patch/native.txt: bản vá mã máy cho bộ nạp trong APK (tools/obbgate TlmLoader). Nguồn: tlm/res/patches/native.json
        (+ native.json trong thư mục dữ liệu nếu có, để thử nghiệm). Dòng: "địa_chỉ_hex byte_cũ_hex byte_mới_hex"."""
        body = patch_list().encode("utf-8")
        log("    -> BỘ NẠP: gửi %d bản vá mã máy" % max(0, body.count(b"\n") - 1))
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if method != "HEAD":
            self.wfile.write(body)

    def _send_theme(self, method):
        """/t.obb, /ts.obb: theme mùa đông. Ưu tiên theme.obb trong thư mục dữ liệu, không có thì dùng bản kèm server."""
        path = config.data_path(THEME_NAME)
        if not os.path.isfile(path):
            path = THEME_BUNDLED
        if not os.path.isfile(path):
            self._send_404()
            return
        log("    -> THEME: game đang tải giao diện mùa đông (%s)" % os.path.basename(path))
        self._send_file(method, path)

    def _send_404(self):
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_file(self, method, path):
        size = os.path.getsize(path)
        start = 0
        m = re.match(r"bytes=(\d+)-", self.headers.get("Range") or "")
        if m and int(m.group(1)) < size:
            start = int(m.group(1))
            self.send_response(206)
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, size - 1, size))
        else:
            self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(size - start))
        self.end_headers()
        log("    -> gửi %s từ byte %d (%d byte)" % (os.path.basename(path), start, size))
        if method == "HEAD":
            return
        with open(path, "rb") as f:
            f.seek(start)
            while True:
                chunk = f.read(1 << 20)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def _handle(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        log("HTTP %s %s từ %s" % (method, self.path, self.client_address[0]))
        if body:
            log("    body (%d byte): %s" % (len(body), body.decode("utf-8", "replace")[:400]))
        if self.path.startswith("/obblog"):
            # chẩn đoán từ trình tải OBB trong APK (tools/obbgate): chỉ ghi log
            msg = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("m", [""])[0]
            log("    -> OBB (từ máy): %s" % msg)
            self.send_response(204)
            self.end_headers()
            return
        if self.path.split("?")[0] == "/patch/native.txt":
            self._send_patches(method)
            return
        if self.path.startswith("/obb"):
            self._send_obb(method)
            return
        if self.path.split("?")[0] in ("/t.obb", "/ts.obb"):
            self._send_theme(method)
            return
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
            else:
                try:                                 # info.json tự viết vẫn nhận cờ theme của server
                    d = json.loads(payload)
                    d.setdefault("enableTheme", bool(config.ENABLE_THEME))
                    payload = json.dumps(d).encode("utf-8")
                except ValueError:
                    pass
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
