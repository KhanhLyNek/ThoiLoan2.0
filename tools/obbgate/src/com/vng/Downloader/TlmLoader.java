package com.vng.Downloader;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.RandomAccessFile;
import java.util.ArrayList;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/**
 * ThoiLoan2.0 - BỘ NẠP BẢN VÁ. Thay System.loadLibrary("cocos2dcpp") (ThoiLoan.<clinit>, ZingPlayReferrer).
 *
 * Mỗi lần mở game: hỏi server http://127.0.0.1:8080/patch/native.txt (danh sách bản vá mã máy, dạng
 * "địa_chỉ_hex byte_cũ_hex byte_mới_hex" mỗi dòng), sao chép libcocos2dcpp.so gốc của APK vào
 * files/tlm/, ghi các byte mới (chỉ khi MỌI byte cũ khớp), rồi System.load bản đã vá.
 * Bản đã vá được giữ lại theo mã băm danh sách -> lần sau không phải vá lại; server tắt thì dùng danh sách lần trước.
 * Có lỗi bất kỳ -> nạp lib gốc như game thường (không bao giờ làm game không vào được).
 */
public class TlmLoader {
    static final String URL_HOST = "127.0.0.1";
    static final int URL_PORT = 8080;
    static boolean loaded;
    static final StringBuilder note = new StringBuilder();

    public static synchronized void load(String name) {
        if (loaded) return;
        String path = null;
        try {
            path = prepare(name);
        } catch (Throwable e) {
            note.append("lỗi chuẩn bị: ").append(e);
        }
        if (path != null) {
            try {
                System.load(path);
                loaded = true;
                TlmObbGate.report("bộ nạp: đã nạp lib vá " + new File(path).getName() + " " + note);
                return;
            } catch (Throwable e) {
                note.append(" | System.load lỗi: ").append(e);
            }
        }
        System.loadLibrary(name);
        loaded = true;
        TlmObbGate.report("bộ nạp: dùng lib gốc. " + note);
    }

    static Object app() throws Exception {
        Class<?> at = Class.forName("android.app.ActivityThread");
        return at.getMethod("currentApplication").invoke(null);
    }

    static String prepare(String name) throws Exception {
        if (!String.valueOf(System.getProperty("os.arch")).contains("64")) {
            note.append("máy 32-bit, bỏ qua vá");
            return null;
        }
        Object ctx = app();
        if (ctx == null) { note.append("chưa có Application"); return null; }
        Object ai = ctx.getClass().getMethod("getApplicationInfo").invoke(ctx);
        String libDir = (String) ai.getClass().getField("nativeLibraryDir").get(ai);
        String apk = (String) ai.getClass().getField("sourceDir").get(ai);
        File files = (File) ctx.getClass().getMethod("getFilesDir").invoke(ctx);
        File dir = new File(files, "tlm");
        dir.mkdirs();

        File list = new File(dir, "native.txt");
        byte[] fresh = fetch("/patch/native.txt", 2500);
        if (fresh != null) {
            writeFile(list, fresh);
            note.append("danh sách từ server; ");
        } else if (list.isFile()) {
            note.append("server không trả lời, dùng danh sách cũ; ");
        } else {
            note.append("không có danh sách vá");
            return null;
        }
        byte[] txt = readFile(list);
        ArrayList<long[]> addrs = new ArrayList<long[]>();
        ArrayList<byte[][]> bytes = new ArrayList<byte[][]>();
        long wantSize = -1;
        for (String ln : new String(txt, "UTF-8").split("\n")) {
            ln = ln.trim();
            if (ln.length() == 0 || ln.startsWith("#")) continue;
            String[] p = ln.split("\\s+");
            if (p[0].equals("size")) { wantSize = Long.parseLong(p[1]); continue; }
            addrs.add(new long[] { Long.parseLong(p[0], 16) });
            bytes.add(new byte[][] { hex(p[1]), hex(p[2]) });
        }
        if (addrs.isEmpty()) { note.append("danh sách rỗng"); return null; }

        File orig = new File(libDir, "lib" + name + ".so");
        long stamp = new File(apk).lastModified();
        String key = Integer.toHexString(java.util.Arrays.hashCode(txt)) + "_" + Long.toHexString(stamp);
        File out = new File(dir, "lib" + name + "_" + key + ".so");
        if (out.isFile() && out.length() > 0) { note.append("dùng bản vá có sẵn"); return out.getPath(); }

        File tmp = new File(dir, "lib" + name + ".tmp");
        if (orig.isFile()) {
            copy(new FileInputStream(orig), new FileOutputStream(tmp));
        } else {
            ZipFile z = new ZipFile(apk);
            try {
                ZipEntry e = z.getEntry("lib/arm64-v8a/lib" + name + ".so");
                if (e == null) { note.append("không thấy lib trong APK"); return null; }
                copy(z.getInputStream(e), new FileOutputStream(tmp));
            } finally { z.close(); }
        }
        if (wantSize > 0 && tmp.length() != wantSize) {
            note.append("lib khác bản (" + tmp.length() + " != " + wantSize + "), không vá");
            tmp.delete();
            return null;
        }
        RandomAccessFile f = new RandomAccessFile(tmp, "rw");
        try {
            for (int i = 0; i < addrs.size(); i++) {
                long a = addrs.get(i)[0];
                byte[] old = bytes.get(i)[0], neu = bytes.get(i)[1];
                byte[] cur = new byte[old.length];
                f.seek(a);
                f.readFully(cur);
                if (!java.util.Arrays.equals(cur, old)) {
                    note.append("byte cũ không khớp ở 0x" + Long.toHexString(a) + ", không vá");
                    f.close();
                    tmp.delete();
                    return null;
                }
            }
            for (int i = 0; i < addrs.size(); i++) {
                f.seek(addrs.get(i)[0]);
                f.write(bytes.get(i)[1]);
            }
        } finally { f.close(); }
        File[] olds = dir.listFiles();
        if (olds != null) for (File o : olds)
            if (o.getName().startsWith("lib" + name + "_") && o.getName().endsWith(".so")) o.delete();
        if (!tmp.renameTo(out)) { note.append("không đổi tên được"); return null; }
        note.append("đã vá " + addrs.size() + " chỗ");
        return out.getPath();
    }

    /** GET http://127.0.0.1:8080<path> trên luồng riêng (luồng chính cấm mạng), chờ tối đa ms. */
    static byte[] fetch(final String path, int ms) {
        final byte[][] res = new byte[1][];
        Thread t = new Thread(new Runnable() { public void run() {
            java.net.Socket s = new java.net.Socket();
            try {
                s.connect(new java.net.InetSocketAddress(URL_HOST, URL_PORT), 1500);
                s.setSoTimeout(2000);
                s.getOutputStream().write(("GET " + path + " HTTP/1.0\r\nHost: " + URL_HOST + "\r\n\r\n").getBytes("UTF-8"));
                InputStream in = new java.io.BufferedInputStream(s.getInputStream());
                String[] st = TlmObbGate.line(in).split(" ");
                if (st.length < 2 || !st[1].equals("200")) return;
                while (TlmObbGate.line(in).length() > 0) { }
                java.io.ByteArrayOutputStream b = new java.io.ByteArrayOutputStream();
                byte[] buf = new byte[8192];
                for (int n; (n = in.read(buf)) > 0; ) b.write(buf, 0, n);
                res[0] = b.toByteArray();
            } catch (Throwable e) {
            } finally {
                try { s.close(); } catch (Throwable e) { }
            }
        } });
        t.setDaemon(true);
        t.start();
        try { t.join(ms); } catch (InterruptedException e) { }
        return res[0];
    }

    static byte[] hex(String s) {
        if (s.equals("-")) return new byte[0];
        byte[] b = new byte[s.length() / 2];
        for (int i = 0; i < b.length; i++) b[i] = (byte) Integer.parseInt(s.substring(2 * i, 2 * i + 2), 16);
        return b;
    }

    static void copy(InputStream in, OutputStream out) throws Exception {
        try {
            byte[] buf = new byte[1 << 16];
            for (int n; (n = in.read(buf)) > 0; ) out.write(buf, 0, n);
        } finally { in.close(); out.close(); }
    }

    static byte[] readFile(File f) throws Exception {
        java.io.ByteArrayOutputStream b = new java.io.ByteArrayOutputStream();
        copy(new FileInputStream(f), b);
        return b.toByteArray();
    }

    static void writeFile(File f, byte[] d) throws Exception {
        OutputStream o = new FileOutputStream(f);
        try { o.write(d); } finally { o.close(); }
    }
}
