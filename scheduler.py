# -*- coding: utf-8 -*-
"""
=============================================================================
MOTOR DE RECORDATORIOS AUTOMÁTICOS (48H / REGLA FIN DE SEMANA)
ANyD Nutricionistas · Román Illescas Quiroga (Col. MAD00274)
=============================================================================
REGLA CLÍNICA:
1. Las citas se recuerdan 2 días antes de la fecha programada.
2. Si los 2 días caen en fin de semana (citas de lunes o martes), el recordatorio
   se anticipa y se envía el VIERNES anterior.
3. Sábados y domingos no disparan envíos para no molestar a los deportistas.
=============================================================================
"""

import sqlite3
from datetime import datetime, timedelta
import os

from email_service import send_reminder_48h
import whatsapp_service

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "anyd_booking.db"))

def get_target_appointment_dates(today_dt=None):
    """
    Calcula las fechas de citas que deben recibir recordatorio hoy:
    - Lunes a Jueves: Citas de hoy + 2 días (en 48h).
    - Viernes: Citas de fin de semana (sábado/domingo), Lunes (Fri+3) y Martes (Fri+4).
    - Fin de semana: Vacío (ya se cubrieron el viernes).
    """
    if today_dt is None:
        today_dt = datetime.now()

    weekday = today_dt.weekday() # 0=Lun, 1=Mar, 2=Mié, 3=Jue, 4=Vie, 5=Sáb, 6=Dom
    dates = []

    if weekday in (0, 1, 2, 3):
        dates.append((today_dt + timedelta(days=2)).strftime("%Y-%m-%d"))
    elif weekday == 4:
        # Viernes: Anticipar todo el fin de semana y el arranque de la próxima semana
        dates.append((today_dt + timedelta(days=1)).strftime("%Y-%m-%d")) # Sábado
        dates.append((today_dt + timedelta(days=2)).strftime("%Y-%m-%d")) # Domingo
        dates.append((today_dt + timedelta(days=3)).strftime("%Y-%m-%d")) # Lunes
        dates.append((today_dt + timedelta(days=4)).strftime("%Y-%m-%d")) # Martes

    return dates

def get_pending_reminders_for_today(today_dt=None):
    """
    Obtiene el listado detallado de citas que deben recibir recordatorio hoy,
    incluyendo enlaces wa.me directos para envío en 1-clic por WhatsApp.
    """
    target_dates = get_target_appointment_dates(today_dt)
    if not target_dates:
        return []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    placeholders = ",".join("?" for _ in target_dates)
    cursor.execute(f"""
        SELECT a.id, a.client_name, a.client_email, a.client_phone, 
               a.appointment_date, a.appointment_time, a.modality, a.service, a.reminder_sent,
               c.phone as client_phone_db
        FROM appointments a
        LEFT JOIN clients c ON a.client_id = c.id
        WHERE a.appointment_date IN ({placeholders}) 
          AND a.status = 'Agendada'
        ORDER BY a.appointment_date ASC, a.appointment_time ASC
    """, target_dates)

    rows = cursor.fetchall()
    reminders = []

    for r in rows:
        phone = r["client_phone"] or r["client_phone_db"] or ""
        wa_data = whatsapp_service.build_whatsapp_payload(
            client_name=r["client_name"],
            phone=phone,
            msg_type="reminder_48h",
            date_str=r["appointment_date"],
            time_str=r["appointment_time"],
            modality=r["modality"] or "Presencial",
            service=r["service"] or "Nutrición Deportiva"
        )

        reminders.append({
            "id": r["id"],
            "client_name": r["client_name"],
            "client_email": r["client_email"],
            "phone": phone,
            "appointment_date": r["appointment_date"],
            "appointment_time": r["appointment_time"],
            "modality": r["modality"] or "Presencial",
            "service": r["service"] or "Nutrición Deportiva",
            "reminder_sent": bool(r["reminder_sent"]),
            "whatsapp_link": wa_data["link"],
            "whatsapp_text": wa_data["text"]
        })

    conn.close()
    return reminders

def run_reminder_check(today_dt=None):
    """
    Ejecuta el envío de recordatorios automáticos (email) y actualiza reminder_sent = 1.
    """
    target_dates = get_target_appointment_dates(today_dt)
    if not target_dates:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fin de semana: Recordatorios ya enviados el viernes.")
        return 0

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    placeholders = ",".join("?" for _ in target_dates)
    cursor.execute(f"""
        SELECT id, client_name, client_email, appointment_date, appointment_time, modality
        FROM appointments
        WHERE appointment_date IN ({placeholders}) 
          AND reminder_sent = 0 
          AND status = 'Agendada'
    """, target_dates)

    appointments_to_remind = cursor.fetchall()
    count = 0

    for appt_id, name, email, appt_date, appt_time, modality in appointments_to_remind:
        if email:
            success = send_reminder_48h(
                to_email=email,
                client_name=name,
                appointment_date=appt_date,
                appointment_time=appt_time,
                modality=modality or "Presencial"
            )
            if success:
                cursor.execute("UPDATE appointments SET reminder_sent = 1 WHERE id = ?", (appt_id,))
                count += 1
        else:
            # Si no tiene email, queda registrado para que Román envíe por WhatsApp con 1-clic
            pass

    conn.commit()
    conn.close()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Recordatorios enviados hoy: {count} para fechas {target_dates}")
    return count

if __name__ == "__main__":
    run_reminder_check()
