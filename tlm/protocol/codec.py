"""Mã hoá / giải mã dữ liệu trong gói (khớp MessageBuffer của game).

- Số nguyên: BIG-ENDIAN.
- "double": số thực IEEE 8 byte big-endian (MessageBuffer::getDouble đọc rồi đổi sang số nguyên).
- Chuỗi: u16 độ dài + byte.
- Đọc vượt cuối gói làm game SẬP -> phản hồi luôn phải đủ byte.
"""
import re
import struct


def u8(v):
    return bytes([int(v) & 0xFF])


def u16(v):
    return (int(v) & 0xFFFF).to_bytes(2, "big")


def u32(v):
    return (int(v) & 0xFFFFFFFF).to_bytes(4, "big")


def f64(v):
    return struct.pack(">d", float(v))


def pstr(s):
    b = str(s).encode("utf-8")
    return u16(len(b)) + b


class Reader:
    """Đọc dữ liệu client gửi lên."""

    def __init__(self, data):
        self.data, self.pos = data, 0

    def remaining(self):
        return len(self.data) - self.pos

    def u8(self):
        v = self.data[self.pos]; self.pos += 1; return v

    def u16(self):
        v = int.from_bytes(self.data[self.pos:self.pos + 2], "big"); self.pos += 2; return v

    def u32(self):
        v = int.from_bytes(self.data[self.pos:self.pos + 4], "big"); self.pos += 4; return v

    def i32(self):
        v = int.from_bytes(self.data[self.pos:self.pos + 4], "big", signed=True); self.pos += 4; return v

    def str(self):
        n = self.u16(); v = self.data[self.pos:self.pos + n].decode("utf-8", "replace"); self.pos += n; return v


def parse_id_and_type(payload):
    """Dữ liệu dạng [int id][chuỗi loại] hoặc [chuỗi loại][int id] -> (id, loại)."""
    if len(payload) >= 4:
        n = int.from_bytes(payload[0:2], "big")
        if 5 <= n <= 8 and len(payload) >= 2 + n and re.match(rb"^[A-Z]{3}_\d+$", payload[2:2 + n]):
            r = Reader(payload); s = r.str()
            return (r.u32() if r.remaining() >= 4 else None), s
        r = Reader(payload); bid = r.u32(); s = ""
        if r.remaining() >= 2:
            try:
                s = r.str()
            except Exception:
                s = ""
        return bid, s
    return None, ""


def describe_payload(data):
    """Liệt kê các chuỗi [u16 độ dài][ký tự in được] tìm thấy (để ghi log)."""
    out, i = [], 0
    while i + 2 <= len(data):
        n = int.from_bytes(data[i:i + 2], "big")
        if 2 <= n <= 200 and i + 2 + n <= len(data):
            chunk = data[i + 2:i + 2 + n]
            if all(32 <= c < 127 or c == 9 for c in chunk):
                out.append((i, chunk.decode()))
                i += 2 + n
                continue
        i += 1
    return out
