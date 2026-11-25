"""NHIỆM VỤ NGÀY (DailyQuest.json). Trước v8.1 server trả số 0 -> luôn là nhiệm vụ 0, không nhận được quà.

6003 sendGetDailyQuestInfo -> (ServerCommunication::onReceived -> GameDataMgr::setDailyQuest):
     [int chỉ số nhiệm vụ][int bậc] -> JsonMgr::getDataDailyQuest: DailyQuest[chỉ số].params, mục tiêu = level[bậc]
     [int TIẾN ĐỘ @0x18 (GameDataMgr+0x5b8, game tự cộng khi làm)][int @0x1c][int @0x20]
     [int SỐ NHIỆM VỤ ĐÃ XONG HÔM NAY @0x24 (> 14 = hết, DailyQuestGUI: còn lại = 15 - số này)][int @4]
6004 getRewardDailyQuest -> nhận quà DailyGift[số đã xong] (vật phẩm vào kho), sang nhiệm vụ kế (bậc = hardMode[số])
6006 sendQuickFinishDailyQuest -> xong ngay (DailyConfig.money[số] G)
6007 sendResetQuest -> đổi nhiệm vụ khác (DailyOther.moneyRenew G)
Lưu st["daily"] = {"day", "idx", "lvl", "progress", "number"}; qua ngày mới (giờ VN) làm lại từ đầu.
"""
import random
import time

from .. import state
from ..data import load_table
from ..protocol.codec import u32
from . import handler
from .inventory import add_item, build_items

DQ = load_table("daily_quest.json")
TOTAL = len(DQ["DailyConfig"]["hardMode"])


def _today():
    return time.strftime("%Y-%m-%d", time.gmtime(time.time() + 7 * 3600))


def _th(st):
    return next((b["level"] for b in st["buildings"] if b["type"] == "TOW_1"), 1)


def _new_quest(st, d, exclude=None):
    th = _th(st)
    pool = [i for i, q in enumerate(DQ["DailyQuest"]) if int(q.get("townhallLevel", 1)) <= th and i != exclude]
    d["idx"] = random.choice(pool or [0])
    hm = DQ["DailyConfig"]["hardMode"]
    d["lvl"] = int(hm[min(d["number"], len(hm) - 1)])
    d["progress"] = 0


def ensure(st):
    d = st.setdefault("daily", {})
    if d.get("day") != _today():
        d.update(day=_today(), number=0)
        _new_quest(st, d)
    return d


def target(d):
    lv = DQ["DailyQuest"][d["idx"]]["level"]
    return int(lv[min(d["lvl"], len(lv) - 1)])


def info(d):
    return (u32(d["idx"]) + u32(d["lvl"]) + u32(d.get("progress", 0)) + u32(0) + u32(0)
            + u32(d["number"]) + u32(0) + bytes(32))


def _send(ctx, ctl, d, why):
    q = DQ["DailyQuest"][d["idx"]]
    ctx.reply(ctl, 6003, 0, info(d), "GỬI cmd=6003 nhiệm vụ ngày %d/%d: %s x%d (%s)"
              % (d["number"] + 1, TOTAL, q["params"], target(d), why))


@handler(6003)
def get_info(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    d = ensure(st)
    state.save(st, ctx.account)
    _send(ctx, ctl, d, "thông tin")
    return True


@handler(6004)
def reward(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    d = ensure(st)
    gifts = DQ["DailyGift"][min(d["number"], len(DQ["DailyGift"]) - 1)]["list"]
    got = []
    for g in gifts:
        gid = int(g["id"])
        if gid >= 1001:                     # 1001.. = rương ChestGift[id - 1001]: bốc 1 món theo tỉ lệ
            chest = DQ["ChestGift"][min(gid - 1001, len(DQ["ChestGift"]) - 1)]["list"]
            g = random.choices(chest, weights=[int(c.get("rate", 1)) for c in chest])[0]
            gid = int(g["id"])
        add_item(st, gid, int(g.get("level", 1)), int(g.get("number", 1)))
        got.append(g | {"id": gid})
    gifts = got
    d["number"] += 1
    if d["number"] < TOTAL:
        _new_quest(st, d)
    state.save(st, ctx.account)
    ctx.reply(ctl, 6004, 0, bytes(64), "GỬI cmd=6004 nhận quà nhiệm vụ ngày: %s"
              % ", ".join("loại %s x%s" % (g["id"], g.get("number", 1)) for g in gifts))
    ctx.reply(ctl, 10008, 0, build_items(st), "GỬI cmd=10008 cập nhật kho đồ")
    _send(ctx, ctl, d, "nhiệm vụ mới")
    return True


@handler(6006)
def quick(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    d = ensure(st)
    money = DQ["DailyConfig"]["money"]
    cost = int(money[min(d["number"], len(money) - 1)])
    state.spend(st, coin=cost)
    d["progress"] = target(d)
    state.save(st, ctx.account)
    ctx.log("XONG NGAY NHIỆM VỤ NGÀY: -%d G" % cost)
    _send(ctx, ctl, d, "xong ngay")
    return True


@handler(6007)
def reset(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    d = ensure(st)
    cost = int(DQ["DailyOther"].get("moneyRenew", 10))
    state.spend(st, coin=cost)
    _new_quest(st, d, exclude=d["idx"])
    state.save(st, ctx.account)
    ctx.log("ĐỔI NHIỆM VỤ NGÀY: -%d G" % cost)
    _send(ctx, ctl, d, "đổi nhiệm vụ")
    return True


def progress(st, key, n=1):
    """Server tự cộng tiến độ cho loại nhiệm vụ nó biết (để thoát game vào lại không mất tiến độ)."""
    d = st.get("daily")
    if not d or d.get("day") != _today() or n <= 0:
        return
    if DQ["DailyQuest"][d["idx"]]["params"] == key:
        d["progress"] = min(target(d), int(d.get("progress", 0)) + int(n))


def on_battle(st, stars, gold, elixir, dark):
    for k in (1, 2, 3):
        if stars >= k:
            progress(st, "ATTACK@%d" % k)
    progress(st, "ROB_GOLD", gold)
    progress(st, "ROB_ELIXIR", elixir)
    progress(st, "ROB_DARK", dark)
