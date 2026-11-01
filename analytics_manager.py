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
4. Alertas de bonos próximos a agotarse (1 o 0 sesiones restantes).
=============================================================================
"""

import sqlite3
import os
from datetime import datetime, timedelta

import whatsapp_service

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

    # 3. Alertas de Bonos (1 sesión restante o 0 restantes)
    c.execute("""
        SELECT b.id, b.order_id, b.client_name, b.client_email, b.tipo_bono,
               b.total_sessions, b.used_sessions, (b.total_sessions - b.used_sessions) as remaining,
               b.purchase_date, c.phone
        FROM bonos b
        LEFT JOIN clients c ON b.client_id = c.id
        WHERE b.status = 'Activo' AND (b.total_sessions - b.used_sessions) <= 1
        ORDER BY remaining ASC, b.id DESC
    """)
    alerts_raw = c.fetchall()

    bono_alerts = []
    for r in alerts_raw:
        rem = r["remaining"]
        phone = r["phone"] or ""
        msg_type = "bono_warning" if rem == 1 else "bono_exhausted"
        wa_data = whatsapp_service.build_whatsapp_payload(
            client_name=r["client_name"],
            phone=phone,
            msg_type=msg_type,
            bono_type=r["tipo_bono"],
            remaining_sessions=rem,
            total_sessions=r["total_sessions"]
        )
        bono_alerts.append({
            "bono_id": r["id"],
            "order_id": r["order_id"],
            "client_name": r["client_name"],
            "phone": phone,
            "tipo_bono": r["tipo_bono"],
            "remaining": rem,
            "total_sessions": r["total_sessions"],
            "alert_type": "last_session" if rem == 1 else "exhausted",
            "whatsapp_link": wa_data["link"],
            "whatsapp_msg": wa_data["text"]
        })

    conn.close()

    return {
        "period": period,
        "report": unified_report,
        "bono_alerts": bono_alerts,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
