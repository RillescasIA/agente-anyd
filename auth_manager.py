# -*- coding: utf-8 -*-
"""
Módulo de Autenticación y Control de Acceso Seguro (ANyD).
Protege la plataforma frente a accesos no autorizados mediante:
- Contraseña administrativa protegida con hash PBKDF2-HMAC-SHA256 (100.000 iteraciones).
- Sesiones firmadas criptográficamente con HMAC-SHA256 en cookies HttpOnly y SameSite=Lax.
- Redirección automática a /login para solicitudes de interfaz web y 401 Unauthorized para APIs.
"""

import os
import json
import time
import hmac
import hashlib
import secrets
import base64
from typing import Optional, Dict, Any, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", "anyd_security_secret_key_mad00274_col_2026")

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "AnydNutri2026!"


def get_stored_credentials() -> Tuple[str, str]:
    """Obtiene el usuario y la contraseña (o hash) configurados en config.json o variables de entorno."""
    user = os.environ.get("ADMIN_USER")
    pwd_or_hash = os.environ.get("ADMIN_PASSWORD")

    if not user or not pwd_or_hash:
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    user = user or cfg.get("admin_username")
                    pwd_or_hash = pwd_or_hash or cfg.get("admin_password")
            except Exception as e:
                print(f"[AUTH ERROR] Error leyendo config.json: {e}")

    user = user or DEFAULT_USERNAME
    pwd_or_hash = pwd_or_hash or DEFAULT_PASSWORD
    return user.strip(), pwd_or_hash.strip()


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """Genera hash seguro PBKDF2-HMAC-SHA256."""
    if not salt:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return f"pbkdf2:sha256:100000${salt}${key.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Compara una contraseña con el hash almacenado (o texto plano para primer arranque)."""
    if not password or not stored_hash:
        return False
    try:
        if stored_hash.startswith("pbkdf2:sha256:"):
            parts = stored_hash.split('$')
            if len(parts) == 3:
                salt, key_hex = parts[1], parts[2]
                computed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
                return hmac.compare_digest(computed, key_hex)
        # Comparación directa de respaldo (si aún no se ha hasheado)
        return hmac.compare_digest(password, stored_hash)
    except Exception:
        return False


def set_admin_credentials(username: str, new_password: str) -> bool:
    """Actualiza y guarda el usuario y hash de contraseña en config.json."""
    try:
        cfg = {}
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)

        hashed = hash_password(new_password)
        cfg["admin_username"] = username.strip()
        cfg["admin_password"] = hashed

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[AUTH ERROR] Error guardando credenciales: {e}")
        return False


def create_session_token(username: str, remember_me: bool = True) -> str:
    """Crea un token de sesión firmado criptográficamente con HMAC-SHA256."""
    days = 30 if remember_me else 2
    exp_timestamp = int(time.time()) + (days * 86400)
    payload_dict = {
        "u": username,
        "exp": exp_timestamp,
        "nonce": secrets.token_hex(8)
    }
    raw_json = json.dumps(payload_dict, separators=(',', ':'))
    b64_payload = base64.urlsafe_b64encode(raw_json.encode('utf-8')).decode('utf-8').rstrip('=')
    signature = hmac.new(SECRET_KEY.encode('utf-8'), b64_payload.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{b64_payload}.{signature}"


def verify_session_token(token: Optional[str]) -> Optional[str]:
    """Verifica la firma y expiración del token de sesión. Retorna el nombre de usuario si es válido."""
    if not token or "." not in token:
        return None
    try:
        b64_payload, signature = token.split(".", 1)
        expected_sig = hmac.new(SECRET_KEY.encode('utf-8'), b64_payload.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None

        # Rellenar padding Base64 si falta
        padded_b64 = b64_payload + "=" * ((4 - len(b64_payload) % 4) % 4)
        raw_json = base64.urlsafe_b64decode(padded_b64.encode('utf-8')).decode('utf-8')
        payload = json.loads(raw_json)

        if payload.get("exp", 0) < time.time():
            return None  # Sesión expirada

        return payload.get("u")
    except Exception:
        return None
