"""Quân đội: luyện quân (cmd 11001-11003, phản hồi lớp rTrainTroop).

11001 [int trại][chuỗi lính][short số] -> hàng đợi; 11003 [chuỗi][int số] lính xong -> trại quân.
Phản hồi game cần (nhánh thành công trong ServerCommunication::onReceived):
  [int id trại lính][double giờ xong] -> GameDataMgr::getBuilding(id) rồi gán giờ xong vào trại (@0x40).
  Trả toàn số 0 (bản cũ) -> id 0 không có công trình -> con trỏ rỗng -> game sập.
11002 / 11003 cùng lớp phản hồi (chưa rõ dữ liệu gửi lên): trả lại int đầu tiên game gửi làm id trại.
Số lính đã luyện được ghi vào state["troops"] (giới hạn theo sức chứa trại quân) và gửi lại khi vào game
qua gói TroopInfo (cmd 1003).
"""
import time

from .. import state
from ..data import load_table
from ..protocol.codec import Reader, f64, u32
from . import handler

_GEN = load_table("battle_gen.json")
_TRAIN = load_table("train.json")          # thời gian luyện (giây) + giá dầu/dầu đen theo cấp


def camp_capacity(st):
    """Tổng chỗ trong các trại quân (ArmyCamp.json, capacity theo cấp)."""
    return sum(int(_GEN["camp_capacity"].get(str(b["level"]), 20)) for b in st["buildings"] if b["type"].startswith("AMC"))


def used_space(troops):
    return sum(int(_GEN["housing"].get(t, 1)) * int(n) for t, n in troops.items())


def fit_to_camps(st):
    """Cắt bớt quân vượt sức chứa trại (bản 4.4 chưa giới hạn). Trả về True nếu có thay đổi."""
    troops = st.get("troops", {})
    cap, changed = camp_capacity(st), False
    while troops and used_space(troops) > cap:
        t = max(troops, key=lambda k: int(troops[k]))
        troops[t] = int(troops[t]) - 1
        if troops[t] <= 0:
            del troops[t]
        changed = True
    return changed


def _cost(st, troop, count):
    info = _TRAIN.get(troop, {})
    lvl = str(st.get("troop_levels", {}).get(troop, 1))
    return (int(info.get("elixir", {}).get(lvl, 0)) * count, int(info.get("dark", {}).get(lvl, 0)) * count,
            int(info.get("time", 20)) * count)


def _queue(st, bid):
    return st.setdefault("train_queue", {}).setdefault(str(bid), [])


def _to_camp(st, troop, n):
    troops = st.setdefault("troops", {})
    troops[troop] = int(troops.get(troop, 0)) + int(n)


def settle_training(st):
    """Lúc vào game: trại lính nào đã hết giờ luyện -> chuyển cả hàng đợi vào trại quân."""
    moved = 0
    now = time.time()
    for bid, q in list(st.get("train_queue", {}).items()):
        if q and float(st.get("train_end", {}).get(bid, 0)) <= now:
            for troop, n in q:
                _to_camp(st, troop, n)
                moved += n
            q.clear()
    return moved


def _take(q, troop, n):
    """Bớt n lính loại troop khỏi hàng đợi (từ đầu). Trả về số đã bớt."""
    got = 0
    for item in q:
        if item[0] == troop and got < n:
            k = min(int(item[1]), n - got)
            item[1] = int(item[1]) - k
            got += k
    q[:] = [i for i in q if int(i[1]) > 0]
    return got


@handler(11001, 11002, 11003)
def train_troop(ctx, ctl, cmd, payload):
    """11001 sendTrainTroop [int trại][chuỗi lính][short số]: vào HÀNG ĐỢI (game tự trừ dầu).
    11002 sendCancelTrainTroop [int trại][chuỗi][short số]: bỏ khỏi hàng đợi, hoàn dầu.
    11003 sendFinishTrainTroop [chuỗi lính][int số]: lính luyện xong -> vào TRẠI QUÂN.
    (Bản cũ cộng thẳng vào trại lúc bấm luyện và cắt theo sức chứa lúc đó -> lệch với game.)"""
    st = state.load(ctx.account)
    bid, note = 0, ""
    try:
        r = Reader(payload)
        if cmd in (11001, 11002):
            bid = r.u32(); troop = r.str(); count = r.u16() if r.remaining() >= 2 else 1
            elixir, dark, secs = _cost(st, troop, count)
            ends = st.setdefault("train_end", {})
            if cmd == 11001:
                state.spend(st, elixir=elixir, dark=dark)
                _queue(st, bid).append([troop, count])
                ends[str(bid)] = max(float(ends.get(str(bid), 0)), time.time()) + secs
                note = ": xếp hàng %s x%d (-%d dầu -%d dầu đen)" % (troop, count, elixir, dark)
            else:
                got = _take(_queue(st, bid), troop, count)
                e2, d2, s2 = _cost(st, troop, got)
                state.add_resource(st, "elixir", e2)
                if d2:
                    state.add_resource(st, "dark_elixir", d2)
                ends[str(bid)] = max(time.time(), float(ends.get(str(bid), 0)) - s2)
                note = ": huỷ %s x%d (hoàn %d dầu)" % (troop, got, e2)
        else:
            troop = r.str(); count = r.u32() if r.remaining() >= 4 else 1
            got = 0
            for qb, q in st.get("train_queue", {}).items():
                k = _take(q, troop, count - got)
                if k and not bid:
                    bid = int(qb)
                got += k
            _to_camp(st, troop, max(got, count))
            note = ": xong %s x%d -> trại quân (có %d, %d/%d chỗ)" % (
                troop, count, st["troops"][troop], used_space(st["troops"]), camp_capacity(st))
    except Exception as e:
        note = " (không đọc được dữ liệu: %s)" % e
    state.save(st, ctx.account)
    ctx.log("LUYỆN QUÂN cmd %d trại id=%d%s" % (cmd, bid, note))
    ctx.reply(ctl, cmd, 0, u32(bid) + f64(int(time.time())) + bytes(256), "GỬI cmd=%d rTrainTroop trại id=%d" % (cmd, bid))
    return True
