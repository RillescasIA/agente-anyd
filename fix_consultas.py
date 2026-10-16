import os
import shutil
import sqlite3
import re
import urllib.request
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "anyd_booking.db")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
EXCEL_PATH = r"G:\Mi unidad\1.- ANyD\Bonos activos_claude.xlsx"
RESERVIO_URL = "https://app.reservio.com/sync/calendar/SBCIDgEoq9ad0vca/RjIpEApMEw.ics"

def clean_name(n):
    if not n:
        return ""
    # remove accents and symbols
    s = (n or "").lower()
    s = re.sub(r'[^a-záéíóúñ]', '', s)
    trans = str.maketrans('áéíóú', 'aeiou')
    return s.translate(trans)

def utc_to_madrid(dt_utc: datetime) -> datetime:
    year = dt_utc.year
    march_31 = datetime(year, 3, 31, 1, 0)
    dst_start = march_31 - timedelta(days=(march_31.weekday() + 1) % 7)
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

def run_cleanup():
    print("=== INICIANDO LIMPIEZA Y AUDITORÍA INTEGRAL DE CONSULTAS Y CITAS ===")
    
    # 1. Backup de seguridad
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"anyd_booking_pre_consultas_fix_{ts}.db")
    shutil.copy2(DB_PATH, backup_file)
    print(f"✓ Backup de seguridad guardado en: {backup_file}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 2. Eliminar citas de prueba manuales/simuladas (IDs 1852 a 1859)
    cursor.execute("""
    DELETE FROM appointments 
    WHERE id BETWEEN 1852 AND 1859
       OR notes LIKE '%Revisión mensual de composición corporal%'
       OR notes LIKE '%Preparación nutricional para media maratón%'
       OR notes LIKE '%Videollamada seguimiento pauta de hidratación%'
    """)
    deleted_fakes = cursor.rowcount
    print(f"✓ Eliminadas {deleted_fakes} citas falsas/mock de prueba (1852-1859)")

    # 3. Eliminar mediciones de bioimpedancia simuladas (SIMULATED_DATA_MC580) y notas clínicas de prueba
    cursor.execute("DELETE FROM tanita_measurements WHERE raw_data LIKE '%SIMULATED_DATA%'")
    del_tanita = cursor.rowcount
    cursor.execute("DELETE FROM clinical_notes WHERE subjective LIKE '%Muy buenas sensaciones de energía y sin fatiga%'")
    del_soap = cursor.rowcount
    cursor.execute("DELETE FROM lab_tests WHERE clinical_interpretation LIKE '%Perfil bioquímico y hematológico óptimo%'")
    del_labs = cursor.rowcount
    print(f"✓ Eliminados registros simulados de prueba: {del_tanita} Tanita, {del_soap} SOAP, {del_labs} Analíticas")

    # 4. Descargar y parsear feed REAL de Reservio (fuente de verdad de agenda)
    print(f"\nDescargando feed oficial de Reservio ({RESERVIO_URL})...")
    req = urllib.request.Request(RESERVIO_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        content = resp.read().decode("utf-8", errors="replace")

    today_str = datetime.now().strftime("%Y-%m-%d")
    raw_events = content.split("BEGIN:VEVENT")
    print(f"✓ Eventos encontrados en Reservio: {len(raw_events) - 1}")

    # Cargar mapa de clientes para asociar client_id
    cursor.execute("SELECT id, fullname, email, phone FROM clients")
    client_rows = cursor.fetchall()
    name_to_client = {}
    email_to_client = {}
    for c in client_rows:
        if c["fullname"]:
            name_to_client[clean_name(c["fullname"])] = dict(c)
        if c["email"]:
            email_to_client[c["email"].strip().lower()] = dict(c)

    # Cargar bonos activos para vincular bono_id
    cursor.execute("SELECT id, client_id, client_name FROM bonos WHERE status = 'Activo'")
    bono_rows = cursor.fetchall()
    client_to_bono = {}
    for b in bono_rows:
        if b["client_id"]:
            client_to_bono[b["client_id"]] = b["id"]
        if b["client_name"]:
            client_to_bono[clean_name(b["client_name"])] = b["id"]

    email_regex = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
    phone_regex = re.compile(r"(\+?\d[\d\s-]{7,}\d)")

    reservio_events_processed = []
    reservio_keys = set() # (clean_name, date)

    for ev in raw_events[1:]:
        sum_m = re.search(r"SUMMARY:(.*)", ev)
        dt_m = re.search(r"DTSTART(?:;[^:]+)?:(\d{8}T\d{6})Z?", ev)
        dtend_m = re.search(r"DTEND(?:;[^:]+)?:(\d{8}T\d{6})Z?", ev)
        desc_m = re.search(r"DESCRIPTION:(.*)", ev)
        status_m = re.search(r"STATUS:(.*)", ev)

        if not sum_m or not dt_m:
            continue

        raw_summary = sum_m.group(1).strip()
        if " - " in raw_summary:
            name_part, service_part = raw_summary.split(" - ", 1)
        else:
            name_part, service_part = raw_summary, "Anyd Nutrición Deportiva"

        client_name = re.sub(r"^\d+\s*[-_]?\s*", "", name_part).strip()
        client_name = client_name.rstrip(":").strip()
        service = normalize_service(service_part)

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

        email = ""
        phone = ""
        reservio_url = ""
        desc_notes = ""

        if desc_m:
            raw_desc = desc_m.group(1).replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";")
            lines = [l.strip() for l in raw_desc.splitlines() if l.strip()]

            m_em = email_regex.search(raw_desc)
            if m_em:
                email = m_em.group(1).strip().lower()

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

            if lines and "@" not in lines[0] and "reservio" not in lines[0] and len(lines[0]) > len(client_name):
                client_name = lines[0].strip().rstrip(":").strip()

        modality = "Online" if "online" in service.lower() else "Presencial"

        # Estado real
        if (status_m and "CANCEL" in status_m.group(1).upper()) or "cancel" in raw_summary.lower() or "cancelada" in desc_notes.lower():
            status = "Cancelada"
        elif date_str < today_str:
            status = "Completada"
        else:
            status = "Agendada"

        c_clean = clean_name(client_name)
        matched_client = email_to_client.get(email) or name_to_client.get(c_clean)
        client_id = matched_client["id"] if matched_client else None
        bono_id = client_to_bono.get(client_id) or client_to_bono.get(c_clean)

        note_text = f"Reservio: {service} ({time_str})"
        if phone:
            note_text += f" - {phone}"
        if desc_notes:
            note_text += f" - {desc_notes}"
        if reservio_url:
            note_text += f" - {reservio_url}"

        reservio_events_processed.append({
            "client_id": client_id,
            "bono_id": bono_id,
            "client_name": client_name,
            "client_email": email or (matched_client.get("email") if matched_client else ""),
            "client_phone": phone or (matched_client.get("phone") if matched_client else ""),
            "appointment_date": date_str,
            "appointment_time": time_str,
            "duration_minutes": dur,
            "service": service,
            "modality": modality,
            "status": status,
            "notes": note_text,
            "clean_name": c_clean
        })
        reservio_keys.add((c_clean, date_str))

    print(f"✓ Eventos procesados y validados de Reservio: {len(reservio_events_processed)}")

    # 5. Identificar y eliminar duplicados de Excel que coinciden con citas de Reservio
    cursor.execute("SELECT id, client_name, appointment_date, appointment_time, notes FROM appointments WHERE notes LIKE 'Importada de%'")
    excel_rows = cursor.fetchall()
    
    deleted_excel_dups = []
    kept_excel_historical = []

    for r in excel_rows:
        ex_id = r["id"]
        ex_name = clean_name(r["client_name"])
        ex_date = r["appointment_date"]

        # Comprobar si existe en Reservio el mismo día
        is_dup = False
        if (ex_name, ex_date) in reservio_keys:
            is_dup = True
        else:
            for (rc_name, rd_date) in reservio_keys:
                if rd_date == ex_date and (ex_name in rc_name or rc_name in ex_name) and len(ex_name) >= 4:
                    is_dup = True
                    break

        if is_dup:
            deleted_excel_dups.append(ex_id)
        else:
            kept_excel_historical.append(ex_id)

    print(f"\n✓ Citas duplicadas de Excel a eliminar (ya cubiertas por Reservio): {len(deleted_excel_dups)}")
    print(f"✓ Citas históricas únicas de Excel que se conservan (anteriores a Reservio): {len(kept_excel_historical)}")

    if deleted_excel_dups:
        cursor.execute(f"DELETE FROM appointments WHERE id IN ({','.join(map(str, deleted_excel_dups))})")
        print(f"✓ Eliminadas con éxito {len(deleted_excel_dups)} filas duplicadas de Excel.")

    # 6. Insertar o actualizar citas de Reservio en appointments
    # Consultar citas actuales para evitar duplicar en la inserción
    cursor.execute("SELECT id, client_name, appointment_date, appointment_time, notes FROM appointments")
    current_appts = cursor.fetchall()
    current_map = {}
    for ca in current_appts:
        c_clean = clean_name(ca["client_name"])
        current_map[(c_clean, ca["appointment_date"], ca["appointment_time"])] = ca["id"]

    inserted_reservio = 0
    updated_reservio = 0

    for rev in reservio_events_processed:
        key = (rev["clean_name"], rev["appointment_date"], rev["appointment_time"])
        if key in current_map:
            # Actualizar estado, notas y bono
            appt_id = current_map[key]
            cursor.execute("""
            UPDATE appointments 
            SET status = ?, notes = ?, bono_id = COALESCE(bono_id, ?),
                service = ?, modality = ?, duration_minutes = ?
            WHERE id = ?
            """, (rev["status"], rev["notes"], rev["bono_id"], rev["service"], rev["modality"], rev["duration_minutes"], appt_id))
            updated_reservio += 1
        else:
            # Si existía en la misma fecha pero con hora dummy '10:00'
            dummy_key = (rev["clean_name"], rev["appointment_date"], "10:00")
            if dummy_key in current_map:
                appt_id = current_map[dummy_key]
                cursor.execute("""
                UPDATE appointments 
                SET appointment_time = ?, duration_minutes = ?, service = ?, modality = ?,
                    status = ?, notes = ?, bono_id = COALESCE(bono_id, ?)
                WHERE id = ?
                """, (rev["appointment_time"], rev["duration_minutes"], rev["service"], rev["modality"],
                      rev["status"], rev["notes"], rev["bono_id"], appt_id))
                del current_map[dummy_key]
                current_map[key] = appt_id
                updated_reservio += 1
            else:
                cursor.execute("""
                INSERT INTO appointments (client_id, bono_id, client_name, client_email, client_phone, appointment_date, appointment_time, duration_minutes, service, modality, status, reminder_sent, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                """, (rev["client_id"], rev["bono_id"], rev["client_name"], rev["client_email"], rev["client_phone"],
                      rev["appointment_date"], rev["appointment_time"], rev["duration_minutes"], rev["service"],
                      rev["modality"], rev["status"], rev["notes"]))
                inserted_reservio += 1
                current_map[key] = cursor.lastrowid

    # 7. Asegurar que TODAS las citas pasadas tienen status 'Completada' (salvo 'Cancelada')
    cursor.execute("""
    UPDATE appointments 
    SET status = 'Completada' 
    WHERE appointment_date < ? AND status = 'Agendada'
    """, (today_str,))
    fixed_past_status = cursor.rowcount
    print(f"✓ Citas pasadas actualizadas a 'Completada': {fixed_past_status}")

    conn.commit()

    # 8. Verificación final de contadores
    cursor.execute("SELECT count(*) FROM appointments")
    total_final = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM appointments WHERE status = 'Agendada'")
    agendadas_final = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM appointments WHERE status = 'Completada'")
    completadas_final = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM appointments WHERE status = 'Cancelada'")
    canceladas_final = cursor.fetchone()[0]

    print("\n" + "="*60)
    print("      BALANCE FINAL DE CITAS Y CONSULTAS AUDITADAS")
    print("="*60)
    print(f" Total de citas consolidadas:    {total_final}")
    print(f"   - Agendadas (futuras):         {agendadas_final}")
    print(f"   - Completadas (histórico real):{completadas_final}")
    print(f"   - Canceladas en Reservio:      {canceladas_final}")
    print(f" Citas Reservio actualizadas:    {updated_reservio}")
    print(f" Citas Reservio nuevas añadidas: {inserted_reservio}")
    print("="*60 + "\n")

    conn.close()

if __name__ == "__main__":
    run_cleanup()
