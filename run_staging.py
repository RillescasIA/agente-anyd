# -*- coding: utf-8 -*-
"""
Lanzador del Entorno de Pruebas (Staging) · Agente ANyD Nutricionistas
Puerto: 8001
Base de datos: anyd_booking_test.db (100% aislada)
Excel: Bonos_activos_TEST.xlsx (100% aislado)
Notificaciones en vivo: DESACTIVADAS (DRY-RUN / SANDBOX)
"""

import os
import sys
import uvicorn

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configurar variables de entorno aisladas para Staging
os.environ["ENV"] = "staging"
os.environ["DB_PATH"] = os.path.join(BASE_DIR, "anyd_booking_test.db")
os.environ["EXCEL_PATH"] = os.path.join(BASE_DIR, "Bonos_activos_TEST.xlsx")
os.environ["ENABLE_LIVE_EMAIL"] = "false"
os.environ["SANDBOX_MODE"] = "true"

print("=" * 70)
print("  🚀 ARRANCANDO AGENTE ANYD EN ENTORNO DE PRUEBAS (STAGING)")
print("=" * 70)
print(f"  • URL Staging:       http://localhost:8001")
print(f"  • Base de Datos:     {os.environ['DB_PATH']}")
print(f"  • Excel de Pruebas:  {os.environ['EXCEL_PATH']}")
print(f"  • Notificaciones:    DESACTIVADAS (Modo Pruebas / Dry-Run)")
print("=" * 70)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)
