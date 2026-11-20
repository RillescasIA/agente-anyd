"""
consultation_manager.py — Bloque A de «Dietowin Next»
=====================================================
Ficha de consulta (bioimpedancia Tanita MC-580 + antropometría ISAK) e informe evolutivo.

Diseño:
- Cada consulta = una fila de `tanita_measurements` (tabla ya existente y usada por el resto del CRM:
  dossier PDF, patrones nutricionales, consulta 360°). Así todo el sistema ve los mismos datos.
- Antropometría en `perimeters_json` / `skinfolds_json` (mismas claves que el formulario de nuevo paciente).
- NUNCA se inventan valores: si un dato no se ha medido queda en NULL (a diferencia de importadores antiguos).
"""
import json
import os
import sqlite3
from datetime import datetime, date
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "anyd_booking.db"))

# --------------------------------------------------------------------------------------
# Catálogos de campos
# --------------------------------------------------------------------------------------
TANITA_FIELDS = [
    "weight", "fat_percent", "fat_mass", "ffm", "muscle_mass", "water_percent",
    "bone_mass", "visceral_fat", "bmr_tanita", "metabolic_age", "physical_rating",
]

PERIMETER_KEYS = ["waist", "hip", "arm_relaxed", "arm_flexed", "chest", "thigh", "calf"]
SKINFOLD_KEYS = ["triceps", "subscapular", "biceps", "iliac_crest", "supraspinale", "abdominal", "thigh", "calf"]

# Alias de importaciones antiguas (dietowin_scanner) -> claves normalizadas
LEGACY_PERIMETER_ALIASES = {
    "cintura_cm": "waist", "cadera_cm": "hip", "brazo_cm": "arm_relaxed", "muslo_cm": "thigh",
    "cintura": "waist", "cadera": "hip", "brazo": "arm_relaxed", "muslo": "thigh", "gemelo": "calf",
}

# Métricas mostradas en el evolutivo. better: "down" | "up" | None (neutral, depende del objetivo)
METRICS: List[Dict[str, Any]] = [
    {"key": "weight", "label": "Peso", "unit": "kg", "group": "Generales", "better": None, "dec": 1},
    {"key": "bmi", "label": "IMC", "unit": "", "group": "Generales", "better": None, "dec": 1},
    {"key": "bmr_cunningham", "label": "Metabolismo basal (Cunningham)", "unit": "kcal", "group": "Generales", "better": "up", "dec": 0},
    {"key": "bmr_tanita", "label": "Metabolismo basal (Tanita)", "unit": "kcal", "group": "Generales", "better": "up", "dec": 0},

    {"key": "fat_mass", "label": "Masa grasa", "unit": "kg", "group": "Composición corporal (BIA)", "better": "down", "dec": 1},
    {"key": "fat_percent", "label": "% Masa grasa", "unit": "%", "group": "Composición corporal (BIA)", "better": "down", "dec": 1},
    {"key": "ffm", "label": "Masa libre de grasa", "unit": "kg", "group": "Composición corporal (BIA)", "better": "up", "dec": 1},
    {"key": "muscle_mass", "label": "Masa muscular total", "unit": "kg", "group": "Composición corporal (BIA)", "better": "up", "dec": 1},
    {"key": "bone_mass", "label": "Mineral óseo", "unit": "kg", "group": "Composición corporal (BIA)", "better": "up", "dec": 1},
    {"key": "water_percent", "label": "% Agua corporal total", "unit": "%", "group": "Composición corporal (BIA)", "better": "up", "dec": 1},
    {"key": "visceral_fat", "label": "Grasa visceral", "unit": "", "group": "Composición corporal (BIA)", "better": "down", "dec": 0},
    {"key": "metabolic_age", "label": "Edad metabólica", "unit": "años", "group": "Composición corporal (BIA)", "better": "down", "dec": 0},

    {"key": "per_waist", "label": "Cintura", "unit": "cm", "group": "Perímetros", "better": "down", "dec": 1},
    {"key": "per_hip", "label": "Cadera", "unit": "cm", "group": "Perímetros", "better": None, "dec": 1},
    {"key": "per_arm_relaxed", "label": "Brazo relajado", "unit": "cm", "group": "Perímetros", "better": None, "dec": 1},
    {"key": "per_arm_flexed", "label": "Brazo contraído", "unit": "cm", "group": "Perímetros", "better": "up", "dec": 1},
    {"key": "per_chest", "label": "Tórax", "unit": "cm", "group": "Perímetros", "better": None, "dec": 1},
    {"key": "per_thigh", "label": "Muslo", "unit": "cm", "group": "Perímetros", "better": None, "dec": 1},
    {"key": "per_calf", "label": "Gemelo", "unit": "cm", "group": "Perímetros", "better": None, "dec": 1},
    {"key": "idx_waist_hip", "label": "Índice cintura/cadera", "unit": "", "group": "Perímetros", "better": "down", "dec": 2},
    {"key": "idx_waist_height", "label": "Índice cintura/altura", "unit": "", "group": "Perímetros", "better": "down", "dec": 2},

    {"key": "sum6", "label": "Σ 6 pliegues", "unit": "mm", "group": "Pliegues cutáneos", "better": "down", "dec": 1},
    {"key": "sum8", "label": "Σ 8 pliegues", "unit": "mm", "group": "Pliegues cutáneos", "better": "down", "dec": 1},
    {"key": "fat_yuhasz", "label": "% Grasa Yuhasz", "unit": "%", "group": "Pliegues cutáneos", "better": "down", "dec": 1},
    {"key": "fat_faulkner", "label": "% Grasa Faulkner", "unit": "%", "group": "Pliegues cutáneos", "better": "down", "dec": 1},
    {"key": "fat_durnin", "label": "% Grasa Durnin-Womersley", "unit": "%", "group": "Pliegues cutáneos", "better": "down", "dec": 1},
]


# --------------------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------------------
def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _num(v: Any) -> Optional[float]:
    """Convierte a float; vacío, 0 o inválido -> None (0 = no medido en los formularios)."""
    if v is None or v == "":
        return None
    try:
        f = float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return f if f != 0 else None


def _r(v: Optional[float], d: int = 1) -> Optional[float]:
    return None if v is None else round(v, d)


def ensure_schema() -> None:
    """Añade columnas necesarias a tanita_measurements (idempotente)."""
    conn = get_db()
    cur = conn.cursor()
    for col, typ in [
        ("skinfolds_json", "TEXT"), ("perimeters_json", "TEXT"), ("sum_skinfolds", "REAL"),
        ("waist_cm", "REAL"), ("hip_cm", "REAL"), ("height_cm", "REAL"),
        ("consultation_notes", "TEXT"), ("source", "TEXT"), ("updated_at", "TEXT"),
    ]:
        try:
            cur.execute(f"ALTER TABLE tanita_measurements ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()


def _age(birth_date: Optional[str], at: Optional[str] = None) -> Optional[int]:
    if not birth_date:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            b = datetime.strptime(birth_date[:10], fmt).date()
            break
        except ValueError:
            continue
    else:
        return None
    ref = datetime.strptime(at[:10], "%Y-%m-%d").date() if at else date.today()
    return ref.year - b.year - ((ref.month, ref.day) < (b.month, b.day))


def _is_female(gender: Optional[str]) -> bool:
    """En el CRM: 'M' = masculino (valor por defecto), 'F' = femenino."""
    g = str(gender or "").strip().upper()
    return g.startswith("F") or g.startswith("W") or g.startswith("MUJ")


# --------------------------------------------------------------------------------------
# Cálculos antropométricos
# --------------------------------------------------------------------------------------
def _durnin_density(sum4: float, age: int, female: bool) -> float:
    """Durnin & Womersley (1974): Densidad = c - m * log10(Σ4)."""
    import math
    table_m = [(19, 1.1620, 0.0630), (29, 1.1631, 0.0632), (39, 1.1422, 0.0544), (49, 1.1620, 0.0700), (200, 1.1715, 0.0779)]
    table_f = [(19, 1.1549, 0.0678), (29, 1.1599, 0.0717), (39, 1.1423, 0.0632), (49, 1.1333, 0.0612), (200, 1.1339, 0.0645)]
    for max_age, c, m in (table_f if female else table_m):
        if age <= max_age:
            return c - m * math.log10(sum4)
    return 1.1


def compute_derived(rec: Dict[str, Any], height_cm: Optional[float], gender: Optional[str], age: Optional[int]) -> Dict[str, Any]:
    """Calcula IMC, Cunningham, índices y % grasa por pliegues a partir de una medición."""
    female = _is_female(gender)
    out: Dict[str, Any] = {}
    w = rec.get("weight")
    h = height_cm
    fat_pct, fat_mass, ffm = rec.get("fat_percent"), rec.get("fat_mass"), rec.get("ffm")

    # Coherencia BIA: completar solo lo derivable matemáticamente
    if w and fat_pct and not fat_mass:
        fat_mass = w * fat_pct / 100
    if w and fat_mass and not ffm:
        ffm = w - fat_mass
    if w and fat_mass and not fat_pct:
        fat_pct = fat_mass / w * 100
    out["fat_mass"], out["ffm"], out["fat_percent"] = _r(fat_mass, 2), _r(ffm, 2), _r(fat_pct, 1)

    out["bmi"] = _r(w / (h / 100) ** 2, 1) if w and h else rec.get("bmi")
    out["bmr_cunningham"] = round(500 + 22 * ffm) if ffm else None

    per = rec.get("perimeters") or {}
    sk = rec.get("skinfolds") or {}
    waist, hip, thigh = per.get("waist"), per.get("hip"), per.get("thigh")
    out["idx_waist_hip"] = _r(waist / hip, 2) if waist and hip else None
    out["idx_waist_height"] = _r(waist / h, 2) if waist and h else None
    out["idx_hip_thigh"] = _r(hip / thigh, 2) if hip and thigh else None

    six = ["triceps", "subscapular", "supraspinale", "abdominal", "thigh", "calf"]
    out["sum6"] = _r(sum(sk[k] for k in six), 1) if all(sk.get(k) for k in six) else None
    out["sum8"] = _r(sum(sk[k] for k in SKINFOLD_KEYS), 1) if all(sk.get(k) for k in SKINFOLD_KEYS) else None
    # Yuhasz (1974) modificada ISAK
    if out["sum6"]:
        out["fat_yuhasz"] = _r(0.1548 * out["sum6"] + 3.580 if female else 0.1051 * out["sum6"] + 2.585, 1)
    else:
        out["fat_yuhasz"] = None
    # Faulkner (1968): tríceps + subescapular + supraespinal + abdominal
    f4 = ["triceps", "subscapular", "supraspinale", "abdominal"]
    out["fat_faulkner"] = _r(0.153 * sum(sk[k] for k in f4) + 5.783, 1) if all(sk.get(k) for k in f4) else None
    # Durnin-Womersley + Siri: bíceps + tríceps + subescapular + cresta ilíaca
    d4 = ["biceps", "triceps", "subscapular", "iliac_crest"]
    if all(sk.get(k) for k in d4) and age:
        dens = _durnin_density(sum(sk[k] for k in d4), age, female)
        out["fat_durnin"] = _r(495 / dens - 450, 1)
    else:
        out["fat_durnin"] = None
    return out


def fat_percent_reference(gender: Optional[str], age: Optional[int]) -> Dict[str, Any]:
    """Rangos saludables de % grasa (Gallagher et al., 2000 — usados por Tanita)."""
    female = _is_female(gender)
    a = age or 30
    if female:
        rng = (21, 33, 39) if a < 40 else (23, 34, 40) if a < 60 else (24, 36, 42)
    else:
        rng = (8, 20, 25) if a < 40 else (11, 22, 28) if a < 60 else (13, 25, 30)
    return {"low": rng[0], "high": rng[1], "obese": rng[2],
            "label": f"Saludable {rng[0]}–{rng[1]} % (Gallagher 2000, {'mujer' if female else 'hombre'})"}


# --------------------------------------------------------------------------------------
# Lectura
# --------------------------------------------------------------------------------------
def get_patient(client_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db()
    c = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not c:
        conn.close()
        return None
    p = conn.execute("SELECT * FROM athlete_profiles WHERE client_id = ?", (client_id,)).fetchone()
    conn.close()
    client, profile = dict(c), dict(p) if p else {}
    return {
        "id": client_id,
        "fullname": client.get("fullname"),
        "email": client.get("email"),
        "phone": client.get("phone"),
        "photo_url": client.get("photo_url"),
        "gender": profile.get("gender") or "",
        "birth_date": profile.get("birth_date") or "",
        "age": _age(profile.get("birth_date")),
        "height_cm": profile.get("height_cm"),
        "sport_discipline": profile.get("sport_discipline") or "",
        "main_goal": profile.get("main_goal") or "",
        "has_profile": bool(p),
    }


def _parse_json(s: Any) -> Dict[str, Any]:
    if not s:
        return {}
    try:
        d = json.loads(s) if isinstance(s, str) else dict(s)
        return d if isinstance(d, dict) else {}
    except (ValueError, TypeError):
        return {}


def _normalize_row(row: sqlite3.Row, patient: Dict[str, Any]) -> Dict[str, Any]:
    r = dict(row)
    per_raw, sk_raw = _parse_json(r.get("perimeters_json")), _parse_json(r.get("skinfolds_json"))
    per: Dict[str, float] = {}
    for k, v in per_raw.items():
        key = LEGACY_PERIMETER_ALIASES.get(k, k)
        if key in PERIMETER_KEYS and _num(v):
            per[key] = _num(v)
    if r.get("waist_cm") and "waist" not in per:
        per["waist"] = _num(r["waist_cm"])
    if r.get("hip_cm") and "hip" not in per:
        per["hip"] = _num(r["hip_cm"])
    sk = {k: _num(v) for k, v in sk_raw.items() if k in SKINFOLD_KEYS and _num(v)}

    rec: Dict[str, Any] = {
        "id": r["id"],
        "date": (r.get("measurement_date") or "")[:10],
        "notes": r.get("consultation_notes") or "",
        "source": r.get("source") or "",
        "perimeters": per,
        "skinfolds": sk,
    }
    for f in TANITA_FIELDS:
        rec[f] = _num(r.get(f))
    rec["bmi"] = _num(r.get("bmi"))
    height = _num(r.get("height_cm")) or _num(patient.get("height_cm"))
    rec["height_cm"] = height
    age = _age(patient.get("birth_date"), rec["date"] or None)
    rec.update(compute_derived(rec, height, patient.get("gender"), age))
    for k in PERIMETER_KEYS:
        rec[f"per_{k}"] = per.get(k)
    return rec


def list_consultations(client_id: int) -> List[Dict[str, Any]]:
    patient = get_patient(client_id) or {}
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM tanita_measurements WHERE client_id = ? ORDER BY measurement_date ASC, id ASC",
        (client_id,),
    ).fetchall()
    conn.close()
    return [_normalize_row(r, patient) for r in rows]


def get_evolution(client_id: int) -> Dict[str, Any]:
    """Historial completo + deltas (vs. anterior y vs. inicio) estilo 'Tabla de Datos' de Dietowin."""
    patient = get_patient(client_id)
    if not patient:
        return {}
    cons = list_consultations(client_id)
    first, last = (cons[0], cons[-1]) if cons else (None, None)
    prev = cons[-2] if len(cons) >= 2 else None

    def delta(a, b, k, dec):
        if not a or not b or a.get(k) is None or b.get(k) is None:
            return None
        return round(a[k] - b[k], dec)

    metrics = []
    for m in METRICS:
        if not any(c.get(m["key"]) is not None for c in cons):
            continue  # ocultar métricas nunca medidas
        metrics.append({
            **m,
            "last": last.get(m["key"]) if last else None,
            "delta_prev": delta(last, prev, m["key"], m["dec"]),
            "delta_first": delta(last, first, m["key"], m["dec"]) if len(cons) >= 2 else None,
            "series": [{"date": c["date"], "value": c.get(m["key"])} for c in cons],
        })

    days_prev = days_total = None
    try:
        if prev:
            days_prev = (datetime.strptime(last["date"], "%Y-%m-%d") - datetime.strptime(prev["date"], "%Y-%m-%d")).days
        if len(cons) >= 2:
            days_total = (datetime.strptime(last["date"], "%Y-%m-%d") - datetime.strptime(first["date"], "%Y-%m-%d")).days
    except (ValueError, TypeError):
        pass

    return {
        "patient": patient,
        "consultations": cons,
        "metrics": metrics,
        "count": len(cons),
        "days_since_prev": days_prev,
        "days_total": days_total,
        "fat_reference": fat_percent_reference(patient.get("gender"), patient.get("age")),
    }


# --------------------------------------------------------------------------------------
# Escritura
# --------------------------------------------------------------------------------------
def save_consultation(client_id: int, data: Dict[str, Any], consultation_id: Optional[int] = None) -> Dict[str, Any]:
    """Crea o actualiza una consulta. Solo guarda lo medido (sin valores inventados)."""
    patient = get_patient(client_id)
    if not patient:
        raise ValueError("Paciente no encontrado")

    meas_date = (data.get("date") or datetime.now().strftime("%Y-%m-%d"))[:10]
    height = _num(data.get("height_cm")) or _num(patient.get("height_cm"))
    rec: Dict[str, Any] = {f: _num(data.get(f)) for f in TANITA_FIELDS}
    per = {k: _num((data.get("perimeters") or {}).get(k)) for k in PERIMETER_KEYS}
    sk = {k: _num((data.get("skinfolds") or {}).get(k)) for k in SKINFOLD_KEYS}
    rec["perimeters"] = {k: v for k, v in per.items() if v}
    rec["skinfolds"] = {k: v for k, v in sk.items() if v}

    if not rec["weight"] and not rec["perimeters"] and not rec["skinfolds"]:
        raise ValueError("La consulta no contiene ninguna medida (peso, perímetros o pliegues)")

    d = compute_derived(rec, height, patient.get("gender"), _age(patient.get("birth_date"), meas_date))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    values = {
        "client_id": client_id,
        "client_name": patient["fullname"],
        "measurement_date": meas_date,
        "weight": rec["weight"],
        "bmi": d["bmi"],
        "fat_percent": d["fat_percent"],
        "fat_mass": d["fat_mass"],
        "ffm": d["ffm"],
        "muscle_mass": rec["muscle_mass"],
        "water_percent": rec["water_percent"],
        "bone_mass": rec["bone_mass"],
        "visceral_fat": rec["visceral_fat"],
        "bmr_tanita": rec["bmr_tanita"],
        "bmr_cunningham": d["bmr_cunningham"],
        "metabolic_age": rec["metabolic_age"],
        "physical_rating": rec["physical_rating"],
        "perimeters_json": json.dumps(rec["perimeters"]) if rec["perimeters"] else None,
        "skinfolds_json": json.dumps(rec["skinfolds"]) if rec["skinfolds"] else None,
        "sum_skinfolds": d["sum6"],
        "waist_cm": rec["perimeters"].get("waist"),
        "hip_cm": rec["perimeters"].get("hip"),
        "height_cm": height,
        "consultation_notes": (data.get("notes") or "").strip() or None,
        "source": data.get("source") or "consulta_web",
        "updated_at": now,
    }

    conn = get_db()
    cur = conn.cursor()
    if consultation_id:
        own = cur.execute("SELECT id FROM tanita_measurements WHERE id = ? AND client_id = ?", (consultation_id, client_id)).fetchone()
        if not own:
            conn.close()
            raise ValueError("Consulta no encontrada para este paciente")
        sets = ", ".join(f"{k} = ?" for k in values)
        cur.execute(f"UPDATE tanita_measurements SET {sets} WHERE id = ?", (*values.values(), consultation_id))
        cid = consultation_id
    else:
        values["created_at"] = now
        cols = ", ".join(values)
        cur.execute(f"INSERT INTO tanita_measurements ({cols}) VALUES ({', '.join('?' * len(values))})", tuple(values.values()))
        cid = cur.lastrowid

    # Mantener la altura del perfil actualizada
    if height and _num(data.get("height_cm")):
        if patient.get("has_profile"):
            cur.execute("UPDATE athlete_profiles SET height_cm = ?, updated_at = ? WHERE client_id = ?", (height, now, client_id))
        else:
            cur.execute("INSERT INTO athlete_profiles (client_id, height_cm) VALUES (?, ?)", (client_id, height))
    conn.commit()
    conn.close()
    return {"success": True, "id": cid, "date": meas_date, "derived": d}


def update_patient_basics(client_id: int, data: Dict[str, Any]) -> None:
    """Sexo, fecha de nacimiento y altura: imprescindibles para los cálculos."""
    conn = get_db()
    exists = conn.execute("SELECT 1 FROM athlete_profiles WHERE client_id = ?", (client_id,)).fetchone()
    fields = {k: data.get(k) for k in ("gender", "birth_date", "height_cm") if data.get(k) not in (None, "")}
    if fields:
        if exists:
            conn.execute(f"UPDATE athlete_profiles SET {', '.join(f'{k} = ?' for k in fields)} WHERE client_id = ?", (*fields.values(), client_id))
        else:
            conn.execute(f"INSERT INTO athlete_profiles (client_id, {', '.join(fields)}) VALUES (?, {', '.join('?' * len(fields))})", (client_id, *fields.values()))
        conn.commit()
    conn.close()


def delete_consultation(client_id: int, consultation_id: int) -> bool:
    conn = get_db()
    cur = conn.execute("DELETE FROM tanita_measurements WHERE id = ? AND client_id = ?", (consultation_id, client_id))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


ensure_schema()
