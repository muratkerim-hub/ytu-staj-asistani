"""
Aşama 8 — İnteraktif Mülakat Simülatörü ve Koçu (interview_bot.py)

Özellikler:
    1. Rol Bazlı Mülakatçı Modları:
       - "Teknik Lider": Mimari kararlar, veri yapıları, araç seçimleri ve hata ayıklama odaklı.
       - "İK / İşe Alım Uzmanı": Takım çalışması, kriz yönetimi, öğrenme hızı ve motivasyon odaklı.
       - "YTÜ Staj Mentoru": Samimi, yapıcı, adayı cesaretlendiren ve anında rehberlik eden mod.
    2. Cevap Değerlendirme & Takip Sorusu (Follow-up):
       - Öğrencinin cevabını STAR metoduna, somutluğuna ve teknik doğruluğuna göre 1-10 puanlar.
       - "Neyi iyi yaptın?", "Neyi eksik bıraktın?" analizi sunar.
       - Cevaptan yola çıkarak gerçek bir mülakatçı gibi takip (follow-up) sorusu sorar.
    3. Mülakat Sonu Karnesi:
       - Oturum bitiminde genel performans skoru (0-100), güçlü yönler ve geliştirilmesi gereken alanlar.
"""
import json
import os
import sys
import time
from dotenv import load_dotenv
from google import genai

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

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
        raise ValueError("GEMINI_API_KEY .env dosyasında veya Streamlit Secrets içinde bulunamadı!")
    return genai.Client(api_key=API_KEY)


def _call_gemini_with_retry(prompt: str, max_retries: int = 3) -> str:
    """Geçici API 503/429 yoğunluklarında bekleme ile yeniden dener."""
    client = _get_client()
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            return response.text
        except Exception as e:
            err_msg = str(e)
            if ("503" in err_msg or "UNAVAILABLE" in err_msg or "429" in err_msg) and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2.5
                time.sleep(wait_time)
                continue
            raise e


def _clean_json_response(raw_text: str) -> dict:
    cleaned = raw_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())


ROLE_PROMPTS = {
    "Teknik Lider": (
        "Sen deneyimli, analitik düşünen ve adayın iddia ettiği teknolojileri gerçekten bilip bilmediğini "
        "test eden bir Kıdemli Teknik Lidersin. Yüzeysel cevapları kabul etmezsin; 'Neden bu kütüphaneyi seçtin?', "
        "'Hangi problemle karşılaştın ve nasıl çözdün?' gibi derin teknik detayları sorgularsın."
    ),
    "İK / İşe Alım Uzmanı": (
        "Sen kurumsal bir şirketin İşe Alım Uzmanısın. Adayın iletişim becerilerini, takım çalışmasına yatkınlığını, "
        "öğrenme azmini, stres anındaki tutumunu ve şirket kültürüne uyumunu (Culture-Fit) test edersin."
    ),
    "YTÜ Staj Mentoru": (
        "Sen Yıldız Teknik Üniversitesi mezunu, şu an sektörde çalışan yardımsever ve samimi bir mentorsun. "
        "Adayın eksiklerini kırmadan gösterir, mülakat heyecanını yatıştırır ve cevabı nasıl daha profesyonel "
        "hale getirebileceğini öğretirsin."
    )
}


# =====================================================================
# 1) MÜLAKAT OTURUMU BAŞLATMA
# =====================================================================
def start_interview(
    cv_sections: dict,
    job_text: str,
    interviewer_role: str = "Teknik Lider"
) -> dict:
    """
    CV ve ilan bağlamını inceleyerek mülakatın ilk açılış sorusunu ve odak noktasını belirler.
    """
    persona = ROLE_PROMPTS.get(interviewer_role, ROLE_PROMPTS["Teknik Lider"])

    projeler = cv_sections.get("projeler", "")
    deneyim = cv_sections.get("deneyim", "")
    egitim = cv_sections.get("egitim", "")

    prompt = f"""
{persona}

Hedef Staj İlanı:
\"\"\"
{job_text[:800]}
\"\"\"

Öğrencinin CV Bilgileri:
- Eğitim: {egitim}
- Projeler: {projeler[:800]}
- Deneyim: {deneyim[:400]}

GÖREVİN:
Mülakata profesyonel ve gerçekçi bir giriş yap. Adayı karşıla ve CV'sindeki en ilgili projeden veya hedeflerinden yola çıkarak İLK MÜLAKAT SORUSUNU sor.

KURALLAR:
1. İlk soru çok genel veya klişe ("Bize kendinden bahset") olmasın; doğrudan adayın CV'sindeki bir proje/teknoloji ile ilanın kesişim noktasına odaklansın.
2. Tonalite seçilen mülakatçı rolüne ({interviewer_role}) uygun olsun.

Yanıtını SADECE aşağıdaki JSON formatında ver:
{{
  "karsilama_mesaji": "Kısa ve role uygun bir karşılama cümlesi",
  "ilk_soru": "İlk mülakat sorusu",
  "sorunun_amaci": "Bu soruda adayın hangi yönü test ediliyor?"
}}
"""
    try:
        raw_json = _call_gemini_with_retry(prompt)
        return {"success": True, "data": _clean_json_response(raw_json)}
    except Exception as e:
        return {"success": False, "error": f"Mülakat başlatma hatası: {str(e)}"}


# =====================================================================
# 2) CEVABI DEĞERLENDİRME & TAKİP SORUSU
# =====================================================================
def evaluate_and_respond(
    conversation_history: list[dict],
    user_answer: str,
    cv_sections: dict,
    job_text: str,
    interviewer_role: str = "Teknik Lider"
) -> dict:
    """
    Kullanıcının son cevabını değerlendirir, puanlar ve mülakatı devam ettirecek bir sonraki soruyu sorar.
    """
    persona = ROLE_PROMPTS.get(interviewer_role, ROLE_PROMPTS["Teknik Lider"])

    # Konuşma geçmişini metne dök
    history_str = ""
    for msg in conversation_history[-6:]:  # Son 3 soru-cevap çifti
        speaker = "Mülakatçı" if msg.get("role") == "assistant" else "Aday"
        history_str += f"{speaker}: {msg.get('content')}\n"

    prompt = f"""
{persona}

Hedef İlan: {job_text[:500]}
CV Projeler: {cv_sections.get('projeler', '')[:600]}

ŞU ANA KADARKİ DİYALOG:
{history_str}
Adayın Son Cevabı:
\"{user_answer}\"

GÖREVİN VE ÇOK KESKİN PUANLAMA KURALLARI (Gerçekçi Mühendislik Mülakatı Standardı):
Gerçek mülakatlar çok zordur; adayların %85'i yüzeysel konuştukları için elenir. Puanı bol keseden dağıtmak KESİNLİKLE YASAKTIR!

ÇOK KATI 1-10 PUANLAMA SKALASI:
- 1 - 3 PUAN (Yetersiz / Kaçamak): Çok kısa (<15 kelime), konudan alakasız, ezber, pasif veya teknik içerikten yoksun yanıtlar.
- 4 - 5 PUAN (Zayıf / Yüzeysel): Genel geçer laflar eden ("Python kullandım", "ekipte çalıştım"), somut kütüphane/mimari/fonksiyon detayı ve problem çözme adımı anlatmayan yüzeysel yanıtlar.
- 6 PUAN (SINIR TAVAN - Tatmin Edici Olmayan Standart Yanıtlar): Ne yapıldığını özetleyen ANCAK derin mimari detay, karşılaşılan spesifik teknik zorluk veya sayısal sonuç (metrik) İÇERMEYEN tüm yanıtlar İÇİN TAVAN PUAN 6'DIR! Tatmin edici olmayan, genel yanıtlar ASLA 6'nın üstüne çıkamaz!
- 7 - 8 PUAN (İyi / Gerçekten Tatmin Edici): SADECE ve SADECE aday STAR metoduna tam uyup; hangi spesifik problemi nasıl çözdüğünü, hangi kütüphaneyi/fonksiyonu neden seçtiğini, ne tür bir teknik zorluk yaşadığını ve gerekçesini net anlattıysa verilebilir.
- 9 - 10 PUAN (Kusursuz / Üst Düzey): Hem derin mimari kıyaslama (örn. neden X yerine Y seçildi?), hem karşılaşılan spesifik hata/darboğazın çözümü, hem de ölçülebilir somut etki (performans, süre, latency, doğruluk oranı, kullanıcı hacmi) içeren olağanüstü cevaplar. (Çok nadir verilir!)

ÖNEMLİ KURAL: Cevap sadece teorik veya genel anlatımdan ibaretse, somut teknik bir derinlik veya sayısal bir etki yoksa KESİNLİKLE 6'NIN ÜSTÜNDE PUAN VERME!

Ayrıca:
1. STAR metoduna (Durum, Görev, Aksiyon, Sonuç) göre eksikleri açıkça listele.
2. Rolüne uygun kalarak adaya kısa ve net bir geri bildirim ver ve hemen ardından MÜLAKATI DEVAM ETTİRECEK ZORLAYICI BİR TAKİP (FOLLOW-UP) SORUSU sor.
3. Adaya "Bu soruya nasıl cevap verseydin daha etkili olurdu?" STAR tüyosu sun.

Yanıtını SADECE aşağıdaki JSON formatında ver:
{{
  "puan": 5,
  "guclu_yonler": ["Eylemi net anlatmış", "Kullandığı aracı belirtmiş"],
  "gelistirilmesi_gerekenler": ["Sayısal sonuç veya etki belirtilmemiş", "Mimari gerekçe eksik"],
  "kisa_geri_bildirim": "Mülakatçının adaya söyleyeceği 1-2 cümlelik gerçekçi ve keskin tepki",
  "sonraki_soru": "Mülakatı devam ettiren yeni veya takip sorusu",
  "ornek_ideal_yanit_tuyosu": "STAR adımıyla şöyle deseydin çok daha etkili olurdu..."
}}
"""
    try:
        raw_json = _call_gemini_with_retry(prompt)
        data = _clean_json_response(raw_json)
        raw_puan = int(data.get("puan", 5))

        # --- PROGRAMATİK KESKİNLİK KİLİDİ ---
        # Tatmin edici olmayan, yüzeysel veya kısa yanıtlar asla 6'nın üstüne çıkamaz!
        import re
        words = user_answer.strip().split()
        word_count = len(words)

        has_metric = bool(re.search(r"%\s*\d+|\d+\s*%|\b\d+\s*(?:k|x|kat|ms|sn|kullanıcı|user|satır|doğruluk|accuracy|fps|qps|mb|gb)\b", user_answer.lower()))
        has_deep_tech = any(w in user_answer.lower() for w in [
            "çünkü", "mimari", "optimiz", "algoritma", "darboğaz", "performans",
            "latency", "query", "pipeline", "docker", "test", "benchmark", "trade-off",
            "nedenle", "karşılaştığım", "hatayı", "çözdüm", "tasarladım", "refactor", "entegre"
        ])

        if word_count < 15:
            raw_puan = min(raw_puan, 3)
        elif word_count < 25:
            raw_puan = min(raw_puan, 5)
        elif raw_puan > 6:
            # 6'nın üstü için GERÇEK tatmin edicilik şartı:
            # Hem yeterli uzunluk (>= 30 kelime) hem de metrik veya derin teknik problem çözümü içermelidir!
            is_satisfying = (word_count >= 30) and (has_metric or has_deep_tech)
            if not is_satisfying:
                raw_puan = 6

        data["puan"] = max(1, min(10, raw_puan))
        return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "error": f"Cevap değerlendirme hatası: {str(e)}"}


# =====================================================================
# 3) MÜLAKAT SONU KARNESİ
# =====================================================================
def generate_interview_summary(
    conversation_history: list[dict],
    scores: list[int]
) -> dict:
    """
    Tüm mülakat oturumunu özetler; genel skor ve eylem planı çıkarır.
    Gerçek dünya seçici mühendislik mülakatı standartlarında değerlendirir.
    """
    transcript = ""
    for msg in conversation_history:
        speaker = "Mülakatçı" if msg.get("role") == "assistant" else "Aday"
        transcript += f"{speaker}: {msg.get('content')}\n"

    avg_score = round(sum(scores) / len(scores) * 10) if scores else 50

    prompt = f"""
Sen Türkiye'nin en seçici teknoloji şirketlerinden birinin Acımasız ama Adil Başmülakatçısısın.
Gerçek dünyada yüzlerce YTÜ ve ODTÜ/İTÜ mezunu arasından sadece en somut, STAR metodunu en iyi uygulayan adaylar staja kabul edilir.

Mülakat Transkripti:
{transcript}

Cevap Puanları Ortalaması: {avg_score}/100

GÖREVİN:
Aday için gerçekçi, asla şişirilmemiş, yapıcı ama dürüst bir MÜLAKAT PERFORMANS KARNESİ hazırla.
Gerçekçi değerlendirme baremi:
- 80-100: Mükemmel (Doğrudan Teklif / En üst %5)
- 65-79: İyi (İkinci tura kalabilir, eksikleri var)
- 50-64: Sınırda / Yetersiz (Gerçek mülakatta elenirdi)
- 0-49: Başarısız (Ciddi teknik ve iletişim hazırlığı gerekiyor)

Yanıtını SADECE aşağıdaki JSON formatında ver:
{{
  "genel_skor": {avg_score},
  "genel_degerlendirme": "2-3 cümlelik dürüst, gerçekçi ve yapıcı değerlendirme",
  "en_guclu_3_yon": ["...", "...", "..."],
  "gelistirilmesi_gereken_3_alan": ["...", "...", "..."],
  "staj_mulakati_icin_altin_ogut": "Gerçek mülakatta elenmemesi için vermen gereken en kritik tavsiye"
}}
"""
    try:
        raw_json = _call_gemini_with_retry(prompt)
        return {"success": True, "data": _clean_json_response(raw_json)}
    except Exception as e:
        return {"success": False, "error": f"Karne üretim hatası: {str(e)}"}


# =====================================================================
# TEST BLOĞU
# =====================================================================
if __name__ == "__main__":
    print("=" * 65)
    print("🎤 MÜLAKAT SİMÜLATÖRÜ (AŞAMA 8) TEST EDİLİYOR...")
    print("=" * 65)

    ornek_cv = {
        "egitim": "Yıldız Teknik Üniversitesi - Matematik Mühendisliği",
        "projeler": "Python ve Streamlit kullanarak staj CV analiz aracı geliştirdim. Pandas ile veri setlerini modelledim.",
        "yetenekler": "Python, SQL, Streamlit, Pandas, Git"
    }
    ornek_ilan = "ABC Teknoloji - Veri Bilimi Stajyeri. Python, Pandas, SQL bilen stajyer aranıyor."

    # 1. Mülakatı Başlat
    print("\n1️⃣ Mülakat Başlatılıyor (Rol: Teknik Lider)...")
    res_start = start_interview(ornek_cv, ornek_ilan, interviewer_role="Teknik Lider")

    if res_start["success"]:
        data = res_start["data"]
        print(f"   👋 {data['karsilama_mesaji']}")
        print(f"   ❓ Soru: {data['ilk_soru']}")
        print(f"   🎯 Amaç: {data['sorunun_amaci']}")

        # 2. Örnek bir aday yanıtı simüle et
        aday_cevabi = (
            "Projemde Python ve Streamlit tercih ettim çünkü hızlıca web arayüzü sunabiliyordum. "
            "Pandas kütüphanesini ise veri temizleme aşamasında kullandım, verilerdeki eksik satırları "
            "doldurup grafiklere hazırladım."
        )
        print(f"\n2️⃣ Aday Yanıtı Simüle Ediliyor:\n   \"{aday_cevabi}\"")

        history = [
            {"role": "assistant", "content": data["ilk_soru"]},
            {"role": "user", "content": aday_cevabi}
        ]

        res_eval = evaluate_and_respond(history, aday_cevabi, ornek_cv, ornek_ilan, interviewer_role="Teknik Lider")
        if res_eval["success"]:
            eval_data = res_eval["data"]
            print(f"\n   ⭐ Puan: {eval_data['puan']}/10")
            print(f"   💬 Geri Bildirim: {eval_data['kisa_geri_bildirim']}")
            print(f"   👉 Takip Sorusu: {eval_data['sonraki_soru']}")
            print(f"   💡 İdeal Yanıt Tüyosu: {eval_data['ornek_ideal_yanit_tuyosu']}")

        print("\n" + "=" * 65)
        print("🎉 AŞAMA 8 TESTLERİ TAMAMLANDI!")
    else:
        print("❌ HATA:", res_start["error"])
