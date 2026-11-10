"""Quân đội: luyện quân (cmd 11001-11003, phản hồi lớp rTrainTroop).

Dữ liệu client 11001 (log): [int id trại lính][chuỗi loại lính "ARM_1"][short số lượng].
Phản hồi game cần (nhánh thành công trong ServerCommunication::onReceived):
  [int id trại lính][double giờ xong] -> GameDataMgr::getBuilding(id) rồi gán giờ xong vào trại (@0x40).
  Trả toàn số 0 (bản cũ) -> id 0 không có công trình -> con trỏ rỗng -> game sập.
11002 / 11003 cùng lớp phản hồi (chưa rõ dữ liệu gửi lên): trả lại int đầu tiên game gửi làm id trại.
Số lính đã luyện được ghi vào state["troops"] (chưa gửi lại cho game: gói TroopInfo chưa giải mã).
"""
from .. import state
from ..protocol.codec import Reader, f64, u32
from . import handler


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
            troops[troop] = int(troops.get(troop, 0)) + count
            state.save(st, ctx.account)
            note = ": %s x%d (tổng %d)" % (troop, count, troops[troop])
        except Exception as e:
            note = " (không đọc được dữ liệu: %s)" % e
    ctx.log("LUYỆN QUÂN cmd %d trại id=%d%s" % (cmd, bid, note))
    ctx.reply(ctl, cmd, 0, u32(bid) + f64(0) + bytes(256), "GỬI cmd=%d rTrainTroop trại id=%d" % (cmd, bid))
    return True
