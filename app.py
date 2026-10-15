"""
YTÜ Staj Asistanı — Streamlit Ana Web Uygulaması (app.py)

Özellikler:
    - Sekmeli modern ve profesyonel kontrol paneli
    - PDF / DOCX dosya yükleme veya tek tıkla örnek veriyle test etme
    - ATS 9 Kriterli Uyumluluk Raporu
    - İlan Eşleştirme, Yetenek Analizi ve Kategori Kırılımı
    - Gemini Destekli STAR Madde İyileştirici
    - İlana Özel Ön Yazı (Cover Letter) Oluşturucu
    - Mülakat Simülasyonu & STAR Yanıt Stratejileri
    - Fact Guard Uydurma Bilgi Denetimi
"""
import os
import sys
import tempfile
from datetime import datetime, date
import streamlit as st

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Modüllerimizi içe aktarıyoruz
from parser import extract_text_from_pdf, extract_text_from_docx, parse_cv_sections
from ats_checker import evaluate_cv, extract_bullets
from job_matcher import match_cv_to_job, SAMPLE_CV, SAMPLE_JOB
from ai_helper import improve_bullet_point, generate_cover_letter, generate_interview_prep, MODEL_NAME, API_KEY
from fact_guard import audit_text
from interview_bot import start_interview, evaluate_and_respond, generate_interview_summary
from correlation_engine import calculate_hire_probability, analyze_job_cv_correlation
from tracker import (
    add_application,
    get_all_applications,
    update_application_status,
    delete_application,
    get_application_statistics,
    STATUS_OPTIONS,
    STATUS_COLORS,
    infer_company_and_role
)
from strategy_engine import (
    YTU_INTERNSHIP_INFO,
    ANNUAL_TIMELINE_PHASES,
    CHECKLIST_ITEMS,
    generate_personalized_strategy
)
from docx_exporter import export_cv_to_bytes, build_resume_docx

# --- Sayfa Yapılandırması ---
st.set_page_config(
    page_title="YTÜ Staj Asistanı",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Özel CSS Stili ---
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
    }
    .badge-pass { background-color: #DEF7EC; color: #03543F; padding: 4px 10px; border-radius: 6px; font-weight: 600; }
    .badge-warn { background-color: #FEF08A; color: #713F12; padding: 4px 10px; border-radius: 6px; font-weight: 600; }
    .badge-fail { background-color: #FDE8E8; color: #9B1C1C; padding: 4px 10px; border-radius: 6px; font-weight: 600; }
    .report-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 14px;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)


# --- Yan Menü (Sidebar) ---
with st.sidebar:
    st.markdown("### 🏛️ YTÜ Staj Asistanı")
    st.caption("Yapay Zeka Destekli ATS ve İlan Eşleştirme Platformu")
    st.divider()

    # API Durum Rozeti
    if API_KEY:
        st.success(f"🟢 Gemini API Aktif (`{MODEL_NAME}`)")
    else:
        st.error("🔴 Gemini API Anahtarı Eksik (.env)")

    st.subheader("1. CV Yükleyin")
    uploaded_file = st.file_uploader(
        "PDF veya DOCX formatında CV seçin:",
        type=["pdf", "docx"],
        help="Metin seçilebilir standart PDF veya DOCX dosyası yükleyin."
    )

    use_sample_cv = st.checkbox("Veya Hazır Örnek CV'yi Kullan", value=(uploaded_file is None))

    st.subheader("2. Hedef Staj İlanı")
    job_text_input = st.text_area(
        "İlan metnini buraya yapıştırın:",
        value=SAMPLE_JOB if use_sample_cv else "",
        height=180,
        placeholder="Şirket adı, aranan nitelikler, iş tanımı..."
    )

    analyze_btn = st.button("🚀 CV ve İlanı Analiz Et", type="primary", use_container_width=True)

    st.divider()
    st.caption("Geliştirici: Murat Kerim Yılmaz | Yıldız Teknik Üniversitesi")


# --- Yardımcı: CV Metnini Getir ---
def get_cv_content():
    if uploaded_file is not None:
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name

        try:
            if file_ext == ".pdf":
                res = extract_text_from_pdf(tmp_path)
            else:
                res = extract_text_from_docx(tmp_path)
            return res
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    elif use_sample_cv:
        return {
            "success": True,
            "text": SAMPLE_CV,
            "page_count": 1,
            "has_images": False,
            "has_tables": False,
            "error": None
        }
    return None


# --- Ana Akış ---
st.markdown('<div class="main-header">🎓 YTÜ Staj ve Kariyer Asistanı</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">CV\'nizi ATS uyumluluğu için denetleyin, staj ilanlarıyla eşleştirin ve Gemini ile güçlendirin.</div>', unsafe_allow_html=True)

cv_data = get_cv_content()

if not cv_data:
    st.info("👈 Başlamak için sol menüden bir CV yükleyin veya 'Örnek CV'yi Kullan' seçeneğini işaretleyin.")
    st.stop()

if not cv_data.get("success"):
    st.error(f"❌ CV Okunamadı: {cv_data.get('error')}")
    st.stop()

cv_text = cv_data["text"]
parsed_cv = parse_cv_sections(cv_text)
job_text = job_text_input.strip() if job_text_input else SAMPLE_JOB

# Analizleri Çalıştır (Oturum durumunda önbelleğe al)
with st.spinner("🔍 ATS, Yetenek Eşleştirme ve Bağıntı Motorları Çalıştırılıyor..."):
    ats_rapor = evaluate_cv(
        parsed_cv=parsed_cv,
        full_text=cv_text,
        page_count=cv_data.get("page_count", 1),
        has_tables=cv_data.get("has_tables", False),
        has_images=cv_data.get("has_images", False)
    )
    match_rapor = match_cv_to_job(parsed_cv, job_text)
    hire_prob = calculate_hire_probability(ats_rapor, match_rapor)
    corr_analysis = analyze_job_cv_correlation(parsed_cv, job_text, match_rapor)

# --- 9 Sekmeli Kontrol Paneli ---
tab_dash, tab_match, tab_ats, tab_star, tab_cl, tab_interview, tab_tracker, tab_strategy, tab_raw = st.tabs([
    "📊 Genel Bakış & İşe Kabul",
    "🎯 İlan Eşleştirme & Bağıntı",
    "📋 ATS Uyumluluk Raporu",
    "✨ STAR Madde Güçlendirici",
    "✉️ Ön Yazı (Cover Letter)",
    "🎤 Mülakat Hazırlığı",
    "🗂️ Staj Başvuru Takipçisi",
    "📅 Staj Stratejisi & YTÜ Takvimi",
    "📄 Ayrıştırılan CV Metni"
])

# =====================================================================
# SEKME 1: GENEL BAKIŞ & İŞE KABUL İHTİMALİ
# =====================================================================
with tab_dash:
    # 🎯 Öne Çıkan Başarı / İşe Kabul Kartı
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%); color: white; padding: 22px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
            <div>
                <span style="background: rgba(255,255,255,0.2); padding: 4px 10px; border-radius: 20px; font-size: 0.85rem; font-weight: 600;">ÇOK BOYUTLU ANALİZ</span>
                <h2 style="margin: 8px 0 4px 0; color: white;">🎯 Tahmini İşe Kabul / Mülakat Çağrılma İhtimali</h2>
                <p style="margin: 0; opacity: 0.92; font-size: 1rem;">{hire_prob['aciklama']}</p>
            </div>
            <div style="text-align: right; padding-top: 8px;">
                <span style="font-size: 3.2rem; font-weight: 800; line-height: 1;">%{hire_prob['ihtimal_yuzdesi']}</span>
                <span style="display: block; font-size: 1.1rem; font-weight: 600; margin-top: 4px;">{hire_prob['rozet']} {hire_prob['seviye']}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 4 Temel Metrik
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        ats_puan = ats_rapor["toplam_puan"]
        st.metric("📋 ATS Filtre Skoru", f"{ats_puan} / 100")
        if ats_puan >= 80:
            st.success("ATS Geçiş: Yüksek")
        elif ats_puan >= 60:
            st.warning("ATS Geçiş: Orta")
        else:
            st.error("ATS Geçiş: Düşük")

    with col2:
        if match_rapor.get("success"):
            eslesme_puan = match_rapor["eslesme_puani"]
            st.metric("🤝 Yetenek Eşleşmesi", f"%{eslesme_puan}")
            st.caption(match_rapor["degerlendirme"])
        else:
            st.metric("🤝 Yetenek Eşleşmesi", "—")

    with col3:
        st.metric("🔗 CV-İlan Alan Bağıntısı", f"%{corr_analysis['baginti_skoru']}")
        st.caption(f"{corr_analysis['alan_uyumu']}")

    with col4:
        if match_rapor.get("success"):
            cov = match_rapor["zorunlu_kapsama"]
            st.metric("📌 Zorunlu Yetenekler", f"{cov['karsilanan']} / {cov['toplam']}")
            oran = round(100 * cov['karsilanan'] / cov['toplam']) if cov['toplam'] else 0
            st.progress(oran / 100)
        else:
            st.metric("📌 Zorunlu Yetenekler", "—")

    st.divider()

    b_col1, b_col2 = st.columns(2)

    with b_col1:
        st.subheader("📊 İşe Kabul Puanı Nasıl Oluştu?")
        st.caption("Farklı boyutların toplam başarı şansına katkısı ve rekabet kesintileri:")
        bilesen = hire_prob["bilesenler"]
        st.write(f"• **ATS Filtre Geçiş Gücü (Max 20):** `{bilesen['ats_etkisi']} puan`")
        st.write(f"• **Zorunlu Yetenek Kapsaması (Max 35):** `{bilesen['zorunlu_kapsama_etkisi']} puan`")
        st.write(f"• **Projelerde Somut Kanıt (Max 25):** `{bilesen['proje_kaniti_etkisi']} puan`")
        st.write(f"• **Tercih Sebebi / Artı Değerler (Max 10):** `{bilesen['arti_deger_etkisi']} puan`")
        st.write(f"• **Fact Guard Güvenilirlik (Max 10):** `{bilesen['guvenilirlik_etkisi']} puan`")
        if bilesen.get("rekabet_kesintisi", 0) > 0:
            st.caption(f"📉 **Piyasa Rekabet Katsayısı:** Başvuru havuzu yoğunluğu ve seçicilik sebebiyle `{bilesen['rekabet_kesintisi']} puan` dengelenmiştir.")

    with b_col2:
        st.subheader("🚀 Şansınızı Hızla Artıracak Aksiyonlar")
        for t in hire_prob["sans_artirici_taktikler"]:
            st.info(f"👉 {t}")

        st.caption(f"**Alan Değerlendirmesi:** {corr_analysis['alan_yorumu']}")

    # 📌 Bu İlanı Başvuru Takipçisine Kaydet
    st.divider()
    default_comp, default_role = infer_company_and_role(job_text)
    with st.expander("📌 Bu İlanı Staj Başvuru Takipçisine Kaydet", expanded=False):
        st.caption("Bu ilana başvurmayı düşünüyorsanız, hesaplanan analiz skorlarıyla birlikte yerel SQLite veritabanınıza kaydedin.")
        with st.form("quick_save_app_form"):
            qs_c1, qs_c2 = st.columns(2)
            with qs_c1:
                f_comp = st.text_input("Şirket Adı:", value=default_comp)
                f_pos = st.text_input("Pozisyon / Rol:", value=default_role)
                f_loc = st.text_input("Lokasyon:", value="İstanbul (Hibrit)")
            with qs_c2:
                f_status = st.selectbox("Başvuru Durumu:", STATUS_OPTIONS, index=0)
                f_date = st.date_input("Başvuru Tarihi:", value=date.today())
                f_notes = st.text_input("Kısa Not:", placeholder="Örn: Kariyer.net üzerinden başvuruldu, cover letter eklendi.")

            save_btn = st.form_submit_button("💾 Başvuruyu Takipçiye Ekle", type="primary")
            if save_btn:
                new_app_id = add_application(
                    company_name=f_comp,
                    position_title=f_pos,
                    location=f_loc,
                    application_date=str(f_date),
                    status=f_status,
                    match_score=match_rapor.get("eslesme_puani", 0) if match_rapor.get("success") else 0,
                    ats_score=ats_rapor.get("toplam_puan", 0),
                    hire_probability=hire_prob.get("ihtimal_yuzdesi", 0),
                    job_description=job_text[:2000],
                    notes=f_notes
                )
                st.success(f"🎉 '{f_comp} - {f_pos}' başvurusu başarıyla takipçiye eklendi! (Kayıt #{new_app_id}) ➔ 'Staj Başvuru Takipçisi' sekmesinden inceleyebilirsiniz.")

    # ATS Uyumlu CV İndirme Butonu
    docx_bytes_dash = export_cv_to_bytes(parsed_cv=parsed_cv, full_text=cv_text)
    st.download_button(
        label="📄 Jake's Resume Formatında ATS Uyumlu Word (.docx) CV İndir",
        data=docx_bytes_dash,
        file_name="ytu_staj_cv_ats_uyumlu.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=True,
        key="btn_download_docx_dash"
    )


# =====================================================================
# SEKME 2: İLAN EŞLEŞTİRME & YETENEK ANALİZİ
# =====================================================================
with tab_match:
    if not match_rapor.get("success"):
        st.warning(match_rapor.get("error", "İlan eşleştirmesi yapılamadı."))
    else:
        # Alan ve Profil Bağıntısı Kutusu
        st.markdown(f"""
        <div style="background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 10px; padding: 16px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                <div>
                    <span style="font-weight: 700; color: #166534; font-size: 1.1rem;">🔗 CV ve İlan Alan Bağıntısı: %{corr_analysis['baginti_skoru']} ({corr_analysis['alan_uyumu']})</span>
                    <p style="margin: 6px 0 0 0; color: #15803D; font-size: 0.95rem;">{corr_analysis['alan_yorumu']}</p>
                </div>
                <div style="text-align: right;">
                    <span style="font-size: 0.85rem; color: #166534;"><strong>CV:</strong> {corr_analysis['cv_baskin_alan']} ➔ <strong>İlan:</strong> {corr_analysis['ilan_hedef_alan']}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.subheader("📊 Kategori Bazında Uyum Oranı")
        for cat in match_rapor["kategori_kirilimi"]:
            c_col1, c_col2 = st.columns([3, 1])
            with c_col1:
                st.write(f"**{cat['kategori_adi']}** ({cat['karsilanan']} / {cat['toplam']} yetenek)")
                st.progress(cat["yuzde"] / 100)
            with c_col2:
                st.metric(label="Kategori Skoru", value=f"%{cat['yuzde']}")

        st.divider()
        st.subheader("📋 İlandaki Tüm Gereksinimler ve CV'deki Karşılıkları")

        filter_option = st.radio(
            "Filtrele:",
            ["Tümü", "Sadece Eksikler", "Kanıtlı Olanlar", "Zayıf Kanıt / Sadece Listelenmiş"],
            horizontal=True
        )

        durum_ikon = {"kanitli": "✅", "listelenmis": "🟡", "dolayli": "🔗", "eksik": "❌"}
        durum_yazi = {
            "kanitli": "Kanıtlı (Proje/Deneyim)",
            "listelenmis": "Sadece Listelenmiş (Yetenekler/Özet)",
            "dolayli": "Dolaylı Çıkarım",
            "eksik": "CV'de Bulunamadı"
        }

        for ev in match_rapor["gereksinimler"]:
            # Filtreleme
            if filter_option == "Sadece Eksikler" and ev["durum"] != "eksik":
                continue
            if filter_option == "Kanıtlı Olanlar" and ev["durum"] != "kanitli":
                continue
            if filter_option == "Zayıf Kanıt / Sadece Listelenmiş" and ev["durum"] not in ("listelenmis", "dolayli"):
                continue

            seviye_renk = "badge-fail" if ev["seviye"] == "zorunlu" else "badge-warn"
            ikon = durum_ikon.get(ev["durum"], "⚪")

            with st.container():
                st.markdown(f"""
                <div class="report-card">
                    <span style="font-size: 1.1rem; font-weight: 600;">{ikon} {ev['etiket']}</span>
                    <span class="{seviye_renk}" style="margin-left: 10px;">{ev['seviye'].upper()}</span>
                    <span style="float: right; color: #6B7280; font-size: 0.9rem;">{ev['kategori_adi']} | Puan: {ev['kazanilan_puan']}/{ev['olasi_puan']}</span>
                    <p style="margin: 8px 0 0 0; color: #374151;">
                        <strong>Durum:</strong> {durum_yazi.get(ev['durum'])} 
                        {('→ CV Bölümleri: ' + ', '.join(ev['cv_bolumleri'])) if ev['cv_bolumleri'] else ''}
                        {('← Kaynak Yetenek: ' + ev['dolayli_kaynak']) if ev['dolayli_kaynak'] else ''}
                    </p>
                </div>
                """, unsafe_allow_html=True)

        if match_rapor.get("ilgili_ekstra_yetenekler"):
            st.divider()
            st.subheader("➕ İlanda İstenmeyen Ama Sizin Sahip Olduğunuz Yetenekler")
            st.caption("Bu yetenekler ilanın alanıyla doğrudan ilgilidir; ön yazıda veya mülakatta artı değer olarak öne çıkarabilirsiniz.")
            ekstralar = [e["yetenek"] for e in match_rapor["ilgili_ekstra_yetenekler"]]
            st.write(", ".join(f"**{e}**" for e in ekstralar))


# =====================================================================
# SEKME 3: ATS UYUMLULUK RAPORU
# =====================================================================
with tab_ats:
    st.subheader(f"🎯 Kural Tabanlı 9 Kriterli ATS Denetimi ({ats_rapor['toplam_puan']} / 100)")
    st.caption("Canva gibi şablonların aksine, gerçek şirket ATS yazılımlarının okuma kuralları test edilir.")

    for c in ats_rapor["detayli_kontroller"]:
        durum = c["durum"]
        if durum == "GEÇTİ":
            badge_class = "badge-pass"
            icon = "✅"
        elif durum == "UYARI":
            badge_class = "badge-warn"
            icon = "⚠️"
        else:
            badge_class = "badge-fail"
            icon = "❌"

        with st.container():
            st.markdown(f"""
            <div class="report-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 700; font-size: 1.05rem;">{icon} {c['kriter']}</span>
                    <div>
                        <span class="{badge_class}">{durum}</span>
                        <span style="font-weight: 600; margin-left: 8px;">{c['puan']}</span>
                    </div>
                </div>
                <p style="margin: 8px 0 4px 0; color: #374151;"><strong>🔎 Tespit:</strong> {c['aciklama']}</p>
                {f'<p style="margin: 0; color: #1E40AF;"><strong>💡 Çözüm Önerisi:</strong> {c["cozum"]}</p>' if durum != "GEÇTİ" else ''}
            </div>
            """, unsafe_allow_html=True)

    st.divider()
    st.subheader("📥 ATS Uyumlu Jake's Resume Şablonunu İndir")
    st.caption("ATS sistemlerinin tablosuz ve tek sütunlu okuma kurallarına tam uyumlu, düzenlenebilir Word belgesi.")
    docx_bytes_ats = export_cv_to_bytes(parsed_cv=parsed_cv, full_text=cv_text)
    st.download_button(
        label="📄 ATS Uyumlu Word (.docx) CV İndir",
        data=docx_bytes_ats,
        file_name="ytu_staj_cv_ats_uyumlu.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        type="primary",
        key="btn_download_docx_ats"
    )


# =====================================================================
# SEKME 4: STAR MADDE GÜÇLENDİRİCİ (AI + FACT GUARD)
# =====================================================================
with tab_star:
    st.subheader("✨ STAR Metoduyla CV Maddesi Güçlendirme")
    st.caption("Pasif ifadeleri eylem odaklı, ölçülebilir ve ATS dostu maddelere dönüştürün. (Uydurma bilgi korumalı)")

    # CV'deki mevcut maddeleri ayıkla
    exp_and_proj = parsed_cv.get("deneyim", "") + "\n" + parsed_cv.get("projeler", "")
    existing_bullets = extract_bullets(exp_and_proj)

    bullet_to_improve = ""
    if existing_bullets:
        selected_bullet = st.selectbox(
            "CV'nizden geliştirmek istediğiniz bir madde seçin:",
            existing_bullets
        )
        bullet_to_improve = selected_bullet

    custom_bullet = st.text_input(
        "Veya kendi zayıf cümlenizi yazın:",
        value=bullet_to_improve,
        placeholder="Örn: Kulüp etkinliğinde sponsorluk işleriyle ilgilendim..."
    )

    if st.button("🪄 Yapay Zeka ile Güçlendir ve Denetle", type="primary"):
        if not custom_bullet.strip():
            st.warning("Lütfen geliştirmek için bir madde yazın veya seçin.")
        else:
            with st.spinner("Gemini ile alternatifler hazırlanıyor ve Fact Guard denetimi yapılıyor..."):
                res_improve = improve_bullet_point(
                    bullet=custom_bullet,
                    target_skills=[g["eslesen_yetenek"] for g in match_rapor.get("gereksinimler", []) if g.get("eslesen_yetenek")][:5],
                    job_context=job_text[:300]
                )

                if not res_improve["success"]:
                    st.error(res_improve["error"])
                else:
                    data = res_improve["data"]
                    st.success("✅ Maddeler başarıyla üretildi!")

                    if data.get("tespit_edilen_eksikler"):
                        st.write("**Orijinal Maddedeki Eksikler:**", ", ".join(data["tespit_edilen_eksikler"]))

                    for idx, alt in enumerate(data.get("alternatifler", []), 1):
                        st.markdown(f"#### Alternatif {idx}: {alt['odak']}")
                        st.info(alt["metin"])
                        st.caption(f"💡 **İpucu:** {alt.get('ipucu', '')}")

                        # Fact Guard ile anında güvenlik denetimi
                        audit = audit_text(alt["metin"], parsed_cv, original_bullet=custom_bullet)
                        g_col1, g_col2 = st.columns([1, 4])
                        with g_col1:
                            if audit["durum"] == "GÜVENLİ":
                                st.success(f"🛡️ {audit['durum']} ({audit['guvenlik_skoru']}/100)")
                            else:
                                st.warning(f"🛡️ {audit['durum']} ({audit['guvenlik_skoru']}/100)")
                        with g_col2:
                            if audit["doldurulmamis_yer_tutucular"]:
                                st.write(f"📝 **Doldurulacak Alanlar:** {', '.join(audit['doldurulmamis_yer_tutucular'])}")
                            if audit["yetkisiz_yetenekler"]:
                                st.error(f"🚨 **CV Dışı Teknoloji Uyarısı:** {', '.join(u['yetenek'] for u in audit['yetkisiz_yetenekler'])}")
                        st.divider()

    st.subheader("📥 Güçlendirilmiş CV'yi Word (.docx) Olarak İndir")
    st.caption("Jake's Resume / Harvard formatında tek sütunlu, 0.5 inç kenar boşluklu, tüm ATS botlarının %100 okuyacağı profesyonel Word belgesi.")
    docx_bytes_star = export_cv_to_bytes(parsed_cv=parsed_cv, full_text=cv_text)
    st.download_button(
        label="📄 Güçlendirilmiş Word (.docx) CV'yi İndir",
        data=docx_bytes_star,
        file_name="ytu_staj_cv_ats_uyumlu.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        type="primary",
        key="btn_download_docx_star"
    )


# =====================================================================
# SEKME 5: İLANA ÖZEL ÖN YAZI (COVER LETTER)
# =====================================================================
with tab_cl:
    st.subheader("✉️ İlana ve CV'nize Özel Ön Yazı (Cover Letter)")
    st.caption("Şablonik olmayan, YTÜ öğrencisi kimliğinizi ve somut projelerinizi ön plana çıkaran profesyonel mektup.")

    if st.button("📝 Ön Yazı Oluştur", type="primary"):
        with st.spinner("Gemini ilana özel ön yazıyı kaleme alıyor..."):
            cl_res = generate_cover_letter(parsed_cv, job_text, match_rapor)

            if not cl_res["success"]:
                st.error(cl_res["error"])
            else:
                cl_data = cl_res["data"]
                st.session_state["cover_letter"] = cl_data

    if "cover_letter" in st.session_state:
        cl_data = st.session_state["cover_letter"]
        st.markdown(f"### {cl_data.get('baslik', 'Ön Yazı')}")
        st.write(cl_data.get("paragraf_giris", ""))
        st.write(cl_data.get("paragraf_teknik_kanit", ""))
        st.write(cl_data.get("paragraf_katki_vizyon", ""))
        st.write(cl_data.get("kapanis_ve_imza", ""))

        full_letter = cl_data.get("tam_metin", "")

        # Fact Guard Denetimi
        audit_cl = audit_text(full_letter, parsed_cv)
        st.divider()
        st.markdown("#### 🛡️ Fact Guard Doğruluk Karnesi")
        if audit_cl["durum"] == "GÜVENLİ":
            st.success(f"Güvenlik Skoru: {audit_cl['guvenlik_skoru']}/100 — Bu ön yazı tamamen gerçek projelerinize dayanıyor.")
        else:
            st.warning(f"Güvenlik Skoru: {audit_cl['guvenlik_skoru']}/100 — {audit_cl['durum']}")
            for oneri in audit_cl["oneriler"]:
                st.write("👉", oneri)

        st.download_button(
            label="📥 Ön Yazıyı İndir (.txt)",
            data=full_letter,
            file_name="on_yazi_ytu_staj.txt",
            mime="text/plain"
        )


# =====================================================================
# SEKME 6: MÜLAKAT HAZIRLIĞI & İNTERAKTİF SİMÜLATÖR
# =====================================================================
with tab_interview:
    st.subheader("🎤 Mülakat Hazırlığı & Canlı Simülatör")
    st.caption("Hem ilana özel soru listesini inceleyin hem de seçtiğiniz mülakatçıyla gerçek zamanlı pratik yapın.")

    sub_sim, sub_list = st.tabs(["🤖 Canlı Mülakat Simülatörü", "📋 Hazır Soru Bankası & Rehber"])

    with sub_sim:
        sim_col1, sim_col2 = st.columns([3, 1])
        with sim_col1:
            selected_role = st.selectbox(
                "Mülakatçı Profilini Seçin:",
                ["Teknik Lider", "İK / İşe Alım Uzmanı", "YTÜ Staj Mentoru"],
                help="Her rol farklı bir bakış açısıyla sorular sorar ve sizi değerlendirir."
            )
        with sim_col2:
            start_sim_btn = st.button("🚀 Yeni Mülakat Başlat", type="primary", use_container_width=True)

        if start_sim_btn:
            with st.spinner(f"{selected_role} hazırlanıyor..."):
                init_res = start_interview(parsed_cv, job_text, interviewer_role=selected_role)
                if init_res["success"]:
                    st.session_state["sim_history"] = [
                        {"role": "assistant", "content": f"{init_res['data']['karsilama_mesaji']}\n\n**Soru:** {init_res['data']['ilk_soru']}", "eval": None}
                    ]
                    st.session_state["sim_scores"] = []
                    st.session_state["sim_role"] = selected_role
                    st.session_state["sim_finished"] = False
                    st.rerun()
                else:
                    st.error(init_res["error"])

        # Sohbet geçmişini göster
        if "sim_history" in st.session_state and st.session_state["sim_history"]:
            for msg in st.session_state["sim_history"]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    if msg.get("eval"):
                        ev = msg["eval"]
                        puan_renk = "badge-pass" if ev["puan"] >= 7 else ("badge-warn" if ev["puan"] >= 5 else "badge-fail")
                        st.markdown(f"""
                        <div style="background: #F9FAFB; border-left: 4px solid #3B82F6; padding: 10px; margin-top: 8px; border-radius: 4px;">
                            <span class="{puan_renk}">Puan: {ev['puan']} / 10</span>
                            <p style="margin: 6px 0 2px 0;"><strong>💬 Değerlendirme:</strong> {ev['kisa_geri_bildirim']}</p>
                            <p style="margin: 0; color: #1E40AF;"><strong>💡 İdeal Yanıt Tüyosu:</strong> {ev['ornek_ideal_yanit_tuyosu']}</p>
                        </div>
                        """, unsafe_allow_html=True)

            # Kullanıcı yanıt girişi
            if not st.session_state.get("sim_finished", False):
                user_input = st.chat_input("Cevabınızı buraya yazın ve Enter'a basın...")
                if user_input:
                    # Kullanıcı mesajını ekle
                    st.session_state["sim_history"].append({"role": "user", "content": user_input, "eval": None})

                    with st.spinner("Mülakatçı cevabınızı analiz ediyor..."):
                        eval_res = evaluate_and_respond(
                            conversation_history=st.session_state["sim_history"],
                            user_answer=user_input,
                            cv_sections=parsed_cv,
                            job_text=job_text,
                            interviewer_role=st.session_state.get("sim_role", "Teknik Lider")
                        )

                        if eval_res["success"]:
                            edata = eval_res["data"]
                            st.session_state["sim_scores"].append(edata["puan"])
                            # Mülakatçının cevabı ve değerlendirmesini ekle
                            next_msg = f"{edata['kisa_geri_bildirim']}\n\n**Takip Sorusu:** {edata['sonraki_soru']}"
                            st.session_state["sim_history"].append({
                                "role": "assistant",
                                "content": next_msg,
                                "eval": edata
                            })
                            st.rerun()
                        else:
                            st.error(eval_res["error"])

                # Mülakatı Bitir Butonu
                st.divider()
                if st.button("🏁 Mülakatı Bitir ve Performans Karnesi Al", type="secondary"):
                    with st.spinner("Genel değerlendirme karnesi çıkarılıyor..."):
                        sum_res = generate_interview_summary(
                            st.session_state["sim_history"],
                            st.session_state["sim_scores"]
                        )
                        if sum_res["success"]:
                            st.session_state["sim_summary"] = sum_res["data"]
                            st.session_state["sim_finished"] = True
                            st.rerun()

            if st.session_state.get("sim_finished", False) and "sim_summary" in st.session_state:
                sdata = st.session_state["sim_summary"]
                st.success("🎉 Mülakat Tamamlandı!")
                st.markdown(f"### 🏆 Genel Mülakat Skoru: {sdata.get('genel_skor', 75)} / 100")
                st.write(sdata.get("genel_degerlendirme", ""))

                k_col1, k_col2 = st.columns(2)
                with k_col1:
                    st.markdown("#### 💪 En Güçlü Yönleriniz")
                    for g in sdata.get("en_guclu_3_yon", []):
                        st.write("✅", g)
                with k_col2:
                    st.markdown("#### 🎯 Geliştirilmesi Gerekenler")
                    for a in sdata.get("gelistirilmesi_gereken_3_alan", []):
                        st.write("⚠️", a)

                st.info(f"💎 **Altın Öğüt:** {sdata.get('staj_mulakati_icin_altin_ogut', '')}")
        else:
            st.info("👆 Başlamak için mülakatçı profilinizi seçin ve **'Yeni Mülakat Başlat'** butonuna tıklayın.")

    with sub_list:
        if st.button("🎯 Tüm Olası Soruları Listele", type="primary"):
            with st.spinner("Mülakat senaryoları hazırlanıyor..."):
                q_res = generate_interview_prep(parsed_cv, job_text, match_rapor)
                if not q_res["success"]:
                    st.error(q_res["error"])
                else:
                    st.session_state["interview_questions"] = q_res["data"]

        if "interview_questions" in st.session_state:
            q_data = st.session_state["interview_questions"]
            for idx, item in enumerate(q_data.get("sorular", []), 1):
                with st.expander(f"Soru {idx} [{item.get('soru_turu', 'Teknik')}]: {item.get('soru')}", expanded=True):
                    st.markdown(f"**🎯 Mülakatçının Amacı:** {item.get('mulakatcinin_amaci')}")
                    st.markdown(f"**💡 STAR Yanıt Stratejisi:**\n{item.get('strateji_ve_ornek_yanit')}")


# =====================================================================
# SEKME 7: STAJ BAŞVURU TAKİPÇİSİ (SQLITE DATABASE)
# =====================================================================
with tab_tracker:
    st.subheader("🗂️ Staj Başvuru ve Mülakat Süreci Takipçisi")
    st.caption("Başvurduğunuz şirketleri, mülakat aşamalarını, notlarınızı ve analiz skorlarınızı yerel SQLite veritabanında güvenle yönetin.")

    stats = get_application_statistics()

    # İstatistik Kartları
    st_col1, st_col2, st_col3, st_col4, st_col5 = st.columns(5)
    with st_col1:
        st.metric("📋 Toplam Başvuru", stats["toplam"])
    with st_col2:
        st.metric("⚡ Aktif Süreç", stats["aktif"])
    with st_col3:
        st.metric("🎤 Mülakat Aşaması", stats["mulakat"])
    with st_col4:
        st.metric("🎉 Teklif Alınan", stats["teklif"])
    with st_col5:
        st.metric("📈 Dönüş Oranı", f"%{stats['donus_orani']}")

    st.divider()

    # İki Sütunlu Kontrol: Arama ve Durum Filtreleme
    t_ctrl1, t_ctrl2 = st.columns([2, 1])
    with t_ctrl1:
        search_kw = st.text_input("🔍 Şirket, pozisyon veya notlarda ara:", placeholder="Örn: Aselsan, Veri, HackerRank...")
    with t_ctrl2:
        status_filter = st.selectbox("Durum Filtresi:", ["Tümü"] + STATUS_OPTIONS, index=0)

    # Yeni Başvuru Ekleme Genişleticisi
    with st.expander("➕ Yeni Başvuru Kaydı Ekle", expanded=False):
        with st.form("manual_add_application_form"):
            m_col1, m_col2 = st.columns(2)
            with m_col1:
                m_comp = st.text_input("Şirket Adı *:", placeholder="Örn: Trendyol")
                m_pos = st.text_input("Pozisyon / Rol *:", placeholder="Örn: Backend Developer Stajyeri")
                m_loc = st.text_input("Lokasyon:", value="İstanbul / Hibrit")
            with m_col2:
                m_status = st.selectbox("Başlangıç Durumu:", STATUS_OPTIONS, index=0)
                m_date = st.date_input("Başvuru Tarihi:", value=date.today())
                m_deadline = st.text_input("Son Tarih / Randevu:", placeholder="Örn: 25 Ekim 2026")

            m_notes = st.text_area("Mülakat Notları / Başvuru Detayları:", placeholder="Örn: LinkedIn üzerinden ilana başvuruldu. İK'dan 1. tur görüşme daveti bekleniyor.")
            m_submit = st.form_submit_button("💾 Başvuruyu Kaydet", type="primary")

            if m_submit:
                if not m_comp or not m_pos:
                    st.error("Lütfen en az Şirket Adı ve Pozisyon alanlarını doldurun.")
                else:
                    new_id = add_application(
                        company_name=m_comp,
                        position_title=m_pos,
                        location=m_loc,
                        application_date=str(m_date),
                        deadline=m_deadline,
                        status=m_status,
                        notes=m_notes
                    )
                    st.success(f"✅ '{m_comp} - {m_pos}' başvurusu başarıyla eklendi! (Kayıt #{new_id})")
                    st.rerun()

    # Başvuruları Getir
    apps = get_all_applications(status_filter=status_filter, search_query=search_kw)

    if not apps:
        st.info("Henüz kayıtlı başvuru bulunmuyor veya seçilen filtreye uygun kayıt yok. Yukarıdaki formdan ilk başvurunuzu ekleyin!")
    else:
        st.write(f"**Toplam {len(apps)} başvuru listeleniyor:**")
        for app_item in apps:
            app_id = app_item["id"]
            app_status = app_item["status"]
            status_color = STATUS_COLORS.get(app_status, "#2563EB")

            with st.container():
                st.markdown(f"""
                <div style="background: #ffffff; border: 1px solid #E5E7EB; border-left: 6px solid {status_color}; border-radius: 10px; padding: 16px; margin-bottom: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                        <div>
                            <span style="font-size: 1.2rem; font-weight: 700; color: #111827;">{app_item['company_name']}</span>
                            <span style="color: #6B7280; font-size: 1.05rem; margin-left: 8px;">— {app_item['position_title']}</span>
                            <div style="margin-top: 4px; font-size: 0.88rem; color: #4B5563;">
                                📍 {app_item['location'] or 'Lokasyon belirtilmedi'} | 📅 Başvuru: {app_item['application_date']} {f'| ⏳ Randevu/Son: {app_item["deadline"]}' if app_item.get('deadline') else ''}
                            </div>
                        </div>
                        <div style="text-align: right; padding-top: 6px;">
                            <span style="background: {status_color}; color: white; padding: 5px 12px; border-radius: 20px; font-weight: 600; font-size: 0.9rem;">
                                {app_status}
                            </span>
                            <div style="margin-top: 6px; font-size: 0.85rem; color: #374151;">
                                {f'🎯 Uyum: <strong>%{app_item["match_score"]}</strong> | ' if app_item.get('match_score') else ''}
                                {f'📋 ATS: <strong>{app_item["ats_score"]}/100</strong> | ' if app_item.get('ats_score') else ''}
                                {f'🔮 Şans: <strong>%{app_item["hire_probability"]}</strong>' if app_item.get('hire_probability') else ''}
                            </div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Detaylar ve Süreç Güncelleme Genişleticisi
                with st.expander(f"⚙️ Başvuru Detaylarını ve Notlarını Yönet (#{app_id} - {app_item['company_name']})"):
                    u_col1, u_col2 = st.columns([3, 2])

                    with u_col1:
                        st.markdown("**📝 Mülakat Notları & Süreç Günlüğü:**")
                        current_notes = app_item.get("notes", "") or ""
                        if current_notes:
                            st.code(current_notes, language="text")
                        else:
                            st.caption("Henüz not eklenmemiş.")

                        if app_item.get("job_description"):
                            with st.expander("📄 Kayıtlı İlan Metnini Görüntüle"):
                                st.text(app_item["job_description"])

                    with u_col2:
                        st.markdown("**🔄 Durum Güncelle:**")
                        current_idx = STATUS_OPTIONS.index(app_status) if app_status in STATUS_OPTIONS else 0
                        new_stat = st.selectbox(
                            "Yeni Durum:",
                            STATUS_OPTIONS,
                            index=current_idx,
                            key=f"status_select_{app_id}"
                        )
                        new_note = st.text_input(
                            "Eklemek İstediğiniz Not:",
                            placeholder="Örn: 2. tur teknik mülakat daveti geldi",
                            key=f"note_input_{app_id}"
                        )

                        btn_col_up, btn_col_del = st.columns([2, 1])
                        with btn_col_up:
                            if st.button("💾 Güncelle", key=f"btn_update_{app_id}", type="primary", use_container_width=True):
                                update_application_status(app_id, new_stat, note_to_append=new_note)
                                st.success("Durum güncellendi!")
                                st.rerun()

                        with btn_col_del:
                            if st.button("🗑️ Sil", key=f"btn_delete_{app_id}", use_container_width=True):
                                delete_application(app_id)
                                st.warning(f"Kayıt #{app_id} silindi.")
                                st.rerun()


# =====================================================================
# SEKME 8: STAJ STRATEJİSİ VE YTÜ TAKVİMİ
# =====================================================================
with tab_strategy:
    st.subheader("📅 Staj Başvuru Stratejisi ve YTÜ Resmi Zaman Çizelgesi")
    st.caption("YTÜ staj yönergesine uygun resmi evrak adımları, akademik yıl takvimi ve kişiselleştirilmiş başvuru taktikleri.")

    # 1. Kişiselleştirme Seçimleri
    strat_col1, strat_col2 = st.columns(2)
    with strat_col1:
        selected_grade = st.selectbox(
            "🎓 Akademik Sınıfınız:",
            ["1. Sınıf", "2. Sınıf", "3. Sınıf", "4. Sınıf / Yeni Mezun"],
            index=2  # default: 3. Sınıf
        )
    with strat_col2:
        selected_type = st.selectbox(
            "📌 Hedeflediğiniz Staj Türü:",
            [
                "Staj II (Mesleki / Yazılım / Ar-Ge Stajı)",
                "Staj I (Temel / Laboratuvar Stajı)",
                "Uzun Dönem / Aday Mühendislik (Part-Time)",
                "Gönüllü Staj / Proje Stajı"
            ],
            index=0
        )

    # Strateji Üretimi
    custom_strategy = generate_personalized_strategy(
        grade_level=selected_grade,
        internship_type=selected_type,
        ats_score=ats_rapor.get("toplam_puan", 80),
        match_score=match_rapor.get("eslesme_puani", 75) if match_rapor.get("success") else 75,
        hire_probability=hire_prob.get("ihtimal_yuzdesi", 70)
    )

    # Kişiselleştirilmiş Değerlendirme Kartı
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%); color: white; padding: 20px; border-radius: 12px; margin-top: 10px; margin-bottom: 24px;">
        <span style="background: rgba(255,255,255,0.2); padding: 3px 10px; border-radius: 20px; font-size: 0.82rem; font-weight: 600;">SİZE ÖZEL STRATEJİ ANALİZİ</span>
        <h3 style="margin: 8px 0 6px 0; color: white;">🎯 {selected_grade} İçin Stratejik Değerlendirme</h3>
        <p style="margin: 0; font-size: 1rem; opacity: 0.95;">{custom_strategy['sinif_yorumu']}</p>
    </div>
    """, unsafe_allow_html=True)

    # Odak Noktaları ve Skor Bazlı Taktikler
    s_col1, s_col2 = st.columns(2)
    with s_col1:
        st.markdown("#### 🎯 Bu Dönemki Öncelikli Odak Noktalarınız")
        for o in custom_strategy["odak_noktalari"]:
            st.info(f"👉 {o}")

    with s_col2:
        st.markdown("#### 💡 Analiz Skorlarınıza Göre Aksiyonlar")
        for w in custom_strategy["uyarilar"]:
            st.warning(w)
        for t in custom_strategy["taktikler"]:
            st.success(t)

    st.divider()

    # 2. Yıllık Başvuru Takvimi (5 Faz)
    st.subheader("🗓️ Akademik Yıl Boyunca 5 Fazlı Başvuru Yol Haritası")
    st.caption("Başvuruların açılış dönemleri, mülakat takvimi ve resmi staj tarihlerinin yıllık dökümü:")

    for phase in ANNUAL_TIMELINE_PHASES:
        with st.container():
            st.markdown(f"""
            <div style="background: #ffffff; border: 1px solid #E5E7EB; border-left: 6px solid {phase['renk']}; border-radius: 10px; padding: 16px; margin-bottom: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                    <div>
                        <span style="font-size: 1.15rem; font-weight: 700; color: #111827;">{phase['rozet']} {phase['faz']}</span>
                        <p style="margin: 4px 0 0 0; color: #4B5563; font-size: 0.95rem;">🎯 <strong>Hedef:</strong> {phase['hedef']}</p>
                    </div>
                    <div>
                        <span style="background: #EFF6FF; color: {phase['renk']}; border: 1px solid {phase['renk']}40; padding: 4px 12px; border-radius: 20px; font-weight: 700; font-size: 0.9rem;">
                            📅 {phase['aylar']}
                        </span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            with st.expander(f"📋 {phase['faz']} Kapsamında Yapılacak Görevler"):
                for task in phase["gorevler"]:
                    st.write(f"• {task}")

    st.divider()

    # 3. İnteraktif YTÜ Resmi Evrak & SGK Kontrol Listesi
    st.subheader("📑 YTÜ Resmi Evrak ve SGK Süreç Kontrol Listesi")
    st.caption("Stajınızın üniversite tarafından onaylanması ve SGK girişinizin yapılması için takip etmeniz gereken yasal kontrol adımları:")

    if "ytu_checklist" not in st.session_state:
        st.session_state["ytu_checklist"] = {item["id"]: False for item in CHECKLIST_ITEMS}

    # İlerleme Çubuğu Hesapla
    completed_count = sum(1 for v in st.session_state["ytu_checklist"].values() if v)
    total_chk = len(CHECKLIST_ITEMS)
    progress_pct = int((completed_count / total_chk) * 100)

    p_col1, p_col2 = st.columns([3, 1])
    with p_col1:
        st.progress(progress_pct / 100)
    with p_col2:
        st.write(f"**%{progress_pct} Tamamlandı** ({completed_count}/{total_chk})")

    for chk in CHECKLIST_ITEMS:
        is_checked = st.session_state["ytu_checklist"].get(chk["id"], False)
        new_val = st.checkbox(
            f"**{chk['baslik']}** — *[{chk['kategori']}]*",
            value=is_checked,
            key=f"chk_input_{chk['id']}",
            help=chk["aciklama"]
        )
        if new_val != is_checked:
            st.session_state["ytu_checklist"][chk["id"]] = new_val
            st.rerun()

        st.caption(f"ℹ️ {chk['aciklama']}")

    st.divider()

    # 4. Şirket Türü Başvuru Matrisi
    st.subheader("🏢 Şirket Türüne Göre Başvuru Stratejisi")
    st.caption("Farklı şirket ekosistemlerinin stajyer seçim kriterleri ve başvuru zamanlamaları:")

    m_col1, m_col2 = st.columns(2)
    s_matrix = custom_strategy["sirket_matrisi"]

    with m_col1:
        for sm in s_matrix[:2]:
            st.markdown(f"""
            <div style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px; padding: 14px; margin-bottom: 12px;">
                <h4 style="margin: 0 0 6px 0; color: #1E3A8A;">🏢 {sm['tur']}</h4>
                <p style="margin: 0 0 4px 0; font-size: 0.88rem; color: #374151;"><strong>Öncelik:</strong> {sm['oncelik']}</p>
                <p style="margin: 0 0 4px 0; font-size: 0.88rem; color: #4B5563;"><strong>Kriter:</strong> {sm['ortalama_kriter']}</p>
                <p style="margin: 0; font-size: 0.88rem; color: #15803D;"><strong>💡 Taktik:</strong> {sm['tavsiye']}</p>
            </div>
            """, unsafe_allow_html=True)

    with m_col2:
        for sm in s_matrix[2:]:
            st.markdown(f"""
            <div style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px; padding: 14px; margin-bottom: 12px;">
                <h4 style="margin: 0 0 6px 0; color: #1E3A8A;">🏢 {sm['tur']}</h4>
                <p style="margin: 0 0 4px 0; font-size: 0.88rem; color: #374151;"><strong>Öncelik:</strong> {sm['oncelik']}</p>
                <p style="margin: 0 0 4px 0; font-size: 0.88rem; color: #4B5563;"><strong>Kriter:</strong> {sm['ortalama_kriter']}</p>
                <p style="margin: 0; font-size: 0.88rem; color: #15803D;"><strong>💡 Taktik:</strong> {sm['tavsiye']}</p>
            </div>
            """, unsafe_allow_html=True)

    # 5. YTÜ Resmi Staj Kuralları Uyarısı
    st.divider()
    st.subheader("⚠️ YTÜ Staj Yönergesinden Kritik Hatırlatmalar")
    for rule in YTU_INTERNSHIP_INFO["onemli_kurallar"]:
        st.markdown(f"- {rule}")


# =====================================================================
# SEKME 9: AYRIŞTIRILAN HAM CV METNİ
# =====================================================================
with tab_raw:
    st.subheader("📄 Parser Tarafından Tanınan CV Bölümleri")
    st.caption("Parser modülünün CV'nizi nasıl okuduğunu ve hangi bölümlere ayırdığını şeffafça inceleyebilirsiniz.")

    for sec_name, sec_content in parsed_cv.items():
        if sec_content.strip():
            with st.expander(f"📌 {sec_name.upper()}", expanded=(sec_name in ["projeler", "deneyim"])):
                st.text(sec_content)
