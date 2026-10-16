# Hoja de Referencia: Accesos, Rutas y Endpoints API

Ficha técnica y mapa de rutas del sistema de reservas para **ANyD Nutricionistas**.

---

## 1. Rutas Locales del Sistema de Archivos

| Recurso | Ruta Absoluta |
| :--- | :--- |
| **Carpeta del Proyecto** | `G:\Mi unidad\1.- IA\IA Gemini\Agente anyd\` |
| **Excel Maestro (Google Drive)** | `G:\Mi unidad\1.- ANyD\Bonos activos_claude.xlsx` |
| **Carpeta de Backups del Excel** | `G:\Mi unidad\1.- IA\IA Gemini\Agente anyd\backups\` |
| **Base de Datos SQLite** | `G:\Mi unidad\1.- IA\IA Gemini\Agente anyd\anyd_booking.db` |
| **Archivo de Configuración** | `G:\Mi unidad\1.- IA\IA Gemini\Agente anyd\config.json` |
| **Lanzador por Lotes (Batch)** | `G:\Mi unidad\1.- IA\IA Gemini\Agente anyd\iniciar_servidor.bat` |
| **Exportación CSV de Reservio** | `C:\Users\Roman\Downloads\clients.csv` |
| **Intérprete Python (ARM64)** | `C:\Users\Roman\AppData\Local\Programs\Python\Python315-arm64\python.exe` |

---

## 2. Direcciones URL y Vistas del Sistema

| Vista | URL | Descripción |
| :--- | :--- | :--- |
| **Calendario / Admin** | `http://localhost:8080/admin` | Cuadrante semanal interactivo (estilo Reservio), drag & drop, duraciones y asistencias. |
| **Histórico / Bonos** | `http://localhost:8080/admin?tab=past` | Listado de citas pasadas y estado de bonos activos sincronizados. |
| **Portal de Reservas** | `http://localhost:8080/reservar` | Portal para que el deportista verifique su bono y reserve hora. |
| **Báscula Tanita MC-580** | `http://localhost:8080/tanita` | Monitor COM en directo y procesador CSV/SD con fórmula Cunningham. |
| **Documentación Swagger** | `http://localhost:8080/docs` | Interfaz interactiva para probar todos los endpoints REST en vivo. |
| **Documentación ReDoc** | `http://localhost:8080/redoc` | Documentación técnica detallada OpenAPI. |

---

## 3. Catálogo de Endpoints REST API

### Calendario y Cuadrante
- **`GET /api/calendar/events`**
  - **Parámetros:** `start` (opcional, YYYY-MM-DD), `end` (opcional, YYYY-MM-DD).
  - **Función:** Devuelve las citas en formato estándar FullCalendar con cálculo dinámico de hora fin según `duration_minutes` y colores por servicio.
- **`POST /api/calendar/reschedule`**
  - **Payload:** `{"id": int, "date": "YYYY-MM-DD", "time": "HH:MM", "duration_minutes": int}`
  - **Función:** Actualiza fecha, hora y duración tras arrastrar (*drag & drop*) o redimensionar una cita en el cuadrante.
- **`POST /api/manual-booking`**
  - **Payload:** `{"client_name": str, "client_email": str, "date": str, "time": str, "duration_minutes": int, "modality": str, "notes": str}`
  - **Función:** Da de alta una cita desde el botón `+ CREAR NUEVO` o haciendo clic en un hueco vacío.
- **`GET /calendar.ics` & `GET /api/calendar/export.ics`**
  - **Función:** Genera el feed oficial iCalendar (RFC 5545) para suscripción en tiempo real en Google Calendar (móvil y PC).
- **`GET /api/client-history?name=...&client_id=...`**
  - **Función:** Devuelve la ficha completa del deportista: datos de contacto, bonos activos/agotados, historial de citas asistidas y mediciones históricas de la Tanita MC-580.

### Portal de Reservas Atletas
- **`GET /api/check-client?email=correo@deportista.com`**
  - **Función:** Comprueba si el deportista tiene un bono activo con consultas disponibles y devuelve sus próximas citas y horas libres de Román.
- **`POST /api/book-appointment`**
  - **Payload:** `{"email": str, "date": str, "time": str, "modality": str, "notes": str}`
  - **Función:** Reserva cita oficial para el atleta, descuenta del cupo y envía email con recordatorio.

### Operativa y Asistencias
- **`POST /api/complete-appointment?id=123`**
  - **Función:** Marca la cita como asistida, descuenta 1 sesión en SQLite y estampa `Román DD/MM/AAAA` en `Bonos activos_claude.xlsx`. Si se agota el bono, traslada la fila a la hoja `Bonos agotados`.
- **`POST /api/cancel-appointment`**
  - **Payload:** `{"id": int}`
  - **Función:** Cancela la cita y libera el hueco en el calendario.
- **`POST /api/update-notes`**
  - **Payload:** `{"id": int, "notes": str}`
  - **Función:** Guarda observaciones clínicas de la sesión.

### Báscula Tanita MC-580
- **`GET /api/tanita/status`**
  - **Función:** Comprueba el estado de la conexión serie COM y devuelve la última medición registrada.
- **`POST /api/tanita/connect`**
  - **Payload:** `{"port": "COM3", "baudrate": 9600}`
  - **Función:** Abre el hilo de escucha continua en el puerto USB seleccionado.
- **`POST /api/tanita/disconnect`**
  - **Función:** Cierra el puerto serie de forma segura.
- **`POST /api/tanita/upload-csv`**
  - **Payload:** Formulario `multipart/form-data` con archivo `file` (.csv).
  - **Función:** Parsea el volcado de la tarjeta SD de la Tanita y calcula el BMR según Cunningham.

### Automatizaciones y Tienda
- **`POST /api/webhook/woocommerce`**
  - **Payload:** JSON del webhook de WooCommerce (`order.completed`).
  - **Función:** Da de alta el bono en el Excel y en SQLite, y envía correo con enlace para reservar.
- **`POST /api/run-reminders`**
  - **Función:** Ejecuta manualmente la comprobación de citas a 48h y envía los correos recordatorios.

---

## 4. Estructura de la Base de Datos (`anyd_booking.db`)

1. **`clients`**:
   - `id`, `reservio_id`, `fullname`, `email`, `phone`, `notes`, `created_at`.
   - *Poblada con los 380 clientes migrados de Reservio.*
2. **`bonos`**:
   - `id`, `order_id`, `client_id`, `client_name`, `client_email`, `tipo_bono`, `purchase_date`, `total_sessions`, `used_sessions`, `status`, `notes`.
   - *Sincronizada con la hoja 'Bonos activos' de Google Drive.*
3. **`appointments`**:
   - `id`, `bono_id`, `client_id`, `client_name`, `client_email`, `client_phone`, `appointment_date`, `appointment_time`, `duration_minutes`, `modality`, `status`, `reminder_sent`, `notes`, `created_at`.
   - *1.859 citas históricas y futuras registradas.*
4. **`tanita_measurements`**:
   - `id`, `client_name`, `measurement_date`, `weight_kg`, `fat_percent`, `fat_mass_kg`, `ffm_kg`, `muscle_mass_kg`, `tbw_kg`, `visceral_fat`, `bmr_cunningham`, `raw_data`.

---

## 5. Estructura del Excel (`Bonos activos_claude.xlsx`)

- **Hoja `Bonos activos`**:
  - Columnas: `Centro` | `Nombre` | `Tipo bono` | `Fecha compra` | `Nº Pedido` | `Importe` | `Activo` | `Forma pago` | `Nutri` | `1ª Consulta` | `2ª Consulta` | `3ª Consulta` | `4ª Consulta` | `5ª Consulta` | ...
  - Criterio de asistencia: Primera celda de consulta en blanco &rarr; escribe `Román DD/MM/AAAA`.
- **Hoja `Bonos agotados`**:
  - Al completar la última consulta del bono, la fila completa se extrae de `Bonos activos` y se traslada al final de `Bonos agotados`.
- **Copias de seguridad**:
  - Antes de cualquier escritura, el sistema guarda una copia con marca de tiempo en:
    `G:\Mi unidad\1.- IA\IA Gemini\Agente anyd\backups\Bonos_activos_backup_YYYYMMDD_HHMMSS.xlsx`.
