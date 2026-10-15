# Proje Devir Notu (HANDOFF)

## Proje Ne Yapıyor?
Öğrencinin CV'sini (PDF/DOCX) okuyup analiz eden, girilen staj ilanına göre eksikleri bulan, kural tabanlı ATS kontrolü yapan, ilan eşleştirme algoritması çalıştıran, uydurma bilgi koruması (fact guard) içeren ve Google Gemini API desteğiyle CV maddelerini güçlendirip ilana özel ön yazı ve mülakat hazırlığı sunan saf Python ağırlıklı bir Streamlit web uygulamasıdır.

## Teknik Bilgiler
- **Python Sürümü:** Python 3.11.9 (64-bit, proje kökündeki `.venv` ortamında)
- **Kullanılan Kütüphaneler:** `google-genai`, `PyMuPDF`, `python-docx`, `streamlit`, `python-dotenv`
- **Geliştirme Ortamı:** PyCharm IDE ve PyCharm Terminali (Yorumlayıcı: `.venv\Scripts\python.exe`)
- **Nasıl Çalıştırılır:**
  1. PyCharm Terminalini aç (`(.venv)` aktif olmalı). Aktif değilse doğrudan `.\.venv\Scripts\python.exe` kullan — PATH'teki `python` MSYS2'ye (`C:\msys64\ucrt64\bin\python.exe`) gidiyor, paketler yanlış yere kurulur.
  2. Modül testleri: `python parser.py`, `python ats_checker.py`, `python job_matcher.py` veya `python ai_helper.py`.
  3. Web Arayüzünü Başlatma: `streamlit run app.py` (veya `.\.venv\Scripts\streamlit.exe run app.py`). Tarayıcıda http://localhost:8501 açılır.

## Şu Ana Kadar Yapılanlar
- **Aşama 1 (Kurulum ve API Bağlantısı):** Python 3.11 `venv` kuruldu, `.env` ile `gemini-2.5-flash` modeli bağlandı ve `test_api.py` ile doğrulandı. `.gitignore` oluşturuldu.
- **Aşama 2 (CV Okuma ve Ayrıştırma - parser.py):** PDF/DOCX okuma, görsel PDF uyarısı ve TR/EN bölüm başlıklarını (`SECTION_KEYWORDS`) sözlüğe ayıran modül yazıldı.
- **Aşama 3 (Profesyonel Kural Tabanlı ATS Motoru - ats_checker.py):** İlk basit sürüm kullanıcı geri bildirimiyle tamamen yenilendi. `parser.py` ile entegre edildi. 9 kapsamlı kriter (İletişim + profesyonel e-posta regex'i, sayfa/kelime yoğunluğu, standart başlıklar, madde uzunlukları, eylem fiili oranı, yılları hariç tutan gerçek metrik regex'i, zayıf ifadeler, tarih formatı tutarlılığı ve tablo/görsel/çok sütunlu tasarım kontrolü) eklendi. Her kriter için GEÇTİ/UYARI/KALDI, puan, tespit ve çözüm önerisi üreten yapı kuruldu. ✅ Test edildi, çalışıyor.
- **Ortam Onarımı (15 Ekim 2026):** `.venv` bozuktu (`pip._vendor.packaging` ve `_distutils_hack` eksik, `pip install` çalışmıyordu). Python 3.11 ile `.venv` yerinde yeniden oluşturuldu, pip 26.2.1'e güncellendi, `requirements.txt` başarıyla kuruldu (google-genai 2.30.1, streamlit 1.66.0, PyMuPDF 1.28.2, python-docx 1.2.0, python-dotenv 1.2.4).
- **PyCharm Yorumlayıcı Düzeltmesi (15 Ekim 2026):** Proje yanlışlıkla sistemdeki Python 3.14'e bağlıydı ("Package requirements not installed" uyarısının sebebi). Yorumlayıcı `Python 3.11 (ytu_staj_asistani)` → `.venv\Scripts\python.exe` olarak değiştirildi. ⚠️ PyCharm'daki "Sync project" butonuna basılmamalı (yanlış Python'a kurabilir).
- **.gitignore (15 Ekim 2026):** Aşama 1'de oluşturulduğu yazıyordu ama dosya yoktu; yeniden oluşturuldu (`.env`, `.venv/`, `__pycache__/`, `.idea/`, kişisel `cv.pdf`/`cv.docx`, `*.db`).
- **Aşama 4 (İlan Analizi ve CV Eşleştirme Motoru - job_matcher.py):** Saf Python ile LLM gerektirmeyen kural tabanlı eşleştirme motoru yazıldı. `data/skills.json` (17 kategori, ~290 yetenek) ve `data/synonyms.json` (eş anlamlılar, büyük/küçük harf duyarlı terimler, Django->Python dolaylı ilişkiler) hazırlandı. İlan metnindeki zorunlu/tercihli gereksinimleri, alternatif grupları ("X veya Y"), CV'deki kanıt seviyelerini (kanıtlı, listelenmiş, dolaylı) tespit eden ağırlıklı puanlama sistemi ve uygulanabilir öneriler modülü kuruldu.
- **Türkçe Karakter / Normalizasyon Düzeltmesi (parser.py & ats_checker.py):** Python'un `'İ'.lower()` sonucunu iki karaktere (`i\u0307`) açması sebebiyle "EĞİTİM" ve "DİLLER" başlıklarının tanınamaması sorunu `turkish_lower()` ile çözüldü. Windows konsolunda Unicode/emoji hatalarını önlemek için `sys.stdout.reconfigure(encoding="utf-8")` eklendi. ATS skoru ve bölüm tanıma %100 uyumlu hale geldi. ✅ Test edildi, çalışıyor.
- **Aşama 5 (Gemini AI Destek Modülü - ai_helper.py):** `google-genai` SDK ile `gemini-2.5-flash` modeli entegre edildi. Zayıf CV maddelerini STAR metodolojisine göre 3 profesyonel alternatife (Eylem & Metrik, Teknik & Mimari, Etki & Problem Çözme) dönüştüren, kesinlikle uydurma veri/sayı üretmeyip `[N]`, `[%X]` yer tutucuları bırakan yapı kuruldu. İlana ve CV'deki gerçek projelere özel şablonik olmayan ön yazı (cover letter) ve teknik mülakat hazırlık modülleri eklendi. Yapılandırılmış JSON yanıtları ve Windows UTF-8 desteği sağlandı. ✅ Test edildi, çalışıyor.
- **Aşama 6 (Uydurma Bilgi Koruyucusu - fact_guard.py):** Öğrencinin CV'sinde gerçekte bulunmayan teknolojilerin yapay zeka tarafından üretilen metinlere eklenmesini (halüsinasyon/yetkisiz teknoloji) denetleyen, doğrulanmamış metrikleri (%50 hızlandırma vb.), şişirilmiş unvanları ("Lead Architect", "Senior") ve doldurulmamış yer tutucuları (`[N]`, `[%X]`) tespit edip 0-100 güvenlik puanı ve koruma raporu üreten modül geliştirildi. `synonyms.json`'a `Pandas -> Veri Analizi, Veri Temizleme` ilişkisi eklenerek denetim hassasiyeti artırıldı. ✅ Test edildi, çalışıyor.
- **Aşama 7 (Streamlit Web Arayüzü - app.py):** Modern, responsive ve sekmeli dashboard arayüzü kuruldu. PDF/DOCX yükleme ve tek tıkla örnek CV deneme seçenekleri, ATS Skoru & İlan Eşleşme metrik kartları, kategori kırılım çubukları, filtreli gereksinim tablosu, 9 kriterli ATS rapor kartları, STAR madde güçlendirici + canlı Fact Guard denetimi, ilana özel ön yazı üreticisi ve metin indirme butonu, mülakat hazırlık genişleticileri ve ham CV inceleme sekmeleri entegre edildi. Syntax ve derleme testleri tamamlandı. ✅ Test edildi, çalışıyor.
- **Aşama 8 (İnteraktif Mülakat Simülatörü - interview_bot.py):** Rol bazlı ("Teknik Lider", "İK Uzmanı", "YTÜ Staj Mentoru") canlı mülakat simülatörü geliştirildi. Adayın yanıtlarını STAR metoduna ve teknik somutluğuna göre 1-10 puanlayan, mülakatçının anlık geri bildirimini ve takip sorusunu üreten, "Nasıl cevap vermeliydin?" STAR tüyoları sağlayan ve oturum bitiminde 0-100 performans karnesi çıkaran modül yazıldı. Geçici 503/429 API yoğunluklarına karşı otomatik yeniden deneme (`_call_gemini_with_retry`) eklendi. `app.py` Sekme 6'ya canlı chat arayüzü olarak entegre edildi. ✅ Test edildi, çalışıyor.
- **İşe Kabul İhtimali ve CV-İlan Bağıntı Motoru (correlation_engine.py):** Kullanıcının önerisiyle; ATS filtresi (%25), zorunlu yetenekler (%35), proje kanıtı (%20), artı değerler (%10) ve Fact Guard güvenilirliği (%10) olmak üzere 5 boyuttan ağırlıklı **% İşe Kabul / Mülakat Çağrılma İhtimali** hesaplayan ve şansı en hızlı artıracak 3 taktik üreten sistem yazıldı. Ayrıca adayın CV'sinin baskın uzmanlığı ile ilanın hedef profili arasındaki anlamsal alan bağıntısını (%0-100) ve alan uyumunu ("Tam Alan Uyumu", "Geçişken Alan" vb.) çıkaran mekanizma kuruldu ve `app.py` Sekme 1 ve Sekme 2'ye öne çıkan kartlar olarak eklendi. ✅ Test edildi, çalışıyor.
- **ATS Puanlama ve Doğruluk Denetimi (ats_checker.py & parser.py):** ATS puanlama motoru en doğru ve adil sonucu vermesi için baştan sona denetlendi ve güçlendirildi:
  1. *İletişim & Profesyonellik:* Tüm metin taranacak şekilde genişletildi. Parantezli/noktalı/boşluklu telefon formatları (`+90 (555) 123 45 67`, `0 (532)...`) eklendi. E-posta profesyonelliğinde öğrenci doğum yılları (örn. 2002, 2003) ceza kapsamından çıkarıldı, amatör rumuzlar (`gamer`, `kral`, `lord` vb.) filtrelendi.
  2. *Çok Satırlı Madde Birleştirme:* PDF'ten metin çıkarılırken iki satıra bölünen maddeler `extract_bullets` içinde akıllıca birleştirilerek eylem ve metrik kayıpları engellendi.
  3. *Genişletilmiş Eylem Fiilleri & Zayıf İfadeler:* Türkçe ve İngilizce 35+ teknik eylem fiili (`modelle`, `uygula`, `yapılandır`, `deploy`, `refactor`, `test et` vb.) ve pasif kelimeler (`destek oldum`, `uğraştım`, `bakıyordum`, `sorumluluğumdaydı` vb.) eklendi.
  4. *Gelişmiş Metrik Tespiti:* Yılları (1990-2035) kesinlikle hariç tutan; yüzdeler (`%40`), çarpanlar (`3x`, `5 kat`), kısaltmalar (`10k`, `100+`), para birimleri (`10.000 TL`), hacimler (`150 kullanıcı`, `10.000 satır`, `120 ms`, `99.9% uptime`, `0.85 F1`) gibi zengin göstergeleri yakalayan regex mimarisi kuruldu.
  5. *Bölüm Başlıkları Kapsamı:* `parser.py` içinde `SECTION_KEYWORDS` genişletilerek `projelerim`, `deneyimlerim`, `yetkinlikler`, `eğitim bilgileri` gibi yaygın varyasyonlar eklendi, yanlış "bölüm eksik" uyarısı (false negative) sıfırlandı.
  6. *PyMuPDF Uyarısı:* `fitz` importu `try: import pymupdf as fitz` şeklinde modernize edilerek konsol uyarıları temizlendi. ✅ Tüm uç durumlar birim testlerle doğrulandı.

- **Aşama 9 (SQLite Başvuru Takipçisi - tracker.py & app.py):** Öğrencinin staj başvurularını, şirketleri, tarihleri, süreç aşamalarını ve notlarını yöneten yerel SQLite veritabanı altyapısı (`data/applications.db`) kuruldu:
  1. *Veritabanı Mimarisi:* `company_name`, `position_title`, `location`, `application_date`, `deadline`, `status`, `match_score`, `ats_score`, `hire_probability`, `job_description`, `notes` alanlarını içeren ilişkisel tablo ve indeksler oluşturuldu.
  2. *Süreç Durumları:* "Başvuruldu" (Mavi), "Ön Eleme Geçildi" (Açık Mavi), "Teknik Mülakat" (Mor), "İK Mülakatı" (Menekşe), "Teklif Alındı 🎉" (Yeşil), "Reddedildi" (Kırmızı), "Geri Çekildi" (Gri) durum yönetimi ve renk kodlaması tanımlandı.
  3. *İstatistik & Dönüşüm Metrikleri:* Toplam başvuru, aktif süreç, mülakat aşaması, alınan teklifler ve dönüş oranı (%) hesaplama fonksiyonu eklendi.
  4. *Tek Tıkla Kayıt:* `app.py` Sekme 1'e ("Genel Bakış") analiz edilen ilanın ATS skoru, uyum skoru ve işe kabul ihtimaliyle birlikte otomatik doldurulup tek tıkla takipçiye kaydedilmesini sağlayan form eklendi (`infer_company_and_role` ile şirket/pozisyon otomatik çekilir).
  5. *Dashboard Sekmesi (Sekme 7):* 5 temel istatistik kartı, arama ve durum filtresi, manuel yeni başvuru ekleme formu, sol kenarı durum rengiyle kodlanmış başvuru kartları, süreç notları günlüğü ve anlık durum güncelleme/silme paneli `app.py` içine entegre edildi. ✅ Test edildi, çalışıyor.

- **Aşama 10 (Staj Stratejisi ve YTÜ Zaman Çizelgesi - strategy_engine.py & app.py):** YTÜ Staj Yönergesi, resmi evrak süreçleri ve akademik yıl takvimiyle tam uyumlu strateji motoru geliştirildi:
  1. *YTÜ Resmi Staj Bilgileri:* Staj I (Temel/Laboratuvar - 2. sınıf sonu), Staj II (Mesleki/Yazılım - 3. sınıf sonu), Gönüllü Staj ve Aday Mühendislik (4. sınıf) kuralları, yaz okulu/ders günü çakışma kısıtlamaları ve SGK gereksinimleri tanımlandı.
  2. *5 Fazlı Yıllık Yol Haritası:* Faz 1 (Kasım-Ocak: Hazırlık & Portfolyo), Faz 2 (Şubat-Mart: Zirve Başvuru & Ulusal Staj Programı), Faz 3 (Nisan-Mayıs: Mülakatlar & YTÜ Evrak Onayı), Faz 4 (Haziran-Ağustos: Stajın İcrası & Teklif Alma), Faz 5 (Eylül-Ekim: Defter Onayı & Sunum) yapılandırıldı.
  3. *Kişiselleştirilmiş Strateji Üretici:* Öğrencinin sınıfına (1, 2, 3, 4. sınıf), staj türüne ve mevcut analiz skorlarına (ATS, Uyum, İşe Kabul) göre özel odak noktaları, skor bazlı uyarılar ve aksiyonlar üreten motor kuruldu.
  4. *İnteraktif Resmi Süreç Checklist'i:* Bölüm yönergesinden müstehaklık belgesine, staj komisyonu onayından staj defteri kaşesine kadar 8 resmi adımı canlı ilerleme çubuğuyla takip eden etkileşimli kontrol paneli oluşturuldu.
  5. *Şirket Türü Başvuru Matrisi:* Savunma Sanayii, Global Teknoloji, Bankacılık & Fintek ve Teknopark Startup'larının stajyer arama kriterleri ve stratejik önerileri entegre edildi. `app.py` Sekme 8 olarak eklendi. ✅ Test edildi, çalışıyor.

- **Aşama 11 (DOCX Dışa Aktarma - docx_exporter.py & app.py):** Öğrencinin CV'sini Jake's Resume / Harvard standartlarında tek sütunlu, ATS dostu Microsoft Word (`.docx`) formatına dönüştüren ihracatçı modül yazıldı:
  1. *ATS Tasarım Standartları:* 0.5 inç (1.27 cm) sayfa kenar boşlukları, 18pt ortalı aday adı, 9.5pt iletişim satırı, Calibri yazı tipi hiyerarşisi, tek sütunlu tablosuz düzen ve bölüm başlıkları altında özel XML tabanlı yatay ayırıcı çizgiler (`w:pBdr/w:bottom`).
  2. *Bölüm Hiyerarşisi:* Başlık & İletişim, Özet/Profil, Eğitim, Deneyim & Stajlar, Projeler (STAR güçlendirilmiş maddelerle uyumlu), Teknik Yetenekler & Araçlar, Sertifikalar & Diller sırasıyla lineer ATS okumasına uygun formatlandı.
  3. *Çift Modlu Çıktı:* Hem yerel diske dosya olarak kaydetme (`export_cv_to_file`) hem de Streamlit üzerinden bellek içi indirme (`export_cv_to_bytes` -> `st.download_button`) desteği.
  4. *Arayüz Entegrasyonu:* `app.py` Sekme 1 (Genel Bakış), Sekme 3 (ATS Raporu) ve Sekme 4 (STAR Güçlendirici) bölümlerine tek tıkla düzenlenebilir ATS uyumlu Word CV indirme butonları yerleştirildi. ✅ Test edildi, çalışıyor.
- **Gerçek Dünya Puanlama ve Mülakat Kalibrasyonu (interview_bot, correlation_engine, job_matcher, ats_checker):** Kullanıcı talebi doğrultusunda sistemdeki tüm puanlama mekanizmaları gerçek dünya seçici mühendislik mülakatı standartlarına göre keskinleştirildi:
  1. *Mülakat Cevap Puanlaması (interview_bot.py):*
     - Prompt seviyesinde 1-10 arası katı barem getirildi: 1-3 (Yetersiz/Kaçamak), 4-5 (Zayıf/Yüzeysel), 6 (Standart/Sınır Tavan), 7-8 (İyi/Gerçekten Tatmin Edici STAR), 9-10 (Kusursuz/Üst Düzey).
     - **Programatik 6 Tavanı Kilidi:** Adayın cevabı < 15 kelime ise max 3; < 25 kelime ise max 5; derin teknik gerekçe veya sayısal metrik içermiyorsa **kesinlikle max 6 puan** ile sınırlandırıldı. Yüzeysel cevapların 7-8 alması tamamen engellendi.
     - *Mülakat Sonu Karnesi:* Acımasız ama adil başmülakatçı personası ve 60 altı elenme baremiyle gerçekçi değerlendirme getirildi.
  2. *İşe Kabul ve Mülakata Çağrılma Oranı (correlation_engine.py):*
     - Aşırı katı ve puanı %5'e düşüren mükerrer cezalar temizlendi; 5 boyutlu ağırlıklı donanım skoru (ATS %20, Zorunlu Yetenek %35, Proje Kanıtı %25, Tercih Sebebi %10, Fact Guard %10) baz alındı.
     - Gerçek dünya piyasa rekabet katsayısı (0.88x) ile dengelendi. Güçlü bir YTÜ öğrencisi profili gerçekçi olarak %50-70 (Yüksek/Rekabetçi), eksikleri olan profiller %30-45 (Orta/Elenme Riski), uyumsuz profiller %10-25 bandına oturtuldu. Tavan %88 olarak belirlendi.
  3. *İlan Eşleşme Skoru (job_matcher.py):*
     - Denge sağlandı: Zorunlu yetenek ağırlığı 3.0, sadece listede geçen yetenekler 0.55 kredi, dolaylı çıkarım 0.45 olarak kalibre edildi.
  4. *ATS Denetimi (ats_checker.py):*
     - Pasif/zayıf kelime cezası artırıldı; tam metrik puanı için en az %50 madde şartı getirildi. ✅ Tüm uç testler başarıyla doğrulandı.
- **DOCX ATS Puan Koruma ve Başlık Normalizasyon Onarımı (docx_exporter.py & parser.py):**
  - *Sorunun Kök Nedeni:* Kullanıcının ATS skoru 70 olan bir CV ile deneme yapıp indirdiği "ATS Uyumlu" Word (.docx) belgesini tekrar sisteme yüklediğinde puanının 60'a düşmesi sorunu tespit edildi. Yapılan analizde:
    1. Python'ın standart `.upper()` fonksiyonu `"Eğitim"` kelimesini İngilizce `I` ile `"EĞITIM"` yapıyordu. Word tekrar okunurken `turkish_lower()` İngilizce `I`'yı Türkçe `ı`'ya (`"eğıtım"`) çevirdiğinden, sözlükteki `"eğitim"` ile eşleşmiyordu.
    2. `docx_exporter.py` içinde `"Özet / Profil"`, `"Deneyim & Stajlar"`, `"Teknik Yetenekler & Araçlar"` ve `"Sertifikalar & Diller"` gibi `/` ve `&` içeren bileşik başlıklar kullanılıyordu. `SECTION_KEYWORDS` bu sembolleri içermediği için sadece "PROJELER" tanınıyor; Eğitim (-4), Yetenekler (-4) ve Özet (-2) başlıkları **tam 10 puan kayıpla** eksik sayılıyordu.
    3. Word dosyalarından liste maddeleri (`List Bullet`) okunurken başında literal `•` karakteri olmadığı için maddelerin birbirine yapışma riski bulunuyordu.
  - *Uygulanan Çözüm:*
    1. `docx_exporter.py` modülüne Türkçe karakter duyarlı `turkish_upper(text)` eklendi (`i -> İ`, `ı -> I`).
    2. DOCX başlıkları standart evrensel ATS başlıklarına dönüştürüldü (`Özet`, `Eğitim`, `İş Deneyimi`, `Projeler`, `Teknik Yetenekler`, bağımsız `Sertifikalar` ve `Yabancı Diller`).
    3. `parser.py` içine `normalize_header_text()` eklendi: İ/I/ı harfleri, Türkçe karakterler, `&` ve `/` sembolleri, noktalama ve boşluklar normalize edilerek hem tam hem kelime sınırıyla eşleşme sağlandı.
    4. `extract_text_from_docx()` içine Word liste/madde imi (`w:numPr` veya List Bullet stili) algılama eklendi, madde imi olmayan listelerin başına `• ` otomatik yerleştirildi.
  - *Sonuç & Doğrulama:* İndirilen DOCX belgesi tekrar yüklendiğinde ATS skoru birebir aynı (örn. 88 -> 88, 81 -> 81) kalarak sıfır kayıpla %100 ATS sadakati sağlandı. ✅ Test edildi, çalışıyor.
- **GitHub Hazırlığı & Açık Kaynak Güvenliği (15 Ekim 2026):**
  - `.gitignore` dosyası güçlendirildi (`.env`, `.venv`, kişisel `*.pdf`, `*.docx`, `*.db`, `.idea`, `__pycache__` sızması engellendi).
  - Başka geliştiricilerin projeyi klonladığında API anahtarını tanımlayabilmesi için `.env.example` şablonu oluşturuldu.
  - Projenin mimarisini, modüllerini, kurulum adımlarını ve özelliklerini içeren profesyonel `README.md` hazırlandı.
  - Streamlit Community Cloud canlı yayını için `st.secrets` ortam değişkeni dinamik köprüsü (`ai_helper.py`, `interview_bot.py`, `app.py`) eklendi.
  - Canlı Web Uygulaması Yayınlandı: `https://ytu-staj-asistani-jnwnekcvhbnja6omlr7fbg.streamlit.app/` (`README.md` tepesine canlı rozet ve buton eklendi).
- **Sade Ana Sayfa (UI Sadeleştirme - app.py, 15 Ekim 2026):** Kullanıcı geri bildirimiyle ana sayfa bilgi yükünden arındırıldı:
  - Ana sayfada (🏠 Özet) yalnızca 3 büyük renk kodlu kart: **Mülakata Çağrılma İhtimali**, **ATS Skoru**, **İlana Uygunluk**; altında eksik zorunlu yetenek etiketleri ve en fazla 3 maddelik "yapman gerekenler" listesi.
  - "İşe kabul puanı nasıl oluştu" dökümü, alan bağıntısı ve ek öneriler **🎯 İlan Uyumu** sekmesine (kapalı expander) taşındı.
  - Sekme adları kısaltıldı (Özet, İlan Uyumu, ATS Raporu, CV Güçlendir, Ön Yazı, Mülakat, Başvurularım, Strateji, CV Metni). `AppTest` ile hatasız render doğrulandı. ✅

## Proje Durumu
- **TÜM 11 AŞAMA VE KULLANICI İNOVASYONLARI EKSİKSİZ TAMAMLANDI!** 🎉
- 11 Temel Modül: `parser.py`, `ats_checker.py`, `job_matcher.py`, `ai_helper.py`, `fact_guard.py`, `interview_bot.py`, `correlation_engine.py`, `tracker.py`, `strategy_engine.py`, `docx_exporter.py`, `app.py`.
- 9 Kapsamlı Sekmeli Web Arayüzü: Genel Bakış & İşe Kabul, İlan Eşleştirme & Bağıntı, ATS Denetimi, STAR Güçlendirici, Ön Yazı Üretici, Mülakat Simülatörü, SQLite Başvuru Takipçisi, Staj Stratejisi & YTÜ Takvimi, Ayrıştırılmış CV Metni.

## Sıradaki İşler / İsteğe Bağlı İleri Seviye Geliştirmeler
1. Canlı kullanıcı testleri ve geri bildirim toplama.
2. Gerçek staj ilanları ve öğrenci CV'leri ile uçtan uca senaryo denemeleri.
3. İleride istenirse PDF dışa aktarma (export to PDF) veya kullanıcı giriş sistemi ekleme.

## Önemli Kararlar / Dikkat Edilecekler
- **Kalite Standardı:** Kodlar yüzeysel/amatör örnekler yerine gerçek dünya senaryolarını (örn. tarihleri metrik sanmamak, e-posta profesyonelliğini denetlemek, gerçek PDF/DOCX dosyasıyla test etmek) kapsayacak derinlikte yazılacak.
- **Model:** `gemini-2.5-flash` kullanılıyor.
- **Mimari:** LangChain kullanılmıyor. Tüm puanlama ve eşleştirme işlemleri saf Python ile yapılıyor.
- **HANDOFF Kuralı:** Projeye her ekleme/değişiklik yapıldığında (yeni modül, aşama tamamlanması, ortam/kütüphane değişikliği, önemli karar) bu dosya aynı oturumda güncellenecek.

## Son Güncelleyen ve Tarih
- **Güncelleyen:** Murat & Antigravity
- **Tarih:** 15 Ekim 2026