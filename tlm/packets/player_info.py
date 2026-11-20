"""GetPlayerInfo (cmd 1001) - thứ tự trường theo CmdReceiveGetPlayerInfo::readData.

Offset @0x.. là vị trí trường trong đối tượng gói của game. Game chép (gói + 0x28) vào
GameDataMgr+0x298 và GameDataMgr+0xd0 (CityMgr::onGetPlayerInfo).
ĐÃ XÁC NHẬN trên máy: cấp @0x58, vàng @0x60, G @0x64, dầu hồng @0x68, hướng dẫn @0x110 (> 69 = xong).
Hướng dẫn ngọc bổ trợ @0x114 (GameDataMgr+0x1bc): <= 14 thì CityMgr::onGetTroopInfo gọi startTutorialCrystal.
"""
import time

from .. import clans, state
from ..protocol.codec import f64, pstr, u8, u16, u32


def build(st, log=None, account=None):
    p = st["player"]
    gold, elixir, dark, coin, (cg, ce, cd) = state.effective_resources(st)
    if log:
        log("    người chơi: vàng %d/%d, dầu %d/%d, dầu đen %d/%d, G %d" % (gold, cg, elixir, ce, dark, cd, coin))
    account = account or st.get("_account") or state.DEFAULT_ACCOUNT
    d = u32(clans.uid_of(account))          # userId (GameDataMgr+0xd0; tài khoản đầu tiên = 1)
    d += pstr(str(p.get("name", "Khach")))  # tên người chơi
    d += u32(p.get("exp", 0))               # @0x54 kinh nghiệm
    d += u32(p.get("level", 1))             # @0x58 cấp người chơi (ĐÃ XÁC NHẬN)
    d += u32(p.get("trophy", 0))            # @0x5c CÚP (UserInfoStruct @0x34)
    d += u32(gold)                          # @0x60 VÀNG (ĐÃ XÁC NHẬN)
    d += f64(coin)                          # @0x64 G (ĐÃ XÁC NHẬN)
    d += u32(elixir)                        # @0x68 DẦU HỒNG (ĐÃ XÁC NHẬN)
    d += u32(dark)                          # @0x6c dầu đen (ĐOÁN)
    d += f64(0) + f64(int(p.get("shield_end", 0))) + f64(0)  # @0x78, @0x80 GIỜ HẾT KHIÊN (GameDataMgr+0x128), @0x88
    d += f64(int(time.time()))              # @0x1f0 GIỜ MÁY CHỦ (giây) -> Utility::setCurTime
    d += u32(0)                             # @0xa4
    d += u32(p.get("tutorial_step", state.TUTORIAL_DONE))  # @0x110 TIẾN ĐỘ HƯỚNG DẪN (> 69 = xong)
    d += u32(clans.clan_id_of(account))     # @0xa8 ID BANG HỘI (GameDataMgr+0x318) -> vào game tự gửi 3037
    cds = list(p.get("shield_cd", [0, 0, 0]))[:3]
    d += u8(1) + b"".join(f64(int(c)) for c in cds)  # cờ + 3 double @0x98/@0x9c/@0xa0: giờ được mua lại khiên 1/2/3
    d += u8(0)                              # cờ @0x200
    d += f64(0) + u32(0) + f64(0)           # @0x130 @0x138 @0x140
    d += pstr("")                           # chuỗi thứ hai
    d += f64(0) + f64(0)                    # @0x90 @0x148
    d += u16(0) + u32(0)                    # @0x150 @0x70
    d += u8(0)                              # @0x160
    d += u32(0) + u32(0)                    # @0x164 @0x168
    d += f64(0) + f64(0) + f64(0)           # @0x170 @0x208 @0x210
    d += u8(0)                              # @0x178
    d += u8(0) + u8(0)                      # hai danh sách byte: 0
    d += u32(0) + f64(0) + u8(0) + u8(0)    # @0x1b0 @0x218 cờ@0x220 @0x1b4
    d += u32(0)                             # @0x1b8
    d += u8(0)                              # danh sách byte thứ ba: 0
    d += u8(0) + u8(0)                      # @0x224 @0x228
    d += u8(0) + u8(0) + u8(0)              # @0x1d8 @0x1d9 @0x1da
    d += u16(0)                             # @0x1dc
    d += u8(0) + u8(0)                      # @0x22c @0x22d
    d += u8(0)                              # cờ @0x1e0
    d += bytes(8)                           # @0x1e8 (getDoubleA, 8 byte)
    d += u32(p.get("tutorial_crystal", state.TUTORIAL_CRYSTAL_DONE))  # @0x114 HƯỚNG DẪN NGỌC (> 14 = xong)
    return d + bytes(256)                   # các trường còn lại = 0
