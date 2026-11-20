"""Hồ sơ cá nhân: thành tựu (cmd 8002).

Gói Achievement (đọc từ nhánh thành công của cmd 8002 trong ServerCommunication::onReceived):
  [byte số mục] rồi mỗi mục [byte id][byte cấp][byte trạng thái @0x3c][int tiến độ].
GameDataMgr::onGetAchievementInfo đọc đúng 16 mục (16 thành tựu trong Achivement.json, mỗi cái 5 cấp)
và tra JsonMgr::getDataAchievement(id, cấp). Thiếu mục -> vector::at ném ngoại lệ -> game sập
(lúc mở tab Thành tựu hoặc khi nhận gói rỗng).
"""
from .. import state
from ..data import load_table
from ..protocol.codec import u8, u32
from . import handler

ACHIEVEMENT_COUNT = 16
REWARD = load_table("achievement.json")      # id -> cấp -> {exp, g}
# thành tựu đếm do server ghi (số 2 sao, 4 dọn chướng ngại, 6 vàng cướp, 7 dầu cướp,
# 13 trận thắng, 14 phòng thủ thành công). Loại "sở hữu" (nhà, cúp) game tự tính lại.


def add_progress(st, aid, n):
    if n <= 0:
        return
    a = st.setdefault("achievements", {}).setdefault(str(aid), {"level": 1, "status": 0, "progress": 0})
    a["progress"] = int(a.get("progress", 0)) + int(n)


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


@handler(8001)
def achievement_reward(ctx, ctl, cmd, payload):
    """sendGetRewardAchievement([byte id]): game tự cộng exp + G (GameDataMgr::getRewardAchievement) rồi lên cấp;
    nhận xong cấp 5 -> trạng thái 2. Server làm y hệt để vào lại game không mất."""
    aid = payload[0] if payload else 0
    st = state.load(ctx.account)
    a = st.setdefault("achievements", {}).setdefault(str(aid), {"level": 1, "status": 0, "progress": 0})
    lvl = int(a.get("level", 1))
    if int(a.get("status", 0)) == 2 or str(aid) not in REWARD:
        ctx.log("thành tựu %d: đã nhận hết" % aid)
        return False
    r = REWARD[str(aid)].get(str(lvl), {"exp": 0, "g": 0})
    p = st["player"]
    p["exp"] = int(p.get("exp", 0)) + int(r["exp"])
    p["coin"] = int(p.get("coin", 0)) + int(r["g"])
    if lvl >= 5:
        a["status"] = 2
    else:
        a["level"] = lvl + 1
    state.save(st, ctx.account)
    ctx.log("NHẬN THƯỞNG THÀNH TỰU %d cấp %d: +%d kinh nghiệm, +%d G" % (aid, lvl, r["exp"], r["g"]))
    return False
