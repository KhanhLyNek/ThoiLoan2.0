"""Trận đánh: tìm/vào trận (cmd 9001) và kết thúc trận (cmd 9003).

9001 game gửi: [int mã màn][int][int]. Mã > 1000 = phó bản màn (mã - 1000); 0 = chinh phạt (tìm đối thủ).
     Server trả BattleInfo: làng đối thủ do botbase dựng (phó bản: cố định theo màn; chinh phạt: ngẫu nhiên).
9003 BattleMgr::sendCmdEndBattle: 7 int đầu =
     [thời gian @0x3c][SỐ SAO @0x44 (upStar)][VÀNG][DẦU][DẦU ĐEN] (BattleMgr::addMoney @0x5c/0x60/0x64)
     [tham số][PHẦN TRĂM PHÁ @0x50 (addPercentLife)], rồi chuỗi kiểm tra và vài int.
     Server cộng chiến lợi phẩm (giới hạn theo sức chứa) và mở màn phó bản kế tiếp khi thắng (>= 1 sao).
11018: đội quân mang vào trận [short số loại] + [chuỗi][short] (chỉ ghi log).
"""
import random

from .. import botbase, state
from ..packets import battle_info
from ..protocol.codec import Reader
from . import handler

MAX_MAP = 50


@handler(9001)
def find_battle(ctx, ctl, cmd, payload):
    map_id = int.from_bytes(payload[0:4], "big") if len(payload) >= 4 else 0
    st = state.load(ctx.account)
    if map_id > 1000:
        level = min(MAX_MAP, map_id - 1000)
        base, name, th = botbase.single_map(level)
        ctx.battle = {"kind": "single", "level": level}
        enemy_id = map_id
        what = "PHÓ BẢN màn %d" % level
    else:
        player_th = next((b["level"] for b in st["buildings"] if b["type"] == "TOW_1"), 1)
        base, name, th, seed = botbase.random_enemy(player_th)
        ctx.battle = {"kind": "pvp", "seed": seed}
        enemy_id = 900000 + seed % 100000
        what = "CHINH PHẠT"
    loot = [sum(b.get(k, 0) for b in base) for k in ("gold", "elixir", "dark")]
    ctx.log("%s: đối thủ '%s', nhà chính cấp %d, %d công trình, chiến lợi phẩm vàng %d / dầu %d / dầu đen %d"
            % (what, name, th, len(base), loot[0], loot[1], loot[2]))
    troops = st.get("troops", {})
    ctx.log("    lính mang theo: %s" % (", ".join("%s x%s" % kv for kv in sorted(troops.items())) or "KHÔNG CÓ (luyện quân trước)"))
    ctx.reply(ctl, 9001, 0, battle_info.build(base, enemy_id, name, th, troops), "GỬI cmd=9001 BattleInfo (%s)" % what)
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
    if battle.get("kind") == "single" and stars > 0:
        lvl = battle["level"]
        rec = st.setdefault("single_stars", {})
        rec[str(lvl)] = max(int(rec.get(str(lvl), 0)), stars)
        p = st["player"]
        if int(p.get("single_map", 1)) <= lvl < MAX_MAP:
            p["single_map"] = lvl + 1
            note = ", mở màn %d" % (lvl + 1)
    state.save(st, ctx.account)
    ctx.battle = None
    ctx.log("KẾT THÚC TRẬN: %d sao, phá %d%%, cướp vàng %d / dầu %d / dầu đen %d%s"
            % (stars, percent, gold, elixir, dark, note))
    return False


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
