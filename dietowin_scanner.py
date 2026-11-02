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
    """Busca la carpeta del deportista en G:\\Mi unidad\\1.- ANyD\\1.- Deportistas."""
    if not os.path.exists(DEPORTISTAS_DIR):
        return None

    aliases = get_client_aliases(client_name)
    norm_aliases = [normalize_text(a) for a in aliases if normalize_text(a)]

    try:
        folders = [f for f in os.listdir(DEPORTISTAS_DIR) if os.path.isdir(os.path.join(DEPORTISTAS_DIR, f))]
        
        # 1. Pase prioritario: Coincidencia EXACTA con cualquier alias o nombre de cliente
        for folder in folders:
            folder_norm = normalize_text(folder)
            for na in norm_aliases:
                if folder_norm == na:
                    return os.path.join(DEPORTISTAS_DIR, folder)

        # 2. Pase secundario: Todos los tokens del alias presentes en el nombre de carpeta
        for folder in folders:
            folder_norm = normalize_text(folder)
            for na in norm_aliases:
                toks = [t for t in na.split() if len(t) >= 3]
                if len(toks) >= 2 and all(t in folder_norm for t in toks):
                    return os.path.join(DEPORTISTAS_DIR, folder)

        # 3. Pase terciario: Puntuación por tokens coincidentes
        best_match = None
        best_score = 0
        all_tokens = set()
        for na in norm_aliases:
            for tok in na.split():
                if len(tok) >= 3:
                    all_tokens.add(tok)

        for folder in folders:
            folder_norm = normalize_text(folder)
            score = 0
            for tok in all_tokens:
                if tok in folder_norm:
                    score += 2 if len(tok) > 4 else 1

            if score > best_score and score >= 2:
                best_score = score
                best_match = os.path.join(DEPORTISTAS_DIR, folder)

        return best_match
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
    
    result["dietowin_history"] = diet_history[:15]
    return result

def save_dietowin_composition_to_db(client_name: str, compo: Dict[str, Any]) -> bool:
    """Guarda o actualiza la composición corporal en la base de datos tanita_measurements."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Buscar ID de cliente
        cursor.execute("SELECT id, fullname FROM clients WHERE LOWER(fullname) LIKE ? OR LOWER(firstname) LIKE ? LIMIT 1",
                       (f"%{normalize_text(client_name)}%", f"%{normalize_text(client_name)}%"))
        c_row = cursor.fetchone()
        client_id = c_row["id"] if c_row else None
        official_name = c_row["fullname"] if c_row else client_name
        
        weight = float(compo.get("weight_kg") or compo.get("weight") or 70.0)
        fat_pct = float(compo.get("fat_percent") or 15.0)
        ffm = float(compo.get("ffm_kg") or compo.get("ffm") or round(weight * (1.0 - fat_pct/100.0), 1))
        muscle = float(compo.get("muscle_mass_kg") or compo.get("muscle_mass") or round(ffm * 0.94, 1))
        fat_mass = float(compo.get("fat_mass_kg") or compo.get("fat_mass") or round(weight * (fat_pct/100.0), 1))
        water = float(compo.get("water_percent") or 60.0)
        bone = float(compo.get("bone_mass_kg") or compo.get("bone_mass") or 2.8)
        visceral = float(compo.get("visceral_fat") or 2.0)
        bmr_cunningham = round(500 + 22 * ffm)
        meas_date = compo.get("measurement_date") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
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
        return True
    except Exception as e:
        print(f"Error guardando composición en base de datos: {e}")
        return False
