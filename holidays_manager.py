import sqlite3
import os
from typing import Dict, Any, List, Optional, Tuple

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "anyd_booking.db"))

# Listado oficial de festivos Nacionales, Comunidad de Madrid y Locales de Alcorcón
OFFICIAL_HOLIDAYS = [
    # --- 2025 ---
    {"date": "2025-01-01", "name": "Año Nuevo", "scope": "Nacional"},
    {"date": "2025-01-06", "name": "Epifanía del Señor / Reyes Magos", "scope": "Nacional"},
    {"date": "2025-04-17", "name": "Jueves Santo", "scope": "Comunidad de Madrid"},
    {"date": "2025-04-18", "name": "Viernes Santo", "scope": "Nacional"},
    {"date": "2025-04-21", "name": "San Dominguín / Fiestas de Alcorcón", "scope": "Local Alcorcón"},
    {"date": "2025-05-01", "name": "Fiesta del Trabajo", "scope": "Nacional"},
    {"date": "2025-05-02", "name": "Fiesta de la Comunidad de Madrid", "scope": "Comunidad de Madrid"},
    {"date": "2025-07-25", "name": "Santiago Apóstol", "scope": "Comunidad de Madrid"},
    {"date": "2025-08-15", "name": "Asunción de la Virgen", "scope": "Nacional"},
    {"date": "2025-09-08", "name": "Ntra. Sra. de los Remedios (Patrona de Alcorcón)", "scope": "Local Alcorcón"},
    {"date": "2025-10-12", "name": "Fiesta Nacional de España", "scope": "Nacional"},
    {"date": "2025-11-01", "name": "Todos los Santos", "scope": "Nacional"},
    {"date": "2025-12-06", "name": "Día de la Constitución Española", "scope": "Nacional"},
    {"date": "2025-12-08", "name": "La Inmaculada Concepción", "scope": "Nacional"},
    {"date": "2025-12-25", "name": "Natividad del Señor / Navidad", "scope": "Nacional"},

    # --- 2026 (OFICIAL) ---
    {"date": "2026-01-01", "name": "Año Nuevo", "scope": "Nacional"},
    {"date": "2026-01-06", "name": "Epifanía del Señor / Reyes Magos", "scope": "Nacional"},
    {"date": "2026-04-02", "name": "Jueves Santo", "scope": "Comunidad de Madrid"},
    {"date": "2026-04-03", "name": "Viernes Santo", "scope": "Nacional"},
    {"date": "2026-04-06", "name": "San Dominguín / Santo Domingo (Alcorcón)", "scope": "Local Alcorcón"},
    {"date": "2026-05-01", "name": "Fiesta del Trabajo", "scope": "Nacional"},
    {"date": "2026-05-02", "name": "Fiesta de la Comunidad de Madrid", "scope": "Comunidad de Madrid"},
    {"date": "2026-08-15", "name": "Asunción de la Virgen", "scope": "Nacional"},
    {"date": "2026-09-08", "name": "Ntra. Sra. de los Remedios (Patrona de Alcorcón)", "scope": "Local Alcorcón"},
    {"date": "2026-10-12", "name": "Fiesta Nacional de España", "scope": "Nacional"},
    {"date": "2026-11-02", "name": "Traslado Todos los Santos", "scope": "Nacional"},
    {"date": "2026-12-07", "name": "Traslado Día de la Constitución", "scope": "Nacional"},
    {"date": "2026-12-08", "name": "La Inmaculada Concepción", "scope": "Nacional"},
    {"date": "2026-12-25", "name": "Natividad del Señor / Navidad", "scope": "Nacional"},

    # --- 2027 (PREVISIÓN) ---
    {"date": "2027-01-01", "name": "Año Nuevo", "scope": "Nacional"},
    {"date": "2027-01-06", "name": "Epifanía del Señor / Reyes Magos", "scope": "Nacional"},
    {"date": "2027-03-25", "name": "Jueves Santo", "scope": "Comunidad de Madrid"},
    {"date": "2027-03-26", "name": "Viernes Santo", "scope": "Nacional"},
    {"date": "2027-03-29", "name": "San Dominguín / Fiestas de Alcorcón", "scope": "Local Alcorcón"},
    {"date": "2027-05-01", "name": "Fiesta del Trabajo", "scope": "Nacional"},
    {"date": "2027-05-02", "name": "Fiesta de la Comunidad de Madrid", "scope": "Comunidad de Madrid"},
    {"date": "2027-08-15", "name": "Asunción de la Virgen", "scope": "Nacional"},
    {"date": "2027-09-08", "name": "Ntra. Sra. de los Remedios (Patrona de Alcorcón)", "scope": "Local Alcorcón"},
    {"date": "2027-10-12", "name": "Fiesta Nacional de España", "scope": "Nacional"},
    {"date": "2027-11-01", "name": "Todos los Santos", "scope": "Nacional"},
    {"date": "2027-12-06", "name": "Día de la Constitución Española", "scope": "Nacional"},
    {"date": "2027-12-08", "name": "La Inmaculada Concepción", "scope": "Nacional"},
    {"date": "2027-12-25", "name": "Natividad del Señor / Navidad", "scope": "Nacional"},
]

def get_db():
    current_db = os.environ.get("DB_PATH", DB_PATH)
    conn = sqlite3.connect(current_db)
    conn.row_factory = sqlite3.Row
    return conn

def init_holidays_table():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS holidays (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        scope TEXT NOT NULL,
        is_closed INTEGER DEFAULT 1,
        color TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("PRAGMA table_info(holidays)")
    cols = [r[1] for r in cursor.fetchall()]
    if "color" not in cols:
        cursor.execute("ALTER TABLE holidays ADD COLUMN color TEXT")

    for h in OFFICIAL_HOLIDAYS:
        cursor.execute("""
        INSERT OR IGNORE INTO holidays (date, name, scope, is_closed)
        VALUES (?, ?, ?, 1)
        """, (h["date"], h["name"], h["scope"]))

    conn.commit()
    conn.close()

def get_holiday_colors(scope: str = "", name: str = "", custom_color: Optional[str] = None) -> Dict[str, str]:
    """
    Paleta cromática diferenciada por concepto según directrices de Román:
    - Festivos (Oficiales, Locales, Fiestas): ROJO (#DC2626 / #EF4444)
    - Congresos / Jornadas Científicas: PÚRPURA / MORADO (#8B5CF6 / #7C3AED)
    - Vacaciones: NARANJA / ÁMBAR (#F59E0B / #D97706)
    - Formación / Máster: AZUL ÍNDIGO (#3B82F6 / #2563EB)
    - Asuntos Propios / Personal: VERDE TEAL (#14B8A6 / #0D9488)
    - Cierre Clínica / Mantenimiento: GRIS PIZARRA (#64748B / #475569)
    - Personalizado (en blanco): BLANCO (#FFFFFF con borde #475569) o color libre elegido
    """
    s = (scope or "").lower()
    n = (name or "").lower()

    if custom_color and custom_color.strip():
        c = custom_color.strip()
        is_white = c.upper() in ("#FFF", "#FFFFFF", "WHITE")
        return {
            "bg": "#FFFFFF" if is_white else c,
            "border": "#64748B" if is_white else c,
            "text": "#0F172A" if is_white else "#FFFFFF",
            "badge_bg": "#F8FAFC" if is_white else f"{c}20",
            "badge_color": "#334155" if is_white else c,
            "concept": "Personalizado",
            "icon": "⚪" if is_white else "🎨"
        }

    # 1. Congresos
    if "congreso" in s or "congreso" in n or "jornada" in n or "ponencia" in n or "simposio" in n:
        return {
            "bg": "#EDE9FE", "border": "#8B5CF6", "text": "#5B21B6",
            "badge_bg": "#EDE9FE", "badge_color": "#7C3AED",
            "concept": "Congreso", "icon": "🏛️"
        }
    # 2. Vacaciones
    elif "vacacion" in s or "vacacion" in n or "verano" in n:
        return {
            "bg": "#FEF3C7", "border": "#F59E0B", "text": "#92400E",
            "badge_bg": "#FEF3C7", "badge_color": "#D97706",
            "concept": "Vacaciones", "icon": "🏖️"
        }
    # 3. Formación / Docencia / Máster
    elif "formaci" in s or "formaci" in n or "master" in n or "máster" in n or "curso" in n or "docencia" in n:
        return {
            "bg": "#DBEAFE", "border": "#3B82F6", "text": "#1E40AF",
            "badge_bg": "#DBEAFE", "badge_color": "#2563EB",
            "concept": "Formación", "icon": "🎓"
        }
    # 4. Asuntos Propios
    elif "asunto" in s or "asunto" in n or "propio" in n or "personal" in n:
        return {
            "bg": "#CCFBF1", "border": "#14B8A6", "text": "#115E59",
            "badge_bg": "#CCFBF1", "badge_color": "#0D9488",
            "concept": "Asuntos Propios", "icon": "🚗"
        }
    # 5. Cierre / Mantenimiento
    elif "cierre" in s or "mantenimiento" in n or "reforma" in n:
        return {
            "bg": "#F1F5F9", "border": "#94A3B8", "text": "#334155",
            "badge_bg": "#F1F5F9", "badge_color": "#475569",
            "concept": "Cierre Clínica", "icon": "🔧"
        }
    # 6. Personalizado (en blanco)
    elif "personalizado" in s or "blanco" in s or "en blanco" in s or "otro" in s:
        return {
            "bg": "#FFFFFF", "border": "#64748B", "text": "#0F172A",
            "badge_bg": "#FFFFFF", "badge_color": "#334155",
            "concept": "Personalizado", "icon": "⚪"
        }
    # 7. Festivos Oficiales / Fiestas (ROJO siempre)
    else:
        return {
            "bg": "#FEE2E2", "border": "#EF4444", "text": "#991B1B",
            "badge_bg": "#FEE2E2", "badge_color": "#DC2626",
            "concept": "Festivo", "icon": "🔴"
        }

def is_holiday(date_str: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Comprueba si una fecha es festivo cerrado.
    Retorna (True, holiday_dict) o (False, None).
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT date, name, scope, is_closed FROM holidays WHERE date = ? AND is_closed = 1", (date_str,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return True, dict(row)
    return False, None

def get_holidays_list(start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT id, date, name, scope, is_closed, color FROM holidays"
    params = []
    if start_date and end_date:
        query += " WHERE date >= ? AND date <= ?"
        params = [start_date, end_date]
    query += " ORDER BY date ASC"
    cursor.execute(query, params)
    raw_rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    result = []
    for r in raw_rows:
        colors = get_holiday_colors(r.get("scope", ""), r.get("name", ""), r.get("color"))
        r["colors"] = colors
        result.append(r)
    return result

def add_custom_holiday(date_str: str, name: str, scope: str = "Bloqueo Clínica", is_closed: int = 1, color: Optional[str] = None) -> bool:
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO holidays (date, name, scope, is_closed, color)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET 
            name = excluded.name, 
            scope = excluded.scope, 
            is_closed = excluded.is_closed,
            color = excluded.color
        """, (date_str, name, scope, is_closed, color))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding holiday: {e}")
        conn.close()
        return False

def remove_holiday(holiday_id: int) -> bool:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM holidays WHERE id = ?", (holiday_id,))
    conn.commit()
    conn.close()
    return True
