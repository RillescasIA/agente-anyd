#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
PUENTE BIDIRECCIONAL TANITA MC-580 · AGENTE ANYD NUTRICIONISTAS
Román Illescas Quiroga (Col. MAD00274)
=============================================================================
1. Detecta automáticamente la báscula en el puerto USB (COM3 Prolific).
2. Recibe órdenes desde https://agente.anyd.es/api/tanita/pending-command
   y envía a la báscula los datos del paciente (Sexo, Altura, Edad, Tara)
   para que la pantalla de la Tanita se encienda y configure automáticamente.
3. Captura la pesada final tras el análisis BIA y la envía en tiempo real a la web.
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
    Envía los comandos protocolarios Tanita para inicializar la báscula con los datos del paciente:
    - D1: Sexo (1=Hombre, 2=Mujer)
    - D2: Tipo (2=Atleta, 0=Estándar)
    - D3: Altura en cm (ej: 178.0)
    - D4: Edad (ej: 30)
    - D0: Tara de ropa (ej: 00.2)
    - G1: Iniciar rutina de pesaje y encender pantalla
    """
    tare_str = f"{float(tare_kg):04.1f}"
    cmds = [
        f"D1 {gender}\r\n".encode(),
        f"D2 {body_type}\r\n".encode(),
        f"D3 {float(height_cm):.1f}\r\n".encode(),
        f"D4 {int(age)}\r\n".encode(),
        f"D0 {tare_str}\r\n".encode(),
        b"G1\r\n"
    ]
    for c in cmds:
        ser.write(c)
        time.sleep(0.12)
        if ser.in_waiting:
            ser.read(ser.in_waiting)
    print(f"\n[TANITA] >>> DATOS ENVIADOS A LA BÁSCULA CON ÉXITO <<<")
    print(f"  Sexo: {'Hombre' if gender==1 else 'Mujer'} | Altura: {height_cm} cm | Edad: {age} | Tara: {tare_kg} kg")
    print(f"  ¡La pantalla de la Tanita MC-580 se ha encendido! Sube al paciente a la plataforma.")

def check_pending_web_command(ser):
    """Consulta si desde la web https://agente.anyd.es se ha pulsado iniciar pesaje."""
    try:
        req = urllib.request.Request(PENDING_CMD_URL, headers={"User-Agent": "TanitaBridge/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
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
    """Envía la medición final a la web para rellenar la ficha."""
    payload = json.dumps({"measurement": measurement}).encode("utf-8")
    req = urllib.request.Request(
        FEED_URL,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "TanitaBridge/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            print(f"[OK] ¡Medición sincronizada con agente.anyd.es!")
            return True
    except Exception as e:
        print(f"[AVISO] Error enviando a la nube: {e}")
        return False

def main():
    print("=" * 70)
    print("  ANyD Nutricionistas · Puente de Enlace Bidireccional Tanita MC-580")
    print("  Román Illescas Quiroga (Col. MAD00274)")
    print("=" * 70)

    port = find_tanita_port()
    if not port:
        print("\n[ALERTA] No se detectó ninguna báscula Tanita conectada al USB.")
        print("Puertos encontrados en este PC:")
        for p in serial.tools.list_ports.comports():
            print(f" - {p.device}: {p.description}")
        print("\nConecta el cable USB de la Tanita y vuelve a ejecutar este programa.")
        input("\nPulsa ENTER para salir...")
        return

    print(f"\n[+] Báscula Tanita MC-580 detectada en: {port}")
    print("[+] Conectando a 9600 baudios (8N1)...")

    try:
        ser = serial.Serial(port, baudrate=9600, timeout=0.5)
        print(f"[OK] ¡Conexión establecida con {port}!")
        print("\n>>> LISTO EN SEGUNDO PLANO <<<")
        print("- Cuando en https://agente.anyd.es/nuevo-paciente pulses 'Iniciar Pesaje',")
        print("  los datos del paciente (altura, edad, sexo) se reflejarán en la báscula al instante.")
        print("- Cuando el paciente termine el pesaje, los datos se volcarán solos en la web.\n")
    except Exception as e:
        print(f"[ERROR] No se pudo abrir {port}: {e}")
        print("Asegúrate de cerrar Dietowin o SuiteBiológica si están abiertas.")
        input("\nPulsa ENTER para salir...")
        return

    buffer = ""
    last_poll_time = 0

    try:
        while True:
            # 1. Comprobar órdenes desde la web cada 1.5 segundos
            now = time.time()
            if now - last_poll_time > 1.5:
                check_pending_web_command(ser)
                last_poll_time = now

            # 2. Leer datos que envíe la báscula al terminar el pesaje
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
