"""Tầng mạng TCP: nhận byte, tách khung, ghi log, chuyển cho handler hoặc tự trả lời."""
import itertools
import json
import os
import socket
import socketserver

from . import config
from .handlers import HANDLERS
from .handlers.context import Context
from .logger import hexdump, log
from .protocol.codec import describe_payload
from .protocol.commands import RECV_CLASS, SEND_NAMES, SKIP_AUTO
from .protocol.frame import build_frame, extract_frame

_counter = itertools.count(1)
PORT_NAMES = {config.GAME_PORT: "GAME", config.CHAT_PORT: "CHAT"}


def load_rules():
    """replies.json (trong thư mục dữ liệu): luật trả lời tay, ưu tiên hơn tự trả lời."""
    try:
        with open(config.data_path("replies.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except ValueError as e:
        log("!! replies.json không phải JSON hợp lệ (%s), bỏ qua." % e)
        return []


def rule_frames(ctl, cmd):
    out = []
    for rule in load_rules():
        m = rule.get("match", {})
        if m.get("ctl") not in (None, ctl) or m.get("cmd") not in (None, cmd):
            continue
        reps = rule.get("reply", [])
        for r in (reps if isinstance(reps, list) else [reps]):
            c = int(r.get("cmd", cmd))
            out.append(("replies.json cmd=%d error=%s" % (c, r.get("error", 0)),
                        build_frame(int(r.get("ctl", ctl)), c, int(r.get("error", 0)), bytes.fromhex(r.get("data_hex", "")))))
    return out


class TcpHandler(socketserver.BaseRequestHandler):
    def handle(self):
        port = self.server.server_address[1]
        label = PORT_NAMES.get(port, str(port))
        cid = next(_counter)
        tag = "#%d [%s]" % (cid, label)
        log("%s kết nối mới từ %s:%d" % ((tag,) + tuple(self.client_address[:2])))
        self.request.settimeout(900)
        ctx = Context(self.request, tag)
        total, buf = 0, bytearray()
        from . import logger
        binpath = os.path.join(logger.BIN_DIR, "conn_%d_%s.bin" % (cid, label))
        with open(binpath, "ab") as raw:
            while True:
                try:
                    data = self.request.recv(65536)
                except socket.timeout:
                    log("%s quá thời gian chờ, đóng." % tag)
                    break
                except OSError as e:
                    log("%s lỗi socket: %s" % (tag, e))
                    break
                if not data:
                    log("%s client đóng kết nối (tổng %d byte)." % (tag, total))
                    break
                total += len(data)
                raw.write(data)
                raw.flush()
                if data[:2] == b"\x16\x03":
                    log("%s nhận %d byte: có vẻ là TLS ClientHello" % (tag, len(data)))
                log("%s nhận %d byte:\n%s" % (tag, len(data), hexdump(data)))
                buf.extend(data)
                while True:
                    try:
                        fr = extract_frame(buf)
                    except ValueError as e:
                        log("%s   !! %s, bỏ bộ đệm." % (tag, e))
                        buf.clear()
                        break
                    if fr is None:
                        break
                    self.on_frame(ctx, *fr)

    def on_frame(self, ctx, hdr, body):
        tag = ctx.tag
        if hdr & 0x20:
            log("%s   KHUNG hdr=0x%02x NÉN zlib, %d byte (chưa giải mã)" % (tag, hdr, len(body)))
            return
        if len(body) < 3:
            log("%s   KHUNG hdr=0x%02x body ngắn: %s" % (tag, hdr, body.hex()))
            return
        ctl, cmd, payload = body[0], int.from_bytes(body[1:3], "big"), body[3:]
        expect = RECV_CLASS.get(cmd)
        log("%s   KHUNG ctl=%d cmd=%d [%s] dữ liệu %d byte%s" % (
            tag, ctl, cmd, SEND_NAMES.get(cmd, "?"), len(payload),
            (" | game xử lý phản hồi bằng CmdReceive" + expect) if expect else " | game KHÔNG có handler cho cmd này"))
        strs = describe_payload(payload)
        if strs:
            log("%s     chuỗi: %s" % (tag, "; ".join("@%d %r" % s for s in strs[:12])))
        log("%s     hex: %s%s" % (tag, payload.hex()[:240], "..." if len(payload) > 120 else ""))

        rules = rule_frames(ctl, cmd)
        for desc, frame in rules:                      # 1. luật tay trong replies.json
            ctx.send(frame, desc)
        ctx.silent = bool(rules)
        handled = False
        fn = HANDLERS.get(cmd)
        if fn and config.AUTO_REPLY:                   # 2. handler riêng (logic game)
            try:
                handled = fn(ctx, ctl, cmd, payload)
            except Exception as e:
                ctx.log("lỗi handler cmd %d: %s" % (cmd, e))
        ctx.silent = False
        if rules or handled or not config.AUTO_REPLY:
            return
        if cmd in SKIP_AUTO:                           # 3. lệnh không được trả lời
            ctx.log("(KHÔNG trả lời cmd %d: %s)" % (cmd, SKIP_AUTO[cmd]))
            return
        if cmd in RECV_CLASS:                          # 4. tự trả lời "thành công" + đệm số 0
            ctx.reply(ctl, cmd)


class ThreadedTcp(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def create_servers():
    return (ThreadedTcp((config.BIND_HOST, config.GAME_PORT), TcpHandler),
            ThreadedTcp((config.BIND_HOST, config.CHAT_PORT), TcpHandler))
