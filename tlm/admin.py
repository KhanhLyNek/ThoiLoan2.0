"""Trang quản trị web: http://127.0.0.1:8080/admin

- Danh sách tài khoản và tài nguyên.
- Sửa một tài khoản: tên, cấp, kinh nghiệm, 4 loại tài nguyên (đặt giá trị hoặc cộng thêm),
  tiến độ hướng dẫn, cấp từng công trình, xoá công trình.
Thay đổi có hiệu lực khi game xin lại dữ liệu: bấm "Về nhà" hoặc thoát game vào lại.
"""
import html
import time
import urllib.parse

from . import gamedata, state

RES = [("gold", "Vàng"), ("elixir", "Dầu hồng"), ("dark_elixir", "Dầu đen"), ("coin", "G")]
CSS = """
body{font-family:system-ui,sans-serif;margin:0;background:#f4f1ea;color:#222}
header{background:#7a4b16;color:#fff;padding:12px 16px}header a{color:#ffe7b3}
main{padding:12px;max-width:960px;margin:auto}
table{border-collapse:collapse;width:100%;background:#fff;margin:8px 0}
th,td{border:1px solid #ddd;padding:6px;text-align:left;font-size:14px}th{background:#efe4d0}
input[type=number],input[type=text]{width:100%;box-sizing:border-box;padding:6px;font-size:15px}
.box{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px;margin:10px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}
button{background:#2e7d32;color:#fff;border:0;border-radius:6px;padding:10px 18px;font-size:16px}
.msg{background:#e8f5e9;border:1px solid #81c784;padding:10px;border-radius:6px}
.warn{color:#b26a00;font-size:13px}.small{font-size:12px;color:#666}
"""


def _page(title, body):
    doc = ("<!doctype html><html lang='vi'><head><meta charset='utf-8'>"
           "<meta name='viewport' content='width=device-width,initial-scale=1'>"
           "<title>%s</title><style>%s</style></head><body><header><b>Thời Loạn - Quản trị</b> · "
           "<a href='/admin'>Tài khoản</a></header><main>%s</main></body></html>") % (html.escape(title), CSS, body)
    return 200, "text/html; charset=utf-8", doc.encode("utf-8"), None


def _fmt(n):
    return "{:,}".format(int(n)).replace(",", ".")


def _list_page():
    rows = []
    for key in state.list_accounts():
        st = state.load(key)
        p = st["player"]
        gold, elixir, dark, coin, _ = state.effective_resources(st)
        rows.append("<tr><td><a href='/admin/edit?acc=%s'>%s</a></td><td>%s</td><td>%s</td>"
                    "<td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%d</td></tr>" % (
                        urllib.parse.quote(key), html.escape(key), html.escape(str(p.get("name", ""))),
                        p.get("level", 1), _fmt(gold), _fmt(elixir), _fmt(dark), _fmt(coin), len(st["buildings"])))
    body = ("<h2>Tài khoản</h2><p class='small'>Mỗi nút đăng nhập (google/facebook/zalo) trên mỗi máy là một "
            "tài khoản. Tài khoản xuất hiện sau lần đăng nhập đầu tiên.</p>"
            "<table><tr><th>Tài khoản</th><th>Tên</th><th>Cấp</th><th>Vàng</th><th>Dầu hồng</th>"
            "<th>Dầu đen</th><th>G</th><th>Công trình</th></tr>%s</table>") % (
                "".join(rows) or "<tr><td colspan=8>Chưa có tài khoản nào. Mở game đăng nhập trước.</td></tr>")
    return _page("Tài khoản", body)


def _edit_page(key, msg=""):
    st = state.load(key)
    p = st["player"]
    cg, ce, cd = state.capacities(st)
    caps = {"gold": cg, "elixir": ce, "dark_elixir": cd, "coin": None}
    q = html.escape
    res_cells = []
    for k, label in RES:
        cap = caps[k]
        res_cells.append(
            "<div><b>%s</b><br><span class='small'>đang lưu: %s%s</span>"
            "<br>Đặt bằng<input type=number name='set_%s' value='%s' min=0>"
            "Cộng thêm<input type=number name='add_%s' placeholder='0'></div>" % (
                label, _fmt(p.get(k, 0)), (" · sức chứa %s" % _fmt(cap)) if cap is not None else "",
                k, int(p.get(k, 0)), k))
    brows = []
    for i, b in enumerate(st["buildings"]):
        maxlv = max([int(x) for x in gamedata.COST.get(b["type"], {})] or [b["level"]])
        brows.append("<tr><td>%s</td><td>%d</td><td>(%d,%d)</td><td><input type=number name='lv_%d' value='%d' "
                     "min=1 max=%d></td><td><input type=checkbox name='del_%d'></td></tr>" % (
                         q(b["type"]), b["id"], b["x"], b["y"], i, b["level"], maxlv, i))
    body = (("<div class='msg'>%s</div>" % q(msg)) if msg else "") + """
<h2>%s</h2>
<form method=post action='/admin/save'>
<input type=hidden name=acc value='%s'>
<div class=box><div class=grid>
<div><b>Tên</b><input type=text name=name value='%s' maxlength=20></div>
<div><b>Cấp</b><input type=number name=level value='%d' min=1 max=300></div>
<div><b>Kinh nghiệm</b><input type=number name=exp value='%d' min=0></div>
<div><b>Hướng dẫn</b><input type=number name=tutorial_step value='%d' min=0 max=200>
<span class=small>70 = đã xong</span></div>
</div></div>
<div class=box><h3>Tài nguyên</h3><div class=grid>%s</div>
<p class=warn>Vàng, dầu hồng, dầu đen hiện trong game tối đa bằng SỨC CHỨA (nhà chính + kho). Lưu số lớn hơn vẫn
được, game sẽ hiện tới mức sức chứa và tự nhận thêm khi bạn xây hoặc nâng kho.</p></div>
<div class=box><h3>Công trình</h3><table><tr><th>Loại</th><th>id</th><th>Vị trí</th><th>Cấp</th><th>Xoá</th></tr>
%s</table><p class=small>Chướng ngại còn lại: %d</p></div>
<button type=submit>Lưu</button>
<p class=small>Sau khi lưu: trong game bấm <b>Về nhà</b> hoặc thoát vào lại để thấy thay đổi.</p>
</form>""" % (q(key), q(key), q(str(p.get("name", ""))), int(p.get("level", 1)), int(p.get("exp", 0)),
              int(p.get("tutorial_step", state.TUTORIAL_DONE)), "".join(res_cells), "".join(brows),
              len(st.get("obstacles", [])))
    return _page(key, body)


def _int(form, name, default=None):
    v = (form.get(name) or [""])[0].strip().replace(".", "").replace(",", "")
    if v == "":
        return default
    try:
        return max(0, int(v))
    except ValueError:
        return default


def _save(form):
    key = (form.get("acc") or [""])[0]
    if not key or key not in state.list_accounts():
        return None, "Không có tài khoản này."
    st = state.load(key)
    p = st["player"]
    changes = []
    name = (form.get("name") or [""])[0].strip()
    if name and name != p.get("name"):
        p["name"] = name[:20]; changes.append("tên")
    for fld in ("level", "exp", "tutorial_step"):
        v = _int(form, fld)
        if v is not None and v != p.get(fld):
            p[fld] = v; changes.append(fld)
    for k, label in RES:
        v = _int(form, "set_" + k)
        if v is not None and v != int(p.get(k, 0)):
            p[k] = v; changes.append("%s=%s" % (label, _fmt(v)))
        add = _int(form, "add_" + k, 0)
        if add:
            p[k] = int(p.get(k, 0)) + add; changes.append("%s +%s" % (label, _fmt(add)))
    keep = []
    for i, b in enumerate(st["buildings"]):
        if (form.get("del_%d" % i) or [""])[0] and b["type"][:3] != "TOW":
            changes.append("xoá %s#%d" % (b["type"], b["id"])); continue
        lv = _int(form, "lv_%d" % i)
        if lv and lv != b["level"]:
            b["level"] = lv; changes.append("%s#%d cấp %d" % (b["type"], b["id"], lv))
        keep.append(b)
    st["buildings"] = keep
    state.save(st, key)
    return key, ("Đã lưu (%s) lúc %s." % (", ".join(changes), time.strftime("%H:%M:%S")) if changes
                 else "Không có gì thay đổi.")


def handle(method, path, body):
    """Trả (mã HTTP, kiểu nội dung, nội dung, chuyển hướng hoặc None)."""
    u = urllib.parse.urlparse(path)
    qs = urllib.parse.parse_qs(u.query)
    if method == "POST" and u.path == "/admin/save":
        key, msg = _save(urllib.parse.parse_qs(body.decode("utf-8", "replace")))
        if key is None:
            return _page("Lỗi", "<div class=msg>%s</div>" % html.escape(msg))
        return 303, "text/plain", b"", "/admin/edit?" + urllib.parse.urlencode({"acc": key, "msg": msg})
    if u.path == "/admin/edit":
        key = (qs.get("acc") or [""])[0]
        if key not in state.list_accounts():
            return _page("Lỗi", "<div class=msg>Không có tài khoản này.</div>")
        return _edit_page(key, (qs.get("msg") or [""])[0])
    return _list_page()
