# Guía de Configuración e Integraciones — Sistema de Reservas ANyD

Este documento detalla paso a paso cómo configurar todas las conexiones externas e integraciones del sistema para **ANyD Nutricionistas**.

---

## 1. Configuración de Correo Electrónico (SMTP)

El sistema genera correos automáticos para:
- Confirmación instantánea de cita al deportista.
- Recordatorio de cita a 48 horas (2 días antes).
- Notificación de compra de bono con enlace de reserva.

### Archivo de configuración: `config.json`
Edita el archivo `config.json` en la raíz del proyecto para introducir tus credenciales:

```json
{
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "tu_correo@anyd.es",
    "smtp_password": "tu_contraseña_de_aplicacion",
    "sender_email": "info@anyd.es",
    "sender_name": "Román Illescas - ANyD Nutricionistas",
    "clinic_name": "ANyD Nutricionistas",
    "website_url": "https://anyd.es",
    "booking_url": "http://localhost:8080/reservar",
    "enable_live_email": true,
    "excel_path": "G:\\Mi unidad\\1.- ANyD\\Bonos activos_claude.xlsx",
    "backup_dir": "G:\\Mi unidad\\1.- IA\\IA Gemini\\Agente anyd\\backups",
    "tanita_default_baudrate": 9600
}
```

> [!TIP]
> **Si usas Gmail / Google Workspace:**
> 1. Ve a tu cuenta de Google &rarr; **Seguridad**.
> 2. Activa la verificación en 2 pasos.
> 3. En **Contraseñas de aplicaciones**, crea una nueva llamada *"Sistema Reservas"* y copia la clave de 16 caracteres en `"smtp_password"`.
> 4. Pon `"enable_live_email": true` para activar el envío real de correos.

---

## 2. Integración con WooCommerce (`anyd.es`)

Para que cada venta de bono en tu tienda WordPress cree automáticamente el cliente y sus sesiones en el Excel y en la base de datos:

1. Inicia sesión en el panel de control de WordPress en `https://anyd.es/wp-admin`.
2. En el menú lateral, dirígete a **WooCommerce** &rarr; **Ajustes**.
3. Haz clic en la pestaña superior **Avanzado** y luego en el submenú **Webhooks**.
4. Haz clic en el botón **Añadir Webhook**:
   - **Nombre:** `ANyD - Alta Bono y Reserva`
   - **Estado:** `Activo`
   - **Tema (Topic):** `Pedido completado` (o `order.completed`)
   - **URL de entrega:** `https://tudominio.es/api/webhook/woocommerce` *(ver sección 6 para exponer el servidor)*
   - **Secreto:** Puedes dejarlo en blanco o introducir una clave compartida.
   - **Versión de la API:** `API REST de WooCommerce v3`
5. Haz clic en **Guardar webhook**.

### ¿Qué hace el sistema al recibir el pedido?
- Extrae el nombre, email, teléfono, importe y método de pago del comprador.
- Detecta el tipo de producto (ej. "Bono 3 consultas", "Bono 5 consultas", "Consulta deportiva").
- Abre `Bonos activos_claude.xlsx`, inserta una nueva fila en la hoja `Bonos activos` con Román asignado y las celdas de consultas preparadas en blanco.
- Da de alta el bono en `anyd_booking.db`.
- Envía al comprador el correo de bienvenida con su enlace directo para agendar cita.

---

## 3. Embeber el Portal de Reservas en tu Web (`anyd.es/reservar`)

Tienes dos métodos para ofrecer el servicio a tus deportistas:

### Método A: Embebido en una página de anyd.es (Recomendado)
Crea o edita la página **Reservar Cita** en WordPress con el tema Astra y añade un bloque **HTML Personalizado**:

```html
<!-- Portal de Reservas ANyD Nutricionistas -->
<div style="width: 100%; max-width: 820px; margin: 0 auto; padding: 15px 0;">
    <iframe 
        src="http://localhost:8080/reservar" 
        width="100%" 
        height="850px" 
        frameborder="0" 
        style="border: none; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.06); width: 100%; min-height: 850px;"
        allow="camera; microphone"
        scrolling="yes">
    </iframe>
</div>
```

*(Cuando el backend tenga dominio público o túnel Cloudflare, cambia `http://localhost:8080` por la URL pública, ej: `https://citas.anyd.es/reservar`)*.

### Método B: Enlace directo en el menú de navegación
En el personalizador de Astra / Menús de WordPress, añade un enlace personalizado:
- **Texto:** `Reservar Cita`
- **URL:** `https://citas.anyd.es/reservar`

---

## 4. Configuración de la Báscula Tanita MC-580

La pantalla [http://localhost:8080/tanita](http://localhost:8080/tanita) ofrece dos vías de entrada de datos:

### Vía 1: Cable USB directo (Puerto Serie / COM)
1. Conecta la Tanita MC-580 al ordenador mediante el cable USB original o un adaptador USB-Serie FTDI.
2. Abre el Administrador de Dispositivos de Windows &rarr; **Puertos (COM y LPT)** y comprueba el número de puerto asignado (por ejemplo, `COM3`).
3. En la interfaz web `/tanita`:
   - Selecciona el puerto COM detectado.
   - Configura la velocidad a **9600 baudios** (estándar de fábrica de Tanita).
   - Haz clic en **"Conectar Báscula"**.
4. Realiza el pesaje en la Tanita. En cuanto la báscula emita el pitido final, los datos se volcarán automáticamente en pantalla.

### Vía 2: Tarjeta SD (Archivo CSV)
1. Extrae la tarjeta SD de la ranura de la Tanita MC-580.
2. Insértala en el lector de tarjetas del PC.
3. En la web `/tanita`, arrastra el archivo `.csv` generado por la báscula a la zona punteada o pulsa en **"Seleccionar CSV de Tarjeta SD"**.
4. El sistema leerá todos los parámetros corporales y calculará instantáneamente el gasto metabólico basal según **Cunningham**:
   $$\text{BMR (kcal/día)} = 500 + 22 \times \text{Masa Libre de Grasa (kg)}$$

---

## 5. Automatización de Recordatorios a 48h

Para que el script de recordatorios se ejecute todos los días automáticamente a las 09:00 de la mañana en Windows:

### Vía Programador de Tareas de Windows (Task Scheduler)
1. Presiona `Win + R`, escribe `taskschd.msc` y pulsa Enter.
2. Haz clic en **Crear tarea básica...**
   - **Nombre:** `Recordatorios 48h ANyD`
   - **Desencadenador:** `Diariamente` a las `09:00`
   - **Acción:** `Iniciar un programa`
   - **Programa o script:** `C:\Users\Roman\AppData\Local\Programs\Python\Python315-arm64\python.exe`
   - **Argumentos:** `-m scheduler`
   - **Iniciar en:** `G:\Mi unidad\1.- IA\IA Gemini\Agente anyd`
3. Haz clic en **Finalizar**.

También puedes forzar el envío manual en cualquier momento haciendo una petición POST:
`POST http://localhost:8080/api/run-reminders`

---

## 6. Opciones para Conexión Externa y Webhooks

Para que el webhook de WooCommerce (`anyd.es`) y los deportistas desde sus móviles puedan conectar con el servidor mientras este corra en tu ordenador:

### Opción 1: Cloudflare Tunnel (100% Gratuito y Seguro — Recomendada)
No requiere abrir puertos en tu router ni IP fija:
1. Descarga `cloudflared` para Windows.
2. Ejecuta:
   ```cmd
   cloudflared tunnel --url http://localhost:8080
   ```
3. Cloudflare te proporcionará un subdominio HTTPS seguro (ej. `https://anyd-reservas.trycloudflare.com`).
4. Utiliza esa URL como destino del Webhook en WooCommerce y como `src` del iframe.

### Opción 2: Despliegue en Servidor VPS o Hosting Python
Si en el futuro deseas tener el servidor encendido 24/7 sin depender de que tu ordenador esté encendido, puedes alojarlo en cualquier VPS económico (Hetzner, DigitalOcean) o PaaS (Render, Railway) copiando simplemente esta carpeta.
