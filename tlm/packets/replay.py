"""Gói nhật ký trận (9047 ReplayBattleList) và dữ liệu xem lại (9011 ReplayBattleInfo).

9047 CmdReceiveReplayBattleList::readData:
  [int n] n x LogBattleData  -> ReplayMgr+0x120 = trận PHÒNG THỦ (BattleReportGUI::showDEFHistory)
  [int n] n x LogBattleData  -> ReplayMgr+0x128 = trận TẤN CÔNG  (showATKHistory)
  [int n] n x [chuỗi][chuỗi][int][double][int]   (danh sách phụ, gửi rỗng)
  LogBattleData (0x98 byte, hiển thị bởi BattleReportGUI::setSlotData):
    int id trận @0 (tag nút Xem lại / Trả thù) | int userId đối thủ @4 (gửi kèm lệnh trả thù 9013)
    chuỗi tên đối thủ @8 | chuỗi tên bang @0x10
    int biểu tượng bang @0x18 (0 = không bang) | int vàng @0x1c | int dầu @0x20 | int dầu đen @0x24
    int cúp đối thủ @0x28 | int cúp được/mất @0x2c | int số sao @0x30 | int % phá @0x34
    double @0x38 | double THỜI ĐIỂM (giây) @0x40 ("... trước") | int @0x4c
    bool HIỆN NÚT XEM LẠI @0x80 | bool HIỆN NÚT TRẢ THÙ @0x81 | 7 x double (bỏ qua)
    [int n] n x [chuỗi lính][int cấp][int số]       lính đã dùng
    [int n] n x [chuỗi lính][byte cấp][short số]    quân bang đã dùng
    byte, byte, byte

9011 CmdReceiveReplayBattleInfo::readData -> ReplayMgr::onGetReplayBattleInfo dựng lại một BattleInfo rồi
  gọi BattleMgr::onGetBattleInfo, sau đó ReplayMgr::dropTroop thả lính theo từng nhịp:
  int id @0x78 | chuỗi tên làng @0x80 | chuỗi @0x88 | int @0xc4 | chuỗi @0xd0 | int @0xc8
  | 7 int (@0x98 @0x9c @0xa0 @0x90 @0x94 @0xa4 @0xa8 = % phá) | double | double
  | int NHỊP KẾT THÚC @0xc0 (ReplayMgr+0x19c, thời lượng = (kết thúc - bắt đầu) / 30 giây)
  | [int n] công trình (giống BattleInfo)
  | [int n] n x [chuỗi lính][int Ô][int CẤP][int NHỊP THẢ]  @0x30/@0x38 = hàng đợi thả lính
        (ReplayMgr::dropTroop: "Clan" = thả quân bang, "SupportTroop" = quân hỗ trợ, còn lại addListTroopDrop)
  | [int n] [chuỗi][int cấp][int số] quân bang @0x40 | [int n] (cùng kiểu) quân hỗ trợ @0x48
  | [int n] x int | 4 double | chuỗi | 3 double | [int n] x [int][byte] | byte | 2 double | [int n] @0x60
  | [byte n] @0x130 | [byte n] @0x138 | [int n] [chuỗi][byte][short] @0x148 (lính đã dùng, màn kết)
  | [int n] @0x140 | [int n] @0x68 | [int n] x [int][byte] | [byte n] | [byte n] | [byte n] @0x70
  | 3 byte | 4 int
"""
from .. import gamedata
from ..botbase import MAP_W
from ..protocol.codec import f64, pstr, u8, u16, u32


def _i32(v):
    return (int(v) & 0xffffffff).to_bytes(4, "big")


def log_entry(e, defense):
    troops = [(t, v) for t, v in sorted((e.get("troops") or {}).items()) if int(v[1]) > 0]
    clan = [(t, v) for t, v in sorted((e.get("clan_troops") or {}).items()) if int(v[1]) > 0]
    loot = (list(e.get("loot") or []) + [0, 0, 0])[:3]
    revenge = bool(defense and e.get("acc") and not e.get("revenged"))
    d = u32(e["id"]) + u32(e.get("uid", 0)) + pstr(e.get("name", "")) + pstr(e.get("clan_name", ""))
    d += u32(e.get("clan_icon", 0) if e.get("clan_name") else 0)
    d += b"".join(u32(max(0, int(x))) for x in loot)
    d += u32(e.get("trophy", 0)) + _i32(e.get("tchange", 0)) + u32(e.get("stars", 0)) + u32(e.get("percent", 0))
    d += f64(e.get("t", 0)) + f64(e.get("t", 0)) + u32(0)
    d += u8(1 if e.get("replay") else 0) + u8(1 if revenge else 0) + bytes(8 * 7)
    d += u32(len(troops)) + b"".join(pstr(t) + u32(max(1, int(v[0]))) + u32(int(v[1])) for t, v in troops)
    d += u32(len(clan)) + b"".join(pstr(t) + u8(max(1, int(v[0]))) + u16(int(v[1])) for t, v in clan)
    return d + u8(0) + u8(0) + u8(0)


def battle_list(defense_log, attack_log):
    """Mới nhất lên đầu (game tự sắp xếp lại bằng ReplayMgr::quicksort)."""
    dl, al = list(reversed(defense_log or [])), list(reversed(attack_log or []))
    d = u32(len(dl)) + b"".join(log_entry(e, True) for e in dl)
    d += u32(len(al)) + b"".join(log_entry(e, False) for e in al)
    return d + u32(0) + bytes(64)


def replay_info(rec):
    loot = (list(rec.get("loot") or []) + [0, 0, 0])[:3]
    d = u32(rec["id"]) + pstr(rec.get("def_name", "")) + pstr(rec.get("att_name", "")) + u32(0) + pstr("") + u32(0)
    d += u32(loot[0]) + u32(loot[1]) + u32(loot[2]) + u32(rec.get("th", 1)) + u32(0) + u32(0)
    d += u32(rec.get("percent", 0)) + f64(0) + f64(0) + u32(rec.get("end_tick", 0))
    base = rec.get("base") or []
    d += u32(len(base))
    for b in base:
        lvl = gamedata.display_level(b["type"], b["level"])
        d += (u32(b["id"]) + pstr(b["type"]) + u32(b["y"] * MAP_W + b["x"]) + u32(lvl)
              + u32(b.get("gold", 0)) + u32(b.get("elixir", 0)) + u32(b.get("dark", 0)) + u32(0))
    acts = sorted(rec.get("actions") or [], key=lambda a: (int(a[3]), int(a[1])))
    d += u32(len(acts)) + b"".join(pstr(t) + u32(cell) + u32(max(1, int(lvl))) + u32(tick) for t, cell, lvl, tick in acts)
    clan = [(t, v) for t, v in sorted((rec.get("clan") or {}).items()) if int(v[1]) > 0]
    d += u32(len(clan)) + b"".join(pstr(t) + u32(max(1, int(v[0]))) + u32(int(v[1])) for t, v in clan)
    d += u32(0)                                             # quân hỗ trợ @0x48
    d += u32(0)                                             # [int n] x int @0xd8
    d += bytes(8 * 4) + pstr("") + bytes(8 * 3)
    d += u32(0) + u8(0) + bytes(8 * 2)                      # [int][byte] list, byte @0x160, 2 double
    d += u32(0) + u8(0) + u8(0)                             # @0x60, @0x130, @0x138
    used = [(t, v) for t, v in sorted((rec.get("used") or {}).items()) if int(v[1]) > 0]
    d += u32(len(used)) + b"".join(pstr(t) + u8(max(1, int(v[0]))) + u16(int(v[1])) for t, v in used)
    d += u32(0) + u32(0) + u32(0) + u8(0) + u8(0) + u8(0)   # @0x140, @0x68, [int][byte], 2 x [byte n], @0x70
    d += u8(0) + u8(0) + u8(0) + u32(0) + u32(0) + u32(0) + u32(0)
    return d + bytes(256)
