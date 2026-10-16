import csv
import sqlite3
import os
import re

CSV_PATH = r"C:\Users\Roman\Downloads\clients.csv"
DB_PATH = r"g:\Mi unidad\1.- IA\IA Gemini\Agente anyd\anyd_booking.db"

def clean_phone(phone):
    if not phone:
        return ""
    # Remove spaces, hyphens, and ensure clean format
    p = re.sub(r"[^\d+]", "", phone.strip())
    return p

def clean_name(firstname, lastname):
    # Some names in Reservio have format '11 - luna' or similar prefixes
    fn = re.sub(r"^\d+\s*[-_]?\s*", "", firstname or "").strip()
    ln = (lastname or "").strip()
    full = f"{fn} {ln}".strip()
    return fn, ln, full

def init_db(conn):
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
    )
    """)
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
    )
    """)
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
        modality TEXT DEFAULT 'Presencial',
        status TEXT DEFAULT 'Agendada',
        reminder_sent INTEGER DEFAULT 0,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (bono_id) REFERENCES bonos (id),
        FOREIGN KEY (client_id) REFERENCES clients (id)
    )
    """)
    conn.commit()

def import_clients():
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    cursor = conn.cursor()

    with open(CSV_PATH, mode="r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        imported = 0
        skipped = 0
        for row in reader:
            email = (row.get("email") or "").strip()
            fn, ln, full = clean_name(row.get("firstname"), row.get("lastname"))
            phone = clean_phone(row.get("phone"))
            note = (row.get("note") or "").strip()
            address = (row.get("address") or "").strip()

            if not email and not phone and not full:
                skipped += 1
                continue

            try:
                cursor.execute("""
                INSERT INTO clients (firstname, lastname, fullname, email, phone, address, note)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    phone = COALESCE(NULLIF(excluded.phone, ''), clients.phone),
                    fullname = COALESCE(NULLIF(excluded.fullname, ''), clients.fullname),
                    note = COALESCE(NULLIF(excluded.note, ''), clients.note)
                """, (fn, ln, full, email if email else None, phone, address, note))
                imported += 1
            except Exception as e:
                skipped += 1

    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM clients")
    total_in_db = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM clients WHERE email IS NOT NULL AND email != ''")
    with_email = cursor.fetchone()[0]
    conn.close()

    print(f"Importación completada con éxito:")
    print(f"- Total de clientes en base de datos: {total_in_db}")
    print(f"- Clientes con email para reservas: {with_email}")

if __name__ == "__main__":
    import_clients()
