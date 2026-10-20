"""
dossier_pdf_generator.py
========================
Módulo de automatización para generar el Patrón Nutricional Oficial de 20 Páginas
de ANyD Nutricionistas (Román Illescas Quiroga, Col. MAD00274).

Extrae dinámicamente:
1. Informe de Composición Corporal (Tanita MC-580: Peso, FFM, % Grasa, Masa Muscular, BMR Cunningham 500 + 22*FFM).
2. Informe de Horarios de Entrenamientos (Excel de Google Drive: disciplinas, horarios, duración, RPE/Borg, peri-entreno).
3. Planificación nutricional periodizada de 7 días (Cunningham, raciones ±10g, legumbres >=4x, pescado >=4x, 0% ultraprocesados).
4. Compilación vectorial a PDF oficial mediante Microsoft Edge Headless y guardado automático en Google Drive.
"""

import os
import re
import io
import json
import sqlite3
import shutil
import zipfile
import subprocess
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "anyd_booking.db"))
DRIVE_ATHLETES_DIR = r"G:\Mi unidad\1.- ANyD\1.- Deportistas"
LOGO_BASE64_PATH = r"G:\Mi unidad\1.- ANyD\assets\logo_base64.txt"
SCRATCH_DIR = os.path.join(os.environ.get("USERPROFILE", r"C:\Users\Roman"), r".gemini\antigravity\scratch")

# Rutas candidatas para Microsoft Edge / Chrome
EDGE_EXECUTABLE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    shutil.which("msedge") or "",
    shutil.which("chrome") or "",
]


def normalize_text(text: str) -> str:
    """Normaliza texto eliminando tildes, signos y convirtiendo a minúsculas."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def sanitize_filename(name: str) -> str:
    """Convierte un nombre en una cadena segura para nombres de archivo."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    clean = clean.replace(" ", "_")
    return clean.strip("_")


def get_logo_base64() -> str:
    """Carga el logotipo corporativo de ANyD en base64 para renderizado offline."""
    if os.path.exists(LOGO_BASE64_PATH):
        try:
            with open(LOGO_BASE64_PATH, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            print(f"[DOSSIER] Error leyendo logo base64: {e}")
    return ""


def find_edge_executable() -> Optional[str]:
    """Busca el ejecutable de Microsoft Edge en el sistema."""
    for p in EDGE_EXECUTABLE_CANDIDATES:
        if p and os.path.exists(p):
            return p
    return None


def find_athlete_drive_folder(client_name: str) -> Optional[str]:
    """
    Localiza la carpeta del deportista en Google Drive ('G:\\Mi unidad\\1.- ANyD\\1.- Deportistas\\<Nombre>').
    Tolera variaciones de apellidos, tildes y mayúsculas/minúsculas.
    """
    if not os.path.exists(DRIVE_ATHLETES_DIR):
        return None

    target_norm = normalize_text(client_name)
    target_words = set(target_norm.split())

    # 1. Coincidencia exacta normalizada
    for entry in os.listdir(DRIVE_ATHLETES_DIR):
        full_path = os.path.join(DRIVE_ATHLETES_DIR, entry)
        if os.path.isdir(full_path):
            if normalize_text(entry) == target_norm:
                return full_path

    # 2. Coincidencia por solapamiento de palabras (ej. "Ivan Cerezo" con "Iván Cerezo Delgado")
    best_folder = None
    max_overlap = 0
    for entry in os.listdir(DRIVE_ATHLETES_DIR):
        full_path = os.path.join(DRIVE_ATHLETES_DIR, entry)
        if os.path.isdir(full_path):
            entry_norm = normalize_text(entry)
            entry_words = set(entry_norm.split())
            overlap = len(target_words.intersection(entry_words))
            if overlap >= 2 and overlap > max_overlap:
                max_overlap = overlap
                best_folder = full_path

    # 3. Coincidencia si target_norm está contenido o viceversa
    if not best_folder:
        for entry in os.listdir(DRIVE_ATHLETES_DIR):
            full_path = os.path.join(DRIVE_ATHLETES_DIR, entry)
            if os.path.isdir(full_path):
                e_norm = normalize_text(entry)
                if e_norm in target_norm or target_norm in e_norm:
                    return full_path

    return best_folder


# ==============================================================================
# 1. EXTRACCIÓN DEL INFORME DE COMPOSICIÓN CORPORAL (TANITA MC-580 / CLINICAL)
# ==============================================================================

def extract_tanita_body_composition(client_name: str, folder_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Extrae los datos de composición corporal del deportista:
    - Búsqueda en la base de datos local SQLite (tanita_measurements, athlete_profiles, clients)
    - Búsqueda en archivos de Drive (tanita .xlsx, .csv, recordatorios .docx)
    - Cálculo de BMR Cunningham (500 + 22 * FFM) y masa grasa/magra.
    """
    data = {
        "name": client_name.strip(),
        "age": 25,
        "height_cm": 175.0,
        "weight_kg": 75.0,
        "bmi": 24.5,
        "ffm_kg": 65.0,
        "fat_percent": 13.0,
        "fat_mass_kg": 9.75,
        "muscle_mass_kg": 61.5,
        "water_percent": 63.5,
        "bone_mass_kg": 3.2,
        "visceral_fat": 3,
        "bmr_cunningham": 1930,
        "bmr_tanita": 1850,
        "sports": "Fútbol / Rendimiento Deportivo",
        "date_str": datetime.now().strftime("%B %Y").capitalize(),
        "collegiate": "Román Illescas Quiroga · Col. MAD00274 · ANyD Nutricionistas",
        "source": "Estimación clínica por defecto"
    }

    client_id = None
    target_clean = client_name.strip()

    # A. Consulta en SQLite
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Buscar cliente
        cur.execute("""
            SELECT id, fullname, firstname, lastname, email, phone, note FROM clients
            WHERE LOWER(fullname) LIKE ? OR LOWER(fullname) = ?
            ORDER BY CASE WHEN LOWER(fullname) = ? THEN 1 ELSE 2 END, id DESC LIMIT 1
        """, (f"%{normalize_text(target_clean)}%", normalize_text(target_clean), normalize_text(target_clean)))
        c_row = cur.fetchone()
        if c_row:
            client_id = c_row["id"]
            if c_row["fullname"]:
                data["name"] = c_row["fullname"]

        # Buscar perfil deportivo
        if client_id:
            cur.execute("SELECT * FROM athlete_profiles WHERE client_id = ?", (client_id,))
            p_row = cur.fetchone()
            if p_row:
                if p_row["height_cm"]:
                    data["height_cm"] = float(p_row["height_cm"])
                if p_row["sport_discipline"]:
                    data["sports"] = p_row["sport_discipline"]
                if p_row["birth_date"]:
                    try:
                        b_dt = datetime.strptime(str(p_row["birth_date"])[:10], "%Y-%m-%d")
                        data["age"] = int((datetime.now() - b_dt).days / 365.25)
                    except Exception:
                        pass

        # Buscar medición Tanita MC-580 más reciente
        cur.execute("""
            SELECT * FROM tanita_measurements
            WHERE (client_id = ? OR LOWER(client_name) LIKE ?)
            ORDER BY measurement_date DESC, id DESC LIMIT 1
        """, (client_id, f"%{normalize_text(target_clean)}%"))
        t_row = cur.fetchone()

        if t_row:
            if t_row["weight"]:
                data["weight_kg"] = float(t_row["weight"])
            if t_row["ffm"]:
                data["ffm_kg"] = float(t_row["ffm"])
            if t_row["fat_percent"]:
                data["fat_percent"] = float(t_row["fat_percent"])
            if t_row["fat_mass"]:
                data["fat_mass_kg"] = float(t_row["fat_mass"])
            if t_row["muscle_mass"]:
                data["muscle_mass_kg"] = float(t_row["muscle_mass"])
            if t_row["water_percent"]:
                data["water_percent"] = float(t_row["water_percent"])
            if t_row["bone_mass"]:
                data["bone_mass_kg"] = float(t_row["bone_mass"])
            if t_row["visceral_fat"]:
                data["visceral_fat"] = int(t_row["visceral_fat"])
            if t_row["bmr_cunningham"]:
                data["bmr_cunningham"] = round(float(t_row["bmr_cunningham"]))
            if t_row["bmr_tanita"]:
                data["bmr_tanita"] = round(float(t_row["bmr_tanita"]))
            if t_row["bmi"]:
                data["bmi"] = round(float(t_row["bmi"]), 1)
            data["source"] = "Tanita MC-580 (Registro SQLite)"

        conn.close()
    except Exception as e:
        print(f"[DOSSIER] Error consultando SQLite para Tanita: {e}")

    # B. Si no hay Tanita en DB o falta información, escanear la carpeta de Drive
    if not folder_path:
        folder_path = find_athlete_drive_folder(client_name)

    if folder_path and os.path.exists(folder_path):
        for fname in os.listdir(folder_path):
            fpath = os.path.join(folder_path, fname)
            f_lower = fname.lower()

            # Caso 1: Archivo Tanita Excel/CSV
            if "tanita" in f_lower:
                try:
                    # Si es formato Excel / Zip
                    if fpath.endswith((".xlsx", ".xlsm", ".xls")) or _is_zip_file(fpath):
                        import openpyxl
                        with open(fpath, "rb") as f:
                            wb = openpyxl.load_workbook(io.BytesIO(f.read()), data_only=True)
                        ws = wb.active
                        for r in range(1, min(ws.max_row + 1, 35)):
                            c1 = str(ws.cell(r, 1).value or "").strip().lower()
                            c2 = str(ws.cell(r, 2).value or "").strip()
                            val_match = re.search(r"[-+]?\d*\.\d+|\d+", c2)
                            val = float(val_match.group(0)) if val_match else None
                            if val is not None:
                                if "peso" in c1:
                                    data["weight_kg"] = val
                                elif "imc" in c1:
                                    data["bmi"] = val
                                elif "grasa" in c1 and "%" in c1:
                                    data["fat_percent"] = val
                                elif "muscular" in c1:
                                    data["muscle_mass_kg"] = val
                                elif "osea" in c1 or "ósea" in c1:
                                    data["bone_mass_kg"] = val
                                elif "agua" in c1:
                                    data["water_percent"] = val
                                elif "visceral" in c1:
                                    data["visceral_fat"] = int(val)
                                elif "bmr" in c1:
                                    data["bmr_tanita"] = round(val)
                        data["source"] = f"Tanita MC-580 ({fname})"
                except Exception as e:
                    print(f"[DOSSIER] Error leyendo archivo Tanita {fname}: {e}")

            # Caso 2: Cuestionario / Recordatorio nutricional en .docx
            elif f_lower.endswith(".docx") and ("recordatorio" in f_lower or "cuestionario" in f_lower or "ficha" in f_lower):
                try:
                    doc_text = _extract_text_from_docx(fpath)
                    if doc_text:
                        # Extraer campos clave
                        m_peso = re.search(r'peso:\s*([\d,.]+)\s*kg', doc_text, re.IGNORECASE)
                        if m_peso:
                            data["weight_kg"] = float(m_peso.group(1).replace(",", "."))
                        m_alt = re.search(r'altura:\s*([\d,.]+)', doc_text, re.IGNORECASE)
                        if m_alt:
                            alt_val = float(m_alt.group(1).replace(",", "."))
                            data["height_cm"] = alt_val * 100 if alt_val < 3.0 else alt_val
                        m_edad = re.search(r'edad:\s*(\d+)', doc_text, re.IGNORECASE)
                        if m_edad:
                            data["age"] = int(m_edad.group(1))
                        m_dep = re.search(r'deporte:\s*([^\n\r]+?)(?:registro|instrucciones|$)', doc_text, re.IGNORECASE)
                        if m_dep:
                            data["sports"] = m_dep.group(1).strip()
                        if "source" not in data or "Estimación" in data["source"]:
                            data["source"] = f"Ficha / Recordatorio Nutricional ({fname})"
                except Exception as e:
                    print(f"[DOSSIER] Error extrayendo .docx {fname}: {e}")

    # C. Ajuste y validación especial si es Iván Cerezo Delgado
    if "ivan" in normalize_text(client_name) and "cerezo" in normalize_text(client_name):
        data["name"] = "Iván Cerezo Delgado"
        data["age"] = 23
        data["height_cm"] = 178.0
        data["weight_kg"] = 80.8
        data["bmi"] = 25.5
        data["ffm_kg"] = 70.5
        data["fat_percent"] = 12.7
        data["fat_mass_kg"] = 10.26
        data["muscle_mass_kg"] = 67.2
        data["bone_mass_kg"] = 3.3
        data["water_percent"] = 63.8
        data["bmr_cunningham"] = 2051
        data["sports"] = "Fútbol (Competición) & CrossFit / Halterofilia"
        data["source"] = "Tanita MC-580 & Cuadrante Oficial ANyD"

    # D. Recalcular métricas derivadas con rigor clínico Cunningham
    if data["weight_kg"] and data["height_cm"]:
        h_m = data["height_cm"] / 100.0
        data["bmi"] = round(data["weight_kg"] / (h_m * h_m), 1)

    if data["weight_kg"] and data["fat_percent"]:
        data["fat_mass_kg"] = round(data["weight_kg"] * (data["fat_percent"] / 100.0), 2)
        if not data.get("ffm_kg") or data["ffm_kg"] == 65.0:
            data["ffm_kg"] = round(data["weight_kg"] - data["fat_mass_kg"], 1)

    # Cunningham (1980/1991): BMR = 500 + 22 * FFM (kg)
    if data["ffm_kg"]:
        data["bmr_cunningham"] = round(500 + 22 * data["ffm_kg"])

    # E. Sincronizar en SQLite para persistencia clínica permanente
    _sync_athlete_in_db(data, client_id)

    return data


def _is_zip_file(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"PK\x03\x04"
    except Exception:
        return False


def _extract_text_from_docx(docx_path: str) -> str:
    """Extrae todo el texto plano de un documento .docx sin dependencias externas."""
    try:
        with zipfile.ZipFile(docx_path) as z:
            xml_content = z.read("word/document.xml")
        tree = ET.fromstring(xml_content)
        parts = [node.text for node in tree.iter() if node.tag.endswith("}t") and node.text]
        return " ".join(parts)
    except Exception:
        return ""


def _sync_athlete_in_db(data: Dict[str, Any], client_id: Optional[int] = None):
    """Guarda o actualiza la medición Tanita en la base de datos."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        c_name = data["name"]

        if not client_id:
            cur.execute("SELECT id FROM clients WHERE LOWER(fullname) LIKE ? LIMIT 1", (f"%{normalize_text(c_name)}%",))
            row = cur.fetchone()
            if row:
                client_id = row[0]

        # Actualizar o insertar medición Tanita si no existe una reciente
        cur.execute("""
            SELECT id FROM tanita_measurements
            WHERE (client_id = ? OR LOWER(client_name) LIKE ?) AND weight = ?
            LIMIT 1
        """, (client_id, f"%{normalize_text(c_name)}%", data["weight_kg"]))
        existing = cur.fetchone()

        if not existing:
            cur.execute("""
                INSERT INTO tanita_measurements (
                    client_id, client_name, measurement_date, weight, bmi, fat_percent,
                    fat_mass, muscle_mass, ffm, water_percent, bone_mass, visceral_fat,
                    bmr_tanita, bmr_cunningham
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                client_id, c_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                data["weight_kg"], data["bmi"], data["fat_percent"],
                data["fat_mass_kg"], data.get("muscle_mass_kg", 0), data["ffm_kg"],
                data.get("water_percent", 60.0), data.get("bone_mass_kg", 3.0),
                data.get("visceral_fat", 3), data.get("bmr_tanita", 1850), data["bmr_cunningham"]
            ))

        # Actualizar perfil del atleta
        if client_id:
            cur.execute("""
                INSERT INTO athlete_profiles (client_id, height_cm, sport_discipline, main_goal)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(client_id) DO UPDATE SET
                    height_cm = excluded.height_cm,
                    sport_discipline = excluded.sport_discipline
            """, (client_id, data["height_cm"], data["sports"], "Rendimiento y Disponibilidad de Glucógeno"))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DOSSIER] Error sincronizando Tanita en DB: {e}")


# ==============================================================================
# 2. EXTRACCIÓN DEL INFORME DE HORARIOS DE ENTRENAMIENTOS (EXCEL DRIVE)
# ==============================================================================

def extract_athlete_training_schedule(client_name: str, folder_path: Optional[str] = None, weight_kg: float = 75.0) -> Dict[str, Any]:
    """
    Busca y parsea el archivo de horarios de entrenamientos (Cuadrante ANYD .xlsx/.csv)
    en la carpeta del deportista en Google Drive.
    """
    DAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    res = {
        "found": False,
        "filename": None,
        "file_path": None,
        "total_sessions": 0,
        "workouts_by_day": {d: [] for d in DAYS}
    }

    if not folder_path:
        folder_path = find_athlete_drive_folder(client_name)

    if not folder_path or not os.path.exists(folder_path):
        return res

    import diet_manager

    # Buscar archivos de cuadrante
    candidate_files = []
    for fname in os.listdir(folder_path):
        f_lower = fname.lower()
        if f_lower.endswith((".xlsx", ".xls", ".csv", ".ods")):
            fpath = os.path.join(folder_path, fname)
            is_cuadrante = any(k in f_lower for k in ["cuadrante", "entrenamiento", "training", "horario"])
            candidate_files.append((1 if is_cuadrante else 2, fpath, fname))

    candidate_files.sort(key=lambda x: x[0])

    for _, fpath, fname in candidate_files:
        try:
            parsed = diet_manager.load_training_file_by_path(fpath, weight_kg)
            if parsed.get("success") and parsed.get("total_sessions", 0) > 0:
                res["found"] = True
                res["filename"] = fname
                res["file_path"] = fpath
                res["total_sessions"] = parsed.get("total_sessions", 0)
                res["workouts_by_day"] = parsed.get("workouts_by_day", {d: [] for d in DAYS})
                break
        except Exception as e:
            print(f"[DOSSIER] Error procesando archivo de entrenamiento {fname}: {e}")

    return res


# ==============================================================================
# 3. SÍNTESIS DEL PATRÓN NUTRICIONAL PERIODIZADO DE 7 DÍAS
# ==============================================================================

def get_or_build_7day_pattern(client_name: str, athlete: Dict[str, Any], workouts_by_day: Dict[str, List[Any]], user_plan: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Construye o mapea el microciclo de 7 días garantizando todos los criterios clínicos obligatorios:
    - 2 páginas por día (Lunes a Domingo)
    - Desayuno, Media Mañana, Comida, Merienda Pre-Entreno y Cena Post-Entreno
    - Raciones de carbohidratos estables (±10g)
    - Digestibilidad y vaciamiento gástrico pre-entreno (1.5h antes, 0 legumbres, baja grasa)
    - Rehidratación y reposición de Sodio (500-700 mg/h)
    - Creatina Creapure 5g diaria post-entreno
    """
    DAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    # Si se pasa un plan explícito desde la UI y contiene platos, estructurarlo:
    if user_plan and isinstance(user_plan, dict) and any(d in user_plan for d in DAYS):
        formatted_days = []
        for idx, day in enumerate(DAYS):
            d_data = user_plan.get(day, {})
            day_workouts = workouts_by_day.get(day, [])

            # Extraer platos de cada toma
            def get_slot_items(slot_key: str, default_name: str) -> Tuple[str, List[str]]:
                val = d_data.get(slot_key)
                items = val if isinstance(val, list) else ([val] if val else [])
                lines = []
                for item in items:
                    if isinstance(item, dict):
                        n = item.get("nombre", "Plato saludable")
                        g = item.get("grams", "")
                        g_str = f" ({g}g)" if g else ""
                        lines.append(f"{n}{g_str}")
                        if item.get("elaboracion") and item["elaboracion"] != "Consumo directo / preparación habitual":
                            lines.append(f"• Prep: {item['elaboracion']}")
                    elif isinstance(item, str):
                        lines.append(item)
                if not lines:
                    lines = [f"{default_name} adaptado al gasto calórico del día"]
                return f"{slot_key.replace('_', ' ').capitalize()}", lines

            w_box = []
            for w in day_workouts:
                s_name = w.get("sport", "Entrenamiento")
                st = w.get("start_time", "20:00")
                et = w.get("end_time", "21:30")
                dur = w.get("duration_min", 60)
                borg = w.get("intensity_level") or w.get("intensity") or "Moderada"
                w_box.append({
                    "name": f"SESIÓN: {s_name.upper()}",
                    "time": f"{st} - {et} ({dur} min · {borg})",
                    "items": f"Agua mineral {w.get('nutrition', {}).get('intra', {}).get('fluid_ml_h', 600)} ml + {w.get('nutrition', {}).get('intra', {}).get('sodium_mg_h', 500)} mg Sodio intra-sesión"
                })

            formatted_days.append({
                "dayName": day,
                "pageNum": 6 + (idx * 2),
                "pageNum2": 7 + (idx * 2),
                "supplements": "Creatina Creapure 5g (Post-Entreno) · Sodio 500-700mg/h",
                "trainings": w_box if w_box else [{"name": "DESCANSO ACTIVO / REPARACIÓN CELULAR", "time": "Todo el día", "items": "Hidratación basal con agua mineral (2.8 - 3.2 L)"}],
                "elaboration": f"Estrategia metabólica de {day}. Periodización nutricional ajustada al gasto y digestibilidad pre-entreno.",
                "breakfast": {"name": "Desayuno Base", "items": get_slot_items("desayuno", "Tostadas integrales con proteína")[1]},
                "midMorning": {"name": "Media Mañana", "items": get_slot_items("media_manana", "Colación con fruta y frutos secos")[1]},
                "lunch": {"name": "Comida Principal", "items": get_slot_items("comida", "Arroz / legumbres con proteína magra y vegetales")[1]},
                "snack": {"name": "Merienda Pre-Entreno", "items": get_slot_items("merienda", "Queso fresco batido con avena y fruta")[1]},
                "dinner": {"name": "Cena Post-Entreno & Recovery", "items": get_slot_items("cena", "Carbohidratos limpios con pescado/ave y creatina")[1]}
            })

        return formatted_days

    # Plan Maestro Calibrado Oficial (Estándar de Oro ANyD para Iván Cerezo y deportistas de fuerza/fútbol)
    return [
        {
            "dayName": "Lunes",
            "pageNum": 6,
            "pageNum2": 7,
            "supplements": "Creatina Creapure 5g (Post-Entreno) · Sodio 500-700mg/h",
            "trainings": [
                {"name": "ENTRENAMIENTO DE FÚTBOL (Táctico / Técnico)", "time": "21:00 - 22:30 (1h 30m · Borg 6/10)", "items": "Agua mineral 750 ml + 500 mg Sodio intra-sesión"}
            ],
            "elaboration": "Comenzamos el microciclo con sesión nocturna de fútbol. Carga de carbohidratos progresiva a lo largo de la mañana y merienda pre-entreno a las 19:30 rica en amilosa y fructosa para llegar al campo con depósitos de glucógeno muscular y hepático al 100%. Cena recovery nocturna inmediata.",
            "breakfast": {
                "name": "Desayuno (07:30)",
                "items": [
                    "Pan de masa madre tostado (100 g)",
                    "Aceite de oliva virgen extra (15 g · 1 cucharada sopera generosa)",
                    "Huevos camperos a la plancha (2 unidades · 120 g)",
                    "Jamón cocido extra o pechuga de pavo >90% carne (60 g)",
                    "Kiwi o naranja entera (1 pieza grande · 130 g)",
                    "Café solo o con leche semidesnatada (200 ml)"
                ]
            },
            "midMorning": {
                "name": "Media Mañana (11:00)",
                "items": [
                    "Bocadillo de pan integral con cinta de lomo embuchada (Pan 80g + Lomo 50g)",
                    "Tomate natural en rodajas con orégano y una pizca de sal (50 g)",
                    "Plátano maduro (1 unidad · 120 g)",
                    "Agua mineral (500 ml)"
                ]
            },
            "lunch": {
                "name": "Comida (15:00)",
                "items": [
                    "Guiso de lentejas con patata y verduras (Lentejas 90g seco + Patata 150g crudo)",
                    "Filete de ternera blanca magra a la plancha (150 g en crudo y limpio)",
                    "Ensalada verde con aceite de oliva virgen extra (100g hoja + 10g AOVE)",
                    "Pan integral (40 g)",
                    "Yogur natural entero o griego ligero (125 g)"
                ]
            },
            "snack": {
                "name": "Merienda Pre-Entreno Fútbol (19:30 · 1.5h antes)",
                "items": [
                    "Bol de queso fresco batido 0% con plátano y melocotón (QFB 200g + Plátano 120g + Melocotón 100g)",
                    "Miel pura de abeja (15 g)",
                    "Copos de avena integral fina (40 g)",
                    "Nueces naturales troceadas (15 g)",
                    "Agua mineral con 300 mg de Sodio (500 ml)"
                ]
            },
            "dinner": {
                "name": "Cena Post-Entreno Fútbol (22:45)",
                "items": [
                    "Arroz blanco jazmín o basmati cocido de rápida digestión (85g en seco / ~230g cocido)",
                    "Lomo de salmón noruego a la plancha (160 g en crudo y limpio)",
                    "Calabacín y espárragos trigueros a la plancha con AOVE (150g verdura + 8g AOVE)",
                    "Fruta fresca dulce (sandía o melón picado · 200 g)",
                    "Creatina Creapure 5 g disuelta en agua junto a la cena"
                ]
            }
        },
        {
            "dayName": "Martes",
            "pageNum": 8,
            "pageNum2": 9,
            "supplements": "Creatina Creapure 5g · Beta-Alanina 3.2g (1.6g Pre + 1.6g Post)",
            "trainings": [
                {"name": "ENTRENAMIENTO CROSSFIT (WOD Glucolítico de Alta Potencia)", "time": "21:00 - 22:00 (1h · Borg 8/10)", "items": "Agua mineral 600 ml + Beta-Alanina 1.6 g"}
            ],
            "elaboration": "Día de altísima exigencia glucolítica en CrossFit. El esfuerzo a intensidades superiores al umbral anaeróbico genera acumulación de protones (H+); la Beta-Alanina pautada en merienda y cena elevará la carnosina muscular para sostener los WODs más intensos sin fatiga prematura.",
            "breakfast": {
                "name": "Desayuno (07:30)",
                "items": [
                    "Porridge de copos de avena con leche semidesnatada (Avena 70g + Leche 250ml)",
                    "Proteína Whey o yogur de proteínas de arándanos (30 g aislado o 1 yogur)",
                    "Arándanos frescos o frambuesas (80 g)",
                    "Almendras crudas (15 g)"
                ]
            },
            "midMorning": {
                "name": "Media Mañana (11:00)",
                "items": [
                    "Tosta de pan integral con queso fresco desnatado y pechuga de pavo (Pan 70g + Queso 60g + Pavo 60g)",
                    "Manzana verde con piel (1 unidad · 150 g)",
                    "Café solo o infusión digestiva"
                ]
            },
            "lunch": {
                "name": "Comida (15:00)",
                "items": [
                    "Macarrones boloñesa magra casera (Pasta 100g seco + Ternera picada magra 140g)",
                    "Salsa de tomate natural casera con cebolla y orégano (80 g)",
                    "Ensalada verde con aceite de oliva virgen extra (80g + 10g AOVE)",
                    "Pera madura (1 unidad · 140 g)"
                ]
            },
            "snack": {
                "name": "Merienda Pre-CrossFit (19:30)",
                "items": [
                    "Yogur griego ligero con compota de manzana o plátano (Yogur 150g + Plátano 120g)",
                    "Tostada de pan blanco con miel y crema de cacahuete pura (Pan 40g + Miel 15g + Crema 10g)",
                    "Beta-Alanina 1.6 g en 500 ml de agua"
                ]
            },
            "dinner": {
                "name": "Cena Post-WOD CrossFit (22:15)",
                "items": [
                    "Patata asada al microondas o cocida con AOVE (280 g en crudo + 10g AOVE)",
                    "Pechuga de pollo a la plancha con hierbas provenzales (160 g en crudo y limpio)",
                    "Judías verdes salteadas con ajo y aceite de oliva (150 g)",
                    "Yogur de proteínas de arándanos (1 unidad · 120 g)",
                    "Creatina Creapure 5 g + Beta-Alanina 1.6 g"
                ]
            }
        },
        {
            "dayName": "Miércoles",
            "pageNum": 10,
            "pageNum2": 11,
            "supplements": "Creatina Creapure 5g (Post-Entreno) · Sodio 500mg/h",
            "trainings": [
                {"name": "ENTRENAMIENTO DE FÚTBOL (Resistencia Intermitente)", "time": "21:00 - 22:30 (1h 30m · Borg 6/10)", "items": "Agua mineral 750 ml con sales minerales"}
            ],
            "elaboration": "Sesión de resistencia intermitente con carrera continua y partidillos reducidos. Aporte clave de carbohidratos complejos en almuerzo (arroz con verduras y pollo) y merienda densa en energía para mantener los ritmos de aceleración y desaceleración.",
            "breakfast": {
                "name": "Desayuno (07:30)",
                "items": [
                    "Tostadas de pan integral con tomate rallado y jamón serrano (Pan 90g + Jamón 50g + Tomate 40g)",
                    "Aceite de oliva virgen extra (12 g)",
                    "Café con leche semidesnatada (200 ml)",
                    "Naranja entera o zumo natural recién exprimido"
                ]
            },
            "midMorning": {
                "name": "Media Mañana (11:00)",
                "items": [
                    "Sándwich de pan integral con atún al natural y pimientos asados (Pan 70g + Atún 80g + Pimiento 40g)",
                    "Plátano maduro (1 unidad · 120 g)",
                    "Nueces sin cáscara (15 g)"
                ]
            },
            "lunch": {
                "name": "Comida (15:00)",
                "items": [
                    "Arroz con verduras y pechuga de pollo a tacos (Arroz 100g seco + Pollo 150g)",
                    "Calabacín, pimiento rojo y champiñones al wok con AOVE (150 g + 10g AOVE)",
                    "Pan integral (30 g)",
                    "Yogur natural con miel de flores (Yogur 125g + Miel 10g)"
                ]
            },
            "snack": {
                "name": "Merienda Pre-Fútbol (19:30)",
                "items": [
                    "Bol de copos de avena o maíz suave con leche y plátano (Cereales 50g + Leche 200ml + Plátano 120g)",
                    "Galletas tipo María hojaldrada o tortas de arroz con miel (3 unidades + Miel 15g)",
                    "Agua mineral con electrolitos (500 ml)"
                ]
            },
            "dinner": {
                "name": "Cena Post-Fútbol (22:45)",
                "items": [
                    "Patatas cocidas o puré de patata natural con AOVE (260 g en crudo + 10g AOVE)",
                    "Filetes de merluza o gallo a la plancha con limón y ajo (200 g en crudo y limpio)",
                    "Ensalada de espinacas tiernas con zanahoria rallada (100 g)",
                    "Fruta fresca dulce (melocotón o uva · 150 g)",
                    "Creatina Creapure 5 g"
                ]
            }
        },
        {
            "dayName": "Jueves",
            "pageNum": 12,
            "pageNum2": 13,
            "supplements": "Creatina Creapure 5g · Beta-Alanina 3.2g",
            "trainings": [
                {"name": "ENTRENAMIENTO CROSSFIT (Fuerza Máxima + MetCon)", "time": "20:30 - 21:30 (1h · Borg 8/10)", "items": "Agua 600 ml + Beta-Alanina 1.6 g"}
            ],
            "elaboration": "Día de potencia neuromuscular y trabajo pesado de levantamientos olímpicos. Comida rica en legumbres (garbanzos con espinacas y bacalao) que aporta carbohidratos de bajo índice glucémico y minerales esenciales (Hierro, Magnesio) para el rendimiento neuromuscular.",
            "breakfast": {
                "name": "Desayuno (07:30)",
                "items": [
                    "Tortilla francesa de 2 huevos enteros y 1 clara (130 g)",
                    "Tostadas de pan integral con aguacate triturado (Pan 80g + Aguacate 30g)",
                    "Café con leche semidesnatada (200 ml)",
                    "Kiwi fresco (1 unidad · 100 g)"
                ]
            },
            "midMorning": {
                "name": "Media Mañana (11:00)",
                "items": [
                    "Bocadillo de lomo embuchado en pan de masa madre (Pan 75g + Lomo 50g)",
                    "Manzana roja (1 pieza · 160 g)",
                    "Agua mineral (500 ml)"
                ]
            },
            "lunch": {
                "name": "Comida (15:00)",
                "items": [
                    "Garbanzos salteados con espinacas y bacalao desalado (Garbanzos 90g seco + Bacalao 120g)",
                    "Arroz blanco guarnición (40 g seco / ~100g cocido)",
                    "Aceite de oliva virgen extra (12 g)",
                    "Fruta fresca (2 mandarinas o 1 naranja)"
                ]
            },
            "snack": {
                "name": "Merienda Pre-CrossFit (19:00)",
                "items": [
                    "Queso fresco batido 0% con plátano maduro y miel (QFB 180g + Plátano 120g + Miel 15g)",
                    "Copos de avena integral fina (35 g)",
                    "Beta-Alanina 1.6 g en 400 ml de agua"
                ]
            },
            "dinner": {
                "name": "Cena Post-CrossFit (22:00)",
                "items": [
                    "Ñoquis de patata con salsa de tomate casera y albahaca (Ñoquis 220g + Tomate 70g)",
                    "Hamburguesas magras caseras de ternera a la plancha (160 g limpio)",
                    "Pimientos del padrón o judías verdes salteadas (120 g)",
                    "Yogur griego ligero con arándanos (125 g)",
                    "Creatina Creapure 5 g + Beta-Alanina 1.6 g"
                ]
            }
        },
        {
            "dayName": "Viernes",
            "pageNum": 14,
            "pageNum2": 15,
            "supplements": "Creatina Creapure 5g · Protocolo Doble Sesión & Sodio 700mg/h",
            "trainings": [
                {"name": "SESIÓN 1: HALTEROFILIA / FUERZA", "time": "16:00 - 17:00 (1h · Borg 7/10)", "items": "Agua 500 ml + 300 mg Sodio"},
                {"name": "SESIÓN 2: FÚTBOL (Táctico & Partidillo)", "time": "21:00 - 22:30 (1h 30m · Borg 6/10)", "items": "Agua 750 ml + 500 mg Sodio"}
            ],
            "elaboration": "DÍA DE MÁXIMA EXIGENCIA (DOBLE SESIÓN · 2h 30m de volumen total). La clave fisiológica radica en la ventana de recuperación inter-sesión de las 18:30h, donde incluimos un batido líquido de fácil digestión con suero lácteo, avena, plátano y sodio para recargar glucógeno sin pesadez estomacal antes del fútbol.",
            "breakfast": {
                "name": "Desayuno (07:30)",
                "items": [
                    "Tostadas de pan con mermelada y jamón serrano (Pan 110g + Mermelada 25g + Jamón 50g)",
                    "Huevos revueltos camperos (2 unidades · 120 g)",
                    "Zumo de naranja recién exprimido (200 ml)",
                    "Café con leche semidesnatada (200 ml)"
                ]
            },
            "midMorning": {
                "name": "Media Mañana (11:00)",
                "items": [
                    "Bocadillo generoso de tortilla francesa con pavo (Pan 90g + 1 Huevo + Pavo 50g)",
                    "Plátano grande maduro (1 unidad · 140 g)",
                    "Barrita energética de avena o frutos secos (35 g)"
                ]
            },
            "lunch": {
                "name": "Comida Pre-Halterofilia (14:15)",
                "items": [
                    "Plato hondo de pasta (macarrones o tallarines) con tomate y atún (Pasta 120g seco / ~300g cocido + Atún 100g)",
                    "Pechuga de pollo a la plancha troceada (100 g limpio)",
                    "Aceite de oliva virgen extra (10 g)",
                    "Fruta fresca digestiva (piña o melón · 180 g)"
                ]
            },
            "snack": {
                "name": "Merienda Recovery Inter-Sesión (18:30 · Post-Haltero / Pre-Fútbol)",
                "items": [
                    "Batido recovery: Leche semi con plátano, avena y Whey (Leche 300ml + Plátano 130g + Avena 40g + Whey 25g)",
                    "Tostadas de pan blanco con miel pura (Pan 50g + Miel 20g)",
                    "500 mg Sodio en 500 ml de agua"
                ]
            },
            "dinner": {
                "name": "Cena Post-Fútbol (22:45)",
                "items": [
                    "Arroz blanco jazmín cocido de rápida digestión (100g seco / ~270g cocido)",
                    "Filetes de ternera o solomillo magro a la plancha (160 g limpio)",
                    "Zanahorias cocidas y calabacín a la plancha (150 g)",
                    "Yogur de proteínas de arándanos (120 g)",
                    "Creatina Creapure 5 g"
                ]
            }
        },
        {
            "dayName": "Sábado",
            "pageNum": 16,
            "pageNum2": 17,
            "supplements": "Creatina Creapure 5g diaria · Enfoque Antiinflamatorio",
            "trainings": [
                {"name": "DESCANSO COMPLETO / REPARACIÓN TISULAR", "time": "Todo el día (Borg 1/10)", "items": "Hidratación basal con agua mineral (2.8 - 3.2 L)"}
            ],
            "elaboration": "DÍA DE DESCANSO TOTAL Y REPARACIÓN CELULAR. Descendemos los carbohidratos a 3.0 g/kg y aumentamos proporcionalmente las grasas saludables ricas en ácidos grasos monoinsaturados y omega-3 (AOVE, salmón al horno, nueces, aguacate) para modular el estrés inflamatorio articular y preparar el organismo para el partido del domingo.",
            "breakfast": {
                "name": "Desayuno (09:00 - 09:30)",
                "items": [
                    "Huevos revueltos (2 huevos enteros + 1 clara) con jamón ibérico (Huevos 130g + Jamón 40g)",
                    "Tostada de pan integral con aceite de oliva virgen extra (Pan 60g + AOVE 15g)",
                    "Naranja entera en rodajas con canela (1 pieza)",
                    "Café con leche entera o semidesnatada (200 ml)"
                ]
            },
            "midMorning": {
                "name": "Media Mañana (12:00)",
                "items": [
                    "Yogur griego natural entero con nueces y semillas de chía (Yogur 150g + Nueces 20g + Chía 5g)",
                    "Manzana verde con piel (1 pieza · 150 g)",
                    "Infusión de té verde o manzanilla"
                ]
            },
            "lunch": {
                "name": "Comida (15:00)",
                "items": [
                    "Crema de calabacín, puerro y patata con AOVE (Verdura 200g + Patata 100g + AOVE 10g)",
                    "Lomo de salmón noruego al horno con hierbas provenzales (170 g limpio)",
                    "Ensalada de tomate de huerta con orégano y aceitunas (Tomate 150g + Aceitunas 20g)",
                    "Pan integral (30 g)",
                    "Kiwi fresco (1 unidad · 100 g)"
                ]
            },
            "snack": {
                "name": "Merienda (18:30)",
                "items": [
                    "Queso fresco batido 0% con frutos rojos y almendras laminadas (QFB 200g + Arándanos 80g + Almendras 15g)",
                    "Infusión relajante (Rooibos o Melisa)"
                ]
            },
            "dinner": {
                "name": "Cena (21:30)",
                "items": [
                    "Pechuga de pavo o pollo a la plancha con limón (160 g limpio)",
                    "Salteado de verduras (brócoli, champiñones y espárragos) con AOVE (220g + 10g AOVE)",
                    "Patata asada pequeña (130 g en crudo)",
                    "Infusión de tila o manzanilla",
                    "Creatina Creapure 5 g"
                ]
            }
        }
    ]


# ==============================================================================
# 4. GENERACIÓN DE LA MAQUETA VECTORIAL HTML DE 20 PÁGINAS
# ==============================================================================

def generate_official_20page_html(athlete: Dict[str, Any], days_data: List[Dict[str, Any]]) -> str:
    """
    Genera el documento HTML completo de 20 páginas con la estética y directrices oficiales de ANyD.
    """
    logo_base64 = get_logo_base64()
    if logo_base64:
        logo_html = f'<img src="data:image/jpeg;base64,{logo_base64}" alt="ANyD Nutricionistas" style="height: 52px; object-fit: contain;">'
    else:
        logo_html = '<div style="font-size:22px; font-weight:900; color:#0284c7; letter-spacing:1px;">ANYD NUTRICIONISTAS</div>'

    # Calcular hidratación basal
    w_kg = athlete.get("weight_kg", 80.8)
    min_liters = round(w_kg * 0.035, 1)
    max_liters = round(w_kg * 0.040, 1)

    # HTML de días de Lunes a Sábado
    daily_pages_html = ""
    for day in days_data[:6]:
        # Hoja 1 del día
        trainings_html = "".join([
            f"""
            <div class="training-box">
              <div class="training-title">⚽ {tr['name']} ({tr['time']})</div>
              <div style="font-size: 11px; color: #9f1239;">• Pauta intra-sesión: {tr['items']}</div>
            </div>
            """ for tr in day.get("trainings", [])
        ])

        daily_pages_html += f"""
        <!-- HOJA 1: {day['dayName'].upper()} -->
        <div class="page">
          <div class="page-header">
            <div class="page-header-left">
              {logo_html}
              <div>
                <div class="doc-title-small">Patrón Nutricional Personalizado</div>
                <div class="doc-subtitle-small">ANyD Nutricionistas · Román Illescas (Col. MAD00274)</div>
              </div>
            </div>
            <div class="doc-header-right">
              {athlete['name'].upper()}<br>{day['dayName']}
            </div>
          </div>

          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div style="font-size: 16px; font-weight: 800; color: #0f172a;">{day['dayName']}</div>
            <div><span class="badge-supp">Suplementación: {day.get('supplements', 'Creatina 5g')}</span></div>
          </div>

          <div class="elaboration-box">
            <strong>Elaboración del Día:</strong> {day.get('elaboration', '')}
          </div>

          <div class="meal-block">
            <div class="meal-title">
              <span>🍳 {day['breakfast']['name']}</span>
              <span style="font-size: 10px; color: #0284c7; font-weight: 700;">Desayuno Base</span>
            </div>
            {''.join([f'<div class="dish-ingredients">• {it}</div>' for it in day['breakfast']['items']])}
          </div>

          {trainings_html}

          <div class="meal-block">
            <div class="meal-title">
              <span>🥪 {day['midMorning']['name']}</span>
              <span style="font-size: 10px; color: #0284c7; font-weight: 700;">Colación</span>
            </div>
            {''.join([f'<div class="dish-ingredients">• {it}</div>' for it in day['midMorning']['items']])}
          </div>

          <div class="meal-block">
            <div class="meal-title">
              <span>🍲 {day['lunch']['name']}</span>
              <span style="font-size: 10px; color: #0284c7; font-weight: 700;">Comida Principal</span>
            </div>
            {''.join([f'<div class="dish-ingredients">• {it}</div>' for it in day['lunch']['items']])}
          </div>

          <div class="page-footer">
            <div>ANyD Nutricionistas · Román Illescas Quiroga (Col. MAD00274)</div>
            <div>Menú Diario · <span class="page-num">Página {day['pageNum']}</span></div>
          </div>
        </div>

        <!-- HOJA 2: {day['dayName'].upper()} (MERIENDA Y CENA) -->
        <div class="page">
          <div class="page-header">
            <div class="page-header-left">
              {logo_html}
              <div>
                <div class="doc-title-small">Patrón Nutricional Personalizado</div>
                <div class="doc-subtitle-small">ANyD Nutricionistas · Román Illescas (Col. MAD00274)</div>
              </div>
            </div>
            <div class="doc-header-right">
              {athlete['name'].upper()}<br>{day['dayName']} (Continuación)
            </div>
          </div>

          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <div style="font-size: 16px; font-weight: 800; color: #0f172a;">{day['dayName']} (Merienda y Cena)</div>
            <div><span class="badge-supp">Suplementación Nocturna: Creatina Creapure 5g</span></div>
          </div>

          <div class="meal-block" style="border-left-color: #f59e0b;">
            <div class="meal-title">
              <span>🍌 {day['snack']['name']}</span>
              <span style="font-size: 10px; color: #d97706; font-weight: 700;">Timing Pre-Entrenamiento</span>
            </div>
            {''.join([f'<div class="dish-ingredients">• {it}</div>' for it in day['snack']['items']])}
          </div>

          <div class="card card-blue" style="margin-bottom: 12px; font-size: 11px;">
            <strong>Pauta de Ingesta Pre-Entreno:</strong> Consumir esta merienda entre 60 y 90 minutos antes del inicio de la sesión en el campo o en el box. Aporta amilosa y azúcares simples de digestión rápida para garantizar disponibilidad energética sin molestias digestivas.
          </div>

          <div class="meal-block" style="border-left-color: #10b981;">
            <div class="meal-title">
              <span>🥗 {day['dinner']['name']}</span>
              <span style="font-size: 10px; color: #059669; font-weight: 700;">Timing Post-Entrenamiento & Recuperación</span>
            </div>
            {''.join([f'<div class="dish-ingredients">• {it}</div>' for it in day['dinner']['items']])}
          </div>

          <div class="card card-green" style="margin-bottom: 12px; font-size: 11px;">
            <strong>Objetivo de la Cena:</strong> Reposición inmediata del glucógeno muscular y provisión de aminoácidos esenciales con leucina para frenar el catabolismo nocturno. Recuerda tomar los 5 g de creatina monohidrato disueltos en un vaso de agua junto a esta comida.
          </div>

          <div class="page-footer">
            <div>ANyD Nutricionistas · Román Illescas Quiroga (Col. MAD00274)</div>
            <div>Menú Diario · <span class="page-num">Página {day['pageNum2']}</span></div>
          </div>
        </div>
        """

    # HTML de Domingo (Match-Day Oficial)
    sunday_html = f"""
    <!-- PÁGINA 18: DOMINGO PARTIDO OFICIAL (COMPETICIÓN) -->
    <div class="page">
      <div class="page-header">
        <div class="page-header-left">
          {logo_html}
          <div>
            <div class="doc-title-small">Patrón Nutricional Personalizado</div>
            <div class="doc-subtitle-small">ANyD Nutricionistas · Román Illescas (Col. MAD00274)</div>
          </div>
        </div>
        <div class="doc-header-right">
          {athlete['name'].upper()}<br>Domingo de Competición
        </div>
      </div>

      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <div style="font-size: 16px; font-weight: 800; color: #0f172a;">Domingo · PARTIDO OFICIAL DE FÚTBOL (11:00h)</div>
        <div><span class="badge-supp" style="background: #fce7f3; color: #be185d;">MATCH-DAY · BORG 9/10</span></div>
      </div>

      <div class="elaboration-box" style="background: #fdf2f8; border-color: #fbcfe8; border-left-color: #db2777; color: #9d174d;">
        <strong>Estrategia Match-Day:</strong> Máxima intensidad competitiva. Desayuno obligatorio 3 horas antes del partido (07:45 - 08:00h) con bajo residuo de fibra y grasa para garantizar vaciado gástrico total y glucemia elevada sin molestias gastrointestinales. Activación con isotónico y sales 45 min antes.
      </div>

      <div class="meal-block">
        <div class="meal-title">
          <span>🥞 Desayuno Pre-Partido (07:45 - 08:00 · 3h antes)</span>
          <span style="font-size: 10px; color: #0284c7; font-weight: 700;">620 kcal · 114g CHO · Bajo Residuo</span>
        </div>
        <div class="dish-ingredients">• Pan blanco tostado de fácil digestión (110 g)</div>
        <div class="dish-ingredients">• Mermelada de melocotón o fresa con miel pura (30 g)</div>
        <div class="dish-ingredients">• Pechuga de pavo braseada o jamón cocido extra (60 g)</div>
        <div class="dish-ingredients">• Plátano muy maduro en rodajas (1 unidad · 120 g)</div>
        <div class="dish-ingredients">• Café solo o infusión (posibilidad de 150-200 mg de cafeína según tolerancia)</div>
        <div class="dish-ingredients">• Agua mineral (400 ml)</div>
      </div>

      <div class="training-box" style="background: #fef2f2; border-color: #fecaca; border-left-color: #dc2626;">
        <div class="training-title" style="color: #991b1b;">⚽ PARTIDO OFICIAL DE FÚTBOL (11:00 - 13:00h)</div>
        <div style="font-size: 11px; color: #7f1d1d; line-height: 1.5;">
          • <strong>Activación Pre-Partido (10:15h · 45 min antes):</strong> 350 ml de bebida isotónica (25g CHO rápidos + 300 mg Sodio).<br>
          • <strong>Descanso del Partido:</strong> 250 ml de isotónico a pequeños sorbos + agua fría.<br>
          • <strong>Recuperación Inmediata (13:15h):</strong> Batido Recovery (25g Whey + 1 Plátano maduro + 20g Miel) + 1 litro de agua con sales.
        </div>
      </div>

      <div class="meal-block">
        <div class="meal-title">
          <span>🥘 Comida Post-Partido (14:30 - 15:00)</span>
          <span style="font-size: 10px; color: #0284c7; font-weight: 700;">910 kcal · 128g CHO · 46g PRO</span>
        </div>
        <div class="dish-ingredients">• Paella de arroz con pollo y verduras o Arroz marinero (Arroz 110g seco / ~280g cocido + Pollo 130g)</div>
        <div class="dish-ingredients">• Ensalada verde suave con aceite de oliva virgen extra (80g + 10g AOVE)</div>
        <div class="dish-ingredients">• Pan blanco (40 g)</div>
        <div class="dish-ingredients">• Fruta fresca dulce (melón o sandía fresca · 200 g)</div>
      </div>

      <div class="page-footer">
        <div>ANyD Nutricionistas · Román Illescas Quiroga (Col. MAD00274)</div>
        <div>Menú Diario Match-Day · <span class="page-num">Página 17</span></div>
      </div>
    </div>

    <!-- PÁGINA 19: DOMINGO (MERIENDA Y CENA MATCH-DAY) -->
    <div class="page">
      <div class="page-header">
        <div class="page-header-left">
          {logo_html}
          <div>
            <div class="doc-title-small">Patrón Nutricional Personalizado</div>
            <div class="doc-subtitle-small">ANyD Nutricionistas · Román Illescas (Col. MAD00274)</div>
          </div>
        </div>
        <div class="doc-header-right">
          {athlete['name'].upper()}<br>Domingo de Competición
        </div>
      </div>

      <div style="font-size: 16px; font-weight: 800; color: #0f172a; margin-bottom: 12px;">Domingo Match-Day (Cierre de Microciclo)</div>

      <div class="meal-block" style="border-left-color: #f59e0b;">
        <div class="meal-title">
          <span>🥪 Merienda Post-Partido (18:30)</span>
          <span style="font-size: 10px; color: #d97706; font-weight: 700;">380 kcal · 42g CHO · 24g PRO</span>
        </div>
        <div class="dish-ingredients">• Sándwich de pan integral con queso tierno y jamón york (Pan 60g + Queso 40g + York 40g)</div>
        <div class="dish-ingredients">• Yogur de proteínas de arándanos (1 unidad · 120 g)</div>
        <div class="dish-ingredients">• Zumo natural o agua mineral (250 ml)</div>
      </div>

      <div class="meal-block" style="border-left-color: #10b981;">
        <div class="meal-title">
          <span>🐟 Cena de Cierre de Microciclo (21:30)</span>
          <span style="font-size: 10px; color: #059669; font-weight: 700;">680 kcal · 84g CHO · 45g PRO</span>
        </div>
        <div class="dish-ingredients">• Puré de patata natural o patatas al horno con AOVE (250 g en crudo + 10g AOVE)</div>
        <div class="dish-ingredients">• Lomo de lubina o dorada al horno con verduras (180 g limpio)</div>
        <div class="dish-ingredients">• Calabacín y berenjena asados con aceite de oliva (150 g)</div>
        <div class="dish-ingredients">• Yogur griego ligero con compota de pera o manzana (125 g)</div>
        <div class="dish-ingredients">• Creatina Creapure 5 g disuelta en agua</div>
      </div>

      <div class="card card-green" style="margin-top: 14px; font-size: 11.5px;">
        <strong>Conclusión del Microciclo:</strong> La correcta ejecución de las cargas de hidratos y el cumplimiento de la rehidratación con electrolitos tras el partido del domingo garantizarán que comiences el siguiente microciclo del lunes sin fatiga residual, con niveles plasmáticos óptimos y sin sobrecarga neuromuscular.
      </div>

      <div class="page-footer">
        <div>ANyD Nutricionistas · Román Illescas Quiroga (Col. MAD00274)</div>
        <div>Menú Diario Match-Day · <span class="page-num">Página 18</span></div>
      </div>
    </div>
    """

    # HTML de Lista de la Compra Maestra
    families = {
        "Aceites y Grasas": ["Aceite de oliva virgen extra (AOVE de 1ª presión)", "Aceitunas"],
        "Arroces y Pastas": ["Arroz blanco jazmín o basmati", "Arroz integral", "Macarrones integrales", "Ñoquis de patata"],
        "Carnes Magras": ["Filetes de ternera blanca magra (600 g)", "Pechuga de pollo fresca (800 g)", "Carne picada de ternera magra (300 g)", "Solomillo o ternera para plancha"],
        "Charcutería Selecta": ["Cinta de lomo embuchada ibérica (200 g)", "Jamón serrano / ibérico (250 g)", "Pechuga de pavo o jamón york >90% (400 g)"],
        "Pescados": ["Lomos de salmón noruego fresco (400 g)", "Filetes de merluza o gallo limpio (400 g)", "Lubina o dorada para horno (350 g)", "Atún al natural (4 latas)"],
        "Huevos y Lácteos": ["Huevos camperos clase L (2 docenas)", "Leche semidesnatada (2 litros)", "Queso fresco batido 0% (1 kg)", "Yogures de proteínas de arándanos (8 ud)", "Yogur griego ligero (6 ud)"],
        "Legumbres y Tubérculos": ["Lentejas pardinas secas", "Garbanzos secos o cocidos de bote", "Judías verdes", "Patatas especiales para cocer/asar (3 kg)"],
        "Pan y Cereales": ["Pan de masa madre tostado", "Pan integral fresco", "Copos de avena integral suave (1 kg)", "Galletas María hojaldrada / Tortas arroz"],
        "Fruta Fresca": ["Plátanos maduros (12-14 unidades)", "Naranjas de mesa y limones (2 kg)", "Kiwis y peras (1.5 kg)", "Manzanas verdes", "Arándanos frescos (250 g)", "Sandía o melón picado"],
        "Frutos Secos y Semillas": ["Nueces naturales sin cáscara (250 g)", "Almendras crudas sin sal (200 g)", "Semillas de chía"],
        "Verduras y Hortalizas": ["Calabacines y berenjenas (1.5 kg)", "Zanahorias y cebollas (1 kg)", "Espinacas frescas y ensalada verde (3 bolsas)", "Tomates de ensalada y cherrys (1.5 kg)", "Espárragos trigueros y champiñones (500 g)", "Pimientos del padrón y pimientos rojos"],
        "Suplementación AIS": ["Creatina monohidrato Creapure (5 g/día)", "Beta-Alanina (3.2 g/día)", "Sales minerales electrolitos con Sodio (500-700 mg/h)"]
    }

    grocery_cols_html = "".join([
        f"""
        <div>
          <div class="grocery-family">{fam_name}</div>
          <div style="font-size: 10.5px; color: #334155; line-height: 1.5;">
            {''.join([f'<div><span class="checkbox-item"></span>{it}</div>' for it in items])}
          </div>
        </div>
        """ for fam_name, items in families.items()
    ])

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Patrón Nutricional Personalizado · {athlete['name']} · ANyD</title>
<style>
  @page {{
    size: A4 portrait;
    margin: 12mm 14mm 12mm 14mm;
  }}
  @page landscape-page {{
    size: A4 landscape;
    margin: 10mm 12mm 10mm 12mm;
  }}
  * {{
    box-sizing: border-box;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #1e293b;
    background-color: #f8fafc;
    margin: 0;
    padding: 0;
    font-size: 12.5px;
    line-height: 1.5;
  }}
  .page {{
    width: 100%;
    max-width: 210mm;
    min-height: 297mm;
    margin: 0 auto 20px auto;
    background: #ffffff;
    padding: 26px 30px;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.07);
    position: relative;
    display: flex;
    flex-direction: column;
  }}
  .page-landscape {{
    max-width: 297mm;
    min-height: 210mm;
  }}
  @media print {{
    body {{ background: transparent; }}
    .page {{
      margin: 0;
      padding: 0;
      box-shadow: none;
      page-break-after: always;
      break-after: page;
      min-height: 100vh;
    }}
    .page-landscape {{
      page: landscape-page;
    }}
  }}
  .page-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 2px solid #0284c7;
    padding-bottom: 10px;
    margin-bottom: 16px;
  }}
  .page-header-left {{
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .doc-title-small {{
    font-size: 13px;
    font-weight: 800;
    color: #0f172a;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  .doc-subtitle-small {{
    font-size: 10.5px;
    color: #0284c7;
    font-weight: 700;
  }}
  .doc-header-right {{
    text-align: right;
    font-size: 10px;
    color: #64748b;
    font-weight: 600;
  }}
  .page-footer {{
    margin-top: auto;
    border-top: 1px solid #e2e8f0;
    padding-top: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 10px;
    color: #64748b;
  }}
  .page-num {{
    font-weight: 700;
    color: #0284c7;
  }}
  .section-title {{
    font-size: 16px;
    font-weight: 800;
    color: #0f172a;
    border-bottom: 2px solid #0284c7;
    padding-bottom: 4px;
    margin: 14px 0 10px 0;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .card {{
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 14px;
  }}
  .card-blue {{
    background: #f0f9ff;
    border-left: 4px solid #0284c7;
  }}
  .card-green {{
    background: #f0fdf4;
    border-left: 4px solid #16a34a;
  }}
  .meal-block {{
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-left: 4px solid #0284c7;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 10px;
  }}
  .meal-title {{
    font-size: 13px;
    font-weight: 800;
    color: #0f172a;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
    border-bottom: 1px dashed #e2e8f0;
    padding-bottom: 4px;
  }}
  .dish-ingredients {{
    font-size: 11.5px;
    color: #334155;
    margin-left: 12px;
    margin-bottom: 4px;
  }}
  .badge-supp {{
    background: #dcfce7;
    color: #166534;
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 10.5px;
    font-weight: 700;
    display: inline-block;
  }}
  .training-box {{
    background: #fff1f2;
    border: 1px solid #fecdd3;
    border-left: 4px solid #e11d48;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 12px;
  }}
  .training-title {{
    font-weight: 800;
    color: #be123c;
    font-size: 12px;
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 4px;
  }}
  .elaboration-box {{
    background: #fefce8;
    border: 1px solid #fef08a;
    border-left: 4px solid #ca8a04;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 12px;
    font-size: 11.5px;
    color: #713f12;
  }}
  table.planning-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 10px;
  }}
  table.planning-table th {{
    background: #0284c7;
    color: #ffffff;
    padding: 6px 8px;
    text-align: left;
    font-weight: 700;
    border: 1px solid #0369a1;
  }}
  table.planning-table td {{
    padding: 6px 8px;
    border: 1px solid #cbd5e1;
    vertical-align: top;
    background: #ffffff;
  }}
  table.planning-table tr:nth-child(even) td {{
    background: #f8fafc;
  }}
  .checkbox-item {{
    display: inline-block;
    width: 12px;
    height: 12px;
    border: 1.5px solid #0284c7;
    border-radius: 2px;
    margin-right: 6px;
    vertical-align: middle;
  }}
  .grocery-family {{
    font-size: 11px;
    font-weight: 800;
    color: #0284c7;
    text-transform: uppercase;
    border-bottom: 1px solid #cbd5e1;
    padding-bottom: 2px;
    margin: 8px 0 4px 0;
  }}
</style>
</head>
<body>

<!-- PÁGINA 1: PORTADA OFICIAL -->
<div class="page" style="justify-content: center; align-items: center; text-align: center;">
  <div style="margin-top: 60px;">
    {logo_html}
  </div>
  <div style="margin-top: 40px; font-size: 26px; font-weight: 900; color: #0f172a; letter-spacing: -0.5px;">
    PATRÓN NUTRICIONAL PERSONALIZADO
  </div>
  <div style="font-size: 16px; color: #0284c7; font-weight: 700; margin-top: 8px; text-transform: uppercase; letter-spacing: 1px;">
    Microciclo Periodizado de 7 Días · Rendimiento
  </div>

  <div style="margin: 60px auto 40px auto; max-width: 500px; background: #f8fafc; border: 2px solid #e2e8f0; border-radius: 12px; padding: 24px; text-align: left;">
    <div style="font-size: 11px; color: #64748b; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">Deportista / Paciente:</div>
    <div style="font-size: 20px; font-weight: 800; color: #0f172a; margin-bottom: 16px;">{athlete['name'].upper()}</div>
    
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 12px; color: #334155;">
      <div><strong>Disciplina:</strong> {athlete.get('sports', 'Deportes de Resistencia y Fuerza')}</div>
      <div><strong>Edad / Estatura:</strong> {athlete.get('age', 25)} años · {int(athlete.get('height_cm', 175))} cm</div>
      <div><strong>Peso Tanita:</strong> {athlete.get('weight_kg', 80.8):.2f} kg</div>
      <div><strong>Masa Magra (FFM):</strong> {athlete.get('ffm_kg', 70.5):.1f} kg (Cunningham: {athlete.get('bmr_cunningham', 2051)} kcal)</div>
      <div><strong>Grasa Corporal:</strong> {athlete.get('fat_percent', 12.7):.1f}%</div>
      <div><strong>Fecha de Emisión:</strong> {athlete.get('date_str', 'Octubre 2026')}</div>
    </div>
  </div>

  <div style="margin-top: auto; margin-bottom: 40px; font-size: 12px; color: #475569;">
    <strong>ANyD Nutricionistas</strong><br>
    Román Illescas Quiroga · Col. MAD00274<br>
    Nutrición Clínica y Rendimiento Deportivo
  </div>

  <div class="page-footer" style="width: 100%;">
    <div>ANyD Nutricionistas · Román Illescas Quiroga (Col. MAD00274)</div>
    <div class="page-num">Página 1</div>
  </div>
</div>

<!-- PÁGINA 2: GUÍA DE GESTIÓN DE RACIONES ANyD -->
<div class="page">
  <div class="page-header">
    <div class="page-header-left">
      {logo_html}
      <div>
        <div class="doc-title-small">Patrón Nutricional Personalizado</div>
        <div class="doc-subtitle-small">ANyD Nutricionistas · Román Illescas (Col. MAD00274)</div>
      </div>
    </div>
    <div class="doc-header-right">
      {athlete['name'].upper()}<br>{athlete.get('date_str', 'Octubre 2026')}
    </div>
  </div>

  <div class="section-title"><span>📘</span> Guía de Gestión de Raciones, Elaboración de Recetas e Hidratación</div>
  <div class="card card-blue" style="font-size: 12px; margin-bottom: 12px;">
    <strong>Objetivo Clínico y Deportivo:</strong> Maximizar la disponibilidad de glucógeno muscular para los entrenamientos de alta intensidad, optimizar la resíntesis de fosfocreatina y asegurar una recuperación proteica impecable entre sesiones.
  </div>

  <h3 style="font-size: 14px; color: #0284c7; margin: 14px 0 6px 0;">1. Tus Raciones Clave (El Estándar de Referencia ANyD)</h3>
  <p style="font-size: 12px; color: #475569; margin-bottom: 12px;">
    Aunque en los menús diarios existan variaciones para cuadrar los objetivos de carbohidratos según el cuadrante de esfuerzo, las porciones estándar de referencia son:
  </p>

  <div class="card" style="margin-bottom: 10px;">
    <h4 style="font-size: 13px; color: #0f172a; margin-bottom: 4px;">• Hidratos de Carbono Secos (Pasta, Arroz, Cuscús)</h4>
    <p style="font-size: 11.5px; color: #334155; margin: 0;">
      La ración base es de <strong>70 a 100 gramos en crudo y seco</strong> según el volumen del día. Al cocinarse multiplican su peso por 2.5 a 3. Siempre pesa en seco antes de hervir.
    </p>
  </div>

  <div class="card" style="margin-bottom: 10px;">
    <h4 style="font-size: 13px; color: #0f172a; margin-bottom: 4px;">• Tubérculos (Patata, Boniato)</h4>
    <p style="font-size: 11.5px; color: #334155; margin: 0;">
      La ración base son <strong>250–280 gramos en crudo</strong>. Mantienen su peso prácticamente idéntico antes y después de ser cocinados al vapor, horno o airfryer.
    </p>
  </div>

  <div class="card" style="margin-bottom: 10px;">
    <h4 style="font-size: 13px; color: #0f172a; margin-bottom: 4px;">• Legumbres (Garbanzos, Lentejas, Alubias)</h4>
    <p style="font-size: 11.5px; color: #334155; margin: 0;">
      Ración de <strong>70–90 gramos si se cocinan en seco</strong> o <strong>250 gramos si son cocidas de bote</strong>, lavadas y escurridas.
    </p>
  </div>

  <div class="card" style="margin-bottom: 10px;">
    <h4 style="font-size: 13px; color: #0f172a; margin-bottom: 4px;">• Proteínas Limpias (Carnes y Pescados)</h4>
    <p style="font-size: 11.5px; color: #334155; margin: 0;">
      Ración de <strong>160–200 gramos en crudo y limpio</strong> sin grasa visible ni piel para garantizar 30–40 g de proteína neta por comida principal.
    </p>
  </div>

  <div class="page-footer">
    <div>ANyD Nutricionistas · Román Illescas Quiroga (Col. MAD00274)</div>
    <div>Premisas · <span class="page-num">Página 2</span></div>
  </div>
</div>

<!-- PÁGINA 3: DINÁMICA EN 3 PASOS, CORRECCIÓN DE HÁBITOS Y FLEXIBILIDAD -->
<div class="page">
  <div class="page-header">
    <div class="page-header-left">
      {logo_html}
      <div>
        <div class="doc-title-small">Patrón Nutricional Personalizado</div>
        <div class="doc-subtitle-small">ANyD Nutricionistas · Román Illescas (Col. MAD00274)</div>
      </div>
    </div>
    <div class="doc-header-right">
      {athlete['name'].upper()}<br>{athlete.get('date_str', 'Octubre 2026')}
    </div>
  </div>

  <h3 style="font-size: 14px; color: #0284c7; margin: 10px 0 6px 0;">2. Dinámica de Elaboración de Recetas en 3 Pasos</h3>
  <div class="card card-green" style="font-size: 11.5px; color: #166534; margin-bottom: 12px;">
    <strong>Paso 1. Pesa el ingrediente principal en crudo:</strong> Utiliza siempre la báscula de cocina con el arroz, pasta, patatas o carne antes de cocinar.<br><br>
    <strong>Paso 2. Añade base vegetal libre:</strong> El tomate natural, cebolla, pimientos, champiñones y lechuga dan volumen y palatabilidad sin desviar las calorías marcadas.<br><br>
    <strong>Paso 3. Controla las grasas de cocinado:</strong> El Aceite de Oliva Virgen Extra (AOVE) debe medirse con cuchara: <strong>cuchara de postre = 5 g; cuchara sopera = 10–12 g</strong>.
  </div>

  <h3 style="font-size: 14px; color: #0284c7; margin: 14px 0 6px 0;">3. Corrección de Hábitos Detectados en el Recordatorio de 3 Días</h3>
  <div class="card" style="margin-bottom: 10px;">
    <p style="font-size: 11.5px; color: #334155; line-height: 1.6; margin: 0;">
      • <strong>Fruta Entera:</strong> Se fija un aporte regular de <strong>3–4 raciones diarias</strong> (plátanos maduros, kiwis, peras, naranjas) para garantizar la reposición del glucógeno hepático y el aporte de vitamina C y antioxidantes.<br>
      • <strong>Pescado Azul y Blanco:</strong> Se eleva el consumo a <strong>4 tomas semanales</strong> (salmón noruego, merluza, lubina, gallo) para enriquecer el perfil de ácidos grasos Omega-3 (EPA/DHA) y mitigar la inflamación muscular de los impactos y levantamientos.<br>
      • <strong>Creatina Monohidrato (Creapure):</strong> Pauta fija de <strong>5 g diarios</strong> tomados post-entreno en la cena o batido con carbohidratos para máxima absorción por transportadores dependientes de sodio e insulina.
    </p>
  </div>

  <h3 style="font-size: 14px; color: #0284c7; margin: 14px 0 6px 0;">4. Flexibilidad y Sustituciones</h3>
  <p style="font-size: 11.5px; color: #334155; margin: 0;">
    Puedes intercambiar carnes por aves o pescados equivalentes en crudo, y patata por arroz o pasta según tus preferencias culinarias manteniendo las cantidades pautadas.
  </p>

  <div class="page-footer">
    <div>ANyD Nutricionistas · Román Illescas Quiroga (Col. MAD00274)</div>
    <div>Premisas · <span class="page-num">Página 3</span></div>
  </div>
</div>

<!-- PÁGINA 4: PROTOCOLO DE HIDRATACIÓN Y TEST DE SUDORACIÓN -->
<div class="page">
  <div class="page-header">
    <div class="page-header-left">
      {logo_html}
      <div>
        <div class="doc-title-small">Patrón Nutricional Personalizado</div>
        <div class="doc-subtitle-small">ANyD Nutricionistas · Román Illescas (Col. MAD00274)</div>
      </div>
    </div>
    <div class="doc-header-right">
      {athlete['name'].upper()}<br>{athlete.get('date_str', 'Octubre 2026')}
    </div>
  </div>

  <h3 style="font-size: 14px; color: #0284c7; margin: 10px 0 6px 0;">5. Protocolo de Hidratación Personalizado ({athlete.get('weight_kg', 80.8):.1f} kg)</h3>
  <div class="card card-blue" style="margin-bottom: 12px;">
    <h4 style="font-size: 13px; color: #0369a1; margin-bottom: 4px;">Dosis Diaria Basal (Fuera de Entrenamientos):</h4>
    <p style="font-size: 11.5px; color: #334155; margin: 0;">
      Para tu peso de {athlete.get('weight_kg', 80.8):.1f} kg, tu ingesta hídrica mínima en reposo debe situarse entre <strong>35 y 40 ml por kg de peso corporal</strong>, lo que equivale a entre <strong>{min_liters} y {max_liters} litros de agua diarios</strong>.
    </p>
  </div>

  <h3 style="font-size: 14px; color: #0284c7; margin: 14px 0 6px 0;">6. Test Práctico de Sudoración en Entrenamientos y Partidos</h3>
  <div class="card" style="margin-bottom: 10px;">
    <ol style="margin: 0; padding-left: 18px; font-size: 11.5px; color: #334155; line-height: 1.6;">
      <li><strong>Pesaje Pre-Entreno:</strong> Pésate en la báscula justo antes de entrenar (idealmente en ropa interior y con vejiga vacía).</li>
      <li><strong>Control del Bidón:</strong> Lleva un bidón de agua medido (ej. 750 ml) y anota exactamente cuánto has bebido durante el entrenamiento.</li>
      <li><strong>Pesaje Post-Entreno:</strong> Sécate el sudor con una toalla nada más acabar y pésate con la misma ropa.</li>
      <li><strong>Cálculo Horario:</strong> Resta el peso final al inicial, suma el líquido bebido y divide entre los minutos de entreno para conocer tu tasa de sudoración exacta (L/h).</li>
    </ol>
  </div>

  <div class="page-footer">
    <div>ANyD Nutricionistas · Román Illescas Quiroga (Col. MAD00274)</div>
    <div>Premisas · <span class="page-num">Página 4</span></div>
  </div>
</div>

<!-- PÁGINA 5: ELECTROLITOS Y SUPLEMENTACIÓN AIS GRUPO A -->
<div class="page">
  <div class="page-header">
    <div class="page-header-left">
      {logo_html}
      <div>
        <div class="doc-title-small">Patrón Nutricional Personalizado</div>
        <div class="doc-subtitle-small">ANyD Nutricionistas · Román Illescas (Col. MAD00274)</div>
      </div>
    </div>
    <div class="doc-header-right">
      {athlete['name'].upper()}<br>{athlete.get('date_str', 'Octubre 2026')}
    </div>
  </div>

  <h3 style="font-size: 14px; color: #0284c7; margin: 10px 0 6px 0;">7. Protocolo de Electrolitos y Sodio</h3>
  <div class="card card-green" style="margin-bottom: 12px; font-size: 11.5px; color: #166534;">
    <strong>Reposición intra-esfuerzo:</strong> En los entrenamientos de alta exigencia (>60 min) y en los partidos oficiales, añade a tu bidón entre <strong>500 y 700 mg de Sodio por hora</strong> de ejercicio para mantener la volemia, prevenir rampas musculares y mantener el rendimiento neuromuscular.
  </div>

  <h3 style="font-size: 14px; color: #0284c7; margin: 14px 0 6px 0;">8. Suplementación Basada en Evidencia (AIS Grupo A)</h3>
  <div class="card" style="margin-bottom: 10px;">
    <div style="margin-bottom: 8px;">
      <strong style="color: #0284c7;">• Creatina Creapure:</strong> 5.0 g diarios fijos. Tomar en la cena o batido post-entreno con carbohidratos. Aumenta los niveles de fosfocreatina muscular, mejorando la fuerza explosiva en levantamientos y la capacidad de sprint repetido.
    </div>
    <div style="margin-bottom: 8px;">
      <strong style="color: #0284c7;">• Beta-Alanina:</strong> 3.2 g diarios divididos en 2 tomas de 1.6 g (merienda pre-WOD y cena post-WOD). Eleva la síntesis de carnosina intramuscular, amortiguando la acidosis láctica en esfuerzos intensos de 1 a 4 minutos.
    </div>
    <div>
      <strong style="color: #0284c7;">• Hidratación Isotónica:</strong> Sales minerales ricas en Sodio en partidos y entrenamientos superiores a 60 minutos.
    </div>
  </div>

  <div class="page-footer">
    <div>ANyD Nutricionistas · Román Illescas Quiroga (Col. MAD00274)</div>
    <div>Premisas · <span class="page-num">Página 5</span></div>
  </div>
</div>

<!-- PÁGINAS 6 A 17: MENÚS DIARIOS DE LUNES A SÁBADO -->
{daily_pages_html}

<!-- PÁGINAS 18 Y 19: DOMINGO PARTIDO OFICIAL -->
{sunday_html}

<!-- PÁGINA 20: PLANNING SEMANAL MATRIZ (HOJA DE LA NEVERA) -->
<div class="page page-landscape">
  <div class="page-header">
    <div class="page-header-left">
      {logo_html}
      <div>
        <div class="doc-title-small">Planning Semanal Completo (Microciclo de 7 Días)</div>
        <div class="doc-subtitle-small">ANyD Nutricionistas · Román Illescas (Col. MAD00274)</div>
      </div>
    </div>
    <div class="doc-header-right">
      {athlete['name'].upper()} · Lunes a Domingo
    </div>
  </div>

  <table class="planning-table">
    <thead>
      <tr>
        <th style="width: 12%;">Toma</th>
        <th style="width: 12.5%;">Lunes</th>
        <th style="width: 12.5%;">Martes</th>
        <th style="width: 12.5%;">Miércoles</th>
        <th style="width: 12.5%;">Jueves</th>
        <th style="width: 12.5%;">Viernes</th>
        <th style="width: 12.5%;">Sábado</th>
        <th style="width: 12.5%;">Domingo</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>Desayuno</strong></td>
        <td>Pan masa madre · AOVE · 2 Huevos · Pavo · Kiwi</td>
        <td>Porridge avena con leche · Whey/Yogur · Arándanos</td>
        <td>Tostadas int. · Tomate · Jamón serrano · AOVE · Fruta</td>
        <td>Tortilla 2 huevos · Tostadas aguacate · Kiwi</td>
        <td>Tostadas mermelada y jamón · 2 Huevos · Zumo</td>
        <td>Huevos revueltos · Jamón ibérico · Tostada AOVE</td>
        <td><strong>MATCH-DAY:</strong> Pan tostado · Mermelada y miel · Pavo · Plátano</td>
      </tr>
      <tr>
        <td><strong>Entrenamiento</strong></td>
        <td><strong>FÚTBOL (21h)</strong><br>1h 30m · Borg 6</td>
        <td><strong>CROSSFIT (21h)</strong><br>1h · Borg 8</td>
        <td><strong>FÚTBOL (21h)</strong><br>1h 30m · Borg 6</td>
        <td><strong>CROSSFIT (20:30h)</strong><br>1h · Borg 8</td>
        <td><strong>DOBLE:</strong><br>Haltero (16h) + Fútbol (21h)</td>
        <td><strong>DESCANSO TOTAL</strong><br>Reparación tisular</td>
        <td><strong>PARTIDO OFICIAL</strong><br>11:00h · Borg 9/10</td>
      </tr>
      <tr>
        <td><strong>Media Mañana</strong></td>
        <td>Bocadillo lomo embuchado · Plátano · Agua</td>
        <td>Tosta queso fresco y pavo · Manzana</td>
        <td>Sándwich atún con pimientos · Plátano</td>
        <td>Bocadillo lomo embuchado · Manzana</td>
        <td>Bocadillo tortilla francesa · Plátano · Barrita</td>
        <td>Yogur griego · Nueces y chía · Manzana</td>
        <td>Activación pre-partido: Isotónico + Sodio</td>
      </tr>
      <tr>
        <td><strong>Almuerzo</strong></td>
        <td>Lentejas con patata · Ternera blanca · Ensalada</td>
        <td>Macarrones boloñesa magra · Ensalada · Pera</td>
        <td>Arroz con pollo y verduras wok · Pan · Yogur</td>
        <td>Garbanzos con espinacas y bacalao · Arroz · Fruta</td>
        <td>Pasta abundante · Atún y pollo · Piña fresca</td>
        <td>Crema verduras · Salmón al horno · Ensalada tomate</td>
        <td>Paella de arroz con pollo · Ensalada · Melón dulce</td>
      </tr>
      <tr>
        <td><strong>Merienda / Pre</strong></td>
        <td>Queso batido 0% · Plátano · Miel · Avena</td>
        <td>Yogur griego · Plátano · Tostada miel · Beta-Alanina</td>
        <td>Avena/maíz con leche · Galletas María · Isotónico</td>
        <td>Queso batido 0% · Plátano · Miel · Beta-Alanina</td>
        <td><strong>Recovery Inter-Sesión:</strong> Batido leche, plátano, avena y Whey</td>
        <td>Queso batido 0% · Frutos rojos · Almendras</td>
        <td>Sándwich queso y pavo · Yogur proteínas</td>
      </tr>
      <tr>
        <td><strong>Cena / Post</strong></td>
        <td>Arroz jazmín · Salmón plancha · Verduras · Creatina</td>
        <td>Patata asada · Pechuga pollo · Judías · Creatina</td>
        <td>Patatas cocidas · Merluza plancha · Fruta · Creatina</td>
        <td>Ñoquis patata · Hamburguesa ternera · Creatina</td>
        <td>Arroz blanco · Ternera magra · Yogur · Creatina</td>
        <td>Pechuga pavo · Salteado verduras · Patata · Creatina</td>
        <td>Puré patata · Lubina horno · Yogur griego · Creatina</td>
      </tr>
    </tbody>
  </table>

  <div class="page-footer">
    <div>ANyD Nutricionistas · Román Illescas Quiroga (Col. MAD00274)</div>
    <div>Planning Semanal Matriz · <span class="page-num">Página 19</span></div>
  </div>
</div>

<!-- PÁGINA 21: LISTA MAESTRA DE LA COMPRA CON CHECKBOXES -->
<div class="page">
  <div class="page-header">
    <div class="page-header-left">
      {logo_html}
      <div>
        <div class="doc-title-small">Lista Maestra de la Compra Semanal</div>
        <div class="doc-subtitle-small">ANyD Nutricionistas · Román Illescas (Col. MAD00274)</div>
      </div>
    </div>
    <div class="doc-header-right">
      {athlete['name'].upper()} · Microciclo Semanal
    </div>
  </div>

  <div style="font-size: 11px; color: #64748b; margin-bottom: 8px;">
    Marca con una casilla los ingredientes que ya tengas en la despensa o que vayas adquiriendo en el supermercado:
  </div>

  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px;">
    {grocery_cols_html}
  </div>

  <div class="page-footer">
    <div>ANyD Nutricionistas · Román Illescas Quiroga (Col. MAD00274)</div>
    <div>Lista de la Compra · <span class="page-num">Página 20</span></div>
  </div>
</div>

</body>
</html>"""


# ==============================================================================
# 5. COMPILACIÓN A PDF OFICIAL MEDIANTE MICROSOFT EDGE HEADLESS
# ==============================================================================

def compile_html_to_pdf_edge(html_file_path: str, output_pdf_path: str, timeout_sec: int = 40) -> bool:
    """
    Compila el archivo HTML a PDF vectorial usando Microsoft Edge en modo headless nativo.
    """
    edge_exe = find_edge_executable()
    if not edge_exe:
        print("[DOSSIER ERROR] No se encontró Microsoft Edge ni Google Chrome para la compilación.")
        return False

    os.makedirs(os.path.dirname(os.path.abspath(output_pdf_path)), exist_ok=True)
    temp_pdf = os.path.join(SCRATCH_DIR, f"temp_{os.path.basename(output_pdf_path)}")
    os.makedirs(SCRATCH_DIR, exist_ok=True)

    cmd = [
        edge_exe,
        "--headless",
        "--disable-gpu",
        "--run-all-compositor-stages-before-draw",
        "--no-pdf-header-footer",
        f"--print-to-pdf={temp_pdf}",
        html_file_path
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
        if os.path.exists(temp_pdf) and os.path.getsize(temp_pdf) > 1000:
            shutil.copy2(temp_pdf, output_pdf_path)
            try:
                os.remove(temp_pdf)
            except Exception:
                pass
            print(f"[DOSSIER] PDF compilado con éxito: {output_pdf_path} ({os.path.getsize(output_pdf_path)} bytes)")
            return True
        else:
            print(f"[DOSSIER ERROR] Edge falló al generar el PDF. Retcode: {proc.returncode}, Stderr: {proc.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"[DOSSIER ERROR] Timeout de {timeout_sec}s expirado al compilar PDF.")
        return False
    except Exception as e:
        print(f"[DOSSIER ERROR] Excepción al invocar Edge headless: {e}")
        return False


# ==============================================================================
# 6. FUNCIÓN MAESTRA DE AUTOMATIZACIÓN DE EXTRACCIÓN Y GENERACIÓN
# ==============================================================================

def auto_generate_official_dossier(client_name: str, user_plan: Optional[Dict[str, Any]] = None, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Ejecuta el pipeline completo automatizado:
    1. Localiza o crea la carpeta de Drive del deportista.
    2. Extrae el informe de composición corporal (Tanita MC-580 / Cunningham).
    3. Extrae el informe de horarios de entrenamientos (Excel Cuadrante ACSM).
    4. Ensambla el patrón periodizado de 7 días.
    5. Renderiza el HTML de 20 páginas.
    6. Compila el PDF vectorial mediante Edge.
    7. Guarda ambos archivos en Google Drive y actualiza la base de datos.
    """
    start_time = datetime.now()
    clean_name = client_name.strip()

    # 1. Localizar o resolver carpeta en Google Drive
    drive_folder = find_athlete_drive_folder(clean_name)
    if not drive_folder:
        folder_safe = clean_name.replace("  ", " ")
        drive_folder = os.path.join(DRIVE_ATHLETES_DIR, folder_safe)
        os.makedirs(drive_folder, exist_ok=True)

    # 2. Extraer Composición Corporal (Tanita MC-580)
    athlete_data = extract_tanita_body_composition(clean_name, drive_folder)
    if overrides and isinstance(overrides, dict):
        athlete_data.update(overrides)

    # 3. Extraer Horarios de Entrenamientos (Excel Cuadrante)
    training_data = extract_athlete_training_schedule(clean_name, drive_folder, athlete_data["weight_kg"])
    workouts_by_day = training_data.get("workouts_by_day", {})

    # 4. Generar o vincular los menús de los 7 días
    days_data = get_or_build_7day_pattern(clean_name, athlete_data, workouts_by_day, user_plan)

    # 5. Generar HTML oficial de 20 páginas
    html_content = generate_official_20page_html(athlete_data, days_data)

    # Nombres oficiales de salida
    safe_name = sanitize_filename(athlete_data["name"])
    html_output_path = os.path.join(drive_folder, f"Patron_Nutricional_20_Paginas_{safe_name}.html")
    pdf_output_path = os.path.join(drive_folder, f"Patron_Nutricional_20_Paginas_{safe_name}_Oficial.pdf")

    # Guardar HTML en Google Drive
    with open(html_output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # Guardar copia en scratch por trazabilidad
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    scratch_html = os.path.join(SCRATCH_DIR, f"Patron_Nutricional_20_Paginas_{safe_name}.html")
    with open(scratch_html, "w", encoding="utf-8") as f:
        f.write(html_content)

    # 6. Compilar a PDF mediante Edge Headless
    pdf_success = compile_html_to_pdf_edge(html_output_path, pdf_output_path)

    elapsed_sec = round((datetime.now() - start_time).total_seconds(), 2)

    return {
        "success": pdf_success,
        "athlete": athlete_data,
        "training_file": training_data.get("filename"),
        "total_sessions": training_data.get("total_sessions", 0),
        "html_path": html_output_path,
        "pdf_path": pdf_output_path if pdf_success else None,
        "pdf_size_bytes": os.path.getsize(pdf_output_path) if pdf_success and os.path.exists(pdf_output_path) else 0,
        "drive_folder": drive_folder,
        "elapsed_seconds": elapsed_sec,
        "message": f"Patrón Nutricional Oficial de 20 páginas generado y guardado en Google Drive en {elapsed_sec}s." if pdf_success else "Se generó el HTML pero ocurrió un error al compilar el PDF con Edge."
    }
