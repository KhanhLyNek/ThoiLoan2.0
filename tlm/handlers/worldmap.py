"""CỔNG THẾ GIỚI: thông tin đảo (14001), đánh chiếm đảo (9017), thu hoạch uranium (14003). Dữ liệu: tlm/worldmap.py.

14001 (game gửi khi mở bản đồ, không dữ liệu) -> WorldMapMgr::onReceiveIslandMapInfo:
  [int -> WorldMapMgr+0x40][int n] n x DataIsland:
      [int id @0][double GIỜ THU HOẠCH @0x10][int UID CHỦ ĐẢO @8][int UID ĐANG GIỮ @0x18]
      [chuỗi TÊN CHỦ @0x20][chuỗi tên người đang đánh @0x28][short ẢNH BANG @0x34][chuỗi TÊN BANG @0x38][bool cần giúp @0x40]
  [int số lần giúp -> WorldMapMgr+0x44] rồi n x [int id][double @0x48] (id PHẢI có trong danh sách trên, không thì sập).
  IslandObject::checkState: id 0 = đảo nhà; uid chủ 0 = đảo trống; uid chủ = GameDataMgr+0xd0 (userId của mình)
  và = uid đang giữ -> trạng thái 2 = ĐẢO CỦA MÌNH (viền xanh, hiện tên, thu hoạch được); chủ khác -> 3 (hiện tên chủ);
  uid đang giữ khác chủ -> 4/5 (đang bị chiếm, viền đỏ).
Đảo TRỐNG: AttackIslandGui::sendAttackIsland -> sendFindMatch = 9001 [int 0][int 1|2][int id đảo] (bản <= 7.6 tưởng
  là chinh phạt thường -> đánh xong không chiếm được đảo). Đảo CÓ CHỦ: 9017 ServerCommunication::sendAttackOccupy
  [int uid đang giữ đảo][int id đảo][int 1|2]. Cả hai trả BattleInfo (cmd 9001, CityMgr đã ở trạng thái 10 = đánh đảo). Kết thúc trận (9003) >= 1 sao -> chiếm đảo (handlers/battle.py).
14003 ServerCommunication::sendHarvestUrainum: [int id đảo] -> WorldMapMgr::onReceiveHarvestUranium:
  [int -> WorldMapMgr+0x40][int id đảo][double giờ thu hoạch mới -> IslandObject+0x138]; kèm 1040 [int tổng uranium]
  (-> GameDataMgr+0x118, số uranium hiển thị).
"""
import time

from .. import botbase, clans, state, worldmap
from ..protocol.codec import Reader, f64, pstr, u16, u32, u8
from . import handler
from .battle import real_base, start_battle


def island_info(account):
    isl = worldmap.load()
    n = worldmap.num_islands(account)
    now = int(time.time())
    rows, times = [], []
    for iid in range(n + 1):
        rec = isl.get(str(iid)) if iid else None
        if rec:
            uid = int(rec["uid"])
            rows.append(u32(iid) + f64(int(rec.get("harvest", now))) + u32(uid) + u32(uid) + pstr(rec.get("name", ""))
                        + pstr("") + u16(int(rec.get("clan_icon", 0)) if rec.get("clan_name") else 0)
                        + pstr(rec.get("clan_name", "")) + u8(0))
            times.append(u32(iid) + f64(int(rec.get("since", now))))
        else:
            rows.append(u32(iid) + f64(0) + u32(0) + u32(0) + pstr("") + pstr("") + u16(0) + pstr("") + u8(0))
            times.append(u32(iid) + f64(0))
    d = u32(0) + u32(len(rows)) + b"".join(rows) + u32(0) + b"".join(times)
    owned = sum(1 for k, v in isl.items() if int(k) <= n and v.get("acc") == account)
    return d, n, owned, sum(1 for k in isl if int(k) <= n)


@handler(14001)
def map_info(ctx, ctl, cmd, payload):
    st = state.load(ctx.account)
    worldmap.refresh_names(ctx.account, st)
    d, n, mine, total = island_info(ctx.account)
    ctx.reply(ctl, 14001, 0, d, "GỬI cmd=14001 bản đồ đảo: %d đảo, %d đảo có chủ, của bạn %d" % (n, total, mine))
    return True


@handler(9017)
def attack_island(ctx, ctl, cmd, payload):
    """Đánh đảo ĐÃ CÓ CHỦ (OccupyIslandGui). Đảo trống đi đường 9001 [0][1|2][id đảo] (handlers/battle.py)."""
    r = Reader(payload)
    holder, iid = r.u32(), r.u32()
    return start_island(ctx, ctl, iid, 9001)


def start_island(ctx, ctl, iid, reply_cmd):
    st = state.load(ctx.account)
    rec = worldmap.load().get(str(iid))
    player_th = next((b["level"] for b in st["buildings"] if b["type"] == "TOW_1"), 1)
    owner = rec.get("acc") if rec else None
    if owner and owner != ctx.account:
        try:
            vst = state.load(owner)
            base, name = real_base(vst), str(vst["player"].get("name", owner))
            th = next((b["level"] for b in vst["buildings"] if b["type"] == "TOW_1"), 1)
        except Exception:
            owner = None
    if not owner or owner == ctx.account:
        import random
        base, name, th, _ = botbase.random_enemy(player_th, random.Random(iid * 7919 + player_th))
        name = "Đảo %d" % iid
    for b in base:                                  # đánh đảo để giành đảo + uranium, không cướp tài nguyên
        b["gold"] = b["elixir"] = b["dark"] = 0
    ctx.battle = {"kind": "island", "island": iid, "dropped": {}}
    enemy_id = clans.uid_of(owner) if owner else 800000 + iid
    return start_battle(ctx, ctl, reply_cmd, st, base, name, th, enemy_id,
                        "ĐÁNH CHIẾM ĐẢO %d (%s)" % (iid, "chủ: %s" % rec["name"] if rec else "đảo trống"))


def on_battle_end(ctx, battle, stars):
    """Gọi từ handlers/battle.py khi trận đánh đảo kết thúc."""
    iid = battle["island"]
    if stars <= 0:
        return ", không chiếm được đảo %d" % iid
    st = state.load(ctx.account)
    old, dropped = worldmap.capture(ctx.account, st, iid)
    note = ", CHIẾM ĐẢO %d%s" % (iid, (" (của %s)" % old) if old else "")
    if dropped:
        note += ", bỏ đảo %s (vượt giới hạn %d đảo)" % (", ".join(map(str, dropped)), worldmap.max_owner(ctx.account))
    return note


@handler(14003)
def harvest(ctx, ctl, cmd, payload):
    iid = int.from_bytes(payload[0:4], "big") if len(payload) >= 4 else 0
    st = state.load(ctx.account)
    res = worldmap.harvest(ctx.account, st, iid)
    if res is None:
        ctx.reply(ctl, 14003, 1, b"", "GỬI cmd=14003 lỗi: đảo %d không phải của bạn" % iid)
        return True
    gain, total, now, amount = res
    state.save(st, ctx.account)
    pct, cap = worldmap.kqb3(st)
    ctx.reply(ctl, 14003, 0, u32(0) + u32(iid) + f64(now),
              "GỬI cmd=14003 thu hoạch đảo %d: đảo sản xuất %d, bạn nhận %d uranium (%d%%, kho %d/%d)"
              % (iid, amount, gain, pct, total, cap) + ("" if pct else " - CHƯA XÂY KHO URANIUM (KQB_3)"))
    ctx.reply(ctl, 1040, 0, u32(total), "GỬI cmd=1040 tổng uranium = %d" % total)
    return True
