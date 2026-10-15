"""
SQLite Başvuru Takip Modülü (tracker.py) - YTÜ Staj Asistanı

Özellikler:
    - Öğrencinin staj başvurularını yerel SQLite veritabanında saklar (data/applications.db).
    - Şirket adı, pozisyon, lokasyon, başvuru tarihi, son tarih, durum yönetimi.
    - Analiz motorundan gelen ATS Skoru, İlan Uyum Skoru ve İşe Alınma İhtimalini kaydeder.
    - Süreç durumu takibi (Başvuruldu -> Ön Eleme -> Teknik Mülakat -> İK Mülakatı -> Teklif / Red).
    - Mülakat notları, mülakat soruları ve kişisel geri bildirim tutma.
    - Başvuru istatistikleri ve dönüşüm oranları (Dönüş oranı %, Mülakat oranı %).
"""
import os
import re
import sqlite3
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DB_DIR, "applications.db")

STATUS_OPTIONS = [
    "Başvuruldu",
    "Ön Eleme Geçildi",
    "Teknik Mülakat",
    "İK Mülakatı",
    "Teklif Alındı 🎉",
    "Reddedildi",
    "Geri Çekildi"
]

STATUS_COLORS = {
    "Başvuruldu": "#2563EB",        # Mavi
    "Ön Eleme Geçildi": "#0284C7",   # Açık Mavi / Gökyüzü
    "Teknik Mülakat": "#7C3AED",     # Mor
    "İK Mülakatı": "#9333EA",        # Menekşe
    "Teklif Alındı 🎉": "#16A34A",   # Yeşil
    "Reddedildi": "#DC2626",        # Kırmızı
    "Geri Çekildi": "#6B7280"       # Gri
}


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Veritabanı bağlantısı oluşturur ve satırları dict gibi erişilebilir yapar."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """Veritabanı tablosunu ve indekslerini oluşturur."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            position_title TEXT NOT NULL,
            location TEXT DEFAULT '',
            application_date TEXT NOT NULL,
            deadline TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Başvuruldu',
            match_score INTEGER DEFAULT 0,
            ats_score INTEGER DEFAULT 0,
            hire_probability INTEGER DEFAULT 0,
            job_description TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON applications(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_company ON applications(company_name);")
    conn.commit()
    conn.close()


def infer_company_and_role(job_text: str) -> tuple[str, str]:
    """İlan metninin ilk satırlarından şirket adı ve pozisyon tahmin eder."""
    if not job_text or not job_text.strip():
        return "Bilinmeyen Şirket", "Stajyer"

    lines = [line.strip() for line in job_text.splitlines() if line.strip()]
    first_line = lines[0] if lines else "Bilinmeyen Şirket"

    # Örn: "Aselsan - Yazılım Mühendisliği Stajyeri" veya "Trendyol | Data Intern"
    delimiters = [" - ", " – ", " | ", ": "]
    for d in delimiters:
        if d in first_line:
            parts = first_line.split(d, 1)
            comp = parts[0].strip()
            pos = parts[1].strip()
            if comp and pos:
                return comp[:60], pos[:60]

    # İlk satırı şirket veya rol olarak değerlendir
    if "staj" in first_line.lower() or "intern" in first_line.lower():
        return "Şirket Adı", first_line[:60]
    return first_line[:60], "Stajyer Mühendis"


def add_application(
    company_name: str,
    position_title: str,
    location: str = "İstanbul / Hibrit",
    application_date: str = None,
    deadline: str = "",
    status: str = "Başvuruldu",
    match_score: int = 0,
    ats_score: int = 0,
    hire_probability: int = 0,
    job_description: str = "",
    notes: str = "",
    db_path: str = DB_PATH
) -> int:
    """Yeni bir staj başvurusu kaydeder ve oluşan ID'yi döndürür."""
    init_db(db_path)
    if not application_date:
        application_date = datetime.now().strftime("%Y-%m-%d")

    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO applications (
            company_name, position_title, location, application_date,
            deadline, status, match_score, ats_score, hire_probability,
            job_description, notes, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        company_name.strip(),
        position_title.strip(),
        location.strip(),
        application_date.strip(),
        deadline.strip(),
        status.strip(),
        int(match_score),
        int(ats_score),
        int(hire_probability),
        job_description.strip(),
        notes.strip()
    ))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id


def get_all_applications(
    status_filter: str = None,
    search_query: str = None,
    db_path: str = DB_PATH
) -> list[dict]:
    """Tüm başvuruları listeler; opsiyonel filtreleme ve arama destekler."""
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    query = "SELECT * FROM applications WHERE 1=1"
    params = []

    if status_filter and status_filter != "Tümü":
        query += " AND status = ?"
        params.append(status_filter)

    if search_query and search_query.strip():
        term = f"%{search_query.strip()}%"
        query += " AND (company_name LIKE ? OR position_title LIKE ? OR notes LIKE ?)"
        params.extend([term, term, term])

    query += " ORDER BY application_date DESC, id DESC"
    cursor.execute(query, params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_application_by_id(app_id: int, db_path: str = DB_PATH) -> dict | None:
    """Belirli bir başvuru kaydını ID ile çeker."""
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM applications WHERE id = ?", (app_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_application(app_id: int, db_path: str = DB_PATH, **kwargs) -> bool:
    """Bir başvurunun alanlarını günceller."""
    if not kwargs:
        return False

    allowed_fields = [
        "company_name", "position_title", "location", "application_date",
        "deadline", "status", "match_score", "ats_score", "hire_probability",
        "job_description", "notes"
    ]
    set_clauses = []
    params = []

    for k, v in kwargs.items():
        if k in allowed_fields:
            set_clauses.append(f"{k} = ?")
            params.append(v)

    if not set_clauses:
        return False

    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    params.append(app_id)

    conn = get_connection(db_path)
    cursor = conn.cursor()
    query = f"UPDATE applications SET {', '.join(set_clauses)} WHERE id = ?"
    cursor.execute(query, params)
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success


def update_application_status(
    app_id: int,
    new_status: str,
    note_to_append: str = None,
    db_path: str = DB_PATH
) -> bool:
    """Başvurunun durumunu günceller ve isteğe bağlı tarihli mülakat notu ekler."""
    app = get_application_by_id(app_id, db_path)
    if not app:
        return False

    notes = app.get("notes", "") or ""
    if note_to_append and note_to_append.strip():
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
        log_entry = f"\n[{now_str} - {new_status}]: {note_to_append.strip()}"
        notes = (notes + log_entry).strip()

    return update_application(app_id, db_path=db_path, status=new_status, notes=notes)


def delete_application(app_id: int, db_path: str = DB_PATH) -> bool:
    """Başvuruyu veritabanından kalıcı olarak siler."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM applications WHERE id = ?", (app_id,))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success


def get_application_statistics(db_path: str = DB_PATH) -> dict:
    """Başvuru sayıları, dönüş oranları ve aşama dağılımını hesaplar."""
    apps = get_all_applications(db_path=db_path)
    total = len(apps)
    if total == 0:
        return {
            "toplam": 0,
            "aktif": 0,
            "mulakat": 0,
            "teklif": 0,
            "red": 0,
            "donus_orani": 0.0,
            "ortalama_uyum": 0,
            "ortalama_ats": 0,
            "durum_dagilimi": {}
        }

    durum_dagilimi = {}
    for st in STATUS_OPTIONS:
        durum_dagilimi[st] = sum(1 for a in apps if a["status"] == st)

    aktif = sum(1 for a in apps if a["status"] not in ["Reddedildi", "Geri Çekildi"])
    mulakat = durum_dagilimi.get("Teknik Mülakat", 0) + durum_dagilimi.get("İK Mülakatı", 0) + durum_dagilimi.get("Ön Eleme Geçildi", 0)
    teklif = durum_dagilimi.get("Teklif Alındı 🎉", 0)
    red = durum_dagilimi.get("Reddedildi", 0)

    # İncelemeye alınan veya dönüş yapılan başvuru oranı
    donus_yapilan = total - durum_dagilimi.get("Başvuruldu", 0)
    donus_orani = round((donus_yapilan / total) * 100, 1) if total > 0 else 0.0

    match_scores = [a["match_score"] for a in apps if a.get("match_score", 0) > 0]
    avg_match = round(sum(match_scores) / len(match_scores)) if match_scores else 0

    ats_scores = [a["ats_score"] for a in apps if a.get("ats_score", 0) > 0]
    avg_ats = round(sum(ats_scores) / len(ats_scores)) if ats_scores else 0

    return {
        "toplam": total,
        "aktif": aktif,
        "mulakat": mulakat,
        "teklif": teklif,
        "red": red,
        "donus_orani": donus_orani,
        "ortalama_uyum": avg_match,
        "ortalama_ats": avg_ats,
        "durum_dagilimi": durum_dagilimi
    }


# --- TEST BLOĞU ---
if __name__ == "__main__":
    test_db = os.path.join(DB_DIR, "test_applications.db")
    if os.path.exists(test_db):
        os.remove(test_db)

    print("🚀 tracker.py Test Ediliyor...\n")
    init_db(test_db)

    # 1. Başvuru ekleme testi
    app_id = add_application(
        company_name="Aselsan",
        position_title="Yazılım Mühendisliği Stajyeri",
        location="Ankara / Hibrit",
        status="Başvuruldu",
        match_score=85,
        ats_score=90,
        hire_probability=82,
        notes="Kariyer Kapısı üzerinden başvuruldu.",
        db_path=test_db
    )
    print(f"✅ Yeni başvuru eklendi, ID: {app_id}")

    # 2. İkinci başvuru ekleme
    add_application(
        company_name="Trendyol",
        position_title="Veri Bilimi Stajyeri",
        location="İstanbul / Maslak",
        status="Teknik Mülakat",
        match_score=78,
        ats_score=85,
        hire_probability=75,
        notes="HackerRank sınavı tamamlandı, teknik mülakat bekleniyor.",
        db_path=test_db
    )

    # 3. Listeleme testi
    all_apps = get_all_applications(db_path=test_db)
    print(f"📋 Toplam başvuru sayısı: {len(all_apps)}")
    for a in all_apps:
        print(f"   • {a['company_name']} - {a['position_title']} | Durum: {a['status']} | Uyum: %{a['match_score']}")

    # 4. Durum güncelleme testi
    update_application_status(app_id, "Ön Eleme Geçildi", "İK'dan telefon geldi, mülakat tarihi 20 Ekim.", db_path=test_db)
    updated_app = get_application_by_id(app_id, db_path=test_db)
    print(f"\n🔄 Güncellenen Durum: {updated_app['status']}")
    print(f"📝 Notlar:\n{updated_app['notes']}")

    # 5. İstatistik testi
    stats = get_application_statistics(db_path=test_db)
    print(f"\n📊 İstatistikler: Toplam={stats['toplam']}, Aktif={stats['aktif']}, Mülakat={stats['mulakat']}, Dönüş Oranı=%{stats['donus_orani']}")

    # Temizlik
    if os.path.exists(test_db):
        os.remove(test_db)
    print("\n✨ tracker.py testleri başarıyla tamamlandı!")
