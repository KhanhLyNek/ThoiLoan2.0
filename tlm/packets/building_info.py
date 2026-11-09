"""BuildingInfo (cmd 1002) - theo CmdReceiveBuildingInfo::readData.

Thứ tự: nhà chính, trại lính, trại quân, quân trong trại, phòng thí nghiệm, mỏ, kho,
phòng thủ, tường, lâu đài bang, nhà thợ xây, bẫy, bia mộ, chướng ngại, ... (mỗi nhóm: u16 số lượng).
Đối tượng chung: int id | chuỗi loại | double@0x40 (giờ xong) | double@0x58 | byte TRẠNG THÁI@0x68
                 | byte cấp@0x28 | byte x | byte y | double@0x60 | short@0xa2 | int@0xa4
Trạng thái @0x68 (suy từ GameDataMgr::refreshBuilderList / getTotalResourceStorage / setSelectedBuilding):
  1 = đang xây, 2 = BÌNH THƯỜNG (có nút nâng cấp, kho được tính), 3 = đang nâng cấp.
  Gửi 0 (bản cũ) làm công trình không có nút nâng cấp và kho không được tính.
"""
from .. import config, gamedata
from ..protocol.codec import pstr, u16, u32

STATE_NORMAL = 2
TAIL = bytes(8) + u16(0) + u32(0)


def _head(b):
    lvl = gamedata.display_level(b["type"], b["level"])
    return (u32(b["id"]) + pstr(b["type"]) + bytes(16)
            + bytes([STATE_NORMAL, lvl & 0xFF, b["x"] & 0xFF, b["y"] & 0xFF]))


def build(st):
    groups = {}
    for b in st["buildings"]:
        groups.setdefault(gamedata.CATEGORY.get(b["type"][:3]), []).append(b)

    def lst(cat, extra=b""):
        items = groups.get(cat, [])
        return u16(len(items)) + b"".join(_head(b) + extra + TAIL for b in items)

    th = (groups.get("townhall") or [{"id": 1, "type": "TOW_1", "x": 20, "y": 19, "level": 1}])[0]
    data = u16(1) + _head(th) + TAIL                       # nhà chính
    data += lst("barrack", extra=u16(0))                    # trại lính (+ hàng đợi rỗng)
    data += lst("armycamp")                                 # trại quân
    data += u16(0)                                          # quân trong trại
    lab = groups.get("lab")
    if lab:                                                 # phòng thí nghiệm: cờ 1 + đối tượng
        data += u16(1) + _head(lab[0]) + pstr("") + u16(0) + u32(0) + TAIL
    else:
        data += u16(0)
    data += lst("resources") + lst("storage") + lst("defense")
    data += u16(0)                                          # tường: chưa hỗ trợ
    data += u16(0)                                          # lâu đài bang: chưa hỗ trợ
    huts = groups.get("builderhut", [])                     # nhà thợ xây: id, tên, x, y, int, chuỗi, double
    data += u16(len(huts)) + b"".join(u32(h["id"]) + pstr(h["type"]) + bytes([h["x"] & 0xFF, h["y"] & 0xFF])
                                      + u32(0) + pstr("") + bytes(8) for h in huts)
    data += lst("trap")                                     # bẫy
    data += u16(0)                                          # bia mộ (RIP): 0
    obs = st.get("obstacles", []) if config.USE_OBB else []
    data += u16(len(obs)) + b"".join(u32(o["id"]) + pstr(o["type"]) + bytes(8)
                                     + bytes([o["x"] & 0xFF, o["y"] & 0xFF]) for o in obs)
    return data + bytes(1024)                               # các danh sách sau: 0
