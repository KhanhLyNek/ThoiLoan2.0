"""Dựng classes2.dex có trình tải OBB riêng (TlmObbGate) từ APK game.

  python tools/obbgate/build.py ThoiLoan.apk [ra/classes2.dex]
  python tools/patch_apk.py ThoiLoan.apk ThoiLoan_vá.apk --replace classes2.dex=tools/obbgate/build/classes2.dex

Các bước: baksmali classes2.dex -> thêm TlmObbGate (src/, biên dịch với stubs/ rồi d8) -> sửa
SampleDownloaderActivity.onCreate: thiếu OBB thì gọi TlmObbGate.start(this) thay trình tải Google Play -> smali lại.
Lần đầu tự tải d8 (r8), smali/baksmali và thư viện phụ vào tools/obbgate/jars/. Cần JDK (javac, java).
"""
import os, shutil, subprocess, sys, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
JARS = os.path.join(HERE, "jars")
G = "https://dl.google.com/android/maven2/"
C = "https://repo1.maven.org/maven2/"
DEPS = {
    "r8.jar": G + "com/android/tools/r8/8.5.35/r8-8.5.35.jar",
    "smali.jar": G + "com/android/tools/smali/smali/3.0.7/smali-3.0.7.jar",
    "baksmali.jar": G + "com/android/tools/smali/smali-baksmali/3.0.7/smali-baksmali-3.0.7.jar",
    "dexlib2.jar": G + "com/android/tools/smali/smali-dexlib2/3.0.7/smali-dexlib2-3.0.7.jar",
    "util.jar": G + "com/android/tools/smali/smali-util/3.0.7/smali-util-3.0.7.jar",
    "antlr-runtime.jar": C + "org/antlr/antlr-runtime/3.5.2/antlr-runtime-3.5.2.jar",
    "antlr.jar": C + "antlr/antlr/2.7.7/antlr-2.7.7.jar",
    "stringtemplate.jar": C + "org/antlr/stringtemplate/3.2.1/stringtemplate-3.2.1.jar",
    "jcommander.jar": C + "com/beust/jcommander/1.64/jcommander-1.64.jar",
    "guava.jar": C + "com/google/guava/guava/31.1-android/guava-31.1-android.jar",
    "failureaccess.jar": C + "com/google/guava/failureaccess/1.0.1/failureaccess-1.0.1.jar",
}
HOOK2_OLD = "    :cond_78\n    invoke-virtual {p0}, Lcom/vng/Downloader/SampleDownloaderActivity;->validateXAPKZipFiles()V"
HOOK2_NEW = ("    :cond_78\n    # ThoiLoan2.0: đã có OBB -> gắn lại + báo chẩn đoán rồi mới kiểm tra\n"
             "    invoke-static {p0}, Lcom/vng/Downloader/TlmObbGate;->delivered(Lcom/vng/Downloader/SampleDownloaderActivity;)V")
HOOK_OLD = "    if-nez v0, :cond_78\n\n    .line 289\n    :try_start_50"
HOOK_NEW = ("    if-nez v0, :cond_78\n\n"
            "    # ThoiLoan2.0: thiếu OBB -> trình tải riêng (server /obb hoặc Google Drive) thay Google Play\n"
            "    invoke-static {p0}, Lcom/vng/Downloader/TlmObbGate;->start(Lcom/vng/Downloader/SampleDownloaderActivity;)V\n\n"
            "    return-void\n\n    .line 289\n    :try_start_50")


def run(*cmd):
    subprocess.check_call(list(cmd))


def main(apk, out):
    os.makedirs(JARS, exist_ok=True)
    for n, u in DEPS.items():
        if not os.path.isfile(os.path.join(JARS, n)):
            print("Tải", n); urllib.request.urlretrieve(u, os.path.join(JARS, n))
    cp = os.pathsep.join(os.path.join(JARS, n) for n in DEPS if n != "r8.jar")
    b = os.path.join(HERE, "build"); shutil.rmtree(b, ignore_errors=True)
    for d in ("stubs", "cls", "dex", "c2"):
        os.makedirs(os.path.join(b, d))
    with zipfile.ZipFile(apk) as z:
        open(os.path.join(b, "orig_classes2.dex"), "wb").write(z.read("classes2.dex"))
    java_files = lambda root: [os.path.join(r, f) for r, _, fs in os.walk(root) for f in fs if f.endswith(".java")]
    run("javac", "-encoding", "UTF-8", "--release", "8", "-d", os.path.join(b, "stubs"), *java_files(os.path.join(HERE, "stubs")))
    run("javac", "-encoding", "UTF-8", "--release", "8", "-cp", os.path.join(b, "stubs"), "-d", os.path.join(b, "cls"),
        *java_files(os.path.join(HERE, "src")))
    classes = [os.path.join(r, f) for r, _, fs in os.walk(os.path.join(b, "cls")) for f in fs]
    run("java", "-cp", os.path.join(JARS, "r8.jar"), "com.android.tools.r8.D8", "--min-api", "14",
        "--classpath", os.path.join(b, "stubs"), "--output", os.path.join(b, "dex"), *classes)
    bak = ["java", "-cp", cp, "com.android.tools.smali.baksmali.Main", "d", "-o", os.path.join(b, "c2")]
    run(*bak, os.path.join(b, "orig_classes2.dex"))
    run(*bak, os.path.join(b, "dex", "classes.dex"))
    p = os.path.join(b, "c2", "com", "vng", "Downloader", "SampleDownloaderActivity.smali")
    s = open(p, encoding="utf-8").read()
    if s.count(HOOK_OLD) != 1 or s.count(HOOK2_OLD) != 1:
        raise SystemExit("Không tìm thấy chỗ móc trong SampleDownloaderActivity.onCreate (APK khác bản 7.6.12?)")
    open(p, "w", encoding="utf-8").write(s.replace(HOOK_OLD, HOOK_NEW).replace(HOOK2_OLD, HOOK2_NEW))
    run("java", "-cp", cp, "com.android.tools.smali.smali.Main", "a", "-a", "15", "-o", out, os.path.join(b, "c2"))
    print("Đã tạo", out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "build", "classes2.dex"))
