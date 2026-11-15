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
Sau đó là nhiều danh sách phụ (phép, quân bang, bẫy, vật phẩm, ...) và 7 double: gửi 0 = rỗng (đã kiểm tra
mọi nhánh số lượng 0 đều bỏ qua).
"""
from .. import gamedata
from ..botbase import MAP_W
from ..protocol.codec import pstr, u8, u32


def build(base, enemy_id, name, th_level, troops=None, troop_levels=None):
    d = u32(enemy_id) + pstr(name) + u32(th_level) + u32(0) + u8(0) + pstr("") + u32(0) + pstr("") + u32(0)
    d += u32(len(base))
    for b in base:
        lvl = gamedata.display_level(b["type"], b["level"])
        d += (u32(b["id"]) + pstr(b["type"]) + u32(b["y"] * MAP_W + b["x"]) + u32(lvl)
              + u32(b.get("gold", 0)) + u32(b.get("elixir", 0)) + u32(b.get("dark", 0)) + u32(0))
    army = [(t, int(n)) for t, n in sorted((troops or {}).items()) if int(n) > 0]
    levels = troop_levels or {}
    d += u32(len(army)) + b"".join(pstr(t) + u32(max(1, int(levels.get(t, 1)))) + u32(n) for t, n in army)
    return d + bytes(2048)
