# ThoiLoanServer v4.1

Server giả chạy localhost cho **Thời Loạn Mobile** (`gsn.zps.thoiloan` 7.6.12), chạy trong Termux.
Chỉ dùng thư viện chuẩn của Python 3 (riêng lưu bằng MySQL cần thêm `pymysql`).

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

## Tài khoản và trang quản trị

- Mỗi **nút đăng nhập** (Google, Facebook, Zalo) trên mỗi máy là **một tài khoản riêng**: `google-<mã máy>`...
  Đây không phải đăng nhập Google thật (Google từ chối APK đã ký lại), chỉ là các ô lưu riêng.
- Làng cũ (`state.json` bản 3.x) tự chuyển sang tài khoản **đăng nhập đầu tiên**.
- **Trang quản trị:** mở trình duyệt trên điện thoại, vào **http://127.0.0.1:8080/admin** (lúc server đang chạy).
  Sửa tên, cấp, kinh nghiệm, **vàng / dầu hồng / dầu đen / G** (đặt số hoặc cộng thêm), cấp từng công trình.
  Lưu xong, trong game bấm **Về nhà** hoặc vào lại game để thấy.
- Vàng và dầu hiện trong game tối đa bằng sức chứa (nhà chính + kho). Lưu số lớn hơn vẫn được, game nhận thêm khi kho lớn lên.

## Lưu bằng MySQL (tuỳ chọn)

Mặc định lưu file JSON trong `/sdcard/ThoiLoan2.0/accounts/`. Để dùng MySQL (MariaDB) ngay trong Termux:

```
pkg install mariadb
pip install pymysql
mysqld_safe &                        # bật MySQL (mỗi lần mở Termux mới)
mariadb -u $(whoami) -e "CREATE DATABASE thoiloan CHARACTER SET utf8mb4; CREATE USER 'tlm'@'localhost' IDENTIFIED BY 'tlm123'; GRANT ALL ON thoiloan.* TO 'tlm'@'localhost';"
```

Rồi tạo file `/sdcard/ThoiLoan2.0/db.json`:

```
{"type": "mysql", "host": "127.0.0.1", "port": 3306, "user": "tlm", "password": "tlm123", "database": "thoiloan"}
```

Lần chạy đầu với MySQL, các tài khoản JSON có sẵn được tự chép vào bảng `accounts`. Không muốn cài MySQL thì có
thể dùng `{"type": "sqlite"}` (có sẵn trong Python). Nếu không mở được MySQL, server báo lỗi và dừng
(không tự chơi trên bản JSON cũ để tránh lệch dữ liệu).

## Dữ liệu người chơi (`/sdcard/ThoiLoan2.0/`)

| File | Ý nghĩa |
|---|---|
| `accounts/` | Mỗi tài khoản một file JSON (khi lưu kiểu JSON) |
| `db.json` | (tuỳ chọn) chọn kiểu lưu: json / sqlite / mysql |
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
  state.py                 đọc/ghi làng theo tài khoản, sức chứa, trừ/cộng tài nguyên
  storage.py               kho lưu: JSON / SQLite / MySQL (chọn bằng db.json)
  admin.py                 trang quản trị web /admin
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
    session.py             1 đăng nhập (chọn tài khoản), 1001 getUserInfo, 1006 về nhà
    city.py                2001 xây, 2003 nâng cấp, 2004 thu hoạch, 2010/2011 dọn chướng ngại
    tutorial.py            1009 bước hướng dẫn
    finish.py              2005/2006 xây-nâng cấp-dọn xong, 2011 RemoveComplete (thưởng G, kinh nghiệm)
    battle.py              9003 kết thúc trận (đang ghi log để giải mã)
  game_server.py           TCP: tách khung -> replies.json -> handler -> tự trả lời
  http_server.py           /info, /login (đăng nhập theo nút + máy), /mail, /admin
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

**v4.1**
- Tắt hướng dẫn "ngọc bổ trợ" tự bật khi nâng nhà chính: gửi ô `@0x114` của GetPlayerInfo = 15 (đã xong).
  Game bật hướng dẫn này khi ô đó ≤ 14 (`CityMgr::onGetTroopInfo` -> `startTutorialCrystal`).

**v4.0**
- Nhiều tài khoản: mỗi nút đăng nhập trên mỗi máy một làng riêng. Làng cũ tự chuyển sang tài khoản đầu tiên.
- Kho lưu chọn được: JSON (mặc định), SQLite, MySQL (`db.json`).
- Trang quản trị `http://127.0.0.1:8080/admin`: sửa 4 loại tài nguyên, tên, cấp, kinh nghiệm, cấp công trình.

**v3.3**
- Sửa lệch id công trình: game cấp id công trình mới theo nhóm (số công trình cùng nhóm + 1), còn server cũ
  cấp id chung cho cả làng, nên "xong ngay" và nâng cấp công trình mới trỏ nhầm công trình khác
  (ví dụ nâng RES_2 thành nâng nhầm trại quân). Server giờ đánh id theo nhóm và tìm theo (nhóm, id).
  `state.json` cũ được tự đánh lại id một lần.

**v3.2**
- Tiến độ hướng dẫn "đã xong" = 70 (trước là 69). Game coi hướng dẫn còn chạy khi ≤ 69 (`TutorialMgr::isDoing`)
  và khi đó khoá các tab cửa hàng (`ShopGUI2::finishStart`), hộp nâng cấp (`BuildingInfoGUI::setUpgradeDialog`)
  và luyện quân (`TrainDialogGUI`). `state.json` cũ có giá trị 69 được tự đổi thành 70.

**v3.1**
- Công trình gửi trạng thái 2 (bình thường) thay vì 0, nên có nút nâng cấp và kho được tính sức chứa.
- Dọn chướng ngại: khi đồng hồ về 0, server trả `FinishBuilding` đúng định dạng `[id][giờ xong]` và gửi
  `RemoveComplete`, nên chướng ngại biến mất, 50% được 1–5 G, cộng kinh nghiệm theo `Obstacle.json`.
  Bản cũ trả toàn số 0 nên game không khớp id và gửi lại `sendFinish` mỗi giây.
- Xây hoặc nâng cấp xong (kể cả "xong ngay" bằng G) cũng trả `[id][giờ xong]`.

**v3.0**: tách thành dự án nhiều tầng, kết quả giống hệt bản một file.
