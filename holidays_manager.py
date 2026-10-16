import sqlite3
import os
from typing import Dict, Any, List, Optional, Tuple

DB_PATH = r"g:\Mi unidad\1.- IA\IA Gemini\Agente anyd\anyd_booking.db"

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
    conn = sqlite3.connect(DB_PATH)
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
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    for h in OFFICIAL_HOLIDAYS:
        cursor.execute("""
        INSERT OR IGNORE INTO holidays (date, name, scope, is_closed)
        VALUES (?, ?, ?, 1)
        """, (h["date"], h["name"], h["scope"]))

    conn.commit()
    conn.close()

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
    query = "SELECT id, date, name, scope, is_closed FROM holidays"
    params = []
    if start_date and end_date:
        query += " WHERE date >= ? AND date <= ?"
        params = [start_date, end_date]
    query += " ORDER BY date ASC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def add_custom_holiday(date_str: str, name: str, scope: str = "Clínica Cerrada", is_closed: int = 1) -> bool:
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO holidays (date, name, scope, is_closed)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET name = excluded.name, scope = excluded.scope, is_closed = excluded.is_closed
        """, (date_str, name, scope, is_closed))
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
