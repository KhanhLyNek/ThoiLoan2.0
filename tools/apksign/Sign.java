// Ký APK v1 + v2 + v3 bằng thư viện apksig của Google (com.android.tools.build:apksig).
// java -cp apksig.jar:. Sign <khoá.pk8> <chứng-chỉ.x509.pem> <vào.apk> <ra.apk> [minSdk]
import com.android.apksig.ApkSigner;
import java.io.File;
import java.io.FileInputStream;
import java.nio.file.Files;
import java.security.KeyFactory;
import java.security.PrivateKey;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.security.spec.PKCS8EncodedKeySpec;
import java.util.Collections;

public class Sign {
    public static void main(String[] a) throws Exception {
        PrivateKey key = KeyFactory.getInstance("RSA").generatePrivate(
                new PKCS8EncodedKeySpec(Files.readAllBytes(new File(a[0]).toPath())));
        X509Certificate cert;
        try (FileInputStream in = new FileInputStream(a[1])) {
            cert = (X509Certificate) CertificateFactory.getInstance("X.509").generateCertificate(in);
        }
        ApkSigner.SignerConfig sc = new ApkSigner.SignerConfig.Builder(
                "ANDROID", key, Collections.singletonList(cert)).build();
        ApkSigner.Builder b = new ApkSigner.Builder(Collections.singletonList(sc))
                .setInputApk(new File(a[2])).setOutputApk(new File(a[3]))
                .setV1SigningEnabled(true).setV2SigningEnabled(true).setV3SigningEnabled(true);
        if (a.length > 4) b.setMinSdkVersion(Integer.parseInt(a[4]));
        b.build().sign();
        System.out.println("Đã ký: " + a[3]);
    }
}
