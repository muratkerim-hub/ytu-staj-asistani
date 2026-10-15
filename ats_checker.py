import os
import re
import sys
from parser import extract_text_from_pdf, extract_text_from_docx, parse_cv_sections

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Güçlü eylem fiilleri (Genişletilmiş Türkçe kökler ve İngilizce karşılıkları)
ACTION_VERBS = [
    # Türkçe eylem fiili kökleri
    "geliştir", "tasarla", "yönet", "entegre", "optimize", "kur", "inşa et",
    "analiz", "otomatikleştir", "hızlandır", "azalt", "artır", "kodla", "eğit",
    "modelle", "uygula", "yaz", "gerçekleştir", "çöz", "sağla", "hazırla",
    "yürüt", "ölç", "yapılandır", "deploy", "refactor", "test et", "dönüştür",
    "üret", "denetle", "araştır", "belgele", "dokümante", "sürdür", "derle", "ölçekle",
    # İngilizce güçlü eylem fiilleri
    "built", "designed", "developed", "optimized", "led", "created", "implemented",
    "automated", "analyzed", "engineered", "reduced", "increased", "architected",
    "modeled", "debugged", "tested", "delivered", "deployed", "refactored",
    "configured", "maintained", "evaluated", "trained", "conducted", "formulated",
    "executed", "spearheaded", "authored", "monitored", "scaled"
]

# Kaçınılması gereken pasif/zayıf ifadeler
WEAK_PHRASES = [
    "sorumluydum", "sorumlu oldum", "yardımcı oldum", "yardım ettim", "çalıştım",
    "görev aldım", "ilgilendim", "katkıda bulundum", "destek oldum", "destek verdim",
    "uğraştım", "bakıyordum", "sorumluluğumdaydı", "yer aldım", "katıldım",
    "helped", "worked on", "responsible for", "assisted", "participated in",
    "supported", "handled", "duties included", "familiar with"
]

# Gayriresmi/amatör e-posta anahtar kelimeleri
UNPROFESSIONAL_EMAIL_PATTERNS = [
    r"gamer", r"kral", r"baba", r"pro_", r"xxx", r"1234", r"aslan", r"crazy",
    r"dark", r"reis", r"pasha", r"lord", r"cute", r"sexy", r"boy", r"girl"
]

# Gerçek sayısal etki (Impact Metrics) Regex kalıpları - Yılları (1990-2035) hariç tutar
METRIC_PATTERNS = [
    # Yüzdeler: %40, 40%, %99.9, 99.9%
    r"%\s*\d+(?:[\.,]\d+)?|\d+(?:[\.,]\d+)?\s*%",
    # Çarpanlar: 3x, 5 kat, 2.5 katına
    r"\b\d+(?:[\.,]\d+)?\s*(?:x|kat(?:ına|a)?)\b",
    # Kısaltmalı sayılar: 10k, 50k, 1.5M, 100+, 500+
    r"\b\d+\s*(?:k|\+)\b|\b\d+(?:[\.,]\d+)?\s*(?:m|b)\b",
    # Para birimleri: $500, 10.000 TL, 5000₺, €1000
    r"[\$€₺]\s*\d+|\b\d+(?:[\.,]\d+)?\s*(?:tl|try|usd|eur|dolar)\b",
    # Somut birimler ve hacimler (kullanıcı, satır, süre, veri hacmi, model skoru vb.)
    r"\b\d+(?:[\.,]\d+)?\+?\s*(?:kullanıcı|user|kişi|veri|satır|kayıt|sample|saniye|sn|sec|dk|dakika|min|saat|hour|gün|day|hafta|week|ay|month|proje|müşteri|client|istek|request|qps|fps|ms|mb|gb|tb|kb|puan|score|doğruluk|accuracy|f1|auc|loss)\b",
    # Binlik sayılar (yıl hariç): örn. 10.000, 50 bin
    r"\b\d+\s*bin\b|\b[1-9]\d{0,2}(?:\.\d{3})+\b"
]


def extract_bullets(text: str) -> list[str]:
    """
    Deneyim ve proje metinlerindeki maddeleri (satırları) ayıklar.
    PDF ve DOCX kaynaklı çok satırlı madde kırılmalarını birleştirir.
    Şirket/pozisyon/tarih başlık satırlarını eler.
    """
    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not raw_lines:
        return []

    bullet_prefixes = r"^[\•\-\*\–\—\▪\▫\◦\►\>\d\.\)]+\s*"
    bullets = []
    current_bullet = ""

    for line in raw_lines:
        # Şirket, pozisyon, tarih benzeri meta satırları ele (örn. 'Yazılım Stajyeri | Tech A.Ş. | 2024')
        if "|" in line or " - 20" in line or "/20" in line:
            if current_bullet:
                bullets.append(current_bullet)
                current_bullet = ""
            continue

        is_explicit_bullet = bool(re.match(bullet_prefixes, line))
        cleaned_line = re.sub(bullet_prefixes, "", line).strip()

        if is_explicit_bullet:
            if current_bullet:
                bullets.append(current_bullet)
            current_bullet = cleaned_line
        else:
            # Madde işareti yoksa; önceki cümlenin PDF satır sonu devamı mı kontrol et
            if current_bullet:
                if not current_bullet.endswith((".", "!", "?")) or (cleaned_line and cleaned_line[0].islower()):
                    current_bullet += " " + cleaned_line
                else:
                    bullets.append(current_bullet)
                    current_bullet = cleaned_line
            else:
                current_bullet = cleaned_line

    if current_bullet:
        bullets.append(current_bullet)

    # En az 4 kelimelik anlamlı açıklama maddelerini tut
    valid_bullets = [b for b in bullets if len(b.split()) >= 4]
    return valid_bullets


def check_contact_details(contact_text: str, full_text: str) -> dict:
    """1. Kontrol: İletişim bilgileri ve profesyonellik (15 Puan)"""
    # İletişim bilgilerini hem ayrıştırılan alanda hem de tüm CV metninde tara (altbilgi/yan kolon kaçırmaz)
    search_area = (contact_text + "\n" + full_text).lower()
    earned = 0
    issues = []

    # 1. E-posta kontrolü
    email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", search_area)
    if email_match:
        email = email_match.group(0)
        earned += 5
        local_part = email.split("@")[0]

        # Öğrenci doğum yıllarını (örn. 2002, 2003) profesyonellik cezasından muaf tut
        cleaned_local = re.sub(r"(19\d\d|20[0-1]\d)", "", local_part)
        excessive_digits = sum(c.isdigit() for c in cleaned_local) >= 3
        has_unprof_pattern = any(re.search(pat, local_part) for pat in UNPROFESSIONAL_EMAIL_PATTERNS)

        if has_unprof_pattern or excessive_digits:
            issues.append(
                f"E-posta adresiniz ('{email}') amatör rumuz veya aşırı rakam içeriyor. 'ad.soyad@...' formatı tercih edilmelidir.")
        else:
            earned += 2
    else:
        issues.append("E-posta adresi tespit edilemedi.")

    # 2. Telefon kontrolü (Parantezli, boşluklu, noktalı TR ve uluslararası formatlar)
    phone_match = re.search(r"(?:\+90|0)?\s*\(?5\d{2}\)?[\s\.\-]?\d{3}[\s\.\-]?\d{2}[\s\.\-]?\d{2}", search_area)
    if phone_match:
        earned += 3
    else:
        issues.append("Telefon numarası tespit edilemedi.")

    # 3. LinkedIn kontrolü
    if "linkedin" in search_area:
        earned += 2
    else:
        issues.append("LinkedIn profil linki eksik.")

    # 4. GitHub / Portfolyo kontrolü (Teknik stajlar için kritik)
    if "github" in search_area or "gitlab" in search_area or "kaggle" in search_area:
        earned += 3
    else:
        issues.append("GitHub / Portfolyo linki eksik (Teknik staj değerlendirmelerinde çok kritiktir).")

    earned = min(15, earned)
    status = "GEÇTİ" if earned >= 12 else ("UYARI" if earned >= 8 else "KALDI")
    return {
        "kriter": "İletişim ve Profesyonellik",
        "durum": status,
        "puan": f"{earned}/15",
        "numeric_score": earned,
        "aciklama": "Tüm iletişim kanalları (E-posta, Tel, LinkedIn, GitHub) tam ve profesyonel." if not issues else " | ".join(issues),
        "cozum": "CV'nin en üstüne ad.soyad@ formatında e-posta, telefon, tıklanabilir LinkedIn ve aktif GitHub profilinizi ekleyin."
    }


def check_length_and_pages(full_text: str, page_count: int) -> dict:
    """2. Kontrol: Sayfa sayısı ve kelime yoğunluğu (10 Puan)"""
    word_count = len(full_text.split())
    earned = 10
    issues = []

    # Sayfa sayısı kontrolü (Öğrenci/yeni mezun için 1 sayfa kuralı)
    if page_count == 2:
        earned -= 3
        issues.append("CV 2 sayfa. Öğrenci ve staj başvurularında 1 sayfa olması şiddetle tavsiye edilir.")
    elif page_count > 2:
        earned -= 6
        issues.append(f"CV {page_count} sayfa. Stajyer CV'si için kesinlikle çok uzun (Maksimum 1 sayfa).")

    # Kelime yoğunluğu aralıkları
    if word_count < 180:
        earned -= 6
        issues.append(f"Kelime sayısı çok düşük ({word_count} kelime). Projeler ve teknolojiler yeterince açıklanmamış.")
    elif 180 <= word_count < 250:
        earned -= 2
        issues.append(f"Kelime sayısı alt sınırda ({word_count} kelime). Proje açıklamalarınızı biraz daha detaylandırabilirsiniz.")
    elif 650 < word_count <= 800:
        earned -= 2
        issues.append(f"Kelime sayısı yoğun ({word_count} kelime). Tek sayfada okunabilirlik zorlaşabilir.")
    elif word_count > 800:
        earned -= 4
        issues.append(f"Kelime sayısı aşırı yoğun ({word_count} kelime). İK uzmanları CV'ye ortalama 6-8 saniye ayırır.")

    earned = max(0, min(10, earned))
    status = "GEÇTİ" if earned == 10 else ("UYARI" if earned >= 6 else "KALDI")
    return {
        "kriter": "Uzunluk ve Kelime Yoğunluğu",
        "durum": status,
        "puan": f"{earned}/10",
        "numeric_score": earned,
        "aciklama": f"{page_count} sayfa, {word_count} kelime (İdeal: 1 sayfa, 250-650 kelime)." if not issues else " | ".join(issues),
        "cozum": "CV'nizi tek sayfaya sığdırın ve kelime hacmini 250-650 arasında tutarak en güçlü yönlerinizi öne çıkarın."
    }


def check_standard_sections(parsed_cv: dict) -> dict:
    """3. Kontrol: Standart ATS bölüm başlıkları (15 Puan)"""
    earned = 0
    missing = []
    has_proj = bool(parsed_cv.get("projeler", "").strip())
    has_exp = bool(parsed_cv.get("deneyim", "").strip())

    if parsed_cv.get("egitim", "").strip():
        earned += 4
    else:
        missing.append("Eğitim (Education)")

    if parsed_cv.get("yetenekler", "").strip():
        earned += 4
    else:
        missing.append("Yetenekler (Skills)")

    if has_proj or has_exp:
        earned += 5
    else:
        missing.append("Projeler veya Deneyim")

    if parsed_cv.get("ozet", "").strip():
        earned += 2
    else:
        missing.append("Özet / Profil (Summary)")

    status = "GEÇTİ" if earned >= 13 else ("UYARI" if earned >= 9 else "KALDI")
    
    if not missing:
        if has_proj and has_exp:
            aciklama = "Mükemmel: Eğitim, Yetenekler, Deneyim, Projeler ve Özet başlıklarının tamamı standart ATS formatında bulundu."
        else:
            aciklama = "Tüm temel ATS başlıkları başarıyla tespit edildi."
    else:
        aciklama = f"Eksik veya standart dışı adlandırılmış başlıklar: {', '.join(missing)}"

    return {
        "kriter": "Standart Bölüm Başlıkları",
        "durum": status,
        "puan": f"{earned}/15",
        "numeric_score": earned,
        "aciklama": aciklama,
        "cozum": "Yaratıcı veya süslü başlıklar yerine ATS algoritmalarının tanıdığı evrensel başlıkları (Eğitim, Deneyim, Projeler, Yetenekler, Özet) kullanın."
    }


def check_bullet_lengths(bullets: list[str]) -> dict:
    """4. Kontrol: Madde işaretlerinin kelime uzunluğu dengesi (10 Puan)"""
    if not bullets:
        return {
            "kriter": "Madde İşareti Uzunlukları",
            "durum": "KALDI",
            "puan": "0/10",
            "numeric_score": 0,
            "aciklama": "Deneyim veya Projeler bölümünde analiz edilecek açıklama maddesi bulunamadı.",
            "cozum": "Projelerinizi düz paragraf yerine madde işaretleri (bullet points) halinde özetleyin."
        }

    too_long = [b for b in bullets if len(b.split()) > 32]
    too_short = [b for b in bullets if len(b.split()) < 6]

    earned = 10
    issues = []
    if too_long:
        earned -= min(6, len(too_long) * 3)
        issues.append(f"{len(too_long)} madde çok uzun (32+ kelime, paragraf gibi).")
    if too_short:
        earned -= min(4, len(too_short) * 2)
        issues.append(f"{len(too_short)} madde çok yüzeysel (<6 kelime).")

    earned = max(0, earned)
    status = "GEÇTİ" if earned >= 8 else ("UYARI" if earned >= 5 else "KALDI")
    return {
        "kriter": "Madde İşareti Uzunlukları",
        "durum": status,
        "puan": f"{earned}/10",
        "numeric_score": earned,
        "aciklama": f"İncelenen {len(bullets)} maddenin uzunlukları ideal dengede (8-28 kelime)." if not issues else " ".join(issues),
        "cozum": "Maddeleri 10-25 kelime aralığında tutun. Uzun paragrafları 2 ayrı maddeye bölün, çok kısa olanları detaylandırın."
    }


def check_action_verbs_and_weak_words(bullets: list[str]) -> dict:
    """5. ve 7. Kontrol: Güçlü eylem fiilleri ve zayıf ifadeler (20 Puan)"""
    if not bullets:
        return {
            "kriter": "Eylem Fiilleri ve Güçlü Dil",
            "durum": "KALDI",
            "puan": "0/20",
            "numeric_score": 0,
            "aciklama": "İncelenecek proje veya deneyim maddesi yok.",
            "cozum": "Maddelerinizi 'Geliştirdim, Tasarladım, Entegre ettim, Optimize ettim' gibi güçlü fiillerle başlatın."
        }

    strong_bullets = 0
    weak_found = []

    for b in bullets:
        b_lower = b.lower()
        if any(verb in b_lower for verb in ACTION_VERBS):
            strong_bullets += 1
        for w in WEAK_PHRASES:
            if w in b_lower:
                weak_found.append(w)

    ratio = strong_bullets / len(bullets)
    action_score = round(ratio * 12)  # 12 puan güçlü eylem oranı

    # Zayıf ifadelere daha keskin ceza (her benzersiz zayıf ifade için -3 puan)
    weak_penalty = min(8, len(set(weak_found)) * 3)
    earned = action_score + max(0, 8 - weak_penalty)
    earned = max(0, min(20, earned))

    status = "GEÇTİ" if earned >= 16 else ("UYARI" if earned >= 10 else "KALDI")
    desc = f"Maddelerin %{int(ratio * 100)}'i güçlü teknik eylem fiili içeriyor."
    if weak_found:
        desc += f" ⚠️ Pasif/zayıf ifadeler elenme sebebidir: {', '.join(set(weak_found))}."

    return {
        "kriter": "Eylem Fiilleri ve Zayıf İfadeler",
        "durum": status,
        "puan": f"{earned}/20",
        "numeric_score": earned,
        "aciklama": desc,
        "cozum": "'Sorumluydum / Yardım ettim / Çalıştım' gibi pasif kelimeler yerine 'Python ile ... geliştirdim / mimari tasarladım' aktif diline geçin."
    }


def check_quantifiable_metrics(bullets: list[str]) -> dict:
    """6. Kontrol: Sayısal sonuçlar ve etki metrikleri (15 Puan) - Mezuniyet/başlangıç yıllarını hariç tutar!"""
    if not bullets:
        return {
            "kriter": "Sayısal Sonuçlar (Impact Metrics)",
            "durum": "KALDI",
            "puan": "0/15",
            "numeric_score": 0,
            "aciklama": "İncelenecek madde bulunamadı.",
            "cozum": "Projelerinize ölçülebilir veriler (oran, süre, hacim) ekleyin."
        }

    def has_metric(b_text: str) -> bool:
        lower = b_text.lower()
        return any(bool(re.search(pat, lower)) for pat in METRIC_PATTERNS)

    metric_bullets = sum(1 for b in bullets if has_metric(b))
    ratio = metric_bullets / len(bullets)

    # Keskin ve zorlayıcı barem (En az %50 metrik şartı)
    if ratio >= 0.50:
        earned = 15
    elif ratio >= 0.25:
        earned = 9
    elif metric_bullets >= 1:
        earned = 5
    else:
        earned = 0

    status = "GEÇTİ" if earned >= 12 else ("UYARI" if earned >= 6 else "KALDI")
    return {
        "kriter": "Sayısal Sonuçlar (Impact Metrics)",
        "durum": status,
        "puan": f"{earned}/15",
        "numeric_score": earned,
        "aciklama": f"{len(bullets)} maddenin {metric_bullets} tanesinde somut sayısal etki (%, süre, veri boyutu, kullanıcı hacmi vb.) tespit edildi.",
        "cozum": "Maddelerinize sayı ekleyin: 'Sorgu süresini %30 kısalttım', '150+ aktif kullanıcıya ulaştım', '10.000 satırlık veriyi temizledim'."
    }


def check_date_consistency(full_text: str) -> dict:
    """8. Kontrol: Tarih formatı tutarlılığı (5 Puan)"""
    slash_dates = re.findall(r"\b(0?[1-9]|1[0-2])\/20\d{2}\b", full_text)  # Örn: 09/2025
    dot_dates = re.findall(r"\b(0?[1-9]|1[0-2])\.20\d{2}\b", full_text)    # Örn: 09.2025
    text_dates = re.findall(
        r"\b(ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-zğüşıöç]*\s+20\d{2}\b",
        full_text.lower()
    )

    used_styles = sum([bool(slash_dates), bool(dot_dates), bool(text_dates)])

    if used_styles > 1:
        return {
            "kriter": "Tarih Formatı Tutarlılığı",
            "durum": "UYARI",
            "puan": "2/5",
            "numeric_score": 2,
            "aciklama": "CV içinde birden fazla farklı tarih gösterimi (örn. hem '09/2025' hem 'Eylül 2025') karışık kullanılmış.",
            "cozum": "Tüm CV boyunca tek bir standart format seçin (Örn: 'Eylül 2024 - Haziran 2025' veya '09/2024 - 06/2025')."
        }

    return {
        "kriter": "Tarih Formatı Tutarlılığı",
        "durum": "GEÇTİ",
        "puan": "5/5",
        "numeric_score": 5,
        "aciklama": "Tarih gösterimleri CV boyunca tutarlı.",
        "cozum": "Mevcut düzenli tarih formatını koruyun."
    }


def check_ats_formatting(has_tables: bool, has_images: bool, full_text: str) -> dict:
    """9. Kontrol: Tablo, görsel ve çok sütunlu tasarım riskleri (10 Puan)"""
    earned = 10
    issues = []

    if has_tables:
        earned -= 4
        issues.append("Belgede tablo yapısı tespit edildi (Eski ATS botları tablo hücrelerini sırasız/parçalı okur).")
    if has_images:
        earned -= 3
        issues.append("Belgede görsel/fotoğraf bulundu (Teknik başvurularda fotoğrafsız, tek sütunlu sade ATS formatı tavsiye edilir).")

    # Çok sütunlu tasarım izleri (tek satırda 6+ ardışık boşluk)
    weird_spacing_lines = sum(1 for line in full_text.splitlines() if re.search(r"\S+\s{6,}\S+", line))
    if weird_spacing_lines > 5:
        earned -= 3
        issues.append("Çok sütunlu (iki kolonlu) tasarım izleri tespit edildi; sütunlar metne dönüştürülürken birbirine karışabilir.")

    # Bozuk karakter veya garip unicode kodlaması kontrolü
    if "\ufffd" in full_text:
        earned -= 2
        issues.append("Metin içinde bozuk karakter (encoding hatası) tespit edildi; ATS botları bu kelimeleri okuyamaz.")

    earned = max(0, min(10, earned))
    status = "GEÇTİ" if earned == 10 else ("UYARI" if earned >= 6 else "KALDI")
    return {
        "kriter": "ATS Okunabilirlik (Tablo/Sütun/Görsel)",
        "durum": status,
        "puan": f"{earned}/10",
        "numeric_score": earned,
        "aciklama": "Tasarım sade, ATS dostu ve tek sütunlu." if not issues else " | ".join(issues),
        "cozum": "Canva tarzı iki sütunlu/fotoğraflı şablonlar yerine tek sütunlu standart (Jake's Resume / Harvard) formatı tercih edin."
    }


def evaluate_cv(
    parsed_cv: dict,
    full_text: str,
    page_count: int = 1,
    has_tables: bool = False,
    has_images: bool = False
) -> dict:
    """Tüm 9 ATS kriterini çalıştırır, 100 üzerinden toplam puan ve detaylı rapor döndürür."""
    exp_and_proj = parsed_cv.get("deneyim", "") + "\n" + parsed_cv.get("projeler", "")
    bullets = extract_bullets(exp_and_proj)

    checks = [
        check_contact_details(parsed_cv.get("baslik_ve_kisisel", "") + "\n" + parsed_cv.get("iletisim", ""), full_text),
        check_length_and_pages(full_text, page_count),
        check_standard_sections(parsed_cv),
        check_bullet_lengths(bullets),
        check_action_verbs_and_weak_words(bullets),
        check_quantifiable_metrics(bullets),
        check_date_consistency(full_text),
        check_ats_formatting(has_tables, has_images, full_text)
    ]

    total_score = sum(c["numeric_score"] for c in checks)

    return {
        "toplam_puan": total_score,
        "incelenen_madde_sayisi": len(bullets),
        "detayli_kontroller": checks
    }


# --- GERÇEK DOSYA VEYA ÖRNEK CV TEST BLOĞU ---
if __name__ == "__main__":
    gercek_pdf = "cv.pdf"
    gercek_docx = "cv.docx"

    if os.path.exists(gercek_pdf):
        print(f"📄 Gerçek PDF bulundu ('{gercek_pdf}'), okunuyor...\n")
        res = extract_text_from_pdf(gercek_pdf)
        raw_text, pages, tables, images = res["text"], res["page_count"], False, res["has_images"]
    elif os.path.exists(gercek_docx):
        print(f"📄 Gerçek DOCX bulundu ('{gercek_docx}'), okunuyor...\n")
        res = extract_text_from_docx(gercek_docx)
        raw_text, pages, tables, images = res["text"], res["page_count"], res["has_tables"], False
    else:
        print("ℹ️ Klasörde 'cv.pdf' bulunamadığı için kapsamlı test CV'si inceleniyor...")
        print("(Kendi CV'ni test etmek için PDF dosyanı 'cv.pdf' adıyla proje klasörüne atabilirsin!)\n")
        pages, tables, images = 1, False, False
        raw_text = """
        Murat Kerim Yılmaz
        murat.yilmaz@std.yildiz.edu.tr | 0555 123 45 67 | github.com/muratyilmaz | linkedin.com/in/muratyilmaz

        ÖZET
        Yıldız Teknik Üniversitesi Matematik Mühendisliği öğrencisiyim. Yapay zeka ve veri mühendisliği alanlarında projeler geliştiriyorum.

        EĞİTİM
        Yıldız Teknik Üniversitesi - Matematik Mühendisliği (Eylül 2025 - Haziran 2029)

        PROJELER
        - Python ve Streamlit kullanarak öğrencilerin staj başvurularını analiz eden yapay zeka destekli bir web uygulaması geliştirdim ve 150+ kullanıcı ile test ettim.
        - Kural tabanlı ATS algoritması tasarladım ve metin ayrıştırma süresini %40 hızlandırdım.
        - Kulüp etkinliğinde sponsorluk işleriyle ilgilendim ve ekipte görev aldım.

        YETENEKLER
        Python, C, SQL, Git, Nesne Yönelimli Programlama (OOP), Streamlit, Veri Analizi
        """

    parsed = parse_cv_sections(raw_text)
    rapor = evaluate_cv(parsed, raw_text, page_count=pages, has_tables=tables, has_images=images)

    print("=" * 65)
    print(f"🎯 PROFESYONEL ATS SKORU: {rapor['toplam_puan']} / 100")
    print(f"📌 İncelenen Deneyim/Proje Maddesi: {rapor['incelenen_madde_sayisi']} adet")
    print("=" * 65)

    for c in rapor["detayli_kontroller"]:
        ikon = "✅" if c["durum"] == "GEÇTİ" else ("⚠️" if c["durum"] == "UYARI" else "❌")
        print(f"\n{ikon} [{c['durum']}] {c['kriter']} ({c['puan']})")
        print(f"   🔎 Tespit : {c['aciklama']}")
        if c["durum"] != "GEÇTİ":
            print(f"   💡 Çözüm  : {c['cozum']}")