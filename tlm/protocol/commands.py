"""Bảng lệnh: lớp xử lý phía game, tên lệnh client, lệnh không tự trả lời."""
from ..data import load_table

# cmd -> lớp CmdReceive (game xử lý gói server gửi về cùng mã cmd). "ErrorCode" = chỉ cần byte error.
RECV_CLASS = {int(k): v for k, v in load_table("recv_class.json").items()}
# cmd client gửi -> tên (đã xác định qua hàm gửi trong libcocos2dcpp.so)
SEND_NAMES = {int(k): v for k, v in load_table("send_names.json").items()}
# không tự trả lời: phản hồi toàn số 0 làm game sập (đã xác nhận qua báo cáo sập)
SKIP_AUTO = {int(k): v for k, v in load_table("skip_auto.json").items()}
