"""Trận đánh: tìm/vào trận (cmd 9001) và kết thúc trận (cmd 9003).

9001 game gửi: [int mã màn][int][int]. Mã > 1000 = phó bản màn (mã - 1000); 0 = chinh phạt (tìm đối thủ).
     Server trả BattleInfo: làng đối thủ do botbase dựng (phó bản: cố định theo màn; chinh phạt: ngẫu nhiên).
9003 BattleMgr::sendCmdEndBattle: 7 int đầu =
     [thời gian @0x3c][SỐ SAO @0x44 (upStar)][VÀNG][DẦU][DẦU ĐEN] (BattleMgr::addMoney @0x5c/0x60/0x64)
     [tham số][PHẦN TRĂM PHÁ @0x50 (addPercentLife)], rồi chuỗi kiểm tra và vài int.
     Server cộng chiến lợi phẩm (giới hạn theo sức chứa) và mở màn phó bản kế tiếp khi thắng (>= 1 sao).
9002 BattleMgr::queueAddTroop: thả 1 lính = [chuỗi loại lính][int ô][int thời điểm][int số thứ tự].
     KHÔNG trả lời: lính đầu tiên game gửi thẳng (không vào hàng đợi), nên phản hồi 9002 làm
     BattleMgr::onGetAddTroopMsg xoá phần tử đầu của hàng đợi rỗng -> memmove âm -> sập.
     Server đếm lính đã thả rồi trừ khỏi trại khi trận kết thúc (9003).
9012 BattleMgr::sendCmdAck (5 giây/lần): [int thời điểm][int n] + n x [chuỗi lính][int ô][int thời điểm]
     = các lính thả SAU lính đầu tiên (hàng đợi queueAddTroop), gửi theo lô. Không trả lời.
9014 (server -> game, lớp ErrorCode) = KẾT QUẢ TRẬN, gửi sau 9003. BattleMgr::onGetBattleResult đọc
     [bool][byte số vật phẩm][...]; onGetBattleUpdate đặt cờ "đã có kết quả" (BattleMgr+0x18d) và gọi
     CityMgr::returnMyHome. Thiếu gói này -> màn mây/chim bay đứng mãi, không về được nhà.
11018: đội quân mang vào trận [short số loại] + [chuỗi][short] (chỉ ghi log).
"""
import random

from .. import botbase, state
from ..packets import battle_info
from ..protocol.codec import Reader, u8
from . import handler

MAX_MAP = 50


@handler(9001)
def find_battle(ctx, ctl, cmd, payload):
    map_id = int.from_bytes(payload[0:4], "big") if len(payload) >= 4 else 0
    st = state.load(ctx.account)
    if map_id > 1000:
        level = min(MAX_MAP, map_id - 1000)
        base, name, th = botbase.single_map(level)
        ctx.battle = {"kind": "single", "level": level, "dropped": {}}
        enemy_id = map_id
        what = "PHÓ BẢN màn %d" % level
    else:
        player_th = next((b["level"] for b in st["buildings"] if b["type"] == "TOW_1"), 1)
        base, name, th, seed = botbase.random_enemy(player_th)
        ctx.battle = {"kind": "pvp", "seed": seed, "dropped": {}}
        enemy_id = 900000 + seed % 100000
        what = "CHINH PHẠT"
    loot = [sum(b.get(k, 0) for b in base) for k in ("gold", "elixir", "dark")]
    ctx.log("%s: đối thủ '%s', nhà chính cấp %d, %d công trình, chiến lợi phẩm vàng %d / dầu %d / dầu đen %d"
            % (what, name, th, len(base), loot[0], loot[1], loot[2]))
    troops = st.get("troops", {})
    ctx.log("    lính mang theo: %s" % (", ".join("%s x%s" % kv for kv in sorted(troops.items())) or "KHÔNG CÓ (luyện quân trước)"))
    ctx.reply(ctl, 9001, 0, battle_info.build(base, enemy_id, name, th, troops, st.get("troop_levels")), "GỬI cmd=9001 BattleInfo (%s)" % what)
    return True


@handler(9003)
def end_battle(ctx, ctl, cmd, payload):
    ints = [int.from_bytes(payload[i:i + 4], "big", signed=True) for i in range(0, min(len(payload), 28), 4)]
    ints += [0] * (7 - len(ints))
    _, stars, gold, elixir, dark, _, percent = ints
    st = state.load(ctx.account)
    for key, amount in (("gold", gold), ("elixir", elixir), ("dark_elixir", dark)):
        if amount > 0:
            state.add_resource(st, key, amount)
    note = ""
    battle = getattr(ctx, "battle", None) or {}
    dropped = battle.get("dropped") or {}
    if dropped:
        troops = st.setdefault("troops", {})
        for t, n in dropped.items():
            left = int(troops.get(t, 0)) - n
            if left > 0:
                troops[t] = left
            else:
                troops.pop(t, None)
        note += ", đã dùng " + ", ".join("%s x%d" % kv for kv in sorted(dropped.items()))
    if battle.get("kind") == "single" and stars > 0:
        lvl = battle["level"]
        rec = st.setdefault("single_stars", {})
        rec[str(lvl)] = max(int(rec.get(str(lvl), 0)), stars)
        p = st["player"]
        if int(p.get("single_map", 1)) <= lvl < MAX_MAP:
            p["single_map"] = lvl + 1
            note += ", mở màn %d" % (lvl + 1)
    state.save(st, ctx.account)
    ctx.battle = None
    ctx.log("KẾT THÚC TRẬN: %d sao, phá %d%%, cướp vàng %d / dầu %d / dầu đen %d%s"
            % (stars, percent, gold, elixir, dark, note))
    ctx.reply(ctl, 9014, 0, u8(0) + u8(0) + bytes(256), "GỬI cmd=9014 kết quả trận (cho phép về nhà)")
    return True


def _count_drop(ctx, troop):
    battle = getattr(ctx, "battle", None)
    if battle is not None:
        d = battle.setdefault("dropped", {})
        d[troop] = d.get(troop, 0) + 1


@handler(9002)
def add_troop(ctx, ctl, cmd, payload):
    try:
        r = Reader(payload)
        troop = r.str()
        cell, tick, seq = r.u32(), r.u32(), r.u32()
    except Exception as e:
        ctx.log("thả lính: không đọc được (%s)" % e)
        return True
    _count_drop(ctx, troop)
    ctx.log("THẢ LÍNH %s (ô %d, t=%d, #%d)" % (troop, cell, tick, seq))
    return True                       # không trả lời, xem ghi chú đầu file


@handler(9012)
def battle_ack(ctx, ctl, cmd, payload):
    try:
        r = Reader(payload)
        r.u32()
        n = r.u32()
        drops = []
        for _ in range(n):
            t = r.str(); r.u32(); r.u32()
            drops.append(t)
            _count_drop(ctx, t)
        if drops:
            cnt = {}
            for t in drops:
                cnt[t] = cnt.get(t, 0) + 1
            ctx.log("THẢ LÍNH (lô): " + ", ".join("%s x%d" % kv for kv in sorted(cnt.items())))
    except Exception as e:
        ctx.log("9012: không đọc được (%s)" % e)
    return True


@handler(11018)
def army_to_battle(ctx, ctl, cmd, payload):
    try:
        r = Reader(payload)
        n = r.u16()
        army = ["%s x%d" % (r.str(), r.u16()) for _ in range(n)]
        ctx.log("QUÂN VÀO TRẬN: %s" % ", ".join(army))
    except Exception as e:
        ctx.log("quân vào trận: không đọc được (%s)" % e)
    return True                       # game không chờ phản hồi lệnh này
