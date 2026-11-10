"""Tầng xử lý lệnh: mỗi cmd client gửi -> một hàm xử lý.

Thêm lệnh mới:
    from . import handler

    @handler(1234)
    def on_something(ctx, ctl, cmd, payload):
        ...cập nhật state...
        ctx.reply(ctl, cmd, error=0, data=b"...")   # tự trả lời
        return True                                   # True = đã trả lời; False/None = để server tự trả lời
Rồi import module đó trong load_all() bên dưới.
"""
HANDLERS = {}


def handler(*cmds):
    def deco(fn):
        for c in cmds:
            HANDLERS[c] = fn
        return fn
    return deco


def load_all():
    from . import session, city, tutorial, battle, finish, profile, shop, army, single  # noqa: F401  (đăng ký handler)
    return HANDLERS
