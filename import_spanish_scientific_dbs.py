# -*- coding: utf-8 -*-
"""
Script de Importación y Consolidación de Bases de Datos Nutricionales Españolas:
1. CESNID (Universitat de Barcelona) - Platos y recetas tradicionales españolas
2. Tablas de Moreiras (Universidad Complutense de Madrid - UCM) - Medidas caseras y gastronomía
3. MAPA / FEN (Ministerio de Agricultura, Pesca y Alimentación & Fundación Española de la Nutrición) - DOP/IGP
4. Open Food Facts España (OFF España) - Productos de supermercado (Mercadona/Hacendado, Carrefour, Lidl...)

Integración en anyd_booking.db y sincronización con Google Drive.
"""
import sqlite3
import csv
import os

DB_PATH = "anyd_booking.db"
CSV_LOCAL = os.path.join("data", "Dietowin_Alimentos_Maestro_Consolidado.csv")
CSV_GDRIVE = r"G:\Mi unidad\1.- ANyD\Dietowin_Alimentos_Maestro_Consolidado.csv"

def upgrade_schema(conn):
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(diet_foods)")
    columns = [col[1] for col in cursor.fetchall()]
    
    new_cols = [
        ("marca", "TEXT DEFAULT 'Genérico'"),
        ("codigo_barras", "TEXT DEFAULT ''"),
        ("medida_casera", "TEXT DEFAULT ''"),
        ("nova_group", "INTEGER DEFAULT 1")
    ]
    for col_name, col_type in new_cols:
        if col_name not in columns:
            cursor.execute(f"ALTER TABLE diet_foods ADD COLUMN {col_name} {col_type}")
            print(f"Columna '{col_name}' añadida con éxito a diet_foods.")
    conn.commit()

# --- 1. CESNID & TABLAS DE MOREIRAS (PLATOS TRADICIONALES Y MEDIDAS CASERAS) ---
CESNID_MOREIRAS_ITEMS = [
    {
        "nombre": "Tortilla de patatas con cebolla tradicional (al AOVE)",
        "familia": "Platos Tradicionales Españoles",
        "marca": "Casero / Tradicional",
        "codigo_barras": "",
        "medida_casera": "1 ración generosa (150g) o pincho de tortilla (100g)",
        "nova_group": 2,
        "fuente_datos": "Tablas de Moreiras (UCM) & CESNID (UB)",
        "kcal": 172.0, "energia_kj": 720.0, "proteina_g": 5.8, "carbohidratos_g": 14.2, "grasa_g": 10.4,
        "fibra_g": 1.4, "agua_g": 67.0, "grasa_sat_g": 2.2, "grasa_mono_g": 6.8, "grasa_poli_g": 1.1,
        "colesterol_mg": 125.0, "calcio_mg": 32.0, "hierro_mg": 1.3, "magnesio_mg": 21.0, "potasio_mg": 280.0,
        "sodio_mg": 240.0, "fosforo_mg": 95.0, "zinc_mg": 0.8, "selenio_ug": 8.5, "vitamina_a_ug": 95.0,
        "vitamina_d_ug": 0.7, "vitamina_e_mg": 2.4, "vitamina_c_mg": 7.0, "vitamina_b1_mg": 0.08,
        "vitamina_b2_mg": 0.15, "vitamina_b3_mg": 1.2, "vitamina_b6_mg": 0.22, "folatos_b9_ug": 22.0, "vitamina_b12_ug": 0.65
    },
    {
        "nombre": "Tortilla de patatas sin cebolla tradicional",
        "familia": "Platos Tradicionales Españoles",
        "marca": "Casero / Tradicional",
        "codigo_barras": "",
        "medida_casera": "1 ración generosa (150g)",
        "nova_group": 2,
        "fuente_datos": "Tablas de Moreiras (UCM) & CESNID (UB)",
        "kcal": 168.0, "energia_kj": 703.0, "proteina_g": 6.0, "carbohidratos_g": 13.8, "grasa_g": 10.1,
        "fibra_g": 1.2, "agua_g": 68.0, "grasa_sat_g": 2.1, "grasa_mono_g": 6.7, "grasa_poli_g": 1.0,
        "colesterol_mg": 130.0, "calcio_mg": 30.0, "hierro_mg": 1.2, "magnesio_mg": 20.0, "potasio_mg": 270.0,
        "sodio_mg": 235.0, "fosforo_mg": 98.0, "zinc_mg": 0.8, "selenio_ug": 8.7, "vitamina_a_ug": 98.0,
        "vitamina_d_ug": 0.75, "vitamina_e_mg": 2.3, "vitamina_c_mg": 5.5, "vitamina_b1_mg": 0.07,
        "vitamina_b2_mg": 0.16, "vitamina_b3_mg": 1.1, "vitamina_b6_mg": 0.21, "folatos_b9_ug": 19.0, "vitamina_b12_ug": 0.68
    },
    {
        "nombre": "Tortilla francesa tradicional (2 huevos camperos)",
        "familia": "Platos Tradicionales Españoles",
        "marca": "Casero / Tradicional",
        "codigo_barras": "",
        "medida_casera": "1 tortilla individual (110g)",
        "nova_group": 2,
        "fuente_datos": "Tablas de Moreiras (UCM)",
        "kcal": 154.0, "energia_kj": 644.0, "proteina_g": 11.5, "carbohidratos_g": 0.7, "grasa_g": 11.8,
        "fibra_g": 0.0, "agua_g": 74.0, "grasa_sat_g": 3.1, "grasa_mono_g": 6.5, "grasa_poli_g": 1.7,
        "colesterol_mg": 380.0, "calcio_mg": 55.0, "hierro_mg": 2.0, "magnesio_mg": 12.0, "potasio_mg": 140.0,
        "sodio_mg": 280.0, "fosforo_mg": 200.0, "zinc_mg": 1.8, "selenio_ug": 28.0, "vitamina_a_ug": 220.0,
        "vitamina_d_ug": 1.8, "vitamina_e_mg": 2.1, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.09,
        "vitamina_b2_mg": 0.35, "vitamina_b3_mg": 0.2, "vitamina_b6_mg": 0.14, "folatos_b9_ug": 45.0, "vitamina_b12_ug": 1.9
    },
    {
        "nombre": "Lentejas estofadas con verduras de la huerta (sin embutido)",
        "familia": "Platos Tradicionales Españoles",
        "marca": "Casero / Tradicional",
        "codigo_barras": "",
        "medida_casera": "1 plato hondo (250g) o 1 cucharón (80g)",
        "nova_group": 2,
        "fuente_datos": "CESNID (Universitat de Barcelona)",
        "kcal": 94.0, "energia_kj": 393.0, "proteina_g": 5.9, "carbohidratos_g": 13.2, "grasa_g": 2.1,
        "fibra_g": 3.8, "agua_g": 74.0, "grasa_sat_g": 0.3, "grasa_mono_g": 1.4, "grasa_poli_g": 0.3,
        "colesterol_mg": 0.0, "calcio_mg": 28.0, "hierro_mg": 2.5, "magnesio_mg": 24.0, "potasio_mg": 310.0,
        "sodio_mg": 210.0, "fosforo_mg": 95.0, "zinc_mg": 0.9, "selenio_ug": 4.5, "vitamina_a_ug": 120.0,
        "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.8, "vitamina_c_mg": 8.5, "vitamina_b1_mg": 0.12,
        "vitamina_b2_mg": 0.06, "vitamina_b3_mg": 1.1, "vitamina_b6_mg": 0.18, "folatos_b9_ug": 62.0, "vitamina_b12_ug": 0.0
    },
    {
        "nombre": "Potaje de garbanzos con espinacas y bacalao desmigado",
        "familia": "Platos Tradicionales Españoles",
        "marca": "Casero / Tradicional",
        "codigo_barras": "",
        "medida_casera": "1 plato hondo (250g)",
        "nova_group": 2,
        "fuente_datos": "Tablas de Moreiras (UCM) & CESNID (UB)",
        "kcal": 118.0, "energia_kj": 494.0, "proteina_g": 7.8, "carbohidratos_g": 13.5, "grasa_g": 3.8,
        "fibra_g": 3.4, "agua_g": 71.0, "grasa_sat_g": 0.6, "grasa_mono_g": 2.4, "grasa_poli_g": 0.5,
        "colesterol_mg": 15.0, "calcio_mg": 58.0, "hierro_mg": 2.1, "magnesio_mg": 32.0, "potasio_mg": 340.0,
        "sodio_mg": 320.0, "fosforo_mg": 110.0, "zinc_mg": 1.1, "selenio_ug": 9.5, "vitamina_a_ug": 180.0,
        "vitamina_d_ug": 0.4, "vitamina_e_mg": 1.2, "vitamina_c_mg": 9.0, "vitamina_b1_mg": 0.11,
        "vitamina_b2_mg": 0.08, "vitamina_b3_mg": 1.8, "vitamina_b6_mg": 0.20, "folatos_b9_ug": 55.0, "vitamina_b12_ug": 0.45
    },
    {
        "nombre": "Cocido madrileño desgrasado (caldo, garbanzos y carnes magras)",
        "familia": "Platos Tradicionales Españoles",
        "marca": "Casero / Tradicional",
        "codigo_barras": "",
        "medida_casera": "1 plato hondo completo (300g)",
        "nova_group": 2,
        "fuente_datos": "Tablas de Moreiras (UCM)",
        "kcal": 105.0, "energia_kj": 439.0, "proteina_g": 6.5, "carbohidratos_g": 12.0, "grasa_g": 3.5,
        "fibra_g": 2.9, "agua_g": 73.0, "grasa_sat_g": 0.9, "grasa_mono_g": 2.0, "grasa_poli_g": 0.4,
        "colesterol_mg": 18.0, "calcio_mg": 42.0, "hierro_mg": 1.8, "magnesio_mg": 26.0, "potasio_mg": 290.0,
        "sodio_mg": 310.0, "fosforo_mg": 105.0, "zinc_mg": 1.3, "selenio_ug": 7.0, "vitamina_a_ug": 65.0,
        "vitamina_d_ug": 0.2, "vitamina_e_mg": 0.7, "vitamina_c_mg": 4.0, "vitamina_b1_mg": 0.10,
        "vitamina_b2_mg": 0.09, "vitamina_b3_mg": 2.1, "vitamina_b6_mg": 0.19, "folatos_b9_ug": 42.0, "vitamina_b12_ug": 0.55
    },
    {
        "nombre": "Gazpacho andaluz tradicional con AOVE y hortalizas",
        "familia": "Platos Tradicionales Españoles",
        "marca": "Casero / Tradicional",
        "codigo_barras": "",
        "medida_casera": "1 vaso grande (200ml) o cuenco (250ml)",
        "nova_group": 2,
        "fuente_datos": "CESNID (Universitat de Barcelona)",
        "kcal": 48.0, "energia_kj": 201.0, "proteina_g": 0.9, "carbohidratos_g": 3.5, "grasa_g": 3.4,
        "fibra_g": 1.2, "agua_g": 90.0, "grasa_sat_g": 0.5, "grasa_mono_g": 2.4, "grasa_poli_g": 0.4,
        "colesterol_mg": 0.0, "calcio_mg": 14.0, "hierro_mg": 0.5, "magnesio_mg": 11.0, "potasio_mg": 210.0,
        "sodio_mg": 180.0, "fosforo_mg": 22.0, "zinc_mg": 0.3, "selenio_ug": 1.2, "vitamina_a_ug": 85.0,
        "vitamina_d_ug": 0.0, "vitamina_e_mg": 1.5, "vitamina_c_mg": 25.0, "vitamina_b1_mg": 0.05,
        "vitamina_b2_mg": 0.04, "vitamina_b3_mg": 0.7, "vitamina_b6_mg": 0.12, "folatos_b9_ug": 20.0, "vitamina_b12_ug": 0.0
    },
    {
        "nombre": "Salmorejo cordobés tradicional con AOVE virgen extra",
        "familia": "Platos Tradicionales Españoles",
        "marca": "Casero / Tradicional",
        "codigo_barras": "",
        "medida_casera": "1 cuenco mediano (180g)",
        "nova_group": 2,
        "fuente_datos": "CESNID (Universitat de Barcelona)",
        "kcal": 88.0, "energia_kj": 368.0, "proteina_g": 1.8, "carbohidratos_g": 8.2, "grasa_g": 5.5,
        "fibra_g": 1.1, "agua_g": 82.0, "grasa_sat_g": 0.8, "grasa_mono_g": 3.9, "grasa_poli_g": 0.6,
        "colesterol_mg": 0.0, "calcio_mg": 18.0, "hierro_mg": 0.7, "magnesio_mg": 14.0, "potasio_mg": 225.0,
        "sodio_mg": 220.0, "fosforo_mg": 35.0, "zinc_mg": 0.4, "selenio_ug": 2.0, "vitamina_a_ug": 95.0,
        "vitamina_d_ug": 0.0, "vitamina_e_mg": 2.2, "vitamina_c_mg": 18.0, "vitamina_b1_mg": 0.06,
        "vitamina_b2_mg": 0.05, "vitamina_b3_mg": 0.9, "vitamina_b6_mg": 0.15, "folatos_b9_ug": 24.0, "vitamina_b12_ug": 0.0
    },
    {
        "nombre": "Pisto manchego tradicional con tomate, calabacín y pimientos",
        "familia": "Platos Tradicionales Españoles",
        "marca": "Casero / Tradicional",
        "codigo_barras": "",
        "medida_casera": "1 plato o ración (180g)",
        "nova_group": 2,
        "fuente_datos": "Tablas de Moreiras (UCM)",
        "kcal": 62.0, "energia_kj": 259.0, "proteina_g": 1.4, "carbohidratos_g": 5.8, "grasa_g": 3.8,
        "fibra_g": 2.2, "agua_g": 86.0, "grasa_sat_g": 0.5, "grasa_mono_g": 2.7, "grasa_poli_g": 0.4,
        "colesterol_mg": 0.0, "calcio_mg": 24.0, "hierro_mg": 0.9, "magnesio_mg": 18.0, "potasio_mg": 280.0,
        "sodio_mg": 190.0, "fosforo_mg": 38.0, "zinc_mg": 0.4, "selenio_ug": 1.5, "vitamina_a_ug": 110.0,
        "vitamina_d_ug": 0.0, "vitamina_e_mg": 1.8, "vitamina_c_mg": 38.0, "vitamina_b1_mg": 0.06,
        "vitamina_b2_mg": 0.05, "vitamina_b3_mg": 0.9, "vitamina_b6_mg": 0.20, "folatos_b9_ug": 30.0, "vitamina_b12_ug": 0.0
    },
    {
        "nombre": "Paella valenciana tradicional de pollo, conejo y verdura (bajo en grasa)",
        "familia": "Platos Tradicionales Españoles",
        "marca": "Casero / Tradicional",
        "codigo_barras": "",
        "medida_casera": "1 plato raso (220g)",
        "nova_group": 2,
        "fuente_datos": "CESNID (Universitat de Barcelona)",
        "kcal": 155.0, "energia_kj": 648.0, "proteina_g": 8.4, "carbohidratos_g": 18.5, "grasa_g": 5.2,
        "fibra_g": 1.5, "agua_g": 65.0, "grasa_sat_g": 1.1, "grasa_mono_g": 3.2, "grasa_poli_g": 0.6,
        "colesterol_mg": 25.0, "calcio_mg": 26.0, "hierro_mg": 1.4, "magnesio_mg": 22.0, "potasio_mg": 230.0,
        "sodio_mg": 260.0, "fosforo_mg": 115.0, "zinc_mg": 1.2, "selenio_ug": 11.0, "vitamina_a_ug": 45.0,
        "vitamina_d_ug": 0.15, "vitamina_e_mg": 1.4, "vitamina_c_mg": 6.0, "vitamina_b1_mg": 0.10,
        "vitamina_b2_mg": 0.08, "vitamina_b3_mg": 3.2, "vitamina_b6_mg": 0.25, "folatos_b9_ug": 22.0, "vitamina_b12_ug": 0.40
    },
    {
        "nombre": "Merluza en salsa verde con almejas y perejil fresco",
        "familia": "Platos Tradicionales Españoles",
        "marca": "Casero / Tradicional",
        "codigo_barras": "",
        "medida_casera": "1 ración individual con salsa (200g)",
        "nova_group": 2,
        "fuente_datos": "CESNID (Universitat de Barcelona)",
        "kcal": 92.0, "energia_kj": 385.0, "proteina_g": 14.5, "carbohidratos_g": 2.1, "grasa_g": 2.8,
        "fibra_g": 0.4, "agua_g": 79.0, "grasa_sat_g": 0.4, "grasa_mono_g": 1.8, "grasa_poli_g": 0.4,
        "colesterol_mg": 45.0, "calcio_mg": 45.0, "hierro_mg": 1.8, "magnesio_mg": 28.0, "potasio_mg": 310.0,
        "sodio_mg": 280.0, "fosforo_mg": 170.0, "zinc_mg": 1.1, "selenio_ug": 26.0, "vitamina_a_ug": 40.0,
        "vitamina_d_ug": 1.2, "vitamina_e_mg": 1.0, "vitamina_c_mg": 12.0, "vitamina_b1_mg": 0.07,
        "vitamina_b2_mg": 0.08, "vitamina_b3_mg": 3.5, "vitamina_b6_mg": 0.22, "folatos_b9_ug": 18.0, "vitamina_b12_ug": 2.2
    },
    {
        "nombre": "Lubina al horno con patatas panaderas y cebolla al AOVE",
        "familia": "Platos Tradicionales Españoles",
        "marca": "Casero / Tradicional",
        "codigo_barras": "",
        "medida_casera": "1 lomo de lubina con guarnición (220g)",
        "nova_group": 2,
        "fuente_datos": "Tablas de Moreiras (UCM)",
        "kcal": 110.0, "energia_kj": 460.0, "proteina_g": 13.8, "carbohidratos_g": 6.2, "grasa_g": 3.4,
        "fibra_g": 0.9, "agua_g": 74.0, "grasa_sat_g": 0.6, "grasa_mono_g": 2.1, "grasa_poli_g": 0.5,
        "colesterol_mg": 48.0, "calcio_mg": 35.0, "hierro_mg": 1.1, "magnesio_mg": 25.0, "potasio_mg": 330.0,
        "sodio_mg": 210.0, "fosforo_mg": 165.0, "zinc_mg": 0.8, "selenio_ug": 24.0, "vitamina_a_ug": 30.0,
        "vitamina_d_ug": 2.5, "vitamina_e_mg": 1.2, "vitamina_c_mg": 8.0, "vitamina_b1_mg": 0.08,
        "vitamina_b2_mg": 0.10, "vitamina_b3_mg": 4.1, "vitamina_b6_mg": 0.30, "folatos_b9_ug": 15.0, "vitamina_b12_ug": 2.8
    },
    {
        "nombre": "Crema de calabacín y puerros con patata y AOVE",
        "familia": "Platos Tradicionales Españoles",
        "marca": "Casero / Tradicional",
        "codigo_barras": "",
        "medida_casera": "1 plato hondo (250g) o tazón (200g)",
        "nova_group": 2,
        "fuente_datos": "CESNID (Universitat de Barcelona)",
        "kcal": 44.0, "energia_kj": 184.0, "proteina_g": 1.2, "carbohidratos_g": 4.0, "grasa_g": 2.6,
        "fibra_g": 1.5, "agua_g": 90.0, "grasa_sat_g": 0.4, "grasa_mono_g": 1.8, "grasa_poli_g": 0.3,
        "colesterol_mg": 0.0, "calcio_mg": 22.0, "hierro_mg": 0.6, "magnesio_mg": 15.0, "potasio_mg": 220.0,
        "sodio_mg": 170.0, "fosforo_mg": 32.0, "zinc_mg": 0.3, "selenio_ug": 1.0, "vitamina_a_ug": 65.0,
        "vitamina_d_ug": 0.0, "vitamina_e_mg": 1.1, "vitamina_c_mg": 14.0, "vitamina_b1_mg": 0.05,
        "vitamina_b2_mg": 0.04, "vitamina_b3_mg": 0.8, "vitamina_b6_mg": 0.14, "folatos_b9_ug": 28.0, "vitamina_b12_ug": 0.0
    },
    {
        "nombre": "Judías verdes salteadas con patata cocida y ajo al AOVE",
        "familia": "Platos Tradicionales Españoles",
        "marca": "Casero / Tradicional",
        "codigo_barras": "",
        "medida_casera": "1 plato (200g)",
        "nova_group": 2,
        "fuente_datos": "Tablas de Moreiras (UCM)",
        "kcal": 58.0, "energia_kj": 242.0, "proteina_g": 1.8, "carbohidratos_g": 7.5, "grasa_g": 2.3,
        "fibra_g": 2.4, "agua_g": 86.0, "grasa_sat_g": 0.3, "grasa_mono_g": 1.6, "grasa_poli_g": 0.3,
        "colesterol_mg": 0.0, "calcio_mg": 38.0, "hierro_mg": 1.0, "magnesio_mg": 21.0, "potasio_mg": 290.0,
        "sodio_mg": 160.0, "fosforo_mg": 45.0, "zinc_mg": 0.4, "selenio_ug": 1.1, "vitamina_a_ug": 50.0,
        "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.9, "vitamina_c_mg": 16.0, "vitamina_b1_mg": 0.07,
        "vitamina_b2_mg": 0.06, "vitamina_b3_mg": 1.0, "vitamina_b6_mg": 0.18, "folatos_b9_ug": 35.0, "vitamina_b12_ug": 0.0
    },
    {
        "nombre": "Pan con tomate y aceite de oliva virgen extra (Pa amb tomàquet)",
        "familia": "Platos Tradicionales Españoles",
        "marca": "Casero / Tradicional",
        "codigo_barras": "",
        "medida_casera": "1 rebanada de pan payés/candeal (60g)",
        "nova_group": 2,
        "fuente_datos": "CESNID (Universitat de Barcelona)",
        "kcal": 228.0, "energia_kj": 954.0, "proteina_g": 5.2, "carbohidratos_g": 32.5, "grasa_g": 8.6,
        "fibra_g": 2.8, "agua_g": 50.0, "grasa_sat_g": 1.2, "grasa_mono_g": 6.2, "grasa_poli_g": 0.9,
        "colesterol_mg": 0.0, "calcio_mg": 25.0, "hierro_mg": 1.5, "magnesio_mg": 22.0, "potasio_mg": 160.0,
        "sodio_mg": 320.0, "fosforo_mg": 68.0, "zinc_mg": 0.6, "selenio_ug": 14.0, "vitamina_a_ug": 25.0,
        "vitamina_d_ug": 0.0, "vitamina_e_mg": 2.0, "vitamina_c_mg": 4.5, "vitamina_b1_mg": 0.12,
        "vitamina_b2_mg": 0.05, "vitamina_b3_mg": 1.6, "vitamina_b6_mg": 0.10, "folatos_b9_ug": 28.0, "vitamina_b12_ug": 0.0
    }
]

# --- 2. MAPA / FEN (ALIMENTOS AUTÓCTONOS, DENOMINACIONES DE ORIGEN DOP/IGP) ---
MAPA_FEN_ITEMS = [
    {
        "nombre": "Lenteja Pardina de Tierra de Campos (IGP) - Grano seco",
        "familia": "Legumbres con IGP",
        "marca": "Alimentos de España (MAPA)",
        "codigo_barras": "",
        "medida_casera": "1 ración cruda (70g) o 1 cucharón cocido (80g)",
        "nova_group": 1,
        "fuente_datos": "MAPA / FEN (Alimentos Tradicionales)",
        "kcal": 310.0, "energia_kj": 1297.0, "proteina_g": 24.2, "carbohidratos_g": 49.0, "grasa_g": 1.6,
        "fibra_g": 12.5, "agua_g": 11.5, "grasa_sat_g": 0.25, "grasa_mono_g": 0.35, "grasa_poli_g": 0.80,
        "colesterol_mg": 0.0, "calcio_mg": 65.0, "hierro_mg": 7.5, "magnesio_mg": 95.0, "potasio_mg": 880.0,
        "sodio_mg": 12.0, "fosforo_mg": 380.0, "zinc_mg": 3.4, "selenio_ug": 12.0, "vitamina_a_ug": 10.0,
        "vitamina_d_ug": 0.0, "vitamina_e_mg": 1.5, "vitamina_c_mg": 3.0, "vitamina_b1_mg": 0.48,
        "vitamina_b2_mg": 0.22, "vitamina_b3_mg": 2.6, "vitamina_b6_mg": 0.58, "folatos_b9_ug": 430.0, "vitamina_b12_ug": 0.0
    },
    {
        "nombre": "Garbanzo de Fuentesaúco (IGP) - Grano seco",
        "familia": "Legumbres con IGP",
        "marca": "Alimentos de España (MAPA)",
        "codigo_barras": "",
        "medida_casera": "1 ración cruda (70g) o 1 plato cocido (200g)",
        "nova_group": 1,
        "fuente_datos": "MAPA / FEN (Alimentos Tradicionales)",
        "kcal": 345.0, "energia_kj": 1443.0, "proteina_g": 20.8, "carbohidratos_g": 50.5, "grasa_g": 5.8,
        "fibra_g": 14.0, "agua_g": 10.0, "grasa_sat_g": 0.8, "grasa_mono_g": 1.9, "grasa_poli_g": 2.6,
        "colesterol_mg": 0.0, "calcio_mg": 130.0, "hierro_mg": 6.8, "magnesio_mg": 115.0, "potasio_mg": 790.0,
        "sodio_mg": 22.0, "fosforo_mg": 360.0, "zinc_mg": 3.1, "selenio_ug": 14.0, "vitamina_a_ug": 25.0,
        "vitamina_d_ug": 0.0, "vitamina_e_mg": 2.8, "vitamina_c_mg": 4.0, "vitamina_b1_mg": 0.45,
        "vitamina_b2_mg": 0.18, "vitamina_b3_mg": 1.8, "vitamina_b6_mg": 0.52, "folatos_b9_ug": 480.0, "vitamina_b12_ug": 0.0
    },
    {
        "nombre": "Faba Asturiana (IGP) - Grano seco granja",
        "familia": "Legumbres con IGP",
        "marca": "Alimentos de España (MAPA)",
        "codigo_barras": "",
        "medida_casera": "1 ración cruda (70g)",
        "nova_group": 1,
        "fuente_datos": "MAPA / FEN (Alimentos Tradicionales)",
        "kcal": 315.0, "energia_kj": 1318.0, "proteina_g": 21.0, "carbohidratos_g": 52.0, "grasa_g": 1.8,
        "fibra_g": 15.5, "agua_g": 11.0, "grasa_sat_g": 0.3, "grasa_mono_g": 0.3, "grasa_poli_g": 0.9,
        "colesterol_mg": 0.0, "calcio_mg": 110.0, "hierro_mg": 6.5, "magnesio_mg": 125.0, "potasio_mg": 1050.0,
        "sodio_mg": 15.0, "fosforo_mg": 410.0, "zinc_mg": 2.8, "selenio_ug": 10.0, "vitamina_a_ug": 5.0,
        "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.8, "vitamina_c_mg": 2.5, "vitamina_b1_mg": 0.50,
        "vitamina_b2_mg": 0.15, "vitamina_b3_mg": 2.2, "vitamina_b6_mg": 0.45, "folatos_b9_ug": 380.0, "vitamina_b12_ug": 0.0
    },
    {
        "nombre": "Jamón 100% Ibérico de Bellota (DOP Jabugo / Guijuelo / Dehesa)",
        "familia": "Carnes Ibéricas de Calidad",
        "marca": "DOP Alimentos de España",
        "codigo_barras": "",
        "medida_casera": "1 plato o ración de corte fino (50g - 8 a 10 lonchas)",
        "nova_group": 3,
        "fuente_datos": "MAPA / FEN (Alimentos Tradicionales)",
        "kcal": 335.0, "energia_kj": 1401.0, "proteina_g": 36.5, "carbohidratos_g": 0.1, "grasa_g": 21.0,
        "fibra_g": 0.0, "agua_g": 38.0, "grasa_sat_g": 6.5, "grasa_mono_g": 12.5, "grasa_poli_g": 1.8,
        "colesterol_mg": 70.0, "calcio_mg": 24.0, "hierro_mg": 2.8, "magnesio_mg": 22.0, "potasio_mg": 380.0,
        "sodio_mg": 1100.0, "fosforo_mg": 240.0, "zinc_mg": 2.5, "selenio_ug": 18.0, "vitamina_a_ug": 15.0,
        "vitamina_d_ug": 0.3, "vitamina_e_mg": 0.6, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.75,
        "vitamina_b2_mg": 0.22, "vitamina_b3_mg": 6.5, "vitamina_b6_mg": 0.45, "folatos_b9_ug": 8.0, "vitamina_b12_ug": 1.8
    },
    {
        "nombre": "Lomo Ibérico de Bellota embuchado curado",
        "familia": "Carnes Ibéricas de Calidad",
        "marca": "DOP Alimentos de España",
        "codigo_barras": "",
        "medida_casera": "5 lonchas medianas (50g)",
        "nova_group": 3,
        "fuente_datos": "MAPA / FEN (Alimentos Tradicionales)",
        "kcal": 310.0, "energia_kj": 1297.0, "proteina_g": 38.0, "carbohidratos_g": 0.5, "grasa_g": 17.5,
        "fibra_g": 0.0, "agua_g": 40.0, "grasa_sat_g": 5.2, "grasa_mono_g": 10.2, "grasa_poli_g": 1.5,
        "colesterol_mg": 65.0, "calcio_mg": 20.0, "hierro_mg": 2.4, "magnesio_mg": 26.0, "potasio_mg": 410.0,
        "sodio_mg": 980.0, "fosforo_mg": 250.0, "zinc_mg": 2.7, "selenio_ug": 20.0, "vitamina_a_ug": 12.0,
        "vitamina_d_ug": 0.25, "vitamina_e_mg": 0.5, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.85,
        "vitamina_b2_mg": 0.25, "vitamina_b3_mg": 7.8, "vitamina_b6_mg": 0.55, "folatos_b9_ug": 9.0, "vitamina_b12_ug": 1.6
    },
    {
        "nombre": "Ternera Gallega Suprema (IGP) - Babilla / Tapa magra",
        "familia": "Carnes con IGP",
        "marca": "Alimentos de España (MAPA)",
        "codigo_barras": "",
        "medida_casera": "1 filete mediano (150g) o 100g",
        "nova_group": 1,
        "fuente_datos": "MAPA / FEN (Alimentos Tradicionales)",
        "kcal": 118.0, "energia_kj": 494.0, "proteina_g": 21.5, "carbohidratos_g": 0.0, "grasa_g": 3.5,
        "fibra_g": 0.0, "agua_g": 74.5, "grasa_sat_g": 1.4, "grasa_mono_g": 1.6, "grasa_poli_g": 0.3,
        "colesterol_mg": 60.0, "calcio_mg": 12.0, "hierro_mg": 2.6, "magnesio_mg": 22.0, "potasio_mg": 350.0,
        "sodio_mg": 65.0, "fosforo_mg": 210.0, "zinc_mg": 4.2, "selenio_ug": 15.0, "vitamina_a_ug": 8.0,
        "vitamina_d_ug": 0.1, "vitamina_e_mg": 0.3, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.08,
        "vitamina_b2_mg": 0.20, "vitamina_b3_mg": 5.8, "vitamina_b6_mg": 0.38, "folatos_b9_ug": 12.0, "vitamina_b12_ug": 2.1
    },
    {
        "nombre": "Sardina atlántica / cantábrica fresca (Lonja española)",
        "familia": "Pescados de Lonja Española",
        "marca": "Pescado de España (MAPA)",
        "codigo_barras": "",
        "medida_casera": "3 a 4 sardinas medianas (150g peso neto limpio)",
        "nova_group": 1,
        "fuente_datos": "MAPA / FEN (Alimentos Tradicionales)",
        "kcal": 153.0, "energia_kj": 640.0, "proteina_g": 18.2, "carbohidratos_g": 0.0, "grasa_g": 9.0,
        "fibra_g": 0.0, "agua_g": 71.0, "grasa_sat_g": 2.5, "grasa_mono_g": 3.2, "grasa_poli_g": 2.8,
        "colesterol_mg": 75.0, "calcio_mg": 85.0, "hierro_mg": 2.2, "magnesio_mg": 29.0, "potasio_mg": 330.0,
        "sodio_mg": 95.0, "fosforo_mg": 260.0, "zinc_mg": 1.4, "selenio_ug": 42.0, "vitamina_a_ug": 62.0,
        "vitamina_d_ug": 7.5, "vitamina_e_mg": 1.6, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.12,
        "vitamina_b2_mg": 0.28, "vitamina_b3_mg": 9.2, "vitamina_b6_mg": 0.70, "folatos_b9_ug": 11.0, "vitamina_b12_ug": 8.9
    },
    {
        "nombre": "Bonito del Norte del Cantábrico fresco (Thunnus alalunga)",
        "familia": "Pescados de Lonja Española",
        "marca": "Pescado de España (MAPA)",
        "codigo_barras": "",
        "medida_casera": "1 rodaja o lomo limpio (150g)",
        "nova_group": 1,
        "fuente_datos": "MAPA / FEN (Alimentos Tradicionales)",
        "kcal": 138.0, "energia_kj": 577.0, "proteina_g": 24.5, "carbohidratos_g": 0.0, "grasa_g": 4.5,
        "fibra_g": 0.0, "agua_g": 70.0, "grasa_sat_g": 1.1, "grasa_mono_g": 1.5, "grasa_poli_g": 1.6,
        "colesterol_mg": 55.0, "calcio_mg": 15.0, "hierro_mg": 1.5, "magnesio_mg": 32.0, "potasio_mg": 360.0,
        "sodio_mg": 50.0, "fosforo_mg": 240.0, "zinc_mg": 1.1, "selenio_ug": 50.0, "vitamina_a_ug": 40.0,
        "vitamina_d_ug": 5.0, "vitamina_e_mg": 1.2, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.14,
        "vitamina_b2_mg": 0.15, "vitamina_b3_mg": 14.5, "vitamina_b6_mg": 0.85, "folatos_b9_ug": 15.0, "vitamina_b12_ug": 5.2
    },
    {
        "nombre": "Mejillón de Galicia (DOP) fresco cocido al vapor",
        "familia": "Pescados y Mariscos de Lonja",
        "marca": "DOP Mexillón de Galicia",
        "codigo_barras": "",
        "medida_casera": "1 ración de carne limpia de mejillón (120g ~ 12-15 uds)",
        "nova_group": 1,
        "fuente_datos": "MAPA / FEN (Alimentos Tradicionales)",
        "kcal": 86.0, "energia_kj": 360.0, "proteina_g": 11.9, "carbohidratos_g": 3.7, "grasa_g": 2.2,
        "fibra_g": 0.0, "agua_g": 80.5, "grasa_sat_g": 0.5, "grasa_mono_g": 0.4, "grasa_poli_g": 0.9,
        "colesterol_mg": 45.0, "calcio_mg": 80.0, "hierro_mg": 4.5, "magnesio_mg": 28.0, "potasio_mg": 270.0,
        "sodio_mg": 290.0, "fosforo_mg": 200.0, "zinc_mg": 1.8, "selenio_ug": 45.0, "vitamina_a_ug": 55.0,
        "vitamina_d_ug": 0.6, "vitamina_e_mg": 0.8, "vitamina_c_mg": 4.0, "vitamina_b1_mg": 0.16,
        "vitamina_b2_mg": 0.22, "vitamina_b3_mg": 2.5, "vitamina_b6_mg": 0.10, "folatos_b9_ug": 33.0, "vitamina_b12_ug": 8.0
    },
    {
        "nombre": "Queso Manchego semicurado (DOP)",
        "familia": "Quesos Tradicionales con DOP",
        "marca": "DOP Queso Manchego",
        "codigo_barras": "",
        "medida_casera": "1 cuña o porción estándar (40g)",
        "nova_group": 3,
        "fuente_datos": "MAPA / FEN (Alimentos Tradicionales)",
        "kcal": 382.0, "energia_kj": 1598.0, "proteina_g": 25.5, "carbohidratos_g": 1.2, "grasa_g": 31.0,
        "fibra_g": 0.0, "agua_g": 38.0, "grasa_sat_g": 19.5, "grasa_mono_g": 8.8, "grasa_poli_g": 1.4,
        "colesterol_mg": 90.0, "calcio_mg": 820.0, "hierro_mg": 1.2, "magnesio_mg": 38.0, "potasio_mg": 120.0,
        "sodio_mg": 680.0, "fosforo_mg": 520.0, "zinc_mg": 3.8, "selenio_ug": 14.0, "vitamina_a_ug": 290.0,
        "vitamina_d_ug": 0.45, "vitamina_e_mg": 0.5, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.04,
        "vitamina_b2_mg": 0.35, "vitamina_b3_mg": 1.1, "vitamina_b6_mg": 0.12, "folatos_b9_ug": 24.0, "vitamina_b12_ug": 1.5
    },
    {
        "nombre": "Aceite de Oliva Virgen Extra Monovarietal Picual (DOP Sierra de Cazorla)",
        "familia": "Aceites y Grasas de Calidad",
        "marca": "DOP Sierra de Cazorla",
        "codigo_barras": "",
        "medida_casera": "1 cucharada sopera (10-15g) o cucharadita postre (5g)",
        "nova_group": 2,
        "fuente_datos": "MAPA / FEN (Alimentos Tradicionales)",
        "kcal": 884.0, "energia_kj": 3699.0, "proteina_g": 0.0, "carbohidratos_g": 0.0, "grasa_g": 100.0,
        "fibra_g": 0.0, "agua_g": 0.0, "grasa_sat_g": 14.0, "grasa_mono_g": 79.0, "grasa_poli_g": 7.0,
        "colesterol_mg": 0.0, "calcio_mg": 1.0, "hierro_mg": 0.2, "magnesio_mg": 0.0, "potasio_mg": 1.0,
        "sodio_mg": 1.0, "fosforo_mg": 0.0, "zinc_mg": 0.0, "selenio_ug": 0.0, "vitamina_a_ug": 0.0,
        "vitamina_d_ug": 0.0, "vitamina_e_mg": 18.0, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.0,
        "vitamina_b2_mg": 0.0, "vitamina_b3_mg": 0.0, "vitamina_b6_mg": 0.0, "folatos_b9_ug": 0.0, "vitamina_b12_ug": 0.0
    },
    {
        "nombre": "Almendra Marcona cruda española (DOP / Calidad Nacional)",
        "familia": "Frutos Secos Nacionales",
        "marca": "Alimentos de España (MAPA)",
        "codigo_barras": "",
        "medida_casera": "1 puñado cerrado (25-30g ~ 20 almendras)",
        "nova_group": 1,
        "fuente_datos": "MAPA / FEN (Alimentos Tradicionales)",
        "kcal": 598.0, "energia_kj": 2502.0, "proteina_g": 20.5, "carbohidratos_g": 5.4, "grasa_g": 53.5,
        "fibra_g": 11.2, "agua_g": 5.0, "grasa_sat_g": 4.2, "grasa_mono_g": 36.5, "grasa_poli_g": 11.2,
        "colesterol_mg": 0.0, "calcio_mg": 252.0, "hierro_mg": 3.8, "magnesio_mg": 260.0, "potasio_mg": 780.0,
        "sodio_mg": 5.0, "fosforo_mg": 460.0, "zinc_mg": 3.2, "selenio_ug": 4.0, "vitamina_a_ug": 2.0,
        "vitamina_d_ug": 0.0, "vitamina_e_mg": 24.0, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.21,
        "vitamina_b2_mg": 0.65, "vitamina_b3_mg": 3.4, "vitamina_b6_mg": 0.12, "folatos_b9_ug": 48.0, "vitamina_b12_ug": 0.0
    }
]

# --- 3. OPEN FOOD FACTS ESPAÑA (MARCAS DE SUPERMERCADOS EN ESPAÑA: HACENDADO, CARREFOUR, LIDL...) ---
OFF_ESPANIA_ITEMS = [
    {
        "nombre": "Copos de Avena Suaves Hacendado",
        "familia": "Cereales y Desayuno",
        "marca": "Hacendado (Mercadona)",
        "codigo_barras": "8480000093850",
        "medida_casera": "1 bol mediano (50g) o 3 cucharadas soperas (30g)",
        "nova_group": 1,
        "fuente_datos": "Open Food Facts España",
        "kcal": 375.0, "energia_kj": 1569.0, "proteina_g": 13.5, "carbohidratos_g": 59.0, "grasa_g": 7.0,
        "fibra_g": 10.0, "agua_g": 8.0, "grasa_sat_g": 1.3, "grasa_mono_g": 2.5, "grasa_poli_g": 2.8,
        "colesterol_mg": 0.0, "calcio_mg": 52.0, "hierro_mg": 4.2, "magnesio_mg": 140.0, "potasio_mg": 360.0,
        "sodio_mg": 10.0, "fosforo_mg": 410.0, "zinc_mg": 3.2, "selenio_ug": 28.0, "vitamina_a_ug": 0.0,
        "vitamina_d_ug": 0.0, "vitamina_e_mg": 1.2, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.50,
        "vitamina_b2_mg": 0.14, "vitamina_b3_mg": 1.1, "vitamina_b6_mg": 0.15, "folatos_b9_ug": 35.0, "vitamina_b12_ug": 0.0
    },
    {
        "nombre": "Queso Fresco Batido 0% M.G. Hacendado",
        "familia": "Lácteos y Derivados",
        "marca": "Hacendado (Mercadona)",
        "codigo_barras": "8480000155695",
        "medida_casera": "1 tarrina individual (120g) o media tarrina grande (250g)",
        "nova_group": 1,
        "fuente_datos": "Open Food Facts España",
        "kcal": 46.0, "energia_kj": 192.0, "proteina_g": 8.0, "carbohidratos_g": 3.5, "grasa_g": 0.1,
        "fibra_g": 0.0, "agua_g": 87.5, "grasa_sat_g": 0.05, "grasa_mono_g": 0.02, "grasa_poli_g": 0.01,
        "colesterol_mg": 2.0, "calcio_mg": 120.0, "hierro_mg": 0.1, "magnesio_mg": 11.0, "potasio_mg": 145.0,
        "sodio_mg": 40.0, "fosforo_mg": 130.0, "zinc_mg": 0.5, "selenio_ug": 3.5, "vitamina_a_ug": 5.0,
        "vitamina_d_ug": 0.05, "vitamina_e_mg": 0.02, "vitamina_c_mg": 0.5, "vitamina_b1_mg": 0.04,
        "vitamina_b2_mg": 0.20, "vitamina_b3_mg": 0.2, "vitamina_b6_mg": 0.06, "folatos_b9_ug": 12.0, "vitamina_b12_ug": 0.45
    },
    {
        "nombre": "Claras de Huevo Pasteurizadas Líquidas Hacendado",
        "familia": "Huevos y Ovoproductos",
        "marca": "Hacendado (Mercadona)",
        "codigo_barras": "8480000650053",
        "medida_casera": "1 vaso estándar (150ml ~ 5 claras) o 100ml",
        "nova_group": 1,
        "fuente_datos": "Open Food Facts España",
        "kcal": 48.0, "energia_kj": 201.0, "proteina_g": 11.0, "carbohidratos_g": 0.7, "grasa_g": 0.1,
        "fibra_g": 0.0, "agua_g": 88.0, "grasa_sat_g": 0.02, "grasa_mono_g": 0.02, "grasa_poli_g": 0.01,
        "colesterol_mg": 0.0, "calcio_mg": 11.0, "hierro_mg": 0.2, "magnesio_mg": 12.0, "potasio_mg": 160.0,
        "sodio_mg": 165.0, "fosforo_mg": 18.0, "zinc_mg": 0.1, "selenio_ug": 20.0, "vitamina_a_ug": 0.0,
        "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.0, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.02,
        "vitamina_b2_mg": 0.42, "vitamina_b3_mg": 0.1, "vitamina_b6_mg": 0.04, "folatos_b9_ug": 6.0, "vitamina_b12_ug": 0.25
    },
    {
        "nombre": "Crema de Cacahuete 100% Cacahuete Tostado Hacendado",
        "familia": "Frutos Secos y Semillas",
        "marca": "Hacendado (Mercadona)",
        "codigo_barras": "8480000216174",
        "medida_casera": "1 cucharada sopera colmada (15-20g)",
        "nova_group": 1,
        "fuente_datos": "Open Food Facts España",
        "kcal": 618.0, "energia_kj": 2586.0, "proteina_g": 30.0, "carbohidratos_g": 7.0, "grasa_g": 50.0,
        "fibra_g": 9.0, "agua_g": 2.0, "grasa_sat_g": 6.8, "grasa_mono_g": 25.5, "grasa_poli_g": 15.5,
        "colesterol_mg": 0.0, "calcio_mg": 45.0, "hierro_mg": 2.2, "magnesio_mg": 180.0, "potasio_mg": 680.0,
        "sodio_mg": 10.0, "fosforo_mg": 390.0, "zinc_mg": 3.1, "selenio_ug": 6.0, "vitamina_a_ug": 0.0,
        "vitamina_d_ug": 0.0, "vitamina_e_mg": 9.0, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.28,
        "vitamina_b2_mg": 0.11, "vitamina_b3_mg": 13.5, "vitamina_b6_mg": 0.45, "folatos_b9_ug": 110.0, "vitamina_b12_ug": 0.0
    },
    {
        "nombre": "Pan de Molde 100% Integral Corteza Tierna Hacendado",
        "familia": "Panes y Cereales",
        "marca": "Hacendado (Mercadona)",
        "codigo_barras": "8480000824058",
        "medida_casera": "1 rebanada (40g) o 2 rebanadas (80g)",
        "nova_group": 3,
        "fuente_datos": "Open Food Facts España",
        "kcal": 235.0, "energia_kj": 983.0, "proteina_g": 9.5, "carbohidratos_g": 40.0, "grasa_g": 2.5,
        "fibra_g": 6.5, "agua_g": 38.0, "grasa_sat_g": 0.5, "grasa_mono_g": 0.7, "grasa_poli_g": 1.1,
        "colesterol_mg": 0.0, "calcio_mg": 60.0, "hierro_mg": 2.2, "magnesio_mg": 55.0, "potasio_mg": 220.0,
        "sodio_mg": 380.0, "fosforo_mg": 140.0, "zinc_mg": 1.5, "selenio_ug": 18.0, "vitamina_a_ug": 0.0,
        "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.8, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.22,
        "vitamina_b2_mg": 0.09, "vitamina_b3_mg": 3.2, "vitamina_b6_mg": 0.16, "folatos_b9_ug": 38.0, "vitamina_b12_ug": 0.0
    },
    {
        "nombre": "Tofu Firme Bio Hacendado (Mercadona)",
        "familia": "Proteínas Vegetales",
        "marca": "Hacendado (Mercadona)",
        "codigo_barras": "8480000164802",
        "medida_casera": "Medio bloque (100g) o bloque entero (200g)",
        "nova_group": 1,
        "fuente_datos": "Open Food Facts España",
        "kcal": 125.0, "energia_kj": 523.0, "proteina_g": 13.0, "carbohidratos_g": 1.5, "grasa_g": 7.5,
        "fibra_g": 1.5, "agua_g": 75.0, "grasa_sat_g": 1.1, "grasa_mono_g": 1.6, "grasa_poli_g": 4.5,
        "colesterol_mg": 0.0, "calcio_mg": 200.0, "hierro_mg": 2.7, "magnesio_mg": 58.0, "potasio_mg": 180.0,
        "sodio_mg": 15.0, "fosforo_mg": 190.0, "zinc_mg": 1.2, "selenio_ug": 9.0, "vitamina_a_ug": 0.0,
        "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.5, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.08,
        "vitamina_b2_mg": 0.05, "vitamina_b3_mg": 0.4, "vitamina_b6_mg": 0.09, "folatos_b9_ug": 28.0, "vitamina_b12_ug": 0.0
    },
    {
        "nombre": "Yogur Griego Natural 0% Grasa Hacendado",
        "familia": "Lácteos y Derivados",
        "marca": "Hacendado (Mercadona)",
        "codigo_barras": "8480000156944",
        "medida_casera": "1 unidad (125g)",
        "nova_group": 1,
        "fuente_datos": "Open Food Facts España",
        "kcal": 55.0, "energia_kj": 230.0, "proteina_g": 9.0, "carbohidratos_g": 4.5, "grasa_g": 0.2,
        "fibra_g": 0.0, "agua_g": 85.5, "grasa_sat_g": 0.1, "grasa_mono_g": 0.05, "grasa_poli_g": 0.02,
        "colesterol_mg": 3.0, "calcio_mg": 130.0, "hierro_mg": 0.1, "magnesio_mg": 12.0, "potasio_mg": 150.0,
        "sodio_mg": 45.0, "fosforo_mg": 140.0, "zinc_mg": 0.6, "selenio_ug": 4.0, "vitamina_a_ug": 8.0,
        "vitamina_d_ug": 0.05, "vitamina_e_mg": 0.02, "vitamina_c_mg": 0.5, "vitamina_b1_mg": 0.04,
        "vitamina_b2_mg": 0.22, "vitamina_b3_mg": 0.2, "vitamina_b6_mg": 0.06, "folatos_b9_ug": 14.0, "vitamina_b12_ug": 0.52
    },
    {
        "nombre": "Pechuga de Pavo 92% Carne en Lonchas Hacendado",
        "familia": "Embutidos Magros",
        "marca": "Hacendado (Mercadona)",
        "codigo_barras": "8480000506305",
        "medida_casera": "4 lonchas (80g) o 2 lonchas (40g)",
        "nova_group": 3,
        "fuente_datos": "Open Food Facts España",
        "kcal": 92.0, "energia_kj": 385.0, "proteina_g": 18.0, "carbohidratos_g": 1.5, "grasa_g": 1.2,
        "fibra_g": 0.0, "agua_g": 76.0, "grasa_sat_g": 0.4, "grasa_mono_g": 0.4, "grasa_poli_g": 0.3,
        "colesterol_mg": 40.0, "calcio_mg": 14.0, "hierro_mg": 1.1, "magnesio_mg": 18.0, "potasio_mg": 280.0,
        "sodio_mg": 680.0, "fosforo_mg": 170.0, "zinc_mg": 1.5, "selenio_ug": 16.0, "vitamina_a_ug": 5.0,
        "vitamina_d_ug": 0.1, "vitamina_e_mg": 0.2, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.06,
        "vitamina_b2_mg": 0.12, "vitamina_b3_mg": 5.2, "vitamina_b6_mg": 0.32, "folatos_b9_ug": 8.0, "vitamina_b12_ug": 0.85
    },
    {
        "nombre": "Skyr Natural Milbona (Lidl España)",
        "familia": "Lácteos y Derivados",
        "marca": "Milbona (Lidl)",
        "codigo_barras": "20542385",
        "medida_casera": "1 tarrina (150g) o 200g",
        "nova_group": 1,
        "fuente_datos": "Open Food Facts España",
        "kcal": 62.0, "energia_kj": 259.0, "proteina_g": 11.0, "carbohidratos_g": 4.0, "grasa_g": 0.2,
        "fibra_g": 0.0, "agua_g": 83.5, "grasa_sat_g": 0.1, "grasa_mono_g": 0.05, "grasa_poli_g": 0.02,
        "colesterol_mg": 2.0, "calcio_mg": 130.0, "hierro_mg": 0.1, "magnesio_mg": 12.0, "potasio_mg": 155.0,
        "sodio_mg": 40.0, "fosforo_mg": 150.0, "zinc_mg": 0.6, "selenio_ug": 4.5, "vitamina_a_ug": 5.0,
        "vitamina_d_ug": 0.05, "vitamina_e_mg": 0.02, "vitamina_c_mg": 0.5, "vitamina_b1_mg": 0.04,
        "vitamina_b2_mg": 0.24, "vitamina_b3_mg": 0.2, "vitamina_b6_mg": 0.07, "folatos_b9_ug": 15.0, "vitamina_b12_ug": 0.55
    },
    {
        "nombre": "Pan de Centeno 100% Integral Rivercote (Lidl)",
        "familia": "Panes y Cereales",
        "marca": "Rivercote (Lidl)",
        "codigo_barras": "20491829",
        "medida_casera": "1 rebanada gruesa (50g)",
        "nova_group": 3,
        "fuente_datos": "Open Food Facts España",
        "kcal": 198.0, "energia_kj": 828.0, "proteina_g": 5.8, "carbohidratos_g": 35.0, "grasa_g": 1.4,
        "fibra_g": 9.2, "agua_g": 45.0, "grasa_sat_g": 0.2, "grasa_mono_g": 0.3, "grasa_poli_g": 0.6,
        "colesterol_mg": 0.0, "calcio_mg": 40.0, "hierro_mg": 2.5, "magnesio_mg": 62.0, "potasio_mg": 290.0,
        "sodio_mg": 360.0, "fosforo_mg": 180.0, "zinc_mg": 1.9, "selenio_ug": 15.0, "vitamina_a_ug": 0.0,
        "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.6, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.24,
        "vitamina_b2_mg": 0.11, "vitamina_b3_mg": 2.4, "vitamina_b6_mg": 0.20, "folatos_b9_ug": 42.0, "vitamina_b12_ug": 0.0
    },
    {
        "nombre": "Copos de Avena Bio Carrefour",
        "familia": "Cereales y Desayuno",
        "marca": "Carrefour Bio",
        "codigo_barras": "3560070500894",
        "medida_casera": "1 bol (50g)",
        "nova_group": 1,
        "fuente_datos": "Open Food Facts España",
        "kcal": 370.0, "energia_kj": 1548.0, "proteina_g": 13.0, "carbohidratos_g": 58.0, "grasa_g": 7.0,
        "fibra_g": 10.0, "agua_g": 9.0, "grasa_sat_g": 1.2, "grasa_mono_g": 2.5, "grasa_poli_g": 2.9,
        "colesterol_mg": 0.0, "calcio_mg": 50.0, "hierro_mg": 4.0, "magnesio_mg": 138.0, "potasio_mg": 355.0,
        "sodio_mg": 10.0, "fosforo_mg": 400.0, "zinc_mg": 3.1, "selenio_ug": 27.0, "vitamina_a_ug": 0.0,
        "vitamina_d_ug": 0.0, "vitamina_e_mg": 1.1, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.48,
        "vitamina_b2_mg": 0.13, "vitamina_b3_mg": 1.0, "vitamina_b6_mg": 0.14, "folatos_b9_ug": 34.0, "vitamina_b12_ug": 0.0
    },
    {
        "nombre": "Atún Claro al Natural en Lata Hacendado",
        "familia": "Conservas de Pescado",
        "marca": "Hacendado (Mercadona)",
        "codigo_barras": "8480000184428",
        "medida_casera": "1 lata escurrida (52g) o pack de 2 latas (104g)",
        "nova_group": 3,
        "fuente_datos": "Open Food Facts España",
        "kcal": 102.0, "energia_kj": 427.0, "proteina_g": 24.0, "carbohidratos_g": 0.0, "grasa_g": 0.7,
        "fibra_g": 0.0, "agua_g": 73.5, "grasa_sat_g": 0.2, "grasa_mono_g": 0.2, "grasa_poli_g": 0.25,
        "colesterol_mg": 45.0, "calcio_mg": 12.0, "hierro_mg": 1.4, "magnesio_mg": 28.0, "potasio_mg": 290.0,
        "sodio_mg": 350.0, "fosforo_mg": 210.0, "zinc_mg": 0.9, "selenio_ug": 65.0, "vitamina_a_ug": 20.0,
        "vitamina_d_ug": 2.2, "vitamina_e_mg": 0.6, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.05,
        "vitamina_b2_mg": 0.10, "vitamina_b3_mg": 12.0, "vitamina_b6_mg": 0.45, "folatos_b9_ug": 10.0, "vitamina_b12_ug": 3.8
    },
    {
        "nombre": "Edamame Congelado Hacendado (Habas de Soja Tierna)",
        "familia": "Legumbres y Verduras",
        "marca": "Hacendado (Mercadona)",
        "codigo_barras": "8480000085442",
        "medida_casera": "1 bol con vainas (150g ~ 75g grano comestible)",
        "nova_group": 1,
        "fuente_datos": "Open Food Facts España",
        "kcal": 122.0, "energia_kj": 510.0, "proteina_g": 11.5, "carbohidratos_g": 6.5, "grasa_g": 5.0,
        "fibra_g": 5.5, "agua_g": 70.0, "grasa_sat_g": 0.7, "grasa_mono_g": 1.1, "grasa_poli_g": 2.6,
        "colesterol_mg": 0.0, "calcio_mg": 63.0, "hierro_mg": 2.3, "magnesio_mg": 64.0, "potasio_mg": 435.0,
        "sodio_mg": 8.0, "fosforo_mg": 169.0, "zinc_mg": 1.4, "selenio_ug": 1.5, "vitamina_a_ug": 15.0,
        "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.7, "vitamina_c_mg": 6.0, "vitamina_b1_mg": 0.20,
        "vitamina_b2_mg": 0.15, "vitamina_b3_mg": 0.9, "vitamina_b6_mg": 0.10, "folatos_b9_ug": 310.0, "vitamina_b12_ug": 0.0
    },
    {
        "nombre": "Chocolate Negro 85% Cacao Hacendado",
        "familia": "Cacao y Dulces",
        "marca": "Hacendado (Mercadona)",
        "codigo_barras": "8480000125742",
        "medida_casera": "1 onza (20g) o 2 onzas (40g)",
        "nova_group": 3,
        "fuente_datos": "Open Food Facts España",
        "kcal": 585.0, "energia_kj": 2448.0, "proteina_g": 9.0, "carbohidratos_g": 18.0, "grasa_g": 51.0,
        "fibra_g": 12.0, "agua_g": 1.5, "grasa_sat_g": 31.0, "grasa_mono_g": 16.5, "grasa_poli_g": 1.8,
        "colesterol_mg": 0.0, "calcio_mg": 60.0, "hierro_mg": 8.5, "magnesio_mg": 220.0, "potasio_mg": 710.0,
        "sodio_mg": 15.0, "fosforo_mg": 290.0, "zinc_mg": 3.3, "selenio_ug": 7.0, "vitamina_a_ug": 5.0,
        "vitamina_d_ug": 0.0, "vitamina_e_mg": 2.1, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.08,
        "vitamina_b2_mg": 0.12, "vitamina_b3_mg": 1.2, "vitamina_b6_mg": 0.05, "folatos_b9_ug": 25.0, "vitamina_b12_ug": 0.0
    }
]

def main():
    conn = sqlite3.connect(DB_PATH)
    upgrade_schema(conn)
    cursor = conn.cursor()

    all_new_items = CESNID_MOREIRAS_ITEMS + MAPA_FEN_ITEMS + OFF_ESPANIA_ITEMS
    print(f"Total de alimentos a procesar de bases españolas: {len(all_new_items)}")

    inserted = 0
    updated = 0

    for item in all_new_items:
        nombre = item["nombre"]
        cursor.execute("SELECT id FROM diet_foods WHERE nombre = ?", (nombre,))
        row = cursor.fetchone()

        if row:
            fid = row[0]
            cursor.execute("""
                UPDATE diet_foods SET
                    familia = :familia, marca = :marca, codigo_barras = :codigo_barras,
                    medida_casera = :medida_casera, nova_group = :nova_group, fuente_datos = :fuente_datos,
                    kcal = :kcal, energia_kj = :energia_kj, proteina_g = :proteina_g, carbohidratos_g = :carbohidratos_g,
                    grasa_g = :grasa_g, fibra_g = :fibra_g, agua_g = :agua_g, grasa_sat_g = :grasa_sat_g,
                    grasa_mono_g = :grasa_mono_g, grasa_poli_g = :grasa_poli_g, colesterol_mg = :colesterol_mg,
                    calcio_mg = :calcio_mg, hierro_mg = :hierro_mg, magnesio_mg = :magnesio_mg,
                    potasio_mg = :potasio_mg, sodio_mg = :sodio_mg, fosforo_mg = :fosforo_mg,
                    zinc_mg = :zinc_mg, selenio_ug = :selenio_ug, vitamina_a_ug = :vitamina_a_ug,
                    vitamina_d_ug = :vitamina_d_ug, vitamina_e_mg = :vitamina_e_mg, vitamina_c_mg = :vitamina_c_mg,
                    vitamina_b1_mg = :vitamina_b1_mg, vitamina_b2_mg = :vitamina_b2_mg, vitamina_b3_mg = :vitamina_b3_mg,
                    vitamina_b6_mg = :vitamina_b6_mg, folatos_b9_ug = :folatos_b9_ug, vitamina_b12_ug = :vitamina_b12_ug
                WHERE id = :id
            """, {**item, "id": fid})
            updated += 1
        else:
            cursor.execute("""
                INSERT INTO diet_foods (
                    nombre, familia, marca, codigo_barras, medida_casera, nova_group, fuente_datos,
                    kcal, energia_kj, proteina_g, carbohidratos_g, grasa_g, fibra_g, agua_g,
                    grasa_sat_g, grasa_mono_g, grasa_poli_g, colesterol_mg, calcio_mg, hierro_mg,
                    magnesio_mg, potasio_mg, sodio_mg, fosforo_mg, zinc_mg, selenio_ug,
                    vitamina_a_ug, vitamina_d_ug, vitamina_e_mg, vitamina_c_mg, vitamina_b1_mg,
                    vitamina_b2_mg, vitamina_b3_mg, vitamina_b6_mg, folatos_b9_ug, vitamina_b12_ug
                ) VALUES (
                    :nombre, :familia, :marca, :codigo_barras, :medida_casera, :nova_group, :fuente_datos,
                    :kcal, :energia_kj, :proteina_g, :carbohidratos_g, :grasa_g, :fibra_g, :agua_g,
                    :grasa_sat_g, :grasa_mono_g, :grasa_poli_g, :colesterol_mg, :calcio_mg, :hierro_mg,
                    :magnesio_mg, :potasio_mg, :sodio_mg, :fosforo_mg, :zinc_mg, :selenio_ug,
                    :vitamina_a_ug, :vitamina_d_ug, :vitamina_e_mg, :vitamina_c_mg, :vitamina_b1_mg,
                    :vitamina_b2_mg, :vitamina_b3_mg, :vitamina_b6_mg, :folatos_b9_ug, :vitamina_b12_ug
                )
            """, item)
            inserted += 1

    conn.commit()
    print(f"Bases españolas integradas: {inserted} nuevos insertados, {updated} actualizados.")

    # Exportar a CSV local y Google Drive con csv estándar
    cursor.execute("SELECT * FROM diet_foods ORDER BY id ASC")
    rows = cursor.fetchall()
    col_names = [description[0] for description in cursor.description]
    conn.close()

    def write_csv(filepath):
        with open(filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(col_names)
            writer.writerows(rows)

    write_csv(CSV_LOCAL)
    print(f"CSV local actualizado ({len(rows)} alimentos): {CSV_LOCAL}")

    try:
        write_csv(CSV_GDRIVE)
        print(f"CSV en Google Drive actualizado: {CSV_GDRIVE}")
    except Exception as e:
        print(f"Nota: No se pudo escribir en GDrive directamente: {e}")

if __name__ == "__main__":
    main()
