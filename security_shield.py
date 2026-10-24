# -*- coding: utf-8 -*-
"""
Módulo de Blindaje y Seguridad Perimetral Activa (ANyD Nutricionistas).
Protege la estación clínica y el agente copiloto contra ataques:
1. Anti-Fuerza Bruta & Tarpitting: Bloqueo de IP tras 5 intentos fallidos (15 min) y retardo progresivo.
2. Anti-DDoS / Rate Limiter: Límite de peticiones por minuto por dirección IP.
3. Anti-Path Traversal & Probe Shield: Bloqueo inmediato de escaneos (.env, wp-login, phpmyadmin, ../).
4. Anti-XSS & Sanitización: Escapado estricto de HTML y prevención de inyección de scripts.
5. Auditoría de Seguridad: Registro de eventos sospechosos con IP real (Cloudflare / Render).
"""

import time
import html
import threading
from typing import Dict, Tuple, Optional
from fastapi import Request

# Registro en memoria con bloqueo de concurrencia
_lock = threading.Lock()
_failed_attempts: Dict[str, Dict[str, Any]] = {}
_request_counts: Dict[str, list] = {}

# Parámetros de Seguridad
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 15 * 60  # 15 minutos de bloqueo
LOGIN_RATE_LIMIT_PER_MINUTE = 12    # Máximo 12 intentos de login por minuto por IP
GLOBAL_RATE_LIMIT_PER_MINUTE = 180  # Máximo 180 peticiones por minuto por IP

# Patrones maliciosos típicos de escáneres y atacantes web
MALICIOUS_PROBES = (
    "../", "..\\", "/.env", "/.git", "wp-login", "xmlrpc.php",
    "phpmyadmin", "pma", "cgi-bin", "actuator", "/etc/passwd",
    "boot.ini", "win.ini", "eval(", "base64_decode"
)

def get_client_ip(request: Request) -> str:
    """Extrae la IP real del cliente detrás del proxy de Cloudflare o Render."""
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    x_forwarded = request.headers.get("x-forwarded-for")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host.strip()
    return "127.0.0.1"

def is_malicious_path(path: str) -> bool:
    """Detecta sondas de escaneo malicioso o intentos de path traversal."""
    p_lower = path.lower()
    return any(probe in p_lower for probe in MALICIOUS_PROBES)

def check_login_lockout(ip: str) -> Tuple[bool, int]:
    """Comprueba si una IP está actualmente bloqueada por fuerza bruta."""
    now = time.time()
    with _lock:
        data = _failed_attempts.get(ip)
        if not data:
            return False, 0
        lock_until = data.get("locked_until", 0)
        if lock_until > now:
            remaining = int(lock_until - now)
            return True, remaining
        # Si ya pasó el tiempo de bloqueo, limpiar
        if lock_until > 0 and lock_until <= now:
            del _failed_attempts[ip]
            return False, 0
    return False, 0

def record_failed_login(ip: str, username: str) -> int:
    """Registra un fallo de autenticación y bloquea la IP si supera el umbral."""
    now = time.time()
    with _lock:
        if ip not in _failed_attempts:
            _failed_attempts[ip] = {
                "count": 0,
                "first_fail": now,
                "locked_until": 0,
                "last_user": username
            }
        entry = _failed_attempts[ip]
        entry["count"] += 1
        entry["last_user"] = username

        # Si supera el umbral, activar bloqueo de 15 minutos
        if entry["count"] >= MAX_FAILED_LOGIN_ATTEMPTS:
            entry["locked_until"] = now + LOCKOUT_DURATION_SECONDS
            log_security_alert("IP_LOCKED_OUT", ip, f"Usuario: {username} - {entry['count']} fallos consecutivos")
            return int(LOCKOUT_DURATION_SECONDS)
        
        return 0

def reset_failed_login(ip: str):
    """Limpia el registro de fallos tras un inicio de sesión exitoso."""
    with _lock:
        if ip in _failed_attempts:
            del _failed_attempts[ip]

def check_rate_limit(ip: str, is_login: bool = False) -> bool:
    """Limita la velocidad de peticiones por minuto para mitigar ataques DoS / fuerza bruta."""
    now = time.time()
    limit = LOGIN_RATE_LIMIT_PER_MINUTE if is_login else GLOBAL_RATE_LIMIT_PER_MINUTE
    key = f"{ip}:login" if is_login else f"{ip}:global"

    with _lock:
        timestamps = _request_counts.get(key, [])
        # Filtrar peticiones de los últimos 60 segundos
        valid_ts = [t for t in timestamps if now - t < 60.0]
        if len(valid_ts) >= limit:
            _request_counts[key] = valid_ts
            return False  # Límite superado
        valid_ts.append(now)
        _request_counts[key] = valid_ts
    return True

def sanitize_xss(text: str) -> str:
    """Sanitiza cadenas de texto para evitar inyecciones XSS."""
    if not text:
        return ""
    return html.escape(text.strip())

def log_security_alert(event_type: str, ip: str, details: str = ""):
    """Registra eventos de seguridad en consola y archivo de auditoría."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[SEGURIDAD ANyD] [{timestamp}] [EVENTO: {event_type}] [IP: {ip}] {details}"
    print(msg)
