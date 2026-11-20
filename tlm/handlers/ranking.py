"""Bảng xếp hạng + cúp.

Mỗi dòng (UserInfoStruct): [int uid][int cấp @0x30][int CÚP @0x34][chuỗi tên][int id bang @0x80]
                           [chuỗi tên bang][byte biểu tượng bang @0x90][int @0xfc][int @0x100]
1016 sendGetRank([byte loại]) -> CmdReceiveRanking: [byte loại @0x34][byte n] + n x (dòng + [byte @0x104])
     loại 0 -> RankTab::setRankListTrophy, khác 0 -> setRankListLevel.
1046 sendGetTopTrophyBoard([byte]) -> CmdReceiveTopTrophyBoard: [byte n] n x dòng (tuần này)
     + [byte n] n x dòng (tuần trước) -> TopTrophyTab::setThisWeek / setLastWeek.
Cúp người chơi = player["trophy"] -> GetPlayerInfo @0x5c (UserInfoStruct @0x34). Cộng/trừ khi đánh trận.
"""
from .. import clans, state
from ..protocol.codec import pstr, u8, u32
from . import handler

TOP = 50


def all_rows():
    rows = []
    for acc in state.list_accounts():
        try:
            p = state.load(acc)["player"]
        except Exception:
            continue
        c = clans.clan_of(acc)
        rows.append({"uid": clans.uid_of(acc), "level": int(p.get("level", 1)), "trophy": int(p.get("trophy", 0)),
                     "name": str(p.get("name", acc)), "cid": c["id"] if c else 0, "cname": c["name"] if c else "",
                     "icon": c["icon"] if c else 0})
    for c in clans.db()["clans"].values():          # thành viên máy của các bang có sẵn
        for m in c["members"]:
            if not m.get("account"):
                rows.append({"uid": m["uid"], "level": m["level"], "trophy": m["trophy"], "name": m["name"],
                             "cid": c["id"], "cname": c["name"], "icon": c["icon"]})
    return rows


def _row(r):
    return (u32(r["uid"]) + u32(r["level"]) + u32(r["trophy"]) + pstr(r["name"]) + u32(r["cid"])
            + pstr(r["cname"]) + u8(r["icon"]) + u32(0) + u32(0))


@handler(1016)
def get_rank(ctx, ctl, cmd, payload):
    kind = payload[0] if payload else 0
    rows = sorted(all_rows(), key=lambda r: -(r["trophy"] if kind == 0 else r["level"] * 100000 + r["trophy"]))[:TOP]
    ctx.reply(ctl, cmd, 0, u8(kind) + u8(len(rows)) + b"".join(_row(r) + u8(0) for r in rows) + bytes(32),
              "GỬI cmd=1016 bảng xếp hạng %s: %d người" % ("cúp" if kind == 0 else "cấp", len(rows)))
    return True


@handler(1046)
def top_trophy_board(ctx, ctl, cmd, payload):
    rows = sorted(all_rows(), key=lambda r: -r["trophy"])[:TOP]
    body = u8(len(rows)) + b"".join(_row(r) for r in rows)
    ctx.reply(ctl, cmd, 0, body + body + bytes(32), "GỬI cmd=1046 bảng cúp tuần: %d người" % len(rows))
    return True


def change_trophy(st, delta):
    p = st["player"]
    p["trophy"] = max(0, int(p.get("trophy", 0)) + int(delta))
    return p["trophy"]
