"""Xây, nâng cấp, thu hoạch, dọn chướng ngại - cập nhật state.json."""
import time

from .. import gamedata, state
from ..protocol.codec import Reader, parse_id_and_type
from . import handler


@handler(2001)
def place_building(ctx, ctl, cmd, payload):
    """sendPlaceBuilding: [chuỗi loại][byte x][byte y][int]. Trả error 0 = cho xây."""
    err, note = _place(payload, ctx.account)
    ctx.log(note)
    ctx.reply(ctl, 2001, err, desc="GỬI cmd=2001 (đặt công trình) error=%d" % err)
    return True


def _place(payload, account):
    try:
        r = Reader(payload)
        btype = r.str(); x = r.u8(); y = r.u8()
    except Exception as e:
        return 1, "không đọc được dữ liệu đặt công trình (%s)" % e
    cat = gamedata.CATEGORY.get(btype[:3])
    levels = gamedata.IMAGE_LEVELS.get(btype, [])
    st = state.load(account)
    if cat is None:
        return 1, "TỪ CHỐI %s: loại này chưa hỗ trợ (hỗ trợ: %s)" % (btype, ", ".join(sorted(gamedata.CATEGORY)))
    if cat in gamedata.SINGLE and any(gamedata.CATEGORY.get(b["type"][:3]) == cat for b in st["buildings"]):
        return 1, "TỪ CHỐI %s: chỉ được có một công trình loại này" % btype
    if not levels:
        return 1, "TỪ CHỐI %s: không có ảnh nào của loại này" % btype
    new_id = state.next_id(st, btype)
    if 1 in levels:
        st["buildings"].append({"id": new_id, "type": btype, "x": x, "y": y, "level": 1, "pending_id": True,
                                "busy_until": time.time() + gamedata.build_time(btype, 1)})
        c = state.pay(st, btype, 1)
        state.save(st, account)
        return 0, "ĐÃ XÂY %s cấp 1 tại (%d,%d), id=%d, trừ %s (vàng/dầu/dầu đen/G)" % (btype, x, y, new_id, c)
    lvl = min(levels)
    st["buildings"].append({"id": new_id, "type": btype, "x": x, "y": y, "level": lvl})
    state.save(st, account)
    return 1, ("TỪ CHỐI trong phiên (không có ảnh %s cấp 1) nhưng ĐÃ LƯU ở cấp %d tại (%d,%d) "
               "-> vào lại game để thấy" % (btype, lvl, x, y))


@handler(2003)
def upgrade(ctx, ctl, cmd, payload):
    """sendUpgradeBuilding: [chuỗi loại][int id][int][byte]. Trừ giá cấp kế tiếp, lưu cấp mới."""
    bid, btype = parse_id_and_type(payload)
    st = state.load(ctx.account)
    b = state.find_building(st, bid, btype=btype or None)
    if not b:
        ctx.log("nâng cấp: không thấy công trình %s id=%s" % (btype, bid))
        return False
    new_level = b["level"] + 1
    if b["type"] in gamedata.COST and str(new_level) not in gamedata.COST[b["type"]]:
        ctx.log("nâng cấp %s: đã ở cấp tối đa" % b["type"])
        return False
    c = state.pay(st, b["type"], new_level)
    b["level"] = new_level
    b["busy_until"] = time.time() + gamedata.build_time(b["type"], new_level)
    state.save(st, ctx.account)
    ctx.log("NÂNG CẤP %s id=%d lên cấp %d, trừ %s" % (b["type"], bid, new_level, c))
    return False                      # để server tự trả lời "thành công"


@handler(2004)
def collect(ctx, ctl, cmd, payload):
    """sendCollect: [int id] (chỉ mỏ, nhóm RES). Thu hoạch theo thời gian (Resource.json)."""
    bid, _ = parse_id_and_type(payload)
    st = state.load(ctx.account)
    b = state.find_building(st, bid, category="RES")
    if not b or b["type"] not in gamedata.RES_INFO:
        ctx.log("thu hoạch: id=%s không phải mỏ" % bid)
        return False
    rtype, rate, cap = gamedata.RES_INFO[b["type"]].get(str(b["level"]), [None, 0, 0])
    now = time.time()
    last = b.get("collected_at")
    amount = cap if last is None else min(cap, int(rate * (now - last) / 3600.0))
    b["collected_at"] = now
    key = gamedata.RES_KEY.get(rtype)
    if key:
        state.add_resource(st, key, amount)
    state.save(st, ctx.account)
    ctx.log("THU HOẠCH %s id=%d: +%d %s" % (b["type"], bid, amount, rtype))
    return False


@handler(2010, 2011)
def remove_obstacle(ctx, ctl, cmd, payload):
    """sendRemoveOBS / sendFinishRemoveOBS: xoá chướng ngại khỏi state, trừ giá Obstacle.json."""
    bid, _ = parse_id_and_type(payload)
    st = state.load(ctx.account)
    o = next((x for x in st.get("obstacles", []) if x["id"] == bid), None)
    if o:
        st["obstacles"].remove(o)
        st.setdefault("timers", {})["OBS:%d" % bid] = time.time() + gamedata.build_time(o["type"], 1)
        c = state.pay(st, o["type"], 1)
        state.save(st, ctx.account)
        ctx.log("DỌN CHƯỚNG NGẠI %s id=%d, trừ %s" % (o["type"], bid, c))
    return False
