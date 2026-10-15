"""
DOCX Dışa Aktarma Modülü (docx_exporter.py) - YTÜ Staj Asistanı

Özellikler:
    - Öğrencinin CV'sini Jake's Resume / Harvard standartlarında tek sütunlu,
      ATS dostu ve profesyonel Microsoft Word (.docx) belgesine dönüştürür.
    - Tablosuz, görselsiz, ATS botlarının %100 kusursuz okuyacağı temiz lineer hiyerarşi.
    - Özel başlık alt çizgileri (XML pBdr), 0.5 inç ideal kenar boşlukları ve kompakt satır aralıkları.
    - İster dosyaya kaydetme (.docx), ister Streamlit için bellek içi (io.BytesIO) dışa aktarma.
    - STAR Madde Güçlendirici'den gelen iyileştirilmiş maddeleri entegre edebilme.
"""
import io
import os
import re
import sys
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Renk Paleti (ATS Dostu Klasik Kurumsal)
COLOR_PRIMARY = RGBColor(0x1E, 0x3A, 0x8A)    # Koyu Lacivert (#1E3A8A)
COLOR_TEXT = RGBColor(0x1F, 0x29, 0x37)       # Koyu Gri/Siyah (#1F2937)
COLOR_MUTED = RGBColor(0x4B, 0x55, 0x63)      # İkincil Gri (#4B5563)


def add_bottom_border(paragraph, hex_color="1E3A8A", size="6"):
    """Bölüm başlıklarının altına ince, zarif bir çizgi ekler (Jake's Resume stili)."""
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), size)       # 6 = ~0.75 pt
    bottom.set(qn('w:space'), '2')
    bottom.set(qn('w:color'), hex_color)
    pBdr.append(bottom)
    pPr.append(pBdr)


def parse_header_contact(header_text: str, full_text: str = "") -> dict:
    """Başlık metninden aday adı ve iletişim kanallarını ayıklar."""
    combined = header_text + "\n" + full_text
    lines = [l.strip() for l in header_text.splitlines() if l.strip()]

    # Aday adı genelde ilk satırdır
    name = "ÖĞRENCİ ADI SOYADI"
    if lines:
        first_clean = re.sub(r"[\|\•\-\–\—].*$", "", lines[0]).strip()
        if len(first_clean.split()) in [2, 3, 4] and not "@" in first_clean:
            name = first_clean

    # E-posta
    email_m = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", combined)
    email = email_m.group(0) if email_m else ""

    # Telefon
    phone_m = re.search(r"(?:\+90|0)?\s*\(?5\d{2}\)?[\s\.\-]?\d{3}[\s\.\-]?\d{2}[\s\.\-]?\d{2}", combined)
    phone = phone_m.group(0) if phone_m else ""

    # LinkedIn
    linkedin = ""
    for item in combined.split():
        if "linkedin.com" in item.lower() or "linkedin" in item.lower():
            cleaned = item.strip("|,;()[]")
            if "linkedin" in cleaned.lower():
                linkedin = cleaned
                break

    # GitHub
    github = ""
    for item in combined.split():
        if "github.com" in item.lower() or ("github" in item.lower() and "/" in item):
            cleaned = item.strip("|,;()[]")
            if "github" in cleaned.lower():
                github = cleaned
                break

    # İletişim satırını oluştur
    contact_parts = []
    if email:
        contact_parts.append(email)
    if phone:
        contact_parts.append(phone)
    if linkedin:
        contact_parts.append(linkedin)
    if github:
        contact_parts.append(github)
    if not contact_parts:
        contact_parts = ["İstanbul, Türkiye", "iletisim@yildiz.edu.tr"]

    return {
        "name": name,
        "contact_line": "  •  ".join(contact_parts)
    }


def turkish_upper(text: str) -> str:
    """Türkçe i -> İ ve ı -> I dönüşümlerini yaparak büyük harfe çevirir."""
    if not text:
        return ""
    return text.replace("i", "İ").replace("ı", "I").upper()


def add_section_header(doc: Document, title: str):
    """ATS dostu standart bölüm başlığı ekler."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True
    add_bottom_border(p, hex_color="1E3A8A", size="6")

    run = p.add_run(turkish_upper(title))
    run.bold = True
    run.font.name = "Calibri"
    run.font.size = Pt(11.5)
    run.font.color.rgb = COLOR_PRIMARY


def add_bullet_point(doc: Document, text: str):
    """Standart girintili madde işareti ekler."""
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(2.5)
    p.paragraph_format.line_spacing = 1.08

    run = p.add_run(text)
    run.font.name = "Calibri"
    run.font.size = Pt(10)
    run.font.color.rgb = COLOR_TEXT


def build_resume_docx(
    parsed_cv: dict,
    candidate_name: str = None,
    contact_line: str = None,
    improved_bullets: list = None,
    full_text: str = ""
) -> Document:
    """
    Ayrıştırılmış CV sözlüğünden Jake's Resume / Harvard standartlarında
    tek sayfa optimize DOCX belgesi oluşturur.
    """
    doc = Document()

    # Kenar Boşlukları (0.5 inç = 1.27 cm - Tek sayfaya mükemmel sığar)
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.5)
        section.bottom_margin = Inches(0.5)
        section.left_margin = Inches(0.5)
        section.right_margin = Inches(0.5)

    # Başlık ve İletişim Bilgileri
    header_info = parse_header_contact(parsed_cv.get("baslik_ve_kisisel", ""), full_text)
    final_name = candidate_name if candidate_name else header_info["name"]
    final_contact = contact_line if contact_line else header_info["contact_line"]

    # 1. ADAY ADI (Ortalı, Büyük, Kalın, 18pt)
    p_name = doc.add_paragraph()
    p_name.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_name.paragraph_format.space_before = Pt(0)
    p_name.paragraph_format.space_after = Pt(2)

    r_name = p_name.add_run(turkish_upper(final_name))
    r_name.bold = True
    r_name.font.name = "Calibri"
    r_name.font.size = Pt(18)
    r_name.font.color.rgb = COLOR_PRIMARY

    # 2. İLETİŞİM BİLGİLERİ SATIRI (Ortalı, 9.5pt)
    p_contact = doc.add_paragraph()
    p_contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_contact.paragraph_format.space_before = Pt(0)
    p_contact.paragraph_format.space_after = Pt(6)

    r_contact = p_contact.add_run(final_contact)
    r_contact.font.name = "Calibri"
    r_contact.font.size = Pt(9.5)
    r_contact.font.color.rgb = COLOR_MUTED

    # 3. ÖZET / PROFİL (Varsa)
    ozet_text = parsed_cv.get("ozet", "").strip()
    if ozet_text:
        add_section_header(doc, "Özet")
        p_ozet = doc.add_paragraph()
        p_ozet.paragraph_format.space_before = Pt(2)
        p_ozet.paragraph_format.space_after = Pt(4)
        p_ozet.paragraph_format.line_spacing = 1.1
        r_ozet = p_ozet.add_run(ozet_text)
        r_ozet.font.name = "Calibri"
        r_ozet.font.size = Pt(10)
        r_ozet.font.color.rgb = COLOR_TEXT

    # 4. EĞİTİM (EDUCATION)
    egitim_text = parsed_cv.get("egitim", "").strip()
    if egitim_text:
        add_section_header(doc, "Eğitim")
        for line in egitim_text.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            p_edu = doc.add_paragraph()
            p_edu.paragraph_format.space_before = Pt(1)
            p_edu.paragraph_format.space_after = Pt(2)
            p_edu.paragraph_format.line_spacing = 1.08

            r_edu = p_edu.add_run(line_str)
            r_edu.font.name = "Calibri"
            r_edu.font.size = Pt(10)
            if "üniversite" in line_str.lower() or "fakülte" in line_str.lower() or "university" in line_str.lower():
                r_edu.bold = True
                r_edu.font.color.rgb = COLOR_PRIMARY
            else:
                r_edu.font.color.rgb = COLOR_TEXT

    # 5. DENEYİM / STAJ (EXPERIENCE)
    deneyim_text = parsed_cv.get("deneyim", "").strip()
    if deneyim_text:
        add_section_header(doc, "İş Deneyimi")
        lines = [l.strip() for l in deneyim_text.splitlines() if l.strip()]
        for l in lines:
            clean_l = re.sub(r"^[\•\-\*\–\—\▪\▫\◦\►\>\d\.\)]+\s*", "", l).strip()
            # Başlık benzeri satır mı (örn: Şirket | Pozisyon | Tarih)
            if "|" in l or " - 20" in l or "/20" in l:
                p_sub = doc.add_paragraph()
                p_sub.paragraph_format.space_before = Pt(3)
                p_sub.paragraph_format.space_after = Pt(1)
                r_sub = p_sub.add_run(l)
                r_sub.bold = True
                r_sub.font.name = "Calibri"
                r_sub.font.size = Pt(10.5)
                r_sub.font.color.rgb = COLOR_PRIMARY
            elif len(clean_l.split()) >= 3:
                add_bullet_point(doc, clean_l)

    # 6. PROJELER (PROJECTS) - Geliştirilmiş STAR maddeleri buraya entegre edilebilir
    projeler_text = parsed_cv.get("projeler", "").strip()
    if projeler_text or improved_bullets:
        add_section_header(doc, "Projeler")

        # Eğer kullanıcı STAR güçlendirici ile yeni maddeler oluşturmuşsa onları da dahil et
        if improved_bullets:
            for ib in improved_bullets:
                add_bullet_point(doc, ib)
        elif projeler_text:
            lines = [l.strip() for l in projeler_text.splitlines() if l.strip()]
            for l in lines:
                clean_l = re.sub(r"^[\•\-\*\–\—\▪\▫\◦\►\>\d\.\)]+\s*", "", l).strip()
                if "|" in l or (len(l.split()) <= 5 and not l.endswith(".")):
                    p_sub = doc.add_paragraph()
                    p_sub.paragraph_format.space_before = Pt(3)
                    p_sub.paragraph_format.space_after = Pt(1)
                    r_sub = p_sub.add_run(l)
                    r_sub.bold = True
                    r_sub.font.name = "Calibri"
                    r_sub.font.size = Pt(10.5)
                    r_sub.font.color.rgb = COLOR_PRIMARY
                elif len(clean_l.split()) >= 3:
                    add_bullet_point(doc, clean_l)

    # 7. TEKNİK YETENEKLER (TECHNICAL SKILLS)
    yetenek_text = parsed_cv.get("yetenekler", "").strip()
    if yetenek_text:
        add_section_header(doc, "Teknik Yetenekler")
        p_skill = doc.add_paragraph()
        p_skill.paragraph_format.space_before = Pt(2)
        p_skill.paragraph_format.space_after = Pt(3)
        p_skill.paragraph_format.line_spacing = 1.1

        # Yetenekleri temiz listele
        r_skill = p_skill.add_run(yetenek_text)
        r_skill.font.name = "Calibri"
        r_skill.font.size = Pt(10)
        r_skill.font.color.rgb = COLOR_TEXT

    # 8. SERTİFİKALAR (Varsa)
    sertifika_text = parsed_cv.get("sertifikalar", "").strip()
    if sertifika_text:
        add_section_header(doc, "Sertifikalar")
        for s_line in sertifika_text.splitlines():
            clean_s = re.sub(r"^[\•\-\*\–\—\▪\▫\◦\►\>\d\.\)]+\s*", "", s_line).strip()
            if clean_s:
                add_bullet_point(doc, clean_s)

    # 9. YABANCI DİLLER (Varsa)
    diller_text = parsed_cv.get("diller", "").strip()
    if diller_text:
        add_section_header(doc, "Yabancı Diller")
        p_lang = doc.add_paragraph()
        p_lang.paragraph_format.space_before = Pt(1)
        p_lang.paragraph_format.space_after = Pt(2)
        r_l_val = p_lang.add_run(diller_text.replace("\n", ", "))
        r_l_val.font.name = "Calibri"
        r_l_val.font.size = Pt(10)
        r_l_val.font.color.rgb = COLOR_TEXT

    return doc


def export_cv_to_bytes(
    parsed_cv: dict,
    candidate_name: str = None,
    contact_line: str = None,
    improved_bullets: list = None,
    full_text: str = ""
) -> bytes:
    """Streamlit doğrudan indirme butonu için DOCX dosyasını bellek içi (bytes) üretir."""
    doc = build_resume_docx(
        parsed_cv=parsed_cv,
        candidate_name=candidate_name,
        contact_line=contact_line,
        improved_bullets=improved_bullets,
        full_text=full_text
    )
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def export_cv_to_file(
    file_path: str,
    parsed_cv: dict,
    candidate_name: str = None,
    contact_line: str = None,
    improved_bullets: list = None,
    full_text: str = ""
) -> str:
    """DOCX dosyasını diske kaydeder ve dosya yolunu döndürür."""
    doc = build_resume_docx(
        parsed_cv=parsed_cv,
        candidate_name=candidate_name,
        contact_line=contact_line,
        improved_bullets=improved_bullets,
        full_text=full_text
    )
    doc.save(file_path)
    return file_path


# --- TEST BLOĞU ---
if __name__ == "__main__":
    print("🚀 docx_exporter.py Test Ediliyor...\n")
    sample_parsed = {
        "baslik_ve_kisisel": "Murat Kerim Yılmaz\nmurat.yilmaz@std.yildiz.edu.tr | 0555 123 45 67 | github.com/muratyilmaz | linkedin.com/in/muratyilmaz",
        "ozet": "Yıldız Teknik Üniversitesi Matematik Mühendisliği öğrencisiyim. Yapay zeka ve veri mühendisliği alanlarında projeler geliştiriyorum.",
        "egitim": "Yıldız Teknik Üniversitesi - Matematik Mühendisliği (Eylül 2025 - Haziran 2029)",
        "projeler": "Staj Asistanı | Python, Streamlit, SQLite\n- Öğrencilerin staj başvurularını analiz eden yapay zeka destekli web uygulaması geliştirdim ve 150+ kullanıcı ile test ettim.\n- Kural tabanlı ATS algoritması tasarlayarak metin ayrıştırma süresini %40 hızlandırdım.",
        "deneyim": "",
        "yetenekler": "Python, C, SQL, Git, Docker, Streamlit, Pandas, OOP, Veri Analizi",
        "sertifikalar": "Python for Data Science - Coursera (2025)",
        "diller": "İngilizce (B2), Türkçe (Anadil)"
    }

    test_output = "test_jakes_resume.docx"
    export_cv_to_file(test_output, sample_parsed)
    print(f"✅ Test DOCX dosyası başarıyla üretildi: '{test_output}'")

    docx_bytes = export_cv_to_bytes(sample_parsed)
    print(f"📦 Bellek içi DOCX boyutu: {len(docx_bytes)} bayt")

    if os.path.exists(test_output):
        os.remove(test_output)
    print("\n✨ docx_exporter.py testleri başarıyla tamamlandı!")
