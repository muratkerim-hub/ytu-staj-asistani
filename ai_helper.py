"""
Aşama 5 — Gemini API ile CV İyileştirme ve Ön Yazı Üretim Modülü (ai_helper.py)

Özellikler:
    1. STAR Metoduyla Madde Güçlendirme:
       - Zayıf / pasif CV maddelerini (örn: "Sponsorluk işleriyle ilgilendim") alır.
       - 3 farklı profesyonel alternatif üretir (Eylem & Metrik Odaklı, Teknik Odaklı, Sonuç Odaklı).
       - ASLA uydurma veri/sayı üretmez; öğrencinin doldurması için [%X / N kişi / N satır]
         formatında köşeli parantezli yer tutucular bırakır.
    2. İlana Özel Ön Yazı (Cover Letter):
       - Şablonik olmayan, YTÜ öğrencisinin gerçek projelerini ilandaki problemlerle
         bağdaştıran 3-4 paragraflık samimi ve profesyonel ön yazı hazırlar.
    3. Hedefe Yönelik Mülakat Soruları ve Yanıt Stratejileri:
       - İlandaki eksik/zayıf noktalardan ve CV'deki projelerden gelebilecek 3-5 teknik soru
         ve nasıl yanıtlanacağına dair STAR rehberi üretir.

Model: .env dosyasından okunur (varsayılan: gemini-2.5-flash)
"""
import json
import os
import re
import sys
from dotenv import load_dotenv
from google import genai
from google.genai import errors

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ortam değişkenlerini yükle
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            API_KEY = st.secrets["GEMINI_API_KEY"]
            os.environ["GEMINI_API_KEY"] = API_KEY
    except Exception:
        pass

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def _get_client() -> genai.Client:
    """Gemini API istemcisini başlatır ve doğrular."""
    global API_KEY
    if not API_KEY:
        API_KEY = os.getenv("GEMINI_API_KEY")
        if not API_KEY:
            try:
                import streamlit as st
                if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
                    API_KEY = st.secrets["GEMINI_API_KEY"]
                    os.environ["GEMINI_API_KEY"] = API_KEY
            except Exception:
                pass

    if not API_KEY:
        raise ValueError(
            "GEMINI_API_KEY .env dosyasında veya Streamlit Secrets içinde bulunamadı! Lütfen geçerli bir API anahtarı ekleyin."
        )
    return genai.Client(api_key=API_KEY)


def _clean_json_response(raw_text: str) -> dict | list:
    """Gemini'den dönen metindeki markdown kod bloklarını temizleyip JSON olarak ayrıştırır."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())


# =====================================================================
# 1) STAR METODUYLA MADDE İYİLEŞTİRME
# =====================================================================
def improve_bullet_point(
    bullet: str,
    target_skills: list[str] = None,
    job_context: str = None
) -> dict:
    """
    Zayıf veya pasif bir CV maddesini STAR metodolojisine göre güçlendirir.
    Uydurma bilgi üretmez; öğrencinin tamamlaması için [%X artış / N adet veri] yer tutucuları bırakır.
    """
    client = _get_client()
    skills_hint = f"\nVurgulanabilecek İlgili Yetenekler: {', '.join(target_skills)}" if target_skills else ""
    context_hint = f"\nHedef İlan/Pozisyon Bağlamı: {job_context[:300]}" if job_context else ""

    prompt = f"""
Sen deneyimli bir teknik işe alım uzmanı ve CV danışmanısın. Bir Türk üniversite öğrencisinin (YTÜ) CV'sindeki zayıf bir deneyim/proje maddesini STAR (Situation, Task, Action, Result) metodolojisine göre profesyonel hale getireceksin.

Öğrencinin Orijinal Maddesi:
"{bullet}"
{skills_hint}{context_hint}

KURALLAR (ÇOK ÖNEMLİ):
1. ASLA hayali veri, gerçekte var olmayan şirket, abartılı veya sahte bir metrik UYDURMA.
2. Sayısal sonuç kısımlarını öğrencinin kendi gerçek verisiyle doldurması için KÖŞELİ PARANTEZ yer tutucu olarak bırak:
   Örnek: "[%X oranında]", "[N+ kullanıcı]", "[N haftalık sürede]", "[N satırlık veri seti]".
3. Güçlü eylem fiilleri kullan (geliştirdi, tasarladı, optimize etti, yönetti, modelledi, entegre etti, analiz etti).
4. Pasif ve zayıf ifadelerden ("yardımcı oldum", "sorumluydum", "çalıştım", "ilgili işleri yaptım") kesinlikle kaçın.
5. 3 farklı odak noktasıyla 3 alternatif üret:
   - Alternatif 1 (Eylem & Metrik Odaklı): Süreç + somut aksiyon + sayısal sonuç yer tutucusu.
   - Alternatif 2 (Teknik & Mimari Odaklı): Kullanılan teknolojiler, metodoloji veya araçların ön plana çıktığı teknik anlatım.
   - Alternatif 3 (Etki & Problem Çözme Odaklı): Çözülen problem ve ekibe/projeye sağlanan iş değeri odaklı.

Yanıtını SADECE aşağıdaki JSON formatında ver (başka açıklama veya metin ekleme):
{{
  "orijinal_madde": "{bullet}",
  "tespit_edilen_eksikler": ["Zayıf fiil kullanımı (ilgilenildi)", "Ölçülebilir metrik yok"],
  "alternatifler": [
    {{
      "odak": "Eylem & Metrik Odaklı",
      "metin": "...",
      "ipucu": "Köşeli parantez içindeki [...] alanını projenizdeki gerçek sayıyla güncelleyin."
    }},
    {{
      "odak": "Teknik & Metodoloji Odaklı",
      "metin": "...",
      "ipucu": "Kullandığınız spesifik kütüphane veya araçları parantez içlerine ekleyin."
    }},
    {{
      "odak": "Etki & Problem Çözme Odaklı",
      "metin": "...",
      "ipucu": "Çözdüğünüz problemin projeye olan katkısını belirtin."
    }}
  ]
}}
"""
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        return {"success": True, "data": _clean_json_response(response.text)}
    except Exception as e:
        return {"success": False, "error": f"Yapay zeka analiz hatası: {str(e)}"}


# =====================================================================
# 2) İLANA ÖZEL ÖN YAZI (COVER LETTER) ÜRETİMİ
# =====================================================================
def generate_cover_letter(
    cv_sections: dict,
    job_text: str,
    match_result: dict = None
) -> dict:
    """
    Öğrencinin gerçek CV içeriği ile hedef staj ilanını bağdaştıran,
    şablonik olmayan 3 paragraflık profesyonel bir ön yazı hazırlar.
    """
    client = _get_client()

    # CV özetini hazırla
    cv_summary = []
    if cv_sections.get("baslik_ve_kisisel"):
        cv_summary.append("KİŞİSEL: " + cv_sections["baslik_ve_kisisel"][:150])
    if cv_sections.get("egitim"):
        cv_summary.append("EĞİTİM: " + cv_sections["egitim"])
    if cv_sections.get("projeler"):
        cv_summary.append("PROJELER:\n" + cv_sections["projeler"])
    if cv_sections.get("deneyim"):
        cv_summary.append("DENEYİM:\n" + cv_sections["deneyim"])
    if cv_sections.get("yetenekler"):
        cv_summary.append("YETENEKLER: " + cv_sections["yetenekler"])

    cv_text = "\n\n".join(cv_summary)

    # Varsa eşleşme sonuçlarından kanıtlı yetenekleri al
    proven_skills = []
    if match_result and match_result.get("gereksinimler"):
        proven_skills = [
            g["eslesen_yetenek"] for g in match_result["gereksinimler"]
            if g.get("durum") == "kanitli" and g.get("eslesen_yetenek")
        ]

    prompt = f"""
Sen bir kariyer danışmanısın. Yıldız Teknik Üniversitesi (YTÜ) öğrencisi için aşağıdaki staj ilanına özel profesyonel, samimi ve ikna edici bir ÖN YAZI (Cover Letter) kaleme alacaksın.

ÖĞRENCİNİN GERÇEK CV BİLGİLERİ:
\"\"\"
{cv_text}
\"\"\"

HEDEF STAJ İLANI:
\"\"\"
{job_text[:1200]}
\"\"\"

KANITLI VE İLANLA EŞLEŞEN YETENEKLER: {', '.join(proven_skills) if proven_skills else 'CV Projelerindeki araçlar'}

KURALLAR (ÇOK ÖNEMLİ):
1. ASLA şablonik, içi boş beylik cümleler kurma ("Kendimi geliştirmek için can atıyorum", "Saygılarımla arz ederim" gibi klişeler yerine somut bağlar kur).
2. Öğrencinin CV'sinde OLMAYAN bir teknoloji, şirket veya projeden ASLA bahsetme (halüsinasyon yasak).
3. 3-4 paragraflık akıcı bir yapı kur:
   - Başlık ve Hitap: Şirket adı ve pozisyonu içeren profesyonel hitap.
   - Paragraf 1 (Kanca & Motivasyon): Neden bu şirket ve neden bu rol? Öğrencinin YTÜ mühendislik/analitik altyapısı ile şirketin faaliyet alanı arasındaki bağ.
   - Paragraf 2 (Teknik Kanıt & Proje Uyumu): CV'sindeki EN İLGİLİ somut projeyi ilandaki bir gereksinimle doğrudan eşleştir. Ne yaptı, hangi araçla çözdü?
   - Paragraf 3 (Değer Önerisi & Staj Vizyonu): Staj boyunca ekibe nasıl yük olmadan hızla adapte olup katkı sağlayabileceği.
   - Kapanış: Görüşme isteği ve profesyonel veda.
4. Türkçe dilbilgisine, saygılı ve özgüvenli tona dikkat et.

Yanıtını SADECE aşağıdaki JSON formatında ver:
{{
  "baslik": "İlgili Departmana / Pozisyona Hitap Başlığı",
  "paragraf_giris": "...",
  "paragraf_teknik_kanit": "...",
  "paragraf_katki_vizyon": "...",
  "kapanis_ve_imza": "...",
  "tam_metin": "Tüm paragrafların birleştirilmiş akıcı hali"
}}
"""
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        return {"success": True, "data": _clean_json_response(response.text)}
    except Exception as e:
        return {"success": False, "error": f"Ön yazı üretim hatası: {str(e)}"}


# =====================================================================
# 3) MÜLAKAT HAZIRLIK SORULARI VE STAR YANIT REHBERİ
# =====================================================================
def generate_interview_prep(
    cv_sections: dict,
    job_text: str,
    match_result: dict = None
) -> dict:
    """
    Eşleştirme motorunun bulduğu eksik/zayıf noktalardan ve öğrencinin
    projelerinden gelebilecek 3-4 teknik/davranışsal mülakat sorusu ve yanıt ipucu üretir.
    """
    client = _get_client()

    missing_items = []
    if match_result:
        if match_result.get("eksik_zorunlu"):
            missing_items.extend([m["etiket"] for m in match_result["eksik_zorunlu"]])
        if match_result.get("zayif_kanit"):
            missing_items.extend([m["eslesen_yetenek"] for m in match_result["zayif_kanit"] if m.get("eslesen_yetenek")])

    projeler = cv_sections.get("projeler", "")
    deneyim = cv_sections.get("deneyim", "")

    prompt = f"""
Sen bir kıdemli teknik mülakatçısın. Aşağıdaki CV'ye ve staj ilanına bakarak adayı zorlayabilecek ama adil 3-4 adet mülakat sorusu hazırlayacaksın.

Öğrencinin Projeleri/Deneyimi:
{projeler}
{deneyim}

İlanda İstenip CV'de Eksik veya Zayıf Görünen Konular:
{', '.join(missing_items[:6]) if missing_items else 'Genel teknik ve ekip yetkinlikleri'}

Hedef İlan Özeti:
{job_text[:800]}

KURALLAR:
1. Sorular gerçekçi bir teknik liderin stajyere soracağı tarzda olmalı.
2. Sorulardan en az 1 tanesi adayın CV'sindeki projenin teknik mimarisine / zorluklarına odaklanmalı ("Neden bu aracı seçtin?", "Karşılaştığın en büyük darboğaz neydi?").
3. Sorulardan en az 1 tanesi adayın bilmediği/eksik olduğu bir teknolojiyi sorarsa adayın dürüstçe ama öğrenme azmini göstererek nasıl yanıt vereceğini öğretmeli.
4. Her soru için öğrencinin STAR formatında nasıl yanıt verebileceğine dair ipucu sağla.

Yanıtını SADECE aşağıdaki JSON formatında ver:
{{
  "sorular": [
    {{
      "soru_turu": "Proje Derinliği / Eksik Teknoloji / Davranışsal",
      "soru": "...",
      "mulakatcinin_amaci": "Bu soruda neyi test ediyor?",
      "strateji_ve_ornek_yanit": "STAR adımlarıyla nasıl cevap verilmeli?"
    }}
  ]
}}
"""
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        return {"success": True, "data": _clean_json_response(response.text)}
    except Exception as e:
        return {"success": False, "error": f"Mülakat hazırlık hatası: {str(e)}"}


# =====================================================================
# TEST BLOĞU
# =====================================================================
if __name__ == "__main__":
    print("=" * 65)
    print("🤖 GEMINI AI YARDIMCISI (AŞAMA 5) TEST EDİLİYOR...")
    print(f"📌 Bağlanılan Model: {MODEL_NAME}")
    print("=" * 65)

    # 1. Test: Zayıf Madde Güçlendirme
    zayif_madde = "Kulüp etkinliğinde sponsorluk işleriyle ilgilendim ve ekipte görev aldım."
    print(f"\n1️⃣ Zayıf Madde Analizi:")
    print(f"   Girdi: \"{zayif_madde}\"")

    res_bullet = improve_bullet_point(
        bullet=zayif_madde,
        target_skills=["Takım Çalışması", "İletişim Becerileri", "Proje Yönetimi"],
        job_context="Veri Bilimi ve Yapay Zeka Stajyeri"
    )

    if res_bullet["success"]:
        data = res_bullet["data"]
        print("   ✅ Tespit Edilen Eksikler:", ", ".join(data.get("tespit_edilen_eksikler", [])))
        for idx, alt in enumerate(data.get("alternatifler", []), 1):
            print(f"\n   🎯 Alternatif {idx} [{alt['odak']}]:")
            print(f"      👉 {alt['metin']}")
            print(f"      💡 İpucu: {alt['ipucu']}")
    else:
        print("   ❌ HATA:", res_bullet["error"])

    # 2. Test: Ön Yazı Üretimi
    print("\n" + "=" * 65)
    print("2️⃣ İlana Özel Ön Yazı Üretimi:")
    ornek_cv_sections = {
        "baslik_ve_kisisel": "Murat Kerim Yılmaz | Yıldız Teknik Üniversitesi Matematik Mühendisliği",
        "projeler": "Python ve Streamlit kullanarak CV analiz aracı geliştirdim. 150+ kullanıcıyla test ettim. Pandas ile veri setlerini temizledim.",
        "yetenekler": "Python, SQL, Streamlit, Pandas, Git, Veri Analizi"
    }
    ornek_ilan = "ABC Teknoloji - Veri Bilimi Stajyeri. Python, Pandas, SQL bilen, veri analizi ve dashboard geliştirme deneyimi olan stajyer aranıyor."

    res_cl = generate_cover_letter(ornek_cv_sections, ornek_ilan)
    if res_cl["success"]:
        cl_data = res_cl["data"]
        print(f"   📌 Başlık: {cl_data.get('baslik')}\n")
        print(f"   📄 Giriş: {cl_data.get('paragraf_giris')[:160]}...\n")
        print(f"   🔬 Teknik Kanıt: {cl_data.get('paragraf_teknik_kanit')[:160]}...\n")
        print(f"   🚀 Vizyon: {cl_data.get('paragraf_katki_vizyon')[:160]}...\n")
        print("   ✅ Ön yazı başarıyla üretildi!")
    else:
        print("   ❌ HATA:", res_cl["error"])

    print("\n" + "=" * 65)
    print("🎉 AŞAMA 5 MODÜL TESTLERİ TAMAMLANDI!")
