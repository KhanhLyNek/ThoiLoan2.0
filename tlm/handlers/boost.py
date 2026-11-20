"""Khiên bảo vệ (1018) và luyện quân nhanh (11004).

1018 ShopGUI(2)::doBuySheild -> sendBuySheild([byte loại 1..3]); game tự trừ G và tự cộng giờ:
     loại   G    khiên       thời gian chờ mua lại
       1   100   1 ngày      5 ngày
       2   150   2 ngày      10 ngày
       3   250   7 ngày      35 ngày
     gốc = max(giờ khiên hiện tại, bây giờ); khiên = gốc + thời gian; chờ[loại] = gốc + thời gian chờ.
     Không có nhánh phản hồi riêng (chỉ errorCodeHandler). Lưu vào player:
       shield_end -> GetPlayerInfo @0x80 (GameDataMgr+0x128)
       shield_cd[3] -> cờ true + 3 double @0x98/@0x9c/@0xa0 (GameDataMgr+0x140..)
11004 BarrackObject::quickTrain -> sendQuickTraining([int id trại]); game đã trừ
     Utility::getCostToBuyTime(tổng thời gian còn lại) G. Server tính lại theo thời gian luyện đã ghi.
"""
import time

from .. import state
from ..costs import time_cost
from ..protocol.codec import Reader
from . import handler

SHIELDS = {1: (100, 86400, 432000), 2: (150, 172800, 864000), 3: (250, 604800, 3024000)}


@handler(1018)
def buy_shield(ctx, ctl, cmd, payload):
    kind = payload[0] if payload else 0
    if kind not in SHIELDS:
        ctx.log("mua khiên: loại lạ %d" % kind)
        return False
    price, dur, cd = SHIELDS[kind]
    st = state.load(ctx.account)
    p = st["player"]
    now = int(time.time())
    cds = list(p.get("shield_cd", [0, 0, 0]))
    if cds[kind - 1] > now:
        ctx.log("mua khiên loại %d: còn chờ %d giây" % (kind, cds[kind - 1] - now))
    state.spend(st, coin=price)
    base = max(int(p.get("shield_end", 0)), now)
    p["shield_end"] = base + dur
    cds[kind - 1] = base + cd
    p["shield_cd"] = cds
    state.save(st, ctx.account)
    ctx.log("MUA KHIÊN loại %d: -%d G, khiên tới %s" % (kind, price, time.strftime("%d/%m %H:%M", time.localtime(p["shield_end"]))))
    return False                         # trả error 0


def train_seconds_left(st, bid):
    end = float(st.get("train_end", {}).get(str(bid), 0))
    return max(0, int(end - time.time()))


@handler(11004)
def quick_train(ctx, ctl, cmd, payload):
    try:
        bid = Reader(payload).u32()
    except Exception:
        bid = 0
    st = state.load(ctx.account)
    left = train_seconds_left(st, bid)
    g = time_cost(left) if left else 0
    state.spend(st, coin=g)
    st.setdefault("train_end", {})[str(bid)] = 0
    state.save(st, ctx.account)
    ctx.log("LUYỆN NHANH trại id=%d: còn %d giây -> -%d G" % (bid, left, g))
    return False
