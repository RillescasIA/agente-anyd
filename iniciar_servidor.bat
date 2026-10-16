@echo off
title Servidor de Reservas ANyD Nutricionistas
echo ========================================================
echo        ANyD Nutricionistas - Servidor de Reservas
echo ========================================================
echo.
echo MENU PRINCIPAL (CENTRAL): http://localhost:8080/
echo.
echo Modulos directos:
echo   - Panel de Administracion: http://localhost:8080/admin
echo   - Portal de Reservas:      http://localhost:8080/reservar
echo   - Bascula Tanita MC-580:   http://localhost:8080/tanita
echo   - Documentacion API:       http://localhost:8080/docs
echo.
echo Presiona Ctrl + C para detener el servidor.
echo.
"C:\Users\Roman\AppData\Local\Programs\Python\Python315-arm64\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload
pause
