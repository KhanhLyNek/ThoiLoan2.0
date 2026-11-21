"""Cây thông Noel vẽ bằng code: 4 tầng lá có khối sáng/tối, tuyết đọng mép tầng, dây đèn, sao vàng, bóng đổ."""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

def tree(H=180, seed=3):
    rng = np.random.default_rng(seed)
    W = int(H * 0.85); S = 4                                     # vẽ lớn 4x rồi thu nhỏ cho mịn
    big = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0)); d = ImageDraw.Draw(big)
    cx = W * S / 2; top = H * S * 0.12; base = H * S * 0.86
    # thân
    d.rectangle([cx - H * S * 0.05, base - H * S * 0.06, cx + H * S * 0.05, H * S * 0.97], fill=(92, 58, 34, 255))
    tiers = 4
    for k in range(tiers):
        f0 = k / tiers; f1 = (k + 1) / tiers
        yt = top + (base - top) * f0 * 0.82; yb = top + (base - top) * (f1 * 0.85 + 0.15)
        half = W * S * (0.16 + 0.34 * f1)
        # nửa trái tối, nửa phải sáng (nắng từ phải trên)
        pts_l = [(cx, yt), (cx - half, yb), (cx, yb + H * S * 0.02)]
        pts_r = [(cx, yt), (cx + half, yb), (cx, yb + H * S * 0.02)]
        d.polygon(pts_l, fill=(20, 78, 52, 255)); d.polygon(pts_r, fill=(34, 112, 70, 255))
        # mép răng cưa có tuyết
        n = 9
        for i in range(n + 1):
            x = cx - half + 2 * half * i / n; y = yb + H * S * 0.012 * math.sin(i * 1.7)
            r = H * S * 0.028
            d.ellipse([x - r * 1.4, y - r, x + r * 1.4, y + r], fill=(236, 244, 255, 255))
        # tuyết trên vai tầng
        d.polygon([(cx, yt + H * S * 0.01), (cx - half * 0.35, yt + (yb - yt) * 0.38), (cx + half * 0.45, yt + (yb - yt) * 0.42)],
                  fill=(244, 249, 255, 235))
    img = big.resize((W, H), Image.LANCZOS)
    a = np.asarray(img).astype(np.float32)
    leaf = (a[..., 1] > a[..., 0] + 25) & (a[..., 3] > 0)
    n = rng.normal(1.0, 0.13, a.shape[:2]); n = np.asarray(Image.fromarray(((n - 0.5) * 200).clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7))).astype(np.float32) / 100 + 0.5
    yy = np.linspace(1.12, 0.85, a.shape[0])[:, None]
    a[..., :3] = np.where(leaf[..., None], (a[..., :3] * (n * yy)[..., None]).clip(0, 255), a[..., :3])
    img = Image.fromarray(a.astype(np.uint8), "RGBA")
    # dây đèn (vòng chéo) + quả châu
    d = ImageDraw.Draw(img)
    cols = [(255, 70, 60), (255, 215, 70), (90, 170, 255), (255, 120, 220), (120, 255, 140)]
    for k in range(5):
        y0 = H * (0.24 + 0.14 * k); half = W * (0.12 + 0.07 * k)
        for i in range(9):
            t = i / 8; x = W / 2 - half + 2 * half * t; y = y0 + H * 0.05 * t + H * 0.012 * math.sin(t * 6)
            c = cols[(i + k) % len(cols)]
            d.ellipse([x - 3.2, y - 3.2, x + 3.2, y + 3.2], fill=c + (90,))
            d.ellipse([x - 1.6, y - 1.6, x + 1.6, y + 1.6], fill=c + (255,))
    for _ in range(10):
        y = rng.uniform(H * 0.3, H * 0.8); half = W * (0.1 + 0.4 * (y / H - 0.12)); x = W / 2 + rng.uniform(-half, half) * 0.8
        c = cols[rng.integers(3)]
        d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=c + (255,)); d.point([(x - 1, y - 1)], fill=(255, 255, 255, 255))
    # sao + quầng sáng
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0)); g = ImageDraw.Draw(glow)
    sx, sy = W / 2, H * 0.1; R = H * 0.07
    g.ellipse([sx - R * 2.2, sy - R * 2.2, sx + R * 2.2, sy + R * 2.2], fill=(255, 230, 120, 130))
    glow = glow.filter(ImageFilter.GaussianBlur(R * 0.9))
    out = Image.alpha_composite(glow, img); d = ImageDraw.Draw(out)
    star = [(sx + (R if i % 2 == 0 else R * 0.45) * math.cos(-math.pi / 2 + i * math.pi / 5),
             sy + (R if i % 2 == 0 else R * 0.45) * math.sin(-math.pi / 2 + i * math.pi / 5)) for i in range(10)]
    d.polygon(star, fill=(255, 214, 60, 255), outline=(200, 140, 20, 255))
    return out

def place(piece, tree_img, bx, by):
    """Đặt gốc cây tại (bx, by) của mảnh bản đồ, kèm bóng đổ xanh nhạt trên tuyết."""
    W, H = tree_img.size
    sh = Image.new("RGBA", piece.size, (0, 0, 0, 0)); d = ImageDraw.Draw(sh)
    d.ellipse([bx - W * 0.55, by - H * 0.07, bx + W * 0.75, by + H * 0.08], fill=(40, 60, 100, 110))
    sh = sh.filter(ImageFilter.GaussianBlur(6))
    piece.alpha_composite(sh)
    piece.alpha_composite(tree_img, (int(bx - W / 2), int(by - H * 0.97)))
    return piece
