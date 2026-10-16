import csv
import sqlite3
import os
import re
from datetime import datetime
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "anyd_booking.db"))

def get_client_id_map(cursor):
    cursor.execute("SELECT id, fullname, email, phone FROM clients")
    rows = cursor.fetchall()
    id_map = {}
    for r in rows:
        cid, name, email, phone = r[0], r[1] or "", r[2] or "", r[3] or ""
        if name:
            id_map[name.strip().lower()] = cid
        if email:
            id_map[email.strip().lower()] = cid
    return id_map, rows

def import_from_csv(csv_path: str):
    if not os.path.exists(csv_path):
        print(f"Error: El archivo {csv_path} no existe.")
        return 0

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    id_map, all_clients = get_client_id_map(cursor)

    imported = 0
    skipped = 0

    with open(csv_path, mode="r", encoding="utf-8-sig", errors="replace") as f:
        # Detect delimiter
        sample = f.read(4096)
        f.seek(0)
        delimiter = ";" if ";" in sample else ","
        reader = csv.DictReader(f, delimiter=delimiter)

        for row in reader:
            # Buscar columnas comunes de Reservio (en español o inglés)
            name = (row.get("Cliente") or row.get("Client") or row.get("Nombre") or row.get("client_name") or "").strip()
            email = (row.get("Email") or row.get("Correo") or row.get("client_email") or "").strip()
            phone = (row.get("Teléfono") or row.get("Telefono") or row.get("Phone") or row.get("client_phone") or "").strip()
            service = (row.get("Servicio") or row.get("Service") or "Anyd Nutrición Deportiva").strip()
            date_raw = (row.get("Fecha") or row.get("Date") or row.get("start_date") or "").strip()
            time_raw = (row.get("Hora") or row.get("Time") or row.get("start_time") or "10:00").strip()
            duration_raw = (row.get("Duración") or row.get("Duracion") or row.get("Duration") or "30").strip()
            status_raw = (row.get("Estado") or row.get("Status") or "Agendada").strip()
            notes = (row.get("Nota") or row.get("Notas") or row.get("Notes") or "").strip()

            if not name and not email:
                continue

            # Parsear fecha a formato YYYY-MM-DD
            date_clean = None
            for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"]:
                try:
                    dt = datetime.strptime(date_raw[:10], fmt)
                    date_clean = dt.strftime("%Y-%m-%d")
                    break
                except:
                    pass

            if not date_clean:
                continue

            # Parsear hora HH:MM
            time_clean = "10:00"
            m_time = re.search(r"(\d{1,2}):(\d{2})", time_raw)
            if m_time:
                time_clean = f"{int(m_time.group(1)):02d}:{m_time.group(2)}"

            # Parsear duración
            dur = 30
            m_dur = re.search(r"(\d+)", duration_raw)
            if m_dur:
                dur = int(m_dur.group(1))

            # Determinar modalidad
            modality = "Online" if "online" in service.lower() else "Presencial"

            # Estado
            status = "Completada" if "complet" in status_raw.lower() or "asisti" in status_raw.lower() else "Agendada"
            if "cancel" in status_raw.lower():
                status = "Cancelada"

            # Buscar o crear cliente
            client_id = id_map.get(name.lower()) or id_map.get(email.lower())
            if not client_id and name:
                cursor.execute("""
                INSERT INTO clients (fullname, email, phone) VALUES (?, ?, ?)
                """, (name, email, phone))
                client_id = cursor.lastrowid
                id_map[name.lower()] = client_id
                if email:
                    id_map[email.lower()] = client_id

            # Comprobar si ya existe cita para evitar duplicados
            cursor.execute("""
            SELECT id FROM appointments WHERE client_name = ? AND appointment_date = ? AND appointment_time = ?
            """, (name, date_clean, time_clean))
            if cursor.fetchone():
                skipped += 1
                continue

            cursor.execute("""
            INSERT INTO appointments (client_id, client_name, client_email, client_phone, appointment_date, appointment_time, duration_minutes, service, modality, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (client_id, name, email, phone, date_clean, time_clean, dur, service, modality, status, notes))
            imported += 1

    conn.commit()
    conn.close()
    print(f"Importación completada: {imported} citas añadidas, {skipped} duplicadas omitidas.")
    return imported

def import_from_ical_url(url: str):
    print(f"Descargando feed de Reservio desde {url}...")
    req = urllib.request.Request(url.replace("webcal://", "https://"), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        content = resp.read().decode("utf-8", errors="replace")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    id_map, _ = get_client_id_map(cursor)

    events = content.split("BEGIN:VEVENT")
    imported = 0
    skipped = 0

    for ev in events[1:]:
        summary = re.search(r"SUMMARY:(.*)", ev)
        dtstart = re.search(r"DTSTART(?:;[^:]+)?:(\d{8}T\d{6})", ev)
        dtend = re.search(r"DTEND(?:;[^:]+)?:(\d{8}T\d{6})", ev)
        desc = re.search(r"DESCRIPTION:(.*)", ev)

        if not dtstart or not summary:
            continue

        raw_title = summary.group(1).strip()
        start_str = dtstart.group(1).strip()
        start_dt = datetime.strptime(start_str[:15], "%Y%m%dT%H%M%S")
        date_str = start_dt.strftime("%Y-%m-%d")
        time_str = start_dt.strftime("%H:%M")

        dur = 30
        if dtend:
            try:
                end_str = dtend.group(1).strip()
                end_dt = datetime.strptime(end_str[:15], "%Y%m%dT%H%M%S")
                dur = int((end_dt - start_dt).total_seconds() / 60)
            except:
                pass

        # Limpiar nombre del deportista
        client_name = raw_title.replace("Cita:", "").replace("Reserva:", "").strip()
        service = "Anyd Nutrición Deportiva"
        if " - " in client_name:
            parts = client_name.split(" - ")
            client_name = parts[0].strip()
            service = parts[1].strip()

        modality = "Online" if "online" in service.lower() else "Presencial"

        # Comprobar duplicado
        cursor.execute("SELECT id FROM appointments WHERE client_name = ? AND appointment_date = ? AND appointment_time = ?", (client_name, date_str, time_str))
        if cursor.fetchone():
            skipped += 1
            continue

        cid = id_map.get(client_name.lower())
        cursor.execute("""
        INSERT INTO appointments (client_id, client_name, appointment_date, appointment_time, duration_minutes, service, modality, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Agendada', ?)
        """, (cid, client_name, date_str, time_str, dur, service, modality, "Importada de Reservio iCal"))
        imported += 1

    conn.commit()
    conn.close()
    print(f"Feed iCal procesado: {imported} citas añadidas, {skipped} duplicadas omitidas.")
    return imported
