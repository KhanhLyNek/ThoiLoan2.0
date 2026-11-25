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
     = TOÀN BỘ lính đã thả từ đầu trận (không phải phần mới) -> lấy ảnh chụp mới nhất.
     = các lính thả SAU lính đầu tiên (hàng đợi queueAddTroop), gửi theo lô. Không trả lời.
9014 (server -> game, lớp ErrorCode) = KẾT QUẢ TRẬN, gửi sau 9003. BattleMgr::onGetBattleResult đọc
     [bool][byte số vật phẩm][...]; onGetBattleUpdate đặt cờ "đã có kết quả" (BattleMgr+0x18d) và gọi
     CityMgr::returnMyHome. Thiếu gói này -> màn mây/chim bay đứng mãi, không về được nhà.
11018: đội quân mang vào trận [short số loại] + [chuỗi][short] -> ghi đè state["troops"] (game là nguồn đúng).
9003 phần đuôi (sau chuỗi kiểm tra): [int tổng số lần thả][int n] n x [chuỗi lính][int ô][int nhịp] = hàng đợi thả lính.
GHI TRẬN (xem lại / nhật ký): mọi lần thả (9002 + 9012 + đuôi 9003) gom theo (lính, ô, nhịp) -> replays.py.
"""
import random
import time

from .. import botbase, clans, replays, state
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


def single_choices(st):
    """Phó bản không dùng quân nhà: bảng chọn = mọi loại lính đã mở theo cấp trại lính (Barrack.json unlockedUnit).
    SỐ LƯỢNG = SỐ ĐANG CHỌN SẴN (SingleBattleSelectGUI::addTroop cộng thẳng vào trường này, loại nào > 0 hiện ở hàng
    trên) -> gửi 0 để hàng trên trống, người chơi tự chọn trong giới hạn sức chứa trại quân ở nhà (@0x14c).
    Lính chọn ở phó bản không lấy từ trại và không mang về nhà."""
    unlock = botbase.GEN.get("barrack_unlock", {})
    out = {}
    for kind in ("BAR_1", "BAR_2"):
        top = max([b["level"] for b in st["buildings"] if b["type"] == kind] or [0])
        for lvl in range(1, top + 1):
            t = unlock.get(kind, {}).get(str(lvl))
            if t:
                out[t] = 0
    return out or {"ARM_1": 0}


@handler(9001)
def find_battle(ctx, ctl, cmd, payload):
    map_id = int.from_bytes(payload[0:4], "big") if len(payload) >= 4 else 0
    island = int.from_bytes(payload[8:12], "big") if len(payload) >= 12 else 0
    if map_id == 0 and 0 < island < 100000:
        # Cổng thế giới, đảo TRỐNG: AttackIslandGui::sendAttackIsland -> sendFindMatch(0, id đảo) = 9001 [0][1|2][id đảo]
        from .worldmap import start_island
        return start_island(ctx, ctl, island, 9001)
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
    return start_battle(ctx, ctl, 9001, st, base, name, th, enemy_id, what)


# Nhà anh hùng -> lính anh hùng (CityMgr::createKingQueenOnCity; BattleObject::isKingQueen). Anh hùng vào trận như
# 1 lính trong danh sách quân của BattleInfo, CẤP = cấp nhà anh hùng. KQB_3 (bệ thần ARM_13/14/15) chưa làm.
HERO_OF = {"KQB_1": "ARM_11", "KQB_2": "ARM_12", "KQB_4": "ARM_18", "KQB_5": "ARM_19"}


def hero_troops(st):
    return {HERO_OF[b["type"]]: max(1, int(b.get("level", 1))) for b in st.get("buildings", []) if b["type"] in HERO_OF}


def start_battle(ctx, ctl, reply_cmd, st, base, name, th, enemy_id, what):
    """Gửi BattleInfo (9001 tìm trận / 9013 trả thù) và chuẩn bị ghi trận."""
    loot = [sum(b.get(k, 0) for b in base) for k in ("gold", "elixir", "dark")]
    ctx.log("%s: đối thủ '%s', nhà chính cấp %d, %d công trình, chiến lợi phẩm vàng %d / dầu %d / dầu đen %d"
            % (what, name, th, len(base), loot[0], loot[1], loot[2]))
    from .army import camp_capacity
    if ctx.battle["kind"] == "single":
        troops, cap = single_choices(st), camp_capacity(st)
        ctx.log("    phó bản: bảng chọn %s (hàng trên trống, tự chọn), sức chứa %d chỗ" % (", ".join(sorted(troops)), cap))
        clan = None
    else:
        troops, cap, clan = dict(st.get("troops", {})), 0, st.get("clan_troops")
        ctx.log("    lính mang theo: %s" % (", ".join("%s x%s" % kv for kv in sorted(troops.items())) or "KHÔNG CÓ (luyện quân trước)"))
        heroes = hero_troops(st)
        if heroes:
            ctx.log("    anh hùng: %s" % ", ".join("%s cấp %d" % (t, l) for t, l in sorted(heroes.items())))
        troops.update({t: 1 for t in heroes})
        ctx.battle["rec"] = {"base": [dict(b) for b in base], "def_name": name, "th": th, "enemy_id": enemy_id,
                             "levels": dict(st.get("troop_levels") or {}, **hero_troops(st)), "clan": dict(clan or {}),
                             "t": int(time.time())}
        ctx.battle["actions"] = {}
    levels = dict(st.get("troop_levels") or {})
    if ctx.battle["kind"] != "single":
        levels.update(hero_troops(st))
    spells = st.get("spells") if ctx.battle["kind"] != "single" else None
    if spells:
        ctx.log("    phép: %s" % ", ".join("%s x%s" % kv for kv in sorted(spells.items())))
    ctx.reply(ctl, reply_cmd, 0, battle_info.build(base, enemy_id, name, th, troops, levels, clan,
                                                     single_capacity=cap, keep_zero=ctx.battle["kind"] == "single",
                                                     spells=spells), "GỬI cmd=%d BattleInfo (%s)" % (reply_cmd, what))
    return True


def _act(ctx, troop, cell, tick):
    """Ghi 1 lần thả lính (trùng lính+ô+nhịp = cùng một lần, vì 9012/9003 gửi lại cả danh sách)."""
    battle = getattr(ctx, "battle", None)
    if battle is not None and "actions" in battle:
        battle["actions"]["%s|%d|%d" % (troop, cell, tick)] = (troop, int(cell), int(tick))


def _drop_tail(payload):
    """Đuôi 9003: [7 int][chuỗi][int tổng][int n] n x [chuỗi][int ô][int nhịp]."""
    r = Reader(payload)
    for _ in range(7):
        r.u32()
    r.str()
    r.u32()
    n = r.u32()
    return [(r.str(), r.u32(), r.u32()) for _ in range(min(n, 5000))]


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
    full = False
    try:
        for troop, cell, tick in _drop_tail(payload):
            _act(ctx, troop, cell, tick)
        full = True
    except Exception:
        pass                                            # gói ngắn (thoát giữa trận) / bản game khác
    acts = list((battle.get("actions") or {}).values())
    by_acts = {}
    for t, _, _ in acts:
        if t not in ("Clan", "SupportTroop"):
            by_acts[t] = by_acts.get(t, 0) + 1
    dropped = dict(battle.get("dropped") or {})
    if full and "actions" in battle:
        dropped = by_acts                                 # 9002 + đuôi 9003 = danh sách thả đầy đủ, chính xác nhất
    else:
        for t, n in by_acts.items():
            dropped[t] = max(n, dropped.get(t, 0))
    used_now = dict(dropped)
    if battle.get("kind") == "single":
        if dropped:
            note += ", phó bản dùng %s (không trừ quân nhà)" % ", ".join("%s x%d" % kv for kv in sorted(dropped.items()))
        dropped = {}
    if dropped:
        troops = st.setdefault("troops", {})
        for t, n in dropped.items():
            if t.startswith("SPE_"):                       # phép thả trong trận -> trừ kho phép
                sp = st.setdefault("spells", {})
                sp[t] = int(sp.get(t, 0)) - n
                if sp[t] <= 0:
                    sp.pop(t, None)
                continue
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
    from .profile import add_progress
    from .daily import on_battle as _daily_battle
    if battle.get("kind") != "single":
        _daily_battle(st, stars, gold, elixir, dark)
        from .goblin_treasure import on_battle as _gt_battle
        _gt_battle(st, gold, elixir, dark)
    add_progress(st, 2, stars)
    add_progress(st, 6, gold)
    add_progress(st, 7, elixir)
    if stars > 0:
        add_progress(st, 13, 1)
    gain = 0
    if battle.get("kind") in ("real", "pvp"):
        from .ranking import change_trophy
        gain = (10 if battle["kind"] == "real" else 5) * stars if stars > 0 else -5
        note += ", cúp %+d (= %d)" % (gain, change_trophy(st, gain))
    state.save(st, ctx.account)
    if battle.get("kind") == "island":
        from .worldmap import on_battle_end
        note += on_battle_end(ctx, battle, stars)
    if battle.get("kind") == "real":
        note += _hit_victim(ctx, battle["victim"], gold, elixir, dark, percent, stars)
    if battle.get("rec") is not None:
        try:
            rid = _record(ctx, battle, acts, used_now, ints[0], stars, percent, (gold, elixir, dark),
                          gain if battle.get("kind") in ("real", "pvp") else 0)
            note += ", ghi trận #%d (%d lần thả)" % (rid, len(acts))
        except Exception as e:
            ctx.log("!! ghi trận lỗi: %s" % e)
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
    else:
        from .profile import add_progress
        add_progress(vst, 14, 1)                 # phòng thủ thành công
    state.save(vst, victim)
    battle = getattr(ctx, "battle", None) or {}
    battle["lost"], battle["victim_tchange"] = list(lost), (-8 * stars if stars > 0 else 0)
    return ", %s mất vàng %d / dầu %d / dầu đen %d%s" % (victim, lost[0], lost[1], lost[2],
                                                          (", được khiên %d giờ" % hours) if hours else "")


def _clan_info(account):
    c = clans.clan_of(account) if account else None
    return (c["name"], int(c.get("icon", 1))) if c else ("", 0)


def _record(ctx, battle, acts, used, end_tick, stars, percent, loot, gain):
    """Lưu bản ghi xem lại + nhật ký tấn công (người đánh) / phòng thủ (người bị đánh). Trả về id trận."""
    rec, now = battle["rec"], int(time.time())
    levels = rec.get("levels") or {}
    me = state.load(ctx.account)
    victim = battle.get("victim")
    clan_used = rec.get("clan") if any(a[0] == "Clan" for a in acts) else {}
    clan_used = {t: [int(levels.get(t, 1)), int(n)] for t, n in (clan_used or {}).items() if int(n) > 0}
    troops_used = {t: [int(levels.get(t, 1)), int(n)] for t, n in used.items() if int(n) > 0}
    last = max([a[2] for a in acts] or [0])
    rid = replays.new_id()
    replays.save({
        "id": rid, "t": now, "attacker": ctx.account, "att_name": me["player"].get("name", ""),
        "defender": victim, "def_name": rec.get("def_name", ""), "th": rec.get("th", 1), "base": rec["base"],
        "actions": [[t, c, int(levels.get(t, 1)), k] for t, c, k in acts],
        "clan": {t: [int(levels.get(t, 1)), int(n)] for t, n in (rec.get("clan") or {}).items() if int(n) > 0},
        "used": troops_used, "end_tick": max(int(end_tick or 0), last + 90), "stars": stars, "percent": percent,
        "loot": list(loot)})
    vst = state.load(victim) if victim else None
    vname, vicon = _clan_info(victim)
    replays.add_log(me, "attack_log", {
        "id": rid, "t": now, "uid": int(rec.get("enemy_id", 0)), "acc": victim, "name": rec.get("def_name", ""),
        "clan_name": vname, "clan_icon": vicon,
        "trophy": int(vst["player"].get("trophy", 0)) if vst else 0, "tchange": gain, "stars": stars,
        "percent": percent, "loot": list(loot), "troops": troops_used, "clan_troops": clan_used, "replay": True})
    state.save(me, ctx.account)
    if vst is not None:
        mname, micon = _clan_info(ctx.account)
        replays.add_log(vst, "defense_log", {
            "id": rid, "t": now, "uid": clans.uid_of(ctx.account), "acc": ctx.account,
            "name": me["player"].get("name", ""), "clan_name": mname, "clan_icon": micon,
            "trophy": int(me["player"].get("trophy", 0)), "tchange": battle.get("victim_tchange", 0),
            "stars": stars, "percent": percent, "loot": battle.get("lost", list(loot)), "troops": troops_used,
            "clan_troops": clan_used, "replay": True, "revenged": False})
        state.save(vst, victim)
    return rid


def _count_drop(ctx, troop):
    """9002: lính thả lẻ (đếm cộng dồn)."""
    battle = getattr(ctx, "battle", None)
    if battle is not None:
        d = battle.setdefault("single_drops", {})
        d[troop] = d.get(troop, 0) + 1
        _merge_drops(battle)


def _merge_drops(battle):
    """Số lính đã dùng = max(đếm 9002, ảnh chụp 9012 mới nhất) cho từng loại.
    9012 gửi lại TOÀN BỘ danh sách đã thả mỗi 5 giây (cộng dồn), bản cũ cộng hết các lần -> trừ lính gấp 3-6 lần."""
    a, b = battle.get("single_drops", {}), battle.get("batch_drops", {})
    battle["dropped"] = {t: max(a.get(t, 0), b.get(t, 0)) for t in set(a) | set(b)}


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
    _act(ctx, troop, cell, tick)
    ctx.log("THẢ LÍNH %s (ô %d, t=%d, #%d)" % (troop, cell, tick, seq))
    return True                       # không trả lời, xem ghi chú đầu file


@handler(9012)
def battle_ack(ctx, ctl, cmd, payload):
    try:
        r = Reader(payload)
        r.u32()
        n = r.u32()
        cnt = {}
        for _ in range(n):
            t, cell, tick = r.str(), r.u32(), r.u32()
            cnt[t] = cnt.get(t, 0) + 1
            _act(ctx, t, cell, tick)
        battle = getattr(ctx, "battle", None)
        if battle is not None and cnt:
            prev = battle.get("batch_drops", {})
            battle["batch_drops"] = {t: max(cnt.get(t, 0), prev.get(t, 0)) for t in set(cnt) | set(prev)}
            _merge_drops(battle)
        if cnt:
            ctx.log("THẢ LÍNH (ảnh chụp, cộng dồn): " + ", ".join("%s x%d" % kv for kv in sorted(cnt.items())))
    except Exception as e:
        ctx.log("9012: không đọc được (%s)" % e)
    return True


@handler(11018)
def army_to_battle(ctx, ctl, cmd, payload):
    try:
        r = Reader(payload)
        n = r.u16()
        army = [(r.str(), r.u16()) for _ in range(n)]
        # quân game thật sự có trong trại -> đồng bộ (game là nguồn đúng; server có thể lệch vì hàng đợi luyện)
        st = state.load(ctx.account)
        st["troops"] = {t: c for t, c in army if c > 0}
        state.save(st, ctx.account)
        ctx.log("QUÂN VÀO TRẬN (đồng bộ trại quân theo game): %s" % ", ".join("%s x%d" % a for a in army))
    except Exception as e:
        ctx.log("quân vào trận: không đọc được (%s)" % e)
    return True                       # game không chờ phản hồi lệnh này


def abandon(ctx):
    """Game thoát giữa trận (tắt app, mất mạng): chốt trận như THUA 0 sao, trừ lính đã thả, không cộng gì.
    Tránh lính đã dùng vẫn còn trong trại / trận treo khi vào lại."""
    battle = getattr(ctx, "battle", None)
    if not battle:
        return
    ctx.log("MẤT KẾT NỐI GIỮA TRẬN -> chốt trận thua 0 sao")
    try:
        sent = []
        ctx.reply = lambda *a, **k: sent.append(a)        # socket đã đóng: không gửi gì
        ctx.push = lambda *a, **k: sent.append(a)
        end_battle(ctx, 0, 9003, bytes(28))
    except Exception as e:
        ctx.log("!! chốt trận lỗi: %s" % e)
    ctx.battle = None
