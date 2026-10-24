#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
PUENTE BIDIRECCIONAL TANITA MC-580 · AGENTE ANYD NUTRICIONISTAS
Román Illescas Quiroga (Col. MAD00274)
=============================================================================
Protocolo Oficial Tanita RS-232 / USB:
- D1{1/2} : Sexo (1=Hombre, 2=Mujer)
- D2{2/0} : Modo (2=Atleta, 0=Estándar)
- D3{altura:05.1f} : Altura en cm (ej: D3178.0)
- D4{edad:02d} : Edad (ej: D430)
- D0{tara:04.1f} : Tara de ropa (ej: D000.2)
- G1 : Dispara la medición y pasa a estado S6 ("SUBA A LA BÁSCULA")
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

FEED_URL = "https://agente.anyd.es/api/tanita/feed"
PENDING_CMD_URL = "https://agente.anyd.es/api/tanita/pending-command"

def find_tanita_port():
    """Busca automáticamente el puerto COM de la Tanita MC-580."""
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if "prolific" in desc or "pl2303" in desc or "067b:23c3" in hwid:
            return p.device
    for p in ports:
        if p.device.upper() == "COM3":
            return p.device
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

    if data["weight"] and data["fat_percent"]:
        data["fat_mass"] = round(data["weight"] * (data["fat_percent"] / 100.0), 2)
        if not data["ffm"]:
            data["ffm"] = round(data["weight"] - data["fat_mass"], 2)

    if data["ffm"]:
        data["bmr_cunningham"] = round(500 + 22 * data["ffm"])

    if data["weight"] and data["weight"] > 20:
        return data
    return None

def send_patient_to_scale(ser, gender=1, body_type=2, height_cm=178.0, age=30, tare_kg=0.2):
    """
    Envía los comandos oficiales Tanita (sin espacios) para eliminar la 'P' intermitente
    y poner la báscula en estado S6 ('SUBA A LA BÁSCULA').
    """
    tare_str = f"{float(tare_kg):04.1f}"
    height_str = f"{float(height_cm):05.1f}"
    age_str = f"{int(age):02d}"

    cmds = [
        f"D1{gender}\r\n".encode(),
        f"D2{body_type}\r\n".encode(),
        f"D3{height_str}\r\n".encode(),
        f"D4{age_str}\r\n".encode(),
        f"D0{tare_str}\r\n".encode(),
        b"G1\r\n"
    ]
    for c in cmds:
        ser.write(c)
        time.sleep(0.1)
        if ser.in_waiting:
            ser.read(ser.in_waiting)

    print(f"\n[TANITA MC-580] >>> 'P' RESUELTA: DATOS DE PACIENTE CARGADOS <<<")
    print(f"  Sexo: {'Hombre' if gender==1 else 'Mujer'} | Altura: {height_cm} cm | Edad: {age} años | Tara: {tare_kg} kg")
    print(f"  Estado Báscula: S6 (SUBA A LA BÁSCULA). ¡Sube al deportista a la plataforma!")

def check_pending_web_command(ser):
    """Consulta si desde la web se ha ordenado un pesaje."""
    try:
        req = urllib.request.Request(PENDING_CMD_URL, headers={"User-Agent": "TanitaBridge/1.0"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("has_command") and data.get("command"):
                cmd = data["command"]
                send_patient_to_scale(
                    ser,
                    gender=cmd.get("gender", 1),
                    body_type=cmd.get("body_type", 2),
                    height_cm=cmd.get("height_cm", 178.0),
                    age=cmd.get("age", 30),
                    tare_kg=cmd.get("tare_kg", 0.2)
                )
    except Exception:
        pass

def send_measurement_to_cloud(measurement):
    """Envía la medición a la nube para rellenar la ficha."""
    payload = json.dumps({"measurement": measurement}).encode("utf-8")
    req = urllib.request.Request(
        FEED_URL,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "TanitaBridge/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            print(f"[OK] ¡Medición sincronizada con https://agente.anyd.es!")
            return True
    except Exception as e:
        print(f"[AVISO] Error enviando a la nube: {e}")
        return False

def main():
    print("=" * 70)
    print("  ANyD Nutricionistas · Puente Bidireccional Tanita MC-580")
    print("  Román Illescas Quiroga (Col. MAD00274)")
    print("=" * 70)

    port = find_tanita_port()
    if not port:
        print("\n[ALERTA] No se detectó la báscula Tanita en los puertos USB.")
        input("\nPulsa ENTER para salir...")
        return

    print(f"\n[+] Báscula Tanita MC-580 detectada en: {port}")
    print("[+] Conectando a 9600 baudios (8N1)...")

    try:
        ser = serial.Serial(port, baudrate=9600, timeout=0.5)
        print(f"[OK] ¡Conexión establecida con {port}!")
        print("\n>>> PUENTE ACTIVO EN SEGUNDO PLANO <<<")
        print("- Si en la pantalla de la Tanita parpadea la 'P', significa que está esperando")
        print("  los datos del paciente (Sexo, Altura, Edad).")
        print("- Al pulsar 'Iniciar Pesaje' en la web, los datos se inyectan solos, la 'P'")
        print("  desaparece y la báscula pide subir al paciente.")
        print("- Al terminar la medición, los números se rellenan automáticamente en la web.\n")
    except Exception as e:
        print(f"[ERROR] No se pudo abrir {port}: {e}")
        print("Asegúrate de que Dietowin / SuiteBiológica está cerrada.")
        input("\nPulsa ENTER para salir...")
        return

    buffer = ""
    last_poll_time = 0

    try:
        while True:
            now = time.time()
            if now - last_poll_time > 1.2:
                check_pending_web_command(ser)
                last_poll_time = now

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
                                print("\n" + "#" * 60)
                                print(f"  ✅ NUEVA MEDICIÓN COMPLETADA [{parsed['timestamp']}]")
                                print(f"  Peso: {parsed['weight']} kg | % Grasa: {parsed['fat_percent']}%")
                                print(f"  FFM (Masa Libre de Grasa): {parsed['ffm']} kg")
                                print(f"  BMR Cunningham: {parsed['bmr_cunningham']} kcal")
                                print("#" * 60)
                                send_measurement_to_cloud(parsed)
                    buffer = ""
            time.sleep(0.08)
    except KeyboardInterrupt:
        print("\n[INFO] Puente detenido por el usuario.")
    finally:
        ser.close()

if __name__ == "__main__":
    main()
