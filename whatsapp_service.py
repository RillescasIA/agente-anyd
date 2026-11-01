# -*- coding: utf-8 -*-
"""
=============================================================================
SERVICIO DE MENSAJERÍA WHATSAPP (1-CLIC wa.me) · AGENTE ANYD NUTRICIONISTAS
Román Illescas Quiroga (Col. MAD00274)
=============================================================================
Genera enlaces estandarizados https://wa.me/{telefono}?text={mensaje} con
formato clínico y deportivo sin costes de API externa, cumpliendo con RGPD.
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
    """Plantilla de confirmación de reserva agendada."""
    first_name = (client_name or "").strip().split()[0] if client_name else "deportista"
    modalidad_info = "en nuestra consulta presencial" if "presencial" in (modality or "").lower() else "online por videollamada"
    
    msg = (
        f"¡Hola {first_name}! Te escribe Román Illescas de ANyD Nutricionistas para confirmarte tu consulta "
        f"de {service} ({modality_info}) programada para el próximo {date_str} a las {time_str}.\n\n"
        f"Si necesitas modificar la fecha o avisarme de cualquier detalle previo, puedes responder a este mensaje. "
        f"¡Nos vemos pronto!"
    )
    return msg

def get_tanita_protocol_msg(client_name, time_str):
    """Plantilla de protocolo preparatorio Tanita MC-580 (T-24h para cita presencial)."""
    first_name = (client_name or "").strip().split()[0] if client_name else "deportista"
    
    msg = (
        f"¡Hola {first_name}! Te escribe Román Illescas de ANyD Nutricionistas para recordarte nuestra consulta presencial "
        f"de mañana a las {time_str}.\n\n"
        f"Para que la medición de bioimpedancia con la báscula clínica Tanita MC-580 sea 100% exacta y fiable, "
        f"recuerda seguir este protocolo:\n"
        f"1. 💧 Normohidratación: Bebe agua con normalidad hoy.\n"
        f"2. 🍽️ Ayuno digestivo: Ayuno de comida sólida 2-3 horas antes de la consulta.\n"
        f"3. 🚽 Vaciado vesical: Orina justo antes de subir a la báscula.\n"
        f"4. 🏃 Sin entreno intenso: Evita entrenamientos extenuantes 12 horas antes.\n"
        f"5. ☕ Evitar diuréticos: No tomes café abundante ni bebidas energéticas en las 3 horas previas.\n\n"
        f"¡Nos vemos mañana en consulta!"
    )
    return msg

def get_bono_warning_msg(client_name, bono_type, remaining_sessions=1, total_sessions=3):
    """Alerta de penúltima sesión / 1 sesión restante del bono."""
    first_name = (client_name or "").strip().split()[0] if client_name else "deportista"
    
    msg = (
        f"¡Hola {first_name}! Te escribe Román Illescas de ANyD Nutricionistas. "
        f"Te informo de que tras esta consulta te queda solo 1 sesión disponible en tu bono {bono_type} "
        f"({total_sessions - 1} de {total_sessions} consumidas).\n\n"
        f"Podemos planificar la última sesión de seguimiento o tramitar la renovación en https://anyd.es para no "
        f"interrumpir la periodización de tu temporada. ¡Seguimos sumando!"
    )
    return msg

def get_bono_exhausted_msg(client_name, bono_type, renewal_url="https://anyd.es"):
    """Alerta de bono completado/agotado (0 sesiones restantes)."""
    first_name = (client_name or "").strip().split()[0] if client_name else "deportista"
    
    msg = (
        f"¡Hola {first_name}! Te escribe Román Illescas de ANyD Nutricionistas. "
        f"Has completado con éxito la última sesión de tu bono {bono_type}.\n\n"
        f"Para continuar con tu seguimiento nutricional, nuevos ajustes de composición corporal y pautas de competición, "
        f"puedes renovar tu bono cómodamente desde nuestra web: {renewal_url}\n\n"
        f"¡Muchas gracias por tu compromiso y confianza en ANyD!"
    )
    return msg

def build_whatsapp_payload(client_name, phone, msg_type="confirmation", **kwargs):
    """Genera la estructura de enlace y texto lista para consumir desde el frontend o backend."""
    if msg_type == "confirmation":
        text = get_booking_confirmation_msg(
            client_name,
            kwargs.get("date_str", ""),
            kwargs.get("time_str", ""),
            kwargs.get("modality", "Presencial"),
            kwargs.get("service", "Nutrición Deportiva")
        )
    elif msg_type == "tanita_protocol":
        text = get_tanita_protocol_msg(client_name, kwargs.get("time_str", ""))
    elif msg_type == "bono_warning":
        text = get_bono_warning_msg(
            client_name,
            kwargs.get("bono_type", "Bono ANyD"),
            kwargs.get("remaining_sessions", 1),
            kwargs.get("total_sessions", 3)
        )
    elif msg_type == "bono_exhausted":
        text = get_bono_exhausted_msg(
            client_name,
            kwargs.get("bono_type", "Bono ANyD"),
            kwargs.get("renewal_url", "https://anyd.es")
        )
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
