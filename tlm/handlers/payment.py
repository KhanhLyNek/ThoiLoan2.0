"""Nạp G miễn phí (server riêng) và rương yêu thương.

12006 AddGGUI::sendZingPayment (nạp THẺ): 4 chuỗi (loại thẻ / seri / mã thẻ / ...).
12007 AddGGUI::sendZingSmsPayment (nạp SMS): 3 chuỗi.
     Phản hồi (onReceiveZingPayment / onReceiveZingSmsPayment): [chuỗi mã giao dịch][int trạng thái][chuỗi thông báo]
     [chuỗi]. Trạng thái 1 = thành công im lặng (riêng SMS: game còn đọc thêm số + nội dung rồi TỰ GỬI TIN NHẮN
     THẬT bằng PlatformUtil::sendSms) -> server trả trạng thái 2 để game chỉ hiện hộp thông báo, không gửi SMS.
     Mọi lần nạp đều thành công: cộng PAY_G G rồi đẩy cmd 1010.
12005 CityMgr::validateGoogleIap (mua Google Play): [chuỗi JSON đơn hàng][chuỗi chữ ký][chuỗi gói].
     APK vá (tools/obbgate: TlmFreePay, móc AndroidPlatform.purchaseAnItem) đổi kiểu nạp Google Play (Google Play, ZaloPay, SMS, thẻ web, ATM) thành lệnh này, không mở
     ứng dụng ngoài (trước đây game bị đẩy ra ngoài rồi quay lại màn tải). Phản hồi error 0 + [chuỗi][chuỗi]
     -> AddGGUI::comsumePurchase (APK vá đã tắt consume) rồi server đẩy 1010.
1047 (server -> game) VIP: [byte cấp VIP][int điểm VIP] -> GameDataMgr+0x424/+0x428 rồi VIPmanager::checkVip.
     Cấp = số mốc Vip.json "requireVipPoint" đã đạt (20, 50, 100, 500, 1000, 5000, 10000, 20000, 50000, 100000).
     Điểm VIP = tổng G đã nạp / VIP_RATE. Đẩy lúc vào game và sau mỗi lần nạp.
1059 VIPmanager::addVipGift [byte cấp VIP]: nhận quà lên cấp VIP (Vip.json Vip[cấp-1].coin G; packId = gói trang bị
     VipBonus - hệ trang bị chưa có). Cấp đã nhận lưu player.vip_gifts -> PlayerInfo @0x1c0 (GameDataMgr+0x268).
1010 (server -> game) cập nhật G: [double số G] -> CityMgr::onGetUpdateCoin -> GameDataMgr::setMoney("coin").
2046 rương yêu thương (ShopGUI2Mgr::onReceiveChestLove): [int số thứ tự quà, từ 1][double giờ mở lần sau].
     Danh sách quà = PackOrder.json poChestLove; trả 0 (bản cũ) -> chỉ số -1 -> vector::at ném lỗi -> game sập.
"""
import json
import random
import time

from .. import state
from ..data import load_table
from ..protocol.codec import Reader, f64, pstr, u8, u32
from . import handler
from .inventory import add_item, item_name

PAY_G = 10000                                   # số G cộng mỗi lần nạp
VIP_RATE = 100                                  # 100 G nạp = 1 điểm VIP (mỗi lần nạp +100 điểm)
try:
    VIP_REQ = [int(v["requireVipPoint"]) for v in load_table("Vip.json")["Vip"]]
except Exception:
    VIP_REQ = [20, 50, 100, 500, 1000, 5000, 10000, 20000, 50000, 100000]
CHEST = load_table("chest_love.json")


def vip_point(st):
    p = st["player"]
    if "vip_point" not in p:                    # bản cũ: tính lại từ tổng G đã nạp
        p["vip_point"] = int(p.get("charged", 0)) // VIP_RATE
    return int(p["vip_point"])


def vip_level(point):
    return sum(1 for need in VIP_REQ if point >= need)


def push_vip(ctx, ctl, st):
    pt = vip_point(st)
    ctx.push(ctl, 1047, u8(vip_level(pt)) + u32(pt) + bytes(32), " [VIP %d, %d điểm]" % (vip_level(pt), pt))


def _add_paid(st, g):
    p = st["player"]
    vip_point(st)
    p["coin"] = int(p.get("coin", 0)) + g
    p["charged"] = int(p.get("charged", 0)) + g
    p["vip_point"] = int(p["vip_point"]) + g // VIP_RATE


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
    _add_paid(st, PAY_G)
    state.save(st, ctx.account)
    msg = "Nạp %s thành công! +%s G" % (kind, "{:,}".format(PAY_G).replace(",", "."))
    trans = "TL%d" % int(time.time())
    ctx.reply(ctl, cmd, 0, pstr(trans) + u32(2) + pstr(msg) + pstr("") + bytes(64),
              "GỬI cmd=%d NẠP %s thành công +%d G (tổng %d)" % (cmd, kind, PAY_G, st["player"]["coin"]))
    push_coin(ctx, ctl, st)
    push_vip(ctx, ctl, st)
    return True


@handler(12006)
def charge_card(ctx, ctl, cmd, payload):
    return _charge(ctx, ctl, cmd, payload, "thẻ")


@handler(12007)
def charge_sms(ctx, ctl, cmd, payload):
    return _charge(ctx, ctl, cmd, payload, "SMS")


@handler(12005)
def charge_iap(ctx, ctl, cmd, payload):
    product = token = ""
    try:
        r = Reader(payload)
        data = json.loads(r.str() or "{}")
        product, token = str(data.get("productId", "")), str(data.get("purchaseToken", ""))
    except Exception:
        pass
    st = state.load(ctx.account)
    _add_paid(st, PAY_G)
    state.save(st, ctx.account)
    ctx.reply(ctl, 12005, 0, pstr(product) + pstr(token) + bytes(64),
              "GỬI cmd=12005 NẠP (%s) thành công +%d G (tổng %d)" % (product or "?", PAY_G, st["player"]["coin"]))
    push_coin(ctx, ctl, st)
    push_vip(ctx, ctl, st)
    return True


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


try:
    VIP_ROWS = load_table("Vip.json")["Vip"]
except Exception:
    VIP_ROWS = []


@handler(1059)
def vip_gift(ctx, ctl, cmd, payload):
    lvl = payload[0] if payload else 0
    st = state.load(ctx.account)
    p = st["player"]
    got = p.setdefault("vip_gifts", [])
    if lvl < 1 or lvl in got or lvl > vip_level(vip_point(st)):
        ctx.log("quà VIP cấp %d: bỏ qua (đã nhận %s, VIP hiện tại %d)" % (lvl, got, vip_level(vip_point(st))))
        return True
    got.append(lvl)
    row = VIP_ROWS[lvl - 1] if lvl - 1 < len(VIP_ROWS) else {}
    coin = int(row.get("coin", 0))
    if coin:
        p["coin"] = int(p.get("coin", 0)) + coin
    state.save(st, ctx.account)
    ctx.log("NHẬN QUÀ VIP cấp %d: +%d G%s" % (lvl, coin, " (gói trang bị %s chưa hỗ trợ)" % row.get("packId") if row.get("packId") else ""))
    if coin:
        push_coin(ctx, ctl, st)
    return True
