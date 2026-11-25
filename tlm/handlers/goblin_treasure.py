"""KHO BÁU YÊU TINH (GoblinTreasureMgr, GiftHunting.json) - THỬ NGHIỆM, định dạng suy từ mã game.

7071 getGoblinTreasureInfo -> onReceiveGoblinTreasureInfo:
     [byte bảng quà @0x50][int VÉ QUAY @0x2c][int ĐIỂM @0x28][int bậc đổi điểm @0x48][int n] n x [int id quà][int số bóng]
     (GoblinTreasureGUI::updateGui hiện "điểm / pointCoinExchangeRate[bậc]")
7072 spin [int số lần] -> onReceiveGoblinTreasureSpin: [int n] n x [int id quà][int bóng thêm]
     (quà @0x30 += bóng, @0x1c = bóng / 3 = số lần nhận được)
7073 sendReceiveGift [int id]... -> nhận quà vào kho (server trả 0 + cập nhật kho đồ)
Điểm: cướp được vàng/dầu (goldPointRate/elixirPointRate) + dầu đen (darkElixirPointRate) -> đủ mốc thì +1 vé.
Vé miễn phí mỗi ngày lúc 7h, 15h, 23h (dailyFreeCoin theo cấp nhà chính). Hết vé thì quay bằng G (costPerSpin).
id quà = vị trí trong spinConfig (nhà chính <= 6) / spinConfig2.
"""
import random
import time

from .. import state
from ..data import load_table
from ..protocol.codec import u8, u32
from . import handler
from .inventory import add_item, build_items

GH = load_table("gift_hunting.json")


def _th(st):
    return next((b["level"] for b in st["buildings"] if b["type"] == "TOW_1"), 1)


def _cfg(st):
    return GH["spinConfig"] if _th(st) <= 6 else GH["spinConfig2"]


def _gt(st):
    g = st.setdefault("goblin_treasure", {"coin": 0, "points": 0, "xlevel": 0, "balls": {}, "free": 0})
    th = str(min(max(_th(st), 5), 12))
    now = time.time() + 7 * 3600                     # giờ VN
    last = float(g.get("free") or 0)
    if not last:
        g["free"] = now
        g["coin"] += 5
    else:
        sched = GH["dailyFreeCoin"].get(th, {})
        t = int(last // 3600) + 1
        while t * 3600 <= now and t - last / 3600 < 24 * 3:
            n = int(sched.get(str(t % 24), 0))
            g["coin"] += n
            t += 1
        g["free"] = now
    return g


def on_battle(st, gold, elixir, dark):
    if _th(st) < int(GH["config"]["levelRequire"]):
        return
    c = GH["config"]
    g = _gt(st)
    g["points"] += gold // max(1, c["goldPointRate"]) + elixir // max(1, c["elixirPointRate"]) + dark // max(1, c["darkElixirPointRate"])
    rates = c["pointCoinExchangeRate"]
    while g["xlevel"] < len(rates) and g["points"] >= rates[g["xlevel"]]:
        g["points"] -= rates[g["xlevel"]]
        g["xlevel"] += 1
        g["coin"] += 1


def info(st):
    g = _gt(st)
    balls = sorted((int(k), int(v)) for k, v in g["balls"].items() if int(v) > 0)
    return (u8(1 if _th(st) <= 6 else 2) + u32(g["coin"]) + u32(g["points"]) + u32(g["xlevel"])
            + u32(len(balls)) + b"".join(u32(k) + u32(v) for k, v in balls) + bytes(32))


@handler(7071)
def get_info(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    d = info(st)
    state.save(st, ctx.account)
    g = st["goblin_treasure"]
    ctx.reply(ctl, 7071, 0, d, "GỬI cmd=7071 kho báu yêu tinh: %d vé, %d điểm" % (g["coin"], g["points"]))
    return True


@handler(7072)
def spin(ctx, ctl, cmd, payload):
    n = int.from_bytes(payload[:4], "big") if len(payload) >= 4 else 1
    n = max(1, min(n, 50))
    st = state.load(ctx.account)
    g = _gt(st)
    use = min(n, g["coin"])
    g["coin"] -= use
    if n > use:
        c = GH["config"]
        cost = (n - use) * int(c["costPerSpin"])
        for k, q in zip(c["quickSpinNum"], c["quickSpinCost"]):
            if n == k and use == 0:
                cost = int(q)
        state.spend(st, coin=cost)
    cfg = _cfg(st)
    ok = [i for i, x in enumerate(cfg) if str(x.get("outGame")) != "true"]
    got = {}
    for _ in range(n):
        i = random.choices(ok, weights=[int(cfg[k].get("rate", 1)) for k in ok])[0]
        got[i] = got.get(i, 0) + 1
    for i, k in got.items():
        g["balls"][str(i)] = int(g["balls"].get(str(i), 0)) + k
    state.save(st, ctx.account)
    ctx.reply(ctl, 7072, 0, u32(len(got)) + b"".join(u32(i) + u32(k) for i, k in sorted(got.items())) + bytes(32),
              "GỬI cmd=7072 quay kho báu x%d (%d vé, %d bằng G): %s" % (n, use, n - use, got))
    return True


@handler(7073)
def receive(ctx, ctl, cmd, payload):
    gid = int.from_bytes(payload[:4], "big") if len(payload) >= 4 else -1
    st = state.load(ctx.account)
    g = _gt(st)
    cfg = _cfg(st)
    out = []
    ids = [gid] if 0 <= gid < len(cfg) else [int(k) for k, v in g["balls"].items() if int(v) >= 3]
    for i in ids:
        while int(g["balls"].get(str(i), 0)) >= 3:
            g["balls"][str(i)] = int(g["balls"][str(i)]) - 3
            x = cfg[i]
            add_item(st, int(x["itemType"]), int(x["itemLevel"]), int(x["num"]))
            out.append("loại %s x%s" % (x["itemType"], x["num"]))
    state.save(st, ctx.account)
    ctx.reply(ctl, 7073, 0, u8(0) + bytes(32), "GỬI cmd=7073 nhận quà kho báu: %s" % (", ".join(out) or "không có"))
    ctx.reply(ctl, 10008, 0, build_items(st), "GỬI cmd=10008 cập nhật kho đồ")
    return True
