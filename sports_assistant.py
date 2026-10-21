# -*- coding: utf-8 -*-
"""
Módulo del Asistente Copiloto de Nutrición y Gasto Energético Deportivo (ANyD).
Responde consultas en lenguaje natural sobre:
- Coste energético bruto y neto de cualquier actividad física (Compendio ACSM/Ainsworth 2011/2024).
- Pautas peri-entreno (hidratación, electrolitos/sodio, hidratos y ratios de recuperación).
- Prescripción proteica e hidratos según consensos ISSN / ACSM / IOC.
- Métricas personalizadas en tiempo real para el deportista activo.
"""

import re
import os
import unicodedata
from typing import Dict, Any, List, Optional, Tuple
import diet_manager
import dossier_pdf_generator

# ==============================================================================
# COMPENDIO AMPLIADO DE ACTIVIDADES FÍSICAS (ACSM / AINSWORTH 2011/2024)
# ==============================================================================

COMPENDIUM_ACTIVITIES: List[Dict[str, Any]] = [
    # --- PILATES & ESTABILIDAD LUMBO-PÉLVICA ---
    {
        "code": "ACSM-02074",
        "category": "Pilates / Estabilidad Core",
        "name_es": "Pilates Máquina / Reformer / Cadillac",
        "acsm_name": "Pilates apparatus, reformer, cadillac, resistance spring work",
        "mets": 4.0,
        "intensity_level": "Moderada",
        "keywords": ["pilates maquina", "pilates máquina", "reformer", "cadillac", "wunda chair", "pilates con muelles", "pilates aparato", "pilates aparatos"],
        "cho_target_g_kg": 0.8,
        "intra_cho_g_h": 0,
        "intra_fluid_ml_h": 450,
        "intra_sodium_mg_h": 250,
        "post_ratio": "1:1",
        "post_cho_g_kg": 0.5,
        "post_pro_g_kg": 0.3,
        "description": "Trabajo de control motor, fuerza isométrica y excéntrica del core y estabilizadores profundos con resistencia variable de muelles.",
        "evidence": "Ainsworth Compendium Code 02074 & ACSM Core Stabilization Guidelines"
    },
    {
        "code": "ACSM-02072",
        "category": "Pilates / Estabilidad Core",
        "name_es": "Pilates Suelo / Mat",
        "acsm_name": "Pilates, mat work, body weight",
        "mets": 3.2,
        "intensity_level": "Baja",
        "keywords": ["pilates suelo", "pilates mat", "pilates esterilla", "pilates"],
        "cho_target_g_kg": 0.7,
        "intra_cho_g_h": 0,
        "intra_fluid_ml_h": 350,
        "intra_sodium_mg_h": 150,
        "post_ratio": "1:1",
        "post_cho_g_kg": 0.4,
        "post_pro_g_kg": 0.25,
        "description": "Secuencia de ejercicios de suelo enfocados en el transverso abdominal, suelo pélvico y alineación axial.",
        "evidence": "Ainsworth Compendium Code 02072"
    },
    {
        "code": "ACSM-02071",
        "category": "Yoga / Movilidad",
        "name_es": "Vinyasa / Power Yoga / Ashtanga",
        "acsm_name": "Yoga, Power / Vinyasa flow vigorous",
        "mets": 4.0,
        "intensity_level": "Moderada",
        "keywords": ["vinyasa", "power yoga", "ashtanga", "bikram", "yoga dinamico", "yoga dinámico"],
        "cho_target_g_kg": 0.8,
        "intra_cho_g_h": 0,
        "intra_fluid_ml_h": 500,
        "intra_sodium_mg_h": 300,
        "post_ratio": "1:1",
        "post_cho_g_kg": 0.5,
        "post_pro_g_kg": 0.25,
        "description": "Secuencia continua y dinámica de asanas con demanda de fuerza estática y cardiovascular moderada.",
        "evidence": "Ainsworth Compendium Code 02071"
    },
    {
        "code": "ACSM-02070",
        "category": "Yoga / Movilidad",
        "name_es": "Hatha Yoga / Movilidad / Estiramientos",
        "acsm_name": "Yoga, Hatha / stretching light to moderate",
        "mets": 2.5,
        "intensity_level": "Baja",
        "keywords": ["yoga", "hatha", "estiramientos", "movilidad", "foam roller", "flexibilidad", "relajacion"],
        "cho_target_g_kg": 0.6,
        "intra_cho_g_h": 0,
        "intra_fluid_ml_h": 300,
        "intra_sodium_mg_h": 100,
        "post_ratio": "1:1",
        "post_cho_g_kg": 0.4,
        "post_pro_g_kg": 0.2,
        "description": "Posturas estáticas de estiramiento y respiración con baja demanda metabólica.",
        "evidence": "Ainsworth Compendium Code 02070"
    },

    # --- FUERZA & HIPERTROFIA ---
    {
        "code": "ACSM-02052",
        "category": "Fuerza / Musculación",
        "name_es": "Entrenamiento de Fuerza / Hipertrofia (Gimnasio)",
        "acsm_name": "Resistance training, multiple sets, bodybuilding/hypertrophy (RPE 7-9)",
        "mets": 6.0,
        "intensity_level": "Alta",
        "keywords": ["fuerza", "hipertrofia", "gimnasio", "pesas", "musculacion", "musculación", "torso", "pierna", "empuje", "traccion", "rutina pesas", "sentadilla", "banca"],
        "cho_target_g_kg": 1.0,
        "intra_cho_g_h": 25,
        "intra_fluid_ml_h": 450,
        "intra_sodium_mg_h": 300,
        "post_ratio": "2:1",
        "post_cho_g_kg": 0.8,
        "post_pro_g_kg": 0.4,
        "description": "Sesión estructurada de sobrecarga progresiva orientada a la tensión mecánica y el estrés metabólico miofibrilar.",
        "evidence": "ACSM / ISSN Position Stand: Resistance Training and MPS"
    },
    {
        "code": "ACSM-02053",
        "category": "Fuerza / Musculación",
        "name_es": "Fuerza Máxima / Powerlifting",
        "acsm_name": "Powerlifting, maximum strength efforts, long rest intervals (RPE 8-10)",
        "mets": 5.0,
        "intensity_level": "Mod-Alta",
        "keywords": ["powerlifting", "fuerza maxima", "fuerza máxima", "peso muerto", "press banca pesado", "1rm", "snc"],
        "cho_target_g_kg": 1.0,
        "intra_cho_g_h": 20,
        "intra_fluid_ml_h": 400,
        "intra_sodium_mg_h": 300,
        "post_ratio": "1.5:1",
        "post_cho_g_kg": 0.7,
        "post_pro_g_kg": 0.4,
        "description": "Esfuerzos máximos neuromusculares con descansos prolongados (3 a 5 min) y alta demanda sobre el Sistema Nervioso Central.",
        "evidence": "ACSM Strength Principles & Neuromuscular Recovery"
    },
    {
        "code": "ACSM-02054",
        "category": "Fuerza / Musculación",
        "name_es": "Halterofilia Olímpica (Arrancada & Dos Tiempos)",
        "acsm_name": "Olympic weightlifting, snatch, clean and jerk explosive",
        "mets": 6.5,
        "intensity_level": "Alta",
        "keywords": ["halterofilia", "arrancada", "dos tiempos", "clean and jerk", "snatch", "levantamiento olimpico"],
        "cho_target_g_kg": 1.1,
        "intra_cho_g_h": 30,
        "intra_fluid_ml_h": 500,
        "intra_sodium_mg_h": 350,
        "post_ratio": "2:1",
        "post_cho_g_kg": 0.8,
        "post_pro_g_kg": 0.4,
        "description": "Potencia explosiva y aceleración de cargas máximas combinada con gran reclutamiento elástico-muscular.",
        "evidence": "IWF / ACSM Olympic Lifting Energy Standards"
    },
    {
        "code": "ACSM-02040",
        "category": "Fuerza / Funcional",
        "name_es": "Calistenia / Street Workout",
        "acsm_name": "Calisthenics, heavy effort, pull-ups, dips, muscle-ups",
        "mets": 7.0,
        "intensity_level": "Alta",
        "keywords": ["calistenia", "street workout", "dominadas", "fondos", "muscle up", "anillas"],
        "cho_target_g_kg": 1.0,
        "intra_cho_g_h": 25,
        "intra_fluid_ml_h": 500,
        "intra_sodium_mg_h": 300,
        "post_ratio": "2:1",
        "post_cho_g_kg": 0.8,
        "post_pro_g_kg": 0.38,
        "description": "Trabajo de fuerza con peso corporal, palancas biomecánicas y alta demanda neuromuscular del tren superior.",
        "evidence": "ACSM Compendium Code 02040"
    },

    # --- CROSSFIT & FUNCIONAL DE ALTA INTENSIDAD ---
    {
        "code": "ACSM-02065",
        "category": "CrossFit / Funcional",
        "name_es": "CrossFit / WOD / MetCon de Alta Intensidad",
        "acsm_name": "High-intensity functional fitness, WOD, metabolic conditioning",
        "mets": 10.5,
        "intensity_level": "Muy Alta",
        "keywords": ["crossfit", "wod", "metcon", "amrap", "emom", "box crossfit"],
        "cho_target_g_kg": 1.3,
        "intra_cho_g_h": 50,
        "intra_fluid_ml_h": 650,
        "intra_sodium_mg_h": 550,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.1,
        "post_pro_g_kg": 0.4,
        "description": "Esfuerzo metabólico mixto con glucólisis anaeróbica acelerada, acidosis metabólica elevada y alto reclutamiento neuromuscular.",
        "evidence": "ACSM Metabolic Conditioning & Acidosis Buffering"
    },
    {
        "code": "ACSM-02066",
        "category": "CrossFit / Funcional",
        "name_es": "HYROX (Carrera + Estaciones Funcionales)",
        "acsm_name": "Hyrox competition and simulation, 1km runs + functional stations",
        "mets": 11.0,
        "intensity_level": "Muy Alta",
        "keywords": ["hyrox", "sled push", "sled pull", "burpee broad jumps", "wall balls", "carrera hyrox"],
        "cho_target_g_kg": 1.4,
        "intra_cho_g_h": 60,
        "intra_fluid_ml_h": 700,
        "intra_sodium_mg_h": 600,
        "post_ratio": "3.5:1",
        "post_cho_g_kg": 1.2,
        "post_pro_g_kg": 0.4,
        "description": "Competición de fitness de resistencia combinando 8 km de carrera fraccionada con 8 estaciones pesadas.",
        "evidence": "ACSM / HYROX High Output Endurance Guidelines"
    },

    # --- CARRERA & RUNNING ---
    {
        "code": "ACSM-12020",
        "category": "Carrera / Running",
        "name_es": "Carrera Continua Z2 (Base Aeróbica / Rodaje)",
        "acsm_name": "Running, 5 to 6 mph (8.0 to 9.7 km/h), moderate aerobic Z2",
        "mets": 8.3,
        "intensity_level": "Moderada",
        "keywords": ["carrera", "running", "rodaje", "correr", "base aerobica", "z2", "carrera suave", "jogging", "trote"],
        "cho_target_g_kg": 1.0,
        "intra_cho_g_h": 30,
        "intra_fluid_ml_h": 550,
        "intra_sodium_mg_h": 400,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.0,
        "post_pro_g_kg": 0.3,
        "description": "Ritmo aeróbico conversacional para desarrollo mitocondrial y oxidación de ácidos grasos.",
        "evidence": "ACSM / IOC Consensus on Endurance Running"
    },
    {
        "code": "ACSM-12030",
        "category": "Carrera / Running",
        "name_es": "Carrera Ritmo Tempo / Umbral / Ritmo Objetivo",
        "acsm_name": "Running, 7.5 to 8.5 mph (12.0 to 13.7 km/h), vigorous threshold Z3-Z4",
        "mets": 11.5,
        "intensity_level": "Alta",
        "keywords": ["tempo", "ritmo maraton", "ritmo media", "umbral lactato", "carrera fuerte", "z3", "z4"],
        "cho_target_g_kg": 1.3,
        "intra_cho_g_h": 50,
        "intra_fluid_ml_h": 650,
        "intra_sodium_mg_h": 500,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.1,
        "post_pro_g_kg": 0.35,
        "description": "Esfuerzo en proximidad al umbral anaeróbico con gran vaciamiento de glucógeno en fibras de contracción rápida.",
        "evidence": "ACSM Guidelines for Threshold Running"
    },
    {
        "code": "ACSM-12040",
        "category": "Carrera / Running",
        "name_es": "Series en Pista / Intervalos Umbral (400m - 1000m)",
        "acsm_name": "Running, track intervals, sprint interval training Z5",
        "mets": 13.0,
        "intensity_level": "Muy Alta",
        "keywords": ["series", "pista", "intervalos", "cuestas", "fartlek", "400m", "1000m", "velocidad", "z5"],
        "cho_target_g_kg": 1.4,
        "intra_cho_g_h": 40,
        "intra_fluid_ml_h": 600,
        "intra_sodium_mg_h": 500,
        "post_ratio": "3.5:1",
        "post_cho_g_kg": 1.2,
        "post_pro_g_kg": 0.38,
        "description": "Repeticiones supramáximas por encima del VO2máx con máxima producción de lactato.",
        "evidence": "ACSM Sprint Interval Training Metabolic Demands"
    },
    {
        "code": "ACSM-12050",
        "category": "Carrera / Running",
        "name_es": "Trail Running / Carrera por Montaña",
        "acsm_name": "Running, cross country, mountain trail with elevation changes",
        "mets": 10.0,
        "intensity_level": "Mod-Alta",
        "keywords": ["trail", "trail running", "montaña", "montana", "carrera montana", "ultratrail"],
        "cho_target_g_kg": 1.2,
        "intra_cho_g_h": 60,
        "intra_fluid_ml_h": 650,
        "intra_sodium_mg_h": 550,
        "post_ratio": "3.5:1",
        "post_cho_g_kg": 1.1,
        "post_pro_g_kg": 0.35,
        "description": "Carrera con desniveles pronunciados, contracciones excéntricas en bajada y demanda de equilibrio.",
        "evidence": "ACSM Mountain Running Consensus"
    },

    # --- CICLISMO ---
    {
        "code": "ACSM-02010",
        "category": "Ciclismo",
        "name_es": "Ciclismo de Carretera Z2 (Fondo Aeróbico)",
        "acsm_name": "Bicycling, road, 14-16 mph (22-26 km/h), moderate aerobic Z2",
        "mets": 7.0,
        "intensity_level": "Moderada",
        "keywords": ["ciclismo", "carretera", "bici carretera", "fondo ciclismo", "peloton", "flaca"],
        "cho_target_g_kg": 1.0,
        "intra_cho_g_h": 60,
        "intra_fluid_ml_h": 600,
        "intra_sodium_mg_h": 500,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.0,
        "post_pro_g_kg": 0.3,
        "description": "Fondo prolongado de baja intensidad con preservación del glucógeno y reposición líquida continua.",
        "evidence": "ACSM / UCI Endurance Hydration and Glycogen Guidelines"
    },
    {
        "code": "ACSM-02030",
        "category": "Ciclismo",
        "name_es": "Mountain Bike / BTT / MTB",
        "acsm_name": "Bicycling, mountain, all-terrain vigorous",
        "mets": 8.5,
        "intensity_level": "Mod-Alta",
        "keywords": ["btt", "mountain bike", "mtb", "bici montana", "bici montaña", "gravel"],
        "cho_target_g_kg": 1.1,
        "intra_cho_g_h": 50,
        "intra_fluid_ml_h": 600,
        "intra_sodium_mg_h": 450,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.0,
        "post_pro_g_kg": 0.3,
        "description": "Cambios continuos de cadencia y potencia por irregularidades del terreno y pendientes.",
        "evidence": "ACSM Off-Road Cycling Protocol"
    },
    {
        "code": "ACSM-02050",
        "category": "Ciclismo",
        "name_es": "Ciclismo Indoor / Rodillo / Spinning",
        "acsm_name": "Bicycling, stationary, moderate to vigorous effort, high sweat rate",
        "mets": 7.5,
        "intensity_level": "Moderada",
        "keywords": ["rodillo", "spinning", "ciclo indoor", "estatica", "bici estatica", "zwift"],
        "cho_target_g_kg": 1.0,
        "intra_cho_g_h": 40,
        "intra_fluid_ml_h": 700,
        "intra_sodium_mg_h": 550,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.0,
        "post_pro_g_kg": 0.3,
        "description": "Esfuerzo continuo sin viento relativo, lo que eleva notablemente la tasa de sudoración y la pérdida hídrica.",
        "evidence": "ACSM Indoor High Sweat Rate Hydration Protocols"
    },

    # --- DEPORTES DE EQUIPO ---
    {
        "code": "ACSM-15610",
        "category": "Deportes de Equipo",
        "name_es": "Fútbol (Partido Oficial / Competición)",
        "acsm_name": "Soccer, competitive match, high intensity intermittent sprinting",
        "mets": 9.0,
        "intensity_level": "Alta",
        "keywords": ["futbol", "fútbol", "partido futbol", "partido", "soccer", "futbol sala", "match day"],
        "cho_target_g_kg": 1.2,
        "intra_cho_g_h": 45,
        "intra_fluid_ml_h": 650,
        "intra_sodium_mg_h": 500,
        "post_ratio": "3.5:1",
        "post_cho_g_kg": 1.1,
        "post_pro_g_kg": 0.35,
        "description": "Actividad intermitente de alta intensidad con sprints repetidos, aceleraciones, deceleraciones y choques.",
        "evidence": "FIFA / ACSM Consensus on Nutrition for Football"
    },
    {
        "code": "ACSM-15611",
        "category": "Deportes de Equipo",
        "name_es": "Fútbol (Entrenamiento Técnico / Táctico)",
        "acsm_name": "Soccer, practice, tactical drills, moderate effort",
        "mets": 7.5,
        "intensity_level": "Mod-Alta",
        "keywords": ["entrenamiento futbol", "sesion futbol", "tactico futbol", "entreno futbol"],
        "cho_target_g_kg": 1.0,
        "intra_cho_g_h": 35,
        "intra_fluid_ml_h": 550,
        "intra_sodium_mg_h": 400,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.0,
        "post_pro_g_kg": 0.3,
        "description": "Rondos, posesiones y ejercicios tácticos con volumen medio y gasto moderado.",
        "evidence": "FIFA Nutrition Protocol for Training"
    },
    {
        "code": "ACSM-15050",
        "category": "Deportes de Equipo",
        "name_es": "Baloncesto / Balonmano",
        "acsm_name": "Basketball, handball, competitive game, vertical jumps and cuts",
        "mets": 8.0,
        "intensity_level": "Alta",
        "keywords": ["baloncesto", "basket", "balonmano", "basket partido"],
        "cho_target_g_kg": 1.1,
        "intra_cho_g_h": 40,
        "intra_fluid_ml_h": 600,
        "intra_sodium_mg_h": 450,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.0,
        "post_pro_g_kg": 0.32,
        "description": "Esfuerzos glucolíticos cortos y repetidos, saltos verticales y transiciones rápidas.",
        "evidence": "FIBA / ACSM Basketball Nutrition Standards"
    },
    {
        "code": "ACSM-15700",
        "category": "Raqueta",
        "name_es": "Pádel / Tenis (Partido Intensivo)",
        "acsm_name": "Padel / Tennis, vigorous match play, lateral changes of direction",
        "mets": 7.3,
        "intensity_level": "Moderada",
        "keywords": ["padel", "pádel", "tenis", "partido padel", "squash", "fronton"],
        "cho_target_g_kg": 1.0,
        "intra_cho_g_h": 35,
        "intra_fluid_ml_h": 600,
        "intra_sodium_mg_h": 450,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.0,
        "post_pro_g_kg": 0.3,
        "description": "Desplazamientos cortos de aceleración y frenada con pausas breves entre puntos.",
        "evidence": "ACSM Racket Sports Energy Expenditure"
    },

    # --- DEPORTES DE COMBATE ---
    {
        "code": "ACSM-15150",
        "category": "Combate / Artes Marciales",
        "name_es": "Taekwondo / Karate (Combate & Técnica)",
        "acsm_name": "Combat sports, taekwondo, karate, kicking drills, competitive sparring",
        "mets": 10.0,
        "intensity_level": "Muy Alta",
        "keywords": ["taekwondo", "tkd", "karate", "combate tkd", "patadas", "peto"],
        "cho_target_g_kg": 1.3,
        "intra_cho_g_h": 40,
        "intra_fluid_ml_h": 600,
        "intra_sodium_mg_h": 500,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.1,
        "post_pro_g_kg": 0.35,
        "description": "Potencia explosiva de tren inferior con glucólisis rápida y alta sudoración bajo las protecciones.",
        "evidence": "WT / ACSM Combat Sports Nutrition Consensus"
    },
    {
        "code": "ACSM-15152",
        "category": "Combate / Artes Marciales",
        "name_es": "Boxeo / Kickboxing / MMA (Sparring y Saco)",
        "acsm_name": "Boxing, kickboxing, MMA, sparring and heavy bag rounds",
        "mets": 11.0,
        "intensity_level": "Muy Alta",
        "keywords": ["boxeo", "kickboxing", "mma", "sparring boxeo", "saco", "guantes", "ring"],
        "cho_target_g_kg": 1.3,
        "intra_cho_g_h": 45,
        "intra_fluid_ml_h": 650,
        "intra_sodium_mg_h": 550,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.1,
        "post_pro_g_kg": 0.35,
        "description": "Rounds intensos con deuda de oxígeno, contracciones isométricas de tronco y alta exigencia anaeróbica.",
        "evidence": "ACSM Combat Conditioning Guidelines"
    },
    {
        "code": "ACSM-15155",
        "category": "Combate / Artes Marciales",
        "name_es": "Judo / Lucha / Brazilian Jiu-Jitsu (BJJ)",
        "acsm_name": "Judo, wrestling, BJJ grappling, ground fighting vigorous",
        "mets": 9.5,
        "intensity_level": "Alta",
        "keywords": ["judo", "bjj", "brazilian jiu jitsu", "lucha", "grappling", "randori", "tatami"],
        "cho_target_g_kg": 1.2,
        "intra_cho_g_h": 35,
        "intra_fluid_ml_h": 600,
        "intra_sodium_mg_h": 450,
        "post_ratio": "2.5:1",
        "post_cho_g_kg": 1.0,
        "post_pro_g_kg": 0.38,
        "description": "Fuerza isométrica continua de agarre (grip) combinada con proyecciones y transiciones en el suelo.",
        "evidence": "IJF / ACSM Grappling Metabolic Demands"
    },

    # --- NATACIÓN ---
    {
        "code": "ACSM-18300",
        "category": "Natación",
        "name_es": "Natación Crol Z2 (Nado Continuo)",
        "acsm_name": "Swimming laps, freestyle, moderate aerobic pace",
        "mets": 7.0,
        "intensity_level": "Moderada",
        "keywords": ["natacion suave", "nadar crol", "piscina z2", "nado continuo"],
        "cho_target_g_kg": 1.0,
        "intra_cho_g_h": 30,
        "intra_fluid_ml_h": 400,
        "intra_sodium_mg_h": 300,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.0,
        "post_pro_g_kg": 0.3,
        "description": "Nado a velocidad constante sin paradas con activación muscular global sin impacto articular.",
        "evidence": "ACSM Aquatic Exercise Metabolic Guidelines"
    },
    {
        "code": "ACSM-18310",
        "category": "Natación",
        "name_es": "Natación Series & Umbral Anaeróbico",
        "acsm_name": "Swimming laps, interval sets, vigorous competitive pace",
        "mets": 9.8,
        "intensity_level": "Alta",
        "keywords": ["natacion", "natación", "series natacion", "series piscina", "estilos natacion"],
        "cho_target_g_kg": 1.2,
        "intra_cho_g_h": 45,
        "intra_fluid_ml_h": 500,
        "intra_sodium_mg_h": 350,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.1,
        "post_pro_g_kg": 0.35,
        "description": "Series cortas y medias a alta velocidad con paradas cronometradas y gran fatiga del tren superior.",
        "evidence": "FINA / ACSM Swimming High Output Protocols"
    },

    # --- OPOSICIONES & TÁCTICO ---
    {
        "code": "ACSM-02060",
        "category": "Táctico / Oposiciones",
        "name_es": "Oposiciones Bomberos (Cuerda, Torres, Agilidad Lastrada)",
        "acsm_name": "Tactical firefighter agility, loaded rope climbs, stairs, tower drill",
        "mets": 8.5,
        "intensity_level": "Muy Alta",
        "keywords": ["bombero", "bomberos", "oposicion bombero", "cuerda bombero", "torres bombero", "lastre"],
        "cho_target_g_kg": 1.3,
        "intra_cho_g_h": 50,
        "intra_fluid_ml_h": 650,
        "intra_sodium_mg_h": 500,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.1,
        "post_pro_g_kg": 0.38,
        "description": "Entrenamiento de fuerza específica de agarre, potencia de tren superior y tolerancia al calor con carga.",
        "evidence": "ACSM Tactical Athlete Nutrition Standards"
    },
    {
        "code": "ACSM-02064",
        "category": "Táctico / Oposiciones",
        "name_es": "Oposiciones Policía Nacional / Guardia Civil (Circuito Agilidad + 1000m)",
        "acsm_name": "Tactical police obstacle course, agility and 1000m run",
        "mets": 8.5,
        "intensity_level": "Alta",
        "keywords": ["policia", "policía", "guardia civil", "circuito policia", "oposicion policia"],
        "cho_target_g_kg": 1.1,
        "intra_cho_g_h": 35,
        "intra_fluid_ml_h": 500,
        "intra_sodium_mg_h": 400,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.0,
        "post_pro_g_kg": 0.32,
        "description": "Coordinación, potencia de salida y resistencia anaeróbica láctica.",
        "evidence": "ACSM Tactical Readiness Protocols"
    }
]


# ==============================================================================
# FUNCIONES DE EXTRACCIÓN Y BÚSQUEDA SEMÁNTICA
# ==============================================================================

def normalize_text_assistant(text: str) -> str:
    """Normaliza texto eliminando acentos, caracteres especiales y mayúsculas."""
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFD', text.lower())
    clean = ''.join(c for c in nfkd if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9\s]', ' ', clean).strip()


def find_matching_activity(query_text: str) -> Optional[Dict[str, Any]]:
    """
    Localiza la actividad física más afín en el Compendio según coincidencia léxica y de palabras clave.
    Prioriza coincidencias específicas (ej. 'pilates maquina' frente a 'pilates' genérico).
    """
    norm = normalize_text_assistant(query_text)
    best_entry = None
    best_score = -1

    for entry in COMPENDIUM_ACTIVITIES:
        score = 0
        for kw in entry["keywords"]:
            clean_kw = normalize_text_assistant(kw)
            if clean_kw in norm:
                # Bonificación proporcional a la longitud de la coincidencia
                kw_len = len(clean_kw.split())
                score += kw_len * 15 + len(clean_kw)
                if norm.startswith(clean_kw) or f" {clean_kw} " in f" {norm} ":
                    score += 20

        if score > best_score:
            best_score = score
            best_entry = entry

    # Si no hubo coincidencia estricta pero contiene palabras clave
    if not best_entry or best_score <= 0:
        if "pilates" in norm:
            if any(k in norm for k in ["maquina", "aparato", "reformer", "cadillac"]):
                return COMPENDIUM_ACTIVITIES[0]  # Pilates Máquina
            return COMPENDIUM_ACTIVITIES[1]  # Pilates Suelo
        elif any(k in norm for k in ["fuerza", "pesas", "gym", "muscul"]):
            return COMPENDIUM_ACTIVITIES[4]  # Fuerza
        elif any(k in norm for k in ["correr", "running", "carrera"]):
            return COMPENDIUM_ACTIVITIES[9]  # Carrera Z2
        elif any(k in norm for k in ["bici", "ciclismo"]):
            return COMPENDIUM_ACTIVITIES[13]  # Ciclismo Z2
        elif "futbol" in norm or "partido" in norm:
            return COMPENDIUM_ACTIVITIES[16]  # Fútbol

    return best_entry if best_score > 0 else None


def extract_duration_minutes(query_text: str) -> int:
    """Extrae la duración en minutos de una frase en lenguaje natural."""
    norm = query_text.lower()

    # Patrón 1: "1 hora y media", "1h 30m"
    m_hm = re.search(r'(\d+)\s*(?:h|hora|horas)\s*(?:y\s*)?(\d+)\s*(?:m|min|minuto|minutos)', norm)
    if m_hm:
        return int(m_hm.group(1)) * 60 + int(m_hm.group(2))

    # Patrón 2: "1 hora", "dos horas", "media hora"
    if "media hora" in norm:
        return 30
    if "una hora y media" in norm or "1 hora y media" in norm:
        return 90
    if "una hora" in norm or "1 hora" in norm or "1h" in norm:
        return 60
    if "dos horas" in norm or "2 horas" in norm or "2h" in norm:
        return 120
    if "tres horas" in norm or "3 horas" in norm:
        return 180

    m_h = re.search(r'(\d+)\s*(?:h|hora|horas)', norm)
    if m_h:
        return int(m_h.group(1)) * 60

    # Patrón 3: "45 min", "90 minutos", "75m"
    m_min = re.search(r'(\d+)\s*(?:minutos|minuto|min|m\b)', norm)
    if m_min:
        return int(m_min.group(1))

    # Por defecto 60 minutos si no se especifica
    return 60


def extract_athlete_context(query_text: str, active_athlete_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Obtiene los parámetros antropométricos y metabólicos del deportista:
    - Si se menciona un nombre en la pregunta (ej. 'en Iván Cerezo', 'en Sergio Iglesias'), lo busca.
    - Si se dice 'en este deportista' o similar, utiliza el activo.
    - Si se especifica un peso (ej. 'si pesa 72 kg'), sobrescribe el peso.
    """
    # 1. Verificar si hay un peso explícito en la pregunta
    m_kg = re.search(r'(\d+(?:[.,]\d+)?)\s*kg\b', query_text, re.IGNORECASE)
    custom_weight = float(m_kg.group(1).replace(',', '.')) if m_kg else None

    # 2. Determinar el nombre del deportista objetivo
    target_name = active_athlete_name or "Iván Cerezo Delgado"

    # Si la consulta menciona explícitamente a otro deportista
    norm_q = normalize_text_assistant(query_text)
    if "sergio" in norm_q and "iglesias" in norm_q:
        target_name = "Sergio Iglesias"
    elif "ariel" in norm_q:
        target_name = "Ariel Camino"
    elif "ivan" in norm_q or "cerezo" in norm_q:
        target_name = "Iván Cerezo Delgado"

    # 3. Extraer bioimpedancia Tanita MC-580 y BMR Cunningham
    athlete_data = dossier_pdf_generator.extract_tanita_body_composition(target_name)

    # Si hubo peso personalizado
    if custom_weight:
        athlete_data["weight_kg"] = custom_weight
        if athlete_data.get("ffm_kg"):
            # Ajustar FFM proporcionalmente
            athlete_data["ffm_kg"] = round(custom_weight * 0.85, 1)
            athlete_data["bmr_cunningham"] = round(500 + 22 * athlete_data["ffm_kg"])

    return athlete_data


# ==============================================================================
# MOTOR DE RESPUESTA INTELIGENTE DEL AGENTE COPILOTO
# ==============================================================================

def process_assistant_query(query: str, active_athlete_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Procesa cualquier consulta de nutrición deportiva y gasto calórico.
    Devuelve un diccionario estructurado con:
    - reply_markdown: Respuesta explicativa en Markdown lista para chat.
    - metrics_card: Tarjeta visual de KPIs numéricos calculados.
    - athlete: Datos del deportista aplicados.
    """
    clean_query = query.strip()
    norm_q = normalize_text_assistant(clean_query)

    # 1. Obtener contexto del deportista
    athlete = extract_athlete_context(clean_query, active_athlete_name)
    weight_kg = athlete.get("weight_kg", 80.8)
    ffm_kg = athlete.get("ffm_kg", 70.5)
    bmr = athlete.get("bmr_cunningham", 2051)
    athlete_name = athlete.get("name", "Deportista ANyD")

    # 2. Comprobar si es una consulta sobre PROTEÍNA o DIRECTRICES ISSN
    if any(k in norm_q for k in ["proteina", "proteínas", "issn", "leucina", "cuanta proteina", "g kg"]):
        goal = "rendimiento"
        if "definicion" in norm_q or "perder grasa" in norm_q or "deficit" in norm_q:
            goal = "definicion"
        elif "hipertrofia" in norm_q or "ganar musculo" in norm_q:
            goal = "hipertrofia"

        calc = diet_manager.calculate_metabolism(
            weight_kg=weight_kg,
            ffm_kg=ffm_kg,
            height_cm=athlete.get("height_cm", 178),
            age=athlete.get("age", 25),
            gender="M",
            pal=1.5,
            goal=goal
        )
        issn = calc.get("issn_guidelines", {})

        reply = f"""### 🥩 Prescripción Proteica ISSN para **{athlete_name}** ({weight_kg:.1f} kg)

Según el **Posicionamiento Oficial de la ISSN (Jäger et al., 2017)**:

* **Objetivo Proteico Diario:** **{calc['target_protein_g']} g/día** 
  * Ratio por peso total: **{calc['protein_g_kg']} g/kg/día**
  * Ratio por Masa Magra (FFM Tanita MC-580): **{issn.get('protein_g_kg_ffm', 2.1)} g/kg FFM**
* **Fraccionamiento Óptimo:** Reparto homogéneo cada **3 a 4 horas** en 4–5 comidas.
* **Dosis por Toma:** **{issn.get('dose_per_meal_g', 30)} g de proteína neta por comida** (rango seguro: {issn.get('dose_range_per_meal', '20 - 32 g')}).
* **Umbral de Leucina (*Leucine Trigger*):** Mínimo **2.700 mg de leucina** en cada comida principal para activar la vía celular **mTORC1** y la síntesis proteica muscular (MPS).
* **Proteína Pre-Sueño (*Pre-Sleep*):** **{issn.get('pre_sleep_protein_g', 35)} g** de proteína de absorción sostenida (queso fresco batido 0% o requesón desnatado) 30–45 min antes de acostarse para sostener la MPS nocturna.
* **Disponibilidad Energética (EA):** **{issn.get('energy_availability_kcal_ffm', 36.5)} kcal/kg FFM/día** ({issn.get('energy_availability_status', 'Óptima')}).
"""
        return {
            "success": True,
            "type": "protein_issn",
            "reply_markdown": reply,
            "athlete_name": athlete_name,
            "metrics": {
                "target_protein_g": calc['target_protein_g'],
                "protein_g_kg": calc['protein_g_kg'],
                "dose_per_meal_g": issn.get('dose_per_meal_g'),
                "leucine_mg": 2700,
                "pre_sleep_g": 35.0
            }
        }

    # 3. Comprobar si es una consulta sobre SUPLEMENTACIÓN (Creatina, Cafeína, Beta-alanina, Sodio)
    if any(k in norm_q for k in ["creatina", "cafeina", "cafeína", "beta alanina", "suplementos", "suplementacion"]):
        caf_min = round(weight_kg * 3.0)
        caf_max = round(weight_kg * 6.0)
        reply = f"""### ⚡ Protocolo de Suplementación Ergonutricional (ISSN & AIS Grupo A) para **{athlete_name}** ({weight_kg:.1f} kg)

* **Creatina Monohidrato Creapure (Kreider et al., 2017):**
  * Dosis fija continua: **5.0 g/día** (0.05–0.07 g/kg).
  * Momento: Inmediatamente post-entreno en cena o batido con hidratos para optimizar la captación vía transportadores dependientes de insulina y sodio.
* **Cafeína Anhidra (Guest et al., 2021):**
  * Dosis ergogénica: **{caf_min} a {caf_max} mg** (3 a 6 mg/kg).
  * Momento: 45 a 60 minutos antes de entrenamientos clave o partidos para elevar el reclutamiento motor y reducir el RPE.
* **Beta-Alanina (Trexler et al., 2015):**
  * Dosis: **3.2 g/día** repartidos en 2 tomas de 1.6 g con las comidas para saturar la carnosina intramuscular sin parestesias.
* **Sodio y Electrolitos:**
  * **500 a 700 mg de Sodio/hora** en sesiones de alta intensidad o superiores a 60 min.
"""
        return {
            "success": True,
            "type": "supplements_issn",
            "reply_markdown": reply,
            "athlete_name": athlete_name,
            "metrics": {
                "creatine_g": 5.0,
                "caffeine_mg": f"{caf_min} - {caf_max} mg",
                "beta_alanine_g": 3.2,
                "sodium_mg_h": 500
            }
        }

    # 4. CONSULTA DE ACTIVIDAD FÍSICA Y COSTE ENERGÉTICO (Pilates máquina, fútbol, fuerza, carrera, etc.)
    activity = find_matching_activity(clean_query)
    duration_min = extract_duration_minutes(clean_query)

    if not activity:
        # Fallback genérico a actividad física moderada
        activity = COMPENDIUM_ACTIVITIES[0]  # Pilates Máquina por defecto si se mencionó pilates
        if "pilates" in norm_q:
            activity = COMPENDIUM_ACTIVITIES[0]

    mets = activity["mets"]
    
    # FÓRMULA OFICIAL DEL COMPENDIO ACSM:
    # Kcal bruta = (METs * 3.5 * peso_kg * minutos) / 200
    gross_kcal = round((mets * 3.5 * weight_kg * duration_min) / 200.0, 1)

    # GASTO BASAL EN ESE INTERVALO (Cunningham / Tanita):
    # Basal por hora = BMR / 24
    basal_hour_kcal = round((bmr / 24.0) * (duration_min / 60.0), 1)

    # COSTE ENERGÉTICO NETO ATRIBUIBLE EXCLUSIVAMENTE AL EJERCICIO:
    net_kcal = round(max(0.0, gross_kcal - basal_hour_kcal), 1)

    # RECOMENDACIONES PERI-ENTRENO SEGÚN INTENSIDAD
    hours = duration_min / 60.0
    pre_cho_g = round(weight_kg * activity["cho_target_g_kg"])
    intra_fluid_ml = round(activity["intra_fluid_ml_h"] * hours)
    intra_sodium_mg = round(activity["intra_sodium_mg_h"] * hours)
    post_cho_g = round(weight_kg * activity["post_cho_g_kg"])
    post_pro_g = round(weight_kg * activity["post_pro_g_kg"])

    # Formateo de duración legible
    if duration_min % 60 == 0:
        h_str = f"{duration_min // 60} hora" if duration_min == 60 else f"{duration_min // 60} horas"
    else:
        h_str = f"{duration_min} minutos"

    reply = f"""### 📊 Análisis de Coste Energético: **{activity['name_es']}**

* **Deportista evaluado:** **{athlete_name}**
* **Parámetros Antropométricos:** Peso: **{weight_kg:.1f} kg** | Masa Magra (FFM): **{ffm_kg:.1f} kg** | TMB Cunningham: **{bmr} kcal/día**
* **Duración de la sesión:** **{h_str} ({duration_min} min)**
* **Código Compendio ACSM:** `{activity['code']}` ({activity['category']})
* **Intensidad Metabólica:** **{mets:.1f} METs** ({activity['intensity_level']})

---

#### ⚡ Balance de Gasto Calórico
* **Gasto Energético Total (Bruto):** **{gross_kcal:.0f} kcal**
* **Gasto Metabólico Basal en reposo ({h_str}):** **{basal_hour_kcal:.0f} kcal** (metabolismo de base Cunningham)
* **Coste Energético Neto del Ejercicio:** **{net_kcal:.0f} kcal netas** (gasto real añadido por la actividad física)

---

#### 🥤 Pauta Nutricional & Hidratación Peri-Esfuerzo (ANyD / ISSN)
1. **Pre-Sesión (1.5–2h antes):** {pre_cho_g} g de carbohidratos ligeros de bajo residuo fibroso y fácil digestión.
2. **Intra-Sesión ({h_str}):**
   * Hidratación estimada: **{intra_fluid_ml} ml** de agua mineral.
   * Reposición electrolítica: **{intra_sodium_mg} mg de Sodio** {f'({activity["intra_cho_g_h"]}g CHO/h)' if activity["intra_cho_g_h"] > 0 else '(sin necesidad de azúcares intra-sesión)'}.
3. **Post-Sesión (Recuperación):**
   * Ratio de Recuperación: **{activity['post_ratio']}** (Carbohidratos:Proteína).
   * Aporte sugerido: **{post_pro_g} g de proteína magra** + **{post_cho_g} g de hidratos** para optimizar la síntesis proteica miofibrilar y la estabilización del glucógeno.

> *Referencia Científica:* {activity['evidence']}.
"""

    return {
        "success": True,
        "type": "exercise_energy_cost",
        "athlete_name": athlete_name,
        "activity_name": activity["name_es"],
        "acsm_code": activity["code"],
        "mets": mets,
        "duration_min": duration_min,
        "gross_kcal": round(gross_kcal),
        "net_kcal": round(net_kcal),
        "basal_kcal": round(basal_hour_kcal),
        "intensity_level": activity["intensity_level"],
        "intra_fluid_ml": intra_fluid_ml,
        "intra_sodium_mg": intra_sodium_mg,
        "post_ratio": activity["post_ratio"],
        "post_pro_g": post_pro_g,
        "post_cho_g": post_cho_g,
        "reply_markdown": reply
    }
