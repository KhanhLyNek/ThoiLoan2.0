package com.vng.Downloader;

/**
 * Nạp G trên server riêng: AndroidPlatform.purchaseAnItem(sku) (mua gói G bằng Google Play) được nối tắt tới đây,
 * tạo đơn hàng giả rồi gọi thẳng ThoiLoan.onPurchaseSuccess(json, chữ ký) như khi Google Play báo mua xong
 * -> native CityMgr::validateGoogleIap gửi lệnh 12005 -> server cộng G (tlm/handlers/payment.py).
 * Không mở Google Play nên game không bị đẩy ra ngoài / văng. consumePurchase cũng bị tắt (build.py).
 */
public class TlmFreePay {
    public static void buy(String sku) {
        long now = System.currentTimeMillis();
        String s = sku == null ? "" : sku.replace("\\", "").replace("\"", "");
        String json = "{\"orderId\":\"TL." + now + "\",\"packageName\":\"gsn.zps.thoiloan\",\"productId\":\"" + s
                + "\",\"purchaseTime\":" + now + ",\"purchaseState\":0,\"purchaseToken\":\"tl" + now + "\"}";
        TlmObbGate.report("mua gói " + s + " (nạp thẳng qua server, không qua Google Play)");
        com.vng.thoiloan.ThoiLoan.onPurchaseSuccess(json, "");
    }
}
