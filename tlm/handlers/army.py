"""Quân đội: luyện quân (cmd 11001-11003, phản hồi lớp rTrainTroop).

Dữ liệu client 11001 (log): [int id trại lính][chuỗi loại lính "ARM_1"][short số lượng].
Phản hồi game cần (nhánh thành công trong ServerCommunication::onReceived):
  [int id trại lính][double giờ xong] -> GameDataMgr::getBuilding(id) rồi gán giờ xong vào trại (@0x40).
  Trả toàn số 0 (bản cũ) -> id 0 không có công trình -> con trỏ rỗng -> game sập.
11002 / 11003 cùng lớp phản hồi (chưa rõ dữ liệu gửi lên): trả lại int đầu tiên game gửi làm id trại.
Số lính đã luyện được ghi vào state["troops"] (giới hạn theo sức chứa trại quân) và gửi lại khi vào game
qua gói TroopInfo (cmd 1003).
"""
from .. import state
from ..data import load_table
from ..protocol.codec import Reader, f64, u32
from . import handler

_GEN = load_table("battle_gen.json")


def camp_capacity(st):
    """Tổng chỗ trong các trại quân (ArmyCamp.json, capacity theo cấp)."""
    return sum(int(_GEN["camp_capacity"].get(str(b["level"]), 20)) for b in st["buildings"] if b["type"].startswith("AMC"))


def used_space(troops):
    return sum(int(_GEN["housing"].get(t, 1)) * int(n) for t, n in troops.items())


def fit_to_camps(st):
    """Cắt bớt quân vượt sức chứa trại (bản 4.4 chưa giới hạn). Trả về True nếu có thay đổi."""
    troops = st.get("troops", {})
    cap, changed = camp_capacity(st), False
    while troops and used_space(troops) > cap:
        t = max(troops, key=lambda k: int(troops[k]))
        troops[t] = int(troops[t]) - 1
        if troops[t] <= 0:
            del troops[t]
        changed = True
    return changed


@handler(11001, 11002, 11003)
def train_troop(ctx, ctl, cmd, payload):
    bid = int.from_bytes(payload[0:4], "big") if len(payload) >= 4 else 0
    note = ""
    if cmd == 11001:
        try:
            r = Reader(payload)
            r.u32()
            troop = r.str()
            count = r.u16() if r.remaining() >= 2 else 1
            st = state.load(ctx.account)
            troops = st.setdefault("troops", {})
            room = camp_capacity(st) - used_space(troops)
            space = int(_GEN["housing"].get(troop, 1))
            count = max(0, min(count, room // max(1, space)))
            troops[troop] = int(troops.get(troop, 0)) + count
            state.save(st, ctx.account)
            note = ": %s +%d (tổng %d, trại %d/%d chỗ)" % (troop, count, troops[troop], used_space(troops), camp_capacity(st))
        except Exception as e:
            note = " (không đọc được dữ liệu: %s)" % e
    ctx.log("LUYỆN QUÂN cmd %d trại id=%d%s" % (cmd, bid, note))
    ctx.reply(ctl, cmd, 0, u32(bid) + f64(0) + bytes(256), "GỬI cmd=%d rTrainTroop trại id=%d" % (cmd, bid))
    return True
