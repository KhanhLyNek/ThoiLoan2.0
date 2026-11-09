"""Xây / nâng cấp / dọn chướng ngại XONG: sendFinish (2005), sendQuickFinish bằng G (2006).

Dữ liệu client: [chuỗi loại][int id][byte].
Phản hồi game cần (đọc từ ServerCommunication::onReceived, nhánh thành công):
  2005/2006 FinishBuilding : [int id][double giờ xong] -> game gán vào công trình (@0x40).
             Trả sai (toàn số 0 như bản cũ) -> game không tìm thấy id 0 và gửi lại mỗi giây.
  2011 RemoveComplete      : [int id][byte G thưởng][int] -> ObstacleObject::getReward cộng G
             và kinh nghiệm (exp của Obstacle.json) rồi xoá chướng ngại.
"""
import random

from .. import gamedata, state
from ..protocol.codec import Reader, f64, u8, u32
from . import handler

OBSTACLE_G_CHANCE = 0.5          # tỉ lệ được G khi dọn chướng ngại
OBSTACLE_G_RANGE = (1, 5)        # số G nếu được


@handler(2005, 2006)
def finish(ctx, ctl, cmd, payload):
    try:
        r = Reader(payload)
        btype = r.str()
        bid = r.u32()
    except Exception as e:
        ctx.log("hoàn tất: không đọc được dữ liệu (%s)" % e)
        return False
    ctx.reply(ctl, cmd, 0, u32(bid) + f64(0) + bytes(256),
              "GỬI cmd=%d FinishBuilding id=%d (xong ngay)" % (cmd, bid))
    if btype.startswith("OBS"):
        _obstacle_done(ctx, ctl, bid, btype)
    else:
        ctx.log("HOÀN TẤT %s id=%d%s" % (btype, bid, " (dùng G)" if cmd == 2006 else ""))
    return True


def _obstacle_done(ctx, ctl, bid, btype):
    st = state.load()
    o = next((x for x in st.get("obstacles", []) if x["id"] == bid), None)
    if o:                                         # phòng khi chưa xoá lúc bắt đầu dọn (2010)
        st["obstacles"].remove(o)
    g = random.randint(*OBSTACLE_G_RANGE) if random.random() < OBSTACLE_G_CHANCE else 0
    exp = int(gamedata.OBSTACLE_EXP.get(btype, 0))
    p = st["player"]
    p["coin"] = int(p.get("coin", 0)) + g
    p["exp"] = int(p.get("exp", 0)) + exp
    state.save(st)
    ctx.push(ctl, 2011, u32(bid) + u8(g) + u32(0) + bytes(256),
             " RemoveComplete id=%d: +%d G, +%d kinh nghiệm" % (bid, g, exp))
