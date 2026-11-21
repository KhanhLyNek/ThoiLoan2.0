"""Vá APK Thời Loạn cho server riêng rồi ký lại (v1+v2+v3) bằng khoá testkey công khai của AOSP.

APK gốc đã vá (bản đang dùng) được ký bằng testkey -> APK mới cùng chữ ký, CÀI ĐÈ được, không mất dữ liệu.

Vá trong lib/arm64-v8a/*.so (chuỗi ghi đè tại chỗ, phần thừa đệm byte 0):
  - địa chỉ /info (cấu hình server)      -> http://<IP>:<cổng>/info
  - theme2018.obb / theme2018SD.obb       -> http://<IP>:<cổng>/t.obb  và  /ts.obb   (theme mùa đông)

Cách dùng (cần Java: Termux `pkg install openjdk-17`; máy tính: JDK bất kỳ):
  python tools/patch_apk.py ThoiLoan.apk ThoiLoan_vá.apk                 # IP 127.0.0.1 (server trên chính máy)
  python tools/patch_apk.py ThoiLoan.apk ThoiLoan_ban.apk --ip 100.64.1.2  # cho bạn bè qua Tailscale
  --replace classes2.dex=tools/obbgate/build/classes2.dex   thay file trong APK (trình tải OBB, xem tools/obbgate)
Lần đầu tự tải apksig.jar (Google Maven) và testkey (mã nguồn AOSP) vào tools/apksign/.
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SIGN_DIR = os.path.join(HERE, "apksign")
DOWNLOADS = {
    "apksig.jar": "https://dl.google.com/android/maven2/com/android/tools/build/apksig/8.7.3/apksig-8.7.3.jar",
    "testkey.pk8": "https://raw.githubusercontent.com/aosp-mirror/platform_build/master/target/product/security/testkey.pk8",
    "testkey.x509.pem": "https://raw.githubusercontent.com/aosp-mirror/platform_build/master/target/product/security/testkey.x509.pem",
}
TESTKEY_SHA1 = "61ed377e85d386a8dfee6b864bd85b0bfaa5af81"


def _slot(data, start):
    """Độ dài ô chứa chuỗi = chuỗi + các byte 0 theo sau (tới chuỗi kế tiếp)."""
    end = data.index(b"\0", start)
    while end < len(data) and data[end] == 0:
        end += 1
    return end - start


def patch_so(data, ip, port):
    data = bytearray(data)
    base = "http://%s:%d" % (ip, port)
    rules = [
        (rb"(?:https://info\.thoiloanmobile\.vn|http://[0-9A-Za-z.\-]+:\d+)/info\0", base + "/info"),
        (rb"http://tlm\.vcdn\.vn/res/theme2018\.obb\0|http://[0-9A-Za-z.\-]+:\d+/t\.obb\0", base + "/t.obb"),
        (rb"http://tlm\.vcdn\.vn/res/theme2018SD\.obb\0|http://[0-9A-Za-z.\-]+:\d+/ts\.obb\0", base + "/ts.obb"),
    ]
    done = []
    for pat, new in rules:
        hits = [m.start() for m in re.finditer(pat, bytes(data))]
        for at in hits:
            room = _slot(data, at)
            raw = new.encode()
            if len(raw) >= room:
                raise SystemExit("Chuỗi '%s' dài quá chỗ trống (%d byte)" % (new, room))
            data[at:at + room] = raw + b"\0" * (room - len(raw))
        done.append((new, len(hits)))
    return bytes(data), done


def ensure_tools():
    os.makedirs(SIGN_DIR, exist_ok=True)
    for name, url in DOWNLOADS.items():
        p = os.path.join(SIGN_DIR, name)
        if not os.path.isfile(p):
            print("Tải", name, "...")
            urllib.request.urlretrieve(url, p)
    import hashlib
    import ssl  # noqa: F401
    pem = open(os.path.join(SIGN_DIR, "testkey.x509.pem")).read()
    der = __import__("base64").b64decode("".join(l for l in pem.splitlines() if "CERT" not in l))
    if hashlib.sha1(der).hexdigest() != TESTKEY_SHA1:
        raise SystemExit("testkey tải về không khớp vân tay mong đợi, dừng lại.")
    if not os.path.isfile(os.path.join(SIGN_DIR, "Sign.class")):
        subprocess.check_call(["javac", "-encoding", "UTF-8", "-cp", "apksig.jar", "Sign.java"], cwd=SIGN_DIR)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--ip", default="127.0.0.1"); ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--replace", action="append", default=[], help="TÊN_TRONG_APK=file_thay")
    a = ap.parse_args()
    repl = dict(r.split("=", 1) for r in a.replace)
    ensure_tools()
    tmp = tempfile.NamedTemporaryFile(suffix=".apk", delete=False).name
    with zipfile.ZipFile(a.src) as zi, zipfile.ZipFile(tmp, "w") as zo:
        for info in zi.infolist():
            n = info.filename
            if re.match(r"META-INF/[^/]+\.(SF|RSA|DSA|EC)$|META-INF/MANIFEST\.MF$", n):
                continue                                         # chữ ký cũ
            data = zi.read(n)
            if n in repl:
                data = open(repl.pop(n), "rb").read()
                print("Thay %s (%d byte)" % (n, len(data)))
            if n.startswith("lib/arm64-v8a/") and n.endswith(".so"):
                data, done = patch_so(data, a.ip, a.port)
                print("Vá %s: %s" % (n, ", ".join("%s x%d" % d for d in done)))
            zo.writestr(info, data, compress_type=info.compress_type)
    if repl:
        raise SystemExit("Không có trong APK: " + ", ".join(repl))
    pk = os.path.join(SIGN_DIR, "testkey.pk8"); cert = os.path.join(SIGN_DIR, "testkey.x509.pem")
    cp = os.pathsep.join([os.path.join(SIGN_DIR, "apksig.jar"), SIGN_DIR])
    subprocess.check_call(["java", "-cp", cp, "Sign", pk, cert, tmp, a.dst, "14"])
    os.remove(tmp)


if __name__ == "__main__":
    main()
