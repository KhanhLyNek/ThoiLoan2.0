"""Biến tranh gốc thành mùa đông: tuyết phủ cỏ/cây, suối đóng băng, đá & gỗ có tuyết trên mặt, châu Noel trên cây."""
import numpy as np
from PIL import Image, ImageFilter

def rgb2hsv(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(-1), a.min(-1); d = mx - mn + 1e-6
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    s = np.where(mx > 0, (mx - mn) / (mx + 1e-6), 0)
    return h, s, mx

def lerp(a, b, t): return a + (b - a) * t[..., None]

def winterize(img, seed=1, ornaments=True):
    rng = np.random.default_rng(seed)
    a = np.asarray(img.convert("RGBA")).astype(np.float32) / 255
    rgb, al = a[..., :3], a[..., 3]
    h, s, v = rgb2hsv(rgb)
    lum = rgb @ np.array([0.3, 0.59, 0.11])
    # độ "xanh lá" (cỏ/cây) và "nước"
    green = np.clip(1.25 - np.abs(h - 92) / 52, 0, 1) * np.clip((s - 0.10) / 0.22, 0, 1)
    water = np.clip(1 - np.abs(h - 190) / 30, 0, 1) * np.clip((s - 0.15) / 0.2, 0, 1)
    dirt = np.clip(1.3 - np.abs(h - 47) / 14, 0, 1) * np.clip((s - 0.2) / 0.2, 0, 1) * np.clip((v - 0.35) / 0.2, 0, 1) * (1 - green)
    neutral = np.clip(1 - s / 0.45, 0, 1) * (1 - green) * (1 - water) * (1 - dirt)            # đá, gỗ nhạt
    # hướng sáng (mặt trên): ảnh sáng hơn phía dưới -> tuyết đọng
    L = Image.fromarray((lum * 255).astype(np.uint8))
    blur = np.asarray(L.filter(ImageFilter.GaussianBlur(3))).astype(np.float32) / 255
    up = np.clip((lum - np.roll(blur, -4, axis=0)) * 4 + 0.5, 0, 1)
    snow_w = np.array([0.96, 0.98, 1.0]); snow_s = np.array([0.55, 0.66, 0.82]); pine = np.array([0.07, 0.20, 0.19])
    # cỏ/tán cây -> tuyết; phần tối giữ xanh thông
    t = np.clip((lum - 0.22) / 0.5, 0, 1) ** 0.9
    snowy = lerp(np.broadcast_to(snow_s, rgb.shape), np.broadcast_to(snow_w, rgb.shape), t)
    dark = np.clip((0.40 - lum) / 0.20, 0, 1)
    snowy = lerp(snowy, np.broadcast_to(pine, rgb.shape) * (0.7 + lum[..., None] * 1.6), dark * 0.9)
    out = lerp(rgb, snowy, green)
    # nước -> băng
    ice = lerp(np.broadcast_to(np.array([0.50, 0.72, 0.86]), rgb.shape), np.broadcast_to(np.array([0.88, 0.96, 1.0]), rgb.shape), np.clip(lum * 1.3, 0, 1))
    out = lerp(out, ice, water * 0.9)
    # đường đất -> tuyết đã giẫm (xám ấm nhạt)
    trod = lerp(np.broadcast_to(np.array([0.62, 0.62, 0.68]), rgb.shape), np.broadcast_to(np.array([0.90, 0.90, 0.94]), rgb.shape), np.clip(lum * 1.2, 0, 1))
    out = lerp(out, trod, np.clip(dirt * 1.1, 0, 1))
    # đá/gỗ: lạnh màu đi + tuyết đọng mặt trên
    grey = out.mean(-1, keepdims=True)
    cold = np.clip((out * 0.35 + grey * 0.65) * np.array([0.93, 0.98, 1.07]) * 1.05, 0, 1)
    out = lerp(out, cold, np.clip(neutral, 0, 1) * 0.85)
    cap = np.clip(up * 1.6 - 0.5, 0, 1) * np.clip((lum - 0.30) / 0.25, 0, 1) * (1 - water) * (1 - green * 0.5)
    out = lerp(out, np.broadcast_to(snow_w, rgb.shape), cap * 0.8)
    # lấp lánh nhẹ
    spark = (rng.random(lum.shape) < 0.004) * green * (lum > 0.45)
    out = lerp(out, np.ones_like(out), spark * 0.7)
    out = np.clip(out, 0, 1)
    res = np.concatenate([out, al[..., None]], -1)
    img2 = Image.fromarray((res * 255).astype(np.uint8), "RGBA")
    if ornaments:
        L2 = np.asarray(Image.fromarray((lum * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))).astype(np.float32) / 255
        rough = np.asarray(Image.fromarray((np.abs(lum - L2) * 255 * 4).clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6))).astype(np.float32) / 255
        canopy = green * (al > 0.95) * (rough > 0.24) * (lum > 0.26) * (lum < 0.46) * (h > 88)
        add_ornaments(img2, canopy, rng)
    return img2

def add_ornaments(img, mask, rng, density=0.00012):
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    ys, xs = np.nonzero(mask > 0.5)
    if len(xs) == 0: return
    n = int(len(xs) * density)
    cols = [(220, 30, 40), (250, 200, 40), (60, 140, 230), (240, 240, 250), (200, 40, 160)]
    for i in rng.choice(len(xs), n, replace=False):
        x, y = xs[i], ys[i]
        c = cols[rng.integers(len(cols))]
        r = 2 + rng.integers(2)
        d.ellipse([x - r - 2, y - r - 2, x + r + 2, y + r + 2], fill=c[:3] + (60,))   # quầng sáng
        d.ellipse([x - r, y - r, x + r, y + r], fill=c + (255,))
        d.point([(x - 1, y - 1)], fill=(255, 255, 255, 255))
