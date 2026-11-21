"""Nhật ký trận đấu, XEM LẠI trận, TRẢ THÙ (xem tlm/replays.py và tlm/packets/replay.py).

9047 ReplayMgr::sendGetLogInfo (gửi lúc đăng nhập, sau TroopInfo; và khi mở hộp thư): không dữ liệu.
     Trả ReplayBattleList: trận phòng thủ + trận tấn công. Game hiện chấm đỏ hộp thư (showInboxNotice).
9011 ReplayMgr::sendReplayBattle: [int id trận][int]. Trả ReplayBattleInfo (làng lúc đánh + hàng đợi thả lính).
     Lỗi != 0 -> game bỏ qua gói (onReceived chỉ gọi onGetReplayBattleInfo khi error = 0).
9013 ReplayMgr::sendRevenge: [int userId đối thủ][int 1|2]. Trả BattleInfo làng HIỆN TẠI của đối thủ
     (ReplayMgr::onGetBattleRevenge). Mã lỗi: 30 = đối thủ đang online (REVENGE_ONLINE),
     31 = đối thủ đang có khiên (REVENGE_SHIELD_TIME), 33 = không tìm thấy (REVENGE_NOT_FOUND).
"""
import time

from .. import clans, replays, state
from ..packets import replay as replay_pkt
from ..protocol.codec import Reader
from . import handler
from .context import online

ERR_ONLINE, ERR_SHIELD, ERR_NOT_FOUND = 30, 31, 33


@handler(9047)
def battle_log(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    dl = [e for e in st.get("defense_log", []) if "id" in e]       # bỏ dòng kiểu cũ (bản <= 6.9, không có id)
    al = [e for e in st.get("attack_log", []) if "id" in e]
    ctx.reply(ctl, 9047, 0, replay_pkt.battle_list(dl, al),
              "GỬI cmd=9047 nhật ký trận (%d phòng thủ, %d tấn công)" % (len(dl), len(al)))
    return True


@handler(9011)
def replay_battle(ctx, ctl, cmd, payload):
    rid = int.from_bytes(payload[0:4], "big") if len(payload) >= 4 else 0
    rec = replays.get(rid) if rid else None
    if rec is None:
        ctx.reply(ctl, 9011, 1, b"", "GỬI cmd=9011 lỗi: không còn dữ liệu xem lại trận #%d" % rid)
        return True
    ctx.log("XEM LẠI trận #%d: %s đánh %s, %d sao %d%%, %d lần thả lính, dài %d giây"
            % (rid, rec.get("att_name"), rec.get("def_name"), rec.get("stars", 0), rec.get("percent", 0),
               len(rec.get("actions") or []), int(rec.get("end_tick", 0)) // 30))
    ctx.reply(ctl, 9011, 0, replay_pkt.replay_info(rec), "GỬI cmd=9011 dữ liệu xem lại trận #%d" % rid)
    return True


@handler(9013)
def revenge(ctx, ctl, cmd, payload):
    from . import battle
    try:
        uid = Reader(payload).u32()
    except Exception:
        uid = 0
    acc = clans.account_of_uid(uid) if uid else None
    if not acc or acc == ctx.account:
        ctx.reply(ctl, 9013, ERR_NOT_FOUND, b"", "GỬI cmd=9013 trả thù: không tìm thấy người chơi %d" % uid)
        return True
    vst = state.load(acc)
    if float(vst["player"].get("shield_end", 0)) > time.time():
        ctx.reply(ctl, 9013, ERR_SHIELD, b"", "GỬI cmd=9013 trả thù: %s đang có khiên" % acc)
        return True
    if online(acc):
        ctx.reply(ctl, 9013, ERR_ONLINE, b"", "GỬI cmd=9013 trả thù: %s đang online" % acc)
        return True
    st = state.load(ctx.account)
    for e in reversed(st.get("defense_log", [])):                 # tắt nút trả thù của trận gần nhất với người này
        if e.get("acc") == acc and not e.get("revenged"):
            e["revenged"] = True
            break
    if float(st["player"].get("shield_end", 0)) > time.time():    # đi đánh -> mất khiên
        st["player"]["shield_end"] = 0
        ctx.log("    đi đánh nên MẤT KHIÊN")
    state.save(st, ctx.account)
    th = next((b["level"] for b in vst["buildings"] if b["type"] == "TOW_1"), 1)
    ctx.battle = {"kind": "real", "victim": acc, "dropped": {}, "revenge": True}
    return battle.start_battle(ctx, ctl, 9013, st, battle.real_base(vst), str(vst["player"].get("name", acc)), th,
                               uid, "TRẢ THÙ %s" % acc)
