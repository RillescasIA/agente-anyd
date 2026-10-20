import os
import re
import unicodedata
import urllib.parse
from datetime import datetime
from typing import Optional, Dict, Any, List

DRIVE_ATHLETES_DIR = r"G:\Mi unidad\1.- ANyD\1.- Deportistas"

def normalize_text(text: str) -> str:
    if not text:
        return ""
    # Eliminar acentos, minúsculas, signos de puntuación y guiones
    nfkd = unicodedata.normalize('NFD', text.lower())
    clean = ''.join(c for c in nfkd if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9\s]', ' ', clean).strip()

def get_all_athlete_folders() -> List[str]:
    if not os.path.exists(DRIVE_ATHLETES_DIR):
        return []
    try:
        return [f for f in os.listdir(DRIVE_ATHLETES_DIR) if os.path.isdir(os.path.join(DRIVE_ATHLETES_DIR, f))]
    except Exception as e:
        print(f"[DRIVE ERROR] Error listando carpetas: {e}")
        return []

def find_athlete_folder(client_name: str) -> Optional[str]:
    """
    Busca la carpeta correspondiente al deportista en G:\\Mi unidad\\1.- ANyD\\1.- Deportistas.
    Utiliza coincidencia exacta y por similitud de palabras (nombre + apellidos).
    """
    if not client_name or not os.path.exists(DRIVE_ATHLETES_DIR):
        return None

    norm_target = normalize_text(client_name)
    target_words = set(w for w in norm_target.split() if len(w) > 2)

    folders = get_all_athlete_folders()

    # 1. Coincidencia exacta normalizada
    for f in folders:
        if normalize_text(f) == norm_target:
            return os.path.join(DRIVE_ATHLETES_DIR, f)

    # 2. Coincidencia por contención completa
    for f in folders:
        norm_f = normalize_text(f)
        if norm_target in norm_f or norm_f in norm_target:
            return os.path.join(DRIVE_ATHLETES_DIR, f)

    # 3. Coincidencia de múltiples palabras significativas (ej. "maria cano" con "Maria Cano Villanueva")
    if target_words:
        best_match = None
        max_matches = 0
        for f in folders:
            f_words = set(w for w in normalize_text(f).split() if len(w) > 2)
            common = target_words.intersection(f_words)
            if len(common) > max_matches and len(common) >= min(2, len(target_words)):
                max_matches = len(common)
                best_match = f
        if best_match:
            return os.path.join(DRIVE_ATHLETES_DIR, best_match)

    return None

def open_athlete_folder(client_name: str) -> Dict[str, Any]:
    """
    Abre la carpeta del deportista en el Explorador local (si está en Windows)
    o retorna el enlace web directo a Google Drive para entornos cloud (Render/Linux).
    """
    clean_target = client_name.strip()
    web_url = f"https://drive.google.com/drive/search?q={urllib.parse.quote(clean_target)}"
    folder_path = find_athlete_folder(clean_target)
    created = False

    if not folder_path and os.path.exists(DRIVE_ATHLETES_DIR):
        clean_name = clean_target.title()
        folder_path = os.path.join(DRIVE_ATHLETES_DIR, clean_name)
        try:
            os.makedirs(folder_path, exist_ok=True)
            created = True
        except Exception:
            pass

    # Si estamos en entorno local con soporte nativo de Windows:
    if folder_path and hasattr(os, "startfile") and os.path.exists(folder_path):
        try:
            os.startfile(folder_path)
            return {
                "success": True,
                "created": created,
                "opened_locally": True,
                "web_url": web_url,
                "path": folder_path,
                "message": f"Carpeta abierta en el Explorador de Windows: {os.path.basename(folder_path)}"
            }
        except Exception as e:
            print(f"[DRIVE] No se pudo abrir localmente: {e}")

    # Fallback seguro para Render (Linux) o cuando no hay soporte local:
    return {
        "success": True,
        "created": created,
        "opened_locally": False,
        "web_url": web_url,
        "path": folder_path,
        "message": f"Accediendo a Google Drive para {clean_target}"
    }

def get_athlete_folder_info(client_name: str) -> Dict[str, Any]:
    folder_path = find_athlete_folder(client_name)
    if not folder_path or not os.path.exists(folder_path):
        return {"exists": False, "folder_name": None, "path": None, "files_count": 0}

    try:
        files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
        return {
            "exists": True,
            "folder_name": os.path.basename(folder_path),
            "path": folder_path,
            "files_count": len(files),
            "recent_files": files[:5]
        }
    except Exception:
        return {"exists": True, "folder_name": os.path.basename(folder_path), "path": folder_path, "files_count": 0}

def save_tanita_report_to_athlete_folder(client_name: str, meas: Dict[str, Any]) -> Dict[str, Any]:
    """
    Genera un informe clínico de la medición Tanita MC-580 y lo guarda directamente en su carpeta de Google Drive.
    """
    folder_path = find_athlete_folder(client_name)
    if not folder_path:
        # Crear carpeta
        clean_name = client_name.strip().title()
        folder_path = os.path.join(DRIVE_ATHLETES_DIR, clean_name)
        os.makedirs(folder_path, exist_ok=True)

    date_stamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"Medicion_Tanita_MC580_{date_stamp}.txt"
    full_path = os.path.join(folder_path, filename)

    weight = meas.get("weight", "--")
    fat_pct = meas.get("fat_percent", "--")
    fat_kg = meas.get("fat_mass", "--")
    muscle_kg = meas.get("muscle_mass", "--")
    ffm_kg = meas.get("ffm", "--")
    water_pct = meas.get("water_percent", "--")
    visceral = meas.get("visceral_fat", "--")
    bone_kg = meas.get("bone_mass", "--")
    bmr_cunningham = meas.get("bmr_cunningham", "--")
    bmr_tanita = meas.get("bmr_tanita", "--")
    metabolic_age = meas.get("metabolic_age", "--")

    content = f"""======================================================================
INFORME DE BIOIMPEDANCIA CLÍNICA — TANITA MC-580
ANYD NUTRICIONISTAS · Román Illescas Quiroga (Col. MAD00274)
Web: https://anyd.es | Sede: Madrid
======================================================================

Deportista:         {client_name}
Fecha del Pesaje:   {datetime.now().strftime('%d/%m/%Y a las %H:%M')}
Dispositivo:        Tanita MC-580 (Multifrecuencia Clínica Segmental)

----------------------------------------------------------------------
1. COMPOSICIÓN CORPORAL GLOBAL
----------------------------------------------------------------------
• Peso Total:               {weight} kg
• Grasa Corporal:           {fat_pct} % ({fat_kg} kg de masa grasa)
• Masa Libre de Grasa (FFM):{ffm_kg} kg
• Masa Muscular Total:      {muscle_kg} kg
• Agua Corporal Total (TBW):{water_pct} %
• Grasa Visceral:           Nivel {visceral}
• Masa Ósea Estimada:       {bone_kg} kg
• Edad Metabólica:          {metabolic_age} años

----------------------------------------------------------------------
2. GASTO METABÓLICO BASAL (BMR) Y REQUERIMIENTO ENERGÉTICO
----------------------------------------------------------------------
• BMR Cunningham (1980/1991): {bmr_cunningham} kcal/día
  [Fórmula oficial ANyD para deportistas: BMR = 500 + 22 * FFM]
• BMR Tanita (Estimación):    {bmr_tanita} kcal/día

Estimación de Gasto Energético Total (TDEE) Periodizado (Criterio Conservador ANyD):
- Día de Descanso (PAL 1.25):             ~{round(float(bmr_cunningham)*1.25) if str(bmr_cunningham).replace('.','',1).isdigit() else '--'} kcal/día
- Día Entrenamiento Moderado (PAL 1.40):   ~{round(float(bmr_cunningham)*1.40) if str(bmr_cunningham).replace('.','',1).isdigit() else '--'} kcal/día
- Día Entrenamiento Intenso (PAL 1.60):    ~{round(float(bmr_cunningham)*1.60) if str(bmr_cunningham).replace('.','',1).isdigit() else '--'} kcal/día

----------------------------------------------------------------------
3. CRITERIOS NUTRICIONALES ANyD NUTRICIONISTAS
----------------------------------------------------------------------
- Carne roja según OMS: Máximo 1-2 tomas por semana (<500g cocida semanal).
- Legumbres: Mínimo 4 tomas semanales (almidón resistente y fibra prebiótica).
- Cereales: 100% integrales de grano entero (refinados solo peri-entreno).
- Raciones estables de hidratos de carbono (variación máx. ±10g).
- Aceite de Oliva Virgen Extra (AOVE) medido en cucharas (5g / 10-12g).
======================================================================
"""

    try:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {
            "success": True,
            "filename": filename,
            "folder": os.path.basename(folder_path),
            "full_path": full_path,
            "message": f"Ficha guardada exitosamente en Drive: {filename}"
        }
    except Exception as e:
        return {"success": False, "message": f"Error escribiendo en Drive: {e}"}
