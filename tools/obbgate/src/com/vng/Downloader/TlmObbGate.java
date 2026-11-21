package com.vng.Downloader;

import android.app.Activity;
import com.google.android.vending.expansion.downloader.Helpers;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.RandomAccessFile;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Thay trình tải OBB của Google Play (không còn dùng được) trong SampleDownloaderActivity.onCreate:
 * thiếu main.1380.<gói>.obb -> tự tải từ server riêng (/obb), không có thì từ Google Drive,
 * hiện tiến độ trên màn hình chờ của game (setText/setPercent native), tải tiếp được khi đứt mạng,
 * xong thì gọi validateXAPKZipFiles() (game tự kiểm CRC rồi startLoadGame()).
 * Cùng gói com.vng.Downloader để gọi được validateXAPKZipFiles() (phạm vi gói).
 */
public class TlmObbGate implements Runnable {
    static final long SIZE = 45330886L;
    static final String[] SOURCES = {
        "http://127.0.0.1:8080/obb",
        "https://drive.google.com/uc?export=download&id=1fsCjbF8orh-TIa45we2l83Bd8ePecscm",
    };
    final SampleDownloaderActivity act;
    long lastUi;

    TlmObbGate(SampleDownloaderActivity a) { act = a; }

    /** Nhánh "đã có OBB" của onCreate: gắn lại OBB (phòng lần gắn đầu hụt), báo chẩn đoán về server, rồi kiểm tra như cũ. */
    public static void delivered(SampleDownloaderActivity a) {
        try {
            Activity ctx = SampleDownloaderActivity.mainActivity;
            String path = Helpers.generateSaveFileName(ctx, Helpers.getExpansionAPKFileName(ctx, true, 1380));
            int rc = mount(path);
            report("có sẵn OBB, " + describe(path) + ", gắn lại -> " + rc);
        } catch (Throwable e) {
            report("có sẵn OBB, lỗi khi gắn lại: " + e);
        }
        a.validateXAPKZipFiles();
    }

    static int mount(String path) {
        try { return com.vng.thoiloan.ThoiLoan.addResourceFile(path); } catch (Throwable e) { return -999; }
    }

    static String describe(String path) {
        File f = new File(path);
        int sdk = -1;
        try { sdk = Class.forName("android.os.Build$VERSION").getField("SDK_INT").getInt(null); } catch (Throwable e) { }
        return "Android SDK " + sdk + ", " + path + " tồn tại=" + f.exists() + " đọc được=" + f.canRead()
                + " cỡ=" + f.length() + (f.length() == SIZE ? " (đúng)" : " (SAI, cần " + SIZE + ")");
    }

    /** Gửi một dòng chẩn đoán về server (/obblog) để hiện trong log.txt. Chạy nền, lỗi thì bỏ qua. */
    static void report(final String msg) {
        Thread t = new Thread(new Runnable() { public void run() {
            try {
                HttpURLConnection c = (HttpURLConnection) new URL(SOURCES[0].replace("/obb", "/obblog?m=")
                        + java.net.URLEncoder.encode(msg, "UTF-8")).openConnection();
                c.setConnectTimeout(3000); c.setReadTimeout(3000);
                c.getResponseCode(); c.disconnect();
            } catch (Throwable e) { }
        } });
        t.setDaemon(true);
        t.start();
    }

    /** APK đã chứa sẵn dữ liệu OBB (patch_apk.py --embed-obb)? Game đọc thẳng assets/ trong APK, không cần file OBB. */
    static boolean embedded() {
        try {
            return TlmObbGate.class.getClassLoader().getResource("assets/800_480/Content/cloud_1.png") != null;
        } catch (Throwable e) { return false; }
    }

    public static void start(SampleDownloaderActivity a) {
        if (embedded()) {
            report("APK có sẵn dữ liệu OBB -> vào game, không cần tải");
            Activity c = SampleDownloaderActivity.mainActivity;
            c.runOnUiThread(new Runnable() { public void run() { SampleDownloaderActivity.startLoadGame(); } });
            return;
        }
        Thread t = new Thread(new TlmObbGate(a), "TlmObbGate");
        t.setDaemon(true);
        t.start();
    }

    void ui(final String text, final int percent) {
        final Activity c = SampleDownloaderActivity.mainActivity;
        if (c == null) return;
        c.runOnUiThread(new Runnable() {
            public void run() {
                try {
                    SampleDownloaderActivity.setText(text);
                    if (percent >= 0) SampleDownloaderActivity.setPercent(percent);
                } catch (Throwable e) { /* bỏ qua lỗi giao diện */ }
            }
        });
    }

    static String mb(long n) { return String.format("%.1f MB", n / 1048576.0); }

    public void run() {
        Activity ctx = SampleDownloaderActivity.mainActivity;
        report("thiếu OBB, bắt đầu tải");
        try { ctx.getObbDir(); } catch (Throwable e) { /* tạo thư mục obb của app */ }
        File dst = new File(Helpers.generateSaveFileName(ctx, Helpers.getExpansionAPKFileName(ctx, true, 1380)));
        File dir = dst.getParentFile();
        if (dir != null) dir.mkdirs();
        File tmp = new File(dst.getPath() + ".tmp");
        for (int round = 1; ; round++) {
            for (String src : SOURCES) {
                try {
                    ui("Đang tải dữ liệu game" + (src.contains("drive") ? " (Google Drive)" : " (máy chủ)") + "...", -1);
                    if (fetch(src, tmp)) {
                        if (tmp.length() == SIZE) {
                            dst.delete();
                            if (!tmp.renameTo(dst)) throw new Exception("không đổi tên được file tải về");
                            ui("Tải xong, đang kiểm tra dữ liệu...", 100);
                            final SampleDownloaderActivity a = act;
                            final String path = dst.getPath();
                            ctx.runOnUiThread(new Runnable() { public void run() {
                                // ThoiLoan.checkResource() đã gọi addResouceZFile() lúc file CHƯA có -> gắn hụt.
                                // Gắn lại OBB vừa tải trước khi cho vào game (thiếu thì văng ở LoadingGui: cloud_1.png).
                                int rc = mount(path);
                                report("tải xong OBB, " + describe(path) + ", gắn -> " + rc);
                                a.validateXAPKZipFiles();
                            } });
                            return;
                        }
                        tmp.delete();               // sai kích thước -> tải lại từ đầu
                    }
                } catch (Throwable e) {
                    ui("Lỗi tải: " + e.getMessage() + " - thử lại sau 5 giây (lần " + round + ")", -1);
                    report("lỗi tải từ " + src + ": " + e);
                    try { Thread.sleep(5000); } catch (InterruptedException ie) { return; }
                }
            }
            try { Thread.sleep(3000); } catch (InterruptedException ie) { return; }
        }
    }

    /** Tải về tmp (nối tiếp nếu có một phần). false = nguồn không có file (thử nguồn sau). */
    boolean fetch(String url, File tmp) throws Exception {
        long have = tmp.isFile() ? tmp.length() : 0;
        if (have > SIZE) { tmp.delete(); have = 0; }
        if (have == SIZE) return true;
        String cur = url;
        HttpURLConnection c = null;
        for (int hop = 0; hop < 10; hop++) {
            c = (HttpURLConnection) new URL(cur).openConnection();
            c.setInstanceFollowRedirects(false);
            c.setConnectTimeout(8000);
            c.setReadTimeout(30000);
            c.setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android) ThoiLoanObb");
            if (have > 0) c.setRequestProperty("Range", "bytes=" + have + "-");
            int code = c.getResponseCode();
            String loc = c.getHeaderField("Location");
            if (code >= 300 && code < 400 && loc != null) {
                cur = new URL(new URL(cur), loc).toString();
                c.disconnect();
                continue;
            }
            if (code == 404) { c.disconnect(); return false; }
            if (code == 416) { c.disconnect(); return tmp.length() == SIZE; }
            if (code != 200 && code != 206) { c.disconnect(); throw new Exception("HTTP " + code); }
            String type = c.getContentType();
            if (type != null && type.startsWith("text/html")) {      // trang "quét virus" của Google Drive
                String html = readAll(c.getInputStream());
                c.disconnect();
                String next = driveConfirm(html);
                if (next == null) throw new Exception("Drive trả trang web thay vì file (link phải để công khai)");
                cur = next;
                continue;
            }
            break;
        }
        if (c == null) return false;
        boolean append = c.getResponseCode() == 206 && have > 0;
        if (!append) have = 0;
        InputStream in = c.getInputStream();
        FileOutputStream out = new FileOutputStream(tmp, append);
        byte[] buf = new byte[256 * 1024];
        long got = have;
        int n;
        try {
            while ((n = in.read(buf)) > 0) {
                out.write(buf, 0, n);
                got += n;
                long now = System.currentTimeMillis();
                if (now - lastUi > 400) {
                    lastUi = now;
                    ui("Đang tải dữ liệu game: " + mb(got) + " / " + mb(SIZE), (int) (got * 100 / SIZE));
                }
            }
        } finally {
            out.close();
            in.close();
            c.disconnect();
        }
        if (got < SIZE) throw new Exception("mất kết nối giữa chừng (" + mb(got) + "), đang tải tiếp");
        RandomAccessFile r = new RandomAccessFile(tmp, "r");
        int b0 = r.read(), b1 = r.read();
        r.close();
        if (b0 != 'P' || b1 != 'K') { tmp.delete(); throw new Exception("file tải về không phải OBB"); }
        return true;
    }

    static String readAll(InputStream in) throws Exception {
        java.io.ByteArrayOutputStream b = new java.io.ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int n;
        while ((n = in.read(buf)) > 0 && b.size() < 2 * 1024 * 1024) b.write(buf, 0, n);
        in.close();
        return b.toString("UTF-8");
    }

    static String driveConfirm(String html) {
        Matcher action = Pattern.compile("action=\"([^\"]+)\"").matcher(html);
        if (!action.find()) return null;
        StringBuilder u = new StringBuilder(action.group(1).replace("&amp;", "&"));
        Matcher m = Pattern.compile("name=\"([^\"]+)\"\\s+value=\"([^\"]*)\"").matcher(html);
        char sep = u.indexOf("?") >= 0 ? '&' : '?';
        while (m.find()) {
            u.append(sep).append(m.group(1)).append('=').append(m.group(2));
            sep = '&';
        }
        return u.toString();
    }
}
