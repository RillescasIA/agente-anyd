import sqlite3
from datetime import datetime, timedelta
import os
from email_service import send_reminder_48h

DB_PATH = r"g:\Mi unidad\1.- IA\IA Gemini\Agente anyd\anyd_booking.db"

def run_reminder_check():
    """
    Busca todas las citas que tendrán lugar dentro de 2 días (48h)
    y envía el email recordatorio a los deportistas si no se ha enviado aún.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    target_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Comprobando citas para recordatorio de 48h (Fecha objetivo: {target_date})...")

    cursor.execute("""
    SELECT id, client_name, client_email, appointment_date, appointment_time, modality
    FROM appointments
    WHERE appointment_date = ? AND reminder_sent = 0 AND status = 'Agendada'
    """, (target_date,))

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

    conn.commit()
    conn.close()
    print(f"Recordatorios enviados hoy: {count}")
    return count

if __name__ == "__main__":
    run_reminder_check()
