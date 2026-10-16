import serial
import serial.tools.list_ports
import threading
import time
import re
import json
import sqlite3
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "anyd_booking.db"))

class TanitaReceiver:
    def __init__(self):
        self.ser: Optional[serial.Serial] = None
        self.is_listening = False
        self.listen_thread: Optional[threading.Thread] = None
        self.active_port: Optional[str] = None
        self.latest_measurement: Optional[Dict[str, Any]] = None
        self.raw_buffer = ""
        self.lock = threading.Lock()
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tanita_measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            client_name TEXT,
            appointment_id INTEGER,
            measurement_date TEXT,
            weight REAL,
            bmi REAL,
            fat_percent REAL,
            fat_mass REAL,
            muscle_mass REAL,
            ffm REAL,
            water_percent REAL,
            bone_mass REAL,
            visceral_fat REAL,
            bmr_tanita REAL,
            bmr_cunningham REAL,
            metabolic_age INTEGER,
            physical_rating INTEGER,
            segmental_data TEXT,
            raw_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients (id)
        )
        """)
        conn.commit()
        conn.close()

    def get_available_ports(self) -> List[Dict[str, str]]:
        ports = []
        for p in serial.tools.list_ports.comports():
            ports.append({
                "port": p.device,
                "description": p.description,
                "hwid": p.hwid
            })
        return ports

    def connect(self, port_name: str, baud_rate: int = 9600) -> bool:
        self.disconnect()
        try:
            self.ser = serial.Serial(
                port=port_name,
                baudrate=baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            self.active_port = port_name
            self.is_listening = True
            self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.listen_thread.start()
            print(f"[TANITA] Conectado exitosamente al puerto {port_name} a {baud_rate} baudios.")
            return True
        except Exception as e:
            print(f"[TANITA ERROR] No se pudo conectar a {port_name}: {e}")
            self.ser = None
            self.is_listening = False
            return False

    def disconnect(self):
        self.is_listening = False
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except:
                pass
        self.ser = None
        self.active_port = None
        print("[TANITA] Puerto serie desconectado.")

    def _listen_loop(self):
        while self.is_listening and self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting > 0:
                    raw_bytes = self.ser.read(self.ser.in_waiting)
                    chunk = raw_bytes.decode("ascii", errors="replace")
                    self.raw_buffer += chunk

                    # Verificar si tenemos una trama completa de la Tanita
                    # Las tramas suelen terminar en \r\n o contener delimitadores { ... } o ~
                    if "\r\n" in self.raw_buffer or "}" in self.raw_buffer:
                        lines = self.raw_buffer.splitlines()
                        for line in lines:
                            line_clean = line.strip()
                            if len(line_clean) > 15:
                                parsed = self.parse_tanita_string(line_clean)
                                if parsed:
                                    with self.lock:
                                        self.latest_measurement = parsed
                                    print(f"[TANITA] ¡Nueva medición recibida! Peso: {parsed.get('weight')} kg, Grasa: {parsed.get('fat_percent')} %")
                        self.raw_buffer = ""
                time.sleep(0.05)
            except Exception as e:
                print(f"[TANITA ERROR en escucha]: {e}")
                time.sleep(1)

    def parse_tanita_string(self, raw_str: str) -> Optional[Dict[str, Any]]:
        """
        Parser universal para Tanita MC-580 (admite formatos tokenizados, etiquetados y CSV).
        """
        data: Dict[str, Any] = {
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
            "bmr_cunningham": None,
            "metabolic_age": None,
            "physical_rating": None,
            "segmental": {}
        }

        # Formato 1: Etiquetado clásico Tanita (Wk, FW, MW, FF, WW, wW, bW, IF, rA...)
        tokens = re.findall(r'([A-Za-z0-9~]+)[,:]\s*"?([^",\r\n]+)"?', raw_str)
        token_dict = {k.strip(): v.strip() for k, v in tokens}

        def get_float(keys):
            for k in keys:
                if k in token_dict:
                    try:
                        return float(token_dict[k])
                    except:
                        pass
            return None

        # Peso
        data["weight"] = get_float(["Wk", "Wb", "Weight", "Peso", "weight"])
        # % Grasa
        data["fat_percent"] = get_float(["FW", "FAT", "Fat%", "% Grasa", "fat_percent", "F%"])
        # Masa Muscular
        data["muscle_mass"] = get_float(["MW", "MUSCLE", "MuscleMass", "Masa Muscular", "muscle_mass"])
        # Masa Libre de Grasa (FFM)
        data["ffm"] = get_float(["FF", "FFM", "Masa Libre Grasa", "ffm"])
        # % Agua Corporal
        data["water_percent"] = get_float(["wW", "TBW%", "% Agua", "water_percent"])
        # Masa Ósea
        data["bone_mass"] = get_float(["bW", "BONE", "Masa Osea", "bone_mass"])
        # Grasa Visceral
        data["visceral_fat"] = get_float(["IF", "VISCERAL", "Grasa Visceral", "visceral_fat"])
        # BMR Tanita
        data["bmr_tanita"] = get_float(["rA", "BMR", "bmr_tanita"])
        # Edad Metabólica
        data["metabolic_age"] = get_float(["MI", "AGEMETA", "Edad Metabolica", "metabolic_age"])
        # IMC
        data["bmi"] = get_float(["BMI", "IMC", "bmi"])

        # Formato 2: Si es un CSV con comas directas sin etiquetas explícitas
        if data["weight"] is None and "," in raw_str:
            parts = [p.strip().replace('"', '') for p in raw_str.split(",")]
            numeric_parts = []
            for p in parts:
                try:
                    numeric_parts.append(float(p))
                except:
                    pass
            # En la trama estándar de Tanita MC:
            # [..., Altura, Peso, %Grasa, MasaGrasa, MasaMuscular, FFM, TBW, %TBW, MasaOsea, Visceral, BMR...]
            if len(numeric_parts) >= 8:
                for idx, val in enumerate(numeric_parts):
                    if 40.0 <= val <= 250.0 and data["weight"] is None:
                        data["weight"] = val
                        if idx + 1 < len(numeric_parts) and 3.0 <= numeric_parts[idx + 1] <= 60.0:
                            data["fat_percent"] = numeric_parts[idx + 1]
                        if idx + 3 < len(numeric_parts) and 20.0 <= numeric_parts[idx + 3] <= 120.0:
                            data["muscle_mass"] = numeric_parts[idx + 3]

        # Cálculos derivados clínicos si faltan valores:
        if data["weight"] is not None and data["fat_percent"] is not None:
            data["fat_mass"] = round(data["weight"] * (data["fat_percent"] / 100.0), 2)
            if data["ffm"] is None:
                data["ffm"] = round(data["weight"] - data["fat_mass"], 2)

        # Cálculo de la Fórmula de Oro de Nutrición Deportiva: Cunningham (1980/1991)
        # BMR = 500 + 22 * FFM (kg)
        if data["ffm"] is not None:
            data["bmr_cunningham"] = round(500 + 22 * data["ffm"])

        # Validación mínima: si detectó peso, la medición es válida
        if data["weight"] is not None and data["weight"] > 20:
            return data
        return None

    def parse_csv_file(self, content_str: str) -> Optional[Dict[str, Any]]:
        """
        Parsea un archivo exportado de la tarjeta SD o CSV de la Tanita.
        """
        lines = content_str.strip().splitlines()
        res = {
            "model": "Tanita MC-580",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
            "bmr_cunningham": None,
            "metabolic_age": None,
            "physical_rating": None
        }

        for line in lines:
            line_clean = line.strip()
            # Extraer Parámetro, Valor
            parts = re.split(r"[,;:\t]", line_clean)
            if len(parts) >= 2:
                param = parts[0].strip().lower()
                val_raw = parts[1].strip()
                # Extraer números decimales
                num_match = re.search(r"[-+]?\d*\.\d+|\d+", val_raw)
                val = float(num_match.group(0)) if num_match else None

                if val is not None:
                    if "peso" in param or "weight" in param:
                        res["weight"] = val
                    elif "imc" in param or "bmi" in param:
                        res["bmi"] = val
                    elif "grasa" in param and "%" in param:
                        res["fat_percent"] = val
                    elif "agua" in param and "%" in param:
                        res["water_percent"] = val
                    elif "muscular" in param or "muscle" in param:
                        res["muscle_mass"] = val
                    elif "libre" in param or "ffm" in param:
                        res["ffm"] = val
                    elif "ósea" in param or "osea" in param or "bone" in param:
                        res["bone_mass"] = val
                    elif "visceral" in param:
                        res["visceral_fat"] = val
                    elif "bmr" in param or "basal" in param:
                        res["bmr_tanita"] = val
                    elif "metabólica" in param or "metabolica" in param or "edad" in param:
                        res["metabolic_age"] = int(val)
                    elif "física" in param or "fisica" in param or "rating" in param:
                        res["physical_rating"] = int(val)

        if res["weight"] and res["fat_percent"]:
            res["fat_mass"] = round(res["weight"] * (res["fat_percent"] / 100.0), 2)
            if not res["ffm"]:
                res["ffm"] = round(res["weight"] - res["fat_mass"], 2)

        if res["ffm"]:
            res["bmr_cunningham"] = round(500 + 22 * res["ffm"])

        if res["weight"]:
            with self.lock:
                self.latest_measurement = res
            return res
        return None

    def save_measurement_to_db(self, client_id: Optional[int], client_name: str, appt_id: Optional[int] = None, data: Optional[Dict[str, Any]] = None) -> bool:
        meas = data or self.latest_measurement
        if not meas:
            return False

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO tanita_measurements (
            client_id, client_name, appointment_id, measurement_date,
            weight, bmi, fat_percent, fat_mass, muscle_mass, ffm,
            water_percent, bone_mass, visceral_fat, bmr_tanita, bmr_cunningham,
            metabolic_age, physical_rating, raw_data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            client_id,
            client_name,
            appt_id,
            meas.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            meas.get("weight"),
            meas.get("bmi"),
            meas.get("fat_percent"),
            meas.get("fat_mass"),
            meas.get("muscle_mass"),
            meas.get("ffm"),
            meas.get("water_percent"),
            meas.get("bone_mass"),
            meas.get("visceral_fat"),
            meas.get("bmr_tanita"),
            meas.get("bmr_cunningham"),
            meas.get("metabolic_age"),
            meas.get("physical_rating"),
            json.dumps(meas, ensure_ascii=False)
        ))
        conn.commit()
        conn.close()
        print(f"[TANITA] Medición guardada exitosamente en la base de datos para: {client_name}")
        return True

    def simulate_measurement(self, weight: float = 74.2, fat_pct: float = 13.8, muscle: float = 61.2) -> Dict[str, Any]:
        """
        Simulación para pruebas inmediatas en consulta sin necesidad de conectar la báscula física.
        """
        fat_mass = round(weight * (fat_pct / 100.0), 2)
        ffm = round(weight - fat_mass, 2)
        cunningham = round(500 + 22 * ffm)
        
        sim = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "model": "Tanita MC-580",
            "weight": weight,
            "bmi": 23.4,
            "fat_percent": fat_pct,
            "fat_mass": fat_mass,
            "muscle_mass": muscle,
            "ffm": ffm,
            "water_percent": 63.5,
            "bone_mass": 3.2,
            "visceral_fat": 4.0,
            "bmr_tanita": 1785.0,
            "bmr_cunningham": cunningham,
            "metabolic_age": 25,
            "physical_rating": 5,
            "segmental": {
                "right_arm_muscle": 3.4,
                "left_arm_muscle": 3.3,
                "right_leg_muscle": 9.8,
                "left_leg_muscle": 9.7,
                "trunk_muscle": 35.0
            },
            "raw": "SIMULATED_DATA_MC580"
        }
        with self.lock:
            self.latest_measurement = sim
        return sim

# Instancia singleton del receptor
tanita_instance = TanitaReceiver()
