"""NHÀ PHÉP (SPF_1) + chế phép, bỏ lính / bỏ phép khỏi quân đội.

Game tự đếm giờ chế phép (SpellFactoryObject::loopTrain), server chỉ cần lưu đúng:
  11008 sendCreateSpell   [chuỗi phép][byte số]   -> thêm vào hàng đợi, trừ dầu/dầu đen (SpellLevel.json theo cấp phép)
  11009 sendCancelSpell   [chuỗi phép][byte 1]    -> bớt khỏi hàng đợi, hoàn tiền
  11010 sendFinishSpell   [chuỗi phép]            -> 1 phép xong: hàng đợi -> phép đã có
  11011 sendQuickCreateSpell                      -> xong cả hàng đợi bằng G
  11016 sendRemoveSpell   [byte n] n x [byte số][chuỗi phép]   (ArmyManagerGUI: bỏ phép)
  11015 sendRemoveTroop   [byte n] n x [short số][chuỗi lính]  (ArmyManagerGUI: bỏ lính khỏi trại quân)
Lưu: st["spells"] = {phép: số}, st["spell_queue"] = [[phép, số]], st["spell_start"] = giờ bắt đầu phép đầu hàng.
Gửi cho game trong BuildingInfo (packets/building_info.py): nhà phép [short cờ] + đối tượng chung + [short n] n x
[chuỗi phép][short số] (hàng đợi) + double + short + int; sau đó phép đã có [short n] n x [chuỗi phép][byte số].
Vào trận: BattleInfo danh sách phép @0x38 [byte n] n x [chuỗi][byte cấp][byte số] (packets/battle_info.py).
"""
import time

from .. import state
from ..costs import time_cost
from ..data import load_table
from ..protocol.codec import Reader
from . import handler

SPELLS = load_table("spells.json")


def factory(st):
    return next((b for b in st["buildings"] if b["type"] == "SPF_1"), None)


def capacity(st):
    f = factory(st)
    return int(SPELLS["factory"].get(str(f["level"]), {}).get("capacity", 0)) if f else 0


def housing(spell):
    return int(SPELLS["spell"].get(spell, {}).get("housing", 1))


def used(st):
    return sum(housing(s) * int(n) for s, n in st.get("spells", {}).items())


def _cost(st, spell, n):
    lv = str(st.get("troop_levels", {}).get(spell, 1))
    e, d = SPELLS["spell"].get(spell, {}).get("cost", {}).get(lv, [0, 0])
    return int(e) * n, int(d) * n


def settle_spells(st):
    """Lúc vào game: phép nào đã hết giờ chế (tính nối tiếp từ spell_start) -> vào kho phép."""
    q = st.get("spell_queue") or []
    t = float(st.get("spell_start") or 0)
    now, done = time.time(), 0
    while q and t:
        sp = q[0][0]
        t += int(SPELLS["spell"].get(sp, {}).get("time", 0))
        if t > now:
            break
        _to_store(st, sp, 1)
        q[0][1] = int(q[0][1]) - 1
        if q[0][1] <= 0:
            q.pop(0)
        st["spell_start"] = t
        done += 1
    if not q:
        st["spell_start"] = 0
    return done


def _to_store(st, spell, n):
    s = st.setdefault("spells", {})
    s[spell] = int(s.get(spell, 0)) + int(n)


@handler(11008)
def create(ctx, ctl, cmd, payload):
    r = Reader(payload)
    spell, n = r.str(), r.u8()
    st = state.load(ctx.account)
    q = st.setdefault("spell_queue", [])
    if not q:
        st["spell_start"] = time.time()
    if q and q[-1][0] == spell:
        q[-1][1] = int(q[-1][1]) + n
    else:
        q.append([spell, n])
    e, d = _cost(st, spell, n)
    state.spend(st, elixir=e, dark=d)
    state.save(st, ctx.account)
    ctx.log("CHẾ PHÉP %s x%d: -%d dầu -%d dầu đen (hàng đợi: %s)" % (spell, n, e, d, q))
    return False


@handler(11009)
def cancel(ctx, ctl, cmd, payload):
    r = Reader(payload)
    spell, n = r.str(), r.u8() or 1
    st = state.load(ctx.account)
    q = st.setdefault("spell_queue", [])
    for item in reversed(q):
        if item[0] == spell:
            k = min(n, int(item[1]))
            item[1] = int(item[1]) - k
            e, d = _cost(st, spell, k)
            state.add_resource(st, "elixir", e)
            state.add_resource(st, "dark_elixir", d)
            break
    q[:] = [i for i in q if int(i[1]) > 0]
    if not q:
        st["spell_start"] = 0
    state.save(st, ctx.account)
    ctx.log("HUỶ CHẾ PHÉP %s x%d (hàng đợi: %s)" % (spell, n, q))
    return False


@handler(11010)
def finish(ctx, ctl, cmd, payload):
    spell = Reader(payload).str()
    st = state.load(ctx.account)
    q = st.setdefault("spell_queue", [])
    item = next((i for i in q if i[0] == spell), None)
    if item:
        item[1] = int(item[1]) - 1
        q[:] = [i for i in q if int(i[1]) > 0]
    _to_store(st, spell, 1)
    st["spell_start"] = time.time() if q else 0
    state.save(st, ctx.account)
    ctx.log("PHÉP XONG %s (kho phép: %s)" % (spell, st["spells"]))
    return False


@handler(11011)
def quick(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    q = st.get("spell_queue") or []
    left = sum(int(SPELLS["spell"].get(s, {}).get("time", 0)) * int(n) for s, n in q)
    if q and st.get("spell_start"):
        left = max(0, left - int(time.time() - float(st["spell_start"])))
    g = time_cost(left) if left else 0
    state.spend(st, coin=g)
    for s, n in q:
        _to_store(st, s, n)
    st["spell_queue"], st["spell_start"] = [], 0
    state.save(st, ctx.account)
    ctx.log("CHẾ PHÉP XONG NGAY: -%d G (kho phép: %s)" % (g, st.get("spells")))
    return False


@handler(11016)
def remove_spell(ctx, ctl, cmd, payload):
    r = Reader(payload)
    st = state.load(ctx.account)
    s = st.setdefault("spells", {})
    out = []
    for _ in range(r.u8()):
        n, sp = r.u8(), r.str()
        s[sp] = max(0, int(s.get(sp, 0)) - n)
        out.append("%s x%d" % (sp, n))
    st["spells"] = {k: v for k, v in s.items() if v > 0}
    state.save(st, ctx.account)
    ctx.log("BỎ PHÉP %s (còn: %s)" % (", ".join(out), st["spells"]))
    return False


@handler(11015)
def remove_troop(ctx, ctl, cmd, payload):
    r = Reader(payload)
    st = state.load(ctx.account)
    t = st.setdefault("troops", {})
    out = []
    for _ in range(r.u8()):
        n, tr = r.u16(), r.str()
        t[tr] = max(0, int(t.get(tr, 0)) - n)
        out.append("%s x%d" % (tr, n))
    st["troops"] = {k: v for k, v in t.items() if v > 0}
    state.save(st, ctx.account)
    ctx.log("BỎ LÍNH %s (còn: %s)" % (", ".join(out), st["troops"]))
    return False
