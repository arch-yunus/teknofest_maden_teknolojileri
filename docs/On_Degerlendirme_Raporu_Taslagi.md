# DeepMine AI - Ön Değerlendirme Raporu (ÖDR)
**TEKNOFEST 2026 Maden Teknolojileri Yarışması**
**Kategori:** Yükseköğretim ve Mezunlar
**Tema:** 4.2 Otonom Madencilik, Yapay Zeka Entegrasyonu ve İş Güvenliği

---

## 1. Proje Özeti
DeepMine AI; yer altı madenciliği için geliştirilmiş, 9 modülden oluşan bütünleşik bir otonom teknoloji ekosistemidir. GPS-denied ortamlarda LiDAR+IMU+Odom füzyonu ile navigasyon yapan araçlar, hibrit GPR-NN modelleriyle 3D rezerv modellemesi yapan ve üretimi optimize eden AI katmanları, su kuyusu otomasyonu ve otonom İHA denetimi ile güçlendirilmiş akıllı İSG sistemlerini kapsar.

## 2. Sorun ve Çözüm Yaklaşımı
### 2.1. Belirlenen Sorunlar:
1.  **Navigasyon Belirsizliği:** Yeraltı galerilerinde sadece LiDAR/Odom kullanımının birikimli hata (drift) riski.
2.  **Üretim Verimliliği:** Rezerv verisinin statik kalması ve dinamik üretim planlamasının eksikliği.
3.  **Su Baskını ve Denetim Zorluğu:** Derin kuyuların manuel takibi ve tehlikeli bölgelere ulaşım zorluğu.
4.  **Ekipman Arızaları:** Plansız duruşların yarattığı operasyonel darboğazlar.

### 2.2. Sunulan Çözümler:
1.  **Füzyon Navigasyonu (4.2.1):** LiDAR, IMU ve Odometer verileri EKF (Extended Kalman Filter) ile birleştirilerek "Zero-Drift" navigasyon hedeflenmiştir.
2.  **Akıllı Üretim Optimizasyonu (4.2.2):** Hibrit GPR-NN modelleriyle oluşturulan 3D haritalar üzerinden en yüksek tenörlü ve en güvenli yollar AI ile otomatik planlanır.
3.  **Bütünleşik İSG ve Otomasyon (4.2.3):**
    *   **Su Kuyusu Otomasyonu:** AI destekli debi ve risk kontrolü ile baskın önleme.
    *   **Otonom İHA (Drone):** Tehlikeli bölgelerin termal/görsel analizi için otonom denetim sistemi.
    *   **Gelişmiş İSG Ajanı:** Personel fizyolojisi (nabız, yorulma) ve çevresel sarsıntıları içeren 7-katmanlı risk analizi.
4.  **Kestirimci Bakım:** RUL (Kalan Ömür) tahmini ve Isolation Forest ile sıfırıncı gün arıza tespiti.

## 3. Yenilikçi (İnovatif) Yönü
Projemiz, TEKNOFEST şartnamesindeki tüm alt başlıkları (4.2.1, 4.2.2, 4.2.3) tek bir ROS 2 çatısı altında senkronize eden ilk yerli çözümlerdendir. Özellikle "bilmiyorum" diyebilen belirsizlik tabanlı rezerv AI ve otonom İHA'nın İSG sistemiyle doğrudan (request-based) entegrasyonu inovatif derinliğimizi oluşturur.

## 4. Uygulanabilirlik ve Sektörel Fayda
DeepMine AI, modüler yapısı sayesinde mevcut maden araçlarına (LHD'ler, kamyonlar) ve sensör ağlarına "Tak-Çalıştır" şeklinde entegre edilebilir. %100 yerli yazılım altyapısı ile operasyonel maliyetleri %30 düşürmeyi ve İSG risklerini %80 azaltmayı hedefler.

## 5. Kullanılan Teknolojiler
- **Navigasyon:** LiDAR SLAM, EKF Fusion, RRT*, APF
- **Yapay Zeka:** TensorFlow (Hybrid GPR-NN), Scikit-Learn (Isolation Forest, RF)
- **Otomasyon:** ROS 2 Humble, Python 3.10, C++ 17, Gazebo
- **İSG:** IoT Sensor Hub, Wearable Physiological Monitoring

---
*Hazırlayan: Bahattin Yunus · TEKNOFEST 2026*
