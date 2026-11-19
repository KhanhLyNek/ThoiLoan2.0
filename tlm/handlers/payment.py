"""Nạp G miễn phí (server riêng) và rương yêu thương.

12006 AddGGUI::sendZingPayment (nạp THẺ): 4 chuỗi (loại thẻ / seri / mã thẻ / ...).
12007 AddGGUI::sendZingSmsPayment (nạp SMS): 3 chuỗi.
     Phản hồi (onReceiveZingPayment / onReceiveZingSmsPayment): [chuỗi mã giao dịch][int trạng thái][chuỗi thông báo]
     [chuỗi]. Trạng thái 1 = thành công im lặng (riêng SMS: game còn đọc thêm số + nội dung rồi TỰ GỬI TIN NHẮN
     THẬT bằng PlatformUtil::sendSms) -> server trả trạng thái 2 để game chỉ hiện hộp thông báo, không gửi SMS.
     Mọi lần nạp đều thành công: cộng PAY_G G rồi đẩy cmd 1010.
1010 (server -> game) cập nhật G: [double số G] -> CityMgr::onGetUpdateCoin -> GameDataMgr::setMoney("coin").
2046 rương yêu thương (ShopGUI2Mgr::onReceiveChestLove): [int số thứ tự quà, từ 1][double giờ mở lần sau].
     Danh sách quà = PackOrder.json poChestLove; trả 0 (bản cũ) -> chỉ số -1 -> vector::at ném lỗi -> game sập.
"""
import random
import time

from .. import state
from ..data import load_table
from ..protocol.codec import Reader, f64, pstr, u32
from . import handler
from .inventory import add_item, item_name

PAY_G = 10000                                   # số G cộng mỗi lần nạp
CHEST = load_table("chest_love.json")


def push_coin(ctx, ctl, st):
    coin = int(st["player"].get("coin", 0))
    ctx.push(ctl, 1010, f64(coin) + bytes(32), " [G = %d]" % coin)


def _charge(ctx, ctl, cmd, payload, kind):
    try:
        r = Reader(payload)
        parts = []
        while r.remaining() >= 2:
            parts.append(r.str())
    except Exception:
        pass
    st = state.load(ctx.account)
    st["player"]["coin"] = int(st["player"].get("coin", 0)) + PAY_G
    st["player"]["charged"] = int(st["player"].get("charged", 0)) + PAY_G
    state.save(st, ctx.account)
    msg = "Nạp %s thành công! +%s G" % (kind, "{:,}".format(PAY_G).replace(",", "."))
    trans = "TL%d" % int(time.time())
    ctx.reply(ctl, cmd, 0, pstr(trans) + u32(2) + pstr(msg) + pstr("") + bytes(64),
              "GỬI cmd=%d NẠP %s thành công +%d G (tổng %d)" % (cmd, kind, PAY_G, st["player"]["coin"]))
    push_coin(ctx, ctl, st)
    return True


@handler(12006)
def charge_card(ctx, ctl, cmd, payload):
    return _charge(ctx, ctl, cmd, payload, "thẻ")


@handler(12007)
def charge_sms(ctx, ctl, cmd, payload):
    return _charge(ctx, ctl, cmd, payload, "SMS")


@handler(2046)
def chest_love(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    th = next((b["level"] for b in st["buildings"] if b["type"] == "TOW_1"), 1)
    lst = CHEST["list"]
    ok = [(i, e) for i, e in enumerate(lst, 1) if int(e["townHallRequired"]) <= th] or [(1, lst[0])]
    idx, e = random.choices(ok, weights=[max(1, int(x["rate"])) for _, x in ok])[0]
    add_item(st, int(e["type"]), int(e["level"]), int(e["num"]))
    nxt = int(time.time()) + int(CHEST["chestLoveTime"]) * 3600
    st["player"]["chest_love_next"] = nxt
    state.save(st, ctx.account)
    ctx.reply(ctl, 2046, 0, u32(idx) + f64(nxt) + bytes(64),
              "GỬI cmd=2046 RƯƠNG YÊU THƯƠNG: quà #%d = %d x %s" % (idx, int(e["num"]), item_name(e["type"], e["level"])))
    return True
