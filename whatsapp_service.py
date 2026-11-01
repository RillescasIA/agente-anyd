# -*- coding: utf-8 -*-
"""
=============================================================================
SERVICIO DE MENSAJERÍA WHATSAPP (1-CLIC wa.me) · AGENTE ANYD NUTRICIONISTAS
Román Illescas Quiroga (Col. MAD00274)
=============================================================================
Genera enlaces estandarizados https://wa.me/{telefono}?text={mensaje} con
formato clínico y deportivo sin costes de API externa, cumpliendo con RGPD.
REGLA CLÍNICA:
- No se envían avisos comerciales ni de agotamiento de bono al paciente (se respeta su espacio).
- Recordatorios de cita 2 días antes (48h). Si cae en fin de semana, se anticipa al viernes.
=============================================================================
"""

import urllib.parse
import re

def clean_phone(phone_str):
    """Limpia y formatea el teléfono para formato internacional E.164 (España 34)."""
    if not phone_str:
        return ""
    digits = re.sub(r'[^0-9]', '', str(phone_str))
    if not digits:
        return ""
    if len(digits) == 9:
        digits = "34" + digits
    elif digits.startswith("0034"):
        digits = digits[2:]
    return digits

def generate_wa_link(phone, text):
    """Genera el enlace final wa.me."""
    target_phone = clean_phone(phone)
    encoded_text = urllib.parse.quote(text)
    if target_phone:
        return f"https://wa.me/{target_phone}?text={encoded_text}"
    return f"https://wa.me/?text={encoded_text}"

def get_booking_confirmation_msg(client_name, date_str, time_str, modality="Presencial", service="Nutrición Deportiva"):
    """Plantilla de confirmación inmediata al agendar la consulta."""
    first_name = (client_name or "").strip().split()[0] if client_name else "deportista"
    modalidad_info = "en nuestra consulta presencial" if "presencial" in (modality or "").lower() else "online por videollamada"
    
    msg = (
        f"¡Hola {first_name}! Te escribe Román Illescas de ANyD Nutricionistas para confirmarte tu consulta "
        f"de {service} ({modalidad_info}) programada para el próximo {date_str} a las {time_str}.\n\n"
        f"Si necesitas modificar la fecha o avisarme de cualquier detalle previo, puedes responder a este mensaje. "
        f"¡Nos vemos pronto!"
    )
    return msg

def get_appointment_reminder_48h_msg(client_name, date_str, time_str, modality="Presencial", service="Nutrición Deportiva"):
    """
    Plantilla oficial de recordatorio de cita enviada 2 días antes (o el viernes si cae en fin de semana).
    """
    first_name = (client_name or "").strip().split()[0] if client_name else "deportista"
    is_presencial = "presencial" in (modality or "").lower()
    
    if is_presencial:
        msg = (
            f"¡Hola {first_name}! Te escribe Román Illescas de ANyD Nutricionistas para recordarte nuestra "
            f"consulta presencial de seguimiento programada para el próximo {date_str} a las {time_str}.\n\n"
            f"Para que la valoración antropométrica y el pesaje en la báscula clínica Tanita MC-580 sean óptimos, "
            f"recuerda estas sencillas pautas:\n"
            f"1. 💧 Normohidratación: Bebe agua con normalidad en las horas previas.\n"
            f"2. 🍽️ Ayuno digestivo: Ayuno de comida sólida 2-3 horas antes de la cita.\n"
            f"3. 🚽 Vaciado vesical: Orinar antes de subir a la báscula.\n"
            f"4. 🏃 Entrenamientos: Evitar esfuerzos extenuantes inmediatamente antes.\n\n"
            f"Cualquier duda o cambio de horario, avísame por aquí. ¡Nos vemos en consulta!"
        )
    else:
        msg = (
            f"¡Hola {first_name}! Te escribe Román Illescas de ANyD Nutricionistas para recordarte nuestra "
            f"consulta online por videollamada programada para el próximo {date_str} a las {time_str}.\n\n"
            f"Revisaremos la evolución de tu planificación nutricional, sensaciones en entrenamientos y los ajustes "
            f"para los próximos objetivos.\n\n"
            f"Cualquier ajuste de horario, avísame con antelación. ¡Nos vemos en videollamada!"
        )
    return msg

def get_tanita_protocol_msg(client_name, time_str):
    """Plantilla específica de protocolo Tanita MC-580."""
    first_name = (client_name or "").strip().split()[0] if client_name else "deportista"
    
    msg = (
        f"¡Hola {first_name}! Te escribe Román Illescas de ANyD Nutricionistas para recordarte nuestra consulta presencial "
        f"a las {time_str}.\n\n"
        f"Para que la medición de bioimpedancia con la báscula clínica Tanita MC-580 sea 100% exacta y fiable, "
        f"recuerda seguir este protocolo:\n"
        f"1. 💧 Normohidratación: Bebe agua con normalidad hoy.\n"
        f"2. 🍽️ Ayuno digestivo: Ayuno de comida sólida 2-3 horas antes de la consulta.\n"
        f"3. 🚽 Vaciado vesical: Orina justo antes de subir a la báscula.\n"
        f"4. 🏃 Sin entreno intenso: Evita entrenamientos extenuantes 12 horas antes.\n"
        f"5. ☕ Evitar diuréticos: No tomes café abundante ni bebidas energéticas en las 3 horas previas.\n\n"
        f"¡Nos vemos en consulta!"
    )
    return msg

def build_whatsapp_payload(client_name, phone, msg_type="reminder_48h", **kwargs):
    """Genera la estructura de enlace y texto lista para consumir desde el frontend o backend."""
    if msg_type == "confirmation":
        text = get_booking_confirmation_msg(
            client_name,
            kwargs.get("date_str", ""),
            kwargs.get("time_str", ""),
            kwargs.get("modality", "Presencial"),
            kwargs.get("service", "Nutrición Deportiva")
        )
    elif msg_type == "reminder_48h":
        text = get_appointment_reminder_48h_msg(
            client_name,
            kwargs.get("date_str", ""),
            kwargs.get("time_str", ""),
            kwargs.get("modality", "Presencial"),
            kwargs.get("service", "Nutrición Deportiva")
        )
    elif msg_type == "tanita_protocol":
        text = get_tanita_protocol_msg(client_name, kwargs.get("time_str", ""))
    else:
        text = kwargs.get("custom_text", f"Hola {client_name}, te escribo de ANyD Nutricionistas.")

    link = generate_wa_link(phone, text)
    return {
        "client_name": client_name,
        "phone": phone,
        "clean_phone": clean_phone(phone),
        "text": text,
        "link": link
    }
