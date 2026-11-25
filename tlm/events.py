"""MỞ SỰ KIỆN không cần APK: game tự tải JSON mới từ server lúc khởi động.

PreloadScreen::checkVersion lấy "json_url" + "json_version" từ /info. PreloadScreen::requestConfig: json_version của
server > bản đã lưu -> GET json_url -> finishRequestConfig: JSON {"Tên": "<nội dung file dạng CHUỖI>"} -> với mỗi mục
CCUserDefault::setStringForKey("Tên.json", chuỗi), lưu "jsonVersion", vào game. JsonMgr::loadJsonFile("json/X.json") hỏi
CCUserDefault "X.json" TRƯỚC, có thì dùng thay file trong OBB. (Giá trị PHẢI là chuỗi: game đọc thẳng con trỏ chuỗi.)

EventConfig.json: CityMgr::onGetEventConfigInfo đọc giờ bắt đầu/kết thúc mọi sự kiện (số nguyên giây) -> biến toàn cục
EventConfig::* ; GameDataMgr::isGoatEvent... = giờ hiện tại trong khoảng + đủ cấp. Bản gốc hết hạn từ 2014-2020.
OPEN = các sự kiện server đã có lệnh xử lý -> mở 2020..2035. Thêm sự kiện mới: viết handler rồi thêm vào OPEN và TĂNG
JSON_VERSION (game chỉ tải lại khi số này lớn hơn bản đã lưu).
"""
import json

from .data import load_table

JSON_VERSION = "101"
START, END = 1577811600, 2051197200          # 2020-01-01 .. 2035-01-01 (giờ VN)

# sự kiện -> (khoá bắt đầu, khoá kết thúc, các khoá phụ đặt = END để tắt giai đoạn phụ)
OPEN = {
    "goat": ("goatEventStart", "goatEventEnd", ()),                     # dê đi dạo trong làng (handlers/goat.py)
    "giftHunting": ("giftHuntingStart", "giftHuntingEnd",               # kho báu yêu tinh (handlers/goblin_treasure.py)
                    ("giftHuntingMiddle", "giftHuntingDiscountSpin10Start")),
}


def event_config():
    ev = dict(load_table("event_config.json"))
    for start, end, later in OPEN.values():
        ev[start], ev[end] = START, END
        for k in later:
            ev[k] = END
    return ev


def json_files():
    """Nội dung trả cho json_url."""
    return {"EventConfig": json.dumps(event_config(), separators=(",", ":"))}
