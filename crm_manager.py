# -*- coding: utf-8 -*-
"""
=============================================================================
CRM MANAGER · CONTROL Y ALTA AUTOMÁTICA DE CLIENTES POR BONO
Agente ANyD Nutricionistas · Román Illescas Quiroga (Col. MAD00274)
=============================================================================
Garantiza que ningún bono quede huérfano y que todo comprador sea dado de alta
o verificado automáticamente en la base de datos de pacientes (clients).
=============================================================================
"""

import re
import sqlite3
import unicodedata
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

# Lista de nombres propios compuestos habituales en España (sin tildes para búsqueda normalizada)
COMPOUND_SPANISH_NAMES = [
    "juan carlos", "jose carlos", "jose joaquin", "jose antonio", "jose manuel", "jose luis",
    "jose maria", "juan antonio", "juan jose", "juan manuel", "juan luis", "miguel angel",
    "maria del carmen", "maria carmen", "maria del pilar", "maria pilar", "maria dolores",
    "maria teresa", "maria jose", "maria isabel", "maria luisa", "maria jesus", "maria angeles",
    "maria fe", "ana maria", "ana belen", "ana isabel", "francisco javier", "francisco jose",
    "francisco de paula", "victor manuel", "luis miguel", "carlos alberto", "angel luis",
    "pedro jose", "pedro antonio"
]

def strip_accents(text: str) -> str:
    """Elimina tildes y diacríticos para comparaciones robustas."""
    if not text:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )

def normalize_phone(phone: Optional[str]) -> str:
    """Extrae los últimos 9 dígitos numéricos del teléfono para búsqueda uniforme."""
    if not phone:
        return ""
    digits = re.sub(r"[^0-9]", "", str(phone))
    return digits[-9:] if len(digits) >= 9 else digits

def split_spanish_fullname(fullname: str) -> Tuple[str, str]:
    """
    Separa de forma inteligente el nombre de pila y los apellidos en el contexto español.
    Respeta nombres compuestos como 'José Joaquín', 'María del Carmen', etc.
    """
    clean = re.sub(r"\s+", " ", (fullname or "").strip())
    # Eliminar posibles notas entre corchetes o tras guión largo
    clean = re.sub(r"\s*[-/].*$", "", clean).strip()

    if not clean:
        return ("", "")

    unaccented_lower = strip_accents(clean).lower()

    # Comprobar nombres compuestos
    for c_name in COMPOUND_SPANISH_NAMES:
        if unaccented_lower.startswith(c_name + " ") or unaccented_lower == c_name:
            fname = clean[:len(c_name)].strip()
            lname = clean[len(c_name):].strip()
            return (fname, lname)

    parts = clean.split(" ")
    if len(parts) == 1:
        return (parts[0], "")
    else:
        return (parts[0], " ".join(parts[1:]))

def find_or_create_client_for_bono(
    conn: sqlite3.Connection,
    client_name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    address: Optional[str] = None,
    order_id: Optional[str] = None,
    tipo_bono: Optional[str] = None
) -> Tuple[int, bool, str]:
    """
    Comprueba si el cliente ya está dado de alta en la tabla 'clients'.
    Si no está dado de alta, lo registra automáticamente con los datos del bono.
    
    Retorna: (client_id, was_created, mensaje)
    """
    cursor = conn.cursor()
    c_name_clean = re.sub(r"\s+", " ", (client_name or "").strip())
    email_clean = (email or "").strip().lower()
    phone_clean = (phone or "").strip()
    phone_norm = normalize_phone(phone_clean)

    existing_client = None

    # 1. Búsqueda por Email (la clave más unívoca si existe)
    if email_clean:
        cursor.execute("SELECT id, firstname, lastname, fullname, email, phone FROM clients WHERE LOWER(email) = LOWER(?)", (email_clean,))
        existing_client = cursor.fetchone()

    # 2. Búsqueda por Nombre Completo exacto
    if not existing_client and c_name_clean:
        cursor.execute("SELECT id, firstname, lastname, fullname, email, phone FROM clients WHERE LOWER(fullname) = LOWER(?)", (c_name_clean,))
        existing_client = cursor.fetchone()

    # 3. Búsqueda por Teléfono normalizado (si se proporcionó teléfono)
    if not existing_client and phone_norm and len(phone_norm) == 9:
        cursor.execute("""
            SELECT id, firstname, lastname, fullname, email, phone 
            FROM clients 
            WHERE phone IS NOT NULL AND phone != ''
        """)
        for r in cursor.fetchall():
            if normalize_phone(r["phone"]) == phone_norm:
                existing_client = r
                break

    # 4. Búsqueda por coincidencia aproximada de nombre de pila + primer apellido
    if not existing_client and c_name_clean:
        parts = c_name_clean.split()
        if len(parts) >= 2:
            cursor.execute("""
                SELECT id, firstname, lastname, fullname, email, phone 
                FROM clients 
                WHERE (fullname LIKE ? AND fullname LIKE ?)
                   OR (firstname LIKE ? AND lastname LIKE ?)
            """, (f"%{parts[0]}%", f"%{parts[1]}%", f"%{parts[0]}%", f"%{parts[1]}%"))
            candidates = cursor.fetchall()
            for cand in candidates:
                cand_lower = (cand["fullname"] or "").lower()
                if parts[0].lower() in cand_lower and parts[1].lower() in cand_lower:
                    existing_client = cand
                    break

    # --- SI EL CLIENTE YA EXISTE ---
    if existing_client:
        c_id = existing_client["id"]
        # Enriquecer datos que estuvieran vacíos
        needs_update = False
        updates = []
        params = []

        if not existing_client["email"] and email_clean:
            updates.append("email = ?")
            params.append(email_clean)
            needs_update = True

        if not existing_client["phone"] and phone_clean:
            updates.append("phone = ?")
            params.append(phone_clean)
            needs_update = True

        if needs_update:
            params.append(c_id)
            cursor.execute(f"UPDATE clients SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()

        return (c_id, False, f"Cliente existente verificado (ID: {c_id})")

    # --- SI EL CLIENTE NO EXISTE: DAR DE ALTA AUTOMÁTICAMENTE ---
    fname, lname = split_spanish_fullname(c_name_clean)
    today_note = f"Alta automática al registrar bono #{order_id or 'S/N'}"
    if tipo_bono:
        today_note += f" ({tipo_bono})"
    today_note += f" el {datetime.now().strftime('%d/%m/%Y %H:%M')}"

    cursor.execute("""
        INSERT INTO clients (firstname, lastname, fullname, email, phone, address, note)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        fname,
        lname,
        c_name_clean,
        email_clean if email_clean else None,
        phone_clean if phone_clean else None,
        address if address else None,
        today_note
    ))
    new_client_id = cursor.lastrowid
    conn.commit()

    return (new_client_id, True, f"Nuevo cliente dado de alta automáticamente (ID: {new_client_id})")

def auto_link_bono_to_pending_appointment(
    conn: sqlite3.Connection,
    client_id: int,
    bono_id: int,
    order_id: str,
    client_name: str
) -> Optional[Dict[str, Any]]:
    """
    Si el deportista tenía alguna consulta en estado 'Pendiente de Bono',
    vincula automáticamente este nuevo bono a esa consulta, la marca como 'Completada'
    y descuenta la primera sesión en el bono (used_sessions = 1).
    """
    cursor = conn.cursor()

    # Buscar la cita más reciente o próxima pendiente de bono para este cliente
    cursor.execute("""
        SELECT id, appointment_date, appointment_time, modality, service 
        FROM appointments 
        WHERE (client_id = ? OR LOWER(client_name) = LOWER(?))
          AND status = 'Pendiente de Bono'
        ORDER BY appointment_date DESC
        LIMIT 1
    """, (client_id, client_name.strip()))
    pending_appt = cursor.fetchone()

    if not pending_appt:
        return None

    appt_id = pending_appt["id"]

    # 1. Asociar el bono a la cita y completarla
    cursor.execute("""
        UPDATE appointments 
        SET bono_id = ?, status = 'Completada' 
        WHERE id = ?
    """, (bono_id, appt_id))

    # 2. Imputar 1 sesión al bono recién creado
    cursor.execute("SELECT total_sessions, used_sessions FROM bonos WHERE id = ?", (bono_id,))
    bono_row = cursor.fetchone()
    if bono_row:
        new_used = bono_row["used_sessions"] + 1
        new_status = "Completado" if new_used >= bono_row["total_sessions"] else "Activo"
        cursor.execute("UPDATE bonos SET used_sessions = ?, status = ? WHERE id = ?", (new_used, new_status, bono_id))

    conn.commit()

    return {
        "appointment_id": appt_id,
        "date": pending_appt["appointment_date"],
        "time": pending_appt["appointment_time"],
        "message": f"Consulta del {pending_appt['appointment_date']} regularizada automáticamente con el bono #{order_id}."
    }
