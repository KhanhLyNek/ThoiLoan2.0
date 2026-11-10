"""Phó bản (bản đồ đánh máy): sendGetSingleMapInfo (cmd 9039, phản hồi lớp SingleMap).

Gói SingleMap (đọc từ nhánh thành công của cmd 9039 trong ServerCommunication::onReceived):
  [int màn hiện tại][int số mục] rồi mỗi mục [int id][int sao][int][int][int][byte][byte].
  Màn hiện tại -> GameDataMgr+0x4b0; tổng sao các mục -> GameDataMgr+0x4dc; danh sách -> saveMapPoint.
Màn Tấn công (GuiFindMatch::show) cuộn bản đồ tới mốc "point<màn hiện tại>". Mốc bắt đầu từ 1, nên trả
toàn số 0 (bản cũ) -> tìm "point0" không có -> UIWidget::getPosition trên con trỏ rỗng -> game sập.
Game có 50 màn (SingleBattle.json). Ý nghĩa 3 int + 2 byte của mỗi mục chưa rõ, nên chưa gửi mục nào.
"""
from .. import state
from ..protocol.codec import u32
from . import handler

MAX_MAP = 50


@handler(9039)
def single_map_info(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    cur = max(1, min(MAX_MAP, int(st["player"].get("single_map", 1))))
    ctx.reply(ctl, 9039, 0, u32(cur) + u32(0) + bytes(256), "GỬI cmd=9039 SingleMap: màn hiện tại %d" % cur)
    return True
