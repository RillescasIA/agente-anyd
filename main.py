import sqlite3
import os
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, HTTPException, Body, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

import excel_manager
import email_service
import scheduler
import tanita_receiver
import drive_manager
import ai_copilot
import holidays_manager
import sync_excel
import sync_reservio_feed
import diet_manager
import clinical_manager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "anyd_booking.db"))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

app = FastAPI(title="ANyD Booking & Bono Manager")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        firstname TEXT,
        lastname TEXT,
        fullname TEXT,
        email TEXT UNIQUE COLLATE NOCASE,
        phone TEXT,
        address TEXT,
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bonos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT UNIQUE,
        client_id INTEGER,
        client_name TEXT,
        client_email TEXT,
        tipo_bono TEXT,
        total_sessions INTEGER,
        used_sessions INTEGER DEFAULT 0,
        purchase_date TEXT,
        price REAL,
        status TEXT DEFAULT 'Activo',
        centro TEXT DEFAULT 'ANYD',
        forma_pago TEXT,
        nutri TEXT DEFAULT 'Román',
        FOREIGN KEY (client_id) REFERENCES clients (id)
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bono_id INTEGER,
        client_id INTEGER,
        client_name TEXT,
        client_email TEXT,
        client_phone TEXT,
        appointment_date TEXT,
        appointment_time TEXT,
        duration_minutes INTEGER DEFAULT 30,
        service TEXT DEFAULT 'Anyd Nutrición Deportiva',
        modality TEXT DEFAULT 'Presencial',
        status TEXT DEFAULT 'Agendada',
        reminder_sent INTEGER DEFAULT 0,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (bono_id) REFERENCES bonos (id),
        FOREIGN KEY (client_id) REFERENCES clients (id)
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tanita_measurements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        client_name TEXT,
        appointment_id INTEGER,
        measurement_date TEXT,
        weight REAL,
        bmi REAL,
        fat_percent REAL,
        fat_mass REAL,
        muscle_mass REAL,
        ffm REAL,
        water_percent REAL,
        bone_mass REAL,
        visceral_fat REAL,
        bmr_tanita REAL,
        bmr_cunningham REAL,
        metabolic_age INTEGER,
        physical_rating INTEGER,
        segmental_data TEXT,
        raw_data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (client_id) REFERENCES clients (id)
    )""")
    conn.commit()
    conn.close()

init_db()

def auto_seed_if_empty():
    """
    Si el servidor arranca con la base de datos vacía (ej. en Render con disco efímero),
    descarga e importa automáticamente todas las citas desde Reservio y las recetas de Dietowin.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM appointments")
        count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='diet_recipes'")
        has_diet_table = cursor.fetchone()[0]
        diet_count = 0
        if has_diet_table:
            cursor.execute("SELECT COUNT(*) FROM diet_recipes")
            diet_count = cursor.fetchone()[0]
        conn.close()

        if count == 0:
            print("[AUTO-SYNC] Base de datos vacía detectada al inicio. Sincronizando con Reservio...")
            sync_reservio_feed.run_reservio_sync()

        if diet_count == 0:
            print("[AUTO-SYNC] Importando recetas y alimentos de Dietowin...")
            import import_dietowin_data
            import_dietowin_data.import_dietowin_to_db()
    except Exception as e:
        print(f"[AUTO-SYNC ERROR] Error en auto-sincronización inicial: {e}")

auto_seed_if_empty()

# Inicializar tabla oficial de festivos Nacionales, Madrid y Alcorcón
holidays_manager.init_holidays_table()
clinical_manager.init_clinical_tables()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

class BookingRequest(BaseModel):
    bono_id: int
    client_id: Optional[int] = None
    client_name: str
    client_email: str
    date: str
    time: str
    duration_minutes: Optional[int] = 30
    modality: str = "Presencial"

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/dashboard/stats")
def api_dashboard_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM clients")
    total_clients = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM diet_recipes")
    total_recipes = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM diet_foods")
    total_foods = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM diet_plans")
    total_plans = c.fetchone()[0]

    today_str = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT COUNT(*) FROM appointments WHERE appointment_date = ?", (today_str,))
    today_appointments = c.fetchone()[0]
    conn.close()

    tanita_status = {
        "connected": tanita_receiver.tanita_instance.is_listening,
        "active_port": tanita_receiver.tanita_instance.active_port,
        "latest_measurement": tanita_receiver.tanita_instance.latest_measurement
    }

    return {
        "clients_count": total_clients,
        "recipes_count": total_recipes,
        "foods_count": total_foods,
        "plans_count": total_plans,
        "today_appointments_count": today_appointments,
        "tanita": tanita_status
    }

@app.get("/reservar", response_class=HTMLResponse)
def page_reservar(request: Request):
    return templates.TemplateResponse(request=request, name="reservar.html")

class ManualBookingRequest(BaseModel):
    client_name: str
    client_email: Optional[str] = ""
    client_phone: Optional[str] = ""
    date: str
    time: str
    duration_minutes: Optional[int] = 30
    service: Optional[str] = "Anyd Nutrición Deportiva"
    modality: str = "Presencial"
    notes: Optional[str] = ""
    bono_id: Optional[int] = None

class RescheduleRequest(BaseModel):
    id: int
    date: str
    time: str
    duration_minutes: Optional[int] = 30
    service: Optional[str] = None
    modality: Optional[str] = None
    notes: Optional[str] = None

class ActionAppointmentRequest(BaseModel):
    id: int
    notes: Optional[str] = None

@app.get("/admin", response_class=HTMLResponse)
def page_admin(
    request: Request,
    tab: str = "today",
    q: Optional[str] = None,
    page: int = 1
):
    conn = get_db()
    cursor = conn.cursor()

    today_str = datetime.now().strftime("%Y-%m-%d")

    # Estadísticas para los contadores
    cursor.execute("SELECT COUNT(*) FROM clients")
    total_clients = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM bonos WHERE status = 'Activo' AND used_sessions < total_sessions")
    active_bonos_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM appointments WHERE appointment_date = ?", (today_str,))
    today_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM appointments WHERE appointment_date > ?", (today_str,))
    future_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM appointments WHERE appointment_date < ?", (today_str,))
    past_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM appointments")
    all_count = cursor.fetchone()[0]

    # Construcción de la consulta según la pestaña seleccionada (pasado, presente, futuro)
    query_parts = ["SELECT id, bono_id, client_name, client_email, client_phone, appointment_date, appointment_time, modality, status, reminder_sent, notes FROM appointments WHERE 1=1"]
    params = []

    if tab == "today":
        query_parts.append("AND appointment_date = ?")
        params.append(today_str)
        order_clause = "ORDER BY appointment_time ASC"
        limit_clause = ""
    elif tab == "future":
        query_parts.append("AND appointment_date > ?")
        params.append(today_str)
        order_clause = "ORDER BY appointment_date ASC, appointment_time ASC"
        limit_clause = ""
    elif tab == "past":
        query_parts.append("AND appointment_date < ?")
        params.append(today_str)
        order_clause = "ORDER BY appointment_date DESC, appointment_time DESC"
        limit_clause = "LIMIT 100"
    else:  # all
        order_clause = "ORDER BY appointment_date DESC, appointment_time DESC"
        limit_clause = "LIMIT 150"

    if q and q.strip():
        search_term = f"%{q.strip().lower()}%"
        query_parts.append("AND (LOWER(client_name) LIKE ? OR LOWER(client_email) LIKE ? OR client_phone LIKE ?)")
        params.extend([search_term, search_term, search_term])

    full_query = f"{' '.join(query_parts)} {order_clause} {limit_clause}"
    cursor.execute(full_query, params)
    appointments = cursor.fetchall()

    # Obtener lista de bonos activos con datos de contacto
    cursor.execute("""
    SELECT b.id, b.order_id, b.client_name, COALESCE(b.client_email, c.email, '') as client_email,
           COALESCE(c.phone, '') as client_phone, b.tipo_bono, b.purchase_date, b.used_sessions,
           b.total_sessions, b.status
    FROM bonos b
    LEFT JOIN clients c ON b.client_id = c.id
    WHERE b.status = 'Activo'
    ORDER BY b.id DESC
    """)
    bonos = cursor.fetchall()

    # Obtener lista de clientes para el selector de cita manual
    cursor.execute("SELECT id, fullname, email, phone FROM clients WHERE fullname IS NOT NULL AND fullname != '' ORDER BY fullname ASC")
    clients_list = cursor.fetchall()

    conn.close()

    stats = {
        "total_clients": total_clients,
        "active_bonos": active_bonos_count,
        "today_count": today_count,
        "future_count": future_count,
        "past_count": past_count,
        "all_count": all_count,
        "today_str": today_str
    }

    return templates.TemplateResponse(request=request, name="admin.html", context={
        "stats": stats,
        "appointments": appointments,
        "bonos": bonos,
        "clients_list": clients_list,
        "current_tab": tab,
        "search_query": q or ""
    })

@app.get("/api/calendar/events")
def get_calendar_events(start: Optional[str] = None, end: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()

    query = "SELECT id, bono_id, client_id, client_name, client_email, client_phone, appointment_date, appointment_time, duration_minutes, modality, status, notes, service FROM appointments WHERE status != 'Cancelada'"
    params = []

    if start and end:
        start_date = start[:10]
        end_date = end[:10]
        query += " AND appointment_date >= ? AND appointment_date <= ?"
        params.extend([start_date, end_date])

    cursor.execute(query, params)
    rows = cursor.fetchall()

    events = []
    for r in rows:
        time_str = r["appointment_time"] or "10:00"
        if len(time_str) >= 5 and ":" in time_str:
            parts = time_str.split(":")
            hh = int(parts[0])
            mm = int(parts[1][:2])
        else:
            hh, mm = 10, 0

        duration = r["duration_minutes"] if ("duration_minutes" in r.keys() and r["duration_minutes"]) else 30
        try:
            start_dt = datetime.strptime(f"{r['appointment_date']} {hh:02d}:{mm:02d}", "%Y-%m-%d %H:%M")
            end_dt = start_dt + timedelta(minutes=duration)
            start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:00")
            end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:00")
        except:
            start_iso = f"{r['appointment_date']}T{hh:02d}:{mm:02d}:00"
            end_iso = f"{r['appointment_date']}T{hh:02d}:{(mm+duration)%60:02d}:00"

        service_title = r["service"] if ("service" in r.keys() and r["service"]) else "Anyd Nutrición Deportiva"
        modality = r["modality"] or "Presencial"
        notes = (r["notes"] or "").lower()

        # Asignar color y servicio igual que Reservio
        bg_color = "#DBEAFE"  # Azul pastel Reservio
        border_color = "#93C5FD"
        text_color = "#1E40AF"

        s_lower = service_title.lower()
        if "catedral" in s_lower:
            service_title = "CF Catedral Nutrición"
            bg_color = "#E9D5FF"  # Lila
            border_color = "#C084FC"
            text_color = "#6B21A8"
        elif "clínica" in s_lower or "clinica" in s_lower:
            service_title = "Anyd Nutrición Clínica"
            bg_color = "#CCFBF1"  # Turquesa
            border_color = "#5EEAD4"
            text_color = "#115E59"
        elif "tracius" in s_lower:
            service_title = "Tracius Nutrición Deportiva"
            bg_color = "#E0E7FF"  # Azul pizarra
            border_color = "#A5B4FC"
            text_color = "#3730A3"
        elif "informativa" in s_lower:
            service_title = "Sesión informativa"
            bg_color = "#F1F5F9"  # Gris neutro
            border_color = "#CBD5E1"
            text_color = "#475569"
        elif "online" in s_lower or ("online" in modality.lower() and "deportiva" not in s_lower):
            service_title = "Anyd Consulta OnLine"
            bg_color = "#FEF08A"  # Amarillo/Lima Reservio
            border_color = "#FACC15"
            text_color = "#854D0E"
        else:
            service_title = "Anyd Nutrición Deportiva"
            bg_color = "#DBEAFE"  # Azul pastel Reservio
            border_color = "#93C5FD"
            text_color = "#1E40AF"

        events.append({
            "id": r["id"],
            "title": r["client_name"],
            "start": start_iso,
            "end": end_iso,
            "backgroundColor": bg_color,
            "borderColor": border_color,
            "textColor": text_color,
            "extendedProps": {
                "client_name": r["client_name"],
                "email": r["client_email"] or "",
                "phone": r["client_phone"] or "",
                "service": service_title,
                "modality": modality,
                "status": r["status"],
                "notes": r["notes"] or "",
                "bono_id": r["bono_id"],
                "date": r["appointment_date"],
                "time": f"{hh:02d}:{mm:02d}",
                "duration_minutes": duration
            }
        })

    conn.close()

    # Inyectar festivos cerrados oficiales de Alcorcón, Comunidad de Madrid y Nacionales
    try:
        start_d = start[:10] if start else None
        end_d = end[:10] if end else None
        holidays = holidays_manager.get_holidays_list(start_d, end_d)
        for h in holidays:
            if h.get("is_closed", 1):
                h_date = h["date"]
                events.append({
                    "id": f"holiday_{h['id']}",
                    "title": f"⛔ CERRADO: {h['name']}",
                    "start": f"{h_date}T09:00:00",
                    "end": f"{h_date}T21:00:00",
                    "backgroundColor": "#FEE2E2",
                    "borderColor": "#F87171",
                    "textColor": "#991B1B",
                    "editable": False,
                    "startEditable": False,
                    "durationEditable": False,
                    "extendedProps": {
                        "client_name": f"⛔ CERRADO: {h['name']}",
                        "service": f"Festivo {h['scope']}",
                        "duration_minutes": 720,
                        "is_holiday": True,
                        "holiday_name": h["name"],
                        "scope": h["scope"],
                        "notes": f"Clínica ANyD cerrada por festividad oficial ({h['scope']}). Bloqueado para reservas."
                    }
                })
    except Exception as e:
        print(f"Error cargando festivos en calendario: {e}")

    return events

@app.get("/calendar.ics")
@app.get("/calendar/sync.ics")
@app.get("/api/calendar/export.ics")
def export_calendar_ics():
    """
    Feed oficial iCalendar (.ics) para sincronización automática con Google Calendar en el móvil de Román.
    Sustituye por completo al feed de Reservio con coste 0€.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, client_name, client_email, client_phone, appointment_date, appointment_time, duration_minutes, modality, notes, service
    FROM appointments
    WHERE status != 'Cancelada' AND appointment_date >= date('now', '-30 days')
    ORDER BY appointment_date ASC, appointment_time ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ANyD Nutricionistas//Sistema de Reservas//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Citas ANyD Nutricionistas",
        "X-WR-TIMEZONE:Europe/Madrid",
        "BEGIN:VTIMEZONE",
        "TZID:Europe/Madrid",
        "X-LIC-LOCATION:Europe/Madrid",
        "BEGIN:DAYLIGHT",
        "TZOFFSETFROM:+0100",
        "TZOFFSETTO:+0200",
        "TZNAME:CEST",
        "DTSTART:19700329T020000",
        "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
        "END:DAYLIGHT",
        "BEGIN:STANDARD",
        "TZOFFSETFROM:+0200",
        "TZOFFSETTO:+0100",
        "TZNAME:CET",
        "DTSTART:19701025T030000",
        "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
        "END:STANDARD",
        "END:VTIMEZONE"
    ]

    for r in rows:
        try:
            date_str = r["appointment_date"]
            time_str = r["appointment_time"] or "10:00"
            if len(time_str) >= 5 and ":" in time_str:
                parts = time_str.split(":")
                hh = int(parts[0])
                mm = int(parts[1][:2])
            else:
                hh, mm = 10, 0
            duration = r["duration_minutes"] if ("duration_minutes" in r.keys() and r["duration_minutes"]) else 30

            start_dt = datetime.strptime(f"{date_str} {hh:02d}:{mm:02d}", "%Y-%m-%d %H:%M")
            end_dt = start_dt + timedelta(minutes=duration)

            dt_stamp = datetime.now().strftime("%Y%m%dT%H%M%SZ")
            dt_start = start_dt.strftime("%Y%m%dT%H%M00")
            dt_end = end_dt.strftime("%Y%m%dT%H%M00")

            service_label = r["service"] if ("service" in r.keys() and r["service"]) else "Nutrición Deportiva"
            modality_label = r["modality"] or "Presencial"
            summary = f"{r['client_name']} - {service_label} ({modality_label})"
            location = "ANyD Nutricionistas (Alcorcón)" if modality_label.lower() == "presencial" else "Online / Videollamada"
            desc = f"Paciente: {r['client_name']}\\nServicio: {service_label}\\nModalidad: {modality_label}\\nTeléfono: {r['client_phone'] or 'N/A'}\\nEmail: {r['client_email'] or 'N/A'}\\nNotas: {r['notes'] or ''}"

            lines.append("BEGIN:VEVENT")
            lines.append(f"UID:anyd-appt-{r['id']}@anyd.es")
            lines.append(f"DTSTAMP:{dt_stamp}")
            lines.append(f"DTSTART;TZID=Europe/Madrid:{dt_start}")
            lines.append(f"DTEND;TZID=Europe/Madrid:{dt_end}")
            lines.append(f"SUMMARY:{summary}")
            lines.append(f"LOCATION:{location}")
            lines.append(f"DESCRIPTION:{desc}")
            lines.append("STATUS:CONFIRMED")
            lines.append("END:VEVENT")
        except:
            continue

    lines.append("END:VCALENDAR")
    ics_content = "\r\n".join(lines)
    return Response(content=ics_content, media_type="text/calendar; charset=utf-8", headers={
        "Content-Disposition": "attachment; filename=citas_anyd.ics",
        "Cache-Control": "no-cache, no-store, must-revalidate"
    })

@app.get("/api/client-history")
def get_client_history(name: Optional[str] = None, email: Optional[str] = None, client_id: Optional[int] = None):
    """
    Devuelve la ficha completa del deportista: datos de contacto, bonos activos/pasados,
    citas asistidas/pendientes y mediciones históricas de la Tanita MC-580.
    """
    conn = get_db()
    cursor = conn.cursor()

    client = None
    if client_id:
        cursor.execute("SELECT id, fullname, email, phone, note FROM clients WHERE id = ?", (client_id,))
        client = cursor.fetchone()
    elif email and email.strip():
        cursor.execute("SELECT id, fullname, email, phone, note FROM clients WHERE LOWER(email) = ?", (email.strip().lower(),))
        client = cursor.fetchone()
    elif name and name.strip():
        cursor.execute("SELECT id, fullname, email, phone, note FROM clients WHERE LOWER(fullname) LIKE ? ORDER BY id DESC LIMIT 1", (f"%{name.strip().lower()}%",))
        client = cursor.fetchone()

    client_name = client["fullname"] if client else (name or "")
    c_id = client["id"] if client else None

    # Bonos del deportista
    cursor.execute("""
    SELECT id, order_id, tipo_bono, purchase_date, total_sessions, used_sessions, status
    FROM bonos
    WHERE (client_id = ? OR LOWER(client_name) LIKE ?)
    ORDER BY id DESC
    """, (c_id, f"%{client_name.strip().lower()}%"))
    bonos = [dict(b) for b in cursor.fetchall()]

    # Citas del deportista
    cursor.execute("""
    SELECT id, appointment_date, appointment_time, duration_minutes, modality, status, notes
    FROM appointments
    WHERE (client_id = ? OR LOWER(client_name) LIKE ?)
    ORDER BY appointment_date DESC, appointment_time DESC
    LIMIT 50
    """, (c_id, f"%{client_name.strip().lower()}%"))
    appts = [dict(a) for a in cursor.fetchall()]

    # Histórico de pesajes Tanita MC-580
    cursor.execute("""
    SELECT id, measurement_date, weight, bmi, fat_percent, fat_mass, muscle_mass, ffm, water_percent, bone_mass, visceral_fat, bmr_cunningham, created_at
    FROM tanita_measurements
    WHERE (client_id = ? OR LOWER(client_name) LIKE ?)
    ORDER BY measurement_date DESC, id DESC
    LIMIT 20
    """, (c_id, f"%{client_name.strip().lower()}%"))
    tanita_records = [dict(t) for t in cursor.fetchall()]

    conn.close()

    return {
        "client": dict(client) if client else {"fullname": client_name, "email": "", "phone": "", "notes": ""},
        "bonos": bonos,
        "appointments": appts,
        "tanita": tanita_records
    }

@app.get("/api/client-details")
def get_client_details(name: str):
    """
    Endpoint de autocompletado rápido: busca un deportista por nombre
    y devuelve su email, teléfono, notas y su bono activo (nº de bono/pedido y sesiones).
    """
    conn = get_db()
    cursor = conn.cursor()

    name_clean = name.strip().lower()

    # Buscar cliente
    cursor.execute("""
    SELECT id, fullname, email, phone, note FROM clients
    WHERE LOWER(fullname) LIKE ? OR LOWER(fullname) = ?
    ORDER BY CASE WHEN LOWER(fullname) = ? THEN 1 ELSE 2 END, id DESC LIMIT 1
    """, (f"%{name_clean}%", name_clean, name_clean))
    client = cursor.fetchone()

    client_id = client["id"] if client else None
    client_name = client["fullname"] if client else name
    client_email = client["email"] if client and client["email"] else ""
    client_phone = client["phone"] if client and client["phone"] else ""
    client_note = client["note"] if client and client["note"] else ""

    # Buscar bono activo más reciente
    cursor.execute("""
    SELECT id, order_id, tipo_bono, total_sessions, used_sessions, status, purchase_date
    FROM bonos
    WHERE (client_id = ? OR LOWER(client_name) LIKE ?)
      AND status = 'Activo' AND used_sessions < total_sessions
    ORDER BY id DESC LIMIT 1
    """, (client_id, f"%{name_clean}%"))
    bono_row = cursor.fetchone()

    bono_info = None
    if bono_row:
        remaining = bono_row["total_sessions"] - bono_row["used_sessions"]
        bono_info = {
            "id": bono_row["id"],
            "order_id": bono_row["order_id"] or f"BONO-{bono_row['id']}",
            "tipo_bono": bono_row["tipo_bono"],
            "total_sessions": bono_row["total_sessions"],
            "used_sessions": bono_row["used_sessions"],
            "remaining_sessions": remaining,
            "status": bono_row["status"],
            "is_active": True
        }
    else:
        # Si no tiene activo, buscar el último bono histórico para avisar
        cursor.execute("""
        SELECT id, order_id, tipo_bono, total_sessions, used_sessions, status
        FROM bonos
        WHERE client_id = ? OR LOWER(client_name) LIKE ?
        ORDER BY id DESC LIMIT 1
        """, (client_id, f"%{name_clean}%"))
        last_bono = cursor.fetchone()
        if last_bono:
            bono_info = {
                "id": None,
                "order_id": last_bono["order_id"],
                "tipo_bono": last_bono["tipo_bono"],
                "total_sessions": last_bono["total_sessions"],
                "used_sessions": last_bono["used_sessions"],
                "remaining_sessions": 0,
                "status": last_bono["status"],
                "is_active": False,
                "is_exhausted": True
            }

    conn.close()

    return {
        "found": bool(client or bono_info),
        "id": client_id,
        "name": client_name,
        "email": client_email,
        "phone": client_phone,
        "note": client_note,
        "bono": bono_info
    }

@app.get("/api/check-client")
def check_client(email: str):
    email_clean = email.strip().lower()
    conn = get_db()
    cursor = conn.cursor()

    # Buscar bono activo por email
    cursor.execute("""
    SELECT id, client_id, client_name, client_email, tipo_bono, total_sessions, used_sessions
    FROM bonos
    WHERE LOWER(client_email) = ? AND status = 'Activo' AND used_sessions < total_sessions
    ORDER BY id DESC LIMIT 1
    """, (email_clean,))
    bono = cursor.fetchone()

    # Si no tiene bono asociado directamente al email, buscar cliente por email y ver sus bonos
    if not bono:
        cursor.execute("SELECT id, fullname FROM clients WHERE LOWER(email) = ?", (email_clean,))
        client = cursor.fetchone()
        if client:
            cursor.execute("""
            SELECT id, client_id, client_name, client_email, tipo_bono, total_sessions, used_sessions
            FROM bonos
            WHERE (client_id = ? OR LOWER(client_name) LIKE ?) AND status = 'Activo' AND used_sessions < total_sessions
            ORDER BY id DESC LIMIT 1
            """, (client["id"], f"%{client['fullname'].lower()}%"))
            bono = cursor.fetchone()

    conn.close()

    if not bono:
        return {"found": False, "has_active_bono": False}

    remaining = bono["total_sessions"] - bono["used_sessions"]
    return {
        "found": True,
        "has_active_bono": True,
        "bono_id": bono["id"],
        "client_id": bono["client_id"],
        "name": bono["client_name"],
        "email": email_clean,
        "tipo_bono": bono["tipo_bono"],
        "total_sessions": bono["total_sessions"],
        "used_sessions": bono["used_sessions"],
        "remaining_sessions": remaining
    }

@app.get("/api/available-slots")
def get_available_slots(date: str):
    """
    Calcula las franjas horarias disponibles para una fecha específica.
    Por defecto: turnos de mañana (10:00 - 13:30) y tarde (16:00 - 20:00) en intervalos de 30 minutos.
    Comprueba festivos de Alcorcón/Madrid/Nacionales y colisiones exactas.
    """
    # 1. Comprobar si la fecha es festivo oficial cerrado
    is_h, h_info = holidays_manager.is_holiday(date)
    if is_h:
        return {
            "slots": [],
            "closed": True,
            "is_holiday": True,
            "holiday_name": h_info["name"],
            "scope": h_info["scope"],
            "message": f"Clínica ANyD CERRADA por festividad ({h_info['scope']}): {h_info['name']}."
        }

    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
        # Si es fin de semana (sábado=5, domingo=6), no hay citas regulares
        if dt.weekday() >= 5:
            return {"slots": [], "closed": True, "message": "Fin de semana (clínica cerrada)."}
    except:
        return {"slots": [], "closed": True, "message": "Fecha inválida."}

    # Franjas de 30 minutos (duración estándar ANyD)
    all_slots = [
        "10:00", "10:30", "11:00", "11:30", "12:00", "12:30", "13:00", "13:30",
        "16:00", "16:30", "17:00", "17:30", "18:00", "18:30", "19:00", "19:30", "20:00"
    ]

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT appointment_time, duration_minutes FROM appointments
    WHERE appointment_date = ? AND status != 'Cancelada'
    """, (date,))
    booked_rows = cursor.fetchall()
    conn.close()

    # Comprobación de solapamiento dinámico
    available = []
    slot_duration = 30  # Duración por norma general (30 minutos)

    for slot_time in all_slots:
        try:
            slot_start = datetime.strptime(f"{date} {slot_time}", "%Y-%m-%d %H:%M")
            slot_end = slot_start + timedelta(minutes=slot_duration)
            overlap = False

            for b in booked_rows:
                b_time = b["appointment_time"] or "10:00"
                if len(b_time) >= 5 and ":" in b_time:
                    parts = b_time.split(":")
                    b_hh = int(parts[0])
                    b_mm = int(parts[1][:2])
                else:
                    b_hh, b_mm = 10, 0
                b_dur = b["duration_minutes"] if ("duration_minutes" in b.keys() and b["duration_minutes"]) else 30

                b_start = datetime.strptime(f"{date} {b_hh:02d}:{b_mm:02d}", "%Y-%m-%d %H:%M")
                b_end = b_start + timedelta(minutes=b_dur)

                # Hay colisión si los intervalos se solapan
                if max(slot_start, b_start) < min(slot_end, b_end):
                    overlap = True
                    break

            if not overlap:
                available.append(slot_time)
        except:
            continue

    return {"slots": available, "closed": False}

@app.post("/api/book-appointment")
def book_appointment(req: BookingRequest):
    # 1. Comprobar festivos cerrados
    is_h, h_info = holidays_manager.is_holiday(req.date)
    if is_h:
        return {
            "success": False,
            "message": f"No se pueden agendar consultas: La clínica ANyD permanece CERRADA por festividad ({h_info['scope']}: {h_info['name']})."
        }

    conn = get_db()
    cursor = conn.cursor()

    dur = req.duration_minutes or 30

    # Comprobar que no esté ocupada la hora
    cursor.execute("""
    SELECT id FROM appointments
    WHERE appointment_date = ? AND appointment_time = ? AND status = 'Agendada'
    """, (req.date, req.time))
    if cursor.fetchone():
        conn.close()
        return {"success": False, "message": "Esa franja horaria ya ha sido reservada. Por favor selecciona otra."}

    # Obtener teléfono y datos del cliente si existen
    cursor.execute("SELECT phone FROM clients WHERE id = ? OR LOWER(email) = ?", (req.client_id, req.client_email.lower()))
    client_row = cursor.fetchone()
    phone = client_row["phone"] if client_row and client_row["phone"] else ""

    # Insertar cita con duración de 30 min por defecto (o personalizada)
    cursor.execute("""
    INSERT INTO appointments (bono_id, client_id, client_name, client_email, client_phone, appointment_date, appointment_time, duration_minutes, modality, status, reminder_sent)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Agendada', 0)
    """, (req.bono_id, req.client_id, req.client_name, req.client_email, phone, req.date, req.time, dur, req.modality))
    
    # Obtener sesiones restantes del bono
    cursor.execute("SELECT total_sessions, used_sessions FROM bonos WHERE id = ?", (req.bono_id,))
    bono_row = cursor.fetchone()
    remaining = (bono_row["total_sessions"] - bono_row["used_sessions"]) if bono_row else None

    conn.commit()
    conn.close()

    # Enviar email de confirmación instantánea con duración de 30 min
    email_service.send_booking_confirmation(
        to_email=req.client_email,
        client_name=req.client_name,
        appointment_date=req.date,
        appointment_time=req.time,
        modality=req.modality,
        remaining_sessions=remaining,
        duration_minutes=dur
    )

    return {
        "success": True,
        "date": req.date,
        "time": req.time,
        "duration_minutes": dur,
        "modality": req.modality,
        "remaining_sessions": remaining
    }

@app.post("/api/complete-appointment")
def complete_appointment(id: int):
    """
    Marca la cita como asistida y sincroniza de inmediato con Excel ('Bonos activos_claude.xlsx').
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM appointments WHERE id = ?", (id,))
    appt = cursor.fetchone()
    if not appt:
        conn.close()
        return {"success": False, "message": "Cita no encontrada."}

    # Actualizar estado de la cita
    cursor.execute("UPDATE appointments SET status = 'Completada' WHERE id = ?", (id,))

    # Actualizar bono
    bono_id = appt["bono_id"]
    cursor.execute("SELECT * FROM bonos WHERE id = ?", (bono_id,))
    bono = cursor.fetchone()

    msg = ""
    if bono:
        new_used = bono["used_sessions"] + 1
        new_status = "Completado" if new_used >= bono["total_sessions"] else "Activo"
        cursor.execute("UPDATE bonos SET used_sessions = ?, status = ? WHERE id = ?", (new_used, new_status, bono_id))

        # Registrar en el Excel real 'G:\Mi unidad\1.- ANyD\Bonos activos_claude.xlsx'
        date_formatted = datetime.strptime(appt["appointment_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
        excel_res = excel_manager.record_consultation_in_excel(
            n_pedido=bono["order_id"],
            nombre=appt["client_name"],
            date_str=date_formatted,
            nutri="Román"
        )
        msg = f"Excel actualizado. Sesiones consumidas: {new_used}/{bono['total_sessions']}."

    conn.commit()
    conn.close()

    return {"success": True, "message": msg}
 
@app.post("/api/sync-excel")
def api_sync_excel():
    r"""
    Sincroniza en caliente la tabla de bonos desde G:\Mi unidad\1.- ANyD\Bonos activos_claude.xlsx.
    """
    try:
        count = sync_excel.sync_active_bonos()
        return {"success": True, "synced": count, "message": f"Sincronizados {count} bonos activos de 'Bonos activos_claude.xlsx'."}
    except FileNotFoundError as e:
        return {"success": False, "is_cloud": True, "message": str(e)}
    except Exception as e:
        return {"success": False, "is_cloud": False, "message": f"Error al sincronizar con Excel: {str(e)}"}

@app.post("/api/upload-excel")
async def api_upload_excel(file: UploadFile = File(...)):
    r"""
    Permite subir 'Bonos activos_claude.xlsx' directamente desde el navegador
    para sincronizar los bonos en Render sin necesidad de acceso físico a G:\.
    """
    try:
        import tempfile
        suffix = os.path.splitext(file.filename)[1] or ".xlsx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        count = sync_excel.sync_active_bonos(file_path=tmp_path)
        try:
            os.remove(tmp_path)
        except:
            pass
        return {"success": True, "synced": count, "message": f"¡Excel subido y sincronizado con éxito! {count} bonos activos actualizados."}
    except Exception as e:
        return {"success": False, "message": f"Error al procesar el archivo Excel: {str(e)}"}

@app.post("/api/sync-reservio")
def api_sync_reservio():
    """
    Sincroniza en caliente todas las reservas desde el feed oficial de Reservio.
    """
    try:
        res = sync_reservio_feed.run_reservio_sync()
        return {
            "success": True,
            "message": f"Sincronizadas {res['total']} citas de Reservio ({res['inserted']} nuevas, {res['updated']} actualizadas)."
        }
    except Exception as e:
        return {"success": False, "message": f"Error al sincronizar con Reservio: {str(e)}"}

@app.post("/api/manual-booking")
def manual_booking(req: ManualBookingRequest):
    conn = get_db()
    cursor = conn.cursor()

    # Buscar si el cliente tiene bono activo o usar el seleccionado
    bono_id = req.bono_id
    if not bono_id:
        cursor.execute("""
        SELECT id, total_sessions, used_sessions FROM bonos
        WHERE (LOWER(client_name) LIKE ? OR (client_email IS NOT NULL AND LOWER(client_email) = ?))
          AND status = 'Activo' AND used_sessions < total_sessions
        ORDER BY id DESC LIMIT 1
        """, (f"%{req.client_name.strip().lower()}%", req.client_email.strip().lower() if req.client_email else ""))
        bono = cursor.fetchone()
        bono_id = bono["id"] if bono else None

    # Buscar client_id o enriquecer ficha
    cursor.execute("SELECT id, email, phone FROM clients WHERE LOWER(fullname) LIKE ? OR (email IS NOT NULL AND email != '' AND LOWER(email) = ?) LIMIT 1",
                   (f"%{req.client_name.strip().lower()}%", req.client_email.strip().lower() if req.client_email else ""))
    client_row = cursor.fetchone()
    if client_row:
        client_id = client_row["id"]
        if req.client_phone and not client_row["phone"]:
            cursor.execute("UPDATE clients SET phone = ? WHERE id = ?", (req.client_phone, client_id))
        if req.client_email and not client_row["email"]:
            cursor.execute("UPDATE clients SET email = ? WHERE id = ?", (req.client_email, client_id))
    else:
        cursor.execute("INSERT INTO clients (fullname, email, phone) VALUES (?, ?, ?)",
                       (req.client_name, req.client_email or "", req.client_phone or ""))
        client_id = cursor.lastrowid

    dur = req.duration_minutes or 30

    serv = req.service or "Anyd Nutrición Deportiva"

    cursor.execute("""
    INSERT INTO appointments (bono_id, client_id, client_name, client_email, client_phone, appointment_date, appointment_time, duration_minutes, modality, status, reminder_sent, notes, service)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Agendada', 0, ?, ?)
    """, (bono_id, client_id, req.client_name, req.client_email, req.client_phone, req.date, req.time, dur, req.modality, req.notes, serv))

    conn.commit()
    conn.close()

    # Si tiene email, enviar confirmación
    if req.client_email:
        email_service.send_booking_confirmation(
            to_email=req.client_email,
            client_name=req.client_name,
            appointment_date=req.date,
            appointment_time=req.time,
            modality=req.modality,
            duration_minutes=dur
        )

    return {"success": True, "message": f"Cita para {req.client_name} agendada para el {req.date} a las {req.time} ({dur} min)."}

@app.post("/api/calendar/reschedule")
def reschedule_appointment(req: RescheduleRequest):
    conn = get_db()
    cursor = conn.cursor()
    dur = req.duration_minutes or 30

    if req.service is not None or req.modality is not None:
        cursor.execute("""
        UPDATE appointments
        SET appointment_date = ?, appointment_time = ?, duration_minutes = ?,
            service = COALESCE(?, service),
            modality = COALESCE(?, modality),
            notes = COALESCE(?, notes)
        WHERE id = ?
        """, (req.date, req.time, dur, req.service, req.modality, req.notes, req.id))
    else:
        cursor.execute("""
        UPDATE appointments
        SET appointment_date = ?, appointment_time = ?, duration_minutes = ?
        WHERE id = ?
        """, (req.date, req.time, dur, req.id))

    conn.commit()
    conn.close()
    return {"success": True, "message": f"Cita actualizada con éxito al {req.date} a las {req.time} ({dur} min)."}

class BulkDurationRequest(BaseModel):
    duration_minutes: int = 30
    only_future: bool = False

@app.post("/api/calendar/bulk-set-duration")
def bulk_set_duration(req: BulkDurationRequest):
    conn = get_db()
    cursor = conn.cursor()
    if req.only_future:
        cursor.execute("UPDATE appointments SET duration_minutes = ? WHERE appointment_date >= date('now')", (req.duration_minutes,))
    else:
        cursor.execute("UPDATE appointments SET duration_minutes = ?", (req.duration_minutes,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return {"success": True, "affected": affected, "duration_minutes": req.duration_minutes}

@app.post("/api/cancel-appointment")
def cancel_appointment(req: ActionAppointmentRequest):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE appointments SET status = 'Cancelada' WHERE id = ?", (req.id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Cita cancelada correctamente."}

@app.post("/api/update-notes")
def update_notes(req: ActionAppointmentRequest):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE appointments SET notes = ? WHERE id = ?", (req.notes, req.id))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Notas clínicas guardadas con éxito."}

@app.post("/api/run-reminders")
def run_reminders():
    sent = scheduler.run_reminder_check()
    return {"success": True, "sent": sent}

@app.post("/api/webhook/woocommerce")
async def woocommerce_webhook(request: Request):
    """
    Endpoint para recibir pedidos completados de WooCommerce desde anyd.es
    """
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Payload inválido")

    order_id = str(payload.get("id"))
    billing = payload.get("billing", {})
    first_name = billing.get("first_name", "")
    last_name = billing.get("last_name", "")
    full_name = f"{first_name} {last_name}".strip()
    email = billing.get("email", "").strip()
    phone = billing.get("phone", "").strip()
    total = payload.get("total", "0")
    payment_method = payload.get("payment_method_title", "Online")
    date_created = payload.get("date_created", datetime.now().strftime("%Y-%m-%d"))

    # Extraer tipo de bono del primer artículo
    line_items = payload.get("line_items", [])
    product_name = line_items[0].get("name", "Bono Consulta") if line_items else "Bono Consulta"

    # Determinar sesiones
    p_upper = product_name.upper()
    if "3" in p_upper:
        total_sessions = 3
    elif "5" in p_upper or "COMPET" in p_upper:
        total_sessions = 5
    elif "6" in p_upper:
        total_sessions = 6
    else:
        total_sessions = 3

    # 1. Registrar en Excel
    excel_manager.add_purchase_to_excel(
        centro="ANYD",
        nombre=full_name,
        tipo_bono=product_name,
        fecha_compra=date_created,
        n_pedido=order_id,
        importe=total,
        forma_pago=payment_method,
        nutri="Román",
        num_sesiones=total_sessions
    )

    # 2. Registrar en Base de Datos Local
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO clients (firstname, lastname, fullname, email, phone)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(email) DO UPDATE SET
        fullname = excluded.fullname,
        phone = COALESCE(NULLIF(excluded.phone, ''), clients.phone)
    """, (first_name, last_name, full_name, email, phone))

    cursor.execute("SELECT id FROM clients WHERE email = ?", (email,))
    client_id = cursor.fetchone()["id"]

    cursor.execute("""
    INSERT INTO bonos (order_id, client_id, client_name, client_email, tipo_bono, total_sessions, used_sessions, purchase_date, price, status, centro, forma_pago, nutri)
    VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, 'Activo', 'ANYD', ?, 'Román')
    ON CONFLICT(order_id) DO NOTHING
    """, (order_id, client_id, full_name, email, product_name, total_sessions, str(date_created)[:10], float(total), payment_method))

    conn.commit()
    conn.close()

    # 3. Enviar email de bienvenida con enlace para reservar
    email_service.send_purchase_confirmation(
        to_email=email,
        client_name=full_name,
        order_id=order_id,
        tipo_bono=product_name,
        sessions_count=total_sessions
    )

    return {"status": "ok", "order_id": order_id, "client": full_name}

# --- ENDPOINTS TANITA MC-580 ---

class TanitaConnectRequest(BaseModel):
    port: str
    baud_rate: int = 9600

class TanitaSaveRequest(BaseModel):
    client_name: str
    measurement: dict
    appointment_id: Optional[int] = None

@app.get("/tanita", response_class=HTMLResponse)
def page_tanita(request: Request):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, fullname, email, phone FROM clients WHERE fullname IS NOT NULL AND fullname != '' ORDER BY fullname ASC")
    clients_list = cursor.fetchall()
    conn.close()
    return templates.TemplateResponse(request=request, name="tanita.html", context={"clients_list": clients_list})

@app.get("/api/tanita/ports")
def get_tanita_ports():
    ports = tanita_receiver.tanita_instance.get_available_ports()
    return {"ports": ports}

@app.post("/api/tanita/connect")
def connect_tanita(req: TanitaConnectRequest):
    success = tanita_receiver.tanita_instance.connect(port_name=req.port, baud_rate=req.baud_rate)
    return {"success": success, "port": req.port}

@app.post("/api/tanita/disconnect")
def disconnect_tanita():
    tanita_receiver.tanita_instance.disconnect()
    return {"success": True}

@app.get("/api/tanita/live")
def get_tanita_live():
    return {
        "connected": tanita_receiver.tanita_instance.is_listening,
        "active_port": tanita_receiver.tanita_instance.active_port,
        "latest_measurement": tanita_receiver.tanita_instance.latest_measurement
    }

@app.post("/api/tanita/simulate")
def simulate_tanita():
    meas = tanita_receiver.tanita_instance.simulate_measurement()
    return {"success": True, "measurement": meas}

@app.post("/api/tanita/upload")
async def upload_tanita(file: UploadFile = File(...)):
    try:
        content_bytes = await file.read()
        content_str = content_bytes.decode("utf-8", errors="replace")
        meas = tanita_receiver.tanita_instance.parse_csv_file(content_str)
        if meas:
            return {"success": True, "measurement": meas}
        return {"success": False, "message": "No se encontraron datos biométricos válidos en el archivo."}
    except Exception as e:
        return {"success": False, "message": f"Error leyendo el archivo: {e}"}

@app.post("/api/tanita/save")
def save_tanita(req: TanitaSaveRequest):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM clients WHERE LOWER(fullname) LIKE ? LIMIT 1", (f"%{req.client_name.strip().lower()}%",))
    client_row = cursor.fetchone()
    client_id = client_row["id"] if client_row else None
    conn.close()

    ok = tanita_receiver.tanita_instance.save_measurement_to_db(
        client_id=client_id,
        client_name=req.client_name,
        appt_id=req.appointment_id,
        data=req.measurement
    )
    return {"success": ok}

# --- ENDPOINTS GOOGLE DRIVE (EXPEDIENTES DEPORTISTAS) ---

class DriveActionRequest(BaseModel):
    name: str

class DriveTanitaSaveRequest(BaseModel):
    name: str
    measurement: dict

@app.get("/api/drive/folder-info")
def get_drive_folder_info(name: str):
    info = drive_manager.get_athlete_folder_info(name)
    return info

@app.post("/api/drive/open-folder")
def open_drive_folder(req: DriveActionRequest):
    res = drive_manager.open_athlete_folder(req.name)
    return res

@app.post("/api/drive/save-tanita")
def save_tanita_to_drive(req: DriveTanitaSaveRequest):
    res = drive_manager.save_tanita_report_to_athlete_folder(req.name, req.measurement)
    return res

# --- ENDPOINTS COPILOTO IA ANyD ---

class CopilotQueryRequest(BaseModel):
    prompt: str

@app.post("/api/ai/copilot")
def query_ai_copilot(req: CopilotQueryRequest):
    res = ai_copilot.process_copilot_query(req.prompt)
    return res

# --- ENDPOINTS GESTIÓN DE FESTIVOS Y CIERRES (ALCORCÓN Y NACIONALES) ---

class AddHolidayRequest(BaseModel):
    date: str
    name: str
    scope: str = "Clínica Cerrada"
    is_closed: int = 1

@app.get("/api/holidays")
def api_get_holidays(start: Optional[str] = None, end: Optional[str] = None):
    return {"holidays": holidays_manager.get_holidays_list(start, end)}

@app.post("/api/holidays/add")
def api_add_holiday(req: AddHolidayRequest):
    ok = holidays_manager.add_custom_holiday(req.date, req.name, req.scope, req.is_closed)
    return {"success": ok}

@app.delete("/api/holidays/{holiday_id}")
def api_delete_holiday(holiday_id: int):
    ok = holidays_manager.remove_holiday(holiday_id)
    return {"success": ok}

# --- ENDPOINTS DIETOWIN 2.0 (ANyD NUTRI-PLANNER) ---

class CalculateNeedsRequest(BaseModel):
    weight_kg: float
    ffm_kg: Optional[float] = 0.0
    height_cm: Optional[float] = 175.0
    age: Optional[int] = 30
    gender: Optional[str] = "M"
    formula: Optional[str] = "cunningham"
    pal: Optional[float] = 1.5
    goal: Optional[str] = "mantenimiento"

class SmartWeekRequest(BaseModel):
    target_kcal: float = 2200.0
    target_protein_g: float = 140.0

class SavePlanRequest(BaseModel):
    client_name: str
    plan_name: str
    client_id: Optional[int] = None
    weight: Optional[float] = 0.0
    ffm: Optional[float] = 0.0
    bmr: Optional[float] = 0.0
    tdee: Optional[float] = 0.0
    target_kcal: Optional[float] = 0.0
    target_protein_g: Optional[float] = 0.0
    target_carbs_g: Optional[float] = 0.0
    target_fat_g: Optional[float] = 0.0
    weekly_data: Optional[Dict[str, Any]] = None
    notes: Optional[str] = ""

@app.get("/dietas", response_class=HTMLResponse)
def page_dietas(request: Request, client: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, fullname, phone, email FROM clients ORDER BY fullname ASC")
    clients = cursor.fetchall()
    conn.close()

    groups = diet_manager.get_canonical_groups()
    recipes_info = diet_manager.get_recipes(limit=1)
    foods_info = diet_manager.get_foods(limit=1)

    return templates.TemplateResponse(request=request, name="dietas.html", context={
        "clients": clients,
        "selected_client": client or "",
        "groups": groups,
        "total_recipes": recipes_info["total"],
        "total_foods": foods_info["total"]
    })

@app.get("/api/diet/recipes")
def api_get_recipes(q: str = "", group: str = "", limit: int = 50, offset: int = 0):
    return diet_manager.get_recipes(query=q, group=group, limit=limit, offset=offset)

@app.get("/api/diet/foods")
def api_get_foods(q: str = "", familia: str = "", fuente: str = "", limit: int = 50, offset: int = 0):
    return diet_manager.get_foods(query=q, familia=familia, fuente=fuente, limit=limit, offset=offset)

@app.get("/api/diet/food/{food_id}")
def api_get_food_detail(food_id: int):
    food = diet_manager.get_food_by_id(food_id)
    if not food:
        raise HTTPException(status_code=404, detail="Alimento no encontrado")
    return food

@app.get("/api/diet/off/search")
def api_search_off(q: str = "", limit: int = 15):
    if not q or len(q.strip()) < 2:
        return {"products": []}
    return {"products": diet_manager.search_open_food_facts(q, page_size=limit)}

@app.get("/api/diet/off/import")
@app.post("/api/diet/off/import")
def api_import_off(item: Dict[str, Any] = Body(...)):
    res = diet_manager.import_off_product_to_db(item)
    return res

# --- ENDPOINTS CRUD Y MANTENIMIENTO DE RECETAS ---
@app.get("/api/diet/recipe/{recipe_id}")
def api_get_recipe_detail(recipe_id: int):
    recipe = diet_manager.get_recipe_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    return recipe

@app.post("/api/diet/recipe")
def api_create_recipe(data: Dict[str, Any] = Body(...)):
    return diet_manager.create_recipe(data)

@app.put("/api/diet/recipe/{recipe_id}")
def api_update_recipe(recipe_id: int, data: Dict[str, Any] = Body(...)):
    return diet_manager.update_recipe(recipe_id, data)

@app.delete("/api/diet/recipe/{recipe_id}")
def api_delete_recipe(recipe_id: int):
    return diet_manager.delete_recipe(recipe_id)

@app.post("/api/diet/recipe/{recipe_id}/copy")
def api_copy_recipe(recipe_id: int):
    return diet_manager.copy_recipe(recipe_id)

# --- ENDPOINTS CRUD Y MANTENIMIENTO DE ALIMENTOS ---
@app.post("/api/diet/food")
def api_create_food(data: Dict[str, Any] = Body(...)):
    return diet_manager.create_food(data)

@app.put("/api/diet/food/{food_id}")
def api_update_food(food_id: int, data: Dict[str, Any] = Body(...)):
    return diet_manager.update_food(food_id, data)

@app.delete("/api/diet/food/{food_id}")
def api_delete_food(food_id: int):
    return diet_manager.delete_food(food_id)

@app.post("/api/diet/food/{food_id}/copy")
def api_copy_food(food_id: int):
    return diet_manager.copy_food(food_id)

@app.get("/api/diet/groups")
def api_get_diet_groups():
    return {"groups": diet_manager.get_canonical_groups()}

@app.post("/api/diet/calculate-needs")
def api_calculate_needs(req: CalculateNeedsRequest):
    return diet_manager.calculate_metabolism(
        weight_kg=req.weight_kg,
        ffm_kg=req.ffm_kg or 0.0,
        height_cm=req.height_cm or 175.0,
        age=req.age or 30,
        gender=req.gender or "M",
        formula=req.formula or "cunningham",
        pal=req.pal or 1.5,
        goal=req.goal or "mantenimiento"
    )

@app.post("/api/diet/generate-smart-week")
def api_generate_smart_week(req: SmartWeekRequest):
    return diet_manager.generate_smart_week(
        target_kcal=req.target_kcal,
        target_protein_g=req.target_protein_g
    )

@app.post("/api/diet/plan/save")
def api_save_diet_plan(req: SavePlanRequest):
    plan_id = diet_manager.save_diet_plan(
        client_name=req.client_name,
        plan_name=req.plan_name,
        client_id=req.client_id,
        weight=req.weight or 0.0,
        ffm=req.ffm or 0.0,
        bmr=req.bmr or 0.0,
        tdee=req.tdee or 0.0,
        target_kcal=req.target_kcal or 0.0,
        target_prot=req.target_protein_g or 0.0,
        target_carbs=req.target_carbs_g or 0.0,
        target_fat=req.target_fat_g or 0.0,
        weekly_data=req.weekly_data or {},
        notes=req.notes or ""
    )
    return {"success": True, "plan_id": plan_id, "message": f"Plan '{req.plan_name}' guardado con éxito."}

@app.get("/api/diet/plans")
def api_get_diet_plans(client: str = ""):
    plans = diet_manager.get_diet_plans_list(client_name=client)
    return {"plans": plans}

@app.get("/api/diet/plan/{plan_id}")
def api_get_diet_plan(plan_id: int):
    plan = diet_manager.get_diet_plan_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    return plan

@app.post("/api/diet/shopping-list")
def api_generate_shopping_list(data: Dict[str, Any] = Body(...)):
    week_data = data.get("week_data") or data
    return diet_manager.generate_shopping_list(week_data)

@app.get("/api/diet/latest-tanita/{client_name}")
def api_get_latest_tanita(client_name: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT weight, ffm, fat_percent, muscle_mass, bmr_cunningham, measurement_date
    FROM tanita_measurements
    WHERE client_name LIKE ?
    ORDER BY measurement_date DESC, id DESC LIMIT 1
    """, (f"%{client_name.strip()}%",))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"found": True, "data": dict(row)}
    return {"found": False}

@app.post("/api/diet/upload-training-schedule")
async def api_upload_training_schedule(file: UploadFile = File(...), weight_kg: float = 75.0):
    try:
        content = await file.read()
        res = diet_manager.parse_training_excel_or_csv(
            file_bytes=content,
            filename=file.filename or "entrenamientos.xlsx",
            weight_kg=weight_kg
        )
        return {"success": True, **res}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/diet/calculate-peri-workout")
def api_calculate_peri_workout(payload: Dict[str, Any] = Body(...)):
    guidelines = diet_manager.compute_peri_workout_guidelines(
        sport=payload.get("sport", "Entrenamiento"),
        duration_min=int(payload.get("duration_min", 60)),
        intensity=payload.get("intensity", "Moderada"),
        weight_kg=float(payload.get("weight_kg", 75.0)),
        start_time=payload.get("start_time", "18:00"),
        notes=payload.get("notes", "")
    )
    return {"success": True, "guidelines": guidelines}

@app.get("/api/diet/download-training-template")
def api_download_training_template():
    excel_bytes = diet_manager.generate_training_excel_template()
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plantilla_entrenamientos_anyd.xlsx"}
    )

# ==========================================
# RUTAS DE LA ESTACIÓN CLÍNICA & DEPORTIVA (CONSULTA 360°)
# ==========================================

@app.get("/consulta", response_class=HTMLResponse)
@app.get("/clinica", response_class=HTMLResponse)
def page_clinica_workstation(request: Request, client_id: Optional[int] = None):
    """
    Estación Clínica Integral: Historia Clínica SOAP, Tanita MC-580,
    Cunningham, Dietowin 2.0 y Analíticas de Sangre.
    """
    return templates.TemplateResponse(request=request, name="consulta.html", context={"initial_client_id": client_id})

@app.get("/api/clinica/athletes")
def api_clinica_athletes(q: str = "", limit: int = 50):
    athletes = clinical_manager.search_athletes(query=q, limit=limit)
    return {"athletes": athletes}

@app.get("/api/clinica/today-appointments")
def api_clinica_today():
    today_list = clinical_manager.get_today_scheduled_athletes()
    return {"today": today_list}

@app.get("/api/clinica/athlete/{client_id}")
def api_clinica_athlete_360(client_id: int):
    data = clinical_manager.get_athlete_360(client_id)
    if not data or not data.get("client"):
        raise HTTPException(status_code=404, detail="Deportista no encontrado")
    return data

@app.post("/api/clinica/athlete/{client_id}/profile")
async def api_save_athlete_profile(client_id: int, request: Request):
    payload = await request.json()
    clinical_manager.save_athlete_profile(client_id, payload)
    return {"success": True, "message": "Ficha y perfil clínico guardados correctamente"}

@app.post("/api/clinica/athlete/{client_id}/soap")
async def api_save_soap_note(client_id: int, request: Request):
    payload = await request.json()
    note_id = clinical_manager.save_soap_note(client_id, payload)
    return {"success": True, "note_id": note_id, "message": "Consulta SOAP registrada correctamente"}

@app.post("/api/clinica/athlete/{client_id}/tanita")
async def api_save_tanita(client_id: int, request: Request):
    payload = await request.json()
    client_name = payload.get("client_name") or f"Atleta {client_id}"
    m_id = clinical_manager.save_manual_tanita(client_id, client_name, payload)
    return {"success": True, "measurement_id": m_id, "message": "Medición de bioimpedancia registrada"}

@app.post("/api/clinica/athlete/{client_id}/lab-test")
async def api_save_lab_test(client_id: int, request: Request):
    payload = await request.json()
    test_id = clinical_manager.save_lab_test(client_id, payload)
    return {"success": True, "test_id": test_id, "message": "Analítica sanguínea registrada correctamente"}



