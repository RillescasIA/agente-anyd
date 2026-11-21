# -*- coding: utf-8 -*-
import os
import openpyxl
import sqlite3
import re
from datetime import datetime

import crm_manager
import excel_manager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_EXCEL = r"G:\Mi unidad\1.- ANyD\Bonos activos_claude.xlsx"
EXCEL_PATH = os.environ.get("EXCEL_PATH", DEFAULT_EXCEL)
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "anyd_booking.db"))

def determine_total_sessions(tipo_bono):
    return excel_manager.determine_num_sessions(tipo_bono)

def sync_active_bonos(file_path=None):
    target_file = file_path or EXCEL_PATH
    if not os.path.exists(target_file):
        raise FileNotFoundError(
            f"No se encontró el archivo '{target_file}'. Si estás en la nube (Render), utiliza el botón para subir el archivo 'Bonos activos_claude.xlsx' o sincroniza desde tu ordenador local (http://localhost:8080)."
        )

    wb = openpyxl.load_workbook(target_file, data_only=True, read_only=True)
    sheet = wb["Bonos activos"]

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    synced = 0
    for r_idx, row in enumerate(sheet.iter_rows(values_only=True)):
        if r_idx == 0 or not row or len(row) < 7:
            continue

        centro = row[0]
        nombre = row[1]
        tipo_bono = row[2]
        fecha_compra = row[3]
        n_pedido = str(row[4]).strip() if row[4] is not None else ""
        importe = row[5]
        activo = str(row[6] or "").strip()
        forma_pago = row[7] if len(row) > 7 else ""
        nutri = (row[8] if len(row) > 8 else None) or "Román"

        if not nombre or activo not in ["Activo", "p", "P"]:
            continue

        total_sessions = determine_total_sessions(tipo_bono)
        used_sessions = 0

        for c_idx in range(9, min(16, len(row))):
            val = row[c_idx]
            if val and str(val).strip():
                used_sessions += 1

        p_date_str = ""
        if isinstance(fecha_compra, datetime):
            p_date_str = fecha_compra.strftime("%Y-%m-%d")
        elif fecha_compra and str(fecha_compra).strip():
            p_date_str = str(fecha_compra).strip()[:10]

        order_key = n_pedido if (n_pedido and n_pedido != "--") else f"MANUAL_{r_idx}"

        client_id, _, _ = crm_manager.find_or_create_client_for_bono(
            conn=conn,
            client_name=str(nombre).strip(),
            order_id=order_key,
            tipo_bono=str(tipo_bono or "Deportiva 3")
        )

        try:
            price_val = float(str(importe).replace(",", ".")) if importe is not None and str(importe).strip() != "" else 0.0
        except Exception:
            price_val = 0.0

        status_val = "Completado" if used_sessions >= total_sessions else "Activo"

        cursor.execute("""
        INSERT INTO bonos (order_id, client_id, client_name, tipo_bono, total_sessions, used_sessions, purchase_date, price, status, centro, forma_pago, nutri)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(order_id) DO UPDATE SET
            client_id = COALESCE(bonos.client_id, excluded.client_id),
            client_name = excluded.client_name,
            tipo_bono = excluded.tipo_bono,
            total_sessions = excluded.total_sessions,
            used_sessions = MAX(bonos.used_sessions, excluded.used_sessions),
            purchase_date = CASE WHEN excluded.purchase_date != '' THEN excluded.purchase_date ELSE bonos.purchase_date END,
            price = CASE WHEN excluded.price > 0 THEN excluded.price ELSE bonos.price END,
            centro = excluded.centro,
            forma_pago = CASE WHEN excluded.forma_pago != '' THEN excluded.forma_pago ELSE bonos.forma_pago END,
            status = CASE WHEN MAX(bonos.used_sessions, excluded.used_sessions) >= excluded.total_sessions THEN 'Completado' ELSE bonos.status END
        """, (
            order_key,
            client_id,
            str(nombre).strip(),
            str(tipo_bono or "Deportiva 3").strip(),
            total_sessions,
            used_sessions,
            p_date_str,
            price_val,
            status_val,
            str(centro).strip() if centro else "ANYD",
            str(forma_pago).strip() if forma_pago else "Online",
            str(nutri).strip()
        ))
        synced += 1

    # Sincronizar bonos que pasaron a 'Bonos agotados' en Excel para marcarlos como Completado en SQLite
    if "Bonos agotados" in wb.sheetnames:
        sh_agotados = wb["Bonos agotados"]
        for r_idx, row in enumerate(sh_agotados.iter_rows(min_row=2, max_row=80, max_col=8, values_only=True)):
            if not row or len(row) < 5:
                continue
            ped_agotado = str(row[4] or "").strip()
            if ped_agotado and ped_agotado != "--":
                cursor.execute("""
                    UPDATE bonos
                    SET status = 'Completado', used_sessions = total_sessions
                    WHERE order_id = ? AND status = 'Activo'
                """, (ped_agotado,))

    wb.close()
    conn.commit()
    conn.close()
    print(f"Sincronizados {synced} bonos activos de '{target_file}' con la base de datos.")
    return synced

if __name__ == "__main__":
    sync_active_bonos()
