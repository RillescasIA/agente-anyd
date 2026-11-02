# -*- coding: utf-8 -*-
"""
schedule_manager.py
Gestor de Horarios y Franjas Ofertadas para Reservas Web · ANyD Nutricionistas
Permite a Román Illescas configurar qué días y en qué franjas de 30 minutos
los pacientes pueden reservar consultas a través de la web (reservar.html).
"""

import os
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "anyd_booking.db")

DAY_NAMES = [
    "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"
]

# Todas las franjas de 30 min posibles en jornada clínica (08:00 a 21:30)
ALL_CLINICAL_SLOTS = [
    f"{h:02d}:{m:02d}"
    for h in range(8, 22)
    for m in (0, 30)
]

# Horario por defecto estándar ANyD
DEFAULT_WEEKDAY_SLOTS = [
    "10:00", "10:30", "11:00", "11:30", "12:00", "12:30", "13:00", "13:30",
    "16:00", "16:30", "17:00", "17:30", "18:00", "18:30", "19:00", "19:30", "20:00"
]

def get_db():
    current_db = os.environ.get("DB_PATH", DEFAULT_DB_PATH)
    conn = sqlite3.connect(current_db)
    conn.row_factory = sqlite3.Row
    return conn

def init_schedule_table():
    """Inicializa la tabla de horarios y franjas ofertadas si no existe."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS booking_schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        day_of_week INTEGER,
        specific_date TEXT,
        is_enabled INTEGER DEFAULT 1,
        slots_json TEXT NOT NULL,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sched_dow ON booking_schedules(day_of_week) WHERE day_of_week IS NOT NULL")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sched_date ON booking_schedules(specific_date) WHERE specific_date IS NOT NULL")

    # Poblar horario semanal por defecto si está vacía
    cursor.execute("SELECT COUNT(*) as cnt FROM booking_schedules WHERE day_of_week IS NOT NULL")
    count = cursor.fetchone()["cnt"]
    if count == 0:
        for dow in range(7):
            is_enabled = 1 if dow < 5 else 0
            slots = DEFAULT_WEEKDAY_SLOTS if is_enabled else []
            cursor.execute("""
            INSERT INTO booking_schedules (day_of_week, is_enabled, slots_json)
            VALUES (?, ?, ?)
            """, (dow, is_enabled, json.dumps(slots)))

    conn.commit()
    conn.close()

def get_weekly_schedule() -> List[Dict[str, Any]]:
    """Devuelve la configuración semanal (Lunes a Domingo) de franjas ofertadas."""
    init_schedule_table()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT day_of_week, is_enabled, slots_json, notes
    FROM booking_schedules
    WHERE day_of_week IS NOT NULL
    ORDER BY day_of_week ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    result = []
    by_dow = {r["day_of_week"]: r for r in rows}

    for dow in range(7):
        if dow in by_dow:
            r = by_dow[dow]
            try:
                slots = json.loads(r["slots_json"])
            except:
                slots = DEFAULT_WEEKDAY_SLOTS if dow < 5 else []
            result.append({
                "day_of_week": dow,
                "day_name": DAY_NAMES[dow],
                "is_enabled": bool(r["is_enabled"]),
                "slots": slots,
                "slots_count": len(slots),
                "notes": r["notes"] or ""
            })
        else:
            is_en = dow < 5
            slots = DEFAULT_WEEKDAY_SLOTS if is_en else []
            result.append({
                "day_of_week": dow,
                "day_name": DAY_NAMES[dow],
                "is_enabled": is_en,
                "slots": slots,
                "slots_count": len(slots),
                "notes": ""
            })
    return result

def save_weekly_schedule(days_config: List[Dict[str, Any]]) -> bool:
    """
    Guarda la configuración semanal completa.
    days_config: list of { "day_of_week": int, "is_enabled": bool, "slots": list[str] }
    """
    init_schedule_table()
    conn = get_db()
    cursor = conn.cursor()
    now_iso = datetime.now().isoformat()

    try:
        for item in days_config:
            dow = int(item["day_of_week"])
            is_enabled = 1 if item.get("is_enabled", True) else 0
            slots = item.get("slots", [])
            # Filtrar y ordenar slots válidos
            clean_slots = sorted(list(set(s for s in slots if s in ALL_CLINICAL_SLOTS)))
            slots_json = json.dumps(clean_slots)
            notes = item.get("notes", "")

            cursor.execute("""
            INSERT INTO booking_schedules (day_of_week, is_enabled, slots_json, notes, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(day_of_week) DO UPDATE SET
                is_enabled = excluded.is_enabled,
                slots_json = excluded.slots_json,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """, (dow, is_enabled, slots_json, notes, now_iso))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving weekly schedule: {e}")
        conn.close()
        return False

def get_specific_date_schedules() -> List[Dict[str, Any]]:
    """Devuelve las excepciones de fechas específicas configuradas."""
    init_schedule_table()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, specific_date, is_enabled, slots_json, notes, updated_at
    FROM booking_schedules
    WHERE specific_date IS NOT NULL
    ORDER BY specific_date ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        try:
            slots = json.loads(r["slots_json"])
        except:
            slots = []
        result.append({
            "id": r["id"],
            "date": r["specific_date"],
            "is_enabled": bool(r["is_enabled"]),
            "slots": slots,
            "slots_count": len(slots),
            "notes": r["notes"] or "",
            "updated_at": r["updated_at"]
        })
    return result

def save_date_schedule(date_str: str, is_enabled: bool, slots: List[str], notes: str = "") -> bool:
    """Configura las franjas ofertadas para una fecha concreta (YYYY-MM-DD)."""
    init_schedule_table()
    conn = get_db()
    cursor = conn.cursor()
    now_iso = datetime.now().isoformat()
    clean_date = date_str[:10]

    try:
        clean_slots = sorted(list(set(s for s in slots if s in ALL_CLINICAL_SLOTS))) if is_enabled else []
        slots_json = json.dumps(clean_slots)
        en_int = 1 if is_enabled else 0

        cursor.execute("""
        INSERT INTO booking_schedules (specific_date, is_enabled, slots_json, notes, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(specific_date) DO UPDATE SET
            is_enabled = excluded.is_enabled,
            slots_json = excluded.slots_json,
            notes = excluded.notes,
            updated_at = excluded.updated_at
        """, (clean_date, en_int, slots_json, notes, now_iso))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving date schedule for {date_str}: {e}")
        conn.close()
        return False

def delete_date_schedule(date_str: str) -> bool:
    """Elimina la excepción de fecha específica y regresa al horario semanal habitual."""
    init_schedule_table()
    conn = get_db()
    cursor = conn.cursor()
    clean_date = date_str[:10]
    try:
        cursor.execute("DELETE FROM booking_schedules WHERE specific_date = ?", (clean_date,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error deleting date schedule for {date_str}: {e}")
        conn.close()
        return False

def get_offered_slots_for_date(date_str: str) -> Dict[str, Any]:
    """
    Determina qué franjas de 30 minutos se ofertan para una fecha específica (YYYY-MM-DD).
    Prioridad:
    1. Regla específica para 'date_str' si existe.
    2. Horario semanal para el día de la semana correspondiente.
    """
    clean_date = date_str[:10]
    try:
        dt = datetime.strptime(clean_date, "%Y-%m-%d")
        dow = dt.weekday()
        day_name = DAY_NAMES[dow]
    except Exception as e:
        return {"slots": [], "is_open": False, "message": "Fecha inválida", "source": "error"}

    init_schedule_table()
    conn = get_db()
    cursor = conn.cursor()

    # 1. Comprobar excepción específica para esta fecha
    cursor.execute("""
    SELECT is_enabled, slots_json, notes FROM booking_schedules
    WHERE specific_date = ?
    """, (clean_date,))
    row_spec = cursor.fetchone()

    if row_spec:
        conn.close()
        is_open = bool(row_spec["is_enabled"])
        try:
            slots = json.loads(row_spec["slots_json"]) if is_open else []
        except:
            slots = []
        return {
            "date": clean_date,
            "day_name": day_name,
            "is_open": is_open,
            "slots": slots,
            "source": "specific_date",
            "notes": row_spec["notes"] or "Horario especial ofertado para esta fecha"
        }

    # 2. Comprobar horario semanal habitual
    cursor.execute("""
    SELECT is_enabled, slots_json, notes FROM booking_schedules
    WHERE day_of_week = ?
    """, (dow,))
    row_dow = cursor.fetchone()
    conn.close()

    if row_dow:
        is_open = bool(row_dow["is_enabled"])
        try:
            slots = json.loads(row_dow["slots_json"]) if is_open else []
        except:
            slots = DEFAULT_WEEKDAY_SLOTS if dow < 5 else []
        return {
            "date": clean_date,
            "day_name": day_name,
            "is_open": is_open,
            "slots": slots,
            "source": "weekly",
            "notes": row_dow["notes"] or ""
        }

    # 3. Fallback por defecto si no hay registro
    is_open = dow < 5
    slots = DEFAULT_WEEKDAY_SLOTS if is_open else []
    return {
        "date": clean_date,
        "day_name": day_name,
        "is_open": is_open,
        "slots": slots,
        "source": "default",
        "notes": ""
    }
