import struct, numpy as np
from PIL import Image
from ccz import read_ccz, write_ccz
def to_img(raw):
    hl, h, w = struct.unpack_from('<III', raw, 0)
    flags = struct.unpack_from('<I', raw, 16)[0]
    assert flags & 0xff == 0x10, hex(flags)
    a = np.frombuffer(raw, dtype='<u2', count=w*h, offset=hl).reshape(h, w)
    rgba = np.stack([(a >> 12) & 15, (a >> 8) & 15, (a >> 4) & 15, a & 15], -1).astype(np.uint8) * 17
    return Image.fromarray(rgba, 'RGBA')
def from_img(img, template_raw):
    hl = struct.unpack_from('<I', template_raw, 0)[0]
    a = np.asarray(img.convert('RGBA')).astype(np.uint16)
    h, w = a.shape[:2]
    # làm tròn có hoà sắc nhẹ để giảm vệt màu 4-bit
    B = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) / 16 - 0.47
    th = np.tile(B, (h // 4 + 1, w // 4 + 1))[:h, :w][..., None]
    q = np.floor(a.astype(np.float32) / 17 + 0.5 + th * np.array([1, 1, 1, 0])).clip(0, 15).astype(np.uint16)
    v = (q[..., 0] << 12) | (q[..., 1] << 8) | (q[..., 2] << 4) | q[..., 3]
    hdr = bytearray(template_raw[:hl])
    struct.pack_into('<II', hdr, 4, h, w)
    struct.pack_into('<I', hdr, 20, w * h * 2)
    return bytes(hdr) + v.astype('<u2').tobytes()
