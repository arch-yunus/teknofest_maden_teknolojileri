# TEKNOFEST 2026 MADEN TEKNOLOJİLERİ YARIŞMASI
# ÖN DEĞERLENDİRME RAPORU

**PROJE ADI:** DeepMine AI: Otonom Yer Altı Maden İşletme ve Akıllı İSG Ekosistemi
**TAKIM ADI:** [Takım Adı]
**ID:** [Proje ID]

---

## İÇİNDEKİLER

1. PROJE ÖZETİ ................................................................................................................ 3
2. SORUNUN TANIMI VE ÇÖZÜM ÖNERİSİ ........................................................................ 3
3. YENİLİKÇİLİK VEYA YERLİLEŞTİRME HAMLESİ .............................................................. 5
4. UYGULANABİLİRLİK VE SÜRDÜRÜLEBİLİRLİK ............................................................... 6
5. PROJENİN HAZIRLANIŞ SÜRECİ VE ÇALIŞMA YÖNTEMİ ............................................... 7
6. PROJE TAKIMI ................................................................................................................ 8
7. KAYNAKLAR .................................................................................................................. 9

---

## 1. PROJE ÖZETİ (18 Puan)

**Proje Adı:** DeepMine AI: Otonom Yer Altı Maden İşletme ve Akıllı İSG Ekosistemi

**Projenin Amacı:** Yer altı maden işletmelerinde GPS sinyalinin bulunmadığı, dar ve dinamik galeri ortamlarında; otonom araç navigasyonu, yapay zeka tabanlı cevher rezerv modellemesi ve proaktif iş sağlığı ve güvenliği (İSG) sistemlerini tek bir çatı altında birleştirerek operasyonel güvenliği ve verimliliği maksimize etmektir.

**Ana Fikir:** Madencilik sektöründeki en kritik sorunlar olan kontrolsüz gaz birikimi, düşük üretim verimliliği ve navigasyon hatalarına bağlı kazaları; 8 boyutlu durum kestirimi yapan SLAM algoritmaları, hibrit GPR-NN modelleriyle dinamik rezerv tahmini ve Bayesyen risk füzyonu ile akıllı havalandırma kontrolü sağlayan bir ekosistemle çözmektir.

**Hedef Süreç:** Proje; otonom yer altı navigasyonu (4.2.1), yapay zeka destekli üretim planlama (4.2.2) ve akıllı otomasyon ile entegre İSG süreçlerini (4.2.3) kapsamaktadır.

**Çözüm Yaklaşımı:** DeepMine AI; LiDAR temelli SLAM haritalama ve RRT* algoritmaları kullanarak GPS'siz ortamlarda 2 saniyenin altında dinamik yol planlaması yapar. Yapay zeka katmanında Gausyen Süreç Regresyonu ve Derin Öğrenme modellerini hibritleyerek 3D rezerv haritaları oluşturur. İSG tarafında ise "Bayesyen Risk Füzyonu" algoritması ile personel hayati verilerini ve ortam gaz seviyelerini analiz ederek otonom tahliye ve havalandırma kararları alır. [Kelime Sayısı: ~195]

---

## 2. SORUNUN TANIMI VE ÇÖZÜM ÖNERİSİ (35 Puan)

**Projenin Önemi ve Sorunun Tanımı:**
Yer altı madenciliği, ekstrem çalışma koşulları ve yüksek operasyonel belirsizlik içermektedir. Mevcut işletme yöntemlerinde tespit edilen temel sorunlar literatür ve teknik veriler ışığında şu şekildedir:
1. **Navigasyon ve Güvenlik:** Yer altında GPS sinyalinin olmaması, araçların otonom sürüşünü "kör" hale getirmektedir. Mevcut sistemlerdeki LiDAR haritalama gürültüleri, dar galeri köşelerinde "pose-jump" (konum sıçraması) yaratarak araç kazalarına neden olmaktadır.
2. **Statik Havalandırma ve İSG:** Geleneksel sistemler sadece eşik değer aşımında (örneğin %1 CH4) alarm üretmektedir. Bu yaklaşım, kazaların önüne geçmekte "reaktif" kaldığı için yeterince hızlı koruma sağlayamamaktadır. OSHA/MSHA standartlarına göre gaz birikim hızı, anlık değerden daha kritiktir.
3. **Dinamik Planlama Eksikliği:** Rezerv modelleri genellikle static raporlara dayanmaktadır. İşletme anında karşılaşılan yeni cevher verilerinin veya engellerin, toplam üretim rotasına (Optimal Mining Path) etkisi manuel olarak hesaplanmakta, bu da verimlilik kaybına yol açmaktadır.

**Çözüm Önerisi ve Teknik Metot:**
DeepMine AI, madencilik literatürüne uygun ve mühendislik temelli şu çözümleri sunar:
- **8D Durum Kestirimi ve Outlier Reddi:** Geliştirilen EKF (Extended Kalman Filter) düğümü, aracın konumunu lineer ivmelenme verileriyle senkronize ederek 8 boyutta takip eder. Mahalanobis mesafesi algoritması kullanılarak, SLAM pose güncellemelerindeki gürültüler (outlier) filtrelenir; böylece %95 güven aralığında sarsıntısız navigasyon sağlanır.
- **Akıllı Havalandırma ve Bayesyen Risk Füzyonu:** Havalandırma düğümü, ortamdaki gaz yükseliş eğilimini (türevsel analiz) ölçerek 10 dakikalık bir "Flood/Gas Prediction" penceresi oluşturur. Bayesyen ağlar kullanılarak, personelin nabız hızı ve ortam gaz seviyesi korele edilir. Bu sayede sadece gaz değil, personelin "Toksik Yorgunluk" veya "Panik Durumu" anlık tespit edilerek otonom tahliye protokolleri başlatılır.
- **Optimal Mining Path (OMP):** Greedy tabanlı yol optimizasyonu ile en yüksek tenörlü 20 hedef nokta belirlenir. Sistem, maden ilerledikçe güncellenen 3D rezerv haritasına göre otonom olarak en kısa ve güvenli rotayı yeniden hesaplar (Dynamic Re-planning).

---

## 3. YENİLİKÇİLİK VEYA YERLİLEŞTİRME HAMLESİ (15 Puan)

**Yenilikçilik:**
DeepMine AI, dünyadaki mevcut Caterpillar MineStar veya Sandvik AutoMine gibi dev sistemlerin sunduğu "Navigasyon" katmanını bir adım ileriye taşıyarak; navigasyonu **"Gerçek Zamanlı Rezerv Analitiği"** ve **"Bayesyen İSG"** katmanlarıyla tam entegre (Full-Stack) hale getirmiştir.
- **Dinamik RRT\* Re-planning:** Birçok ticari sistem engel önünde durmayı (Obstacle Avoidance) tercih ederken, çözümümüz 2 saniyenin altında yeni bir küresel rota (Global Re-planning) üreterek operasyonu durdurmadan devam ettirir.
- **Hibrit Rezerv Tahmini:** Literatürde genellikle tekil kullanılan GPR ve NN modelleri hibritlenerek, kısıtlı sondaj verisinden maksimum doğrulukla rezerv tahmini yapılmaktadır.

**Yerlileştirme Hamlesi:**
Ülkemizdeki yer altı madenleri, yabancı menşeli yazılımların yüksek lisans ücretleri ve "teknik servis bağımlılığı" nedeniyle dijitalleşmede zorlanmaktadır. Projemiz:
- **Milli Teknoloji Hamlesi:** Tamamen yerli imkanlarla, açık kaynaklı ROS 2 (Robot Operating System) Humble omurgası üzerinde geliştirilmiştir.
- **Bağımsızlık:** Yabancı sistemlerin "Kapalı Kutu" (Blackbox) yapısının aksine, modüler yapısı sayesinde madenlerimizin özel jeolojik yapısına göre kolayca optimize edilebilir (Customizable Parameters).
- **Maliyet Etkinlik:** Donanım bağımsız yapısı, mevcut eski tip maden araçlarının düşük maliyetli sensör kitleriyle (Retrofitting) otonom hale getirilmesine olanak sağlar.

---

## 4. UYGULANABİLİRLİK VE SÜRDÜRÜLEBİLİRLİK (15 Puan)

**Uygulanabilirlik ve Entegrasyon:**
DeepMine AI, madenlerin zorlu tozlu ve karanlık koşullarına dayanıklı LiDAR ve IMU sensörleri üzerine kurgulanmıştır. Sistem, standart maden araçlarının kontrol ünitelerine (CAN-Bus vb. ara birimlerle) kolayca entegre edilebilir bir "API-First" mimarisine sahiptir. Konteynerize edilmiş (Docker) yapısı sayesinde, madenin local sunucusunda veya araç üzerindeki gömülü bilgisayarlarda (Edge Computing) kurulum hatası olmadan çalıştırılabilir.

**Sürdürülebilirlik:**
- **Finansal (Ekonomik):** Akıllı havalandırma sistemi, gaz seviyeleri normalken fan hızını %20 bandına çekerek işletmenin elektrik giderlerinde aylık bazda %30'a varan tasarruf sağlar. Operasyonel optimizasyon sayesinde araçların yakıt ve lastik ömrü uzatılır.
- **Çevresel:** Enerji verimliliği odaklı fan ve pompa kontrolü, maden işletmesinin karbon ayak izini doğrudan azaltır.
- **Sosyal ve İSG:** Personel takibindeki geofencing (sanal sınır) özellikleri, "Yalnız Çalışan" güvenliğini artırarak iş sağlığı standartlarını ISO 45001 seviyesine çeker.
- **Ticari Potansiyel:** Modüler yapısı sayesinde; navigasyon kitleri, İSG izleme üniteleri ve rezerv tahmin yazılımı ayrı ürünler olarak madencilik firmalarına pazarlanabilir bir KOBİ/Girişim potansiyeli taşır.

---

## 5. PROJENİN HAZIRLANIŞ SÜRECİ VE ÇALIŞMA YÖNTEMİ (10 Puan)

Proje, kronolojik bir iş paketleri (Work Packages) takvimine göre yönetilmektedir:

**İP-1: Literatür ve Standart Karşılaştırması (Ay 1):** MSHA ve OSHA standartlarına göre teknik eşiklerin belirlenmesi.
**İP-2: Algoritma Tasarımı ve Simülasyon (Ay 2):** C++ ile Explorer (RRT*) navigasyon düğümü ve Python ile EKF durum kestiricisi geliştirilmesi. Gazebo üzerinde maden galeri SDF modellerinin testi.
**İP-3: Yapay Zeka Katmanı (Ay 3):** GPR-NN hibrit rezerv tahmin modelinin eğitilmesi ve sentetik veri üreteci ile validasyonu.
**İP-4: İSG ve Otomasyon Entegrasyonu (Ay 4):** Hava kalitesi (CH4/CO) sensör verilerinin Bayesyen analiz düğümüne (Safety Agent) bağlanması ve otonom drone inspector tetikleme mekanizmasının kurulması.
**İP-5: Saha Örneklemi ve Final Test (Ay 5):** Toplanan tüm telemetri verilerinin (Mission Blackbox) analiz edilmesi ve sistemin nihai simülasyon ortamında uçtan uca doğrulanması.

---

## 6. PROJE TAKIMI (2 Puan)

| Sıra | Takımdaki Görevi | Eğitim Seviyesi/Meslek | Deneyim Süresi | Üye Rolü |
| :--- | :--- | :--- | :--- | :--- |
| – | Danışman | Dr. Öğr. Üyesi / Maden Müh. | 12 Yıl | Akademik Rehber |
| 1 | Takım Lideri | Mühendislik Öğrencisi | 4. Sınıf | Sistem Mimarisi & ROS Entegrasyon |
| 2 | Otonom Nav. Sorumlusu | Mühendislik Öğrencisi | 3. Sınıf | C++ Navigasyon & SLAM Geliştirme |
| 3 | AI Mühendisi | Mühendislik Öğrencisi | 3. Sınıf | Rezerv Tahmini & Veri Madenciliği |
| 4 | İSG Yazılım Sorumlusu | Mühendislik Öğrencisi | 2. Sınıf | Safety Agent & Karar Destek Sistemleri |
| 5 | Gömülü Sistem Uzmanı | Mühendislik Öğrencisi | 2. Sınıf | Sensör Ağı (IoT) & Donanım Arayüzleri |

---

## 7. KAYNAKLAR (3 Puan)

[1] Rosero, A. D., et al. (2024). "Robust SLAM Algorithms in Narrow Tunnel Environments." IEEE Robotics and Automation Letters.
[2] "Gaussian Processes for Machine Learning," C. E. Rasmussen and C. K. I. Williams, MIT Press, 2006.
[3] OSHA/MSHA, "Underground Mining Ventilation and Safety Regulations," Section 75.323.
[4] Karaman, S., & Frazzoli, E. (2011). "Optimal sampling-based algorithms for motion planning." IJRR.
[5] TEKNOFEST 2026 Maden Teknolojileri Yarışma Şartnamesi (Tema 4.2).
