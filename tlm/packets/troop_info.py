"""TroopInfo (cmd 1003) - quân trong trại: [int số loại] rồi mỗi loại [chuỗi tên lính][short số lượng].

(Đọc từ nhánh thành công của cmd 1003 trong ServerCommunication::onReceived -> CityMgr::onGetTroopInfo.)
"""
from ..protocol.codec import pstr, u16, u32


def build(st):
    troops = [(t, int(n)) for t, n in sorted(st.get("troops", {}).items()) if int(n) > 0]
    return u32(len(troops)) + b"".join(pstr(t) + u16(min(n, 0xFFFF)) for t, n in troops) + bytes(256)
