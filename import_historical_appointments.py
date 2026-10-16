import openpyxl
import re
import sqlite3
from datetime import datetime

EXCEL_PATH = r"G:\Mi unidad\1.- ANyD\Bonos activos_claude.xlsx"
DB_PATH = r"g:\Mi unidad\1.- IA\IA Gemini\Agente anyd\anyd_booking.db"

date_pattern = re.compile(r"(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})")

def import_history():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get client mappings
    cursor.execute("SELECT id, fullname, email, phone FROM clients")
    clients = cursor.fetchall()

    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
    inserted = 0

    for sname in ["Bonos activos", "Bonos agotados"]:
        if sname not in wb.sheetnames:
            continue
        sheet = wb[sname]
        for row in sheet.iter_rows(values_only=True):
            client_name = row[1]
            if not client_name or str(client_name).strip() in ["Nombre", "TOTAL", "Año", "None"]:
                continue

            order_id = str(row[4]).strip() if row[4] else ""
            
            # Find client match
            c_name_clean = re.sub(r"[\-\/].*$", "", str(client_name)).strip().lower()
            matched_id = None
            matched_email = None
            matched_phone = None

            for cid, cfullname, cemail, cphone in clients:
                cf_clean = (cfullname or "").lower()
                if c_name_clean in cf_clean or cf_clean in c_name_clean:
                    matched_id = cid
                    matched_email = cemail
                    matched_phone = cphone
                    break

            # Consultations start at column index 9
            for c_idx in range(9, len(row)):
                cell_val = row[c_idx]
                if not cell_val:
                    continue
                val_str = str(cell_val).strip()
                match = date_pattern.search(val_str)
                if match:
                    d, m, y = match.groups()
                    if len(y) == 2:
                        y = "20" + y
                    try:
                        dt = datetime(int(y), int(m), int(d))
                        date_str = dt.strftime("%Y-%m-%d")

                        # Insert appointment if not already existing
                        cursor.execute("""
                        INSERT INTO appointments (client_id, client_name, client_email, client_phone, appointment_date, appointment_time, modality, status, reminder_sent, notes)
                        VALUES (?, ?, ?, ?, ?, ?, 'Presencial', 'Completada', 1, ?)
                        """, (matched_id, str(client_name), matched_email, matched_phone, date_str, "10:00", f"Importada de {sname} - {val_str}"))
                        inserted += 1
                    except Exception as e:
                        pass

    conn.commit()
    conn.close()
    print(f"Importadas {inserted} citas históricas a la base de datos.")

if __name__ == "__main__":
    import_history()
