# -*- coding: utf-8 -*-
"""
=============================================================================
ESCÁNER IMAP DE NUEVOS PEDIDOS (info@anyd.es) · AGENTE ANYD NUTRICIONISTAS
Román Illescas Quiroga (Col. MAD00274)
=============================================================================
Conecta vía IMAP con SSL (mail.anyd.es:993) a la cuenta info@anyd.es,
localiza correos de nuevos pedidos de WooCommerce / anyd.es, extrae los
parámetros del bono y genera automáticamente la fila en Excel y SQLite.
=============================================================================
"""

import imaplib
import email
from email.header import decode_header
import re
import os
import json
import sqlite3
from datetime import datetime

import excel_manager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.environ.get("CONFIG_FILE", os.path.join(BASE_DIR, "config.json"))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "anyd_booking.db"))

def load_imap_config():
    """Carga los parámetros IMAP desde config.json o variables de entorno."""
    cfg = {
        "imap_server": os.environ.get("IMAP_SERVER", "mail.anyd.es"),
        "imap_port": int(os.environ.get("IMAP_PORT", 993)),
        "imap_user": os.environ.get("IMAP_USER", "info@anyd.es"),
        "imap_password": os.environ.get("IMAP_PASSWORD", ""),
        "enable_live_imap": False
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                disk_cfg = json.load(f)
                cfg["imap_server"] = disk_cfg.get("imap_server", cfg["imap_server"])
                cfg["imap_port"] = int(disk_cfg.get("imap_port", cfg["imap_port"]))
                cfg["imap_user"] = disk_cfg.get("imap_user", cfg["imap_user"])
                cfg["imap_password"] = disk_cfg.get("imap_password", cfg["imap_password"])
                cfg["enable_live_imap"] = disk_cfg.get("enable_live_imap", False)
        except Exception as e:
            print(f"[IMAP CONFIG ERROR] {e}")
    return cfg

def decode_mime_header(header_val):
    """Decodifica cabeceras MIME complejas (acentos, UTF-8, quoted-printable)."""
    if not header_val:
        return ""
    decoded_fragments = decode_header(header_val)
    parts = []
    for text, encoding in decoded_fragments:
        if isinstance(text, bytes):
            try:
                parts.append(text.decode(encoding or "utf-8", errors="replace"))
            except:
                parts.append(text.decode("latin-1", errors="replace"))
        else:
            parts.append(str(text))
    return "".join(parts)

def extract_email_body(msg_obj):
    """Extrae el contenido de texto plano o HTML del objeto de correo."""
    body_text = ""
    if msg_obj.is_multipart():
        for part in msg_obj.walk():
            content_type = part.get_content_type()
            content_disp = str(part.get("Content-Disposition") or "")
            if "attachment" in content_disp:
                continue
            if content_type in ["text/plain", "text/html"]:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        body_text += payload.decode(charset, errors="replace") + "\n"
                    except:
                        body_text += payload.decode("latin-1", errors="replace") + "\n"
    else:
        payload = msg_obj.get_payload(decode=True)
        if payload:
            charset = msg_obj.get_content_charset() or "utf-8"
            try:
                body_text = payload.decode(charset, errors="replace")
            except:
                body_text = payload.decode("latin-1", errors="replace")
    return body_text

def parse_order_from_email_text(subject, body, date_str=None):
    """
    Parsea de forma determinista la estructura de los correos de WooCommerce:
    '[ANyD Nutricionistas] Nuevo pedido de cliente (#25786)'
    """
    # 1. Extracción de Order ID
    order_id = None
    m_order = re.search(r'#(\d{4,8})', subject)
    if not m_order:
        m_order = re.search(r'(?:pedido|orden|order)\s*[:#]?\s*(\d{4,8})', body, re.IGNORECASE)
    if m_order:
        order_id = m_order.group(1).strip()

    if not order_id:
        return None

    # 2. Nombre del cliente
    client_name = ""
    m_name = re.search(r'(?:Nombre|Cliente|Facturación|Billing name):\s*([^\n\r<]+)', body, re.IGNORECASE)
    if m_name:
        client_name = m_name.group(1).strip()
    else:
        # Intento de extraer por línea de saludo "Has recibido el siguiente pedido de Nombre Apellidos:"
        m_saludo = re.search(r'pedido de\s+([A-Za-zÁÉÍÓÚáéíóúñÑçÇ\s]{4,40})[:\n\r]', body, re.IGNORECASE)
        if m_saludo:
            client_name = m_saludo.group(1).strip()

    # 3. Email
    client_email = ""
    m_email = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', body)
    if m_email and not "anyd.es" in m_email.group(1).lower():
        client_email = m_email.group(1).strip().lower()

    # 4. Teléfono
    phone = ""
    m_phone = re.search(r'(?:Teléfono|Phone|Móvil|WhatsApp):\s*([0-9+\s-]{9,16})', body, re.IGNORECASE)
    if m_phone:
        phone = re.sub(r'[^0-9+]', '', m_phone.group(1))

    # 5. Detección del tipo de bono
    tipo_bono = "Deportiva 3" # default fallback
    body_upper = (subject + " " + body).upper()

    if "COMPETICIÓN" in body_upper or "COMPETICION" in body_upper:
        tipo_bono = "COMPETICIÓN"
    elif "DEPORTIVA 5" in body_upper or "CLÍNICA 5" in body_upper or "CLINICA 5" in body_upper:
        tipo_bono = "Deportiva 5" if "DEPORTIVA" in body_upper else "Bono Clínica 5"
    elif "DEPORTIVA 3" in body_upper:
        tipo_bono = "Deportiva 3"
    elif "SUELTA" in body_upper or "INDIVIDUAL" in body_upper or "1ª CONSULTA" in body_upper:
        tipo_bono = "Consulta Suelta"

    # 6. Importe total
    price = 159.0
    m_price = re.search(r'(?:Total|Importe|Precio):\s*([0-9.,]+)\s*€', body, re.IGNORECASE)
    if m_price:
        try:
            val_str = m_price.group(1).replace(',', '.')
            price = float(val_str)
        except:
            pass
    else:
        # Precios oficiales ANyD de referencia
        if tipo_bono == "COMPETICIÓN": price = 284.0
        elif tipo_bono in ["Deportiva 5", "Bono Clínica 5"]: price = 249.0
        elif tipo_bono == "Deportiva 3": price = 159.0
        elif tipo_bono == "Consulta Suelta": price = 65.0

    # 7. Forma de pago
    forma_pago = "Online"
    if "transferencia" in body.lower():
        forma_pago = "Transferencia"
    elif "tarjeta" in body.lower() or "redsys" in body.lower() or "stripe" in body.lower():
        forma_pago = "Tarjeta"
    elif "bizum" in body.lower():
        forma_pago = "Bizum"

    fecha = date_str or datetime.now().strftime("%Y-%m-%d")

    return {
        "order_id": order_id,
        "client_name": client_name or f"Cliente Pedido #{order_id}",
        "email": client_email,
        "phone": phone,
        "tipo_bono": tipo_bono,
        "price": price,
        "forma_pago": forma_pago,
        "fecha": fecha
    }

def register_order_to_crm_and_excel(order_data):
    """
    Registra el pedido parseado en SQLite (clients, bonos) y en Excel (Bonos activos_claude.xlsx)
    asegurando total idempotencia.
    """
    order_id = str(order_data["order_id"]).strip()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Comprobar si ya está registrado en DB
    cursor.execute("SELECT id, order_id, client_name, total_sessions FROM bonos WHERE order_id = ?", (order_id,))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        return {
            "already_existed": True,
            "order_id": order_id,
            "client_name": existing["client_name"],
            "message": f"El pedido #{order_id} ya estaba registrado previamente en el sistema."
        }

    client_name = order_data["client_name"].strip()
    email_clean = (order_data["email"] or "").strip().lower()
    phone_clean = (order_data["phone"] or "").strip()
    tipo_bono = order_data["tipo_bono"]
    num_sessions = excel_manager.determine_num_sessions(tipo_bono)
    price = float(order_data.get("price", 159.0))
    forma_pago = order_data.get("forma_pago", "Online")
    fecha = order_data.get("fecha", datetime.now().strftime("%Y-%m-%d"))

    # 1. Registrar / Actualizar en tabla 'clients'
    parts = client_name.split(" ", 1)
    fname = parts[0]
    lname = parts[1] if len(parts) > 1 else ""

    cursor.execute("""
    INSERT INTO clients (firstname, lastname, fullname, email, phone)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(email) DO UPDATE SET
        fullname = excluded.fullname,
        phone = COALESCE(NULLIF(excluded.phone, ''), clients.phone)
    """, (fname, lname, client_name, email_clean if email_clean else None, phone_clean if phone_clean else None))

    cursor.execute("SELECT id FROM clients WHERE fullname = ? ORDER BY id DESC LIMIT 1", (client_name,))
    c_row = cursor.fetchone()
    client_id = c_row["id"] if c_row else None

    # 2. Registrar en tabla 'bonos'
    cursor.execute("""
    INSERT INTO bonos (order_id, client_id, client_name, client_email, tipo_bono, total_sessions, used_sessions, purchase_date, price, status, centro, forma_pago, nutri)
    VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, 'Activo', 'ANYD', ?, 'Román')
    ON CONFLICT(order_id) DO NOTHING
    """, (order_id, client_id, client_name, email_clean, tipo_bono, num_sessions, str(fecha)[:10], price, forma_pago))

    conn.commit()
    conn.close()

    # 3. Registrar en Excel 'Bonos activos_claude.xlsx'
    excel_created = excel_manager.add_purchase_to_excel(
        centro="ANYD",
        nombre=client_name,
        tipo_bono=tipo_bono,
        fecha_compra=fecha,
        n_pedido=order_id,
        importe=price,
        forma_pago=forma_pago,
        nutri="Román",
        num_sesiones=num_sessions
    )

    return {
        "already_existed": False,
        "order_id": order_id,
        "client_name": client_name,
        "tipo_bono": tipo_bono,
        "total_sessions": num_sessions,
        "excel_created": excel_created,
        "message": f"Pedido #{order_id} procesado con éxito. Bono {tipo_bono} creado con {num_sessions} sesiones en blanco."
    }

def scan_imap_orders(mark_as_read=False, max_messages=25):
    """
    Sondea la bandeja de entrada info@anyd.es en el servidor mail.anyd.es:993 vía IMAP SSL.
    """
    cfg = load_imap_config()

    if not cfg.get("enable_live_imap") or not cfg.get("imap_password"):
        return {
            "status": "standby",
            "live_mode": False,
            "message": "IMAP en modo standby: credenciales pendientes de configurar en config.json.",
            "server": cfg.get("imap_server"),
            "user": cfg.get("imap_user"),
            "orders_processed": []
        }

    processed_orders = []
    try:
        mail = imaplib.IMAP4_SSL(cfg["imap_server"], cfg["imap_port"])
        mail.login(cfg["imap_user"], cfg["imap_password"])
        mail.select("INBOX")

        # Buscar correos con asunto de pedido
        status, messages = mail.search(None, '(SUBJECT "pedido")')
        if status != "OK" or not messages[0]:
            status, messages = mail.search(None, '(SUBJECT "order")')

        msg_ids = messages[0].split() if (status == "OK" and messages[0]) else []
        recent_ids = msg_ids[-max_messages:] if len(msg_ids) > max_messages else msg_ids

        for msg_id in reversed(recent_ids):
            res, data = mail.fetch(msg_id, "(RFC822)")
            if res != "OK":
                continue
            raw_email = data[0][1]
            msg_obj = email.message_from_bytes(raw_email)

            subject = decode_mime_header(msg_obj.get("Subject", ""))
            date_raw = msg_obj.get("Date", "")
            body = extract_email_body(msg_obj)

            parsed = parse_order_from_email_text(subject, body)
            if parsed and parsed.get("order_id"):
                reg_res = register_order_to_crm_and_excel(parsed)
                processed_orders.append(reg_res)
                if mark_as_read:
                    mail.store(msg_id, "+FLAGS", "\\Seen")

        mail.close()
        mail.logout()

        return {
            "status": "success",
            "live_mode": True,
            "scanned_count": len(recent_ids),
            "orders_processed": processed_orders,
            "message": f"Escaneo IMAP completado. {len(processed_orders)} pedidos analizados."
        }
    except Exception as e:
        return {
            "status": "error",
            "live_mode": True,
            "message": f"Error conectando a {cfg['imap_server']}: {str(e)}",
            "orders_processed": []
        }
