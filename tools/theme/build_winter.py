"""Dựng theme mùa đông (tlm/res/theme_winter.obb) từ OBB + APK gốc.

  python tools/theme/build_winter.py main.1380.gsn.zps.thoiloan.obb ThoiLoan.apk [ra.obb]

- map/1..4.pvr.ccz : cảnh quanh làng phủ tuyết (wint.py), thêm cây thông Noel (xtree.py) ở ngã ba phía trên
- map/gird.png      : 2 ô nền tuyết (giữ vân của ô cỏ gốc)
- Content/new_map_obj.png/.plist : thêm khung snow_1.png (bông tuyết cho FallingView = tuyết rơi)
Ảnh .pvr.ccz là CCZp (mã hoá, khoá trong libcocos2dcpp.so) + PVR v2 RGBA4444 -> ccz.py / pvr.py.
"""
import io, math, os, re, sys, zipfile
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ccz import read_ccz_bytes, write_ccz_bytes
from pvr import to_img, from_img
from wint import winterize
from xtree import tree, place

def main(obb, apk, out):
    zo, za = zipfile.ZipFile(obb), zipfile.ZipFile(apk)
    files = {}
    for i in range(1, 5):
        raw0 = read_ccz_bytes(zo.read("assets/800_480/map/%d.pvr.ccz" % i))
        w = winterize(to_img(raw0), seed=i)
        if i == 1:
            place(w, tree(170), 600, 372)
        files["assets/800_480/map/%d.pvr.ccz" % i] = write_ccz_bytes(from_img(w, raw0))
        print("mảnh", i, "xong")
    rng = np.random.default_rng(7)
    g = np.asarray(Image.open(io.BytesIO(zo.read("assets/800_480/map/gird.png"))).convert("RGBA")).astype(np.float32)
    lum = g[..., :3] @ np.array([.3, .59, .11]); outg = np.zeros_like(g)
    for sl, base in ((slice(0, 57), 0.0), (slice(57, 114), -0.012)):
        L = lum[sl]; t = np.clip(0.5 + (L - L.mean()) / (L.std() * 5), 0, 1)
        c = np.array([200, 214, 234.]) + (np.array([246, 249, 255.]) - np.array([200, 214, 234.])) * t[..., None]
        outg[sl, ..., :3] = c * (1 + base) + rng.normal(0, 2.2, c.shape); outg[sl, ..., 3] = 255
    files["assets/800_480/map/gird.png"] = _png(Image.fromarray(np.clip(outg, 0, 255).astype(np.uint8), "RGBA"))
    flake = snowflake(32)
    im = Image.open(io.BytesIO(za.read("assets/800_480/Content/new_map_obj.png"))).convert("RGBA")
    X, Y = 4, 182                                          # ô trống trong bảng 512x512
    im.alpha_composite(flake, (X, Y))
    files["assets/800_480/Content/new_map_obj.png"] = _png(im)
    pl = za.read("assets/800_480/Content/new_map_obj.plist").decode().replace("\r\n", "\n")
    frame = ("            <key>snow_1.png</key>\n            <dict>\n                <key>frame</key>\n"
             "                <string>{{%d,%d},{32,32}}</string>\n                <key>offset</key>\n"
             "                <string>{0,0}</string>\n                <key>rotated</key>\n                <false/>\n"
             "                <key>sourceColorRect</key>\n                <string>{{0,0},{32,32}}</string>\n"
             "                <key>sourceSize</key>\n                <string>{32,32}</string>\n            </dict>\n") % (X, Y)
    i = pl.index("        </dict>\n        <key>metadata</key>")
    files["assets/800_480/Content/new_map_obj.plist"] = (pl[:i] + frame + pl[i:]).encode()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
        for n, d in files.items():
            z.writestr(n, d)
    print("Đã tạo", out, os.path.getsize(out), "byte")

def _png(img):
    b = io.BytesIO(); img.save(b, "PNG"); return b.getvalue()

def snowflake(S):
    fl = Image.new("RGBA", (S * 4, S * 4), (0, 0, 0, 0)); d = ImageDraw.Draw(fl); c = S * 2
    for k in range(6):
        a = math.pi * k / 3
        d.line([c, c, c + math.cos(a) * S * 1.55, c + math.sin(a) * S * 1.55], fill=(255, 255, 255, 255), width=7)
        for f in (0.55, 0.85):
            bx, by = c + math.cos(a) * S * 1.55 * f, c + math.sin(a) * S * 1.55 * f
            for s in (-1, 1):
                b = a + s * math.pi / 4
                d.line([bx, by, bx + math.cos(b) * S * 0.45, by + math.sin(b) * S * 0.45], fill=(255, 255, 255, 255), width=5)
    d.ellipse([c - 12, c - 12, c + 12, c + 12], fill=(255, 255, 255, 255))
    out = Image.alpha_composite(Image.new("RGBA", fl.size, (0, 0, 0, 0)), fl.filter(ImageFilter.GaussianBlur(10)))
    out.alpha_composite(fl)
    return out.resize((S, S), Image.LANCZOS)

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else os.path.join(here, "..", "..", "tlm", "res", "theme_winter.obb"))
