"""
Staj Başvuru Stratejisi ve YTÜ Zaman Çizelgesi Motoru (strategy_engine.py)

Özellikler:
    - YTÜ Staj Yönergesi ve resmi mühendislik staj süreçlerine tam uyumlu takvimleme.
    - Akademik yıl bazlı 5 fazlı başvuru yol haritası (Kasım'dan Ekim'e).
    - Öğrencinin sınıf seviyesine (1, 2, 3, 4. sınıf), staj türüne ve mevcut skorlarına göre
      kişiselleştirilmiş haftalık eylem planı.
    - Resmi evrak ve SGK süreç kontrol listesi (Checklist).
    - Şirket tipi başvuru matrisi (Savunma Sanayii / Banka / Global vs. Scale-up / Startup vs. Ar-Ge).
    - Stajı tam zamanlı / aday mühendislik iş teklifine dönüştürme stratejileri.
"""
import os
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# --- YTÜ VE RESMİ STAJ YÖNERGESİ KURALLARI ---
YTU_INTERNSHIP_INFO = {
    "universite": "Yıldız Teknik Üniversitesi",
    "staj_turleri": {
        "staj_1": {
            "ad": "Staj I (Temel / Laboratuvar / Donanım Stajı)",
            "ideal_donem": "2. Sınıf Sonu (Yaz)",
            "sure": "Genellikle 20 - 30 İş Günü",
            "amac": "Temel mühendislik pratikleri, çalışma ortamını tanıma, temel donanım ve yazılım süreçlerini gözlemleme."
        },
        "staj_2": {
            "ad": "Staj II (Mesleki / Ar-Ge / Yazılım Stajı)",
            "ideal_donem": "3. Sınıf Sonu (Yaz)",
            "sure": "Genellikle 20 - 30 İş Günü",
            "amac": "Doğrudan üretim, yazılım mimarisi, veri analizi veya proje geliştirme ekiplerinde aktif mühendislik rolü."
        },
        "gonullu": {
            "ad": "Gönüllü Staj / Proje Stajı",
            "ideal_donem": "Tüm Sınıflar (Yarıyıl Tatili veya Yaz)",
            "sure": "Esnek (Şirketle anlaşmaya bağlı)",
            "amac": "Erken dönemde sektörel deneyim kazanma ve portfolyo güçlendirme (SGK şartları için bölüm sekreterliğiyle görüşülmelidir)."
        },
        "aday_muhendislik": {
            "ad": "Uzun Dönem / Aday Mühendislik (Part-Time)",
            "ideal_donem": "4. Sınıf (Güz ve Bahar Dönemleri)",
            "sure": "Dönem boyunca haftada 2 - 3 tam iş günü",
            "amac": "Mezuniyet sonrasında doğrudan tam zamanlı mühendis kadrosuna geçiş."
        }
    },
    "onemli_kurallar": [
        "⚠️ Stajlar kural olarak ders ve sınav dönemleri dışındaki tatil aylarında (Temmuz - Eylül) yapılır.",
        "⚠️ Yaz okulunda ders alan öğrenciler, derslerinin olduğu günlerde staj yapamaz (Yalnızca ders olmayan günlerde veya Cumartesi çalışılan yerlerde yapılabilir).",
        "⚠️ Staj Kabul Formu, staja başlamadan en az 10-15 gün önce Bölüm Staj Komisyonuna onaylatılmalıdır.",
        "⚠️ SGK İşe Giriş Bildirgesi üniversite tarafından staj başlangıcından 1-3 gün önce e-Devlet'e yüklenir; e-Devlet'te görünmeden staja başlanamaz.",
        "⚠️ Staj defteri her iş günü için teknik detaylarla doldurulmalı ve yetkili mühendis (en az lisans mezunu mühendis) tarafından her sayfası kaşelenip imzalanmalıdır."
    ]
}

# --- YILLIK STRATEJİK BAŞVURU ÇİZELGESİ (5 FAZ) ---
ANNUAL_TIMELINE_PHASES = [
    {
        "faz": "Faz 1: Hazırlık & Portfolyo İnşası",
        "aylar": "Kasım - Ocak",
        "hedef": "Altyapıyı kurma ve büyük kurumsal ilanları yakalama",
        "rozet": "🛠️",
        "renk": "#2563EB",
        "gorevler": [
            "CV'yi tek sayfa, ATS dostu Jake's Resume formatında güncelle ve PDF'e aktar.",
            "GitHub profilindeki en az 2 projenin README dosyasını mimari diyagram ve canlı demo linkiyle profesyonelleştir.",
            "LinkedIn profilini optimize et (Başlık, Hakkında, YTÜ bilgileri, beceriler).",
            "Savunma sanayii ve kurumsal şirketlerin erken staj programlarını (Aselsan, Baykar, Roketsan, Koç, Sabancı vb.) takip et ve başvur."
        ]
    },
    {
        "faz": "Faz 2: Zirve Başvuru & Ulusal Staj Programı",
        "aylar": "Şubat - Mart",
        "hedef": "Maksimum başvuru hacmi ve ilk eleme sınavları",
        "rozet": "🚀",
        "renk": "#7C3AED",
        "gorevler": [
            "Cumhurbaşkanlığı Kariyer Kapısı (Ulusal Staj Programı - USP) başvurunu eksiksiz tamamla.",
            "Orta ve büyük ölçekli teknoloji şirketleri, bankalar ve scale-up'ların staj programlarına başvur.",
            "Haftada en az 5-10 hedefe yönelik, ilana özel uyarlanmış başvuru yap.",
            "HackerRank / LeetCode algoritma testleri ve teknik genel yetenek sınavlarına hazırlan."
        ]
    },
    {
        "faz": "Faz 3: Mülakatlar & YTÜ Resmi Evrak Onayı",
        "aylar": "Nisan - Mayıs",
        "hedef": "Mülakatları başarıyla tamamlama ve stajı resmiyete dökme",
        "rozet": "🤝",
        "renk": "#0284C7",
        "gorevler": [
            "Teknik ve İK mülakatlarında STAR metodunu kullanarak projelerindeki somut etkiyi anlat.",
            "Kabul aldığın şirketten resmi 'Staj Kabul Formu'nu kaşeli/imzalı olarak teslim al.",
            "e-Devlet üzerinden 'Müstehaklık / SGK Provizyon Belgesi'ni indir.",
            "Staj başlamadan en az 15 gün önce tüm belgeleri YTÜ Bölüm Staj Komisyonuna teslim et ve onayı al."
        ]
    },
    {
        "faz": "Faz 4: Stajın İcrası & İş Teklifine Dönüştürme",
        "aylar": "Haziran - Ağustos",
        "hedef": "Maksimum teknik katma değer üretme ve ağ kurma",
        "rozet": "💼",
        "renk": "#16A34A",
        "gorevler": [
            "e-Devlet'ten SGK İşe Giriş Bildirgesinin çıktığını stajın ilk gününden önce kontrol et.",
            "Her iş günü yaptığın işleri, öğrendiğin kütüphaneleri staj günlüğüne/taslak defterine günü gününe kaydet.",
            "Yöneticin ve kıdemli mühendislerle haftalık 15 dakikalık 1-e-1 geri bildirim toplantısı talep et.",
            "Stajın son haftasında 'Aday Mühendislik veya Dönem İçi Part-time' çalışma olasılığını yöneticinle konuş."
        ]
    },
    {
        "faz": "Faz 5: Staj Defteri Onayı & Sunum",
        "aylar": "Eylül - Ekim",
        "hedef": "Stajın akademik olarak saydırılması ve kapatılması",
        "rozet": "🎓",
        "renk": "#D97706",
        "gorevler": [
            "Staj Defterini teknik bir dille, akademik formata uygun olarak tamamla.",
            "Staj Sicil Fişi (Değerlendirme Formu) ve defteri yetkili mühendise kaşeletip kapalı, mühürlü zarfta teslim al.",
            "Güz yarıyılının ilk ayında defteri ve mühürlü zarfı Bölüm Staj Komisyonuna teslim et.",
            "Gerekiyorsa staj sözlü mülakatına / sunumuna katıl ve stajını transkriptine işlet."
        ]
    }
]

# --- ETKİLEŞİMLİ RESMİ SÜREÇ CHECKLIST MADDELERİ ---
CHECKLIST_ITEMS = [
    {
        "id": "chk_yonerge",
        "baslik": "Bölüm Staj Yönergesini İnceleme",
        "aciklama": "Bölümünüzün staj yönergesindeki zorunlu gün sayısını (genelde 20 veya 30 iş günü) ve kabul edilen şirket kriterlerini okuyun.",
        "kategori": "Ön Hazırlık"
    },
    {
        "id": "chk_kabul_yazisi",
        "baslik": "Şirketten İmzalı Staj Kabul Formu Alma",
        "aciklama": "Kabul aldığınız şirketin İK veya yetkili mühendisine YTÜ Staj Kabul Formunu doldurtup kaşe ve ıslak/elektronik imza aldırın.",
        "kategori": "Evrak Süreci"
    },
    {
        "id": "chk_mustehaklik",
        "baslik": "e-Devlet Müstehaklık Belgesi Çıkarma",
        "aciklama": "e-Devlet 'SPAS Müstehaklık Sorgulama' hizmetinden sağlık provizyon belgenizin PDF çıktısını alın.",
        "kategori": "Evrak Süreci"
    },
    {
        "id": "chk_komisyon_onay",
        "baslik": "Bölüm Staj Komisyonu Onayı",
        "aciklama": "Staja başlamadan en az 10-15 gün önce belgeleri bölüm staj sorumlusu araştırma görevlisine/hocasına onaylatın.",
        "kategori": "Evrak Süreci"
    },
    {
        "id": "chk_sgk_kontrol",
        "baslik": "e-Devlet SGK İşe Giriş Bildirgesi Kontrolü",
        "aciklama": "Staj başlamadan 1-2 gün önce e-Devlet'e girerek '4A İşe Giriş Bildirgesi'nin üniversite tarafından yatırıldığını doğrulayın.",
        "kategori": "Staj Başlangıcı"
    },
    {
        "id": "chk_defter_yazim",
        "baslik": "Günlük Staj Defteri Tutulması",
        "aciklama": "Her iş gününde yapılan teknik işleri, kullanılan dilleri ve çözülen problemleri staj defterine teknik bir üslupla işleyin.",
        "kategori": "Staj Sırasında"
    },
    {
        "id": "chk_kase_imza",
        "baslik": "Mühendis Kaşe/İmza ve Kapalı Zarf",
        "aciklama": "Staj bitiminde defterin her sayfasını ve kapalı zarftaki Staj Sicil Fişini mezun bir mühendise kaşeletip imzalatın.",
        "kategori": "Staj Sonu"
    },
    {
        "id": "chk_teslim",
        "baslik": "Güz Dönemi Başında Evrak Teslimi",
        "aciklama": "Dönem başladıktan sonraki ilk 1 ay içinde mühürlü zarfı ve defteri staj komisyonuna elden/sistemden teslim edin.",
        "kategori": "Staj Sonu"
    }
]


def generate_personalized_strategy(
    grade_level: str = "3. Sınıf",
    internship_type: str = "staj_2",
    ats_score: int = 85,
    match_score: int = 75,
    hire_probability: int = 70
) -> dict:
    """
    Öğrencinin sınıfına, staj türüne ve analiz motorundan gelen skorlarına göre
    özel haftalık yol haritası ve taktikler üretir.
    """
    taktikler = []
    uyarilar = []
    odak_noktalari = []

    # 1. Sınıf Düzeyine Göre Strateji
    if "1." in grade_level:
        sinif_yorumu = "1. Sınıf öğrencisisiniz. Zorunlu staj genellikle 2. sınıf sonunda başlasa da, bu yılı kulüp projeleri (Teknofest vb.), açık kaynak katkıları ve temel Python/C/Git pratikleriyle geçirmek sizi rakiplerinizin fersah fersah önüne geçirir."
        odak_noktalari = [
            "GitHub profilinde çalışan en az 2 proje yayınlamak",
            "YTÜ öğrenci kulüplerinde (IEEE, İTÜ/YTÜ Yazılım Kulübü, Teknofest Takımları) aktif geliştirici rolü almak",
            "Yaz aylarında startup'larda gönüllü staj fırsatlarını yoklamak"
        ]
    elif "2." in grade_level:
        sinif_yorumu = "2. Sınıf öğrencisisiniz; Staj I (Temel / Laboratuvar Stajı) için ideal yıldasınız. Amacınız şirketin genel işleyişini, temel araçları (Git, SQL, Linux) ve ekip çalışmasını deneyimlemektir."
        odak_noktalari = [
            "CBİKO Ulusal Staj Programı'na (Kariyer Kapısı) kesinlikle başvurmak",
            "CV'de okul projelerini basit ödev gibi değil, STAR formatında gerçek birer yazılım ürünü gibi sunmak",
            "Büyük kurumsal firmaların ve bankaların 2. sınıf staj programlarını taramak"
        ]
    elif "3." in grade_level:
        sinif_yorumu = "3. Sınıf öğrencisisiniz; kariyerinizin EN KRİTİK staj yılındasınız (Staj II). Bu staj, mezuniyet sonrasında doğrudan tam zamanlı iş teklifi (return offer) alabileceğiniz bir kapıdır."
        odak_noktalari = [
            "Doğrudan üretim kodu (production code) yazabileceğiniz kurumsal veya güçlü scale-up şirketleri hedeflemek",
            "Mülakatlarda derin teknik bilgi (Docker, REST API, Veritabanı optimizasyonu, OOP) göstermek",
            "Staj sonunda yöneticinizle 4. sınıf aday mühendisliği için doğrudan görüşme zemini hazırlamak"
        ]
    else:  # 4. Sınıf veya Yeni Mezun
        sinif_yorumu = "4. Sınıf öğrencisisiniz; hedefiniz sadece zorunlu stajı tamamlamak değil, doğrudan 'Aday Mühendis / Part-Time Mühendis' statüsüne geçerek mezun olmadan işinizi garantiye almaktır."
        odak_noktalari = [
            "Haftada 2-3 tam gün çalışabileceğiniz 'Uzun Dönem Staj / Aday Mühendislik' ilanlarına odaklanmak",
            "Bitirme tezi / projenizi şirketin gerçek bir teknik problemiyle entegre etmek",
            "Şirkette tam zamanlıya dönüşüm oranı yüksek teknoloji ekiplerini tercih etmek"
        ]

    # 2. Skorlara Göre Dinamik Aksiyonlar
    if ats_score < 75:
        uyarilar.append(f"⚠️ ATS Puanınız ({ats_score}/100) kritik seviyede! İK botlarının filtrelerine takılmamak için 'ATS Uyumluluk Raporu' sekmesindeki eksik başlık ve eylem fiillerini derhal düzeltin.")
    else:
        taktikler.append(f"✅ ATS Puanınız ({ats_score}/100) güçlü. CV formatınız büyük şirketlerin bot filtrelerini başarıyla geçecek seviyede.")

    if match_score < 65:
        uyarilar.append(f"⚠️ Hedef ilan ile yetenek uyumunuz (%{match_score}) sınırda. İlanda istenen zorunlu yeteneklerden en az 1-2 tanesini öğrenip CV'nize mini bir projeyle eklemeniz şansınızı katlar.")
    else:
        taktikler.append(f"✅ İlan yetenek eşleşmeniz (%{match_score}) rekabetçi. İlanın dilini mülakatlarda somut örneklerle destekleyin.")

    if hire_probability >= 75:
        taktikler.append(f"🚀 İşe kabul ihtimaliniz (%{hire_probability}) oldukça yüksek! Ön yazınızı ilana özel kişiselleştirip doğrudan şirketlerin kariyer sayfalarından ve LinkedIn ilanlarından başvurun.")
    else:
        taktikler.append(f"💡 İşe kabul ihtimalinizi artırmak için zayıf olduğunuz maddeleri 'STAR Madde Güçlendirici' ile zenginleştirin.")

    # 3. Şirket Türü Başvuru Matrisi
    sirket_matrisi = [
        {
            "tur": "Savunma Sanayii & Kamu (Aselsan, Roketsan, Tusaş, Havelsan, Tübitak)",
            "oncelik": "Yüksek (Özellikle 3. ve 4. sınıf)",
            "ortalama_kriter": "Genelde not ortalaması (GANO >= 2.50 veya 3.00) şartı aranır. Başvurular çok erken (Kasım-Şubat) açılır.",
            "tavsiye": "Resmi web sitelerindeki 'Kariyer' portallarını ve Kariyer Kapısı'nı eksiksiz takip edin."
        },
        {
            "tur": "Global & Yerli Teknoloji Devleri (Trendyol, Getir, Hepsiburada, Amazon TR vb.)",
            "oncelik": "Yüksek (Tüm sınıflar)",
            "ortalama_kriter": "Not ortalamasından ziyade GitHub projeleri, HackerRank skoru ve teknik problem çözme yeteneği kritiktir.",
            "tavsiye": "LeetCode Easy/Medium algoritmaları çözün; CV'de canlı çalışan web/mobil uygulamalarınızı öne çıkarın."
        },
        {
            "tur": "Bankacılık & Fintek (KoçDigital, Garanti BBVA Teknoloji, Yapı Kredi, Akbank vb.)",
            "oncelik": "Orta - Yüksek (2. ve 3. sınıf)",
            "ortalama_kriter": "Büyük veri, kurumsal Java/C# mimarisi ve siber güvenlik odaklı staj programları düzenlerler.",
            "tavsiye": "SQL, veri tabanı yapıları ve OOP prensiplerine mülakatta hakim olduğunuzu kanıtlayın."
        },
        {
            "tur": "Teknopark Startup & Scale-up'lar (YTÜ Yıldız Teknopark, İTÜ Çekirdek vb.)",
            "oncelik": "Çok Yüksek (Özellikle hızlı öğrenmek ve inisiyatif almak için)",
            "ortalama_kriter": "Bürokrasi azdır; kurucu veya CTO ile doğrudan çalışma fırsatı sunarlar.",
            "tavsiye": "YTÜ Yıldız Teknopark'taki şirketlere doğrudan kişiselleştirilmiş bir e-posta ve GitHub linkinizle ulaşın."
        }
    ]

    return {
        "sinif_yorumu": sinif_yorumu,
        "odak_noktalari": odak_noktalari,
        "taktikler": taktikler,
        "uyarilar": uyarilar,
        "sirket_matrisi": sirket_matrisi
    }


# --- TEST BLOĞU ---
if __name__ == "__main__":
    print("🚀 strategy_engine.py Test Ediliyor...\n")
    res = generate_personalized_strategy(
        grade_level="3. Sınıf",
        internship_type="staj_2",
        ats_score=85,
        match_score=80,
        hire_probability=78
    )

    print("🎓 Sınıf Değerlendirmesi:")
    print(res["sinif_yorumu"])
    print("\n🎯 Odak Noktaları:")
    for o in res["odak_noktalari"]:
        print(f"  • {o}")
    print("\n💡 Taktikler:")
    for t in res["taktikler"]:
        print(f"  • {t}")
    print("\n✨ strategy_engine.py testi başarıyla tamamlandı!")
