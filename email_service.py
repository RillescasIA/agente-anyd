import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import json

CONFIG_FILE = r"g:\Mi unidad\1.- IA\IA Gemini\Agente anyd\config.json"

DEFAULT_CONFIG = {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_password": "",
    "sender_email": "info@anyd.es",
    "sender_name": "Román Illescas - ANyD Nutricionistas",
    "clinic_name": "ANyD Nutricionistas",
    "website_url": "https://anyd.es",
    "booking_url": "http://localhost:8080/reservar",
    "enable_live_email": False
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return DEFAULT_CONFIG

def send_email(to_email, subject, html_body):
    cfg = load_config()
    
    if not cfg.get("enable_live_email") or not cfg.get("smtp_user"):
        print(f"\n[EMAIL SIMULADO -> {to_email}] Asunto: {subject}")
        print(f"Para activar envíos reales, configura tus credenciales SMTP en config.json y pon 'enable_live_email': true.\n")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{cfg.get('sender_name')} <{cfg.get('sender_email')}>"
        msg["To"] = to_email

        part = MIMEText(html_body, "html")
        msg.attach(part)

        with smtplib.SMTP(cfg["smtp_server"], cfg["smtp_port"]) as server:
            server.starttls()
            server.login(cfg["smtp_user"], cfg["smtp_password"])
            server.sendmail(cfg["sender_email"], to_email, msg.as_string())

        print(f"[EMAIL ENVIADO] A: {to_email} | Asunto: {subject}")
        return True
    except Exception as e:
        print(f"[ERROR ENVIANDO EMAIL] A: {to_email} | Error: {e}")
        return False

def send_purchase_confirmation(to_email, client_name, order_id, tipo_bono, sessions_count):
    cfg = load_config()
    booking_link = cfg.get("booking_url", "https://anyd.es/reservar")
    
    subject = f"¡Confirmación de tu bono {tipo_bono}! - ANyD Nutricionistas"
    body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #2C3E50; border: 1px solid #EAEAEA; border-radius: 8px;">
        <h2 style="color: #1A5276; text-align: center;">¡Bienvenido a ANyD Nutricionistas!</h2>
        <p>Hola <strong>{client_name}</strong>,</p>
        <p>Hemos confirmado la compra de tu bono correctamente:</p>
        <div style="background-color: #F8F9F9; padding: 15px; border-radius: 6px; margin: 20px 0;">
            <p style="margin: 5px 0;"><strong>Nº de Pedido:</strong> #{order_id}</p>
            <p style="margin: 5px 0;"><strong>Bono adquirido:</strong> {tipo_bono}</p>
            <p style="margin: 5px 0;"><strong>Sesiones incluidas:</strong> {sessions_count} consultas</p>
        </div>
        <p>Ya puedes agendar tu primera consulta directamente a través de nuestro portal de reservas:</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{booking_link}" style="background-color: #27AE60; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px;">Agendar mi Cita</a>
        </div>
        <p style="font-size: 14px; color: #7F8C8D;">Si tienes cualquier duda con tu planificación deportiva o clínica, puedes responder a este correo.</p>
        <hr style="border: none; border-top: 1px solid #EAEAEA; margin: 25px 0;">
        <p style="font-size: 12px; color: #BDC3C7; text-align: center;">Román Illescas Quiroga - Col. MAD00274 | ANyD Nutricionistas</p>
    </div>
    """
    return send_email(to_email, subject, body)

def send_booking_confirmation(to_email, client_name, appointment_date, appointment_time, modality="Presencial", remaining_sessions=None, duration_minutes=30):
    subject = f"Cita Confirmada ({duration_minutes} min): {appointment_date} a las {appointment_time} - ANyD Nutricionistas"
    body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #2C3E50; border: 1px solid #EAEAEA; border-radius: 8px;">
        <h2 style="color: #1A5276; text-align: center;">Cita Confirmada</h2>
        <p>Hola <strong>{client_name}</strong>,</p>
        <p>Tu consulta de nutrición ha quedado agendada con éxito:</p>
        <div style="background-color: #EBF5FB; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #2980B9;">
            <p style="margin: 5px 0;"><strong>📅 Fecha:</strong> {appointment_date}</p>
            <p style="margin: 5px 0;"><strong>⏰ Hora:</strong> {appointment_time}</p>
            <p style="margin: 5px 0;"><strong>⏱️ Duración:</strong> {duration_minutes} minutos</p>
            <p style="margin: 5px 0;"><strong>📍 Modalidad:</strong> {modality}</p>
            {f'<p style="margin: 5px 0;"><strong>🎟️ Sesiones restantes tras la cita:</strong> {remaining_sessions}</p>' if remaining_sessions is not None else ''}
        </div>
        <p>Te enviaremos un recordatorio <strong>2 días antes</strong> de la cita con las instrucciones previas (recuerda evitar entrenamientos extenuantes o comidas copiosas justo antes de la bioimpedancia si es presencial).</p>
        <hr style="border: none; border-top: 1px solid #EAEAEA; margin: 25px 0;">
        <p style="font-size: 12px; color: #BDC3C7; text-align: center;">Román Illescas Quiroga | ANyD Nutricionistas</p>
    </div>
    """
    return send_email(to_email, subject, body)

def send_reminder_48h(to_email, client_name, appointment_date, appointment_time, modality="Presencial"):
    """
    Envía el recordatorio automático 2 días antes de la consulta (Reemplazo exacto de Reservio).
    """
    subject = f"Recordatorio: Tu consulta en ANyD es en 2 días ({appointment_date})"
    body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #2C3E50; border: 1px solid #EAEAEA; border-radius: 8px;">
        <h2 style="color: #E67E22; text-align: center;">Recordatorio de Consulta (en 48h)</h2>
        <p>Hola <strong>{client_name}</strong>,</p>
        <p>Te recordamos que tienes tu próxima consulta nutricional programada para:</p>
        <div style="background-color: #FEF9E7; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #F39C12;">
            <p style="margin: 5px 0;"><strong>📅 Fecha:</strong> {appointment_date}</p>
            <p style="margin: 5px 0;"><strong>⏰ Hora:</strong> {appointment_time}</p>
            <p style="margin: 5px 0;"><strong>📍 Modalidad:</strong> {modality}</p>
        </div>
        <div style="background-color: #F8F9F9; padding: 12px; border-radius: 6px; font-size: 13px;">
            <strong>Recomendaciones para la consulta:</strong>
            <ul>
                <li>Si es presencial para medición antropométrica / Tanita: acudir en ayunas de 2-3h o habiendo hecho una digestión ligera, y bien hidratado.</li>
                <li>Si necesitas modificar o reprogramar tu cita, por favor avísanos con la mayor antelación posible respondiendo a este mensaje.</li>
            </ul>
        </div>
        <hr style="border: none; border-top: 1px solid #EAEAEA; margin: 25px 0;">
        <p style="font-size: 12px; color: #BDC3C7; text-align: center;">Román Illescas Quiroga - Col. MAD00274 | ANyD Nutricionistas</p>
    </div>
    """
    return send_email(to_email, subject, body)
