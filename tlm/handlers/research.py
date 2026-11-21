"""Nghiên cứu lính (phòng thí nghiệm) -> cấp lính.

11005 sendResearch([chuỗi lính][byte]): game tự trừ dầu/dầu đen và đếm giờ. Server trừ giá Troop2.json
      (cấp kế tiếp: researchElixir/researchDarkElixir) và ghi research = {troop, end}.
11007 sendQuickResearch(): xong ngay bằng G (quy đổi thời gian còn lại).
11020 sendFinishResearch(): hết giờ -> xong.
Xong -> troop_levels[lính] + 1 (game tự cộng cấp trong máy qua LaboratoryObject::finishResearch).
CẤP LÍNH gửi lại mỗi lần tải làng trong BuildingInfo (danh sách ngay trước phòng thí nghiệm).
11021 sendGetSkillTroopInfo: [byte cờ][byte n] + n x [chuỗi][byte] là CẤP KỸ NĂNG lính (DataResearchStruct +0xc),
      KHÔNG phải cấp lính (+0x8). Bản 6.7 gửi nhầm cấp lính vào đây -> kỹ năng lính sai. Giờ trả rỗng.
"""
import time

from .. import state
from ..costs import time_cost
from ..data import load_table
from ..protocol.codec import Reader, u8
from . import handler

RESEARCH = load_table("research.json")


def levels_frame(st):
    return u8(0) + u8(0) + bytes(32)             # kỹ năng lính: chưa có


def _finish(ctx, ctl, st, why):
    res = st.get("research")
    if not res:
        return False
    t = res["troop"]
    lv = st.setdefault("troop_levels", {})
    lv[t] = int(lv.get(t, 1)) + 1
    st["research"] = None
    ctx.log("NGHIÊN CỨU XONG %s -> cấp %d (%s)" % (t, lv[t], why))
    return True


def settle_research(ctx, st):
    res = st.get("research")
    if res and float(res.get("end", 0)) <= time.time():
        return _finish(ctx, None, st, "hết giờ")
    return False


@handler(11005)
def research(ctx, ctl, cmd, payload):
    try:
        troop = Reader(payload).str()
    except Exception as e:
        ctx.log("nghiên cứu: không đọc được (%s)" % e)
        return False
    st = state.load(ctx.account)
    settle_research(ctx, st)
    nxt = int(st.get("troop_levels", {}).get(troop, 1)) + 1
    info = RESEARCH.get(troop, {}).get(str(nxt))
    if info is None:
        ctx.log("nghiên cứu %s: đã cấp tối đa" % troop)
        return False
    secs, elixir, dark, _ = info
    state.spend(st, elixir=elixir, dark=dark)
    st["research"] = {"troop": troop, "end": time.time() + secs}
    state.save(st, ctx.account)
    ctx.log("NGHIÊN CỨU %s lên cấp %d: -%d dầu -%d dầu đen, %d giây" % (troop, nxt, elixir, dark, secs))
    return False


@handler(11007, 11020)
def finish_research(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    res = st.get("research")
    if not res:
        ctx.log("xong nghiên cứu: không có nghiên cứu nào")
        return False
    if cmd == 11007:
        left = max(0, int(float(res["end"]) - time.time()))
        g = time_cost(left) if left else 0
        state.spend(st, coin=g)
        _finish(ctx, ctl, st, "xong ngay -%d G" % g)
    else:
        _finish(ctx, ctl, st, "hết giờ")
    state.save(st, ctx.account)
    ctx.reply(ctl, cmd, 0, None, "GỬI cmd=%d xong nghiên cứu" % cmd)
    return True


@handler(11021)
def get_levels(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    if settle_research(ctx, st):
        state.save(st, ctx.account)
    ctx.reply(ctl, 11021, 0, levels_frame(st), "GỬI cmd=11021 kỹ năng lính (rỗng)")
    return True
