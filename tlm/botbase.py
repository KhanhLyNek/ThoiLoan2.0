"""Dựng làng đối thủ (bot) cho phó bản và chinh phạt.

Số công trình mỗi loại theo cấp nhà chính lấy từ TownHall.json; cấp công trình tối đa theo
townHallLevelRequired (chỉ lấy cấp có ảnh trong APK/OBB); kích thước từ JSON công trình.
Làng được đặt ngẫu nhiên quanh nhà chính trên lưới 44x44 ô (giống bản đồ làng), không chồng lấn.
Chiến lợi phẩm chia cho nhà chính, kho và mỏ (trường vàng/dầu/dầu đen của công trình trong trận).
"""
import random

from .data import load_table

GEN = load_table("battle_gen.json")
MAP_W = 44                                     # BaseMap::cellToIso: ô = y * 44 + x (CityMap rộng 0x2c)
LOOT_HOLDERS = ("TOW", "STO", "RES")
BOT_NAMES = ["Hắc Long", "Bạch Hổ", "Thanh Phong", "Lão Tướng", "Kiếm Khách", "Sơn Tặc", "Hải Tặc",
             "Thủ Lĩnh Đỏ", "Chiến Binh", "Lãnh Chúa", "Thợ Săn", "Du Mục", "Phù Thuỷ", "Hiệp Sĩ"]


def _level(btype, th):
    return int(GEN["max_level"].get(btype, {}).get(str(th), 1))


def generate(th, seed, gold=0, elixir=0, dark=0, fill=1.0):
    """Trả về danh sách công trình [{id, type, x, y, level, gold, elixir, dark}] cho nhà chính cấp th."""
    th = max(1, min(11, int(th)))
    rnd = random.Random(seed)
    occupied = set()

    def free(x, y, s):
        if x < 2 or y < 2 or x + s > MAP_W - 2 or y + s > MAP_W - 2:
            return False
        return all((i, j) not in occupied for i in range(x - 1, x + s + 1) for j in range(y - 1, y + s + 1))

    def mark(x, y, s):
        for i in range(x, x + s):
            for j in range(y, y + s):
                occupied.add((i, j))

    out = []
    c = MAP_W // 2 - 2
    mark(c, c, 4)
    out.append({"type": "TOW_1", "x": c, "y": c, "level": th})
    want = []
    for btype, n in GEN["th_counts"].get(str(th), {}).items():
        n = max(1, int(round(n * fill))) if n else 0
        want += [btype] * n
    # phòng thủ trước (gần nhà chính), rồi kho, mỏ, còn lại ra ngoài
    order = {"DEF": 0, "STO": 1, "LAB": 2, "BAR": 3, "AMC": 3, "RES": 4, "BDH": 5}
    rnd.shuffle(want)
    want.sort(key=lambda t: order.get(t[:3], 6))
    for btype in want:
        s = int(GEN["size"].get(btype, 3))
        for radius in range(4, MAP_W // 2):
            spots = [(c + dx, c + dy) for dx in range(-radius, radius + 1) for dy in range(-radius, radius + 1)
                     if max(abs(dx), abs(dy)) == radius]
            rnd.shuffle(spots)
            spot = next(((x, y) for x, y in spots if free(x, y, s)), None)
            if spot:
                mark(spot[0], spot[1], s)
                out.append({"type": btype, "x": spot[0], "y": spot[1], "level": _level(btype, th)})
                break
    # chia chiến lợi phẩm: vàng cho nhà chính + kho vàng + mỏ vàng, dầu tương tự, dầu đen cho STO_3/RES_3
    def spread(key, total, kinds):
        holders = [b for b in out if b["type"] in kinds] or [out[0]]
        for i, b in enumerate(holders):
            share = total // len(holders) + (1 if i < total % len(holders) else 0)
            b[key] = b.get(key, 0) + share
    spread("gold", int(gold), ("TOW_1", "STO_1", "RES_1"))
    spread("elixir", int(elixir), ("TOW_1", "STO_2", "RES_2"))
    if dark:
        spread("dark", int(dark), ("TOW_1", "STO_3", "RES_3"))
    for i, b in enumerate(out, 1):
        b["id"] = i
    return out


def single_map(level):
    """Màn phó bản 1-50: nhà chính tăng dần, chiến lợi phẩm theo SingleBattle.json."""
    info = GEN["single"].get(str(level), {"gold": 500, "elixir": 500, "name": "A%d" % level})
    th = min(11, 1 + (int(level) - 1) // 5)
    fill = 0.5 + 0.5 * (((int(level) - 1) % 5) / 4.0)       # trong cùng cấp nhà chính, màn sau đông hơn
    base = generate(th, seed=1000 + int(level), gold=info["gold"], elixir=info["elixir"], fill=fill)
    return base, "Phó bản %s" % info.get("name", level), th


def random_enemy(player_th, rnd=None):
    """Đối thủ chinh phạt: nhà chính quanh cấp người chơi, chiến lợi phẩm ngẫu nhiên theo cấp."""
    rnd = rnd or random.Random()
    th = max(1, min(11, int(player_th) + rnd.choice((-1, 0, 0, 1))))
    gold = rnd.randint(800, 2500) * th * th
    elixir = rnd.randint(800, 2500) * th * th
    dark = rnd.randint(10, 60) * th * th if th >= 7 else 0
    seed = rnd.randint(1, 10 ** 9)
    base = generate(th, seed=seed, gold=gold, elixir=elixir, dark=dark, fill=rnd.uniform(0.7, 1.0))
    return base, rnd.choice(BOT_NAMES), th, seed
