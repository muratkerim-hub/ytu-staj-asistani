# 🎓 YTÜ Staj Asistanı & CV Analiz Platformu

> **Yıldız Teknik Üniversitesi öğrencileri ve mühendis adayları için geliştirilmiş kural tabanlı ATS denetleyicisi, ilan eşleştirme motoru, yapay zeka destekli mülakat simülatörü ve başvuru takip platformu.**

---

## 🌟 Öne Çıkan Özellikler

### 1. 🔍 Kapsamlı Kural Tabanlı ATS Denetimi (ats_checker.py)
* **9 Kritik Kriter:** İletişim & profesyonellik, sayfa ve kelime yoğunluğu, standart ATS bölüm başlıkları, madde uzunlukları, güçlü eylem fiilleri oranı, zayıf/pasif ifadeler, gerçek sayısal metrikler (yılları hariç tutan özel regex), tarih tutarlılığı ve tablo/görsel/kolon okunabilirliği.
* Her kriter için **GEÇTİ / UYARI / KALDI** durumları, 100 üzerinden puanlama, açık tespitler ve somut aksiyon önerileri.

### 2. 🎯 İlan Analizi & Ağırlıklı Yetenek Eşleştirme (job_matcher.py)
* LLM bağımlılığı olmayan, saf Python kural motoru.
* 17 kategori, 300'e yakın teknoloji sözlüğü (`skills.json`) ve eş anlamlılar (`synonyms.json`).
* Zorunlu gereksinimler, tercih sebepleri, alternatif teknolojiler ("X veya Y") ve CV'deki 3 seviyeli kanıt düzeyi (**Kanıtlı Proje / Listelenmiş / Dolaylı İlişki**).

### 3. 🛡️ Uydurma Bilgi Koruyucusu (fact_guard.py - Anti-Hallucination)
* Yapay zekanın CV'de olmayan teknolojileri eklemesini, doğrulanmamış metrikleri (%50 hızlandırma vb.), şişirilmiş unvanları ("Lead Architect", "Senior") ve doldurulmamış yer tutucuları (`[N]`, `[%X]`) denetleyen güvenlik kalkanı.

### 4. 🚀 STAR Madde Güçlendirici & Ön Yazı Üretici (ai_helper.py)
* Google Gemini 2.5 Flash entegrasyonu.
* Zayıf CV maddelerini **STAR** (Durum, Görev, Eylem, Sonuç) metodolojisine göre 3 farklı mühendislik perspektifinde (Eylem & Metrik, Mimari & Teknik, Problem Çözme) yeniden yazma.
* İlan gereksinimlerine ve adayın gerçek projelerine özel şablonik olmayan ön yazı (cover letter).

### 5. 🤖 Canlı Mülakat Simülatörü (interview_bot.py)
* Rol bazlı canlı simülasyon: **Teknik Lider**, **İK Uzmanı** veya **YTÜ Staj Mentoru**.
* Adayın yanıtlarını STAR kalitesine göre puanlama, anlık geri bildirim ve mülakat sonu detaylı karne.

### 6. 📊 İşe Kabul İhtimali & Alan Bağıntısı (correlation_engine.py)
* 5 boyutlu ağırlıklı algoritma (ATS %20, Zorunlu Yetenekler %35, Proje Kanıtı %25, Tercihler %10, Fact Guard %10).
* Gerçekçi piyasa kalibrasyonu, şansı artıracak 3 taktik ve CV-İlan alan uyumu analizi.

### 7. 📁 SQLite Başvuru Takipçisi (tracker.py)
* Başvuru durumları ("Başvuruldu", "Ön Eleme Geçildi", "Teknik Mülakat", "Teklif Alındı 🎉", "Reddedildi").
* Tek tıkla analiz edilen ilanı takip listesine ekleme, notlar ve süreç dönüşüm istatistikleri.

### 8. 📅 YTÜ Staj Stratejisi & Akademik Yol Haritası (strategy_engine.py)
* YTÜ Staj Yönergesi ile %100 uyumlu (Staj I, Staj II, Gönüllü, Aday Mühendislik).
* 5 fazlı yıllık başvuru takvimi ve interaktif 8 adımlı resmi evrak checklist'i.

### 9. 📄 ATS Uyumlu DOCX Dışa Aktarma (docx_exporter.py)
* Jake's Resume / Harvard standartlarında tek sütunlu, kenar boşlukları ve tipografisi optimize edilmiş, düzenlenebilir Microsoft Word (`.docx`) belgesi oluşturma.

---

## 🛠️ Teknoloji Yığını

* **Programlama Dili:** Python 3.11+
* **Web Arayüzü:** [Streamlit](https://streamlit.io/)
* **Yapay Zeka Modeli:** Google Gemini 2.5 Flash (`google-genai` SDK)
* **Belge İşleme:** PyMuPDF (fitz), python-docx
* **Veritabanı:** SQLite3
* **Kural Motoru:** Saf Python (RegEx, Ağırlıklı İstatistik)

---

## 🚀 Kurulum ve Çalıştırma

### 1. Depoyu Klonlayın
```bash
git clone https://github.com/KULLANICI_ADINIZ/ytu-staj-asistani.git
cd ytu-staj-asistani
```

### 2. Sanal Ortamı Oluşturun ve Aktif Edin
```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Gerekli Paketleri Yükleyin
```bash
pip install -r requirements.txt
```

### 4. Ortam Değişkenlerini Tanımlayın
Proje kök dizininde bulunan `.env.example` dosyasını kopyalayıp `.env` adıyla kaydedin:
```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```
Ardından `.env` dosyasını açıp [Google AI Studio](https://aistudio.google.com/)'dan aldığınız ücretsiz API anahtarınızı girin:
```env
GEMINI_API_KEY=AIzaSy...SİZİN_API_ANAHTARINIZ...
GEMINI_MODEL=gemini-2.5-flash
```

### 5. Uygulamayı Başlatın
```bash
streamlit run app.py
```
Tarayıcınızda otomatik olarak **http://localhost:8501** açılacaktır.

---

## 📂 Proje Dizin Yapısı

```text
ytu_staj_asistani/
├── app.py                  # Streamlit ana web arayüzü ve sekme kontrolleri
├── parser.py               # PDF/DOCX metin okuyucu ve bölüm ayrıştırıcı
├── ats_checker.py          # 9 kriterli kural tabanlı ATS motoru
├── job_matcher.py          # İlan analizi ve yetenek eşleştirme motoru
├── fact_guard.py           # Uydurma bilgi koruyucusu (Fact Guard)
├── ai_helper.py            # Gemini 2.5 Flash STAR güçlendirici ve ön yazı üretici
├── interview_bot.py        # İnteraktif canlı mülakat simülatörü
├── correlation_engine.py   # İşe kabul ihtimali ve alan bağıntı motoru
├── tracker.py              # SQLite başvuru takipçisi
├── strategy_engine.py      # YTÜ staj yönergesi ve akademik takvim stratejisi
├── docx_exporter.py        # Jake's Resume standardında ATS Word CV üretici
├── data/
│   ├── skills.json         # 17 kategori teknoloji ve yetenek sözlüğü
│   └── synonyms.json       # Eş anlamlı terimler ve teknoloji ilişkileri
├── .env.example            # Güvenli ortam değişkenleri şablonu
├── .gitignore              # Gizli dosyaları koruma kuralları
├── requirements.txt        # Bağımlılıklar listesi
└── README.md               # Proje tanıtım ve kurulum dokümanı
```

---

## 🔒 Güvenlik ve Gizlilik

* Bu repo hiçbir kişisel veri, gerçek başvuru notu veya API anahtarı içermez.
* `.env` dosyası ve yerel veritabanı `.gitignore` ile korunmaktadır.

---

## 👨‍💻 Geliştirici

**Murat** — Yıldız Teknik Üniversitesi
Proje ile ilgili geri bildirimleriniz ve katkılarınız için Issue veya Pull Request açabilirsiniz! ⭐
