"""CÁ NHÂN: nhân vật (tướng đại diện) + KHẢM NGỌC/PHA LÊ (CrystalMgr, GemSupport.json) + trang bị đang mặc.

Trước v8.0 server trả số 0 cho tất cả -> chọn nhân vật, mở/khảm ngọc xong thoát ra là mất hết.

1053 sendSetCharacter [chuỗi nhân vật]  (chọn lần đầu)      1068 doChangeChar [chuỗi] (đổi, 500 G = CharacterCommon.costChange)
1082 (CityMgr::onGetCharacter, gửi lúc vào game) -> [chuỗi nhân vật]["" = chưa chọn -> game mở bảng chọn]
     [byte cấp][byte n] n x DataEquipment (trang bị đang mặc) [doubleA giờ đổi nhân vật]
1087 getCrystalInfo -> CrystalMgr::onReceiveCrystalInfo:
     [byte cấp hệ thống @0xc8][int n] n x [byte Ô][short id ngọc][byte cấp][int số]   (ngọc đang khảm)
     [int m] m x [short id][byte cấp][int số]                                         (ngọc trong túi)
     [bool @0xcc][int k] k x [byte ô][bool mở]                                        (ô đã mở)
1088 equipCrystal [byte ô][short id][byte cấp]     1089 unEquipCrystal [byte ô]
1091 unlockSlot [byte ô]  |  saveSlotList [int n] n x [byte ô]
1093 openCrystal [byte cấp][byte bộ][int số] -> dùng vật phẩm loại 77 (đá pha lê) -> [int n] n x [short id][byte cấp][int số]
     (ngọc ra theo GemSupport.json collection[bộ], tỉ lệ rates[cấp-1])
1094 buyCrystal [byte mục shop][int số][byte] -> trừ G (GemSupport shop.cost), cộng đá pha lê (loại 77) vào kho
1095 mergeCrystal [int n] n x [short id][byte cấp][int số] -> [short id][byte cấp] (3 viên cùng cấp -> 1 viên cấp + 1)
1097 sendUpdateCrystalTutorial                      1100 sendGetEquipingCrystalInfo [int uid] -> [byte][int n] n x ô
Lưu: st["character"] = {"type", "level", "changed"}; st["gems"] = {"level", "slots": {ô: [id, cấp]},
     "bag": {"id:cấp": số}, "open": [ô], "order": [ô], "tut": 0|1}
"""
import random
import time

from .. import state
from ..data import load_table
from ..protocol.codec import Reader, f64, pstr, u8, u16, u32
from . import handler
from .inventory import add_item, build_items

GEM = load_table("gem_support.json")


def _gems(st):
    g = st.setdefault("gems", {})
    g.setdefault("level", 1)
    g.setdefault("slots", {})
    g.setdefault("bag", {})
    g.setdefault("open", [])
    g.setdefault("tut", 0)
    return g


def _bag_add(g, gid, lvl, n):
    k = "%d:%d" % (gid, lvl)
    g["bag"][k] = int(g["bag"].get(k, 0)) + n
    if g["bag"][k] <= 0:
        g["bag"].pop(k)


def _i16(v):
    return (int(v) & 0xffff).to_bytes(2, "big")


def crystal_info(st):
    g = _gems(st)
    slots = sorted((int(s), v) for s, v in g["slots"].items())
    d = u8(g["level"]) + u32(len(slots)) + b"".join(u8(s) + _i16(v[0]) + u8(v[1]) + u32(1) for s, v in slots)
    bag = [(int(k.split(":")[0]), int(k.split(":")[1]), n) for k, n in sorted(g["bag"].items()) if n > 0]
    d += u32(len(bag)) + b"".join(_i16(i) + u8(l) + u32(n) for i, l, n in bag)
    d += u8(1 if g["tut"] else 0) + u32(len(g["open"])) + b"".join(u8(s) + u8(1) for s in sorted(g["open"]))
    return d


@handler(1053, 1068)
def set_character(ctx, ctl, cmd, payload):
    try:
        ch = Reader(payload).str()
    except Exception:
        return False
    st = state.load(ctx.account)
    c = st.setdefault("character", {"type": "", "level": 1})
    if cmd == 1068 and c.get("type"):
        cost = int(GEM.get("costChange", 500))
        state.spend(st, coin=cost)
        ctx.log("ĐỔI NHÂN VẬT %s -> %s (-%d G)" % (c["type"], ch, cost))
    else:
        ctx.log("CHỌN NHÂN VẬT %s" % ch)
    c["type"], c["changed"] = ch, int(time.time())
    state.save(st, ctx.account)
    return False


@handler(1082)
def get_character(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    c = st.get("character") or {}
    d = pstr(c.get("type", "")) + u8(int(c.get("level", 1))) + u8(0) + f64(0) + bytes(64)
    ctx.reply(ctl, 1082, 0, d, "GỬI cmd=1082 nhân vật: %s" % (c.get("type") or "chưa chọn"))
    return True


@handler(1087)
def get_crystal(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    g = _gems(st)
    ctx.reply(ctl, 1087, 0, crystal_info(st) + bytes(32),
              "GỬI cmd=1087 ngọc: %d đang khảm, %d loại trong túi, %d ô mở" % (len(g["slots"]), len(g["bag"]), len(g["open"])))
    return True


@handler(1088)
def equip(ctx, ctl, cmd, payload):
    r = Reader(payload)
    slot, gid, lvl = r.u8(), r.u16(), r.u8()
    st = state.load(ctx.account)
    g = _gems(st)
    old = g["slots"].get(str(slot))
    if old:
        _bag_add(g, old[0], old[1], 1)
    _bag_add(g, gid, lvl, -1)
    g["slots"][str(slot)] = [gid, lvl]
    if slot not in g["open"]:
        g["open"].append(slot)
    state.save(st, ctx.account)
    ctx.log("KHẢM NGỌC %d cấp %d vào ô %d%s" % (gid, lvl, slot, (" (tháo ngọc %d cấp %d)" % tuple(old)) if old else ""))
    return False


@handler(1089)
def unequip(ctx, ctl, cmd, payload):
    slot = payload[0] if payload else 0
    st = state.load(ctx.account)
    g = _gems(st)
    old = g["slots"].pop(str(slot), None)
    if old:
        _bag_add(g, old[0], old[1], 1)
    state.save(st, ctx.account)
    ctx.log("THÁO NGỌC ô %d: %s" % (slot, old))
    return False


@handler(1091)
def slots(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    g = _gems(st)
    if len(payload) == 1:
        if payload[0] not in g["open"]:
            g["open"].append(payload[0])
        ctx.log("MỞ Ô NGỌC %d" % payload[0])
    else:
        r = Reader(payload)
        g["order"] = [r.u8() for _ in range(r.u32())]
        ctx.log("LƯU THỨ TỰ Ô NGỌC %s" % g["order"])
    state.save(st, ctx.account)
    return False


@handler(1093)
def open_crystal(ctx, ctl, cmd, payload):
    r = Reader(payload)
    lvl, set_id, n = r.u8(), r.u8(), r.u32()
    st = state.load(ctx.account)
    g = _gems(st)
    it = next((i for i in st.get("items", []) if int(i["type"]) == 77 and int(i["sub"]) == lvl
               and int(i.get("set", 0)) in (set_id, 0) and int(i["count"]) > 0), None)
    if it is not None:
        it["count"] = max(0, int(it["count"]) - n)
    pool = GEM["collection"].get(str(set_id)) or GEM["collection"]["1"]
    weights = [max(0, int((p["rates"] + [0] * 8)[max(0, min(7, lvl - 1))])) for p in pool]
    got = {}
    for _ in range(max(0, min(n, 999))):
        gid = random.choices([p["gemId"] for p in pool], weights=weights or None)[0]
        got[gid] = got.get(gid, 0) + 1
    for gid, k in got.items():
        _bag_add(g, gid, lvl, k)
    state.save(st, ctx.account)
    d = u32(len(got)) + b"".join(_i16(gid) + u8(lvl) + u32(k) for gid, k in sorted(got.items()))
    ctx.reply(ctl, 1093, 0, d + bytes(32), "GỬI cmd=1093 MỞ %d đá pha lê cấp %d bộ %d -> %s" % (n, lvl, set_id, got))
    return True


@handler(1094)
def buy_crystal(ctx, ctl, cmd, payload):
    r = Reader(payload)
    sid, n = r.u8(), r.u32()
    item = GEM["shop"].get(str(sid))
    if not item:
        ctx.log("mua đá pha lê: không có mục %d" % sid)
        return False
    st = state.load(ctx.account)
    cost = int(item["cost"]) * n
    state.spend(st, coin=cost)
    it = add_item(st, int(item["type"]), int(item["level"]), int(item.get("number", 1)) * n)
    it["set"] = int(item.get("setId", 0))
    state.save(st, ctx.account)
    ctx.log("MUA ĐÁ PHA LÊ mục %d x%d (cấp %d, bộ %d): -%d G" % (sid, n, item["level"], it["set"], cost))
    ctx.reply(ctl, 1094, 0, bytes(64), "GỬI cmd=1094 mua đá pha lê xong")
    ctx.reply(ctl, 10008, 0, build_items(st), "GỬI cmd=10008 cập nhật kho đồ")
    return True


@handler(1095)
def merge(ctx, ctl, cmd, payload):
    r = Reader(payload)
    st = state.load(ctx.account)
    g = _gems(st)
    parts = []
    for _ in range(min(r.u32(), 50)):
        gid, lvl, n = r.u16(), r.u8(), r.u32()
        parts.append((gid, lvl, n))
        _bag_add(g, gid, lvl, -n)
    if not parts:
        return False
    gid, lvl = parts[0][0], parts[0][1] + 1
    _bag_add(g, gid, lvl, 1)
    state.save(st, ctx.account)
    ctx.reply(ctl, 1095, 0, _i16(gid) + u8(lvl) + bytes(32), "GỬI cmd=1095 GHÉP NGỌC %s -> %d cấp %d" % (parts, gid, lvl))
    return True


@handler(1097)
def crystal_tut(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    _gems(st)["tut"] = 1
    state.save(st, ctx.account)
    return False


@handler(1100)
def other_crystal(ctx, ctl, cmd, payload):
    uid = int.from_bytes(payload[:4], "big") if len(payload) >= 4 else 0
    from .. import clans
    acc = clans.account_of_uid(uid) or ctx.account
    try:
        st = state.load(acc)
    except Exception:
        st = state.load(ctx.account)
    g = _gems(st)
    sl = sorted((int(s), v) for s, v in g["slots"].items())
    d = u8(g["level"]) + u32(len(sl)) + b"".join(u8(s) + _i16(v[0]) + u8(v[1]) + u32(1) for s, v in sl)
    ctx.reply(ctl, 1100, 0, d + bytes(32), "GỬI cmd=1100 ngọc đang khảm của uid %d" % uid)
    return True
