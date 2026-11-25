# ThoiLoanServer v5.1

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

## Theme mùa đông - Giáng sinh (v7.2)

Game gốc có sẵn hệ thống giao diện theo mùa (bản 2018) kèm hiệu ứng **tuyết rơi**; server dựng lại theme mùa đông:
cảnh quanh làng phủ tuyết, suối đóng băng, nền ô tuyết, cây thông Noel có đèn và ngôi sao, tuyết rơi trên làng.

1. Cài **APK mới** (vá địa chỉ tải theme về server, cùng chữ ký nên cài đè được, không mất dữ liệu).
2. Chạy server như thường (`tl`).
3. Trong game: **Cài đặt > Giao diện** > đồng ý. Game tự tải theme (~2,3 MB) rồi báo khởi động lại.
4. Mở lại game: làng mùa đông + tuyết rơi. Muốn về giao diện thường: bấm lại nút Giao diện.

- Tắt hẳn theme phía server: `python server.py --no-theme` (game bỏ qua theme dù đã tải).
- Thay theme khác: đặt file `theme.obb` vào thư mục dữ liệu (ưu tiên hơn bản kèm server).
- Tự dựng lại / chỉnh theme: `python tools/theme/build_winter.py <OBB gốc> <APK> [ra.obb]`.
- Vá APK cho bạn bè (IP Tailscale): `python tools/patch_apk.py ThoiLoan.apk ThoiLoan_ban.apk --ip 100.x.y.z`
  (cần Java; lần đầu tự tải apksig + khoá testkey). Vá cả địa chỉ /info lẫn địa chỉ theme.

### Dữ liệu game (OBB): nhúng sẵn trong APK, dự phòng tự tải

- **APK đầy đủ** (`--embed-obb`): toàn bộ dữ liệu OBB nằm trong APK (game đọc thẳng `assets/` trong APK), cài là chơi,
  không cần file OBB. `python tools/patch_apk.py ThoiLoan.apk ra.apk --replace classes2.dex=tools/obbgate/build/classes2.dex --embed-obb main.1380.gsn.zps.thoiloan.obb`
- **APK nhẹ** (không nhúng): dùng trình tải bên dưới.

Gỡ app thì Android xoá luôn OBB (~43 MB). APK vá có trình tải riêng (tools/obbgate, thay trình tải Google Play đã chết):
thiếu OBB -> tải từ server (`/obb`, nhanh nếu đặt file `main.1380.gsn.zps.thoiloan.obb` vào thư mục dữ liệu),
không có thì tải từ Google Drive; hiện tiến độ trên màn hình chờ, đứt mạng thì tự thử lại và tải tiếp.
Dựng lại: `python tools/obbgate/build.py ThoiLoan.apk` rồi
`python tools/patch_apk.py ThoiLoan.apk ra.apk --replace classes2.dex=tools/obbgate/build/classes2.dex`.

## Nhật ký trận, xem lại, trả thù (v7.0)

- Mỗi trận chinh phạt được ghi lại: làng đối thủ lúc đánh, từng lính thả (loại, ô, thời điểm), sao, % phá, chiến lợi phẩm.
- Hộp thư > Báo cáo trận: tab **Tấn công** và **Phòng thủ** như game gốc, có chấm đỏ khi đăng nhập.
- Nút **Xem lại**: chiếu lại trận theo đúng thời điểm thả lính (tua nhanh bằng nút tốc độ của game).
- Nút **Trả thù** (trận phòng thủ bị người thật đánh): đánh lại làng hiện tại của người đó, dùng 1 lần.
  Không trả thù được khi đối phương đang online hoặc đang có khiên (game tự báo).
- Trận đánh làng máy cũng có trong tab Tấn công và xem lại được (không có nút trả thù).
- Dữ liệu xem lại lưu trong `thoiloan.db` (bảng `kv`), tự xoá sau 30 ngày; mỗi người giữ 30 trận gần nhất mỗi loại.

## Lưu dữ liệu an toàn (v6.9)

- Mặc định lưu bằng **SQLite** (`thoiloan.db` trong thư mục dữ liệu), chế độ WAL + ghi đồng bộ: mỗi thao tác
  (xây, nâng cấp, luyện quân, nạp G...) ghi xong là nằm chắc trên bộ nhớ. Tắt game, mất mạng, tắt Termux hay sập
  nguồn đều không mất những gì đã làm.
- Lần đầu chạy bản mới: các tài khoản cũ trong `accounts/` được tự chép sang SQLite (thư mục cũ vẫn giữ nguyên).
- Thoát game giữa trận: trận được chốt như thua 0 sao, trừ đúng số lính đã thả.
- Sao lưu tự động vào `backups/` lúc khởi động và mỗi 6 giờ, giữ 7 ngày gần nhất.
- Muốn quay lại lưu JSON: tạo `db.json` với nội dung `{"type": "json"}`.

## Chơi cùng bạn bè (v6.4)

Mỗi người dùng **một tài khoản riêng** trên cùng server: chung bang hội, chat bang hiện ngay cho người đang
online, và khi bấm **Tấn công** có 70% gặp làng **người chơi thật** (nhà chính lệch tối đa 2 cấp, không có khiên).
Người bị đánh mất phần tài nguyên bị cướp (tối đa 20% vàng/dầu, 10% dầu đen) và được khiên 12/14/16 giờ
(phá >= 30% / 60% / 90%). Đi đánh thì mất khiên của mình.

Kết nối từ ngoài mạng nhà (đơn giản nhất: **Tailscale**, miễn phí):
1. Cài Tailscale trên máy chạy server và trên điện thoại của bạn bè, đăng nhập cùng một mạng (hoặc chia sẻ máy).
2. Xem IP Tailscale của máy chạy server (dạng `100.x.y.z`).
3. Chạy server với IP đó: `TLM_IP=100.x.y.z python server.py`.
4. APK của bạn bè phải trỏ trang `/info` tới `100.x.y.z:8080` thay vì `127.0.0.1` (cần bản APK vá theo IP này).

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
  costs.py                 quy đổi thời gian / tài nguyên ra G (giống game)
  botbase.py               dựng làng đối thủ cho phó bản (cố định theo màn) và chinh phạt (ngẫu nhiên)
  gamedata.py              dữ liệu tĩnh: ảnh có sẵn, giá, mỏ, sức chứa
  data/*.json              bảng đã giải mã từ APK/OBB/JSON của game
  protocol/
    frame.py               khung gói TCP (header 0x90, độ dài, ctl, cmd, error)
    codec.py               mã hoá số/chuỗi/double big-endian, đọc dữ liệu client
    commands.py            bảng cmd -> lớp xử lý, tên lệnh, lệnh không trả lời
  packets/
    player_info.py         dựng GetPlayerInfo (1001)
    building_info.py       dựng BuildingInfo (1002)
    troop_info.py          dựng TroopInfo (1003): quân trong trại
    battle_info.py         dựng BattleInfo (9001): làng đối thủ
  handlers/                mỗi lệnh game một hàm xử lý (@handler(cmd))
    session.py             1 đăng nhập (chọn tài khoản), 1001 getUserInfo, 1006 về nhà
    city.py                2001 xây, 2003 nâng cấp, 2004 thu hoạch, 2010/2011 dọn chướng ngại
    tutorial.py            1009 bước hướng dẫn
    finish.py              2005/2006 xây-nâng cấp-dọn xong, 2011 RemoveComplete (thưởng G, kinh nghiệm)
    battle.py              9001 vào trận, 9003 kết thúc trận (chiến lợi phẩm, mở màn), 11018 quân vào trận
    profile.py             8002 thành tựu (16 mục)
    shop.py                1076 mua tài nguyên thiếu bằng G
    army.py                11001-11003 luyện quân (giới hạn theo sức chứa trại)
    single.py              9039 phó bản (màn hiện tại)
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

**v8.3**
- 7008 (sự kiện nâng nhà chính) trả lỗi = "không có sự kiện" theo đúng nhánh của game (trước đây không trả lời).

**v8.2** - Cửa hàng yêu tinh + quà đăng nhập 7 ngày
- Cửa hàng yêu tinh (6008/6009/6010): 6 món ngẫu nhiên từ DailyShop, mua bằng xu nhiệm vụ (vật phẩm loại 14),
  tự làm mới sau 8 giờ hoặc làm mới bằng G.
- Quà đăng nhập 7 ngày (7004 đẩy khi vào game, 7005 nhận quà OnlineGift.json vào kho).

**v8.1** - Nhiệm vụ ngày
- 15 nhiệm vụ mỗi ngày (DailyQuest.json, theo cấp nhà chính), độ khó tăng dần (hardMode). Nhận quà (6004) -> vật phẩm
  vào kho (túi vàng/dầu/dầu đen, rương ChestGift), xong ngay bằng G (6006), đổi nhiệm vụ (6007). Lưu trên server.
- Server tự cộng tiến độ cho: đánh trận (sao), cướp vàng/dầu/dầu đen, thu hoạch mỏ, luyện lính, chế phép, dọn chướng ngại.
- Dùng được túi tài nguyên loại 16/17/18 (quà nhiệm vụ).

**v8.0** - CÁ NHÂN: nhân vật + khảm ngọc (pha lê)
- Chọn / đổi nhân vật (1053/1068) được lưu; 1082 trả nhân vật khi vào game (trước đây luôn rỗng -> chọn lại từ đầu).
- Ngọc (CrystalMgr, GemSupport.json): mua đá pha lê (1094, trừ G), mở đá ra ngọc (1093, theo bộ sưu tập),
  khảm / tháo vào ô (1088/1089), mở ô (1091), ghép 3 -> 1 cấp cao hơn (1095), xem ngọc người khác (1100).
  Tất cả lưu trên server, gửi lại qua 1087 khi mở bảng.

**v7.9** - Xưởng phép, phép, bỏ lính, huỷ xây...
- Xây được NHÀ PHÉP (SPF_1); chế phép (11008), huỷ (11009), phép xong (11010), xong ngay bằng G (11011), bỏ phép (11016).
  Hàng đợi + kho phép lưu trên server, gửi lại trong BuildingInfo; phép mang vào trận (BattleInfo @0x38), dùng xong trừ kho.
  Nghiên cứu phép ở phòng thí nghiệm (SpellLevel.json).
- Bỏ lính khỏi trại quân (11015) nay trừ trên server (trước đây vào lại game lính bỏ đi vẫn còn).
- Huỷ xây/nâng cấp (2009, hoàn 50%), sửa bẫy (2027), dựng lại lâu đài bang (2012), đổi tên (1011), anh hùng (11012/11013).

**v7.8** - công trình nâng cấp xong bị tụt cấp
- Server gửi CẤP THẬT cho game. Bản cũ hạ cấp khi ContentName3 không liệt kê đúng cấp (AMC_1 9, LAB_1 10, CLC_1 7,
  DEF_1/DEF_2 16-17, DEF_3 11-13, STO 12, BDH 2-5... 47 trường hợp) dù JsonMgr::getImageName tự lùi về ảnh gần nhất
  -> game hiện cấp thấp, cho nâng lại, server báo tối đa nhưng vẫn trả "thành công" -> vào lại/đi đánh là tụt cấp.
- Chỉ DEF_4 cấp 9+ còn bị giữ ở 8 (OBB không có ảnh DEF_4_5). Nâng quá cấp tối đa nay trả LỖI cho game.

**v7.7**
- Đánh đảo TRỐNG ở Cổng thế giới đi lệnh 9001 [0][1|2][id đảo] (không phải 9017): bản trước tưởng là chinh phạt thường
  nên thắng xong không chiếm được đảo, không có uranium. Nay nhận ra id đảo -> trận đánh đảo -> chiếm đảo.
- Anh hùng vào trận: BattleInfo gửi kèm lính anh hùng theo nhà anh hùng (KQB_1 -> ARM_11 vua, KQB_2 -> ARM_12 nữ hoàng,
  KQB_4 -> ARM_18, KQB_5 -> ARM_19), cấp = cấp nhà. Trước đây danh sách chỉ có lính thường nên không có anh hùng.
- Bản vá mã máy (qua bộ nạp): giao diện mùa đông BẬT SẴN (USE_THEME mặc định true) -> game tự tải /t.obb và có tuyết rơi.

**v7.6** - bộ nạp bản vá + dê và đại bàng trong làng (cần cài APK mới MỘT LẦN)
- APK có BỘ NẠP BẢN VÁ (`tools/obbgate/src/.../TlmLoader.java`): mỗi lần mở game hỏi server `/patch/native.txt`,
  vá bản sao `libcocos2dcpp.so` (chỉ khi mọi byte cũ khớp) rồi nạp bản đã vá; lỗi gì cũng quay về lib gốc.
  Từ nay sửa mã máy của game chỉ cần `tl` (sửa `tools/native/*.s` -> `python tools/native/build.py <lib gốc>`
  -> `tlm/res/patches/native.json`), không phải cài lại APK. Server tắt thì dùng bản vá lần trước.
  Log ghi `OBB (từ máy): bộ nạp: ...` cho biết đã nạp lib vá hay lib gốc.
- Dê (Farmer, ảnh GOA_1) đi từ nhà chính sang các nhà trong làng, đại bàng bay ngang trời: game gốc đã khoá
  `CityMgr::createFarmer` / `createAngryBird` (thân hàm chỉ còn `ret`); bản vá viết lại hai hàm (tối đa 4 dê, 1 đại bàng,
  không tạo khi đang sắp xếp làng) trong vùng mã chết `TutorialMgr::addCheatFinishTutButton`.

**v7.5** - cổng thế giới (đảo + uranium)
- Bản đồ đảo (14001) có dữ liệu thật: đảo bạn chiếm hiện viền xanh và TÊN BẠN (+ ảnh, tên bang), đảo người khác hiện tên chủ.
- Đánh đảo (9017) vào trận như thường; thắng >= 1 sao là chiếm đảo (đảo trống = làng máy, đảo có chủ = làng của chủ đảo,
  không cướp tài nguyên). Mỗi người giữ tối đa `maxIslandOwner` đảo theo cấp bang, chiếm thêm thì bỏ đảo cũ nhất.
- Thu hoạch uranium (14003 + 1040): đảo sản xuất 120/giờ, tối đa 480; bạn nhận `percentUranium` % theo cấp
  Kho uranium (KQB_3), không quá sức chứa của kho; phần còn lại vào quỹ bang. Uranium lưu trong hồ sơ và gửi lúc đăng nhập.
- Đảo lưu ở kho phụ (`world/islands`), sống qua khởi động lại.

**v5.1**
- Vào trận có lính để thả: BattleInfo gửi kèm lính trong trại (`[tên][số lượng][cấp]`, danh sách mà
  `BattleMgr::addTroop` và thanh chọn lính đọc). Bản 5.0 gửi rỗng nên thanh chọn lính trống.
- Phó bản không còn văng khi nạp làng: phó bản vẽ nhà chính và trại lính bằng ảnh Goblin
  (`TOW_1_GOBLIN_<cấp>`, `BAR_1_GOBLIN_<cấp>`), OBB chỉ có cấp 1, nên hai công trình này luôn cấp 1 trong phó bản.

**v5.0** - đánh trận
- Phó bản và chinh phạt có làng đối thủ: gói BattleInfo (9001) đã giải mã. Mỗi công trình: id, loại, ô (= y*44 + x),
  cấp, vàng/dầu/dầu đen chứa bên trong (phá ra thì thành chiến lợi phẩm). Làng do `botbase.py` dựng theo
  `TownHall.json`: phó bản 50 màn cố định (nhà chính cấp 1 -> 10, chiến lợi phẩm theo `SingleBattle.json`),
  chinh phạt ngẫu nhiên quanh cấp nhà chính của bạn.
- Kết thúc trận (9003) đã giải mã: sao, vàng, dầu, dầu đen, phần trăm phá. Server cộng chiến lợi phẩm và mở
  màn phó bản kế tiếp khi thắng (>= 1 sao).
- Quân không còn mất: gói TroopInfo (1003) gửi lại quân trong trại. Luyện quân giới hạn theo sức chứa trại.

**v4.5**
- Bấm Tấn công không còn văng: gói phó bản 9039 gửi màn hiện tại = 1 (lưu trong tài khoản, `single_map`).
  Bản cũ gửi 0 -> màn Tấn công tìm mốc "point0" trên bản đồ (không có, mốc bắt đầu từ 1) -> con trỏ rỗng.

**v4.4**
- Luyện quân không còn văng: phản hồi cmd 11001 gửi đúng `[id trại lính][giờ xong]` thay vì toàn số 0
  (game gọi `getBuilding(id)`, id 0 không có công trình -> con trỏ rỗng). Số lính luyện được ghi vào state.

**v4.3.1**
- Lâu đài bang gửi cấp 1 thay vì 0: `ClanCastle.json` không có cấu hình cấp 0, game văng ngay khi dựng làng.
  Lâu đài cấp 0 đã lưu được tự nâng lên cấp 1.

**v4.3**
- Mở luyện quân ở trại lính không còn văng: làng luôn có lâu đài bang (đổ nát, cấp 0) như `InitGame.json`;
  thiếu nó thì `ArmyManagerGUI::setLabel` gọi `ClanCastleObject::getTotalTroopClan` trên đối tượng rỗng.
- Công trình vừa đặt nhận đúng id game tự cấp (lần đầu game nhắc tới nó), nên "xong ngay" và nâng cấp
  không còn trỏ nhầm (log: trại lính đầu tiên game gọi là id 2).

**v4.2**
- G không còn bị "hoàn lại": "xong ngay" bằng G (2006) trừ G theo thời gian còn lại, mua tài nguyên thiếu
  bằng G (1076) trừ G và cộng tài nguyên. Công thức theo `Utility::getCostToBuyTime` / `getCostToBuyResources`
  (1 phút = 2 G, 1 giờ = 40 G, 1 ngày = 520 G, 1 tuần = 2000 G; 250 vàng = 3 G).
- Tab Thành tựu không còn văng: server gửi đủ 16 thành tựu (gói 8002) thay vì bỏ qua.

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
