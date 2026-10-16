# Reglas y Arquitectura del Sistema — Agente ANyD

Este documento define la arquitectura técnica y el contexto operativo del sistema propio de gestión, reservas y antropometría para **ANyD Nutricionistas** (**Román Illescas Quiroga**, Col. MAD00274 — Web: [anyd.es](https://anyd.es)).

---

## 1. Módulos y Arquitectura del Ecosistema

1. **Servidor Backend (FastAPI)**:
   - [`main.py`](file:///g:/Mi%20unidad/1.-%20IA/IA%20Gemini/Agente%20anyd/main.py): Orquestador central de endpoints REST, renderizado de plantillas Jinja2, gestión de eventos y sincronización.
   - Base de datos SQLite: [`anyd_booking.db`](file:///g:/Mi%20unidad/1.-%20IA/IA%20Gemini/Agente%20anyd/anyd_booking.db) (`clients`, `bonos`, `appointments`, `tanita_measurements`).
   - Configuración: [`config.json`](file:///g:/Mi%20unidad/1.-%20IA/IA%20Gemini/Agente%20anyd/config.json).

2. **Sincronización con Excel en Google Drive**:
   - [`excel_manager.py`](file:///g:/Mi%20unidad/1.-%20IA/IA%20Gemini/Agente%20anyd/excel_manager.py): Conexión bidireccional con `G:\Mi unidad\1.- ANyD\Bonos activos_claude.xlsx`.
   - Al marcar asistencia: estampa `Román DD/MM/AAAA` en la primera consulta vacía.
   - Al completar la última sesión: traslada automáticamente la fila a la hoja `Bonos agotados`.
   - Copias de seguridad automáticas antes de cada escritura en `backups/`.

3. **Receptor Hardware Tanita MC-580**:
   - [`tanita_receiver.py`](file:///g:/Mi%20unidad/1.-%20IA/IA%20Gemini/Agente%20anyd/tanita_receiver.py): Monitor serie en tiempo real (COM USB, 9600 baudios) y lector de volcados CSV desde tarjeta SD.
   - Cálculo del Gasto Metabólico Basal (BMR) mediante la fórmula de **Cunningham (1980/1991)**:
     $$\text{BMR (kcal/día)} = 500 + 22 \times \text{FFM (kg)}$$

4. **Sincronización con Google Calendar y WhatsApp**:
   - Endpoint `/calendar.ics` y `/api/calendar/export.ics` para suscripción en vivo en Google Calendar (móvil y PC).
   - Generación de enlaces de WhatsApp directos (`wa.me`) con plantillas predefinidas para confirmaciones y recordatorios.

5. **Automatizaciones y Correo Transaccional**:
   - [`email_service.py`](file:///g:/Mi%20unidad/1.-%20IA/IA%20Gemini/Agente%20anyd/email_service.py): Plantillas HTML corporativas con diseño de `anyd.es`.
   - [`scheduler.py`](file:///g:/Mi%20unidad/1.-%20IA/IA%20Gemini/Agente%20anyd/scheduler.py): Cron que detecta citas a 48h (2 días antes) y envía recordatorio con instrucciones de pesaje/consulta.
   - Endpoint `/api/webhook/woocommerce`: Escucha `order.completed` para altas automáticas de bonos y clientes.

6. **Interfaces de Usuario (Templates Jinja2)**:
   - [`templates/admin.html`](file:///g:/Mi%20unidad/1.-%20IA/IA%20Gemini/Agente%20anyd/templates/admin.html): Cuadrante semanal interactivo estilo Reservio, Drag & Drop, duraciones variables, ficha clínica del paciente y sincronización.
   - [`templates/reservar.html`](file:///g:/Mi%20unidad/1.-%20IA/IA%20Gemini/Agente%20anyd/templates/reservar.html): Portal web para deportistas integrado con el branding de `anyd.es` y botón directo de Google Calendar.
   - [`templates/tanita.html`](file:///g:/Mi%20unidad/1.-%20IA/IA%20Gemini/Agente%20anyd/templates/tanita.html): Panel de monitorización y captura en directo de bioimpedancia Tanita MC-580.

---

## 2. Directrices Clínicas ANyD Nutricionistas

Al prescribir, aconsejar o generar planes:
- **Carne roja**: Máximo 1-2 tomas por semana (<500g cocida semanal). Cero embutidos ni procesados.
- **Legumbres**: Mínimo 4 tomas semanales de legumbres (garbanzos, lentejas, alubias, edamame).
- **Cereales**: 100% integrales, excepto en la ventana peri-entreno (donde se priorizan refinados para acelerar vaciamiento gástrico).
- **Consistencia de hidratos**: Raciones estables (variación máxima $\pm 10\text{ g}$ respecto a 70g secos o 250g cocidos).
- **Aceite de oliva virgen extra**: Medición estricta en cucharas (5g postre / 10-12g sopera).

---

## 3. Política Operativa de Duración de Consultas

- **Duración estándar por norma general**: **30 minutos** por consulta.
- **Flexibilidad y modificación**: Todas las consultas son 100% modificables en duración (15 min informativa, 30 min estándar, 45 min extendida, 60 min primera consulta/inicial, 90 min exhaustiva/competición), tanto desde el selector modal como estirando el borde inferior de la cita en el calendario (*drag & drop resize*).
- **Franjas de agendamiento**: Intervalos cada 30 minutos (10:00 a 13:30 y 16:00 a 20:00) con detección automática de colisiones y cálculo de solapamiento en minutos.
