#!/usr/bin/env python3
"""Client giả: chạy thử luồng đăng nhập -> vào làng -> xây -> thu hoạch -> về nhà, không cần điện thoại.

Dùng:  python tools/fake_client.py            (server phải đang chạy)
"""
import json
import socket
import sys
import time
import urllib.request

HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"


def frame(cmd, data=b"", ctl=1):
    body = bytes([ctl]) + cmd.to_bytes(2, "big") + data
    return bytes([0x90]) + len(body).to_bytes(2, "big") + body


def pstr(s):
    return len(s).to_bytes(2, "big") + s.encode()


def recv_all(sock, wait=0.6):
    sock.settimeout(wait)
    got = b""
    try:
        while True:
            d = sock.recv(65536)
            if not d:
                break
            got += d
    except socket.timeout:
        pass
    out, i = [], 0
    while i + 3 <= len(got):
        ln = int.from_bytes(got[i + 1:i + 3], "big")
        body = got[i + 3:i + 3 + ln]
        out.append((int.from_bytes(body[1:3], "big"), body[3], len(body) - 4))
        i += 3 + ln
    return out


def main():
    info = json.loads(urllib.request.urlopen("http://%s:8080/info?platform=android" % HOST).read())
    print("/info  -> server %s:%s" % (info["server_ip"], info["server_port"]))
    login = json.loads(urllib.request.urlopen(urllib.request.Request(
        "http://%s:8080/login" % HOST, data=b"social=google&accessToken=ThoiLoan&deviceId=test")).read())
    print("/login ->", login)
    print("/mail  ->", urllib.request.urlopen("http://%s:8080/mail?country=vn&uId=1" % HOST).read().decode())
    s = socket.create_connection((HOST, 9000))
    steps = [
        ("đăng nhập (cmd 1)", frame(1, pstr(login["sessionKey"]))),
        ("getUserInfo (1001)", frame(1001)),
        ("xây pháo DEF_1 (2001)", frame(2001, pstr("DEF_1") + bytes([12, 12]) + bytes(4))),
        ("thu hoạch mỏ id 3 (2004)", frame(2004, (3).to_bytes(4, "big"))),
        ("thành tựu (8002, bị bỏ qua)", frame(8002)),
        ("về nhà (1006)", frame(1006, (1).to_bytes(4, "big"))),
    ]
    for name, fr in steps:
        s.sendall(fr)
        print("%-30s -> nhận (cmd, error, dữ liệu): %s" % (name, recv_all(s)))
    s.close()


if __name__ == "__main__":
    main()
