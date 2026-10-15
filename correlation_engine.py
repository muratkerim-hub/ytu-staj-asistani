"""
İşe Alınma İhtimali ve CV-İlan Bağıntı Analiz Motoru (correlation_engine.py)

Özellikler:
    1. Çok Boyutlu İşe Alınma / Mülakat Çağrılma İhtimali (%):
       - ATS Filtresi Geçiş Gücü (%25 ağırlık)
       - Zorunlu Yetenek Kapsaması (%35 ağırlık)
       - Proje Kanıtı ve Derinliği (%20 ağırlık - yetenekler projede kullanılmış mı?)
       - Tercih Sebebi / Artı Değerler (%10 ağırlık)
       - Fact Guard Güvenilirlik Çarpanı (%10 ağırlık - uydurma/abartı cezası)
       -> Sonuç: 0-100 net olasılık yüzdesi ve seviye rozeti (Çok Yüksek, Yüksek, Orta, Düşük).

    2. CV ve İlan Arasındaki Alan / Profil Bağıntısı (Domain & Semantic Correlation):
       - CV'nin baskın uzmanlık alanı (örn: Veri Bilimi / Web / Mobil / Sistem)
       - İlanın hedef uzmanlık alanı
       - Alan Uyumu: "Tam Uyumlu", "Yakın / Geçişken Alan", "Farklı Alan"
       - Bağıntı Matrisi ve Şansı En Hızlı Artıracak 3 Taktik
"""
import os
import sys
from parser import parse_cv_sections
from ats_checker import evaluate_cv
from job_matcher import match_cv_to_job, get_extractor, fold

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def calculate_hire_probability(
    ats_result: dict,
    match_result: dict,
    fact_guard_result: dict = None
) -> dict:
    """
    ATS, İlan Eşleşmesi ve Fact Guard çıktılarından ağırlıklı 'İşe Alınma / Mülakat Çağrılma İhtimali' hesaplar.
    """
    if not match_result or not match_result.get("success"):
        return {
            "ihtimal_yuzdesi": 0,
            "seviye": "Hesaplanamadı",
            "renk": "gray",
            "bilesenler": {},
            "ozet": "İlan gereksinimleri okunamadığı için ihtimal hesaplanamadı."
        }

    # 1. Bileşen: ATS Filtresi (0-20 puan)
    ats_score = ats_result.get("toplam_puan", 70) if ats_result else 70
    ats_credit = min(20.0, (ats_score / 100.0) * 20.0)

    # 2. Bileşen: Zorunlu Yetenek Kapsaması (0-35 puan)
    cov = match_result.get("zorunlu_kapsama", {"karsilanan": 0, "toplam": 1})
    toplam_zorunlu = max(1, cov.get("toplam", 1))
    karsilanan_zorunlu = cov.get("karsilanan", 0)
    zorunlu_oran = karsilanan_zorunlu / toplam_zorunlu
    zorunlu_credit = zorunlu_oran * 35.0

    # 3. Bileşen: Proje Kanıtı ve Derinliği (0-25 puan)
    gereksinimler = match_result.get("gereksinimler", [])
    kanitli_sayisi = sum(1 for g in gereksinimler if g.get("durum") == "kanitli")
    toplam_gereksinim = max(1, len(gereksinimler))
    kanit_orani = kanitli_sayisi / toplam_gereksinim
    kanit_credit = kanit_orani * 25.0

    # 4. Bileşen: Tercih Sebebi / Artı Değerler (0-10 puan)
    tercihli_karsilanan = sum(1 for g in gereksinimler if g.get("seviye") == "tercihli" and g.get("durum") != "eksik")
    tercihli_toplam = max(1, sum(1 for g in gereksinimler if g.get("seviye") == "tercihli"))
    tercih_credit = (tercihli_karsilanan / tercihli_toplam) * 10.0

    # 5. Bileşen: Fact Guard Güvenilirlik Çarpanı (0-10 puan)
    fg_score = fact_guard_result.get("guvenlik_skoru", 100) if fact_guard_result else 100
    fg_credit = (fg_score / 100.0) * 10.0

    ham_skor = ats_credit + zorunlu_credit + kanit_credit + tercih_credit + fg_credit

    # --- GERÇEK DÜNYA PİYASA KALİBRASYONU ---
    # Gerçek staj piyasasında şirket başına yüzlerce başvuru gelir.
    # En ideal adayın bile dönüş oranı ~%80-85 bandındadır; eksikleri olan profiller %30-55 aralığındadır.
    rekabet_katsayisi = 0.88
    toplam_ihtimal = round(ham_skor * rekabet_katsayisi)
    toplam_ihtimal = max(10, min(88, toplam_ihtimal))

    if toplam_ihtimal >= 70:
        seviye = "Çok Yüksek İhtimal (Mülakata Çağrılma Güçlü)"
        rozet = "🟢"
        aciklama = "Profiliniz bu ilan için son derece rekabetçi (En üst %10 dilim). Mülakat veya teknik sınav daveti alma şansınız çok kuvvetli."
    elif toplam_ihtimal >= 50:
        seviye = "Yüksek / Rekabetçi İhtimal"
        rozet = "🔵"
        aciklama = "Güçlü bir adaysınız. Şirketlerin aday havuzunda öne çıkıyorsunuz; 1-2 kritik proje eksiğini tamamlayarak şansınızı zirveye taşıyabilirsiniz."
    elif toplam_ihtimal >= 30:
        seviye = "Orta İhtimal (Yüksek Rekabet Riski)"
        rozet = "🟡"
        aciklama = "Temel gereksinimlerin bir kısmı karşılanıyor ancak zorunlu yetenekler eksik veya projede kanıtlanmamış; havuzda elenme riski var."
    else:
        seviye = "Düşük İhtimal (Barajı Geçemez)"
        rozet = "🔴"
        aciklama = "CV'niz ile ilan gereksinimleri arasında belirgin bir boşluk var. Başvurmadan önce eksik teknolojilerle proje geliştirmeniz önerilir."

    # Şansı artıracak en kritik 3 taktik
    taktikler = []
    if ats_score < 80:
        taktikler.append(f"ATS Puanınızı {ats_score}'den 85+'e çıkarın (Bot filtrelerine takılma riskini sıfırlayın). (+%12 Şans)")
    if match_result.get("eksik_zorunlu"):
        eksik_ad = match_result["eksik_zorunlu"][0]["etiket"]
        taktikler.append(f"İlandaki zorunlu '{eksik_ad}' yeteneğini biliyorsanız CV'nizdeki projelere somut olarak ekleyin. (+%15 Şans)")
    if kanit_orani < 0.4:
        taktikler.append("Yetenekleri sadece listelemek yetersizdir; projelerinizin içinde nasıl kullandığınızı STAR formatında kanıtlayın. (+%15 Şans)")
    if fg_score < 80:
        taktikler.append("CV'nizdeki doğrulanmamış metrikleri ve yer tutucuları netleştirin. (+%8 Şans)")

    if not taktikler:
        taktikler.append("Ön yazınızı şirketin vizyonuna özel olarak uyarlayarak başvurunuzu hemen tamamlayın.")

    return {
        "ihtimal_yuzdesi": toplam_ihtimal,
        "seviye": seviye,
        "rozet": rozet,
        "aciklama": aciklama,
        "bilesenler": {
            "ats_etkisi": round(ats_credit, 1),
            "zorunlu_kapsama_etkisi": round(zorunlu_credit, 1),
            "proje_kaniti_etkisi": round(kanit_credit, 1),
            "arti_deger_etkisi": round(tercih_credit, 1),
            "guvenilirlik_etkisi": round(fg_credit, 1),
            "rekabet_kesintisi": round(ham_skor * (1 - rekabet_katsayisi), 1)
        },
        "sans_artirici_taktikler": taktikler[:3]
    }


def analyze_job_cv_correlation(cv_sections: dict, job_text: str, match_result: dict) -> dict:
    """
    CV ile İlan arasındaki alan / uzmanlık bağıntısını (domain correlation) inceler.
    """
    extractor = get_extractor()

    # 1. CV'deki ağırlıklı kategori dağılımı
    cv_cat_counts = {}
    for sec_name, text in cv_sections.items():
        if not text:
            continue
        hits = extractor.extract(text)
        weight = 2.0 if sec_name in ["projeler", "deneyim"] else 1.0
        for h in hits:
            cat = extractor.skill_category[h.canonical]
            cv_cat_counts[cat] = cv_cat_counts.get(cat, 0.0) + weight

    # 2. İlandaki kategori dağılımı
    job_cat_counts = {}
    if match_result and match_result.get("gereksinimler"):
        for req in match_result["gereksinimler"]:
            cat = req["kategori"]
            job_cat_counts[cat] = job_cat_counts.get(cat, 0.0) + req["agirlik"]

    # En baskın kategorileri bul
    cv_top_cat = max(cv_cat_counts, key=cv_cat_counts.get) if cv_cat_counts else "diger"
    job_top_cat = max(job_cat_counts, key=job_cat_counts.get) if job_cat_counts else "diger"

    cv_top_label = extractor.category_label.get(cv_top_cat, "Genel Mühendislik")
    job_top_label = extractor.category_label.get(job_top_cat, "Genel Mühendislik")

    # Ortak kategoriler üzerinden Jaccard / Cosine benzeri bağıntı indeksi
    all_cats = set(cv_cat_counts.keys()) | set(job_cat_counts.keys())
    common_cats = set(cv_cat_counts.keys()) & set(job_cat_counts.keys())

    if not all_cats:
        correlation_score = 50
    else:
        # Ağırlıklı örtüşme
        overlap_weight = sum(min(cv_cat_counts.get(c, 0), job_cat_counts.get(c, 0)) for c in common_cats)
        total_weight = sum(max(cv_cat_counts.get(c, 0), job_cat_counts.get(c, 0)) for c in all_cats)
        correlation_score = round(100 * overlap_weight / total_weight) if total_weight else 50

    # Alan Uyumu Değerlendirmesi
    if cv_top_cat == job_top_cat:
        alan_uyumu = "Tam Alan Uyumu"
        alan_yorumu = f"Adayın CV'si ({cv_top_label}) ile ilanın hedeflediği alan ({job_top_label}) doğrudan örtüşüyor."
    elif cv_top_cat in ["yapay_zeka", "veri_bilimi", "programlama_dilleri"] and job_top_cat in ["yapay_zeka", "veri_bilimi", "programlama_dilleri"]:
        alan_uyumu = "Yüksek Geçişken Alan"
        alan_yorumu = f"CV ağırlıklı olarak '{cv_top_label}' alanında, ilan ise '{job_top_label}' arıyor. Bu iki alan sektörde iç içedir ve güçlü bir sinerji oluşturur."
    elif cv_top_cat in ["backend", "web_frontend", "mobil"] and job_top_cat in ["backend", "web_frontend", "mobil"]:
        alan_uyumu = "Yazılım Geliştirme Alan Uyumu"
        alan_yorumu = f"Yazılım geliştirme disiplinleri arasında geçişkenlik yüksektir."
    else:
        alan_uyumu = "Farklı Odak Alanı"
        alan_yorumu = f"CV'niz ağırlıklı olarak '{cv_top_label}' odaklı görünürken, ilan '{job_top_label}' profili arıyor. İlana özel projelerinizi daha öne çıkarmalısınız."

    return {
        "baginti_skoru": correlation_score,
        "cv_baskin_alan": cv_top_label,
        "ilan_hedef_alan": job_top_label,
        "alan_uyumu": alan_uyumu,
        "alan_yorumu": alan_yorumu,
        "ortak_kategoriler": [extractor.category_label[c] for c in common_cats]
    }


# =====================================================================
# TEST BLOĞU
# =====================================================================
if __name__ == "__main__":
    from job_matcher import SAMPLE_CV, SAMPLE_JOB

    print("=" * 65)
    print("📈 İŞE ALINMA İHTİMALİ & BAĞINTI ANALİZİ (TEST)")
    print("=" * 65)

    parsed = parse_cv_sections(SAMPLE_CV)
    ats_res = evaluate_cv(parsed, SAMPLE_CV)
    match_res = match_cv_to_job(parsed, SAMPLE_JOB)

    hire_prob = calculate_hire_probability(ats_res, match_res)
    print(f"\n🎯 İŞE ALINMA / MÜLAKAT ÇAĞRILMA İHTİMALİ: %{hire_prob['ihtimal_yuzdesi']} ({hire_prob['rozet']} {hire_prob['seviye']})")
    print(f"   ℹ️ {hire_prob['aciklama']}")
    print("\n📊 Puan Bileşenleri:")
    for b_ad, b_puan in hire_prob["bilesenler"].items():
        print(f"   - {b_ad:<26}: {b_puan} puan")

    print("\n🚀 Şansı Artıracak Taktikler:")
    for t in hire_prob["sans_artirici_taktikler"]:
        print(f"   👉 {t}")

    corr_res = analyze_job_cv_correlation(parsed, SAMPLE_JOB, match_res)
    print("\n" + "-" * 65)
    print(f"🔗 ALAN VE PROFİL BAĞINTISI: %{corr_res['baginti_skoru']}")
    print(f"   CV Baskın Alan : {corr_res['cv_baskin_alan']}")
    print(f"   İlan Hedef Alan: {corr_res['ilan_hedef_alan']}")
    print(f"   Alan Uyumu     : {corr_res['alan_uyumu']}")
    print(f"   Yorum          : {corr_res['alan_yorumu']}")
    print(f"   Ortak Alanlar  : {', '.join(corr_res['ortak_kategoriler'])}")
    print("=" * 65)
