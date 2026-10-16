import urllib.request
import re
import sqlite3
import os
import shutil
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "anyd_booking.db"))
RESERVIO_ICAL_URL = "https://app.reservio.com/sync/calendar/SBCIDgEoq9ad0vca/RjIpEApMEw.ics"

def utc_to_madrid(dt_utc: datetime) -> datetime:
    """Convierte UTC a horario oficial peninsular de Madrid (CET / CEST con cambio de hora)."""
    year = dt_utc.year
    # Último domingo de marzo a las 01:00 UTC (inicio verano UTC+2)
    march_31 = datetime(year, 3, 31, 1, 0)
    dst_start = march_31 - timedelta(days=(march_31.weekday() + 1) % 7)
    # Último domingo de octubre a las 01:00 UTC (inicio invierno UTC+1)
    oct_31 = datetime(year, 10, 31, 1, 0)
    dst_end = oct_31 - timedelta(days=(oct_31.weekday() + 1) % 7)

    if dst_start <= dt_utc < dst_end:
        return dt_utc + timedelta(hours=2)
    else:
        return dt_utc + timedelta(hours=1)

def normalize_service(raw_service: str) -> str:
    s = (raw_service or "").strip()
    s_clean = re.sub(r"^\d+\s*[-_]?\s*", "", s).strip()
    s_lower = s_clean.lower()
    
    if "catedral" in s_lower:
        return "CF Catedral Nutrición"
    elif "tracius" in s_lower and "online" in s_lower:
        return "Anyd Consulta OnLine"
    elif "tracius" in s_lower and "clínica" in s_lower:
        return "Anyd Nutrición Clínica"
    elif "tracius" in s_lower:
        return "Tracius Nutrición Deportiva"
    elif "clínica" in s_lower or "clinica" in s_lower:
        return "Anyd Nutrición Clínica"
    elif "online" in s_lower:
        return "Anyd Consulta OnLine"
    elif "informativa" in s_lower:
        return "Sesión informativa"
    elif not s_clean or s_clean.lower() == "no asignado":
        return "Anyd Nutrición Deportiva"
    return s_clean

def clean_phone_number(raw_phone: str) -> str:
    if not raw_phone:
        return ""
    p = re.sub(r"[^\d+]", "", raw_phone.strip())
    if len(p) == 9 and p[0] in "6789":
        p = "+34" + p
    return p

def run_reservio_sync():
    print(f"Descargando feed de Reservio desde {RESERVIO_ICAL_URL}...")
    req = urllib.request.Request(RESERVIO_ICAL_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        content = resp.read().decode("utf-8", errors="replace")

    # Copia de seguridad automática de seguridad
    backup_path = os.path.join(BASE_DIR, "backups", f"anyd_booking_pre_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, backup_path)
        print(f"✓ Backup de seguridad guardado en: {backup_path}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Cargar mapa de clientes
    cursor.execute("SELECT id, fullname, email, phone FROM clients")
    client_rows = cursor.fetchall()
    
    name_to_client = {}
    email_to_client = {}
    for c in client_rows:
        if c["fullname"]:
            name_to_client[c["fullname"].strip().lower()] = dict(c)
        if c["email"]:
            email_to_client[c["email"].strip().lower()] = dict(c)

    # Cargar citas existentes
    cursor.execute("SELECT id, client_name, appointment_date, appointment_time, notes FROM appointments")
    existing_appts = cursor.fetchall()
    
    appt_exact_map = set()
    appt_date_name_map = {}
    
    for a in existing_appts:
        c_name = (a["client_name"] or "").strip().lower()
        d_str = a["appointment_date"]
        t_str = a["appointment_time"] or "10:00"
        
        appt_exact_map.add((c_name, d_str, t_str))
        appt_date_name_map.setdefault((c_name, d_str), []).append(dict(a))

    today_str = datetime.now().strftime("%Y-%m-%d")
    raw_events = content.split("BEGIN:VEVENT")

    inserted_count = 0
    updated_count = 0
    skipped_count = 0
    new_clients_count = 0
    future_count = 0

    email_regex = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
    phone_regex = re.compile(r"(\+?\d[\d\s-]{7,}\d)")

    for ev in raw_events[1:]:
        sum_m = re.search(r"SUMMARY:(.*)", ev)
        dt_m = re.search(r"DTSTART(?:;[^:]+)?:(\d{8}T\d{6})Z?", ev)
        dtend_m = re.search(r"DTEND(?:;[^:]+)?:(\d{8}T\d{6})Z?", ev)
        desc_m = re.search(r"DESCRIPTION:(.*)", ev)

        if not sum_m or not dt_m:
            continue

        raw_summary = sum_m.group(1).strip()
        if " - " in raw_summary:
            name_part, service_part = raw_summary.split(" - ", 1)
        else:
            name_part, service_part = raw_summary, "Anyd Nutrición Deportiva"

        client_name = re.sub(r"^\d+\s*[-_]?\s*", "", name_part).strip()
        service = normalize_service(service_part)

        # Parsear fechas y duración
        dt_utc = datetime.strptime(dt_m.group(1).strip(), "%Y%m%dT%H%M%S")
        dt_local = utc_to_madrid(dt_utc)
        date_str = dt_local.strftime("%Y-%m-%d")
        time_str = dt_local.strftime("%H:%M")

        dur = 30
        if dtend_m:
            try:
                end_utc = datetime.strptime(dtend_m.group(1).strip(), "%Y%m%dT%H%M%S")
                end_local = utc_to_madrid(end_utc)
                dur = round((end_local - dt_local).total_seconds() / 60)
                if dur <= 5 or dur > 240:
                    dur = 30
            except:
                dur = 30

        # Parsear descripción (Nombre, Email, Teléfono, Notas)
        email = ""
        phone = ""
        reservio_url = ""
        desc_notes = ""

        if desc_m:
            raw_desc = desc_m.group(1).replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";")
            lines = [l.strip() for l in raw_desc.splitlines() if l.strip()]

            # Buscar email
            m_em = email_regex.search(raw_desc)
            if m_em:
                email = m_em.group(1).strip()

            # Buscar teléfono
            for line in lines:
                m_ph = phone_regex.search(line)
                if m_ph and "@" not in line and "reservio.com" not in line:
                    phone = clean_phone_number(m_ph.group(1))
                    break

            for line in lines:
                if "reservio.com" in line:
                    reservio_url = line
                elif line != email and line != phone and line != client_name and not email_regex.search(line):
                    desc_notes = line

            # A veces la línea 1 tiene el nombre completo más exacto que el resumen
            if lines and "@" not in lines[0] and "reservio" not in lines[0] and len(lines[0]) > len(client_name):
                client_name = lines[0].strip()

        # Modalidad
        modality = "Online" if "online" in service.lower() else "Presencial"

        # Estado
        if date_str < today_str:
            status = "Completada"
        else:
            status = "Agendada"
            future_count += 1

        # Limpieza de email y teléfono (evitar cadenas vacías que rompen UNIQUE en SQLite)
        clean_em = email.strip().lower() if (email and email.strip()) else None
        clean_ph = phone.strip() if (phone and phone.strip()) else None

        # Matching o creación del cliente
        matched_client = None
        if clean_em and clean_em in email_to_client:
            matched_client = email_to_client[clean_em]
        elif client_name and client_name.strip().lower() in name_to_client:
            matched_client = name_to_client[client_name.strip().lower()]

        client_id = matched_client["id"] if matched_client else None

        if not matched_client and client_name:
            try:
                cursor.execute("""
                INSERT INTO clients (fullname, email, phone, note)
                VALUES (?, ?, ?, 'Importado de Reservio')
                """, (client_name, clean_em, clean_ph))
                client_id = cursor.lastrowid
                new_c = {"id": client_id, "fullname": client_name, "email": clean_em, "phone": clean_ph}
                name_to_client[client_name.strip().lower()] = new_c
                if clean_em:
                    email_to_client[clean_em] = new_c
                new_clients_count += 1
            except sqlite3.IntegrityError:
                if clean_em:
                    cursor.execute("SELECT id, fullname, email, phone FROM clients WHERE email = ?", (clean_em,))
                    r = cursor.fetchone()
                    if r:
                        client_id = r["id"]
                        matched_client = dict(r)
        elif matched_client:
            update_fields = []
            update_vals = []
            if not matched_client.get("phone") and clean_ph:
                update_fields.append("phone = ?")
                update_vals.append(clean_ph)
                matched_client["phone"] = clean_ph
            if not matched_client.get("email") and clean_em:
                update_fields.append("email = ?")
                update_vals.append(clean_em)
                matched_client["email"] = clean_em
            if update_fields:
                update_vals.append(client_id)
                cursor.execute(f"UPDATE clients SET {', '.join(update_fields)} WHERE id = ?", update_vals)

        final_email = clean_em or (matched_client.get("email") if matched_client else None)
        final_phone = clean_ph or (matched_client.get("phone") if matched_client else None)

        # Gestión de duplicados / actualización de horas reales de Excel
        key_exact = (client_name.lower(), date_str, time_str)
        key_date = (client_name.lower(), date_str)

        if key_exact in appt_exact_map:
            skipped_count += 1
            continue

        # Si ya existía una cita de Excel el mismo día con la hora por defecto "10:00" y notas de Excel
        if key_date in appt_date_name_map:
            candidates = appt_date_name_map[key_date]
            # Si tiene hora 10:00 y es importada de Excel, la actualizamos con la hora exacta de Reservio
            matching_excel_appt = next((a for a in candidates if a["appointment_time"] == "10:00" and "Importada de" in (a["notes"] or "")), None)
            if matching_excel_appt:
                cursor.execute("""
                UPDATE appointments
                SET appointment_time = ?, duration_minutes = ?, service = ?, modality = ?,
                    client_email = COALESCE(NULLIF(client_email, ''), ?),
                    client_phone = COALESCE(NULLIF(client_phone, ''), ?),
                    notes = ?
                WHERE id = ?
                """, (time_str, dur, service, modality, final_email, final_phone, f"Reservio (Real: {time_str}) · {matching_excel_appt['notes']}", matching_excel_appt["id"]))
                matching_excel_appt["appointment_time"] = time_str
                appt_exact_map.add(key_exact)
                updated_count += 1
                continue

        # Cita nueva (no existía en la base de datos)
        note_text = f"Reservio: {service} ({time_str})"
        if desc_notes:
            note_text += f" - {desc_notes}"
        if reservio_url:
            note_text += f" - {reservio_url}"

        cursor.execute("""
        INSERT INTO appointments (client_id, client_name, client_email, client_phone, appointment_date, appointment_time, duration_minutes, service, modality, status, reminder_sent, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """, (client_id, client_name, final_email, final_phone, date_str, time_str, dur, service, modality, status, note_text))
        
        appt_exact_map.add(key_exact)
        appt_date_name_map.setdefault(key_date, []).append({
            "id": cursor.lastrowid, "client_name": client_name, "appointment_date": date_str, "appointment_time": time_str, "notes": note_text
        })
        inserted_count += 1

    conn.commit()
    conn.close()

    print("\n" + "="*55)
    print("      RESUMEN DE LA MIGRACIÓN DE RESERVIO")
    print("="*55)
    print(f" Total eventos procesados en feed:   {len(raw_events) - 1}")
    print(f" Citas nuevas importadas:            {inserted_count}")
    print(f" Citas actualizadas con hora real:   {updated_count}")
    print(f" Citas futuras en agenda (>= hoy):   {future_count}")
    print(f" Nuevos deportistas creados:         {new_clients_count}")
    print(f" Citas duplicadas omitidas:          {skipped_count}")
    print("="*55 + "\n")
    return {
        "total": len(raw_events) - 1,
        "inserted": inserted_count,
        "updated": updated_count,
        "future": future_count,
        "new_clients": new_clients_count,
        "skipped": skipped_count
    }

if __name__ == "__main__":
    run_reservio_sync()
