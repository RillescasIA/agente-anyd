# -*- coding: utf-8 -*-
"""
Script de inicialización de datos para el Entorno de Pruebas (Staging).
Crea 'anyd_booking_test.db' y 'Bonos_activos_TEST.xlsx' con deportistas y citas ficticias
para pruebas 100% aisladas sin riesgo de contactar ni alterar datos reales.
"""

import sqlite3
import os
import shutil
from datetime import datetime, timedelta
import openpyxl

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DB_PATH = os.path.join(BASE_DIR, "anyd_booking_test.db")
REAL_DB_PATH = os.path.join(BASE_DIR, "anyd_booking.db")
TEST_EXCEL_PATH = os.path.join(BASE_DIR, "Bonos_activos_TEST.xlsx")
REAL_EXCEL_PATH = r"G:\Mi unidad\1.- ANyD\Bonos activos_claude.xlsx"

def setup_test_database():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
        print(f"Base de datos de pruebas anterior eliminada: {TEST_DB_PATH}")

    # Copiar estructura desde real
    real_conn = sqlite3.connect(REAL_DB_PATH)
    real_c = real_conn.cursor()
    real_c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL AND name != 'sqlite_sequence'")
    table_sqls = [r[0] for r in real_c.fetchall()]
    real_conn.close()

    test_conn = sqlite3.connect(TEST_DB_PATH)
    test_c = test_conn.cursor()

    for sql in table_sqls:
        test_c.execute(sql)

    # Insertar 3 pacientes sintéticos de prueba
    test_clients = [
        ("Carlos", "Alcaraz Test", "Carlos Alcaraz Test", "alcaraz.test@anyd.es", "+34600000001", "Tenista profesional de prueba", 1, "2026-10-15 10:00:00", "WhatsApp", "Consentimiento WhatsApp: 'ACEPTO'"),
        ("Marta", "García Test", "Marta García Test", "marta.test@anyd.es", "+34600000002", "Triatleta popular de prueba", 0, None, None, None),
        ("Pablo", "Carreño Test", "Pablo Carreño Test", "pablo.test@anyd.es", "+34600000003", "Corredor de trail de prueba", 1, "2026-10-20 12:30:00", "WhatsApp", "Consentimiento WhatsApp: 'ACEPTO'")
    ]

    for tc in test_clients:
        test_c.execute("""
            INSERT INTO clients (firstname, lastname, fullname, email, phone, note, rgpd_accepted, rgpd_date, rgpd_channel, rgpd_evidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, tc)

    # Insertar bonos de prueba
    test_bonos = [
        ("TEST-9001", 1, "Carlos Alcaraz Test", "alcaraz.test@anyd.es", "Deportiva 3", 3, 1, "2026-10-10", 159.0, "Activo", "ANYD", "Online", "Román"),
        ("TEST-9002", 2, "Marta García Test", "marta.test@anyd.es", "Deportiva 5", 5, 2, "2026-10-12", 249.0, "Activo", "ANYD", "Transferencia", "Román"),
        ("TEST-9003", 3, "Pablo Carreño Test", "pablo.test@anyd.es", "Deportiva 3", 3, 3, "2026-09-01", 159.0, "Agotado", "ANYD", "Online", "Román")
    ]

    for tb in test_bonos:
        test_c.execute("""
            INSERT INTO bonos (order_id, client_id, client_name, client_email, tipo_bono, total_sessions, used_sessions, purchase_date, price, status, centro, forma_pago, nutri)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, tb)

    # Insertar citas de prueba (hoy + 2 días, hoy + 3 días)
    d1 = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    d2 = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")

    test_appointments = [
        (1, 1, "Carlos Alcaraz Test", "alcaraz.test@anyd.es", "+34600000001", d1, "17:00", "Presencial", "Agendada", 0, "Anyd Nutrición Deportiva"),
        (2, 2, "Marta García Test", "marta.test@anyd.es", "+34600000002", d2, "18:30", "Online", "Agendada", 0, "Anyd Consulta OnLine")
    ]

    for ta in test_appointments:
        test_c.execute("""
            INSERT INTO appointments (bono_id, client_id, client_name, client_email, client_phone, appointment_date, appointment_time, modality, status, reminder_sent, service)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ta)

    # Insertar registro de trazabilidad RGPD en rgpd_consents
    test_c.execute("""
        INSERT INTO rgpd_consents (client_id, client_name, phone, channel, consent_type, status, patient_reply, timestamp)
        VALUES (1, 'Carlos Alcaraz Test', '+34600000001', 'WhatsApp', 'Datos de Salud y Planificación Nutricional', 'Aceptado', 'ACEPTO', '2026-10-15 10:00:00')
    """)

    test_conn.commit()
    test_conn.close()
    print("✓ Base de datos de pruebas inicializada con éxito (anyd_booking_test.db).")

def setup_test_excel():
    if os.path.exists(REAL_EXCEL_PATH):
        shutil.copy2(REAL_EXCEL_PATH, TEST_EXCEL_PATH)
        print(f"✓ Excel de pruebas creado como réplica exacta: {TEST_EXCEL_PATH}")
    else:
        # Crear estructura básica si no existe la ruta de G:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Bonos activos"
        ws.append(["Centro", "Nombre", "Tipo de bono", "Fecha compra", "Nº pedido", "Precio", "Estado", "Forma de pago", "Nutri", "Consulta 1", "Consulta 2", "Consulta 3"])
        ws.append(["ANYD", "Carlos Alcaraz Test", "Deportiva 3", "2026-10-10", "TEST-9001", 159, "Activo", "Online", "Román", "Román 12/10/2026", " ", " "])
        ws.append(["ANYD", "Marta García Test", "Deportiva 5", "2026-10-12", "TEST-9002", 249, "Activo", "Transferencia", "Román", "Román 15/10/2026", "Román 22/10/2026", " "])
        wb.save(TEST_EXCEL_PATH)
        wb.close()
        print(f"✓ Excel de pruebas creado desde cero: {TEST_EXCEL_PATH}")

if __name__ == "__main__":
    setup_test_database()
    setup_test_excel()
