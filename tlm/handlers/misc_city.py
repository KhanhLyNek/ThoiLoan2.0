"""Các lệnh làng còn thiếu (trước v7.9 server tự trả số 0 nhưng KHÔNG lưu gì -> vào lại game bị lệch):

2009 cancelPlace        [chuỗi loại][int id][byte]  huỷ đang xây / đang nâng cấp -> hoàn 50% giá
                         (đang xây mới -> xoá công trình; đang nâng cấp -> về cấp cũ)
2027 sendRepairTrap     [int id]       sửa bẫy đã nổ (giá = giá cấp hiện tại / 10 vàng... game tự trừ; server ghi nhận)
2012 sendRebuildClanCastle             dựng lại lâu đài bang cấp 1 (nếu chưa có)
1011 sendChangeName     [chuỗi tên]    đổi tên
11012 sendHealKQ        [byte loại]    hồi máu anh hùng bằng G -> ghi nhận
11013 sendUpdateKQ      [byte loại]    anh hùng ngủ / canh -> ghi nhận
"""
import time

from .. import gamedata, state
from ..protocol.codec import Reader
from . import handler


@handler(2009)
def cancel_place(ctx, ctl, cmd, payload):
    r = Reader(payload)
    try:
        btype, bid = r.str(), r.u32()
    except Exception as e:
        ctx.log("huỷ xây: không đọc được (%s)" % e)
        return False
    st = state.load(ctx.account)
    b = state.find_building(st, bid, btype=btype or None)
    if not b:
        ctx.log("huỷ xây: không thấy %s id=%s" % (btype, bid))
        return False
    c = gamedata.cost_of(b["type"], b["level"])
    refund = [int(x) // 2 for x in c]
    for key, v in zip(("gold", "elixir", "dark_elixir"), refund[:3]):
        if v:
            state.add_resource(st, key, v)
    if b["level"] <= 1:
        st["buildings"].remove(b)
        what = "xoá công trình đang xây"
    else:
        b["level"] -= 1
        what = "về cấp %d" % b["level"]
    b.pop("busy_until", None)
    state.save(st, ctx.account)
    ctx.log("HUỶ XÂY/NÂNG %s id=%d: %s, hoàn %s" % (btype, bid, what, refund))
    return False


@handler(2027)
def repair_trap(ctx, ctl, cmd, payload):
    bid = int.from_bytes(payload[:4], "big") if len(payload) >= 4 else 0
    st = state.load(ctx.account)
    b = state.find_building(st, bid)
    if b is not None:
        b.pop("broken", None)
        state.save(st, ctx.account)
    ctx.log("SỬA BẪY id=%d" % bid)
    return False


@handler(2012)
def rebuild_cc(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    if not any(b["type"].startswith("CLC") for b in st["buildings"]):
        st["buildings"].append({"id": state.next_id(st, "CLC_1"), "type": "CLC_1", "x": 22, "y": 22, "level": 1})
        state.save(st, ctx.account)
        ctx.log("DỰNG LẠI LÂU ĐÀI BANG cấp 1")
    return False


@handler(1011)
def change_name(ctx, ctl, cmd, payload):
    try:
        name = Reader(payload).str().strip()
    except Exception:
        return False
    if name:
        st = state.load(ctx.account)
        old = st["player"].get("name", "")
        st["player"]["name"] = name[:20]
        state.save(st, ctx.account)
        ctx.log("ĐỔI TÊN: %s -> %s" % (old, name[:20]))
    return False


@handler(11012, 11013)
def hero_state(ctx, ctl, cmd, payload):
    kind = payload[0] if payload else 0
    st = state.load(ctx.account)
    h = st.setdefault("hero_state", {})
    if cmd == 11012:
        h[str(kind)] = {"healed": int(time.time())}
        ctx.log("HỒI MÁU ANH HÙNG loại %d" % kind)
    else:
        h.setdefault(str(kind), {})["toggled"] = int(time.time())
        ctx.log("ĐỔI TRẠNG THÁI ANH HÙNG loại %d" % kind)
    state.save(st, ctx.account)
    return False
