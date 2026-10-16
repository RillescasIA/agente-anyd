import openpyxl
import sqlite3
import re
from datetime import datetime

EXCEL_PATH = r"G:\Mi unidad\1.- ANyD\Bonos activos_claude.xlsx"
DB_PATH = r"g:\Mi unidad\1.- IA\IA Gemini\Agente anyd\anyd_booking.db"

def determine_total_sessions(tipo_bono):
    tipo = str(tipo_bono).upper()
    if "3" in tipo:
        return 3
    elif "5" in tipo or "COMPET" in tipo:
        return 5
    elif "6" in tipo:
        return 6
    elif "SUELTA" in tipo or "INDIVIDUAL" in tipo or "CONSULTA" in tipo:
        return 1
    return 3 # default fallback

def sync_active_bonos():
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
    sheet = wb["Bonos activos"]
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get all clients for fuzzy matching
    cursor.execute("SELECT id, fullname, email, phone FROM clients")
    clients = cursor.fetchall()

    synced = 0
    for r_idx, row in enumerate(sheet.iter_rows(values_only=True)):
        if r_idx == 0:
            continue
        
        centro = row[0]
        nombre = row[1]
        tipo_bono = row[2]
        fecha_compra = row[3]
        n_pedido = str(row[4]).strip() if row[4] is not None else ""
        importe = row[5]
        activo = row[6]
        forma_pago = row[7]
        nutri = row[8] or "Román"

        if not nombre or activo != "Activo":
            continue

        # Count consultations done vs empty
        total_sessions = determine_total_sessions(tipo_bono)
        used_sessions = 0
        consultations = []
        
        # Consultations start at column index 9 (Consulta 1, 2, 3...)
        for c_idx in range(9, len(row)):
            val = row[c_idx]
            if val and str(val).strip():
                used_sessions += 1
                consultations.append(str(val).strip())

        # Format purchase date
        p_date_str = ""
        if isinstance(fecha_compra, datetime):
            p_date_str = fecha_compra.strftime("%Y-%m-%d")
        elif fecha_compra:
            p_date_str = str(fecha_compra)[:10]

        # Match client in database
        client_id = None
        client_email = None
        
        # Clean nombre
        nombre_clean = re.sub(r"\s*-\s*.*$", "", str(nombre)).strip().lower()
        for cid, cname, cemail, cphone in clients:
            if cname:
                cname_clean = cname.lower()
                if nombre_clean in cname_clean or cname_clean in nombre_clean:
                    client_id = cid
                    client_email = cemail
                    break

        # If not found in clients, create a new client
        if not client_id:
            cursor.execute("""
            INSERT INTO clients (fullname) VALUES (?)
            """, (str(nombre),))
            client_id = cursor.lastrowid

        # Insert or update bono
        cursor.execute("""
        INSERT INTO bonos (order_id, client_id, client_name, client_email, tipo_bono, total_sessions, used_sessions, purchase_date, price, status, centro, forma_pago, nutri)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Activo', ?, ?, ?)
        ON CONFLICT(order_id) DO UPDATE SET
            used_sessions = excluded.used_sessions,
            total_sessions = excluded.total_sessions,
            status = excluded.status,
            client_email = COALESCE(excluded.client_email, bonos.client_email)
        """, (
            n_pedido if n_pedido and n_pedido != "--" else f"MANUAL_{r_idx}",
            client_id,
            str(nombre),
            client_email,
            str(tipo_bono),
            total_sessions,
            used_sessions,
            p_date_str,
            float(importe) if importe and str(importe).replace(".", "").isdigit() else 0.0,
            str(centro) if centro else "ANYD",
            str(forma_pago) if forma_pago else "",
            str(nutri)
        ))
        synced += 1

    conn.commit()
    conn.close()
    print(f"Sincronizados {synced} bonos activos de '{EXCEL_PATH}' con la base de datos.")
    return synced

if __name__ == "__main__":
    sync_active_bonos()
