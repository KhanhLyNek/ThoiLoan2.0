"""Phiên chơi: thông tin người chơi, dữ liệu làng, về nhà."""
from .. import config, state
from ..packets import building_info, player_info
from ..protocol.codec import Reader
from . import handler


@handler(1)
def login(ctx, ctl, cmd, payload):
    """Login: dữ liệu bắt đầu bằng sessionKey (chuỗi) do /login cấp -> chọn tài khoản cho kết nối."""
    try:
        key = Reader(payload).str().strip()
    except Exception:
        key = ""
    if key:
        ctx.account = key
    ctx.log("tài khoản: %s" % ctx.account)
    return False                      # server tự trả lời "thành công"


def push_city(ctx, ctl, with_player=False):
    """Đẩy dữ liệu làng. Game KHÔNG tự xin công trình (getBuildingInfo không có chỗ gọi)."""
    if not config.PUSH_ENABLED:
        return
    st = state.load(ctx.account)
    if with_player:
        ctx.push(ctl, 1001, player_info.build(st, log=ctx.log), " [thông tin người chơi]")
    ctx.push(ctl, 1002, building_info.build(st),
             " [%d công trình + %d chướng ngại]" % (len(st["buildings"]), len(st.get("obstacles", []))))
    ctx.push(ctl, 1003, bytes(512), " [quân: toàn số 0]")


@handler(1001)
def get_user_info(ctx, ctl, cmd, payload):
    """getUserInfo: trả GetPlayerInfo rồi đẩy BuildingInfo + TroopInfo."""
    st = state.load(ctx.account)
    ctx.reply(ctl, 1001, 0, player_info.build(st, log=ctx.log), "GỬI cmd=1001 GetPlayerInfo")
    if not ctx.silent:
        push_city(ctx, ctl)
    return True


@handler(1006)
def visit_friend(ctx, ctl, cmd, payload):
    """Bấm "về nhà" (CityMgr::returnMyHome) = sendVisitFriend(userId): gửi lại toàn bộ làng."""
    if not ctx.silent:
        push_city(ctx, ctl, with_player=True)
    return True
