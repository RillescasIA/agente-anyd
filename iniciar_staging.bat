@echo off
title Agente ANyD - Entorno de Pruebas (Staging)
cd /d "%~dp0"
echo ==========================================================
echo   Iniciando Agente ANyD en Entorno de Pruebas (Staging)
echo   Puerto: 8001
echo   URL: http://localhost:8001/admin
echo ==========================================================
python run_staging.py
pause
