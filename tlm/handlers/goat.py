"""SỰ KIỆN DÊ (GoatEventMgr, GoatEvent.json) - dê đi dạo trong làng. THỬ NGHIỆM, định dạng suy từ mã game.

Chỉ chạy khi GameDataMgr::isGoatEvent: giờ hiện tại trong [goatEventStart, goatEventEnd] (EventConfig.json - server mở
qua json_url, xem tlm/events.py) và nhà chính >= vicStarRequireTownHallLevel (3). Khi đó CityMgr::onGetBuildingInfo gửi:
7029 sendGetGoatEventInfo [int] -> GoatEventMgr::onGetGoatEventInfo:
     [byte cấp chuồng @8][bool ĐÃ NHẬN DÊ MIỄN PHÍ @0xc (false -> mở FreeGoatGui)][int @0x10][int @0x14][byte @0x18]
     [byte n1] n1 x int  [byte n2] n2 x int
     [byte n3] n3 x [int id dê][byte cấp 1-3 (ảnh avatar GOA_<cấp>)][int giờ][chuỗi chủ] -> createGoat = DÊ ĐI DẠO
     [int @0x38]
     (gói này KHÔNG xoá dê cũ -> chỉ gửi 1 lần mỗi lần vào làng)
7030 nhận dê miễn phí (FreeGoatGui) -> onGetGoatFree: [byte n] n x [int id][byte cấp][int giờ][chuỗi chủ] -> thêm dê
7031 mua dê [int gói goatShop] (G)   7032 mua cỏ [int gói foodShop] (G -> vật phẩm 31)
7036 nâng cấp dê [int id][int]  (tốn cỏ = config.requireFood[cấp mới])     7038 nâng chuồng
7037 thu hoạch dê [int id] -> onGetHarvestGoat: [int id -> removeGoat][byte n] n x [short loại][byte cấp][short số]
     (quà goatBonus[cấp dê], game hiện bảng quà)
Lưu st["goat"] = {"stable", "free", "next", "goats": [[id, cấp, giờ]]}.
"""
import random
import time

from .. import state
from ..data import load_table
from ..protocol.codec import pstr, u8, u16, u32
from . import handler
from .inventory import add_item, build_items

GOAT = load_table("goat_event.json")
FOOD = 31


def _g(st):
    g = st.setdefault("goat", {})
    g.setdefault("stable", 1)
    g.setdefault("free", 0)
    g.setdefault("next", 1)
    g.setdefault("goats", [])
    return g


def _new(g, lvl):
    gid = int(g["next"])
    g["next"] = gid + 1
    rec = [gid, max(1, min(3, int(lvl))), int(time.time())]
    g["goats"].append(rec)
    return rec


def _goat_bytes(st, goats):
    owner = str(st["player"].get("name", ""))
    return b"".join(u32(i) + u8(l) + u32(t) + pstr(owner) for i, l, t in goats)


def info(st):
    g = _g(st)
    return (u8(g["stable"]) + u8(1 if g["free"] else 0) + u32(0) + u32(0) + u8(0) + u8(0) + u8(0)
            + u8(len(g["goats"])) + _goat_bytes(st, g["goats"]) + u32(0) + bytes(32))


@handler(7029)
def goat_info(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    g = _g(st)
    state.save(st, ctx.account)
    ctx.reply(ctl, 7029, 0, info(st), "GỬI cmd=7029 sự kiện dê: chuồng cấp %d, %d con dê%s"
              % (g["stable"], len(g["goats"]), "" if g["free"] else " (chưa nhận dê miễn phí -> mở bảng nhận)"))
    return True


def _push_goats(ctx, ctl, st, new, why):
    ctx.reply(ctl, 7030, 0, u8(len(new)) + _goat_bytes(st, new) + bytes(16),
              "GỬI cmd=7030 %s: %s" % (why, ", ".join("dê %d cấp %d" % (i, l) for i, l, _ in new)))


@handler(7030)
def goat_free(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    g = _g(st)
    if g["free"]:
        ctx.log("dê miễn phí: đã nhận rồi")
        return False
    g["free"] = 1
    new = []
    for it in GOAT["freeGift"]:
        if int(it["id"]) == 0:
            new += [_new(g, it["level"]) for _ in range(int(it.get("num", 1)))]
        else:
            add_item(st, int(it["id"]), int(it.get("level", 1)), int(it.get("num", 1)))
    state.save(st, ctx.account)
    _push_goats(ctx, ctl, st, new, "nhận dê miễn phí")
    ctx.reply(ctl, 10008, 0, build_items(st), "GỬI cmd=10008 cập nhật kho đồ (cỏ cho dê)")
    return True


@handler(7031)
def buy_goat(ctx, ctl, cmd, payload):
    pack = int.from_bytes(payload[:4], "big") if len(payload) >= 4 else 0
    shop = GOAT["goatShop"]
    item = shop[max(0, min(pack, len(shop) - 1))]
    st = state.load(ctx.account)
    g = _g(st)
    state.spend(st, coin=int(item["money"]))
    new = [_new(g, 1) for _ in range(int(item["num"]))]
    state.save(st, ctx.account)
    _push_goats(ctx, ctl, st, new, "mua %d dê (-%d G)" % (item["num"], item["money"]))
    return True


@handler(7032)
def buy_food(ctx, ctl, cmd, payload):
    pack = int.from_bytes(payload[:4], "big") if len(payload) >= 4 else 0
    shop = GOAT["foodShop"]
    item = shop[max(0, min(pack, len(shop) - 1))]
    st = state.load(ctx.account)
    state.spend(st, coin=int(item["money"]))
    add_item(st, int(item["id"]), int(item.get("level", 1)), int(item["num"]))
    state.save(st, ctx.account)
    ctx.log("MUA CỎ CHO DÊ x%d (-%d G)" % (item["num"], item["money"]))
    ctx.reply(ctl, 10008, 0, build_items(st), "GỬI cmd=10008 cập nhật kho đồ")
    return False


@handler(7036)
def upgrade_goat(ctx, ctl, cmd, payload):
    gid = int.from_bytes(payload[:4], "big") if len(payload) >= 4 else 0
    st = state.load(ctx.account)
    g = _g(st)
    rec = next((r for r in g["goats"] if r[0] == gid), None)
    if not rec or rec[1] >= 3:
        ctx.log("nâng cấp dê %d: không có / đã tối đa" % gid)
        return False
    need = int(GOAT["config"]["requireFood"][rec[1] + 1])
    food = next((i for i in st.get("items", []) if int(i["type"]) == FOOD), None)
    if food is not None:
        food["count"] = max(0, int(food["count"]) - need)
    rec[1] += 1
    state.save(st, ctx.account)
    ctx.log("NÂNG CẤP DÊ %d -> cấp %d (-%d cỏ)" % (gid, rec[1], need))
    ctx.reply(ctl, 10008, 0, build_items(st), "GỬI cmd=10008 cập nhật kho đồ")
    return False


@handler(7038)
def upgrade_stable(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    g = _g(st)
    g["stable"] = min(len(GOAT["goatCap"]) - 1, int(g["stable"]) + 1)
    state.save(st, ctx.account)
    ctx.log("NÂNG CHUỒNG DÊ -> cấp %d" % g["stable"])
    return False


def _roll(level):
    from .daily import DQ
    pool = GOAT["goatBonus"][max(1, min(level, len(GOAT["goatBonus"]) - 1))]
    out = []
    for it in pool:
        if random.randint(1, 100) > int(it.get("rate", 100)):
            continue
        tid, lvl, n = int(it["id"]), int(it.get("level", 1)), int(it.get("num", 1))
        if tid >= 1001:                                   # rương ChestGift
            chest = DQ["ChestGift"][min(tid - 1001, len(DQ["ChestGift"]) - 1)]["list"]
            c = random.choices(chest, weights=[int(x.get("rate", 1)) for x in chest])[0]
            tid, lvl, n = int(c["id"]), int(c.get("level", 1)), int(c.get("number", 1)) * n
        out.append((tid, lvl, n))
    return out


@handler(7037)
def harvest(ctx, ctl, cmd, payload):
    gid = int.from_bytes(payload[:4], "big") if len(payload) >= 4 else 0
    st = state.load(ctx.account)
    g = _g(st)
    rec = next((r for r in g["goats"] if r[0] == gid), None)
    if not rec:
        ctx.log("thu hoạch dê %d: không có" % gid)
        return False
    g["goats"].remove(rec)
    gifts = _roll(rec[1])
    for t, l, n in gifts:
        add_item(st, t, l, n)
    state.save(st, ctx.account)
    d = u32(gid) + u8(len(gifts)) + b"".join(u16(t) + u8(l) + u16(n) for t, l, n in gifts)
    ctx.reply(ctl, 7037, 0, d + bytes(16), "GỬI cmd=7037 thu hoạch dê %d cấp %d: %s"
              % (gid, rec[1], ", ".join("loại %d x%d" % (t, n) for t, _, n in gifts)))
    ctx.reply(ctl, 10008, 0, build_items(st), "GỬI cmd=10008 cập nhật kho đồ")
    return True
