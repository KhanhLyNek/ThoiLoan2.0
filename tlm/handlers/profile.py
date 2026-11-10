"""Hồ sơ cá nhân: thành tựu (cmd 8002).

Gói Achievement (đọc từ nhánh thành công của cmd 8002 trong ServerCommunication::onReceived):
  [byte số mục] rồi mỗi mục [byte id][byte cấp][byte trạng thái @0x3c][int tiến độ].
GameDataMgr::onGetAchievementInfo đọc đúng 16 mục (16 thành tựu trong Achivement.json, mỗi cái 5 cấp)
và tra JsonMgr::getDataAchievement(id, cấp). Thiếu mục -> vector::at ném ngoại lệ -> game sập
(lúc mở tab Thành tựu hoặc khi nhận gói rỗng).
"""
from .. import state
from ..protocol.codec import u8, u32
from . import handler

ACHIEVEMENT_COUNT = 16


@handler(8002)
def achievement(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    saved = st.get("achievements", {})
    data = u8(ACHIEVEMENT_COUNT)
    for aid in range(1, ACHIEVEMENT_COUNT + 1):
        a = saved.get(str(aid), {})
        data += u8(aid) + u8(a.get("level", 1)) + u8(a.get("status", 0)) + u32(a.get("progress", 0))
    ctx.reply(ctl, 8002, 0, data + bytes(256), "GỬI cmd=8002 Achievement (%d thành tựu)" % ACHIEVEMENT_COUNT)
    return True
