"""Giải mã / mã hoá ảnh .pvr.ccz (CCZp) của Thời Loạn và đọc/ghi PVR."""
import struct, zlib
KEY = [0xabc12bca, 0x21aaa11b, 0xbb22ccc1, 0x1aabbc22]
M = 0xffffffff

def _stream():
    k = [0] * 1024
    s, z = 0, 0
    for _ in range(6):
        s = (s + 0x9e3779b9) & M
        e = (s >> 2) & 3
        for p in range(1024):
            y = k[(p + 1) % 1024]
            mx = ((((z >> 5) ^ (y << 2) & M) + ((y >> 3) ^ (z << 4) & M)) & M) ^ (((s ^ y) + (KEY[(p & 3) ^ e] ^ z)) & M)
            k[p] = (k[p] + mx) & M
            z = k[p]
    return k
STREAM = _stream()

def xor(buf):
    n = (len(buf) - 12) // 4
    w = list(struct.unpack_from("<%dI" % n, buf, 12))
    b, i = 0, 0
    while i < n and i < 512:
        w[i] ^= STREAM[b]; b = (b + 1) % 1024; i += 1
    while i < n:
        w[i] ^= STREAM[b]; b = (b + 1) % 1024; i += 64
    out = bytearray(buf); struct.pack_into("<%dI" % n, out, 12, *w)
    return bytes(out)

def read_ccz_bytes(b):
    if b[:4] == b"CCZp": b = xor(b)
    return zlib.decompress(b[16:])

def write_ccz_bytes(raw, encrypt=True):
    b = (b"CCZp" if encrypt else b"CCZ!") + struct.pack(">HHII", 0, 2, 0, len(raw)) + zlib.compress(raw, 9)
    return xor(b) if encrypt else b

def read_ccz(path):
    return read_ccz_bytes(open(path, "rb").read())

def write_ccz(path, raw, encrypt=True):
    open(path, "wb").write(write_ccz_bytes(raw, encrypt))
