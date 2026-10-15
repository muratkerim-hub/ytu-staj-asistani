"""
Aşama 4 — İlan Analizi ve CV-İlan Eşleştirme Motoru (saf Python, LLM yok).

Akış:
    1. İlan metni satır/cümle bazında okunur, bölüm başlıklarına göre (Aranan Nitelikler,
       Tercih Sebebi, İş Tanımı, Hakkımızda...) her yetenek ZORUNLU / TERCİHLİ olarak sınıflanır.
       "Python, Java veya C#" gibi ifadeler "en az biri yeterli" (alternatif grup) olarak tanınır.
    2. CV bölümlerinde (parser.parse_cv_sections çıktısı) yetenekler aranır:
         - Deneyim / Projeler içinde geçiyorsa  -> KANITLI    (tam puan)
         - Sadece Yetenekler/Eğitim/Özet'te ise -> LİSTELENMİŞ (kısmi puan)
         - Hiç yazmıyor ama başka yetenekten çıkarılabiliyorsa (Django -> Python) -> DOLAYLI
    3. Ağırlıklı puan (0-100), kategori kırılımı, eksikler, zayıf kanıtlar ve
       CV'de olup ilanda istenmeyen (öne çıkarılabilecek) yetenekler raporlanır.

Veri dosyaları: data/skills.json (kanonik sözlük), data/synonyms.json (eş anlamlılar, ilişkiler).
"""
import json
import os
import re
import sys
from dataclasses import dataclass
from functools import lru_cache

from parser import extract_text_from_pdf, extract_text_from_docx, parse_cv_sections

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# --- Puanlama sabitleri (Gerçekçi Mühendislik Stajı Standartları) ---
WEIGHT_REQUIRED = 3.0        # "Aranan Nitelikler" altındaki / "zorunlu" yetenek
WEIGHT_RESPONSIBILITY = 2.0  # "İş Tanımı / Sorumluluklar" veya başlıksız kısımda geçen yetenek
WEIGHT_PREFERRED = 1.0       # "Tercih sebebi / artı / nice to have"
CREDIT_PROVEN = 1.0          # Deneyim veya Projeler bölümünde somut kanıtlı
CREDIT_LISTED = 0.55         # Yetenekler / Özet bölümünde listelenmiş
IMPLIED_FACTOR = 0.45        # Dolaylı eşleşme (örn. Django -> Python)

PROVEN_SECTIONS = {"deneyim", "projeler"}

SECTION_LABELS = {
    "baslik_ve_kisisel": "Başlık", "iletisim": "İletişim", "ozet": "Özet", "egitim": "Eğitim",
    "deneyim": "Deneyim", "projeler": "Projeler", "yetenekler": "Yetenekler",
    "sertifikalar": "Sertifikalar", "diller": "Diller",
}

# =====================================================================
# 1) METİN NORMALİZASYONU
# =====================================================================
# Türkçe karakterleri ASCII'ye katlar. Her karakter tek karaktere eşlendiği için
# katlanmış metindeki indeksler orijinal metinle birebir aynıdır (eşleşmeyi geri gösterebilmek için önemli).
_TR_FOLD = str.maketrans({
    "İ": "i", "I": "i", "ı": "i", "Ş": "s", "ş": "s", "Ç": "c", "ç": "c", "Ğ": "g", "ğ": "g",
    "Ö": "o", "ö": "o", "Ü": "u", "ü": "u", "Â": "a", "â": "a", "Î": "i", "î": "i", "Û": "u", "û": "u",
    "’": "'", "`": "'",
})


def fold(text: str) -> str:
    """Büyük/küçük harf ve Türkçe karakter duyarsız karşılaştırma için metni normalize eder (uzunluk korunur)."""
    translated = text.translate(_TR_FOLD)
    return "".join(ch.lower() if len(ch.lower()) == 1 else ch for ch in translated)


# Türkçe çekim/yapım ekleri (katlanmış halde). "Python'da" gibi kesme işaretli ekler her zaman,
# kesmesiz ekler ("istatistiksel", "optimizasyonu", "veri analizinde") yalnızca 4+ harfli terimlerde tolere edilir.
_TR_SUFFIXES = sorted({
    "da", "de", "ta", "te", "dan", "den", "tan", "ten", "nda", "nde", "ndan", "nden",
    "i", "u", "yi", "yu", "ni", "nu", "in", "un", "nin", "nun", "yin", "yun",
    "a", "e", "ya", "ye", "na", "ne", "la", "le", "yla", "yle", "iyla", "iyle", "ile",
    "lar", "ler", "lari", "leri", "si", "su", "sel", "sal", "li", "lu",
    "ki", "daki", "deki", "ndaki", "ndeki",
}, key=len, reverse=True)
_TR_SUFFIX_RE = "(?:" + "|".join(_TR_SUFFIXES) + "){1,3}"

# Belirli terimler için bağlam istisnaları (katlanmış alias -> negatif ileri bakış).
#   "C sınıfı ehliyet", "C Blok" -> C dili değil;  "R&D" / "R & D" -> R dili değil;
#   "Spring 2025 / Spring semester" -> Spring framework değil.
_NEGATIVE_CONTEXT = {
    "c": r"(?!\s*(?i:s[ıi]n[ıi]f|blok|tipi|ehliyet))",
    "r": r"(?!\s*&)",
    "spring": r"(?!\s+(?:20\d\d|semester|term|donemi))",
}


# =====================================================================
# 2) YETENEK ÇIKARICI
# =====================================================================
@dataclass
class SkillHit:
    canonical: str
    start: int
    end: int
    text: str


class SkillExtractor:
    """skills.json + synonyms.json'dan derlenmiş regex'lerle metindeki yetenekleri bulur."""

    def __init__(self, skills_data: dict, synonyms_data: dict):
        self.skill_category: dict[str, str] = {}
        self.category_label: dict[str, str] = {}
        self.category_multiplier: dict[str, float] = {}

        for cat_key, cat in skills_data.items():
            if cat_key.startswith("_"):
                continue
            self.category_label[cat_key] = cat["label"]
            self.category_multiplier[cat_key] = float(cat.get("weight_multiplier", 1.0))
            for skill in cat["skills"]:
                if skill in self.skill_category:
                    raise ValueError(f"skills.json: '{skill}' hem '{self.skill_category[skill]}' hem '{cat_key}' kategorisinde.")
                self.skill_category[skill] = cat_key

        case_sensitive = set(synonyms_data.get("case_sensitive", []))
        aliases = synonyms_data.get("aliases", {})
        implies = synonyms_data.get("implies", {})

        # Veri bütünlüğü: synonyms.json'daki her isim skills.json'da tanımlı olmalı
        referenced = set(aliases) | set(implies) | {t for targets in implies.values() for t in targets}
        unknown = sorted(referenced - set(self.skill_category))
        if unknown:
            raise ValueError(f"synonyms.json içinde skills.json'da olmayan yetenekler var: {unknown}")

        self.implied_closure = {s: self._closure(s, implies) for s in implies}

        # Her alias için tek bir regex; aynı alias iki farklı yeteneğe atanmışsa hata ver
        alias_owner: dict[str, str] = {}
        self._patterns: list[tuple[re.Pattern, str, bool]] = []
        for canonical in self.skill_category:
            for alias in [canonical] + aliases.get(canonical, []):
                is_cs = alias in case_sensitive
                key = alias if is_cs else fold(alias)
                owner = alias_owner.get(key)
                if owner and owner != canonical:
                    raise ValueError(f"Eş anlamlı çakışması: '{alias}' hem '{owner}' hem '{canonical}' için tanımlı.")
                if owner:
                    continue
                alias_owner[key] = canonical
                self._patterns.append((self._compile(alias, is_cs), canonical, is_cs))

    @staticmethod
    def _closure(skill: str, implies: dict) -> list[str]:
        """Django -> Python, PyTorch -> Derin Öğrenme -> Makine Öğrenmesi -> Yapay Zeka (geçişli)."""
        seen, stack = set(), list(implies.get(skill, []))
        while stack:
            current = stack.pop()
            if current in seen or current == skill:
                continue
            seen.add(current)
            stack.extend(implies.get(current, []))
        return sorted(seen)

    @staticmethod
    def _compile(alias: str, case_sensitive: bool) -> re.Pattern:
        src = alias if case_sensitive else fold(alias)
        core = r"[\s\-]+".join(re.escape(part) for part in src.split())

        if len(src) == 1:
            # Tek harfli diller (C, R): "USB-C", "Objective-C", "R&D" gibi durumları dışla
            left, right = r"(?<![\w\-.])", r"(?![\w+#&\-])"
        else:
            left, right = r"(?<!\w)", r"(?![\w+#])"

        suffix = r"['’]\w+"
        if not case_sensitive and len(src) >= 4 and src[-1].isalpha():
            suffix += "|" + _TR_SUFFIX_RE
        negative = _NEGATIVE_CONTEXT.get(fold(alias), "")

        return re.compile(f"{left}{core}(?:{suffix})?{right}{negative}")

    def extract(self, text: str) -> list[SkillHit]:
        """Metindeki yetenekleri bulur. Çakışan eşleşmelerde en uzun olan kazanır
        ('React Native' > 'React', 'Microsoft SQL Server' > 'SQL', 'C++' > 'C')."""
        if not text:
            return []
        folded = fold(text)
        candidates = []
        for pattern, canonical, is_cs in self._patterns:
            for m in pattern.finditer(text if is_cs else folded):
                candidates.append(SkillHit(canonical, m.start(), m.end(), text[m.start():m.end()]))

        candidates.sort(key=lambda h: (-(h.end - h.start), h.start))
        occupied = bytearray(len(text))
        accepted = []
        for hit in candidates:
            if any(occupied[hit.start:hit.end]):
                continue
            occupied[hit.start:hit.end] = b"\x01" * (hit.end - hit.start)
            accepted.append(hit)
        return sorted(accepted, key=lambda h: h.start)


@lru_cache(maxsize=1)
def get_extractor() -> SkillExtractor:
    """Sözlükleri bir kez yükler ve derler (Streamlit'te her istekte tekrar derlenmesin)."""
    with open(os.path.join(DATA_DIR, "skills.json"), encoding="utf-8") as f:
        skills_data = json.load(f)
    with open(os.path.join(DATA_DIR, "synonyms.json"), encoding="utf-8") as f:
        synonyms_data = json.load(f)
    return SkillExtractor(skills_data, synonyms_data)


# =====================================================================
# 3) İLAN ANALİZİ
# =====================================================================
# Bölüm başlığı anahtar kelimeleri (katlanmış). SIRA ÖNEMLİ: "preferred qualifications" önce tercihli
# olarak yakalanmalı, yoksa "qualifications" yüzünden zorunlu sanılır.
_JOB_HEADERS = [
    ("tercihli", ["tercihen", "tercih sebebi", "tercih nedeni", "tercih edilen", "tercih edilir", "arti deger",
                  "artilar", "nice to have", "nice-to-have", "preferred", "bonus", "plus", "avantaj",
                  "olursa iyi olur", "olmasi artidir"]),
    ("zorunlu", ["aranan nitelik", "aranan ozellik", "genel nitelik", "nitelikler", "gereksinim", "beklentilerimiz",
                 "senden beklediklerimiz", "sizden beklediklerimiz", "adaylarda aradig", "aradigimiz", "requirements",
                 "qualifications", "must have", "must-have", "what we're looking for", "what we are looking for",
                 "what you'll need", "what you need", "teknik beceri", "teknik yetkinlik", "yetkinlikler",
                 "required skills", "skills"]),
    ("is_tanimi", ["is tanimi", "gorev tanimi", "sorumluluk", "gorevler", "neler yapacaksin", "ne yapacaksin",
                   "responsibilities", "what you'll do", "what you will do", "job description", "pozisyon hakkinda",
                   "rol hakkinda", "the role"]),
    ("yoksay", ["hakkimizda", "biz kimiz", "about us", "about the company", "sirket hakkinda", "yan haklar",
                "neler sunuyoruz", "sunduklarimiz", "benefits", "perks", "what we offer", "calisma kosullari",
                "basvuru"]),
]

_PREFERRED_MARKERS = re.compile(
    r"tercih|\barti(?:dir|si|lar)?\b|arti deger|avantaj|nice to have|preferred|\bbonus\b|\bplus\b|"
    r"olmasi guzel|hos karsilanir")
_REQUIRED_MARKERS = re.compile(r"zorunlu|mutlaka|\bsart(?:tir)?\b|\bmust\b|required|gereklidir|olmazsa olmaz")
_ONE_OF_MARKERS = re.compile(r"en az bir|birinde|birine|herhangi bir|at least one|one of|any of")

_GAP_OR = re.compile(r"^\s*(?:,?\s*(?:veya|ya da|yahut|or|and/or|ve/veya)|/|\|)\s*$")
_GAP_LIST = re.compile(r"^\s*(?:,|ve|and|&|\+)\s*$")
_BULLET_PREFIX = re.compile(r"^[\-\•\*\u25cf\u25aa\u2022\d\.\)\s]+")


def _detect_job_header(line: str) -> tuple[str | None, str]:
    """Satır bir bölüm başlığıysa (tür, başlıktan sonra aynı satırda kalan metin) döndürür."""
    head, sep, rest = line.partition(":")
    candidate = fold(_BULLET_PREFIX.sub("", head)).strip(" -–:")
    if not candidate or len(candidate.split()) > 6 or len(candidate) > 60:
        return None, line
    if not sep and len(candidate.split()) > 4:  # İki nokta yoksa başlık daha kısa olmalı
        return None, line
    for header_type, keywords in _JOB_HEADERS:
        if any(kw in candidate for kw in keywords):
            return header_type, rest.strip()
    return None, line


def _group_hits(hits: list[SkillHit], folded_segment: str) -> list[list[SkillHit]]:
    """Bir cümledeki yetenekleri gruplar.
    'Python, Java veya C#'  -> [[Python, Java, C#]]  (biri yeterli)
    'Python, SQL ve Git'    -> [[Python], [SQL], [Git]] (hepsi ayrı ayrı gerekli)"""
    if not hits:
        return []
    one_of = bool(_ONE_OF_MARKERS.search(folded_segment))
    groups, chain, chain_has_or = [], [hits[0]], False

    def flush():
        if chain_has_or or (one_of and len(chain) > 1):
            groups.append(list(chain))
        else:
            groups.extend([h] for h in chain)

    for prev, cur in zip(hits, hits[1:]):
        gap = folded_segment[prev.end:cur.start]
        if _GAP_OR.match(gap):
            chain.append(cur)
            chain_has_or = True
        elif _GAP_LIST.match(gap) or not gap.strip():
            chain.append(cur)
        else:
            flush()
            chain, chain_has_or = [cur], False
    flush()
    return groups


def analyze_job_posting(job_text: str) -> list[dict]:
    """İlan metninden gereksinim listesi çıkarır.
    Her eleman: {"yetenekler": [...], "seviye": "zorunlu"|"tercihli", "agirlik": float,
                "kaynak": "aranan"|"is_tanimi"|"genel"|"tercihli", "kategori": str, "satir": str}"""
    extractor = get_extractor()
    section = "genel"
    raw_items = []

    for raw_line in job_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        header_type, remainder = _detect_job_header(line)
        if header_type:
            section = header_type
            line = remainder
            if not line:
                continue
        if section == "yoksay":
            continue

        # "X zorunludur. Y tercih sebebidir." gibi satırları cümlelere böl
        for segment in re.split(r"(?<=[.;!?])\s+", line):
            folded = fold(segment)
            hits = extractor.extract(segment)
            if not hits:
                continue

            if _PREFERRED_MARKERS.search(folded):
                level, source = "tercihli", "tercihli"
            elif _REQUIRED_MARKERS.search(folded) or section == "zorunlu":
                level, source = "zorunlu", "aranan"
            elif section == "tercihli":
                level, source = "tercihli", "tercihli"
            else:
                level, source = "zorunlu", ("is_tanimi" if section == "is_tanimi" else "genel")

            weight = {"aranan": WEIGHT_REQUIRED, "tercihli": WEIGHT_PREFERRED}.get(source, WEIGHT_RESPONSIBILITY)
            for group in _group_hits(hits, folded):
                skills = list(dict.fromkeys(h.canonical for h in group))  # sırayı koruyarak tekilleştir
                raw_items.append({"yetenekler": skills, "seviye": level, "agirlik": weight,
                                  "kaynak": source, "satir": segment.strip()})

    # Tekilleştirme: aynı yetenek(ler) birden çok kez geçtiyse en yüksek ağırlıklı olanı tut
    best: dict[frozenset, dict] = {}
    for item in raw_items:
        key = frozenset(item["yetenekler"])
        if key not in best or item["agirlik"] > best[key]["agirlik"]:
            best[key] = item

    # Tekil olarak zaten (en az aynı ağırlıkta) istenen bir yeteneği içeren alternatif grupları at
    singles = {next(iter(k)): v["agirlik"] for k, v in best.items() if len(k) == 1}
    items = []
    for key, item in best.items():
        if len(key) > 1 and any(singles.get(s, 0) >= item["agirlik"] for s in key):
            continue
        item["kategori"] = extractor.skill_category[item["yetenekler"][0]]
        items.append(item)

    items.sort(key=lambda it: (-it["agirlik"], it["kategori"], it["yetenekler"][0]))
    return items


# =====================================================================
# 4) CV PROFİLİ
# =====================================================================
def build_cv_profile(cv_sections: dict) -> dict:
    """CV'deki her yetenek için en güçlü kanıtı bulur.
    Dönüş: {yetenek: {"durum": "kanitli"|"listelenmis"|"dolayli", "kredi": float,
                      "bolumler": [...], "ifadeler": [...], "kaynak": str|None}}"""
    extractor = get_extractor()
    profile: dict[str, dict] = {}

    for section, text in cv_sections.items():
        for hit in extractor.extract(text or ""):
            category = extractor.skill_category[hit.canonical]
            proven = section in PROVEN_SECTIONS or (section == "diller" and category == "yabanci_dil")
            credit = CREDIT_PROVEN if proven else CREDIT_LISTED
            entry = profile.setdefault(hit.canonical, {"durum": None, "kredi": 0.0, "bolumler": set(),
                                                       "ifadeler": set(), "kaynak": None})
            entry["bolumler"].add(section)
            entry["ifadeler"].add(hit.text.strip())
            if credit > entry["kredi"]:
                entry["kredi"] = credit
                entry["durum"] = "kanitli" if proven else "listelenmis"

    # Dolaylı yetenekler: CV'de doğrudan yazmayan ama başka yetenekten çıkarılabilenler
    for source, entry in list(profile.items()):
        for target in extractor.implied_closure.get(source, []):
            credit = round(entry["kredi"] * IMPLIED_FACTOR, 3)
            current = profile.get(target)
            if current is None or (current["durum"] == "dolayli" and credit > current["kredi"]):
                profile[target] = {"durum": "dolayli", "kredi": credit, "bolumler": set(),
                                   "ifadeler": set(), "kaynak": source}

    for entry in profile.values():
        entry["bolumler"] = sorted(entry["bolumler"])
        entry["ifadeler"] = sorted(entry["ifadeler"])
    return profile


# =====================================================================
# 5) EŞLEŞTİRME VE PUANLAMA
# =====================================================================
def _grade(score: int) -> str:
    if score >= 80:
        return "Üst Düzey Eşleşme (Mülakat Barajını Geçti)"
    if score >= 65:
        return "İyi Eşleşme — 1-2 kritik eksiklik var"
    if score >= 45:
        return "Orta Eşleşme — Zorunlu yeteneklerde belirgin boşluklar var"
    return "Zayıf Eşleşme (Elenme Riski Çok Yüksek)"


def _section_names(sections: list[str]) -> str:
    return ", ".join(SECTION_LABELS.get(s, s) for s in sections)


def match_cv_to_job(cv_sections: dict, job_text: str) -> dict:
    """CV bölümlerini (parse_cv_sections çıktısı) ilan metniyle eşleştirir ve detaylı rapor döndürür."""
    extractor = get_extractor()
    items = analyze_job_posting(job_text)
    if not items:
        return {"success": False,
                "error": "İlan metninde tanınan bir yetenek bulunamadı. Lütfen ilanın 'Aranan Nitelikler' kısmını da eklediğinizden emin olun."}

    profile = build_cv_profile(cv_sections)
    notes = []
    if not any(cv_sections.get(s) for s in PROVEN_SECTIONS):
        notes.append("CV'de 'Deneyim' veya 'Projeler' başlığı tespit edilemedi; bu yüzden hiçbir yetenek 'kanıtlı' sayılamadı. "
                     "Standart başlıklar kullanmak eşleşme puanını doğrudan artırır.")

    total_possible = total_earned = 0.0
    evaluated = []
    for item in items:
        best_skill, best_entry = None, None
        for skill in item["yetenekler"]:
            entry = profile.get(skill)
            if entry and (best_entry is None or entry["kredi"] > best_entry["kredi"]):
                best_skill, best_entry = skill, entry

        weight = item["agirlik"] * extractor.category_multiplier[item["kategori"]]
        credit = best_entry["kredi"] if best_entry else 0.0
        total_possible += weight
        total_earned += weight * credit

        evaluated.append({
            **item,
            "etiket": " / ".join(item["yetenekler"]),
            "kategori_adi": extractor.category_label[item["kategori"]],
            "durum": best_entry["durum"] if best_entry else "eksik",
            "eslesen_yetenek": best_skill,
            "cv_bolumleri": best_entry["bolumler"] if best_entry else [],
            "dolayli_kaynak": best_entry["kaynak"] if best_entry else None,
            "kredi": credit,
            "olasi_puan": round(weight, 2),
            "kazanilan_puan": round(weight * credit, 2),
        })

    score = round(100 * total_earned / total_possible) if total_possible else 0

    # Kategori kırılımı
    breakdown: dict[str, dict] = {}
    for ev in evaluated:
        cat = breakdown.setdefault(ev["kategori"], {"kategori": ev["kategori"], "kategori_adi": ev["kategori_adi"],
                                                    "kazanilan": 0.0, "olasi": 0.0, "karsilanan": 0, "toplam": 0})
        cat["kazanilan"] += ev["kazanilan_puan"]
        cat["olasi"] += ev["olasi_puan"]
        cat["toplam"] += 1
        cat["karsilanan"] += ev["durum"] != "eksik"
    category_breakdown = sorted(
        ({**c, "yuzde": round(100 * c["kazanilan"] / c["olasi"]) if c["olasi"] else 0} for c in breakdown.values()),
        key=lambda c: -c["olasi"])

    required = [ev for ev in evaluated if ev["seviye"] == "zorunlu"]
    missing_required = [ev for ev in required if ev["durum"] == "eksik"]
    missing_preferred = [ev for ev in evaluated if ev["seviye"] == "tercihli" and ev["durum"] == "eksik"]
    weak_evidence = [ev for ev in evaluated if ev["durum"] in ("listelenmis", "dolayli")]

    # CV'de olup ilanda istenmeyen yetenekler (dolaylılar hariç — onları öğrenci açıkça yazmadı)
    requested = {s for ev in evaluated for s in ev["yetenekler"]}
    job_categories = {ev["kategori"] for ev in evaluated}
    extras = [
        {"yetenek": skill, "kategori": extractor.skill_category[skill],
         "kategori_adi": extractor.category_label[extractor.skill_category[skill]],
         "durum": entry["durum"], "cv_bolumleri": entry["bolumler"]}
        for skill, entry in profile.items()
        if skill not in requested and entry["durum"] != "dolayli"
    ]
    extras.sort(key=lambda e: (e["durum"] != "kanitli", e["yetenek"]))
    extra_relevant = [e for e in extras if e["kategori"] in job_categories]
    extra_other = [e for e in extras if e["kategori"] not in job_categories]

    # Uygulanabilir öneriler (uydurma bilgi eklemeyi teşvik etmeden)
    suggestions = []
    for ev in missing_required:
        suggestions.append(f"❌ '{ev['etiket']}' ilanda zorunlu ama CV'nde görünmüyor. Gerçekten biliyorsan bir proje/deneyim "
                           f"maddesinde nasıl kullandığını yaz; bilmiyorsan CV'ye ekleme, öğrenme listene al.")
    for ev in weak_evidence:
        if ev["durum"] == "listelenmis":
            suggestions.append(f"⚠️ '{ev['eslesen_yetenek']}' sadece {_section_names(ev['cv_bolumleri'])} bölümünde geçiyor. "
                               f"Projeler/Deneyim'de somut bir kullanımını göstermek bu eşleşmeyi güçlendirir.")
        else:
            suggestions.append(f"ℹ️ '{ev['eslesen_yetenek']}' CV'nde açıkça yazmıyor, '{ev['dolayli_kaynak']}' üzerinden dolaylı eşleşti. "
                               f"ATS sistemleri bu ilişkiyi kuramaz; biliyorsan '{ev['eslesen_yetenek']}' kelimesini açıkça yaz.")
    if extra_relevant:
        names = ", ".join(e["yetenek"] for e in extra_relevant[:5])
        suggestions.append(f"💡 İlanla aynı alanda olup ilanda istenmeyen yeteneklerin var ({names}). "
                           f"Ön yazında veya özette bunları öne çıkarabilirsin.")

    return {
        "success": True,
        "error": None,
        "eslesme_puani": score,
        "degerlendirme": _grade(score),
        "zorunlu_kapsama": {"karsilanan": len(required) - len(missing_required), "toplam": len(required)},
        "gereksinimler": evaluated,
        "kategori_kirilimi": category_breakdown,
        "eksik_zorunlu": missing_required,
        "eksik_tercihli": missing_preferred,
        "zayif_kanit": weak_evidence,
        "ilgili_ekstra_yetenekler": extra_relevant,
        "diger_ekstra_yetenekler": extra_other,
        "oneriler": suggestions,
        "notlar": notes,
    }


# =====================================================================
# 6) KONSOL RAPORU + TEST BLOĞU
# =====================================================================
_STATUS_ICON = {"kanitli": "✅", "listelenmis": "🟡", "dolayli": "🔗", "eksik": "❌"}
_STATUS_TEXT = {"kanitli": "Kanıtlı", "listelenmis": "Sadece listelenmiş", "dolayli": "Dolaylı", "eksik": "Eksik"}


def print_report(result: dict) -> None:
    if not result["success"]:
        print(result["error"])
        return
    cov = result["zorunlu_kapsama"]
    print("=" * 70)
    print(f"🎯 İLAN EŞLEŞME PUANI: {result['eslesme_puani']} / 100  —  {result['degerlendirme']}")
    print(f"📌 Zorunlu gereksinim kapsaması: {cov['karsilanan']} / {cov['toplam']}")
    print("=" * 70)

    print("\n📊 KATEGORİ KIRILIMI")
    for c in result["kategori_kirilimi"]:
        bar = "█" * (c["yuzde"] // 10) + "░" * (10 - c["yuzde"] // 10)
        print(f"   {c['kategori_adi']:<36} {bar} %{c['yuzde']:<3} ({c['karsilanan']}/{c['toplam']})")

    print("\n📋 GEREKSİNİMLER")
    for ev in result["gereksinimler"]:
        level = "ZORUNLU " if ev["seviye"] == "zorunlu" else "TERCİHLİ"
        detail = _STATUS_TEXT[ev["durum"]]
        if ev["durum"] in ("kanitli", "listelenmis"):
            detail += f" → {_section_names(ev['cv_bolumleri'])}"
        elif ev["durum"] == "dolayli":
            detail += f" ← {ev['dolayli_kaynak']}"
        if len(ev["yetenekler"]) > 1 and ev["eslesen_yetenek"]:
            detail += f" (karşılayan: {ev['eslesen_yetenek']})"
        print(f"   {_STATUS_ICON[ev['durum']]} [{level}] {ev['etiket']:<32} {detail}")

    if result["ilgili_ekstra_yetenekler"] or result["diger_ekstra_yetenekler"]:
        print("\n➕ CV'DE OLUP İLANDA İSTENMEYENLER")
        if result["ilgili_ekstra_yetenekler"]:
            print("   İlgili alan  : " + ", ".join(e["yetenek"] for e in result["ilgili_ekstra_yetenekler"]))
        if result["diger_ekstra_yetenekler"]:
            print("   Diğer        : " + ", ".join(e["yetenek"] for e in result["diger_ekstra_yetenekler"]))

    if result["oneriler"]:
        print("\n🛠️ ÖNERİLER")
        for s in result["oneriler"]:
            print(f"   {s}")
    for n in result["notlar"]:
        print(f"\n📝 Not: {n}")


SAMPLE_JOB = """
Veri Bilimi Stajyeri — ABC Teknoloji A.Ş.

Hakkımızda
Yapay zeka ve bulut çözümleri geliştiren, 200+ kişilik bir teknoloji şirketiyiz. Udemy ve Coursera eğitim desteği sağlıyoruz.

Neler Yapacaksın?
- Müşteri verileri üzerinde veri analizi ve görselleştirme çalışmaları yapmak
- Makine öğrenmesi modellerinin geliştirilmesine destek olmak
- REST API'ler üzerinden veri toplama süreçlerinde görev almak

Aranan Nitelikler
- Üniversitelerin Bilgisayar, Matematik veya İstatistik bölümlerinde 3. veya 4. sınıf öğrencisi
- Python'a hakim, Pandas ve NumPy kütüphanelerini kullanmış
- SQL bilgisi zorunludur
- Git ile versiyon kontrolü deneyimi
- İstatistik ve olasılık konularında temel bilgi
- İyi derecede İngilizce
- Takım çalışmasına yatkın

Tercih Sebebi
- Docker veya Kubernetes deneyimi
- TensorFlow, PyTorch veya scikit-learn kütüphanelerinden en az birinde proje deneyimi
- Power BI / Tableau ile dashboard hazırlamış olmak
- AWS ya da GCP gibi bulut platformlarına aşinalık

Yan Haklar
- Esnek çalışma saatleri, yemek kartı, Docker eğitimleri
"""

SAMPLE_CV = """
Murat Kerim Yılmaz
murat.yilmaz@std.yildiz.edu.tr | 0555 123 45 67 | github.com/muratyilmaz

ÖZET
Yıldız Teknik Üniversitesi Matematik Mühendisliği öğrencisiyim. Yapay zeka ve veri mühendisliği alanlarında projeler geliştiriyorum.

EĞİTİM
Yıldız Teknik Üniversitesi - Matematik Mühendisliği (Eylül 2025 - Haziran 2029)
İlgili Dersler: Lineer Cebir, Olasılık, İstatistik, Sayısal Analiz

PROJELER
- Python ve Streamlit kullanarak öğrencilerin staj başvurularını analiz eden yapay zeka destekli bir web uygulaması geliştirdim ve 150+ kullanıcı ile test ettim.
- Pandas ile 50.000 satırlık açık veri setini temizledim, Matplotlib ile görselleştirip regresyon modeli kurdum.
- Gemini API ile CV maddelerini iyileştiren bir modül tasarladım.

YETENEKLER
Python, C, SQL, Git, Nesne Yönelimli Programlama (OOP), Streamlit, Veri Analizi, Django

DİLLER
İngilizce (B2), Almanca (A2)
"""


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows'ta emoji/Türkçe karakter hatasını önler

    # Gerçek dosyalar varsa onları kullan: cv.pdf / cv.docx ve ilan.txt
    if os.path.exists("cv.pdf"):
        print("📄 'cv.pdf' bulundu, okunuyor...")
        cv_res = extract_text_from_pdf("cv.pdf")
    elif os.path.exists("cv.docx"):
        print("📄 'cv.docx' bulundu, okunuyor...")
        cv_res = extract_text_from_docx("cv.docx")
    else:
        print("ℹ️ 'cv.pdf' bulunamadı, örnek CV kullanılıyor.")
        cv_res = {"success": True, "text": SAMPLE_CV}

    if os.path.exists("ilan.txt"):
        print("📄 'ilan.txt' bulundu, okunuyor...")
        with open("ilan.txt", encoding="utf-8") as f:
            job_text = f.read()
    else:
        print("ℹ️ 'ilan.txt' bulunamadı, örnek staj ilanı kullanılıyor.")
        print("(Kendi ilanını denemek için ilan metnini 'ilan.txt' adıyla proje klasörüne kaydedebilirsin.)")
        job_text = SAMPLE_JOB

    if not cv_res["success"]:
        print(cv_res["error"])
        sys.exit(1)

    print()
    print_report(match_cv_to_job(parse_cv_sections(cv_res["text"]), job_text))
