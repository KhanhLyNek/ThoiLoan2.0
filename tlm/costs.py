"""Quy đổi ra G giống game (Utility::calculateExchangeCost, bảng mốc đọc từ libcocos2dcpp.so).

- Thời gian còn lại -> G  (Utility::getCostToBuyTime):      60 s = 2, 1 giờ = 40, 1 ngày = 520, 1 tuần = 2000.
- Mua tài nguyên thiếu -> G (Utility::getCostToBuyResources): bảng riêng cho vàng/dầu và cho dầu đen.
Giữa hai mốc: nội suy tuyến tính. Vượt mốc cuối: chia ra các khối bằng mốc cuối rồi cộng phần dư.
Làm tròn xuống: khớp với game (hộp "Thiếu tài nguyên" hiện 250 vàng = 3 G).
"""
TIME_X = (60, 3600, 86400, 604800)
TIME_Y = (2, 40, 520, 2000)
RES_X = (100, 1000, 10000, 100000, 1000000, 10000000)     # vàng, dầu hồng
RES_Y = (2, 10, 50, 250, 1200, 6000)
DARK_X = (1, 10, 100, 1000, 10000, 100000)                  # dầu đen
DARK_Y = (2, 10, 50, 250, 1200, 6000)


def exchange(value, xs, ys):
    value = int(value)
    if value <= 0:
        return 0
    if value <= xs[0]:
        return ys[0]
    if value > xs[-1]:
        q, r = divmod(value, xs[-1])
        return q * ys[-1] + exchange(r, xs, ys)
    for i in range(len(xs) - 1):
        if value <= xs[i + 1]:
            span = xs[i + 1] - xs[i]
            return ys[i] + (value - xs[i]) * (ys[i + 1] - ys[i]) // span
    return ys[-1]


def time_cost(seconds):
    return exchange(seconds, TIME_X, TIME_Y)


def resource_cost(gold=0, elixir=0, dark=0):
    return exchange(gold, RES_X, RES_Y) + exchange(elixir, RES_X, RES_Y) + exchange(dark, DARK_X, DARK_Y)
