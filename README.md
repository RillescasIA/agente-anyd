# Sistema Propio de Reservas y Gestión de Bonos — ANyD Nutricionistas

Sistema integral de gestión de citas, bonos deportivos y antropometría desarrollado a medida para **ANyD Nutricionistas** (**Román Illescas Quiroga**, Col. MAD00274 — Web: [anyd.es](https://anyd.es)).

Este sistema **sustituye de forma definitiva y completa a la plataforma de pago Reservio**, eliminando cuotas mensuales recurrentes y comisiones por volumen de citas.

---

## 🌟 Resumen de Capacidades

1. **Calendario Semanal Interactivo (`/admin`)**:
   - Réplica exacta de la interfaz visual de Reservio (cuadrante de lunes a domingo de 09:00 a 22:00).
   - **Arrastrar y Soltar (*Drag & Drop*)**: Mueve citas libremente entre días y horas con confirmación flotante instantánea.
   - **Duración Variable y Redimensión**: Modifica la duración (15, 30, 45, 60, 90 min) estirando el borde inferior de la cita o desde el modal.
   - Código de colores por servicio (*Nutrición Deportiva, OnLine, Clínica, CF Catedral, Tracius*).
   - Botón directo para marcar asistencia e inscribir la sesión en el Excel.

2. **Portal Web de Reservas para Deportistas (`/reservar`)**:
   - Interfaz 100% responsive adaptada al diseño oficial de `anyd.es` (paleta `#0086cd`, `#101218`, tipografías Montserrat y Lato).
   - Validación instantánea por correo electrónico del deportista.
   - Comprobación de saldo de bonos en tiempo real: si no dispone de bono activo, le redirige a la tienda de `anyd.es`.
   - Embebible vía `iframe` en `anyd.es/reservar`.

3. **Receptor Directo para Báscula Tanita MC-580 (`/tanita`)**:
   - Conexión USB directa en tiempo real mediante puerto COM virtual (9600 baudios).
   - Zona de importación para archivos CSV de tarjetas SD.
   - Cálculo clínico instantáneo del Gasto Metabólico Basal (BMR/TMB) mediante la **fórmula Cunningham (1980/1991)**: $\text{BMR} = 500 + 22 \times \text{FFM}$.
   - Registro histórico de mediciones vinculado al expediente del cliente.

4. **Sincronización Bidireccional con Excel en Google Drive**:
   - Conexión directa con `G:\Mi unidad\1.- ANyD\Bonos activos_claude.xlsx`.
   - Al marcar asistencia: estampa `Román DD/MM/AAAA` en la primera consulta libre.
   - Al agotar la última sesión: traslada automáticamente la fila a la hoja `Bonos agotados`.
   - Sistema de **copias de seguridad automáticas** antes de cada escritura en la carpeta `backups/`.

5. **Motor Webhook para WooCommerce (`anyd.es`)**:
   - Endpoint `/api/webhook/woocommerce` que escucha eventos `order.completed`.
   - Crea automáticamente el cliente, da de alta el bono en el Excel y la base de datos, y envía el correo con enlace único de reserva.

6. **Servicio Automatizado de Recordatorios a 48h**:
   - Notificación por correo electrónico 2 días antes de la cita con instrucciones, dirección física o enlace de videollamada.

7. **Sincronización Directa con Google Calendar (`/calendar.ics`)**:
   - Feed oficial iCalendar RFC 5545 para suscripción en vivo en Google Calendar (Android / iPhone / PC).
   - Botón directo "Añadir a mi Google Calendar" en la confirmación de reserva para el deportista.

8. **Ficha Clínica del Deportista y Mensajería WhatsApp**:
   - Consulta instantánea de historial de citas, asistencias, bonos y pesajes de la Tanita MC-580 desde el cuadrante.
   - Botón de WhatsApp integrado (`wa.me`) con plantillas predefinidas para confirmaciones y recordatorios inmediatos.

---

## 🚀 Inicio Rápido

### Opción A: Con el lanzador de Windows (Recomendada)
Haz doble clic en el archivo:
```text
iniciar_servidor.bat
```
Se abrirá la consola y el servidor estará activo en `http://localhost:8080`.

### Opción B: Mediante PowerShell o Terminal
```powershell
& "C:\Users\Roman\AppData\Local\Programs\Python\Python315-arm64\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

---

## 📌 Enlaces de Acceso y Producción

| Módulo | Enlace Local (PC) | Enlace Nube (Render) | Descripción |
| :--- | :--- | :--- | :--- |
| **🏠 Menú Central Hub** | [http://localhost:8000/](http://localhost:8000/) | [https://agente-anyd.onrender.com/](https://agente-anyd.onrender.com/) | Portal de entrada unificado con acceso a todos los módulos. |
| **📅 Calendario / Admin** | [http://localhost:8000/admin](http://localhost:8000/admin) | [https://agente-anyd.onrender.com/admin](https://agente-anyd.onrender.com/admin) | Cuadrante semanal estilo Reservio, drag & drop, asistencias y bonos. |
| **🎟️ Histórico / Bonos** | [http://localhost:8000/admin?tab=past](http://localhost:8000/admin?tab=past) | [https://agente-anyd.onrender.com/admin?tab=past](https://agente-anyd.onrender.com/admin?tab=past) | Listado de citas pasadas y estado de bonos activos sincronizados. |
| **🔗 Portal de Reservas** | [http://localhost:8000/reservar](http://localhost:8000/reservar) | [https://agente-anyd.onrender.com/reservar](https://agente-anyd.onrender.com/reservar) | Portal público donde el deportista reserva con su email. |
| **⚖️ Báscula Tanita MC-580**| [http://localhost:8000/tanita](http://localhost:8000/tanita) | [https://agente-anyd.onrender.com/tanita](https://agente-anyd.onrender.com/tanita) | Monitor en vivo USB/COM y lector de tarjetas SD Tanita. |
| **📲 Feed Google Calendar** | [http://localhost:8000/calendar.ics](http://localhost:8000/calendar.ics) | [https://agente-anyd.onrender.com/calendar.ics](https://agente-anyd.onrender.com/calendar.ics) | Feed oficial iCal para suscripción en Google Calendar. |
| **📖 Swagger / API Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | [https://agente-anyd.onrender.com/docs](https://agente-anyd.onrender.com/docs) | Documentación interactiva de todos los endpoints REST. |

---

## 📁 Estructura del Proyecto

```text
g:\Mi unidad\1.- IA\IA Gemini\Agente anyd\
│
├── main.py                               # Servidor principal FastAPI y endpoints de la API
├── sync_reservio_feed.py                 # Sincronizador en caliente del feed oficial iCal de Reservio
├── excel_manager.py                      # Motor de lectura/escritura del Excel de Google Drive y copias
├── tanita_receiver.py                    # Módulo de lectura serie COM y parseo CSV de la Tanita MC-580
├── email_service.py                      # Plantillas HTML y envío de emails transaccionales
├── scheduler.py                          # Cron en segundo plano para recordatorios de citas a 48h
├── config.json                           # Configuración de servidor, correo SMTP y rutas
├── iniciar_servidor.bat                  # Lanzador rápido en 1 clic para Windows
│
├── anyd_booking.db                       # Base de datos SQLite (2.923 citas, 390 clientes)
│
├── templates/                            # Plantillas HTML Jinja2
│   ├── index.html                        # Portal central (Hub de bienvenida)
│   ├── admin.html                        # Cuadrante semanal FullCalendar 6 (estilo Reservio)
│   ├── reservar.html                     # Portal de reservas branding anyd.es
│   └── tanita.html                       # Interfaz de pesaje en directo Tanita MC-580
│
├── backups/                              # Copias de seguridad automáticas de la BD y Excel
├── PLAN_TRANSICION_Y_AUDITORIA_RESERVIO.md # Auditoría operativa y hoja de ruta para sustituir Reservio
├── README.md                             # Documentación general del sistema
├── CONFIGURACION.md                      # Guía de configuración (WooCommerce, SMTP, Tanita)
└── ACCESOS_Y_RUTAS.md                    # Hoja de referencia de accesos y endpoints
```
