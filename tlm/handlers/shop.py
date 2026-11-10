"""Mua bằng G: sendBuyRes (cmd 1076) = mua phần tài nguyên còn thiếu.

Dữ liệu client: [int vàng][int dầu hồng][int dầu đen][int] (log: 000000fa 00000000... = mua 250 vàng).
Server cộng tài nguyên và trừ G theo Utility::getCostToBuyResources (costs.resource_cost).
"""
from .. import costs, state
from ..protocol.codec import Reader
from . import handler


@handler(1076)
def buy_resources(ctx, ctl, cmd, payload):
    try:
        r = Reader(payload)
        gold, elixir, dark = r.i32(), r.i32(), r.i32()
    except Exception as e:
        ctx.log("mua tài nguyên: không đọc được dữ liệu (%s)" % e)
        return False
    st = state.load(ctx.account)
    p = st["player"]
    g = costs.resource_cost(max(0, gold), max(0, elixir), max(0, dark))
    p["gold"] = int(p.get("gold", 0)) + max(0, gold)
    p["elixir"] = int(p.get("elixir", 0)) + max(0, elixir)
    p["dark_elixir"] = int(p.get("dark_elixir", 0)) + max(0, dark)
    p["coin"] = max(0, int(p.get("coin", 0)) - g)
    state.save(st, ctx.account)
    ctx.log("MUA BẰNG G: +%d vàng +%d dầu +%d dầu đen, trừ %d G (còn %d G)" % (gold, elixir, dark, g, p["coin"]))
    return False                      # server tự trả lời "thành công"
