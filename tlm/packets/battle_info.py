"""BattleInfo (cmd 9001) - làng đối thủ, theo CmdReceiveBattleInfo::readData.

Đầu gói: int id đối thủ | chuỗi tên | int @0x90 | int @0x94 | bool @0x98 | chuỗi | int @0x9c | chuỗi
         | int @0xa8 | int SỐ CÔNG TRÌNH
Mỗi công trình (BuildingObject): int id @0x310 | chuỗi loại | int Ô @0x70 (= y*44 + x, BaseMap::cellToIso)
         | int cấp @0x68 | int vàng @0x74 | int dầu @0x78 | int dầu đen @0x7c | int @0x328
         (vàng/dầu/dầu đen: BuildingResource::onDealDamage cộng vào chiến lợi phẩm qua BattleMgr::addMoney)
Tiếp theo: int số loại LÍNH CỦA NGƯỜI ĐÁNH, mỗi loại [chuỗi tên][int CẤP @0xc][int SỐ LƯỢNG @0x8]
         (gói @0x30 -> BattleMgr+0xc8, dùng bởi BattleMgr::addTroop và thanh chọn lính BattleTroopGui).
         BattleMgr::addTroopBuy: cùng tên VÀ cùng @0xc thì cộng dồn @0x8 -> @0xc là cấp, @0x8 là số lượng.
         (v5.2 trở về trước gửi ngược -> 20 lính cấp 1 hiện thành 1 lính "cấp 20" không có chỉ số, chết ngay.)
         Gửi rỗng -> vào trận không có lính để thả.
Tiếp theo: QUÂN BANG (@0x40) [int n] n x [chuỗi][byte cấp][short số].
Phó bản (int đầu = 1000 + màn > 1): danh sách lính @0x30 = BẢNG CHỌN của SingleBattleSelectGUI (this+0x208):
         mỗi loại lính đã mở, SỐ LƯỢNG = số đang chọn sẵn (addTroop cộng vào đây, > 0 thì hiện ở hàng trên) -> gửi 0.
         @0x14c = sức chứa (addTroop chặn khi chỗ ở lính > sức chứa - đã chọn).
Sau đó là nhiều danh sách phụ (quân hỗ trợ @0x48, phép @0x38, bẫy, vật phẩm, ...) và 7 double: gửi 0 = rỗng (đã kiểm tra
mọi nhánh số lượng 0 đều bỏ qua).
"""
from .. import gamedata
from ..botbase import MAP_W
from ..protocol.codec import pstr, u8, u16, u32


def build(base, enemy_id, name, th_level, troops=None, troop_levels=None, clan_troops=None, single_capacity=0,
          keep_zero=False, spells=None):
    d = u32(enemy_id) + pstr(name) + u32(th_level) + u32(0) + u8(0) + pstr("") + u32(0) + pstr("") + u32(0)
    d += u32(len(base))
    for b in base:
        lvl = gamedata.display_level(b["type"], b["level"])
        d += (u32(b["id"]) + pstr(b["type"]) + u32(b["y"] * MAP_W + b["x"]) + u32(lvl)
              + u32(b.get("gold", 0)) + u32(b.get("elixir", 0)) + u32(b.get("dark", 0)) + u32(0))
    army = [(t, int(n)) for t, n in sorted((troops or {}).items()) if int(n) > 0 or keep_zero]
    levels = troop_levels or {}
    d += u32(len(army)) + b"".join(pstr(t) + u32(max(1, int(levels.get(t, 1)))) + u32(n) for t, n in army)
    # danh sách @0x40 (BattleMgr+0xd8, getLevelTroop loại 1) = QUÂN BANG: [int n] n x [chuỗi][byte cấp][short số]
    ct = [(t, int(n)) for t, n in sorted((clan_troops or {}).items()) if int(n) > 0]
    d += u32(len(ct)) + b"".join(pstr(t) + u8(max(1, int(levels.get(t, 1)))) + u16(n) for t, n in ct)
    # các trường tới @0x14c/@0x150 (theo readData): quân hỗ trợ @0x48, [int n x int], 7 double, int @0x108,
    # int @0x10c, chuỗi, short @0x110, [int n x (chuỗi,byte,short)] @0x118, [int n x (int,byte)], byte @0x128,
    # [int n x chuỗi] @0x138, byte @0x148, double @0xf8, double @0x100,
    # int @0x14c = SỨC CHỨA LÍNH PHÓ BẢN, byte @0x150 = sức chứa phép (SingleBattleSelectGUI::initData)
    d += u32(0) + u32(0) + bytes(8 * 7) + u32(0) + u32(0) + pstr("") + u16(0) + u32(0) + u32(0) + u8(0)
    d += u32(0) + u8(0) + bytes(16) + u32(single_capacity) + u8(0)
    # sau @0x150: [byte n] (byte, doubleA, chuỗi) x2 (dòng trang bị), [byte n] (int, chuỗi), [byte n] (chuỗi, byte),
    # rồi PHÉP MANG VÀO TRẬN @0x38: [byte n] n x [chuỗi phép][byte cấp @0xc][byte số @8]
    sp = [(s, int(n)) for s, n in sorted((spells or {}).items()) if int(n) > 0]
    lv = troop_levels or {}
    d += u8(0) + u8(0) + u8(0) + u8(0)
    d += u8(len(sp)) + b"".join(pstr(s) + u8(max(1, int(lv.get(s, 1)))) + u8(n & 0xFF) for s, n in sp)
    return d + bytes(2048)
