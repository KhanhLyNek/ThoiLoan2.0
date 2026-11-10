"""Ngữ cảnh một kết nối: gửi khung, ghi log."""
from .. import config
from ..logger import log
from ..protocol.commands import RECV_CLASS
from ..protocol.frame import build_frame


class Context:
    def __init__(self, sock, tag):
        self.sock, self.tag = sock, tag
        self.silent = False          # True khi replies.json đã trả lời thay (handler chỉ chạy logic)
        self.account = "default"     # tài khoản (sessionKey), gán khi game gửi Login (cmd 1)
        self.battle = None           # trận đang đánh (phó bản / chinh phạt), gán ở cmd 9001

    def log(self, msg):
        log("%s   %s" % (self.tag, msg))

    def send(self, frame, desc):
        if self.silent:
            return
        try:
            self.sock.sendall(frame)
            self.log("-> %s (%d byte)" % (desc, len(frame)))
        except OSError as e:
            self.log("gửi thất bại: %s" % e)

    def reply(self, ctl, cmd, error=0, data=None, desc=None):
        """Trả lời; data=None -> đệm số 0 (để game không đọc vượt cuối gói)."""
        data = bytes(config.AUTO_PAD) if data is None else data
        self.send(build_frame(ctl, cmd, error, data),
                  desc or "GỬI cmd=%d lớp %s, error=%d, dữ liệu %d byte" % (cmd, RECV_CLASS.get(cmd, "?"), error, len(data)))

    def push(self, ctl, cmd, data, note=""):
        """Server chủ động gửi (không phải trả lời)."""
        self.send(build_frame(ctl, cmd, 0, data),
                  "ĐẨY chủ động cmd=%d lớp %s%s" % (cmd, RECV_CLASS.get(cmd, "?"), note))
