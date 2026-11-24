// ThoiLoan2.0: dê (Farmer, ảnh GOA_1) và đại bàng (Eagle) đi lại trong làng.
// Game gốc 7.6.12 đã rút ruột CityMgr::createFarmer / createAngryBird thành "ret"; CityMgr::loop vẫn gọi
// hai hàm này mỗi 300 nhịp. Mã dưới đây đặt vào vùng của TutorialMgr::addCheatFinishTutButton (hàm chết,
// không ai gọi) và hai hàm rỗng được sửa thành "b" tới đây.
// Ký hiệu S_xxx = địa chỉ tuyệt đối, được tools/native/build.py thay bằng "start + (xxx - CAVE)".
start:
farmer:                                 // x0 = CityMgr*, w1 bỏ qua
    stp x29, x30, [sp, #-48]!
    mov x29, sp
    stp x19, x20, [sp, #16]
    mov x19, x0
    .inst 0xadadadad                    // adrp x0, trang của isEditMode (build.py tính)
    ldrb w0, [x0, #S_EDITMODE_LO]       // GameDataMgr::isEditMode: đang sắp xếp làng -> thôi
    cbnz w0, 1f
    ldr x0, [x19, #0xb8]                // vector<Farmer*>*
    cbz x0, 1f
    ldp x1, x2, [x0]
    sub x2, x2, x1
    cmp x2, #(MAX_FARMER * 8)
    b.ge 1f
    mov x0, #0xb0
    bl S_NEW
    mov x20, x0
    bl S_FARMER_CTOR
    lsr x1, x20, #4                     // id riêng cho từng con (removeFarmer tìm theo id)
    and w1, w1, #0x7fffffff
    mov x0, x20
    bl S_FARMER_CREATE
    str x20, [sp, #32]
    ldr x0, [x19, #0xb8]
    add x1, sp, #32
    bl S_PUSH_BACK
1:  ldp x19, x20, [sp, #16]
    ldp x29, x30, [sp], #48
    ret

eagle:                                  // x0 = CityMgr*
    stp x29, x30, [sp, #-48]!
    mov x29, sp
    stp x19, x20, [sp, #16]
    mov x19, x0
    .inst 0xadadadad                    // adrp x0, trang của isEditMode (build.py tính)
    ldrb w0, [x0, #S_EDITMODE_LO]
    cbnz w0, 2f
    ldr x0, [x19, #0xc0]                // vector<Eagle*>*
    cbz x0, 2f
    ldp x1, x2, [x0]
    sub x2, x2, x1
    cmp x2, #(MAX_EAGLE * 8)
    b.ge 2f
    mov x0, #0x90
    bl S_NEW
    mov x20, x0
    bl S_EAGLE_CTOR
    lsr x1, x20, #4
    and w1, w1, #0x7fffffff
    mov x0, x20
    bl S_EAGLE_CREATE
    str x20, [sp, #32]
    ldr x0, [x19, #0xc0]
    add x1, sp, #32
    bl S_PUSH_BACK
2:  ldp x19, x20, [sp, #16]
    ldp x29, x30, [sp], #48
    ret
