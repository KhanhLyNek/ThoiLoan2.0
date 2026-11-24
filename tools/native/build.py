"""Dịch tools/native/*.s thành bản vá byte cho libcocos2dcpp.so (arm64) -> tlm/res/patches/native.json.

  python tools/native/build.py [đường/dẫn/libcocos2dcpp.so để kiểm tra]

Bản vá áp lúc chạy bởi bộ nạp trong APK (TlmLoader): sao chép lib gốc, ghi các byte mới (sau khi kiểm byte cũ
khớp), rồi System.load bản đã vá. Cần llvm-mc + llvm-objcopy (hoặc clang). Địa chỉ dưới đây là của bản 7.6.12.
"""
import json, os, struct, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "tlm", "res", "patches", "native.json")

CAVE = 0xacb3c4            # TutorialMgr::addCheatFinishTutButton (640 byte, không ai gọi) -> chỗ đặt mã mới
CAVE_SIZE = 640
SYMS = {
    "NEW": 0xf3e154,             # operator new(size_t)
    "FARMER_CTOR": 0xaf069c,     # Farmer::Farmer()
    "FARMER_CREATE": 0xaf0944,   # Farmer::create(int id)
    "EAGLE_CTOR": 0xaef894,      # Eagle::Eagle()
    "EAGLE_CREATE": 0xaef990,    # Eagle::create(int id)
    "PUSH_BACK": 0x710ea8,       # vector<MapObject*>::_M_emplace_back_aux(T* const&) (dùng chung cho vector con trỏ)
}
EDITMODE = 0x133644d             # GameDataMgr::isEditMode (bool)
CREATE_FARMER = 0x97cb5c         # CityMgr::createFarmer(int) = "ret"
CREATE_EAGLE = 0x97cc34          # CityMgr::createAngryBird() = "ret"
RET = bytes.fromhex("c0035fd6")
MAX_FARMER, MAX_EAGLE = 4, 1


def b_insn(pc, target, link=False):
    off = (target - pc) // 4
    assert -(1 << 25) <= off < (1 << 25)
    return struct.pack("<I", (0x94000000 if link else 0x14000000) | (off & 0x3ffffff))


def adrp(pc, target, rd=0):
    imm = ((target & ~0xfff) - (pc & ~0xfff)) >> 12
    return struct.pack("<I", 0x90000000 | ((imm & 3) << 29) | (((imm >> 2) & 0x7ffff) << 5) | rd)


def assemble(src):
    s = open(src, encoding="utf-8").read()
    for k, v in SYMS.items():
        s = s.replace("S_" + k, "start + %d" % (v - CAVE))
    s = s.replace("S_EDITMODE_LO", str(EDITMODE & 0xfff)).replace("MAX_FARMER", str(MAX_FARMER)).replace("MAX_EAGLE", str(MAX_EAGLE))
    s = "\n".join(l.split("//")[0] for l in s.splitlines()) + "\n"
    with tempfile.TemporaryDirectory() as d:
        a, o, b = (os.path.join(d, n) for n in ("a.s", "a.o", "a.bin"))
        open(a, "w").write(".text\n" + s)
        subprocess.check_call(["llvm-mc", "--triple=aarch64", "-filetype=obj", "-o", o, a])
        rel = subprocess.run(["llvm-readobj", "-r", o], capture_output=True, text=True).stdout
        assert "R_AARCH64" not in rel, "còn relocation chưa giải:\n" + rel
        subprocess.check_call(["llvm-objcopy", "-O", "binary", "--only-section=.text", o, b])
        code = bytearray(open(b, "rb").read())
        syms = subprocess.run(["llvm-nm", o], capture_output=True, text=True).stdout
    labels = {l.split()[-1]: int(l.split()[0], 16) for l in syms.splitlines() if len(l.split()) == 3}
    i = 0
    while True:
        i = code.find(struct.pack("<I", 0xadadadad), i)
        if i < 0:
            break
        code[i:i + 4] = adrp(CAVE + i, EDITMODE)
    return bytes(code), labels


def main(lib=None):
    code, lab = assemble(os.path.join(HERE, "village.s"))
    assert len(code) <= CAVE_SIZE, len(code)
    patches = [
        {"name": "Dê + đại bàng: mã mới (vùng TutorialMgr::addCheatFinishTutButton)", "addr": CAVE,
         "old": None, "new": code.hex()},
        {"name": "CityMgr::createFarmer -> mã mới", "addr": CREATE_FARMER, "old": RET.hex(),
         "new": b_insn(CREATE_FARMER, CAVE + lab["farmer"]).hex()},
        {"name": "CityMgr::createAngryBird -> mã mới", "addr": CREATE_EAGLE, "old": RET.hex(),
         "new": b_insn(CREATE_EAGLE, CAVE + lab["eagle"]).hex()},
    ]
    if lib:
        raw = open(lib, "rb").read()
        patches[0]["old"] = raw[CAVE:CAVE + len(code)].hex()
        for p in patches:
            assert raw[p["addr"]:p["addr"] + len(p["new"]) // 2].hex() == p["old"], p["name"]
    else:
        old = json.load(open(OUT)) if os.path.exists(OUT) else {}
        prev = {p["addr"]: p for p in old.get("patches", [])}
        if CAVE in prev and len(prev[CAVE]["old"]) >= len(code.hex()):
            patches[0]["old"] = prev[CAVE]["old"][:len(code.hex())]
        else:
            raise SystemExit("Cần đường dẫn libcocos2dcpp.so gốc để lấy byte cũ của vùng trống")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    doc = {"_ghi_chu": "Bản vá mã máy libcocos2dcpp.so (arm64-v8a, Thời Loạn 7.6.12). addr = vị trí trong file "
                       "(= địa chỉ ảo, đoạn mã nạp ở 0). Bộ nạp chỉ vá khi mọi byte 'old' khớp. Sinh bởi tools/native/build.py.",
           "lib_size": len(raw) if lib else old.get("lib_size"), "patches": patches}
    json.dump(doc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Đã ghi", OUT, "(%d byte mã mới)" % len(code))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
