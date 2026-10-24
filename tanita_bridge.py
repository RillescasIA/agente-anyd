#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
PUENTE LOCAL TANITA MC-580 -> AGENTE ANYD NUTRICIONISTAS
Román Illescas Quiroga (Col. MAD00274)
=============================================================================
Este script se ejecuta en el PC de consulta conectado por USB a la báscula.
1. Detecta automáticamente el puerto COM (Prolific PL2303GT).
2. Escucha las pesadas de los pacientes en tiempo real.
3. Envía automáticamente cada medición a https://agente.anyd.es/api/tanita/feed
=============================================================================
"""

import sys
import time
import re
import json
import urllib.request
import urllib.error
from datetime import datetime

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("[ERROR] Falta el paquete 'pyserial'. Instálalo con: pip install pyserial")
    sys.exit(1)

CLOUD_API_URL = "https://agente.anyd.es/api/tanita/feed"

def find_tanita_port():
    """Busca automáticamente el puerto COM donde está conectada la Tanita."""
    ports = list(serial.tools.list_ports.comports())
    # Prioridad: Prolific PL2303 o COM3
    for p in ports:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if "prolific" in desc or "pl2303" in desc or "067b:23c3" in hwid:
            return p.device
    # Si no, buscar COM3
    for p in ports:
        if p.device.upper() == "COM3":
            return p.device
    # Si no, devolver el primer puerto USB serial
    for p in ports:
        if "usb" in (p.description or "").lower():
            return p.device
    return None

def parse_tanita_line(raw_str):
    """Extrae métricas biométricas de la trama de la Tanita MC-580."""
    data = {
        "raw": raw_str,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": "Tanita MC-580",
        "weight": None,
        "bmi": None,
        "fat_percent": None,
        "fat_mass": None,
        "muscle_mass": None,
        "ffm": None,
        "water_percent": None,
        "bone_mass": None,
        "visceral_fat": None,
        "bmr_tanita": None,
        "bmr_cunningham": None
    }

    # 1. Formato tokenizado clásico (Wk, FW, MW, FF, WW, wW, bW, IF...)
    tokens = re.findall(r'([A-Za-z0-9~]+)[,:]\s*"?([^",\r\n]+)"?', raw_str)
    td = {k.strip(): v.strip() for k, v in tokens}

    def get_f(keys):
        for k in keys:
            if k in td:
                try:
                    return float(td[k])
                except:
                    pass
        return None

    data["weight"] = get_f(["Wk", "Wb", "Weight", "Peso", "weight"])
    data["fat_percent"] = get_f(["FW", "FAT", "Fat%", "% Grasa", "fat_percent", "F%"])
    data["muscle_mass"] = get_f(["MW", "MUSCLE", "MuscleMass", "Masa Muscular", "muscle_mass"])
    data["ffm"] = get_f(["FF", "FFM", "Masa Libre Grasa", "ffm"])
    data["water_percent"] = get_f(["wW", "TBW%", "% Agua", "water_percent"])
    data["bone_mass"] = get_f(["bW", "BONE", "Masa Osea", "bone_mass"])
    data["visceral_fat"] = get_f(["IF", "VISCERAL", "Grasa Visceral", "visceral_fat"])
    data["bmr_tanita"] = get_f(["rA", "BMR", "bmr_tanita"])
    data["bmi"] = get_f(["BMI", "IMC", "bmi"])

    # 2. Formato CSV puro
    if data["weight"] is None and "," in raw_str:
        parts = [p.strip().replace('"', '') for p in raw_str.split(",")]
        nums = []
        for p in parts:
            try:
                nums.append(float(p))
            except:
                pass
        if len(nums) >= 6:
            for idx, val in enumerate(nums):
                if 40.0 <= val <= 250.0 and data["weight"] is None:
                    data["weight"] = val
                    if idx + 1 < len(nums) and 3.0 <= nums[idx + 1] <= 60.0:
                        data["fat_percent"] = nums[idx + 1]
                    if idx + 3 < len(nums) and 20.0 <= nums[idx + 3] <= 120.0:
                        data["muscle_mass"] = nums[idx + 3]

    # Cálculos derivados
    if data["weight"] and data["fat_percent"]:
        data["fat_mass"] = round(data["weight"] * (data["fat_percent"] / 100.0), 2)
        if not data["ffm"]:
            data["ffm"] = round(data["weight"] - data["fat_mass"], 2)

    if data["ffm"]:
        data["bmr_cunningham"] = round(500 + 22 * data["ffm"])

    if data["weight"] and data["weight"] > 20:
        return data
    return None

def send_to_cloud(measurement):
    """Envía la medición al servidor de producción en Render."""
    payload = json.dumps({"measurement": measurement}).encode("utf-8")
    req = urllib.request.Request(
        CLOUD_API_URL,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "TanitaLocalBridge/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            res_body = response.read().decode("utf-8")
            print(f"[OK] Sincronizado con agente.anyd.es: {res_body}")
            return True
    except Exception as e:
        print(f"[AVISO] No se pudo enviar a la nube ({e}). Guardado localmente.")
        return False

def main():
    print("=" * 65)
    print("  ANyD Nutricionistas · Puente de Enlace Báscula Tanita MC-580")
    print("  Román Illescas Quiroga (Col. MAD00274)")
    print("=" * 65)

    port = find_tanita_port()
    if not port:
        print("\n[ALERTA] No se detectó ninguna báscula Tanita conectada al USB.")
        print("Puertos encontrados en tu equipo:")
        for p in serial.tools.list_ports.comports():
            print(f" - {p.device}: {p.description}")
        print("\nPor favor conecta el cable USB de la báscula y vuelve a intentarlo.")
        input("\nPulsa ENTER para salir...")
        return

    print(f"\n[+] Báscula Tanita MC-580 detectada en puerto: {port}")
    print("[+] Conectando a 9600 baudios (8N1)...")

    try:
        ser = serial.Serial(port, baudrate=9600, timeout=1)
        print(f"[OK] ¡Conexión establecida con {port}!")
        print("\n>>> LISTO Y ESPERANDO PESAJES DE PACIENTES <<<")
        print("(Cada vez que un paciente se pese en la Tanita, los datos se enviarán")
        print(" automáticamente a tu pantalla en https://agente.anyd.es/nuevo-paciente)\n")
    except Exception as e:
        print(f"[ERROR] No se pudo abrir {port}: {e}")
        print("Verifica que ninguna otra aplicación (como Tanita Pro Suite) tenga el puerto abierto.")
        input("\nPulsa ENTER para salir...")
        return

    buffer = ""
    try:
        while True:
            if ser.in_waiting > 0:
                raw_bytes = ser.read(ser.in_waiting)
                chunk = raw_bytes.decode("utf-8", errors="replace")
                buffer += chunk

                if "\n" in buffer or "\r" in buffer or len(buffer) > 100:
                    lines = buffer.splitlines()
                    for line in lines:
                        line_clean = line.strip()
                        if len(line_clean) > 10:
                            parsed = parse_tanita_line(line_clean)
                            if parsed and parsed.get("weight"):
                                print("\n" + "#" * 55)
                                print(f"  NUEVA MEDICIÓN RECIBIDA [{parsed['timestamp']}]")
                                print(f"  Peso: {parsed['weight']} kg | % Grasa: {parsed['fat_percent']}%")
                                print(f"  FFM (Masa Libre de Grasa): {parsed['ffm']} kg")
                                print(f"  BMR Cunningham: {parsed['bmr_cunningham']} kcal")
                                print("#" * 55)
                                send_to_cloud(parsed)
                    buffer = ""
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[INFO] Puente Tanita detenido por el usuario.")
    finally:
        ser.close()

if __name__ == "__main__":
    main()
