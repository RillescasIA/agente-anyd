# -*- coding: utf-8 -*-
"""
dietowin_scanner.py
Integración y Escáner de Fichas Clínicas de Dietowin & Bioimpedancia Tanita MC-580
para ANyD Nutricionistas · Román Illescas Quiroga (Col. MAD00274).

Localiza expedientes, extrae métricas de composición corporal desde:
1. PDFs oficiales de 'Composición Corporal' exportados por Dietowin / SuiteBiológica 11.
2. Archivos Excel / CSV de Tanita MC-580 en Google Drive.
3. Cuestionarios y fichas clínicas de inicio (Consultas .docx) con peso, talla y deporte.
4. Bases de datos y archivos .DW11W / .DW11D de C:\\SuiteBiológica11.
5. Tabla SQLite tanita_measurements.
"""

import os
import re
import io
import json
import sqlite3
import unicodedata
from datetime import datetime
from typing import Dict, Any, Optional, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "anyd_booking.db"))
DEPORTISTAS_DIR = r"G:\Mi unidad\1.- ANyD\1.- Deportistas"
SUITE_DIR = r"C:\SuiteBiológica11"

def get_db():
    current_db = os.environ.get("DB_PATH", DEFAULT_DB_PATH)
    conn = sqlite3.connect(current_db)
    conn.row_factory = sqlite3.Row
    return conn

def normalize_text(text: str) -> str:
    """Normaliza texto eliminando acentos, caracteres especiales y dobles espacios."""
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', str(text))
    t = "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()
    return re.sub(r'\s+', ' ', t)

def get_client_aliases(client_name: str) -> List[str]:
    """Obtiene variantes del nombre del cliente desde la base de datos (firstname, lastname, fullname)."""
    aliases = [client_name]
    norm_input = normalize_text(client_name)
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT firstname, lastname, fullname, email FROM clients
            WHERE LOWER(fullname) LIKE ? OR LOWER(firstname) LIKE ? OR LOWER(lastname) LIKE ?
        """, (f"%{norm_input}%", f"%{norm_input}%", f"%{norm_input}%"))
        rows = cursor.fetchall()
        conn.close()
        
        for r in rows:
            fn = r["firstname"] or ""
            ln = r["lastname"] or ""
            full = r["fullname"] or ""
            for name in [fn, ln, full, f"{fn} {ln}".strip()]:
                if name and len(name) >= 3 and name not in aliases:
                    aliases.append(name)
    except Exception as e:
        print(f"Error consultando alias para {client_name}: {e}")
        
    return aliases

def find_athlete_drive_folder(client_name: str) -> Optional[str]:
    """Busca la carpeta del deportista en G:\\Mi unidad\\1.- ANyD\\1.- Deportistas con ponderación estricta."""
    if not os.path.exists(DEPORTISTAS_DIR):
        return None

    norm_target = normalize_text(client_name)
    aliases = get_client_aliases(client_name)
    all_names = [client_name] + aliases
    norm_aliases = [normalize_text(a) for a in all_names if normalize_text(a)]

    try:
        folders = [f for f in os.listdir(DEPORTISTAS_DIR) if os.path.isdir(os.path.join(DEPORTISTAS_DIR, f))]
        
        # 1. Coincidencia EXACTA con cualquier alias o nombre de cliente
        for folder in folders:
            folder_norm = normalize_text(folder)
            for na in norm_aliases:
                if folder_norm == na:
                    return os.path.join(DEPORTISTAS_DIR, folder)

        # 2. Puntuación ponderada de tokens
        scored = []
        target_tokens = set()
        for na in norm_aliases:
            for t in na.split():
                if len(t) >= 3:
                    target_tokens.add(t)

        client_tokens = [t for t in normalize_text(client_name).split() if len(t) >= 3]

        for folder in folders:
            folder_norm = normalize_text(folder)
            f_toks = set([t for t in folder_norm.split() if len(t) >= 3])
            common = target_tokens.intersection(f_toks)

            score = 0
            if len(common) >= 2:
                score = 100 + len(common) * 30
            elif len(common) == 1:
                tok = list(common)[0]
                if len(tok) >= 4:
                    score = 25
                    if any(na in folder_norm or folder_norm in na for na in norm_aliases if len(na) >= 4):
                        score = 45

            # Bonificación estricta por tokens del nombre primario solicitado
            for ct in client_tokens:
                if ct in folder_norm:
                    score += 40

            if score > 0:
                scored.append((score, os.path.join(DEPORTISTAS_DIR, folder)))

        if scored:
            scored.sort(key=lambda x: x[0], reverse=True)
            return scored[0][1]

        return None
    except Exception as e:
        print(f"Error escaneando carpetas de deportistas: {e}")
        return None

def extract_composition_from_pdf(pdf_path: str) -> Optional[Dict[str, Any]]:
    """Extrae la tabla completa de composición corporal de un PDF de Dietowin."""
    try:
        import pypdf
        reader = pypdf.PdfReader(pdf_path)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"

        norm_full = normalize_text(full_text)
        if not any(k in norm_full for k in ["composicion corporal", "tabla de datos", "masa grasa", "tanita", "bia", "bioimpedancia"]):
            return None

        data = {
            "source_type": "Dietowin PDF Composición Corporal",
            "source_file": os.path.basename(pdf_path),
            "full_path": pdf_path,
            "measurement_date": None,
            "weight_kg": None,
            "height_cm": None,
            "bmi": None,
            "fat_percent": None,
            "fat_mass_kg": None,
            "ffm_kg": None,
            "ffm_percent": None,
            "muscle_mass_kg": None,
            "muscle_percent": None,
            "water_liters": None,
            "water_percent": None,
            "bone_mass_kg": None,
            "visceral_fat": None,
            "bmr_dietowin": None,
            "bmr_cunningham": None,
            "metabolic_age": None,
            "segmental": {}
        }

        # 1. Fecha del informe
        m_date = re.search(r'Del d[ií]a\s+(\d{2}/\d{2}/\d{4})', full_text, re.IGNORECASE) or re.search(r'Fecha:\s+(\d{2}/\d{2}/\d{4})', full_text, re.IGNORECASE) or re.search(r'TABLA DE DATOS\s+(\d{2}/\d{2}/\d{4})', full_text, re.IGNORECASE)
        if m_date:
            raw_d = m_date.group(1)
            try:
                dt = datetime.strptime(raw_d, "%d/%m/%Y")
                data["measurement_date"] = dt.strftime("%Y-%m-%d")
            except:
                data["measurement_date"] = raw_d
        else:
            m_fn_date = re.search(r'(\d{2})[-_](\d{2})[-_](\d{4})', os.path.basename(pdf_path))
            if m_fn_date:
                data["measurement_date"] = f"{m_fn_date.group(3)}-{m_fn_date.group(2)}-{m_fn_date.group(1)}"

        # 2. Altura
        m_h = re.search(r'Altura\s+([\d,.]+)\s*cm', full_text, re.IGNORECASE)
        if m_h:
            data["height_cm"] = float(m_h.group(1).replace(',', '.'))

        # 3. Peso
        m_w = re.search(r'Peso\s+([\d,.]+)\s*kg', full_text, re.IGNORECASE)
        if m_w:
            data["weight_kg"] = float(m_w.group(1).replace(',', '.'))

        # 4. IMC
        m_imc = re.search(r'IMC\s+([\d,.]+)', full_text, re.IGNORECASE)
        if m_imc:
            data["bmi"] = float(m_imc.group(1).replace(',', '.'))

        # 5. % Masa Grasa
        m_fat_pct = re.search(r'%\s*Masa Grasa\s+([\d,.]+)\s*%', full_text, re.IGNORECASE)
        if m_fat_pct:
            data["fat_percent"] = float(m_fat_pct.group(1).replace(',', '.'))

        # 6. Masa Grasa en kg
        m_fat_kg = re.search(r'Masa Grasa\s+([\d,.]+)\s*kg', full_text, re.IGNORECASE)
        if m_fat_kg:
            data["fat_mass_kg"] = float(m_fat_kg.group(1).replace(',', '.'))

        # 7. Masa Libre de Grasa (FFM)
        m_ffm = re.search(r'Masa Libre de Grasa\s+([\d,.]+)\s*kg', full_text, re.IGNORECASE)
        if m_ffm:
            data["ffm_kg"] = float(m_ffm.group(1).replace(',', '.'))
        m_ffm_pct = re.search(r'%\s*Masa Libre de Grasa\s+([\d,.]+)\s*%', full_text, re.IGNORECASE)
        if m_ffm_pct:
            data["ffm_percent"] = float(m_ffm_pct.group(1).replace(',', '.'))

        # 8. Masa Muscular Total
        m_mm = re.search(r'Masa Muscular Total\s+([\d,.]+)\s*kg', full_text, re.IGNORECASE) or re.search(r'Masa Muscular\s+([\d,.]+)\s*kg', full_text, re.IGNORECASE)
        if m_mm:
            data["muscle_mass_kg"] = float(m_mm.group(1).replace(',', '.'))
        m_mm_pct = re.search(r'%\s*Masa Muscular Total\s+([\d,.]+)\s*%', full_text, re.IGNORECASE)
        if m_mm_pct:
            data["muscle_percent"] = float(m_mm_pct.group(1).replace(',', '.'))

        # 9. Agua Corporal Total
        m_act_kg = re.search(r'Agua Corporal Total\s+([\d,.]+)\s*kg', full_text, re.IGNORECASE)
        if m_act_kg:
            data["water_liters"] = float(m_act_kg.group(1).replace(',', '.'))
        m_act_pct = re.search(r'%\s*ACT\s+([\d,.]+)\s*%', full_text, re.IGNORECASE)
        if m_act_pct:
            data["water_percent"] = float(m_act_pct.group(1).replace(',', '.'))

        # 10. Mineral Óseo
        m_bone = re.search(r'Mineral [ÓO]seo\s+([\d,.]+)\s*kg', full_text, re.IGNORECASE)
        if m_bone:
            data["bone_mass_kg"] = float(m_bone.group(1).replace(',', '.'))

        # 11. Grasa Visceral
        m_visc = re.search(r'[IÍ]ndice de Grasa Visceral\s+(\d+)', full_text, re.IGNORECASE)
        if m_visc:
            data["visceral_fat"] = int(m_visc.group(1))

        # 12. BMR Dietowin
        m_bmr = re.search(r'Metabolismo Basal\s+([\d,.]+)\s*kcal', full_text, re.IGNORECASE)
        if m_bmr:
            data["bmr_dietowin"] = int(m_bmr.group(1).replace('.', '').replace(',', ''))

        # 13. Edad Metabólica
        m_age = re.search(r'Edad Metab[oó]lica\s+(\d+)', full_text, re.IGNORECASE)
        if m_age:
            data["metabolic_age"] = int(m_age.group(1))

        # Estimaciones si faltan
        if data["weight_kg"] and data["fat_percent"] and not data["ffm_kg"]:
            data["fat_mass_kg"] = round(data["weight_kg"] * (data["fat_percent"] / 100.0), 1)
            data["ffm_kg"] = round(data["weight_kg"] - data["fat_mass_kg"], 1)

        # Cunningham BMR Gold Standard: 500 + 22 * FFM
        if data["ffm_kg"]:
            data["bmr_cunningham"] = round(500 + 22 * data["ffm_kg"])

        return data
    except Exception as e:
        print(f"Error procesando PDF de composición {pdf_path}: {e}")
        return None

def extract_composition_from_excel(excel_path: str) -> Optional[Dict[str, Any]]:
    """Extrae métricas de composición de archivos Excel / CSV de Tanita MC-580."""
    try:
        import openpyxl
        try:
            wb = openpyxl.load_workbook(excel_path, data_only=True)
        except:
            with open(excel_path, 'rb') as f:
                content = f.read()
            wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)

        ws = wb.active
        data = {
            "source_type": "Excel Tanita MC-580",
            "source_file": os.path.basename(excel_path),
            "full_path": excel_path,
            "measurement_date": None,
            "weight_kg": None,
            "height_cm": None,
            "bmi": None,
            "fat_percent": None,
            "fat_mass_kg": None,
            "ffm_kg": None,
            "ffm_percent": None,
            "muscle_mass_kg": None,
            "water_percent": None,
            "bone_mass_kg": None,
            "visceral_fat": None,
            "bmr_dietowin": None,
            "bmr_cunningham": None,
            "metabolic_age": None,
            "segmental": {}
        }

        m_fn_date = re.search(r'(\d{2})(\d{2})(\d{4})', os.path.basename(excel_path))
        if m_fn_date:
            data["measurement_date"] = f"{m_fn_date.group(3)}-{m_fn_date.group(2)}-{m_fn_date.group(1)}"

        for row in ws.iter_rows(values_only=True):
            row_str = " ".join(str(c) for c in row if c is not None)
            rl = normalize_text(row_str)

            if 'peso' in rl and 'kg' in rl:
                m = re.search(r'(\d+(?:[.,]\d+)?)\s*kg', row_str, re.IGNORECASE)
                if m: data["weight_kg"] = float(m.group(1).replace(',', '.'))
            if 'grasa corporal' in rl and '%' in row_str:
                m = re.search(r'(\d+(?:[.,]\d+)?)\s*%', row_str)
                if m: data["fat_percent"] = float(m.group(1).replace(',', '.'))
            if 'masa muscular' in rl:
                m = re.search(r'(\d+(?:[.,]\d+)?)\s*kg', row_str, re.IGNORECASE) or re.search(r'(\d+(?:[.,]\d+)?)', row_str.split(',')[-1])
                if m: data["muscle_mass_kg"] = float(m.group(1).replace(',', '.'))
            if 'agua corporal' in rl and '%' in row_str:
                m = re.search(r'(\d+(?:[.,]\d+)?)\s*%', row_str)
                if m: data["water_percent"] = float(m.group(1).replace(',', '.'))
            if 'masa' in rl and 'sea' in rl:
                m = re.search(r'(\d+(?:[.,]\d+)?)\s*kg', row_str, re.IGNORECASE)
                if m: data["bone_mass_kg"] = float(m.group(1).replace(',', '.'))
            if 'grasa visceral' in rl:
                m = re.search(r'(\d+(?:[.,]\d+)?)', row_str.split(',')[-1])
                if m: data["visceral_fat"] = float(m.group(1).replace(',', '.'))
            if 'bmr' in rl and 'kcal' in rl:
                m = re.search(r'(\d+)\s*kcal', row_str, re.IGNORECASE)
                if m: data["bmr_dietowin"] = int(m.group(1))
            if 'edad metab' in rl:
                m = re.search(r'(\d+)\s*a[ñn]os', row_str, re.IGNORECASE)
                if m: data["metabolic_age"] = int(m.group(1))
            if 'imc' in rl:
                m = re.search(r'(\d+(?:[.,]\d+)?)', row_str.split(',')[-1])
                if m: data["bmi"] = float(m.group(1).replace(',', '.'))

        if data["weight_kg"] and data["fat_percent"]:
            data["fat_mass_kg"] = round(data["weight_kg"] * (data["fat_percent"] / 100.0), 1)
            data["ffm_kg"] = round(data["weight_kg"] - data["fat_mass_kg"], 1)
            data["bmr_cunningham"] = round(500 + 22 * data["ffm_kg"])

        return data if data.get("weight_kg") else None
    except Exception as e:
        print(f"Error procesando Excel Tanita {excel_path}: {e}")
        return None

def extract_composition_from_docx(docx_path: str) -> Optional[Dict[str, Any]]:
    """Extrae datos antropométricos y clínicos desde cuestionarios de consulta (.docx)."""
    try:
        import docx
        doc = docx.Document(docx_path)
        full_text = "\n".join([p.text for p in doc.paragraphs] + [
            " ".join([c.text for c in row.cells]) for table in doc.tables for row in table.rows
        ])
        
        m_peso = re.search(r'Peso:\s*(\d+(?:[.,]\d+)?)', full_text, re.IGNORECASE)
        m_altura = re.search(r'Altura:\s*(\d+(?:[.,]\d+)?)', full_text, re.IGNORECASE)
        m_edad = re.search(r'Edad:\s*(\d+)', full_text, re.IGNORECASE)
        m_deporte = re.search(r'Deporte:\s*([^\n\r]+)', full_text, re.IGNORECASE)
        m_fecha = re.search(r'Fecha\s*(?:cuestionario|consulta)?:\s*(\d{2}/\d{2}/\d{4})', full_text, re.IGNORECASE)
        
        if not m_peso:
            return None
            
        weight = float(m_peso.group(1).replace(',', '.'))
        height = float(m_altura.group(1).replace(',', '.')) if m_altura else None
        
        # Estimación conservadora si es registro inicial sin bioimpedancia directa
        # Para mujer atlética (~21% grasa) / hombre atlético (~14% grasa)
        fat_est = 20.0
        fat_mass = round(weight * (fat_est / 100.0), 1)
        ffm = round(weight - fat_mass, 1)
        muscle_est = round(ffm * 0.94, 1)
        cunningham = round(500 + 22 * ffm)
        
        meas_date = None
        if m_fecha:
            try:
                meas_date = datetime.strptime(m_fecha.group(1), "%d/%m/%Y").strftime("%Y-%m-%d")
            except:
                meas_date = m_fecha.group(1)
        else:
            meas_date = datetime.fromtimestamp(os.path.getmtime(docx_path)).strftime("%Y-%m-%d")
            
        return {
            "source_type": "Ficha de Consulta / Anamnesis ANyD (.docx)",
            "source_file": os.path.basename(docx_path),
            "full_path": docx_path,
            "measurement_date": meas_date,
            "weight_kg": weight,
            "height_cm": height,
            "bmi": round(weight / ((height/100.0)**2), 1) if height else None,
            "fat_percent": fat_est,
            "fat_mass_kg": fat_mass,
            "ffm_kg": ffm,
            "muscle_mass_kg": muscle_est,
            "water_percent": 58.0,
            "bone_mass_kg": 2.5,
            "visceral_fat": 2,
            "bmr_cunningham": cunningham,
            "metabolic_age": int(m_edad.group(1)) if m_edad else None,
            "sport_discipline": m_deporte.group(1).strip() if m_deporte else None,
            "is_anamnesis_estimate": True
        }
    except Exception as e:
        print(f"Error extrayendo de docx {docx_path}: {e}")
        return None

def scan_client_dietowin_profile(client_name: str) -> Dict[str, Any]:
    """
    Escanea y recupera la ficha completa del cliente en Dietowin y su última composición corporal.
    Busca de forma inteligente en:
    1. Carpeta de Google Drive del paciente (PDFs de Composición Corporal, Excels de Tanita y Docx de Consulta).
    2. Tabla interna SQLite tanita_measurements y athlete_profiles.
    3. Archivos Dietowin en C:\\SuiteBiológica11 (DietaWeb y Datos).
    """
    result = {
        "client_name": client_name,
        "found": False,
        "matched_folder": None,
        "composition": None,
        "dietowin_history": [],
        "source": None
    }

    aliases = get_client_aliases(client_name)
    folder = find_athlete_drive_folder(client_name)
    result["matched_folder"] = folder

    candidates_compo = []
    diet_history = []

    # 1. Escanear carpeta de Google Drive
    if folder and os.path.exists(folder):
        try:
            for root, dirs, files in os.walk(folder):
                for f in files:
                    f_lower = f.lower()
                    f_norm = normalize_text(f)
                    full_p = os.path.join(root, f)

                    # A. Informes de composición corporal en PDF
                    if f_lower.endswith(".pdf") and any(k in f_norm for k in ["composicion", "bioimpedancia", "tanita", "antropometria"]):
                        compo = extract_composition_from_pdf(full_p)
                        if compo and compo.get("weight_kg"):
                            candidates_compo.append(compo)

                    # B. Archivos Tanita Excel
                    elif any(k in f_norm for k in ["tanita", "bioimpedancia", "composicion", "antropometria"]) and (f_lower.endswith(".xlsx") or f_lower.endswith(".xlsm") or not os.path.splitext(f)[1]):
                        compo = extract_composition_from_excel(full_p)
                        if compo and compo.get("weight_kg"):
                            candidates_compo.append(compo)

                    # C. Cuestionario de consulta .docx
                    elif f_lower.endswith(".docx") and any(k in f_norm for k in ["consulta", "anamnesis", "cuestionario", "recordatorio"]):
                        compo = extract_composition_from_docx(full_p)
                        if compo and compo.get("weight_kg"):
                            candidates_compo.append(compo)

                    # D. Historial de dietas / patrones Dietowin exportados
                    if f_lower.endswith(".pdf") and any(k in f_norm for k in ["patron", "dieta", "adaptacion", "planificacion"]):
                        m_date = re.search(r'(\d{2})[-_](\d{2})[-_](\d{4})', f)
                        d_str = f"{m_date.group(1)}/{m_date.group(2)}/{m_date.group(3)}" if m_date else ""
                        diet_history.append({
                            "title": f.replace(".PDF", "").replace(".pdf", ""),
                            "date": d_str,
                            "file": f,
                            "type": "PDF Exportado"
                        })
        except Exception as e:
            print(f"Error escaneando Drive para {client_name}: {e}")

    # 2. Comprobar archivos Dietowin en C:\SuiteBiológica11\DietaWeb
    dietaweb_dir = os.path.join(SUITE_DIR, "DietaWeb")
    if os.path.exists(dietaweb_dir):
        all_tokens = set()
        for a in aliases:
            for t in normalize_text(a).split():
                if len(t) >= 4:
                    all_tokens.add(t)
        try:
            for f in os.listdir(dietaweb_dir):
                if f.endswith(".DW11W"):
                    fp = os.path.join(dietaweb_dir, f)
                    try:
                        with open(fp, "rb") as d_fp:
                            head = d_fp.read(600).decode("latin1", errors="replace")
                            head_norm = normalize_text(head)
                            if any(tok in head_norm for tok in all_tokens):
                                m_nom = re.search(r'NombrePaciente=(.+)', head)
                                patient_nom = m_nom.group(1).strip() if m_nom else f
                                m_tit = re.search(r'Titulo=(.+)', head)
                                diet_tit = m_tit.group(1).strip() if m_tit else "Patrón Dietowin"
                                m_fec = re.search(r'FechaInicio=(\d+)', head)
                                diet_history.append({
                                    "title": f"{diet_tit} ({f.split('_')[-1].replace('.DW11W','')})",
                                    "patient": patient_nom,
                                    "file": f,
                                    "type": "Dietowin DietaWeb (DW11W)"
                                })
                    except:
                        pass
        except Exception as e:
            print(f"Error comprobando DietaWeb: {e}")

    # 3. Comprobar base de datos SQLite tanita_measurements
    try:
        conn = get_db()
        cursor = conn.cursor()
        for a in aliases:
            norm_a = normalize_text(a)
            cursor.execute("""
            SELECT weight, ffm, fat_percent, fat_mass, muscle_mass, water_percent, bone_mass, visceral_fat, bmr_cunningham, measurement_date
            FROM tanita_measurements
            WHERE LOWER(client_name) LIKE ? OR LOWER(client_name) = ?
            ORDER BY measurement_date DESC, id DESC LIMIT 1
            """, (f"%{norm_a}%", norm_a))
            db_tanita = cursor.fetchone()
            if db_tanita:
                db_compo = {
                    "source_type": "Báscula Tanita MC-580 (Registro Consulta)",
                    "source_file": "anyd_booking.db",
                    "measurement_date": db_tanita["measurement_date"],
                    "weight_kg": db_tanita["weight"],
                    "fat_percent": db_tanita["fat_percent"],
                    "fat_mass_kg": db_tanita["fat_mass"],
                    "ffm_kg": db_tanita["ffm"],
                    "muscle_mass_kg": db_tanita["muscle_mass"],
                    "water_percent": db_tanita["water_percent"],
                    "bone_mass_kg": db_tanita["bone_mass"],
                    "visceral_fat": db_tanita["visceral_fat"],
                    "bmr_cunningham": db_tanita["bmr_cunningham"] or (round(500 + 22 * db_tanita["ffm"]) if db_tanita["ffm"] else None)
                }
                candidates_compo.append(db_compo)
                break
        conn.close()
    except Exception as e:
        print(f"Error consultando DB tanita_measurements: {e}")

    # Ordenar candidatos por prioridad de fuente y fecha más reciente
    def sort_key(c):
        score = 0
        st = c.get("source_type", "")
        if "Dietowin PDF" in st: score += 50
        elif "Tanita" in st: score += 40
        elif "Consulta" in st: score += 20
        d = str(c.get("measurement_date") or "2000-01-01")
        return (score, d)

    candidates_compo.sort(key=sort_key, reverse=True)

    if candidates_compo:
        result["composition"] = candidates_compo[0]
        result["found"] = True
        result["source"] = result["composition"].get("source_type", "Composición Corporal")
        # Auto-guardar en la base de datos de mediciones si proviene de un archivo externo
        if "Registro Consulta" not in result["source"]:
            save_dietowin_composition_to_db(client_name, result["composition"])
    
    result["dietowin_history"] = diet_history[:15]
    return result

def save_dietowin_composition_to_db(client_name: str, compo: Dict[str, Any]) -> bool:
    """Guarda o actualiza la composición corporal en la base de datos tanita_measurements en ambas BDs."""
    try:
        norm_c = normalize_text(client_name)
        weight = float(compo.get("weight_kg") or compo.get("weight") or 70.0)
        fat_pct = float(compo.get("fat_percent") or 15.0)
        ffm = float(compo.get("ffm_kg") or compo.get("ffm") or round(weight * (1.0 - fat_pct/100.0), 1))
        muscle = float(compo.get("muscle_mass_kg") or compo.get("muscle_mass") or round(ffm * 0.94, 1))
        fat_mass = float(compo.get("fat_mass_kg") or compo.get("fat_mass") or round(weight * (fat_pct/100.0), 1))
        water = float(compo.get("water_percent") or 60.0)
        bone = float(compo.get("bone_mass_kg") or compo.get("bone_mass") or 2.8)
        visceral = float(compo.get("visceral_fat") or 2.0)
        bmr_cunningham = round(500 + 22 * ffm)
        meas_date = str(compo.get("measurement_date") or datetime.now().strftime("%Y-%m-%d"))

        for db_file in [os.path.join(BASE_DIR, "anyd_booking.db"), os.path.join(BASE_DIR, "anyd_booking_test.db")]:
            if not os.path.exists(db_file):
                continue
            try:
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                cursor.execute("SELECT id, fullname FROM clients WHERE LOWER(fullname) LIKE ? OR LOWER(firstname) LIKE ? LIMIT 1",
                               (f"%{norm_c}%", f"%{norm_c}%"))
                c_row = cursor.fetchone()
                client_id = c_row[0] if c_row else None
                official_name = c_row[1] if c_row else client_name

                # Evitar registros duplicados para la misma fecha y paciente
                cursor.execute("SELECT id FROM tanita_measurements WHERE (client_id = ? OR client_name = ?) AND measurement_date = ?",
                               (client_id, official_name, meas_date))
                existing = cursor.fetchone()
                if not existing:
                    cursor.execute("""
                        INSERT INTO tanita_measurements (
                            client_id, client_name, measurement_date, weight, bmi, fat_percent, fat_mass,
                            muscle_mass, ffm, water_percent, bone_mass, visceral_fat, bmr_cunningham, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        client_id, official_name, meas_date, weight, round(weight / (1.75**2), 1), fat_pct, fat_mass,
                        muscle, ffm, water, bone, visceral, bmr_cunningham, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))
                    conn.commit()
                conn.close()
            except Exception:
                pass
        return True
    except Exception as e:
        print(f"Error guardando composición en DB: {e}")
        return False
        print(f"Error guardando composición en base de datos: {e}")
        return False


# =====================================================================
# INTEGRACIÓN AUTÓNOMA DIETOWIN: CARGA DE PATRONES Y NOTAS PARTICULARES
# =====================================================================

def find_latest_dw11w_file(client_name: str) -> Optional[Dict[str, Any]]:
    """Localiza el archivo de patrón .DW11W más reciente de este paciente en C:\\SuiteBiológica11\\DietaWeb."""
    dietaweb_dir = os.path.join(SUITE_DIR, "DietaWeb")
    if not os.path.exists(dietaweb_dir):
        return None
        
    norm_target = normalize_text(client_name)
    aliases = get_client_aliases(client_name)
    all_names = [client_name] + aliases
    norm_aliases = [normalize_text(a) for a in all_names if normalize_text(a)]
    
    target_tokens = set()
    for na in norm_aliases:
        for t in na.split():
            if len(t) >= 3:
                target_tokens.add(t)

    # Detectar si hay un IDPaciente activo en Suite11.INI
    active_patient_id = None
    ini_path = os.path.join(SUITE_DIR, "Suite11.INI")
    if os.path.exists(ini_path):
        try:
            with open(ini_path, "r", encoding="latin1") as f:
                for line in f:
                    if line.startswith("IDPaciente="):
                        active_patient_id = line.strip().split("=", 1)[1]
                        break
        except Exception:
            pass

    import glob
    files = glob.glob(os.path.join(dietaweb_dir, "*.DW11W"))
    matches = []
    
    for f in files:
        # Descartar archivos vacíos (0 bytes)
        try:
            if os.path.getsize(f) == 0:
                continue
        except Exception:
            continue

        try:
            fname = os.path.basename(f)
            with open(f, 'rb') as fp:
                head = fp.read(1500).decode('latin1', errors='replace')
                m_nom = re.search(r'NombrePaciente=(.+)', head)
                m_tit = re.search(r'Titulo=(.+)', head)
                patient_name = m_nom.group(1).strip() if m_nom else ""
                title = m_tit.group(1).strip() if m_tit else fname
                
                norm_p = normalize_text(patient_name)
                if not norm_p or len(norm_p) < 2:
                    continue

                p_toks = set([t for t in norm_p.split() if len(t) >= 3])
                common = target_tokens.intersection(p_toks)
                score = 0

                # 1. Coincidencia exacta con ID de paciente activo en Dietowin
                if active_patient_id and fname.startswith(f"{active_patient_id}_"):
                    if any(tok in norm_p for tok in target_tokens):
                        score = 110

                # 2. Coincidencia exacta con el nombre o cualquier alias
                if score == 0:
                    if any(norm_p == na for na in norm_aliases):
                        score = 100
                    elif any(len(na) >= 4 and (na in norm_p or norm_p in na) for na in norm_aliases):
                        score = 85
                    elif len(common) >= 2:
                        score = 60 + len(common) * 10
                    elif len(common) == 1 and len(list(common)[0]) >= 4:
                        score = 45

                # 3. Ponderación por nombre de pila para evitar falsos positivos familiares (ej: Ivan vs Carol)
                if score > 0:
                    q_first = norm_target.split()[0] if norm_target else ""
                    p_first = norm_p.split()[0] if norm_p else ""
                    if q_first and p_first:
                        if p_first.startswith(q_first) or q_first.startswith(p_first):
                            score += 40
                        elif len(q_first) >= 4 and q_first not in norm_p:
                            score -= 60

                if score > 0:
                    mtime = os.path.getmtime(f)
                    matches.append((score, mtime, f, patient_name, title))
        except Exception:
            pass
            
    if not matches:
        return None
        
    matches.sort(key=lambda x: (x[0], x[1]), reverse=True)
    best = matches[0]
    return {
        "file_path": best[2],
        "patient_name": best[3],
        "title": best[4],
        "mtime": best[1],
        "date_str": datetime.fromtimestamp(best[1]).strftime("%Y-%m-%d")
    }

def lookup_item_macros(name: str, conn) -> Dict[str, Any]:
    """Busca macros de una receta o alimento de Dietowin en la base de datos oficial."""
    clean_name = re.sub(r'^\d+\s*g\.?\s*(?:de\s*)?', '', name, flags=re.IGNORECASE).strip()
    m_g = re.search(r'^(\d+)\s*g', name, re.IGNORECASE)
    grams = float(m_g.group(1)) if m_g else 100.0
    
    c = conn.cursor()
    # 1. Buscar en diet_recipes
    c.execute("SELECT id, nombre, kcal, proteina_g, carbohidratos_g, grasa_g FROM diet_recipes WHERE LOWER(nombre) = ? OR LOWER(nombre) LIKE ? LIMIT 1",
              (clean_name.lower(), f"%{clean_name.lower()}%"))
    r = c.fetchone()
    if r:
        return {
            "nombre": r["nombre"],
            "kcal": float(r["kcal"] or 0),
            "proteina_g": float(r["proteina_g"] or 0),
            "carbohidratos_g": float(r["carbohidratos_g"] or 0),
            "grasa_g": float(r["grasa_g"] or 0),
            "grams": grams,
            "tipo": "recipe"
        }
        
    # 2. Buscar en diet_foods
    c.execute("SELECT id, nombre, kcal, proteina_g, carbohidratos_g, grasa_g FROM diet_foods WHERE LOWER(nombre) = ? OR LOWER(nombre) LIKE ? LIMIT 1",
              (clean_name.lower(), f"%{clean_name.lower()}%"))
    f = c.fetchone()
    if f:
        mult = grams / 100.0
        return {
            "nombre": f["nombre"],
            "kcal": round(float(f["kcal"] or 0) * mult, 1),
            "proteina_g": round(float(f["proteina_g"] or 0) * mult, 1),
            "carbohidratos_g": round(float(f["carbohidratos_g"] or 0) * mult, 1),
            "grasa_g": round(float(f["grasa_g"] or 0) * mult, 1),
            "grams": grams,
            "tipo": "food"
        }
        
    # 3. Estimación por defecto
    return {
        "nombre": name,
        "kcal": round(grams * 1.5, 1),
        "proteina_g": round(grams * 0.08, 1),
        "carbohidratos_g": round(grams * 0.20, 1),
        "grasa_g": round(grams * 0.04, 1),
        "grams": grams,
        "tipo": "food"
    }

def parse_latest_dw11w_for_client(client_name: str) -> Optional[Dict[str, Any]]:
    """Parsea el último patrón .DW11W del paciente y lo convierte a estructura semanal del agente."""
    latest = find_latest_dw11w_file(client_name)
    if not latest:
        return None
        
    conn = get_db()
    try:
        with open(latest["file_path"], 'rb') as fp:
            lines = fp.read().decode('latin1', errors='replace').splitlines()
            
        days_map = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
        week_state = {
            d: {
                "workouts": [], "suplementacion": [], "desayuno": [], "media_manana": [],
                "almuerzo": [], "merienda": [], "cena": [], "recena": []
            } for d in days_map.values()
        }
        
        consejos = []
        raw_days = {}
        has_recena = False
        
        for line in lines:
            line = line.strip()
            if not line or '=' not in line: continue
            k, v = line.split('=', 1)
            k, v = k.strip(), v.strip()
            
            m_h = re.match(r'^Hora:(\d+):(\d+)$', k)
            if m_h:
                d_idx, m_idx = int(m_h.group(1)), int(m_h.group(2))
                raw_days.setdefault(d_idx, {}).setdefault(m_idx, {})["hora"] = v
                continue
            m_r = re.match(r'^Receta:(\d+):(\d+)$', k)
            if m_r:
                d_idx, m_idx = int(m_r.group(1)), int(m_r.group(2))
                raw_days.setdefault(d_idx, {}).setdefault(m_idx, {})["receta"] = v
                continue
            m_i = re.match(r'^Ingredientes:(\d+):(\d+)$', k)
            if m_i:
                d_idx, m_idx = int(m_i.group(1)), int(m_i.group(2))
                raw_days.setdefault(d_idx, {}).setdefault(m_idx, {})["ingredientes"] = v.replace('<b>Ingredientes: </b>', '').strip()
                continue
            m_e = re.match(r'^Elaboracion:(\d+):(\d+)$', k)
            if m_e:
                d_idx, m_idx = int(m_e.group(1)), int(m_e.group(2))
                raw_days.setdefault(d_idx, {}).setdefault(m_idx, {})["elaboracion"] = v.replace('Elaboración: ', '').strip()
                continue
            if k.startswith('Consejo:') and v and v != 'Fin' and not k.endswith('Filename'):
                consejos.append(v)
                
        for d_idx, day_name in days_map.items():
            items = raw_days.get(d_idx, {})
            for m_idx in sorted(items.keys()):
                it = items[m_idx]
                hora_raw = it.get("hora", "").strip()
                receta_raw = it.get("receta", "").strip()
                if not receta_raw or receta_raw == '(sin receta)':
                    continue
                    
                hl = hora_raw.lower()
                if 'desayuno' in hl:
                    slot = 'desayuno'
                elif 'media ma' in hl or 'tentemp' in hl:
                    slot = 'media_manana'
                elif 'almuerzo' in hl or 'comida' in hl:
                    slot = 'almuerzo'
                elif 'merienda' in hl:
                    slot = 'merienda'
                elif 'cena' in hl:
                    slot = 'cena'
                elif 'recena' in hl:
                    slot = 'recena'
                    has_recena = True
                elif 'suplement' in hl:
                    slot = 'suplementacion'
                elif 'entren' in hl or 'pesas' in hl or 'cf' in hl or 'tkd' in hl or 'carrera' in hl:
                    rl = receta_raw.lower()
                    if any(s in rl for s in ['taekwondo', 'fuerza', 'crossfit', 'carrera', 'rodaje', 'entrenamiento', 'pesas', 'wod', 'series', 'haltero']):
                        m_time = re.search(r'(\d{1,2}:\d{2})', hora_raw)
                        st_time = m_time.group(1) if m_time else ("09:00" if "mañana" in hl else "18:30")
                        if len(st_time) == 4: st_time = "0" + st_time
                        
                        # Evitar duplicados idénticos a la misma hora
                        w_list = week_state[day_name]["workouts"]
                        if not any(w["sport"] == receta_raw and w["start_time"] == st_time for w in w_list):
                            w_list.append({
                                "sport": receta_raw,
                                "start_time": st_time,
                                "duration_min": 75,
                                "intensity": "Alta",
                                "nutrition": {
                                    "intra": {"fluid_ml_h": 600, "sodium_mg_h": 450}
                                }
                            })
                        continue
                    else:
                        slot = 'merienda'
                else:
                    slot = 'almuerzo'
                    
                food_obj = lookup_item_macros(receta_raw, conn)
                if it.get("ingredientes"): food_obj["ingredientes"] = it["ingredientes"]
                if it.get("elaboracion"): food_obj["elaboracion"] = it["elaboracion"]
                week_state[day_name][slot].append(food_obj)
                
        # Estructura de slots recomendada
        active_slots = [
            {"id": "slot_suplementacion", "key": "suplementacion", "label": "Suplementación", "icon": "💊", "time": "08:00", "defaultTime": "08:00", "type": "food"},
            {"id": "slot_desayuno", "key": "desayuno", "label": "Desayuno", "icon": "🌅", "time": "08:30", "defaultTime": "08:30", "type": "food"},
            {"id": "slot_media_manana", "key": "media_manana", "label": "Media mañana", "icon": "🥪", "time": "11:30", "defaultTime": "11:30", "type": "food"},
            {"id": "slot_almuerzo", "key": "almuerzo", "label": "Almuerzo", "icon": "🍲", "time": "14:30", "defaultTime": "14:30", "type": "food"},
            {"id": "slot_merienda", "key": "merienda", "label": "Media tarde", "icon": "☕", "time": "18:00", "defaultTime": "18:00", "type": "food"},
            {"id": "slot_entrenamiento", "key": "entrenamiento", "label": "Entrenamiento", "icon": "🏃", "time": "18:30", "defaultTime": "18:30", "type": "workout"},
            {"id": "slot_cena", "key": "cena", "label": "Cena", "icon": "🥗", "time": "21:30", "defaultTime": "21:30", "type": "food"}
        ]
        if has_recena:
            active_slots.append({
                "id": "slot_recena", "key": "recena", "label": "Recena", "icon": "🥛", "time": "23:00", "defaultTime": "23:00", "type": "food", "isCustom": True
            })
            
        plan_result = {
            "found": True,
            "patient_name": latest["patient_name"],
            "title": latest["title"],
            "file": os.path.basename(latest["file_path"]),
            "date_str": latest["date_str"],
            "mtime": latest["mtime"],
            "consejos": consejos,
            "weekly_data": week_state,
            "active_slots": active_slots
        }

        # Auto-guardar en la tabla diet_plans para que esté disponible en el historial
        try:
            norm_name = normalize_text(client_name)
            c.execute("SELECT id, fullname FROM clients WHERE LOWER(fullname) LIKE ? OR LOWER(firstname) LIKE ? LIMIT 1",
                      (f"%{norm_name}%", f"%{norm_name}%"))
            c_row = c.fetchone()
            cid = c_row["id"] if c_row else None
            cname = c_row["fullname"] if c_row else client_name

            for db_file in [os.path.join(BASE_DIR, "anyd_booking.db"), os.path.join(BASE_DIR, "anyd_booking_test.db")]:
                if os.path.exists(db_file):
                    try:
                        c_db = sqlite3.connect(db_file)
                        cur_db = c_db.cursor()
                        cur_db.execute("SELECT id FROM diet_plans WHERE client_id = ? AND plan_name = ?", (cid, latest["title"]))
                        if not cur_db.fetchone():
                            cur_db.execute("""
                                INSERT INTO diet_plans (client_id, client_name, plan_name, weekly_data_json, notes, created_at)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (cid, cname, latest["title"], json.dumps(week_state), os.path.basename(latest["file_path"]), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                            c_db.commit()
                        c_db.close()
                    except Exception:
                        pass
        except Exception:
            pass

        return plan_result
    finally:
        conn.close()

def get_client_particular_notes(client_name: str) -> Dict[str, Any]:
    """Agrega todas las notas particulares y clínicas del paciente (Dietowin, CRM, evolución médica y Drive)."""
    notes = {
        "client_name": client_name,
        "crm_note": "",
        "dietowin_consejos": [],
        "clinical_evolution": [],
        "allergies": "",
        "pathologies": "",
        "digestive_issues": "",
        "profile_notes": "",
        "anamnesis_docx_summary": ""
    }
    
    conn = get_db()
    c = conn.cursor()
    
    # 1. Notas del CRM y ficha de atleta
    c.execute("SELECT id, fullname, note FROM clients WHERE LOWER(fullname) LIKE ? OR LOWER(fullname) = ? LIMIT 1",
              (f"%{normalize_text(client_name)}%", normalize_text(client_name)))
    client_row = c.fetchone()
    if client_row:
        notes["crm_note"] = client_row["note"] or ""
        client_id = client_row["id"]
        
        c.execute("SELECT allergies, pathologies, digestive_issues, notes FROM athlete_profiles WHERE client_id = ?", (client_id,))
        p_row = c.fetchone()
        if p_row:
            notes["allergies"] = p_row["allergies"] or ""
            notes["pathologies"] = p_row["pathologies"] or ""
            notes["digestive_issues"] = p_row["digestive_issues"] or ""
            notes["profile_notes"] = p_row["notes"] or ""
            
        c.execute("""
            SELECT session_date, session_type, subjective, objective, assessment, plan, private_notes
            FROM clinical_notes WHERE client_id = ?
            ORDER BY session_date DESC, id DESC LIMIT 5
        """, (client_id,))
        for cn in c.fetchall():
            notes["clinical_evolution"].append({
                "date": cn["session_date"],
                "type": cn["session_type"] or "Consulta",
                "private_notes": cn["private_notes"] or "",
                "subjective": cn["subjective"] or "",
                "plan": cn["plan"] or ""
            })
            
    conn.close()
    
    # 2. Consejos particulares de Dietowin desde el último .DW11W
    dw_plan = parse_latest_dw11w_for_client(client_name)
    if dw_plan and dw_plan.get("consejos"):
        notes["dietowin_consejos"] = dw_plan["consejos"]
        notes["dietowin_plan_title"] = dw_plan.get("title")
        notes["dietowin_plan_date"] = dw_plan.get("date_str")
        
    # 3. Resumen de Anamnesis / Cuestionario docx en Drive
    folder = find_athlete_drive_folder(client_name)
    if folder and os.path.exists(folder):
        for f in os.listdir(folder):
            if f.lower().endswith(".docx") and any(k in f.lower() for k in ["consulta", "anamnesis", "recordatorio"]):
                try:
                    import docx
                    doc = docx.Document(os.path.join(folder, f))
                    summary_lines = []
                    for p in doc.paragraphs:
                        txt = p.text.strip()
                        if txt and any(k in txt.lower() for k in ["objetivo", "deporte", "alergia", "intolerancia", "horario", "observaci", "suplement", "gustos"]):
                            summary_lines.append(txt)
                    if summary_lines:
                        notes["anamnesis_docx_summary"] = " | ".join(summary_lines[:6])
                except Exception:
                    pass
                break
                
    return notes

def check_or_register_athlete(client_name: str, phone: str = "", email: str = "", auto_register: bool = True) -> Dict[str, Any]:
    """Comprueba si el paciente existe en el CRM; si no existe, lo da de alta."""
    clean_name = client_name.strip()
    if not clean_name:
        return {"exists": False, "action": "invalid_name", "client": None}
        
    conn = get_db()
    cursor = conn.cursor()
    norm_name = normalize_text(clean_name)
    
    cursor.execute("""
        SELECT id, firstname, lastname, fullname, email, phone, note, created_at, photo_url
        FROM clients
        WHERE LOWER(fullname) = ? OR LOWER(fullname) LIKE ?
        ORDER BY CASE WHEN LOWER(fullname) = ? THEN 1 ELSE 2 END, id DESC LIMIT 1
    """, (norm_name, f"%{norm_name}%", norm_name))
    row = cursor.fetchone()
    
    if row:
        client_data = dict(row)
        conn.close()
        return {
            "exists": True,
            "action": "loaded",
            "client": client_data,
            "message": f"Paciente '{client_data['fullname']}' localizado en el CRM."
        }
        
    if not auto_register:
        conn.close()
        return {
            "exists": False,
            "action": "not_found",
            "client": None,
            "message": f"El paciente '{clean_name}' no existe en el sistema."
        }
        
    parts = clean_name.split(" ", 1)
    fname = parts[0]
    lname = parts[1] if len(parts) > 1 else ""
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("""
        INSERT INTO clients (firstname, lastname, fullname, email, phone, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (fname, lname, clean_name, email or "", phone or "", "Alta automática desde Patrones Nutricionales", created_at))
    client_id = cursor.lastrowid
    
    cursor.execute("""
        INSERT INTO athlete_profiles (client_id, main_goal, notes, updated_at)
        VALUES (?, ?, ?, ?)
    """, (client_id, "Rendimiento Deportivo y Salud", "Alta automática", created_at))
    conn.commit()
    
    cursor.execute("SELECT id, firstname, lastname, fullname, email, phone, note, created_at, photo_url FROM clients WHERE id = ?", (client_id,))
    new_client = dict(cursor.fetchone())
    conn.close()
    
    return {
        "exists": False,
        "action": "registered",
        "client": new_client,
        "message": f"Nuevo paciente '{clean_name}' dado de alta con éxito en el sistema."
    }

def get_athlete_evolution_history(client_name: str) -> Dict[str, Any]:
    """Recupera todo el historial evolutivo de consultas y pesajes con cálculos de deltas y variación."""
    conn = get_db()
    cursor = conn.cursor()
    norm_name = normalize_text(client_name)
    
    cursor.execute("""
        SELECT id, firstname, lastname, fullname FROM clients
        WHERE LOWER(fullname) = ? OR LOWER(fullname) LIKE ?
        ORDER BY CASE WHEN LOWER(fullname) = ? THEN 1 ELSE 2 END, id DESC LIMIT 1
    """, (norm_name, f"%{norm_name}%", norm_name))
    client_row = cursor.fetchone()
    
    client_id = client_row["id"] if client_row else None
    official_name = client_row["fullname"] if client_row else client_name
    
    cursor.execute("""
        SELECT id, measurement_date, weight, bmi, fat_percent, fat_mass, muscle_mass,
               ffm, water_percent, bone_mass, visceral_fat, bmr_cunningham, perimeters_json, created_at
        FROM tanita_measurements
        WHERE (client_id = ? OR LOWER(client_name) LIKE ? OR LOWER(client_name) = ?)
        ORDER BY measurement_date ASC, id ASC
    """, (client_id, f"%{norm_name}%", norm_name))
    rows = cursor.fetchall()
    
    # Si no hay mediciones en la BD para este deportista, escanear activamente Drive y Dietowin
    if not rows:
        conn.close()
        scan_client_dietowin_profile(client_name)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, measurement_date, weight, bmi, fat_percent, fat_mass, muscle_mass,
                   ffm, water_percent, bone_mass, visceral_fat, bmr_cunningham, perimeters_json, created_at
            FROM tanita_measurements
            WHERE (client_id = ? OR LOWER(client_name) LIKE ? OR LOWER(client_name) = ?)
            ORDER BY measurement_date ASC, id ASC
        """, (client_id, f"%{norm_name}%", norm_name))
        rows = cursor.fetchall()

    conn.close()
    
    consultations = []
    prev = None
    
    for r in rows:
        d = dict(r)
        # Parse perimeters if available
        try:
            d["perimeters"] = json.loads(d.get("perimeters_json") or "{}")
        except:
            d["perimeters"] = {}
            
        # Calcular deltas con la consulta anterior
        deltas = {}
        if prev:
            if d.get("weight") and prev.get("weight"):
                deltas["weight"] = round(d["weight"] - prev["weight"], 1)
            if d.get("fat_percent") and prev.get("fat_percent"):
                deltas["fat_percent"] = round(d["fat_percent"] - prev["fat_percent"], 1)
            if d.get("fat_mass") and prev.get("fat_mass"):
                deltas["fat_mass"] = round(d["fat_mass"] - prev["fat_mass"], 1)
            if d.get("muscle_mass") and prev.get("muscle_mass"):
                deltas["muscle_mass"] = round(d["muscle_mass"] - prev["muscle_mass"], 1)
            if d.get("ffm") and prev.get("ffm"):
                deltas["ffm"] = round(d["ffm"] - prev["ffm"], 1)
            if d.get("water_percent") and prev.get("water_percent"):
                deltas["water_percent"] = round(d["water_percent"] - prev["water_percent"], 1)
            if d.get("visceral_fat") and prev.get("visceral_fat"):
                deltas["visceral_fat"] = round(d["visceral_fat"] - prev["visceral_fat"], 1)
        d["deltas"] = deltas
        consultations.append(d)
        prev = d
        
    return {
        "client_name": official_name,
        "client_id": client_id,
        "total_consultations": len(consultations),
        "consultations": consultations,
        "latest": consultations[-1] if consultations else None
    }

def add_consultation_measurement(client_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Registra una nueva consulta/evolutivo para el deportista en tanita_measurements y clinical_notes."""
    conn = get_db()
    cursor = conn.cursor()
    norm_name = normalize_text(client_name)
    
    cursor.execute("""
        SELECT id, fullname FROM clients
        WHERE LOWER(fullname) = ? OR LOWER(fullname) LIKE ?
        ORDER BY CASE WHEN LOWER(fullname) = ? THEN 1 ELSE 2 END, id DESC LIMIT 1
    """, (norm_name, f"%{norm_name}%", norm_name))
    client_row = cursor.fetchone()
    
    if not client_row:
        # Dar de alta al paciente si no existe
        client_id = ensure_client_exists(conn, client_name)
        official_name = client_name
    else:
        client_id = client_row["id"]
        official_name = client_row["fullname"]
        
    meas_date = data.get("measurement_date") or datetime.now().strftime("%Y-%m-%d")
    weight = float(data.get("weight") or 70.0)
    fat_pct = float(data.get("fat_percent") or 15.0)
    fat_mass = float(data.get("fat_mass") or round(weight * (fat_pct / 100.0), 1))
    ffm = float(data.get("ffm") or round(weight - fat_mass, 1))
    muscle = float(data.get("muscle_mass") or round(ffm * 0.94, 1))
    water = float(data.get("water_percent") or 60.0)
    bone = float(data.get("bone_mass") or 2.8)
    visceral = float(data.get("visceral_fat") or 2.0)
    bmr_cunningham = round(500 + 22 * ffm)
    bmi = float(data.get("bmi") or round(weight / (1.75**2), 1))
    
    perims = {
        "cintura_cm": data.get("cintura_cm"),
        "cadera_cm": data.get("cadera_cm"),
        "brazo_cm": data.get("brazo_cm"),
        "muslo_cm": data.get("muslo_cm")
    }
    perims_json = json.dumps({k: v for k, v in perims.items() if v is not None})
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("""
        INSERT INTO tanita_measurements (
            client_id, client_name, measurement_date, weight, bmi, fat_percent, fat_mass,
            muscle_mass, ffm, water_percent, bone_mass, visceral_fat, bmr_cunningham, perimeters_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        client_id, official_name, meas_date, weight, bmi, fat_pct, fat_mass,
        muscle, ffm, water, bone, visceral, bmr_cunningham, perims_json, created_at
    ))
    meas_id = cursor.lastrowid
    
    # Si hay notas de consulta, guardar en clinical_notes
    notes_text = data.get("notes") or ""
    if notes_text:
        cursor.execute("""
            INSERT INTO clinical_notes (
                client_id, session_date, session_type, subjective, objective, private_notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            client_id, meas_date, "Seguimiento Evolutivo", notes_text,
            f"Peso: {weight}kg · FFM: {ffm}kg · Grasa: {fat_pct}% · Músculo: {muscle}kg",
            notes_text, created_at
        ))
        
    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "id": meas_id,
        "client_name": official_name,
        "measurement_date": meas_date,
        "weight": weight,
        "ffm": ffm,
        "bmr_cunningham": bmr_cunningham,
        "message": f"Consulta del día {meas_date} guardada con éxito en el evolutivo."
    }
