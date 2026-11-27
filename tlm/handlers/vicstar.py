"""SỰ KIỆN SAO CHIẾN THẮNG (CollectStarGUI, EventConfig vicStar*). THỬ NGHIỆM.

Mở khi GameDataMgr::isVicStarEvent (giờ trong [vicStarStart, vicStarEnd], nhà chính >= vicStarRequireTownHallLevel).
7020 sendGetVicStarInfo -> [short SỐ SAO @GameDataMgr+0x538][byte n] n x [byte trạng thái mốc (2 = đã nhận)]
     -> GameDataMgr+0x558; CollectStarGUI::checkVicStarSTT: mốc vicStarRequire[i] <= số sao và chưa nhận -> chấm đỏ.
7078 sendGetRewardVicStar [int mốc] -> nhận quà mốc (server: vicStarRequire[i] x vicStarRateG[i] G), trả lại 7020.
7077 sendQuickRewardVicStar [int mốc] -> mua đủ sao bằng G rồi nhận.
Sao cộng từ mỗi trận tấn công (handlers/battle.py gọi on_battle); làm lại mỗi tuần (thứ Hai, giờ VN).
"""
import time

from .. import state
from ..data import load_table
from ..protocol.codec import u8, u16
from . import handler
from .payment import push_coin

EV = load_table("event_config.json")
REQ = [int(x) for x in EV.get("vicStarRequire", [30, 45, 60, 75, 90, 105])]
RATE = [int(x) for x in EV.get("vicStarRateG", [1, 2, 3, 3, 4, 4])]


def _week():
    t = time.gmtime(time.time() + 7 * 3600)
    return time.strftime("%G-%V", t)


def _v(st):
    v = st.setdefault("vicstar", {})
    if v.get("week") != _week():
        v.update(week=_week(), stars=0, got=[])
    return v


def info(v):
    return u16(min(int(v["stars"]), 0x7fff)) + u8(len(REQ)) + b"".join(u8(2 if i in v["got"] else 0)
                                                                        for i in range(len(REQ))) + bytes(16)


def _send(ctx, ctl, v, why):
    ctx.reply(ctl, 7020, 0, info(v), "GỬI cmd=7020 sao chiến thắng: %d sao, đã nhận mốc %s (%s)" % (v["stars"], v["got"], why))


@handler(7020)
def get_info(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    v = _v(st)
    state.save(st, ctx.account)
    _send(ctx, ctl, v, "thông tin")
    return True


@handler(7078, 7077)
def reward(ctx, ctl, cmd, payload):
    i = int.from_bytes(payload[:4], "big") if len(payload) >= 4 else 0
    st = state.load(ctx.account)
    v = _v(st)
    if not (0 <= i < len(REQ)) or i in v["got"]:
        ctx.log("sao chiến thắng: mốc %d không hợp lệ / đã nhận" % i)
        _send(ctx, ctl, v, "từ chối")
        return True
    if cmd == 7077 and v["stars"] < REQ[i]:
        cost = (REQ[i] - int(v["stars"])) * 2
        state.spend(st, coin=cost)
        v["stars"] = REQ[i]
        ctx.log("MUA SAO CHIẾN THẮNG đủ mốc %d: -%d G" % (i, cost))
    if v["stars"] < REQ[i]:
        ctx.log("sao chiến thắng: chưa đủ sao cho mốc %d (%d/%d)" % (i, v["stars"], REQ[i]))
        _send(ctx, ctl, v, "chưa đủ")
        return True
    g = REQ[i] * RATE[min(i, len(RATE) - 1)]
    v["got"].append(i)
    st["player"]["coin"] = int(st["player"].get("coin", 0)) + g
    state.save(st, ctx.account)
    ctx.log("NHẬN QUÀ SAO CHIẾN THẮNG mốc %d (%d sao): +%d G" % (i, REQ[i], g))
    push_coin(ctx, ctl, st)
    _send(ctx, ctl, v, "đã nhận")
    return True


def on_battle(st, stars):
    if stars > 0:
        v = _v(st)
        v["stars"] = int(v["stars"]) + int(stars)
