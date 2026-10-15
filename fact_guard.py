"""
Aşama 6 — Uydurma Bilgi Koruyucusu / Fact Guard (fact_guard.py)

Amaç:
    Yapay zekanın (LLM) veya kullanıcının CV'ye mülakatta adayı zor durumda
    bırakacak "uydurma / doğrulanmamış" bilgi eklemesini engellemek.

Denetimler:
    1. Yetkisiz Teknoloji Tespiti (Unauthorized Tech Injection):
       - Üretilen metinde geçen teknolojiler orijinal CV'de var mı?
       - CV'de hiç olmayan (ne doğrudan ne dolaylı) bir teknoloji eklendiyse RİSK alarmı verir.
    2. Uydurma / Somut Sayı Denetimi (Fabricated Metrics):
       - Orijinal maddede olmayan ve yer tutucu `[...]` formatında olmayan
         uydurma yüzdeler (%40), kullanıcı sayıları (5000+ kullanıcı) tespit edilir.
    3. Rol Şişirme / Unvan Abartısı (Role / Seniority Inflation):
       - Stajyer seviyesindeki öğrenciye "Lead Architect", "Kıdemli Yönetici",
         "Teknik Danışman" gibi abartılı roller verilip verilmediğini kontrol eder.
    4. Doldurulmamış Yer Tutucular (Unfilled Placeholders):
       - Metinde hâlâ doldurulmayı bekleyen `[N]`, `[%X]`, `[...]` alanlarını listeler.
"""
import os
import re
import sys
from parser import parse_cv_sections
from job_matcher import get_extractor, fold, build_cv_profile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Şişirilmiş / abartılı unvan kalıpları
INFLATED_ROLES = [
    r"\blead architect\b", r"\bk[ıi]demli mimar\b", r"\bsenior\b", r"\bk[ıi]demli\b",
    r"\bhead of\b", r"\bdirekt[oö]r\b", r"\bcto\b", r"\bchief\b",
    r"\btek ba[sş][ıi]na y[oö]netti\b", r"\bt[uü]m sorumlulu[gğ]u ald[ıi]\b"
]

# Sayısal metrik regex'i (yıllar ve telefonlar hariç)
METRIC_PATTERN = re.compile(
    r"(?<!\w)(?:%\s*\d+|\d+\s*%(?:\s*art[ıi][sş]|\s*azal[ıi][sş])?|"
    r"\d+[\.,]?\d*\s*(?:kullan[ıi]c[ıi]|ki[sş]i|kat[ıi]l[ıi]mc[ıi]|sat[ıi]r|mb|gb|tb|kat|kat[ıi]na|saat|dakika|sn|ms|tl|\$|€))\b",
    re.IGNORECASE
)

# Yer tutucu kalıbı (köşeli parantez içindekiler: [N], [%X], [N+ kullanıcı] vb.)
PLACEHOLDER_PATTERN = re.compile(r"\[[^\]]{1,60}\]")


def extract_original_skills(cv_sections: dict) -> set[str]:
    """Orijinal CV'de geçen (doğrudan veya dolaylı) tüm meşru yeteneklerin kümesini çıkarır."""
    profile = build_cv_profile(cv_sections)
    return set(profile.keys())


def audit_text(
    generated_text: str,
    original_cv_sections: dict,
    original_bullet: str = ""
) -> dict:
    """
    Üretilen metni (CV maddesi veya ön yazı) orijinal CV içeriğiyle karşılaştırarak
    doğruluk ve güvenlik denetimi yapar.
    """
    extractor = get_extractor()
    legit_skills = extract_original_skills(original_cv_sections)

    # 1. Yetkisiz Yetenek Kontrolü
    hits_in_generated = extractor.extract(generated_text)
    generated_skills = {h.canonical: h.text for h in hits_in_generated}

    unauthorized_skills = []
    for skill_name, raw_term in generated_skills.items():
        if skill_name not in legit_skills:
            unauthorized_skills.append({
                "yetenek": skill_name,
                "metindeki_ifade": raw_term,
                "kategori": extractor.skill_category.get(skill_name, "Diger")
            })

    # 2. Doldurulmamış Yer Tutucu Kontrolü
    placeholders = PLACEHOLDER_PATTERN.findall(generated_text)

    # 3. Uydurma Metrik Kontrolü (Yer tutucu olmayan ve orijinalde bulunmayan sayılar)
    # Yer tutucuları geçici olarak gizleyip metin içindeki çıplak metrikleri tara
    text_without_placeholders = PLACEHOLDER_PATTERN.sub(" ", generated_text)
    found_metrics = [m.strip() for m in METRIC_PATTERN.findall(text_without_placeholders)]

    # Orijinal maddede geçen metrikler meşrudur
    original_metrics = set(METRIC_PATTERN.findall(original_bullet)) if original_bullet else set()
    suspicious_metrics = [m for m in found_metrics if m not in original_metrics]

    # 4. Unvan ve Rol Şişirme Kontrolü
    inflated_roles_found = []
    folded_gen = fold(generated_text)
    for role_regex in INFLATED_ROLES:
        if re.search(role_regex, folded_gen):
            inflated_roles_found.append(role_regex.replace(r"\b", "").replace(r"[ıi]", "i").replace(r"[oö]", "ö").replace(r"[sş]", "ş"))

    # Güvenlik Puanı ve Durum Hesaplama
    risk_score = 100
    risk_reasons = []

    if unauthorized_skills:
        penalty = len(unauthorized_skills) * 25
        risk_score -= penalty
        skill_names = ", ".join(u["yetenek"] for u in unauthorized_skills)
        risk_reasons.append(
            f"🚨 CV'nizde yer almayan teknoloji tespit edildi: {skill_names}. "
            f"Mülakatta bu araçlardan soru gelirse zor durumda kalabilirsiniz."
        )

    if suspicious_metrics:
        penalty = len(suspicious_metrics) * 15
        risk_score -= penalty
        metric_str = ", ".join(suspicious_metrics[:3])
        risk_reasons.append(
            f"⚠️ Orijinal metinde bulunmayan somut metrik tespit edildi: {metric_str}. "
            f"Eğer bu sayı gerçek bir başarınız değilse köşeli parantez içinde yer tutucu yapın veya düzeltin."
        )

    if inflated_roles_found:
        risk_score -= 20
        roles_str = ", ".join(inflated_roles_found)
        risk_reasons.append(
            f"⚠️ Abartılı rol / unvan ifadesi tespit edildi: '{roles_str}'. "
            f"Stajyer seviyesi için gerçekçi bir unvan tercih edin."
        )

    risk_score = max(0, min(100, risk_score))

    if risk_score >= 85:
        durum = "GÜVENLİ"
    elif risk_score >= 60:
        durum = "DİKKAT"
    else:
        durum = "YÜKSEK RİSKLİ"

    # Öneriler ve Temizleme
    oneriler = []
    if placeholders:
        oneriler.append(
            f"💡 Metinde henüz doldurulmamış {len(placeholders)} adet yer tutucu var ({', '.join(placeholders[:3])}...). "
            f"CV'nizi kaydetmeden önce bu alanları kendi gerçek sayılarınızla doldurun."
        )
    for r in risk_reasons:
        oneriler.append(r)

    return {
        "guvenlik_skoru": risk_score,
        "durum": durum,
        "yetkisiz_yetenekler": unauthorized_skills,
        "supheli_metrikler": suspicious_metrics,
        "doldurulmamis_yer_tutucular": placeholders,
        "sisirilmis_roller": inflated_roles_found,
        "oneriler": oneriler,
        "orijinal_yetenek_sayisi": len(legit_skills)
    }


# =====================================================================
# TEST BLOĞU
# =====================================================================
if __name__ == "__main__":
    print("=" * 65)
    print("🛡️ UYDURMA BİLGİ KORUYUCUSU (FACT GUARD - AŞAMA 6) TESTİ")
    print("=" * 65)

    ornek_cv = {
        "projeler": "Python ve Streamlit kullanarak CV analiz aracı geliştirdim. Pandas ile verileri modelledim.",
        "yetenekler": "Python, Pandas, SQL, Streamlit, Git"
    }

    # Senaryo 1: Güvenli ve yer tutuculu iyi bir metin
    metin_guvenli = (
        "Python ve Streamlit kütüphaneleriyle interaktif bir CV analiz platformu geliştirdi; "
        "Pandas ile veri temizleme süreçlerini otomatikleştirerek kullanıcıların analiz süresini [%X oranında] kısalttı."
    )

    # Senaryo 2: Halüsinasyonlu (Kafka ve Kubernetes uydurulmuş + sahte %50 hızlandırma)
    metin_riskli = (
        "Lead Architect olarak Apache Kafka ve Kubernetes mimarisi tasarladı; "
        "mikroservisleri optimize ederek sistem hızını %50 artırdı ve 10000 kullanıcıya hizmet verdi."
    )

    print("\n1️⃣ SENARYO 1: Güvenli ve Yer Tutuculu Madde İncelemesi")
    res1 = audit_text(metin_guvenli, ornek_cv, original_bullet="Python ile CV analiz aracı yaptım")
    print(f"   🎯 Güvenlik Skoru : {res1['guvenlik_skoru']}/100 ({res1['durum']})")
    print(f"   📌 Yer Tutucular  : {res1['doldurulmamis_yer_tutucular']}")
    if res1["oneriler"]:
        for o in res1["oneriler"]:
            print(f"   👉 {o}")

    print("\n" + "-" * 65)
    print("2️⃣ SENARYO 2: Riskli ve Uydurma Teknolojili Madde İncelemesi")
    res2 = audit_text(metin_riskli, ornek_cv, original_bullet="Python ile CV analiz aracı yaptım")
    print(f"   🎯 Güvenlik Skoru : {res2['guvenlik_skoru']}/100 ({res2['durum']})")
    print(f"   🚨 Yetkisiz Yetenekler: {[u['yetenek'] for u in res2['yetkisiz_yetenekler']]}")
    print(f"   ⚠️ Şüpheli Metrikler  : {res2['supheli_metrikler']}")
    print(f"   ⚠️ Şişirilmiş Roller  : {res2['sisirilmis_roller']}")
    print("   💡 Öneriler ve Uyarılar:")
    for o in res2["oneriler"]:
        print(f"      👉 {o}")

    print("\n" + "=" * 65)
    print("🎉 AŞAMA 6 MODÜL TESTLERİ TAMAMLANDI!")
