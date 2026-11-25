"""BuildingInfo (cmd 1002) - theo CmdReceiveBuildingInfo::readData.

Thứ tự: nhà chính, trại lính, trại quân, CẤP LÍNH, phòng thí nghiệm, mỏ, kho,
phòng thủ, tường, lâu đài bang, nhà thợ xây, bẫy, bia mộ, chướng ngại, nhà phép, phép, TRANG TRÍ, NHÀ ANH HÙNG (KQB), ...
(mỗi nhóm: u16 số lượng).
Đối tượng chung: int id | chuỗi loại | double@0x40 (giờ xong) | double@0x58 | byte TRẠNG THÁI@0x68
                 | byte cấp@0x28 | byte x | byte y | double@0x60 | short@0xa2 | int@0xa4
Trạng thái @0x68 (suy từ GameDataMgr::refreshBuilderList / getTotalResourceStorage / setSelectedBuilding):
  1 = đang xây, 2 = BÌNH THƯỜNG (có nút nâng cấp, kho được tính), 3 = đang nâng cấp.
  Gửi 0 (bản cũ) làm công trình không có nút nâng cấp và kho không được tính.
"""
from .. import clans, config, gamedata, state
from ..protocol.codec import f64, pstr, u8, u16, u32

STATE_NORMAL = 2
TAIL = bytes(8) + u16(0) + u32(0)


def _head(b):
    lvl = gamedata.display_level(b["type"], b["level"])
    return (u32(b["id"]) + pstr(b["type"]) + bytes(16)
            + bytes([STATE_NORMAL, lvl & 0xFF, b["x"] & 0xFF, b["y"] & 0xFF]))


def _hero_hp(b):
    hp = gamedata.HERO_HP.get(b["type"], {})
    # cấp anh hùng = cấp nhà anh hùng (CityKingQueen::setInfo đọc byte cấp @0x28 của công trình)
    return int(hp.get(str(b.get("level", 1)), hp.get("1", 0))) & 0x7FFF


def _clan_troops(st, count_fn):
    ct = [(t, int(n)) for t, n in sorted(st.get("clan_troops", {}).items()) if int(n) > 0]
    lv = st.get("troop_levels", {})
    return count_fn(len(ct)) + b"".join(pstr(t) + u8(max(1, int(lv.get(t, 1)))) + u16(n) for t, n in ct)


def build(st, account=None):
    account = account or st.get("_account") or state.DEFAULT_ACCOUNT
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
    # CẤP LÍNH (nghiên cứu): [short n] n x [chuỗi lính][byte cấp] -> vector DataResearchStruct mà
    # GameDataMgr::getTroopLevel đọc (phòng thí nghiệm, lính trong trại, thanh chọn lính, chỉ số khi đánh).
    # Bản cũ gửi 0 -> sau mỗi lần tải lại làng (về nhà sau trận, vào lại game) mọi lính về cấp 1.
    lv = [(t, int(l)) for t, l in sorted(st.get("troop_levels", {}).items()) if int(l) > 1]
    data += u16(len(lv)) + b"".join(pstr(t) + u8(l & 0xFF) for t, l in lv)
    lab = groups.get("lab")
    if lab:                                                 # phòng thí nghiệm: cờ 1 + đối tượng
        data += u16(1) + _head(lab[0]) + pstr("") + u16(0) + u32(0) + TAIL
    else:
        data += u16(0)
    data += lst("resources") + lst("storage") + lst("defense")
    walls = groups.get("wall", [])                          # tường: [int id][chuỗi loại][byte cấp][byte x][byte y]
    data += u16(len(walls)) + b"".join(                     #  (trạng thái @0x68 game tự đặt)
        u32(w["id"]) + pstr(w["type"]) + bytes([gamedata.display_level(w["type"], w["level"]) & 0xFF,
                                                w["x"] & 0xFF, w["y"] & 0xFF]) for w in walls)
    clc = groups.get("clancastle")                          # lâu đài bang: cờ 1 + đối tượng + phần thêm
    if clc:                                                 # (game mặc định ai cũng có; thiếu -> mở luyện quân
        data += (u16(1) + _head(clc[0]) + TAIL              #  sập ở ClanCastleObject::getTotalTroopClan)
                 + bytes(8)                                 # double@0x248
                 + u8(0)                                    # byte
                 + _clan_troops(st, u16))                   # QUÂN BANG: [short n] n x [chuỗi][byte cấp][short số]
    else:
        data += u16(0)
    # ĐANG Ở BANG (GameDataMgr+0x318 = id bang từ GetPlayerInfo > 0): readData đọc thêm
    # [byte biểu tượng bang -> +0x328][chuỗi tên bang -> +0x320] ngay sau lâu đài bang.
    # Thiếu 2 trường này -> mọi danh sách sau bị lệch -> chướng ngại sai tên ảnh -> game sập (Avatar::changeFrame).
    clan = clans.clan_of(account)
    if clan:
        data += u8(clan["icon"]) + pstr(clan["name"])
    huts = groups.get("builderhut", [])                     # nhà thợ xây: id, tên, x, y, int, chuỗi, double
    data += u16(len(huts)) + b"".join(u32(h["id"]) + pstr(h["type"]) + bytes([h["x"] & 0xFF, h["y"] & 0xFF])
                                      + u32(0) + pstr("") + bytes(8) for h in huts)
    data += lst("trap")                                     # bẫy
    data += u16(0)                                          # bia mộ (RIP): 0
    obs = st.get("obstacles", []) if config.USE_OBB else []
    data += u16(len(obs)) + b"".join(u32(o["id"]) + pstr(o["type"]) + bytes(8)
                                     + bytes([o["x"] & 0xFF, o["y"] & 0xFF]) for o in obs)
    spf = groups.get("spellfactory")                        # NHÀ PHÉP: [short cờ] + đối tượng chung (không TAIL)
    if spf:                                                 #  + hàng đợi [short n] n x [chuỗi phép][short số]
        q = [(s, int(n)) for s, n in st.get("spell_queue", []) if int(n) > 0]   # + double@0x60 short@0xa2 int@0xa4
        h = _head(spf[0])                                   # @0x40 = GIỜ BẮT ĐẦU CHẾ (getStartTrainTime, giây)
        h = h[:4 + 2 + len(spf[0]["type"])] + f64(int(st.get("spell_start") or 0)) + h[4 + 2 + len(spf[0]["type"]) + 8:]
        data += (u16(1) + h + u16(len(q)) + b"".join(pstr(s) + u16(n) for s, n in q) + TAIL)
    else:
        data += u16(0)
    sp = [(s, int(n)) for s, n in sorted(st.get("spells", {}).items()) if int(n) > 0]
    data += u16(len(sp)) + b"".join(pstr(s) + u8(n & 0xFF) for s, n in sp)   # PHÉP ĐÃ CÓ -> GameDataMgr+0x88
    decos = groups.get("decoration", [])                    # trang trí (DecorationObject): id, loại, double
    data += u16(len(decos)) + b"".join(                     #  giờ bắt đầu @0x40 (giây), byte trạng thái @0x68,
        u32(d["id"]) + pstr(d["type"]) + f64(d.get("placed_at", 0))   # byte cấp, x, y, @0x1a8, @0x1ac,
        + bytes([STATE_NORMAL, 1, d["x"] & 0xFF, d["y"] & 0xFF, 0, 0])  # số ngọc khảm (mỗi viên 3 byte)
        + u8(0) for d in decos)                             # còn hạn = giờ bắt đầu + time > giờ hiện tại
    kqbs = groups.get("kqbarrack", [])                      # nhà anh hùng (KQBarrack): đối tượng chung + double@0x60
    data += u16(len(kqbs)) + b"".join(                      #  + short máu anh hùng @0x1e8 + double@0x1f0 (giờ hồi máu)
        _head(k) + bytes(8) + u16(_hero_hp(k)) + bytes(8)    #  + bool@0x1f8 ANH HÙNG SẴN SÀNG + short@0xa2 + int@0xa4.
        + u8(1) + u16(0) + u32(0) for k in kqbs)            #  Có 4 danh sách KQBarrack, cùng đổ vào 1 vector.
    # bool@0x1f8: CityMgr::createKingQueenOnCity -> CityKingQueen::setInfo(..., cờ): 1 = guard() (canh gác),
    # khác 1 = sleep() (đi về bệ ngủ -> BaseMap::pathTo). Gửi 0 (bản <= 7.2) -> huỷ "Sắp xếp làng" dựng lại anh hùng
    # khi bản đồ tìm đường chưa sẵn -> AStar::findShortestPath đọc nút đích rỗng -> văng.
    return data + bytes(1024)                               # các danh sách sau: 0
