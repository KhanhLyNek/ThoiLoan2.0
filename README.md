# ThoiLoanServer v3.1

Server giả chạy localhost cho **Thời Loạn Mobile** (`gsn.zps.thoiloan` 7.6.12), chạy trong Termux.
Chỉ dùng thư viện chuẩn của Python 3, không cần cài thêm gói nào.

## Cài lần đầu (Termux)

```
termux-setup-storage                 # chỉ làm 1 lần
pkg install git gh python
gh auth login                        # GitHub.com -> HTTPS -> Login with a web browser
gh repo clone KhanhLyNek/ThoiLoan2.0 ~/ThoiLoan2.0
```

## Chạy

```
cd ~/ThoiLoan2.0
git pull                             # lấy bản mới nhất
python server.py                     # Ctrl+C để dừng
```

Kiểm tra server mà không cần điện thoại hay game (mở Termux thứ hai):

```
python tools/fake_client.py
```

Tuỳ chọn: `--no-auto`, `--empty`, `--no-push`, `--no-obb` (xem đầu file `server.py`).

## Gửi log

```
mkdir -p ~/ThoiLoan2.0/logs
cp /sdcard/ThoiLoan2.0/log.txt ~/ThoiLoan2.0/logs/log.txt
cd ~/ThoiLoan2.0 && git add logs && git commit -m log && git push
```

Báo cáo sập: dán vào file `logs/crash.txt` rồi đẩy lên giống như trên.

## Dữ liệu người chơi (`/sdcard/ThoiLoan2.0/`)

| File | Ý nghĩa |
|---|---|
| `state.json` | Làng: người chơi (vàng, dầu, G, hướng dẫn...), công trình, chướng ngại. Xoá file = làng về ban đầu |
| `log.txt` | Log lần chạy hiện tại |
| `old_logs/` | Log cũ, nén theo giờ tạo |
| `replies.json` | (tuỳ chọn) luật trả lời tay, ưu tiên hơn tự trả lời |
| `info.json` | (tuỳ chọn) ghi đè JSON của `/info` |

## Cấu trúc mã

```
server.py                  điểm chạy: khởi tạo thư mục, log, mở cổng HTTP 8080, GAME 9000, CHAT 9001
tlm/
  config.py                cổng, IP, tuỳ chọn, thư mục dữ liệu
  logger.py                log ra màn hình + log.txt, nén log cũ
  state.py                 đọc/ghi state.json, sức chứa, trừ/cộng tài nguyên
  gamedata.py              dữ liệu tĩnh: ảnh có sẵn, giá, mỏ, sức chứa
  data/*.json              bảng đã giải mã từ APK/OBB/JSON của game
  protocol/
    frame.py               khung gói TCP (header 0x90, độ dài, ctl, cmd, error)
    codec.py               mã hoá số/chuỗi/double big-endian, đọc dữ liệu client
    commands.py            bảng cmd -> lớp xử lý, tên lệnh, lệnh không trả lời
  packets/
    player_info.py         dựng GetPlayerInfo (1001)
    building_info.py       dựng BuildingInfo (1002)
  handlers/                mỗi lệnh game một hàm xử lý (@handler(cmd))
    session.py             1001 getUserInfo, 1006 về nhà
    city.py                2001 xây, 2003 nâng cấp, 2004 thu hoạch, 2010/2011 dọn chướng ngại
    tutorial.py            1009 bước hướng dẫn
    finish.py              2005/2006 xây-nâng cấp-dọn xong, 2011 RemoveComplete (thưởng G, kinh nghiệm)
    battle.py              9003 kết thúc trận (đang ghi log để giải mã)
  game_server.py           TCP: tách khung -> replies.json -> handler -> tự trả lời
  http_server.py           /info, /login (đăng nhập khách), /mail
tools/fake_client.py       client giả để thử nhanh
```

Một gói từ game đi qua 4 tầng:
**mạng** (`game_server`) → **giao thức** (`protocol`) → **xử lý** (`handlers`) → **trạng thái** (`state`) và **dựng gói trả về** (`packets`).

## Thêm một lệnh mới

1. Xem log: dòng `KHUNG ctl=1 cmd=XXXX [...]` cho biết game gửi gì.
2. Tạo hàm trong `tlm/handlers/` (hoặc thêm vào file có sẵn):

```python
from . import handler

@handler(XXXX)
def ten_lenh(ctx, ctl, cmd, payload):
    ...                       # đọc payload bằng protocol.codec.Reader, cập nhật state
    ctx.reply(ctl, cmd, 0, b"...")
    return True               # False = để server tự trả lời "thành công" + đệm số 0
```

3. Nếu là file mới, thêm vào `load_all()` trong `tlm/handlers/__init__.py`.
4. Lệnh trả về làm game sập: thêm vào `tlm/data/skip_auto.json`.

## Thay đổi

**v3.1**
- Công trình gửi trạng thái 2 (bình thường) thay vì 0, nên có nút nâng cấp và kho được tính sức chứa.
- Dọn chướng ngại: khi đồng hồ về 0, server trả `FinishBuilding` đúng định dạng `[id][giờ xong]` và gửi
  `RemoveComplete`, nên chướng ngại biến mất, 50% được 1–5 G, cộng kinh nghiệm theo `Obstacle.json`.
  Bản cũ trả toàn số 0 nên game không khớp id và gửi lại `sendFinish` mỗi giây.
- Xây hoặc nâng cấp xong (kể cả "xong ngay" bằng G) cũng trả `[id][giờ xong]`.

**v3.0**: tách thành dự án nhiều tầng, kết quả giống hệt bản một file.
