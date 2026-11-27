"""Phiên chơi: thông tin người chơi, dữ liệu làng, về nhà."""
from .. import config, state
from ..packets import building_info, player_info, troop_info
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
    from .context import register
    register(ctx)
    ctx.log("tài khoản: %s" % ctx.account)
    return False                      # server tự trả lời "thành công"


def push_city(ctx, ctl, with_player=False):
    """Đẩy dữ liệu làng. Game KHÔNG tự xin công trình (getBuildingInfo không có chỗ gọi)."""
    if not config.PUSH_ENABLED:
        return
    st = state.load(ctx.account)
    from .army import fit_to_camps, settle_training
    from .research import settle_research
    from .spell import settle_spells
    moved = settle_training(st) + int(settle_research(ctx, st)) + settle_spells(st)
    if fit_to_camps(st) or moved:
        state.save(st, ctx.account)
    if with_player:
        ctx.push(ctl, 1001, player_info.build(st, log=ctx.log, account=ctx.account), " [thông tin người chơi]")
    ctx.push(ctl, 1002, building_info.build(st, account=ctx.account),
             " [%d công trình + %d chướng ngại]" % (len(st["buildings"]), len(st.get("obstacles", []))))
    ctx.push(ctl, 1003, troop_info.build(st),
             " [quân: %s]" % (", ".join("%s x%s" % kv for kv in sorted(st.get("troops", {}).items())) or "trống"))



@handler(1001)
def get_user_info(ctx, ctl, cmd, payload):
    """getUserInfo: trả GetPlayerInfo rồi đẩy BuildingInfo + TroopInfo."""
    st = state.load(ctx.account)
    ctx.reply(ctl, 1001, 0, player_info.build(st, log=ctx.log, account=ctx.account), "GỬI cmd=1001 GetPlayerInfo")
    if not ctx.silent:
        push_city(ctx, ctl)
        from .payment import push_vip
        push_vip(ctx, ctl, st)
        from .daily import push_login7
        st = state.load(ctx.account)                 # tải lại: push_city vừa lưu (lính luyện xong, phép...)
        push_login7(ctx, ctl, st)
        state.save(st, ctx.account)
    return True


@handler(1006)
def visit_friend(ctx, ctl, cmd, payload):
    """CityMgr::sendVisitPlayer(uid) (về nhà = uid của mình; thăm bạn / thăm chủ đảo từ bản đồ thế giới
    OccupyIslandGui::sendVisit = uid khác, game đặt trạng thái 2 = đang thăm). Không có phản hồi riêng: game dựng làng
    từ 1001/1002/1003 được đẩy. Ở trạng thái thăm CityMgr::onGetPlayerInfo chỉ chép vào GameDataMgr+0x298 (người được
    thăm), không đè dữ liệu của mình (+0xd0)."""
    if ctx.silent:
        return True
    uid = int.from_bytes(payload[:4], "big") if len(payload) >= 4 else 0
    from .. import clans
    acc = clans.account_of_uid(uid) if uid else None
    if acc and acc != ctx.account:
        try:
            vst = state.load(acc)
        except Exception:
            vst = None
        if vst:
            ctx.log("THĂM LÀNG %s (uid %d)" % (vst["player"].get("name", acc), uid))
            ctx.push(ctl, 1001, player_info.build(vst, account=acc), " [người được thăm]")
            ctx.push(ctl, 1002, building_info.build(vst, account=acc), " [làng %s: %d công trình]" % (acc, len(vst["buildings"])))
            ctx.push(ctl, 1003, troop_info.build(vst), " [quân người được thăm]")
            return True
    if uid and acc != ctx.account:
        ctx.log("thăm uid %d: không có người chơi này (đảo trống / máy) -> về nhà" % uid)
    push_city(ctx, ctl, with_player=True)
    return True
