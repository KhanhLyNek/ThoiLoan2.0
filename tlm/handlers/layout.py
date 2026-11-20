"""Di chuyển / xoay / sắp xếp công trình - lưu vị trí mới vào state.

2002 MapObject::sendMoveObj (kéo thả 1 công trình): [chuỗi loại][int id][byte x][byte y]
2007 sendMoveListWall (kéo thả tường): [short n] + n x [int id][byte x][byte y]
2008 sendUpgradeWall: [int][short n] + n x [int id][byte dùng G]
2024 sendEditMap(0) (lưu chế độ "Sắp xếp làng", SortBuildingGUI::doSaveMap):
     [int n] + n x [int id][chuỗi loại][byte x][byte y]   (mọi công trình trừ chướng ngại OBS/ROS)
2029 DefenseObject::changeDirection (nút xoay hướng phòng thủ): [int id][byte hướng 1..8]
Trong game KHÔNG có nút "di chuyển": chạm chọn công trình rồi giữ và kéo sang chỗ mới.
"""
from .. import state
from ..protocol.codec import Reader
from . import handler


def _move(st, bid, btype, x, y):
    b = state.find_building(st, bid, btype=btype)
    if b is None:
        o = next((o for o in st.get("obstacles", []) if o["id"] == bid and o["type"] == btype), None)
        if o is None:
            return None
        b = o
    old = (b["x"], b["y"])
    b["x"], b["y"] = x, y
    return old


@handler(2002)
def move_obj(ctx, ctl, cmd, payload):
    try:
        r = Reader(payload)
        btype = r.str(); bid = r.u32(); x = r.u8(); y = r.u8()
    except Exception as e:
        ctx.log("di chuyển: không đọc được (%s)" % e)
        return False
    st = state.load(ctx.account)
    old = _move(st, bid, btype, x, y)
    if old is None:
        ctx.log("di chuyển: không thấy %s id=%d" % (btype, bid))
        return False
    state.save(st, ctx.account)
    ctx.log("DI CHUYỂN %s id=%d: (%d,%d) -> (%d,%d)" % (btype, bid, old[0], old[1], x, y))
    return False                      # server tự trả lời error 0


@handler(2007)
def move_walls(ctx, ctl, cmd, payload):
    """Game không chờ phản hồi 2007 (onReceived không có nhánh) -> chỉ lưu, không trả lời."""
    try:
        r = Reader(payload)
        n = r.u16()
        walls = [(r.u32(), r.u8(), r.u8()) for _ in range(n)]
    except Exception as e:
        ctx.log("di chuyển tường: không đọc được (%s)" % e)
        return True
    st = state.load(ctx.account)
    moved = sum(1 for wid, x, y in walls if _move(st, wid, "WAL_1", x, y) is not None)
    state.save(st, ctx.account)
    ctx.log("DI CHUYỂN %d đoạn tường (lưu %d)" % (len(walls), moved))
    return True


@handler(2008)
def upgrade_walls(ctx, ctl, cmd, payload):
    """sendUpgradeWall: [int][short n] + n x [int id tường][byte dùng G]. Game không chờ phản hồi.
    Mỗi đoạn lên 1 cấp, trừ giá cost.json (dùng G -> quy đổi tài nguyên sang G)."""
    from ..costs import resource_cost
    from .. import gamedata
    try:
        r = Reader(payload)
        r.u32()
        n = r.u16()
        ids = [r.u32() for _ in range(n)]
        use_g = r.u8() if r.remaining() >= 1 else 0
    except Exception as e:
        ctx.log("nâng tường: không đọc được (%s)" % e)
        return True
    st = state.load(ctx.account)
    done = 0
    total = [0, 0, 0, 0]
    for wid in ids:
        w = state.find_building(st, wid, btype="WAL_1")
        if w is None or str(w["level"] + 1) not in gamedata.COST.get(w["type"], {}):
            continue
        c = gamedata.cost_of(w["type"], w["level"] + 1)
        if use_g:
            state.spend(st, coin=resource_cost(c[0], c[1], c[2]) + c[3])
        else:
            state.spend(st, gold=c[0], elixir=c[1], dark=c[2], coin=c[3])
        w["level"] += 1
        total = [a + b for a, b in zip(total, c)]
        done += 1
    state.save(st, ctx.account)
    ctx.log("NÂNG CẤP %d/%d đoạn tường, giá %s%s" % (done, len(ids), total, " (trả bằng G)" if use_g else ""))
    return True


@handler(2024)
def edit_map(ctx, ctl, cmd, payload):
    try:
        r = Reader(payload)
        n = r.u32()
        items = [(r.u32(), r.str(), r.u8(), r.u8()) for _ in range(n)]
    except Exception as e:
        ctx.log("sắp xếp làng: không đọc được (%s)" % e)
        return False
    st = state.load(ctx.account)
    moved = 0
    for bid, btype, x, y in items:
        old = _move(st, bid, btype, x, y)
        if old is not None and old != (x, y):
            moved += 1
    state.save(st, ctx.account)
    ctx.log("SẮP XẾP LÀNG: %d công trình, %d cái đổi chỗ" % (len(items), moved))
    return False


@handler(2029)
def change_direction(ctx, ctl, cmd, payload):
    try:
        r = Reader(payload)
        bid = r.u32(); d = r.u8()
    except Exception as e:
        ctx.log("xoay hướng: không đọc được (%s)" % e)
        return True
    st = state.load(ctx.account)
    b = state.find_building(st, bid, category="DEF")
    if b is not None:
        b["direction"] = d
        state.save(st, ctx.account)
    ctx.log("XOAY HƯỚNG phòng thủ id=%d -> hướng %d" % (bid, d))
    return True
