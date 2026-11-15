"""Giờ máy chủ, kho đồ (vật phẩm) và gia hạn trang trí.

1015 GetCurTime: game hỏi giờ định kỳ; phản hồi [double giây] -> Utility::setCurTime. Bản cũ trả số 0 nên
     đồng hồ game bị đặt về 0 liên tục -> mọi thứ tính theo thời gian (trang trí hết hạn, sự kiện, làm mới
     cửa hàng...) sai. Giờ trả giờ thật.
10008 ItemInfo (CmdReceiveItemInfo::readData):
     [short n] + n x [int id][byte loại][byte cấp][int số lượng][byte cờ]       (vật phẩm thường)
     [short m] + m x [int id][byte loại][byte cấp][int số lượng][double giờ]    (vật phẩm đang làm: 0)
     loại/cấp tra Item.json qua JsonMgr::getDataInventoryItem(loại, cấp).
10005 sendUseItemRes: [int id vật phẩm][short số lượng] - dùng túi tài nguyên (loại 1 vàng, 2 dầu, 3 dầu đen).
2014 sendResetDecoration: [int id] - gia hạn trang trí hết hạn (trừ costExpire G, tính lại từ bây giờ).
"""
import time

from .. import gamedata, state
from ..protocol.codec import Reader, f64, u8, u16, u32
from . import handler


def build_items(st):
    items = [i for i in st.get("items", []) if int(i.get("count", 0)) > 0]
    d = u16(len(items))
    for i in items:
        d += u32(i["id"]) + u8(int(i["type"])) + u8(int(i["sub"])) + u32(int(i["count"])) + u8(0)
    return d + u16(0) + bytes(64)


def add_item(st, itype, sub, count):
    """Cộng vật phẩm vào kho (gộp với vật phẩm cùng loại/cấp). Trả về vật phẩm."""
    items = st.setdefault("items", [])
    it = next((i for i in items if int(i["type"]) == itype and int(i["sub"]) == sub), None)
    if it is None:
        it = {"id": max([i["id"] for i in items] or [0]) + 1, "type": itype, "sub": sub, "count": 0}
        items.append(it)
    it["count"] = int(it["count"]) + count
    return it


def item_name(itype, sub):
    info = gamedata.ITEMS.get(str(itype), {}).get(str(sub), {})
    kind = {"1": "túi vàng", "2": "túi dầu hồng", "3": "túi dầu đen"}.get(str(itype))
    if kind:
        return "%s %s" % (kind, "{:,}".format(info.get("value", 0)).replace(",", "."))
    return info.get("name") or "vật phẩm loại %s cấp %s" % (itype, sub)


@handler(1015)
def cur_time(ctx, ctl, cmd, payload):
    ctx.reply(ctl, 1015, 0, f64(int(time.time())) + bytes(64), "GỬI cmd=1015 giờ máy chủ")
    return True


@handler(10008)
def item_info(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    ctx.reply(ctl, 10008, 0, build_items(st),
              "GỬI cmd=10008 kho đồ: %d vật phẩm" % len([i for i in st.get("items", []) if i.get("count")]))
    return True


@handler(10005)
def use_item_res(ctx, ctl, cmd, payload):
    try:
        r = Reader(payload)
        iid = r.u32(); n = max(1, r.u16())
    except Exception as e:
        ctx.log("dùng vật phẩm: không đọc được (%s)" % e)
        return False
    st = state.load(ctx.account)
    it = next((i for i in st.get("items", []) if i["id"] == iid), None)
    if it is None or int(it["count"]) <= 0:
        ctx.log("dùng vật phẩm id=%d: không có trong kho" % iid)
        return False
    n = min(n, int(it["count"]))
    key = gamedata.ITEM_RES.get(str(it["type"]))
    value = int(gamedata.ITEMS.get(str(it["type"]), {}).get(str(it["sub"]), {}).get("value", 0))
    if key:
        state.add_resource(st, key, value * n)
    it["count"] = int(it["count"]) - n
    state.save(st, ctx.account)
    ctx.log("DÙNG %d x %s (còn %d)" % (n, item_name(it["type"], it["sub"]), it["count"]))
    return False


@handler(2014)
def reset_deco(ctx, ctl, cmd, payload):
    try:
        bid = Reader(payload).u32()
    except Exception as e:
        ctx.log("gia hạn trang trí: không đọc được (%s)" % e)
        return False
    st = state.load(ctx.account)
    b = state.find_building(st, bid, category="DEC")
    if b is None:
        ctx.log("gia hạn trang trí: không thấy id=%d" % bid)
        return False
    cost = int(gamedata.DECO.get(b["type"], {}).get("costExpire", 0))
    coin = state.effective_resources(st)[3]
    st["player"]["coin"] = max(0, coin - cost)
    b["placed_at"] = int(time.time())
    state.save(st, ctx.account)
    ctx.log("GIA HẠN TRANG TRÍ %s id=%d, trừ %d G" % (b["type"], bid, cost))
    return False
