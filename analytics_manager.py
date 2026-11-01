# -*- coding: utf-8 -*-
"""
=============================================================================
MOTOR DE ANALÍTICA, INGRESOS Y SESIONES · AGENTE ANYD NUTRICIONISTAS
Román Illescas Quiroga (Col. MAD00274)
=============================================================================
Cálculo de métricas de rendimiento clínico y financiero:
1. Criterio de Caja Cobrada (Fecha de compra de bonos).
2. Criterio de Producción por Sesión Impartida (Fecha de consulta completada).
3. Agrupación temporal: Mensual y Semanal.
4. Recordatorios de Cita a 48h (Anticipo a Viernes si cae en Fin de Semana).
   * REGLA CLÍNICA: No se envía ningún aviso comercial o de agotamiento de bono
     al deportista para evitar intromisión o sensación de persecución.
=============================================================================
"""

import sqlite3
import os
from datetime import datetime, timedelta

import scheduler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "anyd_booking.db"))

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_financial_and_sessions_analytics(period="month", limit=12):
    """
    Calcula simultáneamente:
    - Caja cobrada (Ingresos brutos por venta de bonos en el periodo).
    - Producción devengada (Sesiones asistidas * precio/sesión).
    - Conteo de sesiones semanales y mensuales.
    - Listado de recordatorios de cita debidos hoy (48h / regla viernes).
    """
    conn = get_db_connection()
    c = conn.cursor()

    time_format_sql = "%Y-%m" if period == "month" else "%Y-W%W"

    # 1. Caja cobrada por periodo (ventas de bonos)
    c.execute(f"""
        SELECT 
            strftime('{time_format_sql}', purchase_date) as periodo,
            COUNT(id) as bonos_vendidos,
            ROUND(SUM(COALESCE(price, 0)), 2) as caja_total
        FROM bonos
        WHERE purchase_date IS NOT NULL AND purchase_date != ''
        GROUP BY periodo
        ORDER BY periodo DESC
        LIMIT ?
    """, (limit,))
    caja_rows = {r["periodo"]: {"bonos_vendidos": r["bonos_vendidos"], "caja_total": r["caja_total"]} for r in c.fetchall()}

    # 2. Producción y Sesiones impartidas por periodo (citas completadas/asistidas)
    c.execute(f"""
        SELECT 
            strftime('{time_format_sql}', a.appointment_date) as periodo,
            COUNT(a.id) as sesiones_totales,
            SUM(CASE WHEN a.status IN ('Completada', 'Asistida') OR a.appointment_date < date('now') THEN 1 ELSE 0 END) as sesiones_realizadas,
            SUM(CASE WHEN a.status = 'Cancelada' THEN 1 ELSE 0 END) as sesiones_canceladas,
            SUM(CASE WHEN a.modality = 'Presencial' THEN 1 ELSE 0 END) as sesiones_presenciales,
            SUM(CASE WHEN a.modality != 'Presencial' THEN 1 ELSE 0 END) as sesiones_online,
            ROUND(SUM(
                CASE 
                    WHEN a.status IN ('Completada', 'Asistida') OR a.appointment_date < date('now') THEN
                        COALESCE(b.price / NULLIF(b.total_sessions, 0), 55.0)
                    ELSE 0
                END
            ), 2) as produccion_total
        FROM appointments a
        LEFT JOIN bonos b ON a.bono_id = b.id
        WHERE a.appointment_date IS NOT NULL AND a.appointment_date != ''
        GROUP BY periodo
        ORDER BY periodo DESC
        LIMIT ?
    """, (limit,))
    sesiones_rows = {r["periodo"]: dict(r) for r in c.fetchall()}

    # Unificar periodos cronológicos
    all_periods = sorted(list(set(list(caja_rows.keys()) + list(sesiones_rows.keys()))), reverse=True)[:limit]

    unified_report = []
    for p in all_periods:
        caja_info = caja_rows.get(p, {"bonos_vendidos": 0, "caja_total": 0.0})
        ses_info = sesiones_rows.get(p, {
            "sesiones_totales": 0,
            "sesiones_realizadas": 0,
            "sesiones_canceladas": 0,
            "sesiones_presenciales": 0,
            "sesiones_online": 0,
            "produccion_total": 0.0
        })

        unified_report.append({
            "periodo": p,
            "caja_total": caja_info["caja_total"],
            "bonos_vendidos": caja_info["bonos_vendidos"],
            "produccion_total": ses_info["produccion_total"],
            "sesiones_realizadas": ses_info["sesiones_realizadas"],
            "sesiones_totales": ses_info["sesiones_totales"],
            "sesiones_canceladas": ses_info["sesiones_canceladas"],
            "presenciales": ses_info["sesiones_presenciales"],
            "online": ses_info["sesiones_online"]
        })

    # 3. Estado interno de Bonos (Contabilidad interna clínica, sin perseguir al paciente)
    c.execute("SELECT COUNT(*) FROM bonos WHERE status = 'Activo'")
    bonos_activos = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM bonos WHERE status != 'Activo' OR used_sessions >= total_sessions")
    bonos_agotados = c.fetchone()[0]

    conn.close()

    # 4. Recordatorios de Cita a 48h (Regla de fin de semana: lunes/martes avisados el viernes)
    pending_reminders = scheduler.get_pending_reminders_for_today()

    return {
        "period": period,
        "report": unified_report,
        "bonos_summary": {
            "activos": bonos_activos,
            "agotados": bonos_agotados
        },
        "pending_reminders": pending_reminders,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
