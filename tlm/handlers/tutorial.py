"""Hướng dẫn tân thủ: sendUpdateTut (cmd 1009, không dữ liệu) = qua một bước."""
from .. import state
from . import handler


@handler(1009)
def update_tutorial(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    p = st["player"]
    if p.get("tutorial_step", state.TUTORIAL_DONE) < state.TUTORIAL_DONE:
        p["tutorial_step"] = p.get("tutorial_step", 0) + 1
        state.save(st, ctx.account)
        ctx.log("hướng dẫn: bước %d" % p["tutorial_step"])
    return False                      # server tự trả lời (ErrorCode -> stopWaitRespond)
