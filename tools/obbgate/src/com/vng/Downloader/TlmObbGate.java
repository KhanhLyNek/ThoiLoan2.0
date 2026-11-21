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
    /** Phản hồi HTTP tối giản. http:// đi qua Socket tự viết: app targetSdk 29 bị Android cấm HTTP thường
     *  (cleartext) với HttpURLConnection, nên tải từ server 127.0.0.1 / báo chẩn đoán trước đây đều hỏng âm thầm. */
    static class Resp {
        int code; String type, location; long length = -1; InputStream in;
        java.net.Socket sock; HttpURLConnection conn;
        void close() {
            try { if (in != null) in.close(); } catch (Throwable e) { }
            try { if (sock != null) sock.close(); } catch (Throwable e) { }
            if (conn != null) conn.disconnect();
        }
    }

    static Resp open(String url, long have) throws Exception {
        URL u = new URL(url);
        Resp r = new Resp();
        if ("http".equals(u.getProtocol())) {
            int port = u.getPort() > 0 ? u.getPort() : 80;
            r.sock = new java.net.Socket();
            r.sock.connect(new java.net.InetSocketAddress(u.getHost(), port), 8000);
            r.sock.setSoTimeout(30000);
            String path = u.getFile().length() > 0 ? u.getFile() : "/";
            String req = "GET " + path + " HTTP/1.0\r\nHost: " + u.getHost() + ":" + port
                    + "\r\nUser-Agent: ThoiLoanObb\r\n" + (have > 0 ? "Range: bytes=" + have + "-\r\n" : "") + "\r\n";
            r.sock.getOutputStream().write(req.getBytes("UTF-8"));
            InputStream in = new java.io.BufferedInputStream(r.sock.getInputStream(), 65536);
            String[] parts = line(in).split(" ");
            r.code = parts.length > 1 ? Integer.parseInt(parts[1]) : 0;
            for (String h = line(in); h.length() > 0; h = line(in)) {
                int i = h.indexOf(':');
                if (i < 0) continue;
                String k = h.substring(0, i).trim().toLowerCase(), v = h.substring(i + 1).trim();
                if (k.equals("content-type")) r.type = v;
                else if (k.equals("location")) r.location = v;
                else if (k.equals("content-length")) r.length = Long.parseLong(v);
            }
            r.in = in;
            return r;
        }
        HttpURLConnection c = (HttpURLConnection) u.openConnection();
        c.setInstanceFollowRedirects(false);
        c.setConnectTimeout(8000);
        c.setReadTimeout(30000);
        c.setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android) ThoiLoanObb");
        if (have > 0) c.setRequestProperty("Range", "bytes=" + have + "-");
        r.conn = c;
        r.code = c.getResponseCode();
        r.type = c.getContentType();
        r.location = c.getHeaderField("Location");
        r.length = c.getContentLength();
        if (r.code < 400) r.in = c.getInputStream();
        return r;
    }

    static String line(InputStream in) throws Exception {
        StringBuilder b = new StringBuilder();
        int ch;
        while ((ch = in.read()) >= 0 && ch != '\n') if (ch != '\r') b.append((char) ch);
        return b.toString();
    }

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
                open(SOURCES[0].replace("/obb", "/obblog?m=") + java.net.URLEncoder.encode(msg, "UTF-8"), 0).close();
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
        Resp c = null;
        for (int hop = 0; hop < 10; hop++) {
            c = open(cur, have);
            if (c.code >= 300 && c.code < 400 && c.location != null) {
                cur = new URL(new URL(cur), c.location).toString();
                c.close();
                continue;
            }
            if (c.code == 404) { c.close(); return false; }
            if (c.code == 416) { c.close(); return tmp.length() == SIZE; }
            if (c.code != 200 && c.code != 206) { c.close(); throw new Exception("HTTP " + c.code); }
            if (c.type != null && c.type.startsWith("text/html")) {      // trang "quét virus" của Google Drive
                String html = readAll(c.in);
                c.close();
                String next = driveConfirm(html);
                if (next == null) throw new Exception("Drive trả trang web thay vì file (link phải để công khai)");
                cur = next;
                continue;
            }
            break;
        }
        if (c == null) return false;
        boolean append = c.code == 206 && have > 0;
        if (!append) have = 0;
        FileOutputStream out = new FileOutputStream(tmp, append);
        byte[] buf = new byte[256 * 1024];
        long got = have;
        int n;
        try {
            while ((n = c.in.read(buf)) > 0) {
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
            c.close();
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
