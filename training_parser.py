# -*- coding: utf-8 -*-
"""
training_parser.py
Módulo de Procesamiento Inteligente de Entrenamientos por Copy-Paste
para ANyD Nutricionistas · Román Illescas Quiroga (Col. MAD00274).

Permite copiar y pegar textos de planificaciones semanales (desde WhatsApp,
cuadrantes de entrenadores, correos o notas del deportista) y traducirlos
automáticamente a la estructura formal del Patrón Nutricional ANyD:
- Reconoce los 7 días (Lunes a Domingo) o días sueltos.
- Identifica disciplinas según los 28 deportes oficiales del compendio ACSM de ANyD.
- Detección precisa de descansos totales o activos.
- Desglose de horas de inicio, duración real (filtrando distancias como 8x1000m o 10km).
- Cálculo de gasto calórico según METs oficiales y peso corporal.
- Periodización automática de carbohidratos (ACSM/IOC) según la carga de cada día.
- Protocolos peri-entreno de vaciamiento gástrico, digestibilidad y ventanas de recuperación.
"""

import re
import unicodedata
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import diet_manager

DAYS_LIST = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

DAY_MAP = {
    "lunes": "Lunes", "lun": "Lunes",
    "martes": "Martes", "mar": "Martes",
    "miercoles": "Miércoles", "miércoles": "Miércoles", "mie": "Miércoles", "mié": "Miércoles",
    "jueves": "Jueves", "jue": "Jueves",
    "viernes": "Viernes", "vie": "Viernes",
    "sabado": "Sábado", "sábado": "Sábado", "sab": "Sábado", "sáb": "Sábado",
    "domingo": "Domingo", "dom": "Domingo",
    "dia 1": "Lunes", "dia 2": "Martes", "dia 3": "Miércoles",
    "dia 4": "Jueves", "dia 5": "Viernes", "dia 6": "Sábado", "dia 7": "Domingo"
}

DAY_START_REGEX = re.compile(
    r'^(?:[-*•\d\.\)]\s*)*\b(' + '|'.join(re.escape(k) for k in sorted(DAY_MAP.keys(), key=len, reverse=True)) + r')\b[:\s-]*',
    re.IGNORECASE
)

def remove_accents(text: str) -> str:
    """Elimina tildes y diacríticos preservando caracteres alfanuméricos."""
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()

# Catálogo priorizado de las 28 disciplinas oficiales de ANyD
DISCIPLINES_PRIORITY = [
    # 1. Halterofilia Olímpica
    {
        "keywords": ["halterofilia", "haltero", "snatch", "clean and jerk", "clean & jerk", "arrancada", "dos tiempos", "levantamiento olimpico"],
        "name": "🏋️ Halterofilia Olímpica (Arrancada & Dos Tiempos)",
        "acsm_name": "Olympic weightlifting, snatch, clean and jerk explosive",
        "mets": 6.5,
        "intensity": "Alta",
        "code": "ACSM-02054",
        "cho_target_g_kg": 1.1,
        "intra_cho_g_h": 30,
        "intra_fluid_ml_h": 500,
        "intra_sodium_mg_h": 350,
        "post_ratio": "2:1"
    },
    # 2. CrossFit WOD
    {
        "keywords": ["crossfit", "wod", "metcon", "box", "amrap", "emom", "for time", "hero wod"],
        "name": "🏋️‍♀️🔥 CrossFit / WOD / MetCon de Alta Intensidad",
        "acsm_name": "CrossFit, high intensity functional circuit, metcon (RPE 8-10)",
        "mets": 9.5,
        "intensity": "Muy Alta",
        "code": "ACSM-02055",
        "cho_target_g_kg": 1.2,
        "intra_cho_g_h": 30,
        "intra_fluid_ml_h": 600,
        "intra_sodium_mg_h": 400,
        "post_ratio": "2:1"
    },
    # 3. HYROX
    {
        "keywords": ["hyrox", "sled push", "sled pull", "burpee broad jumps", "wall balls", "sandbag lunges", "farmers carry", "skierg"],
        "name": "⚡🏅 HYROX (Carrera + Estaciones Funcionales)",
        "acsm_name": "HYROX simulation / high intensity functional race (RPE 8-10)",
        "mets": 10.5,
        "intensity": "Muy Alta",
        "code": "ACSM-02056",
        "cho_target_g_kg": 1.3,
        "intra_cho_g_h": 45,
        "intra_fluid_ml_h": 700,
        "intra_sodium_mg_h": 450,
        "post_ratio": "3:1"
    },
    # 4. Series en Pista / Intervalos Umbral
    {
        "keywords": ["series en pista", "series pista", "series 1000m", "series 400m", "series 800m", "series", "pista", "intervalos pista", "farlek", "fartlek", "vo2max", "vma"],
        "name": "⏱️ Series en Pista / Intervalos Umbral (400m - 1000m)",
        "acsm_name": "Running, track, interval training (Z4-Z5, VO2max)",
        "mets": 11.5,
        "intensity": "Muy Alta",
        "code": "ACSM-12020",
        "cho_target_g_kg": 1.3,
        "intra_cho_g_h": 45,
        "intra_fluid_ml_h": 650,
        "intra_sodium_mg_h": 450,
        "post_ratio": "3:1"
    },
    # 5. Ciclismo de Carretera Fondo Z2
    {
        "keywords": ["bici de carretera", "ciclismo de carretera", "ciclismo carretera", "carretera z2", "bici carretera", "carretera fondo", "fondo carretera", "flaca", "ciclismo fondo"],
        "name": "🚴‍♂️ Ciclismo de Carretera Z2 (Fondo Aeróbico)",
        "acsm_name": "Bicycling, road, 20-25 km/h, endurance Z2 moderate-vigorous",
        "mets": 8.5,
        "intensity": "Moderada",
        "code": "ACSM-01030",
        "cho_target_g_kg": 1.2,
        "intra_cho_g_h": 60,
        "intra_fluid_ml_h": 650,
        "intra_sodium_mg_h": 500,
        "post_ratio": "3:1"
    },
    # 6. Mountain Bike / BTT / MTB
    {
        "keywords": ["mountain bike", "btt", "mtb", "bici de montana", "bici de montaña", "ciclismo de montana", "ciclismo de montaña", "bici monte"],
        "name": "🚵 Mountain Bike / BTT / MTB",
        "acsm_name": "Bicycling, mountain, uphill / technical trail, vigorous",
        "mets": 9.0,
        "intensity": "Mod-Alta",
        "code": "ACSM-01040",
        "cho_target_g_kg": 1.2,
        "intra_cho_g_h": 50,
        "intra_fluid_ml_h": 600,
        "intra_sodium_mg_h": 450,
        "post_ratio": "3:1"
    },
    # 7. Ciclismo Indoor / Rodillo / Spinning
    {
        "keywords": ["rodillo", "spinning", "ciclo indoor", "ciclismo indoor", "zwift", "smart trainer"],
        "name": "🚴 Ciclismo Indoor / Rodillo / Spinning",
        "acsm_name": "Bicycling, stationary, moderate to vigorous (Zwift/Spinning)",
        "mets": 7.5,
        "intensity": "Mod-Alta",
        "code": "ACSM-01050",
        "cho_target_g_kg": 1.0,
        "intra_cho_g_h": 40,
        "intra_fluid_ml_h": 700,
        "intra_sodium_mg_h": 500,
        "post_ratio": "2:1"
    },
    # 8. Ciclismo Genérico / Bici
    {
        "keywords": ["ciclismo", "bici", "bicicleta", "bike"],
        "name": "🚴‍♂️ Ciclismo de Carretera Z2 (Fondo Aeróbico)",
        "acsm_name": "Bicycling, road, 20-25 km/h, endurance Z2 moderate-vigorous",
        "mets": 8.0,
        "intensity": "Moderada",
        "code": "ACSM-01030",
        "cho_target_g_kg": 1.1,
        "intra_cho_g_h": 50,
        "intra_fluid_ml_h": 600,
        "intra_sodium_mg_h": 450,
        "post_ratio": "3:1"
    },
    # 9. Trail Running / Montaña
    {
        "keywords": ["trail running", "trail", "carrera montana", "carrera montaña", "ultra trail", "desnivel", "monte"],
        "name": "⛰️ Trail Running / Carrera por Montaña",
        "acsm_name": "Trail running, uneven terrain, elevation gain, vigorous",
        "mets": 10.0,
        "intensity": "Muy Alta",
        "code": "ACSM-12025",
        "cho_target_g_kg": 1.3,
        "intra_cho_g_h": 60,
        "intra_fluid_ml_h": 700,
        "intra_sodium_mg_h": 550,
        "post_ratio": "3:1"
    },
    # 10. Carrera Ritmo Tempo / Maratón
    {
        "keywords": ["ritmo tempo", "tempo run", "ritmo maraton", "ritmo maratón", "umbral anaerobico", "umbral anaeróbico", "z3", "z4", "media maraton", "maraton", "maratón"],
        "name": "🏃 Carrera Ritmo Tempo / Umbral / Ritmo Objetivo",
        "acsm_name": "Running, tempo run, lactate threshold pace (Z3-Z4)",
        "mets": 10.0,
        "intensity": "Mod-Alta",
        "code": "ACSM-12026",
        "cho_target_g_kg": 1.2,
        "intra_cho_g_h": 45,
        "intra_fluid_ml_h": 600,
        "intra_sodium_mg_h": 400,
        "post_ratio": "3:1"
    },
    # 11. Carrera Continua Z2 (Base Aeróbica / Rodaje)
    {
        "keywords": ["carrera continua", "carrera z2", "rodaje z2", "rodaje suave", "rodaje largo", "rodaje", "running", "correr", "carrera", "trote"],
        "name": "🏃‍♂️ Carrera Continua Z2 (Base Aeróbica / Rodaje)",
        "acsm_name": "Running, 8-10 km/h, continuous aerobic Z2 base",
        "mets": 8.5,
        "intensity": "Moderada",
        "code": "ACSM-12030",
        "cho_target_g_kg": 1.0,
        "intra_cho_g_h": 30,
        "intra_fluid_ml_h": 500,
        "intra_sodium_mg_h": 350,
        "post_ratio": "2:1"
    },
    # 12. Fuerza / Hipertrofia (Gimnasio)
    {
        "keywords": ["hipertrofia", "gimnasio", "gym", "pesas", "rutina pesas", "torso", "pierna", "empuje", "traccion", "tracción", "ppl", "brazos", "espalda", "pecho", "cuadriceps", "fuerza hipertrofia"],
        "name": "🏋️‍♂️ Entrenamiento de Fuerza / Hipertrofia (Gimnasio)",
        "acsm_name": "Resistance training, multiple sets, bodybuilding/hypertrophy (RPE 7-9)",
        "mets": 6.0,
        "intensity": "Alta",
        "code": "ACSM-02052",
        "cho_target_g_kg": 1.0,
        "intra_cho_g_h": 25,
        "intra_fluid_ml_h": 450,
        "intra_sodium_mg_h": 300,
        "post_ratio": "2:1"
    },
    # 13. Fuerza Máxima / Powerlifting
    {
        "keywords": ["powerlifting", "fuerza maxima", "fuerza máxima", "peso muerto", "press banca", "sentadilla pesada", "1rm", "fuerza basica", "fuerza pura"],
        "name": "🏋️ Fuerza Máxima / Powerlifting",
        "acsm_name": "Powerlifting, maximum strength efforts, long rest intervals (RPE 8-10)",
        "mets": 5.0,
        "intensity": "Mod-Alta",
        "code": "ACSM-02053",
        "cho_target_g_kg": 1.0,
        "intra_cho_g_h": 20,
        "intra_fluid_ml_h": 400,
        "intra_sodium_mg_h": 300,
        "post_ratio": "1.5:1"
    },
    # 14. Fuerza genérica
    {
        "keywords": ["fuerza", "resistencia", "musculacion", "musculación"],
        "name": "🏋️‍♂️ Entrenamiento de Fuerza / Hipertrofia (Gimnasio)",
        "acsm_name": "Resistance training, multiple sets, bodybuilding/hypertrophy (RPE 7-9)",
        "mets": 6.0,
        "intensity": "Alta",
        "code": "ACSM-02052",
        "cho_target_g_kg": 1.0,
        "intra_cho_g_h": 25,
        "intra_fluid_ml_h": 450,
        "intra_sodium_mg_h": 300,
        "post_ratio": "2:1"
    },
    # 15. Calistenia
    {
        "keywords": ["calistenia", "street workout", "dominadas", "fondos", "muscle up", "anillas"],
        "name": "🤸 Calistenia / Street Workout",
        "acsm_name": "Calisthenics, heavy effort, pull-ups, dips, muscle-ups",
        "mets": 7.0,
        "intensity": "Alta",
        "code": "ACSM-02040",
        "cho_target_g_kg": 1.0,
        "intra_cho_g_h": 25,
        "intra_fluid_ml_h": 450,
        "intra_sodium_mg_h": 300,
        "post_ratio": "2:1"
    },
    # 16. Natación Series & Umbral
    {
        "keywords": ["natacion series", "natación series", "series piscina", "series crol", "intervalos natacion", "intervalos natación"],
        "name": "🏊‍♂️ Natación Series & Umbral Anaeróbico",
        "acsm_name": "Swimming, intervals, vigorous effort (laps fast)",
        "mets": 9.5,
        "intensity": "Muy Alta",
        "code": "ACSM-18355",
        "cho_target_g_kg": 1.2,
        "intra_cho_g_h": 40,
        "intra_fluid_ml_h": 500,
        "intra_sodium_mg_h": 350,
        "post_ratio": "3:1"
    },
    # 17. Natación Z2 / Fondo
    {
        "keywords": ["natacion", "natación", "nadar", "piscina", "aguas abiertas", "crol"],
        "name": "🏊‍♂️ Natación Crol Z2 (Nado Continuo)",
        "acsm_name": "Swimming, crawl, moderate pace (continuous aerobic Z2)",
        "mets": 7.0,
        "intensity": "Moderada",
        "code": "ACSM-18310",
        "cho_target_g_kg": 1.0,
        "intra_cho_g_h": 25,
        "intra_fluid_ml_h": 400,
        "intra_sodium_mg_h": 300,
        "post_ratio": "2:1"
    },
    # 18. Boxeo / MMA / Deportes de Contacto
    {
        "keywords": ["boxeo", "boxing", "sparring", "saco de boxeo", "mma", "kickboxing", "muay thai", "artes marciales mixtas"],
        "name": "🥊 Boxeo / Kickboxing / MMA (Sparring y Saco)",
        "acsm_name": "Boxing / MMA sparring, bag work, high intensity bouts",
        "mets": 9.0,
        "intensity": "Muy Alta",
        "code": "ACSM-15040",
        "cho_target_g_kg": 1.2,
        "intra_cho_g_h": 30,
        "intra_fluid_ml_h": 650,
        "intra_sodium_mg_h": 450,
        "post_ratio": "2:1"
    },
    # 19. Taekwondo / Karate
    {
        "keywords": ["taekwondo", "tkd", "karate", "katas", "kumite", "artes marciales", "combate"],
        "name": "🥋 Taekwondo / Karate (Combate & Técnica)",
        "acsm_name": "Taekwondo / Karate, sparring, kicks, technical forms",
        "mets": 8.5,
        "intensity": "Alta",
        "code": "ACSM-15070",
        "cho_target_g_kg": 1.1,
        "intra_cho_g_h": 30,
        "intra_fluid_ml_h": 550,
        "intra_sodium_mg_h": 350,
        "post_ratio": "2:1"
    },
    # 20. Judo / BJJ / Lucha
    {
        "keywords": ["judo", "bjj", "brazilian jiu jitsu", "jiu jitsu", "lucha", "grappling"],
        "name": "🥋 Judo / Lucha / Brazilian Jiu-Jitsu (BJJ)",
        "acsm_name": "Judo, jujitsu, wrestling, continuous sparring on mat",
        "mets": 9.5,
        "intensity": "Muy Alta",
        "code": "ACSM-15080",
        "cho_target_g_kg": 1.2,
        "intra_cho_g_h": 30,
        "intra_fluid_ml_h": 600,
        "intra_sodium_mg_h": 400,
        "post_ratio": "2:1"
    },
    # 21. Fútbol Partido / Competición
    {
        "keywords": ["partido de futbol", "partido de fútbol", "partido futbol", "partido f11", "partido f7", "futsal", "futbol sala", "competicion futbol"],
        "name": "⚽ Fútbol (Partido Oficial / Competición)",
        "acsm_name": "Soccer, competitive match play, repeated sprints (90 min)",
        "mets": 10.0,
        "intensity": "Muy Alta",
        "code": "ACSM-15200",
        "cho_target_g_kg": 1.3,
        "intra_cho_g_h": 45,
        "intra_fluid_ml_h": 650,
        "intra_sodium_mg_h": 450,
        "post_ratio": "3:1"
    },
    # 22. Fútbol Entrenamiento
    {
        "keywords": ["futbol", "fútbol", "entreno futbol", "entrenamiento futbol", "rondo"],
        "name": "⚽ Fútbol (Entrenamiento Técnico / Táctico)",
        "acsm_name": "Soccer, training drills, tactical and technical sessions",
        "mets": 8.0,
        "intensity": "Alta",
        "code": "ACSM-15205",
        "cho_target_g_kg": 1.1,
        "intra_cho_g_h": 30,
        "intra_fluid_ml_h": 550,
        "intra_sodium_mg_h": 400,
        "post_ratio": "2.5:1"
    },
    # 23. Pádel / Tenis
    {
        "keywords": ["padel", "pádel", "tenis", "partido de padel", "partido de tenis"],
        "name": "🎾 Pádel / Tenis (Partido Intensivo)",
        "acsm_name": "Padel / Tennis, competitive match play, frequent multidirectional sprints",
        "mets": 7.5,
        "intensity": "Mod-Alta",
        "code": "ACSM-15390",
        "cho_target_g_kg": 1.0,
        "intra_cho_g_h": 30,
        "intra_fluid_ml_h": 550,
        "intra_sodium_mg_h": 400,
        "post_ratio": "2:1"
    },
    # 24. Baloncesto / Balonmano
    {
        "keywords": ["baloncesto", "basket", "balonmano", "partido basket"],
        "name": "🏀 Baloncesto / Balonmano",
        "acsm_name": "Basketball / Handball, competitive game or intense drill",
        "mets": 8.0,
        "intensity": "Alta",
        "code": "ACSM-15020",
        "cho_target_g_kg": 1.1,
        "intra_cho_g_h": 35,
        "intra_fluid_ml_h": 600,
        "intra_sodium_mg_h": 400,
        "post_ratio": "2.5:1"
    },
    # 25. Oposiciones Bomberos
    {
        "keywords": ["oposiciones bomberos", "bomberos", "subir cuerda", "press banca bomberos", "torre bomberos"],
        "name": "🚒 Oposiciones Bomberos (Cuerda, Torres, Agilidad Lastrada)",
        "acsm_name": "Firefighter physical test prep, heavy climbing and anaerobic circuit",
        "mets": 9.5,
        "intensity": "Muy Alta",
        "code": "ACSM-15901",
        "cho_target_g_kg": 1.2,
        "intra_cho_g_h": 40,
        "intra_fluid_ml_h": 600,
        "intra_sodium_mg_h": 450,
        "post_ratio": "2.5:1"
    },
    # 26. Oposiciones Policía / CNP / Guardia Civil
    {
        "keywords": ["oposiciones policia", "oposiciones cnp", "guardia civil", "circuito agilidad", "1000m policia", "barra dominadas"],
        "name": "🚓 Oposiciones Policía Nacional / Guardia Civil (Circuito Agilidad + 1000m)",
        "acsm_name": "Police officer test prep, agility circuit and 1000m interval",
        "mets": 9.0,
        "intensity": "Muy Alta",
        "code": "ACSM-15902",
        "cho_target_g_kg": 1.2,
        "intra_cho_g_h": 35,
        "intra_fluid_ml_h": 550,
        "intra_sodium_mg_h": 400,
        "post_ratio": "2:1"
    },
    # 27. Pilates
    {
        "keywords": ["pilates maquina", "pilates reformer", "pilates", "reformer"],
        "name": "🧘‍♀️ Pilates Máquina / Reformer / Cadillac",
        "acsm_name": "Pilates apparatus, reformer, cadillac, resistance spring work",
        "mets": 4.0,
        "intensity": "Moderada",
        "code": "ACSM-02074",
        "cho_target_g_kg": 0.8,
        "intra_cho_g_h": 0,
        "intra_fluid_ml_h": 450,
        "intra_sodium_mg_h": 250,
        "post_ratio": "1:1"
    },
    # 28. Yoga / Movilidad / Paseo
    {
        "keywords": ["yoga", "vinyasa", "ashtanga", "estiramientos", "movilidad", "foam roller", "recuperacion activa", "paseo", "caminar", "andada"],
        "name": "🧘‍♂️ Hatha Yoga / Movilidad / Estiramientos",
        "acsm_name": "Yoga, Hatha / stretching light to moderate",
        "mets": 2.8,
        "intensity": "Baja",
        "code": "ACSM-02070",
        "cho_target_g_kg": 0.6,
        "intra_cho_g_h": 0,
        "intra_fluid_ml_h": 300,
        "intra_sodium_mg_h": 100,
        "post_ratio": "1:1"
    }
]

REST_KEYWORDS = ["descanso", "reposo", "off", "nada", "libre", "relax", "recuperacion pasiva", "dia libre", "d\xeda libre"]

def match_discipline(text: str) -> Dict[str, Any]:
    """Empareja un texto de entrenamiento con una de las disciplinas priorizadas del compendio."""
    norm = remove_accents(text)
    
    # 1. Comprobar descansos
    if any(re.search(r'\b' + re.escape(rst) + r'\b', norm) for rst in REST_KEYWORDS):
        return {
            "name": "🛌✨ Descanso Total Pasivo / Regeneración Estructural",
            "mets": 1.0,
            "intensity": "Descanso",
            "code": "ACSM-00000",
            "is_rest": True,
            "post_ratio": "1:1"
        }
        
    # 2. Buscar por longitud de palabra clave descendente (específico antes que genérico)
    best_disc = None
    best_match_len = -1
    
    for disc in DISCIPLINES_PRIORITY:
        for kw in disc["keywords"]:
            kw_norm = remove_accents(kw)
            # Buscar con delimitador o subcadena
            if kw_norm in norm:
                # Comprobar límite de palabra si la clave es corta (<5 chars) para evitar falsos positivos
                if len(kw_norm) < 5 and not re.search(r'\b' + re.escape(kw_norm) + r'\b', norm):
                    continue
                if len(kw_norm) > best_match_len:
                    best_match_len = len(kw_norm)
                    best_disc = disc
                    
    if best_disc:
        return best_disc
        
    # Genérico por defecto si no hay coincidencia
    clean_desc = text.strip()[:40]
    return {
        "name": f"🏃 {clean_desc}",
        "mets": 7.0,
        "intensity": "Moderada",
        "code": "ACSM-15999",
        "is_rest": False,
        "post_ratio": "2:1"
    }

def extract_duration_minutes(text: str) -> int:
    """
    Extrae la duración en minutos de un texto, eliminando previamente
    distancias como 8x1000m, 400m o 10km para no corromper los minutos.
    """
    # 1. Eliminar patrones de series y distancias
    cleaned = re.sub(r'\d+x\d+\s*m\b', ' ', text, flags=re.IGNORECASE)
    cleaned = re.sub(r'\b\d+(?:[.,]\d+)?\s*(?:km|kms|k|metros|m)\b', ' ', cleaned, flags=re.IGNORECASE)
    
    # 2. Formato hora + minutos: 1h30, 1h 30m, 1h30min
    m_hm = re.search(r'(\d+)\s*h(?:oras?)?\s*(\d+)\s*(?:min|m|\')?', cleaned, re.IGNORECASE)
    if m_hm:
        return int(m_hm.group(1)) * 60 + int(m_hm.group(2))
        
    # 3. Formato horas: 1.5 horas, 2h, 1 hora
    m_h = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:h|hora|horas)\b', cleaned, re.IGNORECASE)
    if m_h:
        val = float(m_h.group(1).replace(',', '.'))
        return round(val * 60)
        
    # 4. Formato minutos explícitos: 75 min, 45', 60 minutos
    m_min = re.search(r'(\d+)\s*(?:minutos|min|mins|\')\b', cleaned, re.IGNORECASE)
    if m_min:
        return int(m_min.group(1))
        
    # 5. Rango horario: de 18:00 a 19:30
    m_range = re.search(r'(\d{1,2})[:.](\d{2})\s*(?:a|-)\s*(\d{1,2})[:.](\d{2})', cleaned)
    if m_range:
        h1, m1, h2, m2 = int(m_range.group(1)), int(m_range.group(2)), int(m_range.group(3)), int(m_range.group(4))
        diff = (h2 * 60 + m2) - (h1 * 60 + m1)
        if diff > 0:
            return diff
            
    # Duración por defecto si no se especifica
    return 60

def extract_start_time(text: str) -> str:
    """Extrae la hora de inicio de la sesión."""
    # Rango de hora a hora: 'de 18:00 a 19:00'
    m_range = re.search(r'(?:de\s+)?(\d{1,2})[:.](\d{2})\s*(?:a|-)', text, re.IGNORECASE)
    if m_range:
        return f"{int(m_range.group(1)):02d}:{int(m_range.group(2)):02d}"
        
    # 'a las 19:00' o '19:30'
    m_time = re.search(r'(?:a las\s+)?(\d{1,2})[:.](\d{2})', text, re.IGNORECASE)
    if m_time:
        return f"{int(m_time.group(1)):02d}:{int(m_time.group(2)):02d}"
        
    # 'a las 9am' / 'a las 7pm' / '18h'
    m_ampm = re.search(r'(\d{1,2})\s*(am|pm|h)\b', text, re.IGNORECASE)
    if m_ampm:
        hh = int(m_ampm.group(1))
        mer = m_ampm.group(2).lower()
        if mer == 'pm' and hh < 12: hh += 12
        return f"{hh:02d}:00"
        
    # Heurística mañana / tarde
    norm = remove_accents(text)
    if any(k in norm for k in ["manana", "am", "desayuno", "primera hora"]):
        return "09:30"
    elif any(k in norm for k in ["mediodia", "comida"]):
        return "14:00"
    else:
        return "18:00"

def parse_training_copy_paste(
    raw_text: str,
    weight_kg: float = 75.0,
    auto_periodize_carbs: bool = True,
    auto_adjust_digestibility: bool = True
) -> Dict[str, Any]:
    """
    Parsea texto plano de entrenamientos semanales y genera la estructura
    oficial de prescripción del patrón nutricional ANyD.
    """
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    
    parsed_by_day: Dict[str, List[Dict[str, Any]]] = {d: [] for d in DAYS_LIST}
    current_day = None
    
    for line in lines:
        line_norm = remove_accents(line)
        
        # 1. Detectar si la línea encabeza un día
        m_day = DAY_START_REGEX.match(line_norm)
        if m_day:
            day_token = m_day.group(1).lower()
            current_day = DAY_MAP[day_token]
            line_content = line[m_day.end():].strip()
        else:
            line_content = line
            
        if not current_day:
            continue
            
        if not line_content:
            continue
            
        # 2. Identificar si es descanso
        if any(re.search(r'\b' + re.escape(r_kw) + r'\b', remove_accents(line_content)) for r_kw in REST_KEYWORDS):
            parsed_by_day[current_day] = [{
                "sport": "🛌✨ Descanso Total Pasivo / Regeneración Estructural",
                "start_time": "00:00",
                "end_time": "00:00",
                "duration_min": 0,
                "intensity": "Descanso",
                "intensity_level": "Descanso",
                "energy_kcal": 0,
                "is_rest": True,
                "theme": {"border": "#94A3B8", "bg": "#F8FAFC", "text": "#475569", "badge_bg": "#E2E8F0", "badge_text": "#334155"},
                "pre_window": "--",
                "post_window": "--",
                "nutrition": {
                    "pre": {"carbs_g": 0, "water_ml": 250, "sodium_mg": 0, "recommended_foods": "Hidratación normal a demanda"},
                    "intra": {"carbs_g_h": 0, "fluid_ml_h": 0, "sodium_mg_h": 0, "format": "No requiere ingesta peri-esfuerzo"},
                    "post": {"protein_g": 0, "carbs_g": 0, "ratio": "1:1"}
                },
                "raw_text": line_content
            }]
            continue
            
        # 3. Detectar disciplina, duración y hora
        disc = match_discipline(line_content)
        dur = extract_duration_minutes(line_content)
        start_t = extract_start_time(line_content)
        
        # 4. Calcular guías peri-entreno oficiales ANyD
        guidelines = diet_manager.compute_peri_workout_guidelines(
            sport=disc["name"],
            duration_min=dur,
            intensity=disc["intensity"],
            weight_kg=weight_kg,
            start_time=start_t,
            notes=line_content
        )
        
        guidelines["raw_text"] = line_content
        guidelines["is_rest"] = False
        
        # Si el día ya tenía marcado descanso previo, sustituirlo
        if len(parsed_by_day[current_day]) == 1 and parsed_by_day[current_day][0].get("is_rest"):
            parsed_by_day[current_day] = []
            
        parsed_by_day[current_day].append(guidelines)
        
    # Rellenar días que hayan quedado sin mención como Descanso Total
    for d in DAYS_LIST:
        if not parsed_by_day[d]:
            parsed_by_day[d] = [{
                "sport": "🛌✨ Descanso Total Pasivo / Regeneración Estructural",
                "start_time": "00:00",
                "end_time": "00:00",
                "duration_min": 0,
                "intensity": "Descanso",
                "intensity_level": "Descanso",
                "energy_kcal": 0,
                "is_rest": True,
                "theme": {"border": "#94A3B8", "bg": "#F8FAFC", "text": "#475569", "badge_bg": "#E2E8F0", "badge_text": "#334155"},
                "pre_window": "--",
                "post_window": "--",
                "nutrition": {
                    "pre": {"carbs_g": 0, "water_ml": 250, "sodium_mg": 0, "recommended_foods": "Pauta de descanso: hidratación normal"},
                    "intra": {"carbs_g_h": 0, "fluid_ml_h": 0, "sodium_mg_h": 0, "format": "Día de regeneración pasiva"},
                    "post": {"protein_g": 0, "carbs_g": 0, "ratio": "1:1"}
                },
                "raw_text": "Descanso no especificado"
            }]
            
    # Periodización de carbohidratos ACSM/IOC según carga diaria
    periodized_carbs: Dict[str, Dict[str, Any]] = {}
    total_kcal = 0
    total_sessions = 0
    active_days = 0
    
    for d in DAYS_LIST:
        day_workouts = parsed_by_day[d]
        is_day_rest = all(w.get("is_rest") for w in day_workouts)
        day_dur = sum(w.get("duration_min", 0) for w in day_workouts if not w.get("is_rest"))
        day_kcal = sum(w.get("acsm_data", {}).get("energy_kcal", 0) or w.get("energy_kcal", 0) for w in day_workouts if not w.get("is_rest"))
        
        total_kcal += day_kcal
        if not is_day_rest:
            total_sessions += len([w for w in day_workouts if not w.get("is_rest")])
            active_days += 1
            
        # Target de hidratos de carbono (g/kg y g totales) según IOC/ACSM
        if is_day_rest:
            cho_g_kg = 3.0
            load_label = "Descanso / Regeneración"
            color = "#64748B"
        elif day_dur <= 60 and day_kcal < 550:
            cho_g_kg = 4.5
            load_label = "Carga Moderada"
            color = "#0284C7"
        elif day_dur <= 90 and day_kcal < 900:
            cho_g_kg = 5.5
            load_label = "Carga Alta"
            color = "#EA580C"
        else:
            cho_g_kg = 7.0
            load_label = "Carga Muy Alta / Resistencia"
            color = "#DC2626"
            
        periodized_carbs[d] = {
            "is_rest": is_day_rest,
            "duration_min": day_dur,
            "energy_kcal": day_kcal,
            "cho_g_kg": cho_g_kg,
            "cho_total_g": round(cho_g_kg * weight_kg),
            "load_label": load_label,
            "badge_color": color
        }
        
    return {
        "success": True,
        "workouts_by_day": parsed_by_day,
        "periodized_carbs": periodized_carbs,
        "summary": {
            "total_sessions": total_sessions,
            "active_days": active_days,
            "rest_days": 7 - active_days,
            "total_kcal": total_kcal,
            "weight_kg": weight_kg
        }
    }
