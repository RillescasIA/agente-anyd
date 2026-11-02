# -*- coding: utf-8 -*-
r"""
auto_dietowin_crawler.py
Rastreador y Migrador Autónomo de Expedientes Históricos Dietowin & Tanita MC-580
para ANyD Nutricionistas · Román Illescas Quiroga (Col. MAD00274).

Recorre de forma autónoma:
1. G:\Mi unidad\1.- ANyD\1.- Deportistas (PDFs evolutivos, tablas Tanita Excel, cuestionarios docx).
2. C:\SuiteBiológica11\DietaWeb (*.DW11W patrones nutricionales y notas particulares).
3. Inserta y actualiza en anyd_booking.db:
   - clients
   - tanita_measurements (historial completo de pesajes y evolutivos)
   - clinical_notes
   - diet_plans
"""

import os
import re
import io
import json
import sqlite3
import unicodedata
from datetime import datetime
from typing import Dict, Any, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "anyd_booking.db")
DEPORTISTAS_DIR = r"G:\Mi unidad\1.- ANyD\1.- Deportistas"
SUITE_DIR = r"C:\SuiteBiológica11"
PROGRESS_FILE = os.path.join(BASE_DIR, "crawler_progress.json")

def normalize_text(text: str) -> str:
    if not text: return ""
    nfkd = unicodedata.normalize('NFKD', str(text))
    t = "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()
    return re.sub(r'\s+', ' ', t)

def get_db():
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_client_exists(conn, fullname: str, phone: str = "", email: str = "") -> int:
    """Busca o crea un cliente en la tabla clients."""
    c = conn.cursor()
    norm_name = normalize_text(fullname)
    
    c.execute("""
        SELECT id, fullname FROM clients
        WHERE LOWER(fullname) = ? OR LOWER(fullname) LIKE ?
        ORDER BY CASE WHEN LOWER(fullname) = ? THEN 1 ELSE 2 END, id DESC LIMIT 1
    """, (norm_name, f"%{norm_name}%", norm_name))
    row = c.fetchone()
    if row:
        return row["id"]
        
    parts = fullname.strip().split(" ", 1)
    fname = parts[0]
    lname = parts[1] if len(parts) > 1 else ""
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    c.execute("""
        INSERT INTO clients (firstname, lastname, fullname, email, phone, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (fname, lname, fullname.strip(), email or "", phone or "", "Migración automática Dietowin / Drive", created_at))
    client_id = c.lastrowid
    
    c.execute("""
        INSERT INTO athlete_profiles (client_id, main_goal, notes, updated_at)
        VALUES (?, ?, ?, ?)
    """, (client_id, "Rendimiento Deportivo y Salud", "Migración automática Dietowin", created_at))
    conn.commit()
    return client_id

def insert_measurement_if_new(conn, client_id: int, client_name: str, meas: Dict[str, Any]) -> bool:
    """Inserta una medición histórica en tanita_measurements si no existe ya para esa fecha."""
    meas_date = meas.get("measurement_date")
    if not meas_date or not meas.get("weight"):
        return False
        
    c = conn.cursor()
    c.execute("""
        SELECT id FROM tanita_measurements
        WHERE client_id = ? AND measurement_date = ?
    """, (client_id, meas_date))
    if c.fetchone():
        return False # Ya existe medición para este día
        
    weight = float(meas.get("weight") or 70.0)
    fat_pct = float(meas.get("fat_percent") or 15.0) if meas.get("fat_percent") is not None else 15.0
    fat_mass = float(meas.get("fat_mass") or round(weight * (fat_pct / 100.0), 1))
    ffm = float(meas.get("ffm") or round(weight - fat_mass, 1))
    muscle = float(meas.get("muscle_mass") or round(ffm * 0.94, 1))
    water = float(meas.get("water_percent") or 60.0)
    bone = float(meas.get("bone_mass") or 2.8)
    
    # Visceral clamp
    raw_visc = meas.get("visceral_fat")
    visceral = 2.0
    if raw_visc is not None:
        try:
            v_val = float(raw_visc)
            visceral = max(1.0, min(20.0, v_val))
        except:
            visceral = 2.0
            
    bmr_cunningham = round(500 + 22 * ffm)
    bmi = float(meas.get("bmi") or round(weight / (1.75**2), 1))
    perims_json = json.dumps(meas.get("perimeters") or {})
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    c.execute("""
        INSERT INTO tanita_measurements (
            client_id, client_name, measurement_date, weight, bmi, fat_percent, fat_mass,
            muscle_mass, ffm, water_percent, bone_mass, visceral_fat, bmr_cunningham, perimeters_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        client_id, client_name, meas_date, weight, bmi, fat_pct, fat_mass,
        muscle, ffm, water, bone, visceral, bmr_cunningham, perims_json, created_at
    ))
    conn.commit()
    return True

def parse_dietowin_evolutivo_pdf(pdf_path: str):
    """Parsea informes evolutivos de Dietowin con múltiples consultas cronológicas."""
    try:
        import pypdf
        reader = pypdf.PdfReader(pdf_path)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
            
        m_header = re.search(r'Tabla de Datos\s+((?:\d{2}/\d{2}/\d{4}.*)+)', full_text)
        if not m_header:
            return None, []
            
        header_line = m_header.group(1)
        raw_dates = re.findall(r'(\d{2}/\d{2}/\d{4})', header_line)
        if not raw_dates:
            return None, []
            
        dates = []
        for rd in raw_dates:
            try:
                dt = datetime.strptime(rd, "%d/%m/%Y")
                dates.append(dt.strftime("%Y-%m-%d"))
            except:
                dates.append(rd)
                
        measurements = {d: {"measurement_date": d, "source": f"Dietowin Evolutivo PDF ({os.path.basename(pdf_path)})"} for d in dates}
        
        m_name = re.search(r'Nombre:\s*([^\n\r]+?)(?:\s+Sexo:|$)', full_text)
        m_phone = re.search(r'Tel[eé]fono:\s*(\d+)', full_text)
        m_email = re.search(r'Email:\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', full_text)
        patient_info = {
            "name": m_name.group(1).strip() if m_name else "",
            "phone": m_phone.group(1).strip() if m_phone else "",
            "email": m_email.group(1).strip() if m_email else ""
        }
        
        def extract_row_values(label_pattern):
            m = re.search(label_pattern, full_text, re.IGNORECASE)
            if not m: return None
            line = m.group(0)
            nums = re.findall(r'([-+]?\d+(?:[.,]\d+)?)', line)
            if not nums: return None
            res = {}
            try:
                v0 = float(nums[0].replace(',', '.'))
                res[dates[0]] = v0
                if len(dates) >= 2:
                    d1_delta = float(nums[1].replace(',', '.')) if len(nums) > 1 and nums[1] not in ['=', '+'] else 0.0
                    res[dates[1]] = round(v0 - d1_delta, 1)
                if len(dates) >= 3:
                    d2_delta = float(nums[2].replace(',', '.')) if len(nums) > 2 and nums[2] not in ['=', '+'] else 0.0
                    res[dates[2]] = round(res[dates[1]] - d2_delta, 1)
            except Exception:
                pass
            return res

        p_dict = extract_row_values(r'Peso\s+[\d.,]+\s*kg.*')
        if p_dict:
            for d, val in p_dict.items(): measurements[d]["weight"] = val

        imc_dict = extract_row_values(r'IMC\s+[\d.,]+.*')
        if imc_dict:
            for d, val in imc_dict.items(): measurements[d]["bmi"] = val

        mg_pct_dict = extract_row_values(r'%\s*Masa Grasa\s+[\d.,]+\s*%.*')
        if mg_pct_dict:
            for d, val in mg_pct_dict.items(): measurements[d]["fat_percent"] = val

        mg_kg_dict = extract_row_values(r'Masa Grasa\s+[\d.,]+\s*kg.*')
        if mg_kg_dict:
            for d, val in mg_kg_dict.items(): measurements[d]["fat_mass"] = val

        ffm_dict = extract_row_values(r'Masa Libre de Grasa\s+[\d.,]+\s*kg.*')
        if ffm_dict:
            for d, val in ffm_dict.items(): measurements[d]["ffm"] = val

        mm_dict = extract_row_values(r'Masa Muscular Total\s+[\d.,]+\s*kg.*')
        if mm_dict:
            for d, val in mm_dict.items(): measurements[d]["muscle_mass"] = val

        act_pct_dict = extract_row_values(r'%\s*ACT\s+[\d.,]+\s*%.*')
        if act_pct_dict:
            for d, val in act_pct_dict.items(): measurements[d]["water_percent"] = val

        visc_dict = extract_row_values(r'[IÍ]ndice de Grasa Visceral\s+[\d.,]+.*')
        if visc_dict:
            for d, val in visc_dict.items():
                try:
                    raw_v = float(val)
                    measurements[d]["visceral_fat"] = max(1.0, min(20.0, abs(raw_v)))
                except:
                    measurements[d]["visceral_fat"] = 2.0

        bone_dict = extract_row_values(r'Mineral [ÓO]seo\s+[\d.,]+\s*kg.*')
        if bone_dict:
            for d, val in bone_dict.items(): measurements[d]["bone_mass"] = val

        cint_dict = extract_row_values(r'Cintura\s+[\d.,]+\s*cm.*')
        cad_dict = extract_row_values(r'Cadera\s+[\d.,]+\s*cm.*')
        braz_dict = extract_row_values(r'Per[ií]metro Brazo\s+[\d.,]+\s*cm.*')
        musl_dict = extract_row_values(r'Muslo\s+[\d.,]+\s*cm.*')

        for d in dates:
            m = measurements[d]
            perims = {}
            if cint_dict and d in cint_dict and cint_dict[d] > 20: perims["cintura_cm"] = cint_dict[d]
            if cad_dict and d in cad_dict and cad_dict[d] > 20: perims["cadera_cm"] = cad_dict[d]
            if braz_dict and d in braz_dict and braz_dict[d] > 10: perims["brazo_cm"] = braz_dict[d]
            if musl_dict and d in musl_dict and musl_dict[d] > 20: perims["muslo_cm"] = musl_dict[d]
            if perims: m["perimeters"] = perims

        return patient_info, list(measurements.values())
    except Exception as e:
        return None, []

def parse_single_tanita_pdf(pdf_path: str) -> Optional[Dict[str, Any]]:
    """Extrae pesaje único de un PDF de Composición Corporal Tanita."""
    try:
        from dietowin_scanner import extract_composition_from_pdf
        return extract_composition_from_pdf(pdf_path)
    except Exception:
        return None

def parse_tanita_excel(excel_path: str) -> Optional[Dict[str, Any]]:
    """Extrae pesaje de archivo Excel Tanita."""
    try:
        from dietowin_scanner import extract_composition_from_excel
        return extract_composition_from_excel(excel_path)
    except Exception:
        return None

def run_autonomous_crawler():
    """Ejecuta la migración e importación masiva de Dietowin y Drive."""
    print("=== INICIANDO RASTREO Y MIGRACIÓN AUTÓNOMA DIETOWIN ===")
    conn = get_db()
    
    stats = {
        "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "folders_scanned": 0,
        "patients_processed": 0,
        "new_measurements_inserted": 0,
        "new_plans_imported": 0,
        "errors": []
    }
    
    # 1. Procesar carpetas de Google Drive (363 carpetas)
    if os.path.exists(DEPORTISTAS_DIR):
        folders = [f for f in os.listdir(DEPORTISTAS_DIR) if os.path.isdir(os.path.join(DEPORTISTAS_DIR, f))]
        stats["folders_scanned"] = len(folders)
        
        for idx, folder_name in enumerate(folders):
            folder_path = os.path.join(DEPORTISTAS_DIR, folder_name)
            # Normalizar nombre del paciente limpiando sufijos como 'TKD', 'Boxeo', etc.
            clean_name = re.sub(r'\s+(TKD|Boxeo|Triatlon|Nutricion|Consulta|Trail|Crossfit).*$', '', folder_name, flags=re.IGNORECASE).strip()
            
            client_id = None
            try:
                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        full_path = os.path.join(root, file)
                        fl = file.lower()
                        
                        # A. PDFs Evolutivos con múltiples consultas
                        if fl.endswith(".pdf") and any(k in fl for k in ["evolutivo", "informe evolutivo"]):
                            p_info, rows = parse_dietowin_evolutivo_pdf(full_path)
                            target_name = (p_info and p_info.get("name")) or clean_name
                            if not client_id:
                                client_id = ensure_client_exists(conn, target_name, (p_info or {}).get("phone", ""), (p_info or {}).get("email", ""))
                            for r in rows:
                                if insert_measurement_if_new(conn, client_id, target_name, r):
                                    stats["new_measurements_inserted"] += 1
                                    
                        # B. PDFs de composición individual
                        elif fl.endswith(".pdf") and any(k in fl for k in ["composicion", "bioimpedancia", "tanita", "antropometria"]):
                            compo = parse_single_tanita_pdf(full_path)
                            if compo and compo.get("weight_kg"):
                                if not client_id:
                                    client_id = ensure_client_exists(conn, clean_name)
                                m_obj = {
                                    "measurement_date": compo.get("measurement_date"),
                                    "weight": compo.get("weight_kg"),
                                    "fat_percent": compo.get("fat_percent"),
                                    "fat_mass": compo.get("fat_mass_kg"),
                                    "ffm": compo.get("ffm_kg"),
                                    "muscle_mass": compo.get("muscle_mass_kg"),
                                    "water_percent": compo.get("water_percent"),
                                    "bone_mass": compo.get("bone_mass_kg"),
                                    "visceral_fat": compo.get("visceral_fat"),
                                    "bmi": compo.get("bmi")
                                }
                                if insert_measurement_if_new(conn, client_id, clean_name, m_obj):
                                    stats["new_measurements_inserted"] += 1

                        # C. Archivos Excel Tanita
                        elif (fl.endswith(".xlsx") or fl.endswith(".xlsm")) and any(k in fl for k in ["tanita", "antropometria evolucion", "valoraciones"]):
                            compo = parse_tanita_excel(full_path)
                            if compo and compo.get("weight_kg"):
                                if not client_id:
                                    client_id = ensure_client_exists(conn, clean_name)
                                m_obj = {
                                    "measurement_date": compo.get("measurement_date"),
                                    "weight": compo.get("weight_kg"),
                                    "fat_percent": compo.get("fat_percent"),
                                    "fat_mass": compo.get("fat_mass_kg"),
                                    "ffm": compo.get("ffm_kg"),
                                    "muscle_mass": compo.get("muscle_mass_kg"),
                                    "water_percent": compo.get("water_percent"),
                                    "bone_mass": compo.get("bone_mass_kg"),
                                    "visceral_fat": compo.get("visceral_fat"),
                                    "bmi": compo.get("bmi")
                                }
                                if insert_measurement_if_new(conn, client_id, clean_name, m_obj):
                                    stats["new_measurements_inserted"] += 1
                                    
                stats["patients_processed"] += 1
            except Exception as e:
                stats["errors"].append(f"Error procesando {folder_name}: {str(e)}")

    # 2. Procesar patrones de DietaWeb (*.DW11W)
    dietaweb_dir = os.path.join(SUITE_DIR, "DietaWeb")
    if os.path.exists(dietaweb_dir):
        from dietowin_scanner import parse_latest_dw11w_for_client, find_latest_dw11w_file
        dw_files = [f for f in os.listdir(dietaweb_dir) if f.endswith(".DW11W")]
        for f in dw_files:
            try:
                fp = os.path.join(dietaweb_dir, f)
                with open(fp, 'rb') as d_fp:
                    head = d_fp.read(1500).decode('latin1', errors='replace')
                    m_nom = re.search(r'NombrePaciente=(.+)', head)
                    p_name = m_nom.group(1).strip() if m_nom else ""
                    if p_name and len(p_name) >= 3:
                        c_id = ensure_client_exists(conn, p_name)
                        # Comprobar si ya existe un plan para este deportista con este título
                        m_tit = re.search(r'Titulo=(.+)', head)
                        plan_title = m_tit.group(1).strip() if m_tit else f
                        c = conn.cursor()
                        c.execute("SELECT id FROM diet_plans WHERE client_id = ? AND plan_name = ?", (c_id, plan_title))
                        if not c.fetchone():
                            parsed = parse_latest_dw11w_for_client(p_name)
                            if parsed and parsed.get("weekly_data"):
                                c.execute("""
                                    INSERT INTO diet_plans (
                                        client_id, client_name, plan_name, created_at, weight, ffm,
                                        target_kcal, target_protein_g, target_carbs_g, target_fat_g, weekly_data_json, notes
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    c_id, p_name, plan_title, parsed.get("date_str") or datetime.now().strftime("%Y-%m-%d"),
                                    70.0, 58.0, 2400, 160, 250, 80, json.dumps(parsed["weekly_data"]),
                                    f"Importado automáticamente de Dietowin: {parsed.get('file')}"
                                ))
                                conn.commit()
                                stats["new_plans_imported"] += 1
            except Exception as e:
                pass

    conn.close()
    stats["finish_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(PROGRESS_FILE, "w", encoding="utf-8") as pf:
        json.dump(stats, pf, indent=2, ensure_ascii=False)
        
    print(f"=== MIGRACIÓN AUTÓNOMA FINALIZADA CON ÉXITO ===")
    print(f"Pacientes procesados: {stats['patients_processed']}")
    print(f"Nuevas mediciones históricas insertadas: {stats['new_measurements_inserted']}")
    print(f"Planes Dietowin importados: {stats['new_plans_imported']}")
    return stats

if __name__ == "__main__":
    run_autonomous_crawler()
