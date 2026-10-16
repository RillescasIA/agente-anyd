import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "anyd_booking.db"))

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_clinical_tables():
    """
    Crea las tablas necesarias para la Estación Clínica & Deportiva:
    - athlete_profiles: Ficha deportiva, antecedentes médicos y objetivos.
    - clinical_notes: Registro estructurado de consultas SOAP.
    - lab_tests: Analíticas sanguíneas y biomarcadores deportivos.
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS athlete_profiles (
        client_id INTEGER PRIMARY KEY,
        birth_date TEXT,
        gender TEXT DEFAULT 'M',
        height_cm REAL DEFAULT 175.0,
        sport_discipline TEXT DEFAULT 'Deportes de Resistencia',
        competition_level TEXT DEFAULT 'Aficionado / Popular',
        training_days_week INTEGER DEFAULT 4,
        training_hours_week REAL DEFAULT 6.0,
        competition_date TEXT,
        main_goal TEXT DEFAULT 'Rendimiento y Composición Corporal',
        allergies TEXT,
        pathologies TEXT,
        medications TEXT,
        digestive_issues TEXT,
        notes TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (client_id) REFERENCES clients (id)
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clinical_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        appointment_id INTEGER,
        session_date TEXT NOT NULL,
        session_type TEXT DEFAULT 'Seguimiento',
        subjective TEXT,
        objective TEXT,
        assessment TEXT,
        plan TEXT,
        private_notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (client_id) REFERENCES clients (id),
        FOREIGN KEY (appointment_id) REFERENCES appointments (id)
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lab_tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        test_date TEXT NOT NULL,
        lab_name TEXT DEFAULT 'Analítica Sanguínea General',
        hemoglobin REAL,
        hematocrit REAL,
        ferritin REAL,
        iron REAL,
        vitamin_d REAL,
        glucose REAL,
        hba1c REAL,
        cholesterol_total REAL,
        hdl REAL,
        ldl REAL,
        triglycerides REAL,
        ast_got REAL,
        alt_gpt REAL,
        urea REAL,
        creatinine REAL,
        crp REAL,
        cpk REAL,
        testosterone REAL,
        cortisol REAL,
        tsh REAL,
        clinical_interpretation TEXT,
        action_plan TEXT,
        file_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (client_id) REFERENCES clients (id)
    )""")

    conn.commit()
    conn.close()

def search_athletes(query: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    """
    Busca atletas por nombre, teléfono o email, incluyendo su último bono y medición.
    """
    conn = get_db()
    cursor = conn.cursor()

    sql = """
    SELECT 
        c.id, c.fullname, c.email, c.phone,
        p.sport_discipline, p.main_goal, p.gender, p.height_cm,
        (SELECT COUNT(*) FROM appointments a WHERE a.client_id = c.id) as total_appointments,
        (SELECT b.tipo_bono || ' (' || b.used_sessions || '/' || b.total_sessions || ')' 
         FROM bonos b WHERE b.client_id = c.id AND b.status = 'Activo' ORDER BY b.id DESC LIMIT 1) as bono_info,
        (SELECT tm.weight FROM tanita_measurements tm WHERE tm.client_id = c.id ORDER BY tm.measurement_date DESC LIMIT 1) as last_weight,
        (SELECT tm.ffm FROM tanita_measurements tm WHERE tm.client_id = c.id ORDER BY tm.measurement_date DESC LIMIT 1) as last_ffm,
        (SELECT tm.fat_percent FROM tanita_measurements tm WHERE tm.client_id = c.id ORDER BY tm.measurement_date DESC LIMIT 1) as last_fat_pct
    FROM clients c
    LEFT JOIN athlete_profiles p ON c.id = p.client_id
    WHERE 1=1
    """
    params = []
    if query:
        q = f"%{query.strip()}%"
        sql += " AND (c.fullname LIKE ? OR c.email LIKE ? OR c.phone LIKE ?)"
        params.extend([q, q, q])

    sql += " ORDER BY c.fullname ASC LIMIT ?"
    params.append(limit)

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    athletes = [dict(r) for r in rows]
    conn.close()
    return athletes

def get_today_scheduled_athletes() -> List[Dict[str, Any]]:
    """
    Devuelve los atletas que tienen cita programada para hoy.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    cursor = conn.cursor()

    sql = """
    SELECT 
        a.id as appointment_id, a.client_id, a.client_name, a.appointment_time, a.modality, a.service, a.status,
        c.phone, c.email,
        p.sport_discipline,
        (SELECT tm.weight FROM tanita_measurements tm WHERE tm.client_id = a.client_id ORDER BY tm.measurement_date DESC LIMIT 1) as last_weight
    FROM appointments a
    LEFT JOIN clients c ON a.client_id = c.id
    LEFT JOIN athlete_profiles p ON a.client_id = p.client_id
    WHERE a.appointment_date = ?
    ORDER BY a.appointment_time ASC
    """
    cursor.execute(sql, (today_str,))
    rows = cursor.fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results

def get_athlete_360(client_id: int) -> Dict[str, Any]:
    """
    Reúne en un único objeto toda la información 360° del deportista:
    - Datos personales y de contacto
    - Perfil deportivo y antecedentes clínicos (athlete_profiles)
    - Bonos y saldo
    - Historial de citas
    - Historial completo de mediciones Tanita con deltas calculados
    - Notas SOAP clínicas
    - Analíticas sanguíneas con evaluación de biomarcadores
    - Planes nutricionales asignados
    """
    conn = get_db()
    cursor = conn.cursor()

    # 1. Datos básicos
    cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
    client_row = cursor.fetchone()
    if not client_row:
        conn.close()
        return {}
    client = dict(client_row)

    # 2. Perfil deportivo / antecedentes
    cursor.execute("SELECT * FROM athlete_profiles WHERE client_id = ?", (client_id,))
    profile_row = cursor.fetchone()
    if profile_row:
        profile = dict(profile_row)
    else:
        # Perfil por defecto
        profile = {
            "client_id": client_id,
            "birth_date": "",
            "gender": "M",
            "height_cm": 175.0,
            "sport_discipline": "Deportes de Resistencia",
            "competition_level": "Aficionado / Popular",
            "training_days_week": 4,
            "training_hours_week": 6.0,
            "competition_date": "",
            "main_goal": "Rendimiento y Composición Corporal",
            "allergies": "",
            "pathologies": "",
            "medications": "",
            "digestive_issues": "",
            "notes": ""
        }

    # 3. Bonos
    cursor.execute("SELECT * FROM bonos WHERE client_id = ? ORDER BY id DESC", (client_id,))
    bonos = [dict(r) for r in cursor.fetchall()]

    # 4. Citas
    cursor.execute("""
    SELECT id, appointment_date, appointment_time, modality, service, status, notes 
    FROM appointments WHERE client_id = ? ORDER BY appointment_date DESC, appointment_time DESC LIMIT 20
    """, (client_id,))
    appointments = [dict(r) for r in cursor.fetchall()]

    # 5. Mediciones Tanita
    cursor.execute("""
    SELECT id, measurement_date, weight, bmi, fat_percent, fat_mass, muscle_mass, ffm,
           water_percent, bone_mass, visceral_fat, bmr_tanita, bmr_cunningham, metabolic_age, physical_rating
    FROM tanita_measurements WHERE client_id = ? ORDER BY measurement_date ASC
    """, (client_id,))
    tanita_history = [dict(r) for r in cursor.fetchall()]

    # Calcular deltas respecto a la última medición si hay >= 2
    tanita_deltas = {}
    if len(tanita_history) >= 2:
        last = tanita_history[-1]
        prev = tanita_history[-2]
        tanita_deltas = {
            "weight_delta": round((last.get("weight") or 0) - (prev.get("weight") or 0), 2),
            "fat_pct_delta": round((last.get("fat_percent") or 0) - (prev.get("fat_percent") or 0), 2),
            "ffm_delta": round((last.get("ffm") or 0) - (prev.get("ffm") or 0), 2),
            "muscle_delta": round((last.get("muscle_mass") or 0) - (prev.get("muscle_mass") or 0), 2),
        }

    # 6. Notas SOAP
    cursor.execute("""
    SELECT * FROM clinical_notes WHERE client_id = ? ORDER BY session_date DESC, id DESC
    """, (client_id,))
    soap_notes = [dict(r) for r in cursor.fetchall()]

    # 7. Analíticas de sangre
    cursor.execute("""
    SELECT * FROM lab_tests WHERE client_id = ? ORDER BY test_date DESC, id DESC
    """, (client_id,))
    raw_labs = [dict(r) for r in cursor.fetchall()]

    # Enriquecer analíticas con semáforos de referencia clínica/deportiva
    labs_enriched = []
    for lab in raw_labs:
        evaluated = evaluate_biomarkers(lab, profile.get("gender", "M"))
        lab["evaluated_biomarkers"] = evaluated
        labs_enriched.append(lab)

    # 8. Planes Nutricionales
    cursor.execute("""
    SELECT id, plan_name, created_at, weight, ffm, bmr, tdee, target_kcal, target_protein_g, target_carbs_g, target_fat_g, weekly_data_json, notes
    FROM diet_plans WHERE client_id = ? ORDER BY id DESC
    """, (client_id,))
    diet_plans = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        "client": client,
        "profile": profile,
        "bonos": bonos,
        "appointments": appointments,
        "tanita_history": tanita_history,
        "tanita_deltas": tanita_deltas,
        "latest_tanita": tanita_history[-1] if tanita_history else None,
        "soap_notes": soap_notes,
        "lab_tests": labs_enriched,
        "diet_plans": diet_plans
    }

def evaluate_biomarkers(lab: Dict[str, Any], gender: str = "M") -> Dict[str, Dict[str, Any]]:
    """
    Evalúa biomarcadores sanguíneos según rangos específicos para deportistas de alto rendimiento.
    Retorna un diccionario con valor, rango de referencia, unidad y badge de estado ('optimal', 'warning', 'alert').
    """
    is_male = gender.upper() == "M"

    specs = {
        "hemoglobin": {
            "name": "Hemoglobina",
            "unit": "g/dL",
            "val": lab.get("hemoglobin"),
            "ref": "13.5 - 17.5" if is_male else "12.0 - 15.5",
            "eval": lambda v: "alert" if v is not None and (v < (13.0 if is_male else 11.5) or v > 18.0) else ("warning" if v is not None and (v < (13.5 if is_male else 12.0)) else "optimal")
        },
        "hematocrit": {
            "name": "Hematocrito",
            "unit": "%",
            "val": lab.get("hematocrit"),
            "ref": "40 - 50%" if is_male else "36 - 46%",
            "eval": lambda v: "alert" if v is not None and (v < 37 or v > 52) else ("warning" if v is not None and (v < 40 if is_male else v < 36) else "optimal")
        },
        "ferritin": {
            "name": "Ferritina (Depósitos de Hierro)",
            "unit": "ng/mL (μg/L)",
            "val": lab.get("ferritin"),
            "ref": "> 40 - 50 ng/mL (Deportista)",
            "eval": lambda v: "alert" if v is not None and v < 25 else ("warning" if v is not None and v < 40 else "optimal")
        },
        "iron": {
            "name": "Hierro Sérico",
            "unit": "μg/dL",
            "val": lab.get("iron"),
            "ref": "60 - 160 μg/dL",
            "eval": lambda v: "alert" if v is not None and (v < 50 or v > 180) else ("warning" if v is not None and v < 60 else "optimal")
        },
        "vitamin_d": {
            "name": "Vitamina D (25-OH)",
            "unit": "ng/mL",
            "val": lab.get("vitamin_d"),
            "ref": "40 - 60 ng/mL (Óptimo rendimiento)",
            "eval": lambda v: "alert" if v is not None and v < 25 else ("warning" if v is not None and v < 35 else "optimal")
        },
        "glucose": {
            "name": "Glucosa Basal",
            "unit": "mg/dL",
            "val": lab.get("glucose"),
            "ref": "70 - 100 mg/dL",
            "eval": lambda v: "alert" if v is not None and (v < 65 or v > 115) else ("warning" if v is not None and v > 100 else "optimal")
        },
        "cholesterol_total": {
            "name": "Colesterol Total",
            "unit": "mg/dL",
            "val": lab.get("cholesterol_total"),
            "ref": "< 200 mg/dL",
            "eval": lambda v: "alert" if v is not None and v > 240 else ("warning" if v is not None and v > 200 else "optimal")
        },
        "hdl": {
            "name": "Colesterol HDL (Bueno)",
            "unit": "mg/dL",
            "val": lab.get("hdl"),
            "ref": "> 45 mg/dL",
            "eval": lambda v: "alert" if v is not None and v < 35 else ("warning" if v is not None and v < 45 else "optimal")
        },
        "ldl": {
            "name": "Colesterol LDL",
            "unit": "mg/dL",
            "val": lab.get("ldl"),
            "ref": "< 115 mg/dL",
            "eval": lambda v: "alert" if v is not None and v > 140 else ("warning" if v is not None and v > 115 else "optimal")
        },
        "triglycerides": {
            "name": "Triglicéridos",
            "unit": "mg/dL",
            "val": lab.get("triglycerides"),
            "ref": "< 150 mg/dL",
            "eval": lambda v: "alert" if v is not None and v > 200 else ("warning" if v is not None and v > 150 else "optimal")
        },
        "alt_gpt": {
            "name": "ALT / GPT (Hepático)",
            "unit": "U/L",
            "val": lab.get("alt_gpt"),
            "ref": "< 45 U/L",
            "eval": lambda v: "alert" if v is not None and v > 65 else ("warning" if v is not None and v > 45 else "optimal")
        },
        "ast_got": {
            "name": "AST / GOT (Hepático / Muscular)",
            "unit": "U/L",
            "val": lab.get("ast_got"),
            "ref": "< 40 U/L",
            "eval": lambda v: "alert" if v is not None and v > 65 else ("warning" if v is not None and v > 40 else "optimal")
        },
        "cpk": {
            "name": "Creatina Kinasa (CPK - Daño Muscular)",
            "unit": "U/L",
            "val": lab.get("cpk"),
            "ref": "< 250 U/L (Basal)",
            "eval": lambda v: "alert" if v is not None and v > 800 else ("warning" if v is not None and v > 350 else "optimal")
        },
        "creatinine": {
            "name": "Creatinina (Función Renal)",
            "unit": "mg/dL",
            "val": lab.get("creatinine"),
            "ref": "0.7 - 1.25 mg/dL",
            "eval": lambda v: "alert" if v is not None and v > 1.4 else ("warning" if v is not None and v > 1.25 else "optimal")
        },
        "crp": {
            "name": "Proteína C Reactiva (PCR - Inflamación)",
            "unit": "mg/L",
            "val": lab.get("crp"),
            "ref": "< 1.0 mg/L",
            "eval": lambda v: "alert" if v is not None and v > 3.0 else ("warning" if v is not None and v > 1.0 else "optimal")
        }
    }

    result = {}
    for key, item in specs.items():
        v = item["val"]
        if v is not None and v != "":
            status = item["eval"](float(v))
            result[key] = {
                "name": item["name"],
                "val": float(v),
                "unit": item["unit"],
                "ref": item["ref"],
                "status": status
            }
    return result

def save_athlete_profile(client_id: int, data: Dict[str, Any]) -> bool:
    """
    Guarda o actualiza la ficha deportiva y médica del atleta.
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO athlete_profiles (
        client_id, birth_date, gender, height_cm, sport_discipline, competition_level,
        training_days_week, training_hours_week, competition_date, main_goal,
        allergies, pathologies, medications, digestive_issues, notes, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(client_id) DO UPDATE SET
        birth_date = excluded.birth_date,
        gender = excluded.gender,
        height_cm = excluded.height_cm,
        sport_discipline = excluded.sport_discipline,
        competition_level = excluded.competition_level,
        training_days_week = excluded.training_days_week,
        training_hours_week = excluded.training_hours_week,
        competition_date = excluded.competition_date,
        main_goal = excluded.main_goal,
        allergies = excluded.allergies,
        pathologies = excluded.pathologies,
        medications = excluded.medications,
        digestive_issues = excluded.digestive_issues,
        notes = excluded.notes,
        updated_at = CURRENT_TIMESTAMP
    """, (
        client_id,
        data.get("birth_date", ""),
        data.get("gender", "M"),
        float(data.get("height_cm", 175.0)),
        data.get("sport_discipline", "Deportes de Resistencia"),
        data.get("competition_level", "Aficionado / Popular"),
        int(data.get("training_days_week", 4)),
        float(data.get("training_hours_week", 6.0)),
        data.get("competition_date", ""),
        data.get("main_goal", "Rendimiento"),
        data.get("allergies", ""),
        data.get("pathologies", ""),
        data.get("medications", ""),
        data.get("digestive_issues", ""),
        data.get("notes", "")
    ))
    conn.commit()
    conn.close()
    return True

def save_soap_note(client_id: int, data: Dict[str, Any]) -> int:
    """
    Guarda una nota clínica de consulta según el estándar SOAP.
    """
    conn = get_db()
    cursor = conn.cursor()

    session_date = data.get("session_date") or datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
    INSERT INTO clinical_notes (
        client_id, appointment_id, session_date, session_type,
        subjective, objective, assessment, plan, private_notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        client_id,
        data.get("appointment_id"),
        session_date,
        data.get("session_type", "Seguimiento"),
        data.get("subjective", ""),
        data.get("objective", ""),
        data.get("assessment", ""),
        data.get("plan", ""),
        data.get("private_notes", "")
    ))
    note_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return note_id

def save_lab_test(client_id: int, data: Dict[str, Any]) -> int:
    """
    Registra una nueva analítica sanguínea con sus biomarcadores.
    """
    conn = get_db()
    cursor = conn.cursor()

    test_date = data.get("test_date") or datetime.now().strftime("%Y-%m-%d")

    def parse_float(val):
        try:
            return float(val) if val not in [None, ""] else None
        except:
            return None

    cursor.execute("""
    INSERT INTO lab_tests (
        client_id, test_date, lab_name,
        hemoglobin, hematocrit, ferritin, iron, vitamin_d,
        glucose, hba1c, cholesterol_total, hdl, ldl, triglycerides,
        ast_got, alt_gpt, urea, creatinine, crp, cpk,
        testosterone, cortisol, tsh,
        clinical_interpretation, action_plan, file_path
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        client_id,
        test_date,
        data.get("lab_name", "Laboratorio Clínico"),
        parse_float(data.get("hemoglobin")),
        parse_float(data.get("hematocrit")),
        parse_float(data.get("ferritin")),
        parse_float(data.get("iron")),
        parse_float(data.get("vitamin_d")),
        parse_float(data.get("glucose")),
        parse_float(data.get("hba1c")),
        parse_float(data.get("cholesterol_total")),
        parse_float(data.get("hdl")),
        parse_float(data.get("ldl")),
        parse_float(data.get("triglycerides")),
        parse_float(data.get("ast_got")),
        parse_float(data.get("alt_gpt")),
        parse_float(data.get("urea")),
        parse_float(data.get("creatinine")),
        parse_float(data.get("crp")),
        parse_float(data.get("cpk")),
        parse_float(data.get("testosterone")),
        parse_float(data.get("cortisol")),
        parse_float(data.get("tsh")),
        data.get("clinical_interpretation", ""),
        data.get("action_plan", ""),
        data.get("file_path", "")
    ))
    test_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return test_id

def save_manual_tanita(client_id: int, client_name: str, data: Dict[str, Any]) -> int:
    """
    Permite registrar un pesaje de Tanita MC-580 manualmente o desde volcado rápido.
    Calcula automáticamente BMR Cunningham = 500 + 22 * FFM.
    """
    conn = get_db()
    cursor = conn.cursor()

    measurement_date = data.get("measurement_date") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    weight = float(data.get("weight", 70.0))
    ffm = float(data.get("ffm", 58.0))
    fat_pct = float(data.get("fat_percent", 15.0))
    fat_mass = round(weight * (fat_pct / 100.0), 2)
    muscle_mass = round(ffm * 0.95, 2)
    bmr_cunningham = round(500.0 + (22.0 * ffm), 1)

    cursor.execute("""
    INSERT INTO tanita_measurements (
        client_id, client_name, measurement_date, weight, bmi, fat_percent, fat_mass,
        muscle_mass, ffm, water_percent, bone_mass, visceral_fat, bmr_tanita, bmr_cunningham,
        metabolic_age, physical_rating, segmental_data, raw_data
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        client_id,
        client_name,
        measurement_date,
        weight,
        float(data.get("bmi", 22.5)),
        fat_pct,
        fat_mass,
        muscle_mass,
        ffm,
        float(data.get("water_percent", 60.0)),
        float(data.get("bone_mass", 3.1)),
        float(data.get("visceral_fat", 3.0)),
        float(data.get("bmr_tanita", bmr_cunningham)),
        bmr_cunningham,
        int(data.get("metabolic_age", 25)),
        int(data.get("physical_rating", 5)),
        json.dumps(data.get("segmental_data", {})),
        "MANUAL_ENTRY_OR_LIVE"
    ))
    measurement_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return measurement_id
