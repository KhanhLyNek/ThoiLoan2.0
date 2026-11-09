"""Trận đánh. BattleMgr::sendCmdEndBattle = cmd 9003: 7 int + chuỗi + ... (chưa giải mã hết)."""
from . import handler


@handler(9003)
def end_battle(ctx, ctl, cmd, payload):
    ints = [int.from_bytes(payload[i:i + 4], "big", signed=True) for i in range(0, min(len(payload), 28), 4)]
    ctx.log("KẾT THÚC TRẬN: 7 số đầu = %s (chưa rõ ô nào là chiến lợi phẩm, gửi log này để giải mã)" % ints)
    return False
