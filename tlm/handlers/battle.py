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
import time

from .. import botbase, clans, state
from ..packets import battle_info
from ..protocol.codec import Reader, u8
from . import handler

MAX_MAP = 50
REAL_CHANCE = 0.7          # tỉ lệ gặp làng NGƯỜI CHƠI THẬT (nếu có ai hợp lệ) thay vì làng máy
LOOT_RATE = (0.2, 0.2, 0.1)  # phần trăm vàng / dầu / dầu đen có thể cướp
SHIELD_AFTER = ((90, 16), (60, 14), (30, 12))   # % phá -> số giờ khiên cho người bị đánh


def _real_opponents(account, player_th):
    """Tài khoản khác: nhà chính lệch <= 2 cấp, không có khiên."""
    now = time.time()
    out = []
    for acc in state.list_accounts():
        if acc == account:
            continue
        try:
            st = state.load(acc)
        except Exception:
            continue
        th = next((b["level"] for b in st["buildings"] if b["type"] == "TOW_1"), 1)
        if abs(th - player_th) <= 2 and float(st["player"].get("shield_end", 0)) <= now:
            out.append((acc, st, th))
    return out


def real_base(st):
    """Làng người chơi thật -> danh sách công trình cho BattleInfo (đánh số lại id 1..n, chia chiến lợi phẩm)."""
    allowed = botbase.GEN["size"]
    out = [dict(id=0, type=b["type"], x=b["x"], y=b["y"], level=b["level"]) for b in st["buildings"]
           if b["type"] in allowed]
    gold, elixir, dark, _, _ = state.effective_resources(st)
    for key, total, kinds in (("gold", int(gold * LOOT_RATE[0]), ("TOW_1", "STO_1", "RES_1")),
                              ("elixir", int(elixir * LOOT_RATE[1]), ("TOW_1", "STO_2", "RES_2")),
                              ("dark", int(dark * LOOT_RATE[2]), ("TOW_1", "STO_3", "RES_3"))):
        holders = [b for b in out if b["type"] in kinds] or out[:1]
        for i, b in enumerate(holders):
            b[key] = b.get(key, 0) + total // len(holders) + (1 if i < total % len(holders) else 0)
    for i, b in enumerate(out, 1):
        b["id"] = i
    return out


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
        real = _real_opponents(ctx.account, player_th)
        if real and random.random() < REAL_CHANCE:
            acc, vst, th = random.choice(real)
            base = real_base(vst)
            name = str(vst["player"].get("name", acc))
            ctx.battle = {"kind": "real", "victim": acc, "dropped": {}}
            enemy_id = clans.uid_of(acc)
            what = "CHINH PHẠT NGƯỜI CHƠI THẬT (%s)" % acc
        else:
            base, name, th, seed = botbase.random_enemy(player_th)
            ctx.battle = {"kind": "pvp", "seed": seed, "dropped": {}}
            enemy_id = 900000 + seed % 100000
            what = "CHINH PHẠT"
        if float(st["player"].get("shield_end", 0)) > time.time():   # đi đánh -> mất khiên
            st["player"]["shield_end"] = 0
            state.save(st, ctx.account)
            ctx.log("    đi đánh nên MẤT KHIÊN")
    loot = [sum(b.get(k, 0) for b in base) for k in ("gold", "elixir", "dark")]
    ctx.log("%s: đối thủ '%s', nhà chính cấp %d, %d công trình, chiến lợi phẩm vàng %d / dầu %d / dầu đen %d"
            % (what, name, th, len(base), loot[0], loot[1], loot[2]))
    troops = st.get("troops", {})
    ctx.log("    lính mang theo: %s" % (", ".join("%s x%s" % kv for kv in sorted(troops.items())) or "KHÔNG CÓ (luyện quân trước)"))
    ctx.reply(ctl, 9001, 0, battle_info.build(base, enemy_id, name, th, troops, st.get("troop_levels"),
                                                st.get("clan_troops")), "GỬI cmd=9001 BattleInfo (%s)" % what)
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
        if st.get("clan_troops"):
            st["clan_troops"] = {}                      # quân bang dùng 1 lần
            note += ", hết quân bang"
    if battle.get("kind") == "single" and stars > 0:
        lvl = battle["level"]
        rec = st.setdefault("single_stars", {})
        rec[str(lvl)] = max(int(rec.get(str(lvl), 0)), stars)
        p = st["player"]
        if int(p.get("single_map", 1)) <= lvl < MAX_MAP:
            p["single_map"] = lvl + 1
            note += ", mở màn %d" % (lvl + 1)
    if battle.get("kind") in ("real", "pvp"):
        from .ranking import change_trophy
        gain = (10 if battle["kind"] == "real" else 5) * stars if stars > 0 else -5
        note += ", cúp %+d (= %d)" % (gain, change_trophy(st, gain))
    state.save(st, ctx.account)
    if battle.get("kind") == "real":
        note += _hit_victim(ctx, battle["victim"], gold, elixir, dark, percent, stars)
    ctx.battle = None
    ctx.log("KẾT THÚC TRẬN: %d sao, phá %d%%, cướp vàng %d / dầu %d / dầu đen %d%s"
            % (stars, percent, gold, elixir, dark, note))
    ctx.reply(ctl, 9014, 0, u8(0) + u8(0) + bytes(256), "GỬI cmd=9014 kết quả trận (cho phép về nhà)")
    return True


def _hit_victim(ctx, victim, gold, elixir, dark, percent, stars):
    """Trừ tài nguyên người bị đánh (không quá phần cướp được), cho khiên theo % phá, ghi nhật ký phòng thủ."""
    vst = state.load(victim)
    p = vst["player"]
    g, e, d, _, _ = state.effective_resources(vst)
    lost = (min(max(gold, 0), int(g * LOOT_RATE[0]) + 1), min(max(elixir, 0), int(e * LOOT_RATE[1]) + 1),
            min(max(dark, 0), int(d * LOOT_RATE[2]) + 1))
    state.spend(vst, gold=lost[0], elixir=lost[1], dark=lost[2])
    hours = next((h for pct, h in SHIELD_AFTER if percent >= pct or stars >= 3 and pct == 90), 0)
    if hours:
        p["shield_end"] = int(time.time()) + hours * 3600
    if stars > 0:
        p["trophy"] = max(0, int(p.get("trophy", 0)) - 8 * stars)
    me = state.load(ctx.account)["player"].get("name", ctx.account)
    log = vst.setdefault("defense_log", [])
    log.append({"t": int(time.time()), "by": ctx.account, "name": me, "stars": stars, "percent": percent,
                "lost": list(lost)})
    del log[:-30]
    state.save(vst, victim)
    return ", %s mất vàng %d / dầu %d / dầu đen %d%s" % (victim, lost[0], lost[1], lost[2],
                                                          (", được khiên %d giờ" % hours) if hours else "")


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
