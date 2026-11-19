"""Bang hội: tạo / tìm / vào / rời / sửa / chức vụ / đuổi / chat.

Định dạng lấy từ libcocos2dcpp.so (7.6.12):
3003 sendCreateClan: [chuỗi tên][byte biểu tượng][byte kiểu][int cúp tối thiểu][chuỗi mô tả]   (game trừ 40000 vàng)
     phản hồi: [int id bang] -> game gán GameDataMgr+0x150 rồi tự gửi 3037.
3004 sendGetClan / 3017 searchClan [chuỗi] -> CmdReceiveClan:
     [int n] + n x [int id][chuỗi tên][byte biểu tượng][byte kiểu][byte số thành viên][int cúp]
              + n x [int id][byte cấp bang]
3037 sendGetClanDetail [int id] -> CmdReceiveClanDetail:
     [int id][chuỗi tên][byte biểu tượng][byte kiểu][int cúp tối thiểu][chuỗi mô tả][int tổng cúp][byte n]
     n x [int uid][byte chức 1/2/3][int cấp][byte 1][int cúp][chuỗi tên][int quân đã cho][int quân đã nhận]
     [chuỗi][int][int][int CẤP BANG >= 1 (tra WorldMap.json "clan"[cấp-1])][double][chuỗi]
     [int n x (int,int,int) urani tuần này][bool][int n x (int,int,int) tuần trước][int][int]
     Game tìm chính mình (uid = GameDataMgr+0xd0) trong danh sách; không thấy -> coi như không có bang.
3005 sendJoinClan [int id][chuỗi lời nhắn]: game tự gán +0x150 = id; phản hồi rỗng; server đẩy 3033 [int id]
     (game gán id bang rồi gửi 3037).
3006 sendLeaveClan: phản hồi rỗng -> MyClanGUI::finishLeave.
3008 sendKickMemberTitle [int uid] -> đẩy 3020 [int uid] (game xoá thành viên).
3009 sendChangeMemberTitle [int uid][byte chức] / 3014 sendEditClan (như 3003) -> đẩy 3033 để tải lại.
4001 sendClanChat [chuỗi] -> đẩy 4002 [int uid][chuỗi][int 0][byte 0] (ChatGui::onGetNewChat).
4003 sendGetClanMsg: trả danh sách rỗng rồi đẩy lại tin cũ bằng 4002.
player_info @0xa8 = id bang (GameDataMgr+0x318) -> lúc vào game tự gửi 3037.
"""
import time

from .. import clans, state
from ..protocol.codec import Reader, f64, pstr, u8, u32
from . import handler

CREATE_GOLD = 40000            # CreateClanGUI::createClan -> CityMgr::useRes(40000 vàng)


def _me(ctx):
    st = state.load(ctx.account)
    p = st["player"]
    return st, clans.uid_of(ctx.account), str(p.get("name", "Khach")), int(p.get("level", 1)), int(p.get("trophy", 0))


def _list(cs):
    d = u32(len(cs))
    for c in cs:
        d += u32(c["id"]) + pstr(c["name"]) + u8(c["icon"]) + u8(c["type"]) + u8(len(c["members"]))
        d += u32(sum(m["trophy"] for m in c["members"]))
    for c in cs:
        d += u32(c["id"]) + u8(c.get("level", 1))
    return d + bytes(32)


def build_detail(c):
    ms = sorted(c["members"], key=lambda m: (m["role"], -m["trophy"]))
    d = u32(c["id"]) + pstr(c["name"]) + u8(c["icon"]) + u8(c["type"]) + u32(c["min_trophy"]) + pstr(c["desc"])
    d += u32(sum(m["trophy"] for m in ms)) + u8(len(ms))
    for m in ms:
        d += u32(m["uid"]) + u8(m["role"]) + u32(m["level"]) + u8(1) + u32(m["trophy"]) + pstr(m["name"])
        d += u32(m.get("donated", 0)) + u32(m.get("received", 0))
    d += pstr("") + u32(0) + u32(0) + u32(max(1, int(c.get("level", 1)))) + f64(0) + pstr("")
    d += u32(0) + u8(0) + u32(0) + u32(0) + u32(0)
    return d + bytes(64)


def _read_info(payload):
    r = Reader(payload)
    return r.str(), r.u8(), r.u8(), r.u32(), r.str()


def push_reload(ctx, ctl, cid):
    ctx.push(ctl, 3033, u32(cid) + bytes(16), " [tải lại bang %d]" % cid)


@handler(3003)
def create_clan(ctx, ctl, cmd, payload):
    try:
        name, icon, ctype, min_trophy, desc = _read_info(payload)
    except Exception as e:
        ctx.log("tạo bang: không đọc được (%s)" % e)
        ctx.reply(ctl, cmd, 1, bytes(16))
        return True
    st, uid, pname, plevel, trophy = _me(ctx)
    gold = state.effective_resources(st)[0]
    st["player"]["gold"] = max(0, gold - CREATE_GOLD)
    state.save(st, ctx.account)
    c = clans.create(ctx.account, uid, pname, plevel, trophy, name, icon, ctype, min_trophy, desc)
    ctx.reply(ctl, cmd, 0, u32(c["id"]) + bytes(16),
              "GỬI cmd=3003 TẠO BANG \"%s\" id=%d (trừ %d vàng)" % (name, c["id"], CREATE_GOLD))
    return True


@handler(3014)
def edit_clan(ctx, ctl, cmd, payload):
    c = clans.clan_of(ctx.account)
    try:
        name, icon, ctype, min_trophy, desc = _read_info(payload)
    except Exception as e:
        ctx.log("sửa bang: không đọc được (%s)" % e)
        c = None
    if c is None:
        ctx.reply(ctl, cmd, 1, bytes(16))
        return True
    c.update(name=name or c["name"], icon=icon, type=ctype, min_trophy=min_trophy, desc=desc)
    clans.save()
    ctx.reply(ctl, cmd, 0, bytes(16), "GỬI cmd=3014 SỬA BANG \"%s\"" % c["name"])
    push_reload(ctx, ctl, c["id"])
    return True


@handler(3004)
def get_clans(ctx, ctl, cmd, payload):
    cs = sorted(clans.search(""), key=lambda c: -len(c["members"]))
    ctx.reply(ctl, cmd, 0, _list(cs), "GỬI cmd=3004 DANH SÁCH %d BANG" % len(cs))
    return True


@handler(3017)
def search_clan(ctx, ctl, cmd, payload):
    try:
        text = Reader(payload).str()
    except Exception:
        text = ""
    cs = clans.search(text)
    ctx.reply(ctl, cmd, 0, _list(cs), "GỬI cmd=3017 TÌM \"%s\": %d bang" % (text, len(cs)))
    return True


@handler(3037)
def clan_detail(ctx, ctl, cmd, payload):
    try:
        cid = Reader(payload).u32()
    except Exception:
        cid = 0
    st, uid, pname, plevel, trophy = _me(ctx)
    clans.refresh_member(ctx.account, pname, plevel, trophy)
    c = clans.get(cid) if cid else clans.clan_of(ctx.account)
    if c is None:
        ctx.reply(ctl, cmd, 1, bytes(16), "GỬI cmd=3037 không có bang id=%d (error 1)" % cid)
        return True
    ctx.reply(ctl, cmd, 0, build_detail(c),
              "GỬI cmd=3037 CHI TIẾT BANG \"%s\" id=%d, %d thành viên" % (c["name"], c["id"], len(c["members"])))
    return True


@handler(3005)
def join_clan(ctx, ctl, cmd, payload):
    try:
        cid = Reader(payload).u32()
    except Exception:
        cid = 0
    st, uid, pname, plevel, trophy = _me(ctx)
    c = clans.join(ctx.account, uid, pname, plevel, trophy, cid)
    if c is None:
        ctx.reply(ctl, cmd, 1, bytes(16), "GỬI cmd=3005 không vào được bang id=%d" % cid)
        return True
    ctx.reply(ctl, cmd, 0, bytes(16), "GỬI cmd=3005 VÀO BANG \"%s\" id=%d" % (c["name"], cid))
    push_reload(ctx, ctl, cid)
    return True


@handler(3006)
def leave_clan(ctx, ctl, cmd, payload):
    c = clans.leave(ctx.account)
    ctx.reply(ctl, cmd, 0, bytes(16), "GỬI cmd=3006 RỜI BANG %s" % (("\"%s\"" % c["name"]) if c else "(không có)"))
    return True


def _my_rank(ctx):
    c = clans.clan_of(ctx.account)
    if c is None:
        return None, None
    return c, clans.member(c, account=ctx.account)


@handler(3008)
def kick_member(ctx, ctl, cmd, payload):
    try:
        target = Reader(payload).u32()
    except Exception:
        target = 0
    c, me = _my_rank(ctx)
    m = clans.member(c, uid=target) if c else None
    if m is None or me["role"] > 2 or m["role"] <= me["role"]:
        ctx.reply(ctl, cmd, 1, bytes(16), "GỬI cmd=3008 không được đuổi uid=%d" % target)
        return True
    c["members"].remove(m)
    clans.save()
    ctx.reply(ctl, cmd, 0, bytes(16), "GỬI cmd=3008 ĐUỔI %s khỏi bang" % m["name"])
    ctx.push(ctl, 3020, u32(target) + bytes(16), " [%s rời bang]" % m["name"])
    return True


@handler(3009)
def change_title(ctx, ctl, cmd, payload):
    try:
        r = Reader(payload)
        target, role = r.u32(), r.u8()
    except Exception:
        target, role = 0, 0
    c, me = _my_rank(ctx)
    m = clans.member(c, uid=target) if c else None
    if m is None or me["role"] != 1 or role not in (1, 2, 3):
        ctx.reply(ctl, cmd, 1, bytes(16), "GỬI cmd=3009 không đổi được chức uid=%d" % target)
        return True
    if role == 1:                       # nhường bang chủ
        me["role"] = 2
    m["role"] = role
    clans.save()
    ctx.reply(ctl, cmd, 0, bytes(16), "GỬI cmd=3009 %s -> chức %d" % (m["name"], role))
    push_reload(ctx, ctl, c["id"])
    return True


def _chat_frame(uid, msg):
    return u32(uid) + pstr(msg) + u32(0) + u8(0) + bytes(16)


@handler(4001)
def clan_chat(ctx, ctl, cmd, payload):
    try:
        msg = Reader(payload).str()
    except Exception:
        msg = ""
    c = clans.clan_of(ctx.account)
    ctx.reply(ctl, cmd, 0, bytes(16), "GỬI cmd=4001 chat bang")
    if c is None or not msg:
        return True
    uid = clans.uid_of(ctx.account)
    c.setdefault("chat", []).append({"uid": uid, "msg": msg, "t": int(time.time())})
    del c["chat"][:-clans.CHAT_KEEP]
    clans.save()
    ctx.push(ctl, 4002, _chat_frame(uid, msg), " [chat: %s]" % msg)
    return True


@handler(4003)
def get_clan_msg(ctx, ctl, cmd, payload):
    # [byte n tin=0][double][byte n=0] + đệm 0
    ctx.reply(ctl, cmd, 0, bytes(128), "GỬI cmd=4003 lịch sử chat (đẩy lại bằng 4002)")
    c = clans.clan_of(ctx.account)
    if c:
        for m in c.get("chat", [])[-20:]:
            ctx.push(ctl, 4002, _chat_frame(m["uid"], m["msg"]), "")
    return True


@handler(3002)
def request_troop(ctx, ctl, cmd, payload):
    ctx.log("xin quân bang hội (chưa có ai cho quân - chỉ trả lời thành công)")
    return False
