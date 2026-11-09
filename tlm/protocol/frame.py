"""Khung gói tin (suy ra từ PacketFactory::packPacket / getValidSize / analyzeData).

byte 0  : cờ header. bit3 = độ dài 4 byte (ngược lại 2 byte), bit5 = payload nén zlib.
độ dài  : u16 (hoặc u32 nếu bit3) BIG-ENDIAN = số byte phía sau nó.
client->server: [controller 1B][cmd u16][dữ liệu...]
server->client: [controller 1B][cmd u16][error 1B][dữ liệu...]
"""


def extract_frame(buf):
    """Lấy 1 khung từ bytearray buf. Trả (header, body) hoặc None nếu chưa đủ dữ liệu."""
    if len(buf) < 3:
        return None
    hdr = buf[0]
    if hdr & 0x08:
        if len(buf) < 5:
            return None
        ln, start = int.from_bytes(buf[1:5], "big"), 5
    else:
        ln, start = int.from_bytes(buf[1:3], "big"), 3
    if ln > 4 * 1024 * 1024:
        raise ValueError("độ dài khung bất thường: %d" % ln)
    if len(buf) < start + ln:
        return None
    body = bytes(buf[start:start + ln])
    del buf[:start + ln]
    return hdr, body


def build_frame(ctl, cmd, error, data=b""):
    """Khung server->client (không nén, độ dài 2 byte)."""
    body = bytes([ctl & 0xFF]) + int(cmd).to_bytes(2, "big") + bytes([error & 0xFF]) + data
    return bytes([0x90]) + len(body).to_bytes(2, "big") + body
