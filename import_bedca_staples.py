import sqlite3
import csv
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "anyd_booking.db"))
CSV_LOCAL = os.path.join(BASE_DIR, "data", "Dietowin_Alimentos_Maestro_Consolidado.csv")
CSV_GDRIVE = r"G:\Mi unidad\1.- ANyD\Dietowin_Alimentos_Maestro_Consolidado.csv"

# Lista canónica de los alimentos e ingredientes más comunes en consulta clínica y nutrición deportiva
# Fuentes de datos: BEDCA (Base de Datos Española de Composición de Alimentos) / CESNID / AESAN
BEDCA_STAPLE_FOODS = [
    # 1. CEREALES, GRANOS Y TUBÉRCULOS
    {
        "id": 1,
        "nombre": "Avena, copos integrales",
        "familia": "Cereales, Tubérculos y Derivados",
        "kcal": 367.0, "energia_kj": 1546.0, "proteina_g": 13.5, "carbohidratos_g": 58.7, "grasa_g": 7.0, "fibra_g": 10.0, "agua_g": 9.5,
        "grasa_sat_g": 1.3, "grasa_mono_g": 2.6, "grasa_poli_g": 2.8, "colesterol_mg": 0.0,
        "calcio_mg": 54.0, "hierro_mg": 4.7, "magnesio_mg": 139.0, "potasio_mg": 355.0, "sodio_mg": 2.0, "fosforo_mg": 410.0, "zinc_mg": 3.2, "selenio_ug": 12.0,
        "vitamina_a_ug": 0.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.8, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.5, "vitamina_b2_mg": 0.15, "vitamina_b3_mg": 1.1, "vitamina_b6_mg": 0.12, "folatos_b9_ug": 32.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 2,
        "nombre": "Arroz blanco",
        "familia": "Cereales, Tubérculos y Derivados",
        "kcal": 364.0, "energia_kj": 1547.0, "proteina_g": 7.0, "carbohidratos_g": 81.6, "grasa_g": 0.9, "fibra_g": 1.4, "agua_g": 12.0,
        "grasa_sat_g": 0.2, "grasa_mono_g": 0.3, "grasa_poli_g": 0.3, "colesterol_mg": 0.0,
        "calcio_mg": 10.0, "hierro_mg": 1.0, "magnesio_mg": 28.0, "potasio_mg": 105.0, "sodio_mg": 2.0, "fosforo_mg": 115.0, "zinc_mg": 1.1, "selenio_ug": 10.0,
        "vitamina_a_ug": 0.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.1, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.08, "vitamina_b2_mg": 0.03, "vitamina_b3_mg": 1.6, "vitamina_b6_mg": 0.15, "folatos_b9_ug": 9.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 3,
        "nombre": "Arroz integral",
        "familia": "Cereales, Tubérculos y Derivados",
        "kcal": 350.0, "energia_kj": 1480.0, "proteina_g": 7.5, "carbohidratos_g": 74.0, "grasa_g": 2.2, "fibra_g": 4.0, "agua_g": 11.5,
        "grasa_sat_g": 0.5, "grasa_mono_g": 0.8, "grasa_poli_g": 0.8, "colesterol_mg": 0.0,
        "calcio_mg": 23.0, "hierro_mg": 1.6, "magnesio_mg": 110.0, "potasio_mg": 215.0, "sodio_mg": 4.0, "fosforo_mg": 260.0, "zinc_mg": 1.5, "selenio_ug": 17.0,
        "vitamina_a_ug": 0.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.7, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.3, "vitamina_b2_mg": 0.05, "vitamina_b3_mg": 4.3, "vitamina_b6_mg": 0.3, "folatos_b9_ug": 20.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 4,
        "nombre": "Pasta alimenticia de trigo (macarrones / espaguetis)",
        "familia": "Cereales, Tubérculos y Derivados",
        "kcal": 360.0, "energia_kj": 1528.0, "proteina_g": 12.0, "carbohidratos_g": 72.0, "grasa_g": 1.8, "fibra_g": 3.6, "agua_g": 10.5,
        "grasa_sat_g": 0.3, "grasa_mono_g": 0.3, "grasa_poli_g": 0.7, "colesterol_mg": 0.0,
        "calcio_mg": 25.0, "hierro_mg": 1.5, "magnesio_mg": 45.0, "potasio_mg": 180.0, "sodio_mg": 3.0, "fosforo_mg": 150.0, "zinc_mg": 1.2, "selenio_ug": 26.0,
        "vitamina_a_ug": 0.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.4, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.12, "vitamina_b2_mg": 0.06, "vitamina_b3_mg": 2.0, "vitamina_b6_mg": 0.14, "folatos_b9_ug": 18.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 5,
        "nombre": "Pasta integral de trigo",
        "familia": "Cereales, Tubérculos y Derivados",
        "kcal": 348.0, "energia_kj": 1472.0, "proteina_g": 13.0, "carbohidratos_g": 64.5, "grasa_g": 2.5, "fibra_g": 8.0, "agua_g": 11.0,
        "grasa_sat_g": 0.4, "grasa_mono_g": 0.4, "grasa_poli_g": 1.1, "colesterol_mg": 0.0,
        "calcio_mg": 35.0, "hierro_mg": 3.2, "magnesio_mg": 95.0, "potasio_mg": 320.0, "sodio_mg": 4.0, "fosforo_mg": 240.0, "zinc_mg": 2.0, "selenio_ug": 35.0,
        "vitamina_a_ug": 0.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 1.2, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.35, "vitamina_b2_mg": 0.12, "vitamina_b3_mg": 4.5, "vitamina_b6_mg": 0.32, "folatos_b9_ug": 42.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 6,
        "nombre": "Pan integral de trigo",
        "familia": "Cereales, Tubérculos y Derivados",
        "kcal": 245.0, "energia_kj": 1035.0, "proteina_g": 9.2, "carbohidratos_g": 45.0, "grasa_g": 2.4, "fibra_g": 6.8, "agua_g": 36.0,
        "grasa_sat_g": 0.5, "grasa_mono_g": 0.5, "grasa_poli_g": 1.0, "colesterol_mg": 0.0,
        "calcio_mg": 54.0, "hierro_mg": 2.7, "magnesio_mg": 76.0, "potasio_mg": 230.0, "sodio_mg": 510.0, "fosforo_mg": 180.0, "zinc_mg": 1.8, "selenio_ug": 22.0,
        "vitamina_a_ug": 0.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.6, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.25, "vitamina_b2_mg": 0.09, "vitamina_b3_mg": 3.4, "vitamina_b6_mg": 0.22, "folatos_b9_ug": 38.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 7,
        "nombre": "Pan de centeno",
        "familia": "Cereales, Tubérculos y Derivados",
        "kcal": 235.0, "energia_kj": 992.0, "proteina_g": 7.8, "carbohidratos_g": 46.0, "grasa_g": 1.5, "fibra_g": 7.2, "agua_g": 37.0,
        "grasa_sat_g": 0.3, "grasa_mono_g": 0.3, "grasa_poli_g": 0.6, "colesterol_mg": 0.0,
        "calcio_mg": 40.0, "hierro_mg": 2.5, "magnesio_mg": 55.0, "potasio_mg": 210.0, "sodio_mg": 480.0, "fosforo_mg": 150.0, "zinc_mg": 1.5, "selenio_ug": 18.0,
        "vitamina_a_ug": 0.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.4, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.2, "vitamina_b2_mg": 0.08, "vitamina_b3_mg": 2.8, "vitamina_b6_mg": 0.18, "folatos_b9_ug": 30.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 8,
        "nombre": "Pan blanco de barra",
        "familia": "Cereales, Tubérculos y Derivados",
        "kcal": 265.0, "energia_kj": 1122.0, "proteina_g": 8.5, "carbohidratos_g": 53.5, "grasa_g": 1.6, "fibra_g": 2.7, "agua_g": 33.5,
        "grasa_sat_g": 0.4, "grasa_mono_g": 0.3, "grasa_poli_g": 0.6, "colesterol_mg": 0.0,
        "calcio_mg": 20.0, "hierro_mg": 1.6, "magnesio_mg": 25.0, "potasio_mg": 130.0, "sodio_mg": 540.0, "fosforo_mg": 95.0, "zinc_mg": 0.8, "selenio_ug": 15.0,
        "vitamina_a_ug": 0.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.3, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.12, "vitamina_b2_mg": 0.05, "vitamina_b3_mg": 1.8, "vitamina_b6_mg": 0.1, "folatos_b9_ug": 22.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 9,
        "nombre": "Patata cocida / al vapor",
        "familia": "Cereales, Tubérculos y Derivados",
        "kcal": 85.0, "energia_kj": 358.0, "proteina_g": 2.0, "carbohidratos_g": 18.0, "grasa_g": 0.1, "fibra_g": 1.8, "agua_g": 78.0,
        "grasa_sat_g": 0.03, "grasa_mono_g": 0.01, "grasa_poli_g": 0.04, "colesterol_mg": 0.0,
        "calcio_mg": 9.0, "hierro_mg": 0.7, "magnesio_mg": 21.0, "potasio_mg": 418.0, "sodio_mg": 4.0, "fosforo_mg": 50.0, "zinc_mg": 0.3, "selenio_ug": 1.0,
        "vitamina_a_ug": 2.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.1, "vitamina_c_mg": 14.0, "vitamina_b1_mg": 0.08, "vitamina_b2_mg": 0.04, "vitamina_b3_mg": 1.4, "vitamina_b6_mg": 0.28, "folatos_b9_ug": 16.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 10,
        "nombre": "Boniato / Batata cocida",
        "familia": "Cereales, Tubérculos y Derivados",
        "kcal": 98.0, "energia_kj": 415.0, "proteina_g": 1.6, "carbohidratos_g": 21.5, "grasa_g": 0.3, "fibra_g": 2.8, "agua_g": 73.5,
        "grasa_sat_g": 0.07, "grasa_mono_g": 0.02, "grasa_poli_g": 0.1, "colesterol_mg": 0.0,
        "calcio_mg": 28.0, "hierro_mg": 0.8, "magnesio_mg": 24.0, "potasio_mg": 380.0, "sodio_mg": 15.0, "fosforo_mg": 48.0, "zinc_mg": 0.4, "selenio_ug": 1.0,
        "vitamina_a_ug": 680.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.5, "vitamina_c_mg": 20.0, "vitamina_b1_mg": 0.09, "vitamina_b2_mg": 0.05, "vitamina_b3_mg": 1.2, "vitamina_b6_mg": 0.25, "folatos_b9_ug": 21.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 11,
        "nombre": "Quinoa cocida",
        "familia": "Cereales, Tubérculos y Derivados",
        "kcal": 120.0, "energia_kj": 506.0, "proteina_g": 4.4, "carbohidratos_g": 21.3, "grasa_g": 1.9, "fibra_g": 2.8, "agua_g": 69.0,
        "grasa_sat_g": 0.2, "grasa_mono_g": 0.5, "grasa_poli_g": 1.1, "colesterol_mg": 0.0,
        "calcio_mg": 17.0, "hierro_mg": 1.5, "magnesio_mg": 64.0, "potasio_mg": 172.0, "sodio_mg": 7.0, "fosforo_mg": 152.0, "zinc_mg": 1.1, "selenio_ug": 3.0,
        "vitamina_a_ug": 1.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.6, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.1, "vitamina_b2_mg": 0.08, "vitamina_b3_mg": 0.8, "vitamina_b6_mg": 0.16, "folatos_b9_ug": 42.0, "vitamina_b12_ug": 0.0
    },

    # 2. LEGUMBRES Y DERIVADOS
    {
        "id": 12,
        "nombre": "Garbanzos, cocidos",
        "familia": "Legumbres y Derivados",
        "kcal": 128.0, "energia_kj": 538.0, "proteina_g": 8.4, "carbohidratos_g": 16.8, "grasa_g": 2.6, "fibra_g": 6.8, "agua_g": 62.5,
        "grasa_sat_g": 0.3, "grasa_mono_g": 0.7, "grasa_poli_g": 1.2, "colesterol_mg": 0.0,
        "calcio_mg": 49.0, "hierro_mg": 2.2, "magnesio_mg": 40.0, "potasio_mg": 290.0, "sodio_mg": 24.0, "fosforo_mg": 125.0, "zinc_mg": 1.1, "selenio_ug": 3.0,
        "vitamina_a_ug": 8.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.6, "vitamina_c_mg": 1.5, "vitamina_b1_mg": 0.12, "vitamina_b2_mg": 0.05, "vitamina_b3_mg": 0.8, "vitamina_b6_mg": 0.14, "folatos_b9_ug": 65.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 13,
        "nombre": "Lentejas, cocidas",
        "familia": "Legumbres y Derivados",
        "kcal": 116.0, "energia_kj": 489.0, "proteina_g": 9.0, "carbohidratos_g": 15.5, "grasa_g": 0.4, "fibra_g": 7.9, "agua_g": 69.0,
        "grasa_sat_g": 0.06, "grasa_mono_g": 0.07, "grasa_poli_g": 0.2, "colesterol_mg": 0.0,
        "calcio_mg": 19.0, "hierro_mg": 3.3, "magnesio_mg": 36.0, "potasio_mg": 369.0, "sodio_mg": 3.0, "fosforo_mg": 180.0, "zinc_mg": 1.3, "selenio_ug": 3.0,
        "vitamina_a_ug": 2.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.2, "vitamina_c_mg": 1.5, "vitamina_b1_mg": 0.17, "vitamina_b2_mg": 0.07, "vitamina_b3_mg": 1.1, "vitamina_b6_mg": 0.18, "folatos_b9_ug": 181.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 14,
        "nombre": "Alubias blancas, cocidas",
        "familia": "Legumbres y Derivados",
        "kcal": 114.0, "energia_kj": 481.0, "proteina_g": 8.2, "carbohidratos_g": 16.0, "grasa_g": 0.5, "fibra_g": 6.5, "agua_g": 68.0,
        "grasa_sat_g": 0.09, "grasa_mono_g": 0.08, "grasa_poli_g": 0.25, "colesterol_mg": 0.0,
        "calcio_mg": 55.0, "hierro_mg": 2.5, "magnesio_mg": 45.0, "potasio_mg": 385.0, "sodio_mg": 10.0, "fosforo_mg": 140.0, "zinc_mg": 1.0, "selenio_ug": 4.0,
        "vitamina_a_ug": 0.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.1, "vitamina_c_mg": 0.5, "vitamina_b1_mg": 0.15, "vitamina_b2_mg": 0.06, "vitamina_b3_mg": 0.9, "vitamina_b6_mg": 0.15, "folatos_b9_ug": 95.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 15,
        "nombre": "Edamame (soja verde) cocido",
        "familia": "Legumbres y Derivados",
        "kcal": 122.0, "energia_kj": 512.0, "proteina_g": 11.5, "carbohidratos_g": 8.5, "grasa_g": 5.2, "fibra_g": 5.0, "agua_g": 72.0,
        "grasa_sat_g": 0.7, "grasa_mono_g": 1.2, "grasa_poli_g": 2.3, "colesterol_mg": 0.0,
        "calcio_mg": 63.0, "hierro_mg": 2.3, "magnesio_mg": 64.0, "potasio_mg": 435.0, "sodio_mg": 6.0, "fosforo_mg": 169.0, "zinc_mg": 1.4, "selenio_ug": 2.0,
        "vitamina_a_ug": 15.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.7, "vitamina_c_mg": 6.0, "vitamina_b1_mg": 0.2, "vitamina_b2_mg": 0.15, "vitamina_b3_mg": 0.9, "vitamina_b6_mg": 0.1, "folatos_b9_ug": 311.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 16,
        "nombre": "Soja texturizada fina (peso seco)",
        "familia": "Legumbres y Derivados",
        "kcal": 335.0, "energia_kj": 1412.0, "proteina_g": 50.0, "carbohidratos_g": 28.0, "grasa_g": 1.2, "fibra_g": 14.0, "agua_g": 6.0,
        "grasa_sat_g": 0.3, "grasa_mono_g": 0.2, "grasa_poli_g": 0.6, "colesterol_mg": 0.0,
        "calcio_mg": 220.0, "hierro_mg": 9.5, "magnesio_mg": 250.0, "potasio_mg": 1700.0, "sodio_mg": 15.0, "fosforo_mg": 650.0, "zinc_mg": 4.5, "selenio_ug": 18.0,
        "vitamina_a_ug": 0.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 1.5, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.7, "vitamina_b2_mg": 0.3, "vitamina_b3_mg": 3.0, "vitamina_b6_mg": 0.5, "folatos_b9_ug": 250.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 17,
        "nombre": "Tofu firme",
        "familia": "Legumbres y Derivados",
        "kcal": 120.0, "energia_kj": 504.0, "proteina_g": 13.0, "carbohidratos_g": 2.5, "grasa_g": 6.8, "fibra_g": 1.5, "agua_g": 76.0,
        "grasa_sat_g": 1.0, "grasa_mono_g": 1.5, "grasa_poli_g": 3.8, "colesterol_mg": 0.0,
        "calcio_mg": 240.0, "hierro_mg": 2.8, "magnesio_mg": 58.0, "potasio_mg": 160.0, "sodio_mg": 14.0, "fosforo_mg": 190.0, "zinc_mg": 1.6, "selenio_ug": 9.0,
        "vitamina_a_ug": 0.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.4, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.1, "vitamina_b2_mg": 0.05, "vitamina_b3_mg": 0.4, "vitamina_b6_mg": 0.08, "folatos_b9_ug": 19.0, "vitamina_b12_ug": 0.0
    },

    # 3. FRUTAS FRESCAS Y DESECADAS
    {
        "id": 18,
        "nombre": "Plátano maduro",
        "familia": "Frutas Frescas",
        "kcal": 89.0, "energia_kj": 377.0, "proteina_g": 1.1, "carbohidratos_g": 20.8, "grasa_g": 0.3, "fibra_g": 2.5, "agua_g": 75.1,
        "grasa_sat_g": 0.1, "grasa_mono_g": 0.05, "grasa_poli_g": 0.08, "colesterol_mg": 0.0,
        "calcio_mg": 5.0, "hierro_mg": 0.3, "magnesio_mg": 28.0, "potasio_mg": 358.0, "sodio_mg": 1.0, "fosforo_mg": 22.0, "zinc_mg": 0.16, "selenio_ug": 1.0,
        "vitamina_a_ug": 19.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.2, "vitamina_c_mg": 10.3, "vitamina_b1_mg": 0.04, "vitamina_b2_mg": 0.07, "vitamina_b3_mg": 0.8, "vitamina_b6_mg": 0.51, "folatos_b9_ug": 22.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 19,
        "nombre": "Manzana, con piel",
        "familia": "Frutas Frescas",
        "kcal": 52.0, "energia_kj": 220.0, "proteina_g": 0.3, "carbohidratos_g": 12.0, "grasa_g": 0.2, "fibra_g": 2.4, "agua_g": 85.0,
        "grasa_sat_g": 0.03, "grasa_mono_g": 0.01, "grasa_poli_g": 0.05, "colesterol_mg": 0.0,
        "calcio_mg": 6.0, "hierro_mg": 0.2, "magnesio_mg": 5.0, "potasio_mg": 107.0, "sodio_mg": 1.0, "fosforo_mg": 11.0, "zinc_mg": 0.05, "selenio_ug": 0.5,
        "vitamina_a_ug": 3.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.2, "vitamina_c_mg": 12.0, "vitamina_b1_mg": 0.02, "vitamina_b2_mg": 0.02, "vitamina_b3_mg": 0.1, "vitamina_b6_mg": 0.04, "folatos_b9_ug": 3.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 20,
        "nombre": "Frutos rojos variados (arándanos, moras, frambuesas)",
        "familia": "Frutas Frescas",
        "kcal": 45.0, "energia_kj": 190.0, "proteina_g": 0.9, "carbohidratos_g": 8.5, "grasa_g": 0.4, "fibra_g": 5.0, "agua_g": 84.5,
        "grasa_sat_g": 0.03, "grasa_mono_g": 0.04, "grasa_poli_g": 0.2, "colesterol_mg": 0.0,
        "calcio_mg": 22.0, "hierro_mg": 0.7, "magnesio_mg": 18.0, "potasio_mg": 160.0, "sodio_mg": 1.0, "fosforo_mg": 24.0, "zinc_mg": 0.3, "selenio_ug": 0.6,
        "vitamina_a_ug": 6.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 1.1, "vitamina_c_mg": 25.0, "vitamina_b1_mg": 0.03, "vitamina_b2_mg": 0.04, "vitamina_b3_mg": 0.5, "vitamina_b6_mg": 0.06, "folatos_b9_ug": 25.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 21,
        "nombre": "Naranja",
        "familia": "Frutas Frescas",
        "kcal": 42.0, "energia_kj": 178.0, "proteina_g": 0.8, "carbohidratos_g": 8.6, "grasa_g": 0.1, "fibra_g": 2.0, "agua_g": 88.0,
        "grasa_sat_g": 0.02, "grasa_mono_g": 0.02, "grasa_poli_g": 0.03, "colesterol_mg": 0.0,
        "calcio_mg": 36.0, "hierro_mg": 0.3, "magnesio_mg": 12.0, "potasio_mg": 180.0, "sodio_mg": 1.0, "fosforo_mg": 20.0, "zinc_mg": 0.1, "selenio_ug": 0.5,
        "vitamina_a_ug": 11.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.2, "vitamina_c_mg": 50.0, "vitamina_b1_mg": 0.08, "vitamina_b2_mg": 0.03, "vitamina_b3_mg": 0.3, "vitamina_b6_mg": 0.06, "folatos_b9_ug": 30.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 22,
        "nombre": "Kiwi verde",
        "familia": "Frutas Frescas",
        "kcal": 55.0, "energia_kj": 232.0, "proteina_g": 1.0, "carbohidratos_g": 10.5, "grasa_g": 0.5, "fibra_g": 2.8, "agua_g": 84.0,
        "grasa_sat_g": 0.04, "grasa_mono_g": 0.05, "grasa_poli_g": 0.25, "colesterol_mg": 0.0,
        "calcio_mg": 25.0, "hierro_mg": 0.4, "magnesio_mg": 15.0, "potasio_mg": 290.0, "sodio_mg": 4.0, "fosforo_mg": 30.0, "zinc_mg": 0.15, "selenio_ug": 0.8,
        "vitamina_a_ug": 5.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 1.0, "vitamina_c_mg": 85.0, "vitamina_b1_mg": 0.02, "vitamina_b2_mg": 0.03, "vitamina_b3_mg": 0.4, "vitamina_b6_mg": 0.12, "folatos_b9_ug": 34.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 23,
        "nombre": "Dátiles sin hueso (tipo Medjoul)",
        "familia": "Frutas Desecadas",
        "kcal": 280.0, "energia_kj": 1185.0, "proteina_g": 2.2, "carbohidratos_g": 67.0, "grasa_g": 0.4, "fibra_g": 7.0, "agua_g": 21.0,
        "grasa_sat_g": 0.08, "grasa_mono_g": 0.04, "grasa_poli_g": 0.12, "colesterol_mg": 0.0,
        "calcio_mg": 64.0, "hierro_mg": 1.8, "magnesio_mg": 54.0, "potasio_mg": 650.0, "sodio_mg": 2.0, "fosforo_mg": 62.0, "zinc_mg": 0.4, "selenio_ug": 2.5,
        "vitamina_a_ug": 7.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.1, "vitamina_c_mg": 0.4, "vitamina_b1_mg": 0.05, "vitamina_b2_mg": 0.06, "vitamina_b3_mg": 1.6, "vitamina_b6_mg": 0.25, "folatos_b9_ug": 19.0, "vitamina_b12_ug": 0.0
    },

    # 4. VERDURAS Y HORTALIZAS
    {
        "id": 24,
        "nombre": "Espinacas frescas",
        "familia": "Verduras y Hortalizas",
        "kcal": 23.0, "energia_kj": 96.0, "proteina_g": 2.9, "carbohidratos_g": 1.4, "grasa_g": 0.4, "fibra_g": 2.6, "agua_g": 91.0,
        "grasa_sat_g": 0.06, "grasa_mono_g": 0.02, "grasa_poli_g": 0.17, "colesterol_mg": 0.0,
        "calcio_mg": 99.0, "hierro_mg": 2.7, "magnesio_mg": 79.0, "potasio_mg": 558.0, "sodio_mg": 79.0, "fosforo_mg": 49.0, "zinc_mg": 0.5, "selenio_ug": 1.0,
        "vitamina_a_ug": 469.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 2.0, "vitamina_c_mg": 28.1, "vitamina_b1_mg": 0.08, "vitamina_b2_mg": 0.2, "vitamina_b3_mg": 0.7, "vitamina_b6_mg": 0.2, "folatos_b9_ug": 194.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 25,
        "nombre": "Brócoli cocido",
        "familia": "Verduras y Hortalizas",
        "kcal": 35.0, "energia_kj": 147.0, "proteina_g": 3.2, "carbohidratos_g": 2.8, "grasa_g": 0.6, "fibra_g": 3.0, "agua_g": 89.5,
        "grasa_sat_g": 0.08, "grasa_mono_g": 0.03, "grasa_poli_g": 0.25, "colesterol_mg": 0.0,
        "calcio_mg": 56.0, "hierro_mg": 0.9, "magnesio_mg": 22.0, "potasio_mg": 310.0, "sodio_mg": 35.0, "fosforo_mg": 66.0, "zinc_mg": 0.6, "selenio_ug": 1.6,
        "vitamina_a_ug": 77.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 1.4, "vitamina_c_mg": 65.0, "vitamina_b1_mg": 0.07, "vitamina_b2_mg": 0.12, "vitamina_b3_mg": 0.6, "vitamina_b6_mg": 0.16, "folatos_b9_ug": 108.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 26,
        "nombre": "Calabacín con piel",
        "familia": "Verduras y Hortalizas",
        "kcal": 17.0, "energia_kj": 71.0, "proteina_g": 1.2, "carbohidratos_g": 2.2, "grasa_g": 0.2, "fibra_g": 1.2, "agua_g": 94.5,
        "grasa_sat_g": 0.04, "grasa_mono_g": 0.01, "grasa_poli_g": 0.08, "colesterol_mg": 0.0,
        "calcio_mg": 19.0, "hierro_mg": 0.5, "magnesio_mg": 18.0, "potasio_mg": 260.0, "sodio_mg": 3.0, "fosforo_mg": 38.0, "zinc_mg": 0.3, "selenio_ug": 0.3,
        "vitamina_a_ug": 10.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.1, "vitamina_c_mg": 17.0, "vitamina_b1_mg": 0.05, "vitamina_b2_mg": 0.04, "vitamina_b3_mg": 0.5, "vitamina_b6_mg": 0.16, "folatos_b9_ug": 24.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 27,
        "nombre": "Zanahoria cruda",
        "familia": "Verduras y Hortalizas",
        "kcal": 37.0, "energia_kj": 156.0, "proteina_g": 0.9, "carbohidratos_g": 6.9, "grasa_g": 0.2, "fibra_g": 2.8, "agua_g": 88.5,
        "grasa_sat_g": 0.03, "grasa_mono_g": 0.01, "grasa_poli_g": 0.08, "colesterol_mg": 0.0,
        "calcio_mg": 33.0, "hierro_mg": 0.4, "magnesio_mg": 12.0, "potasio_mg": 320.0, "sodio_mg": 69.0, "fosforo_mg": 35.0, "zinc_mg": 0.24, "selenio_ug": 0.1,
        "vitamina_a_ug": 835.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.7, "vitamina_c_mg": 6.0, "vitamina_b1_mg": 0.07, "vitamina_b2_mg": 0.05, "vitamina_b3_mg": 0.6, "vitamina_b6_mg": 0.14, "folatos_b9_ug": 19.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 28,
        "nombre": "Tomate maduro para ensalada",
        "familia": "Verduras y Hortalizas",
        "kcal": 19.0, "energia_kj": 81.0, "proteina_g": 1.0, "carbohidratos_g": 3.1, "grasa_g": 0.2, "fibra_g": 1.4, "agua_g": 94.0,
        "grasa_sat_g": 0.03, "grasa_mono_g": 0.03, "grasa_poli_g": 0.08, "colesterol_mg": 0.0,
        "calcio_mg": 11.0, "hierro_mg": 0.5, "magnesio_mg": 11.0, "potasio_mg": 240.0, "sodio_mg": 4.0, "fosforo_mg": 24.0, "zinc_mg": 0.2, "selenio_ug": 0.4,
        "vitamina_a_ug": 42.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.9, "vitamina_c_mg": 26.0, "vitamina_b1_mg": 0.06, "vitamina_b2_mg": 0.04, "vitamina_b3_mg": 0.7, "vitamina_b6_mg": 0.08, "folatos_b9_ug": 15.0, "vitamina_b12_ug": 0.0
    },

    # 5. PESCADOS Y MARISCOS
    {
        "id": 29,
        "nombre": "Salmón fresco",
        "familia": "Pescados Azules (Omega-3)",
        "kcal": 182.0, "energia_kj": 760.0, "proteina_g": 19.9, "carbohidratos_g": 0.0, "grasa_g": 12.0, "fibra_g": 0.0, "agua_g": 68.0,
        "grasa_sat_g": 2.1, "grasa_mono_g": 4.8, "grasa_poli_g": 3.9, "colesterol_mg": 50.0,
        "calcio_mg": 11.0, "hierro_mg": 0.7, "magnesio_mg": 26.0, "potasio_mg": 340.0, "sodio_mg": 55.0, "fosforo_mg": 250.0, "zinc_mg": 0.6, "selenio_ug": 36.0,
        "vitamina_a_ug": 40.0, "vitamina_d_ug": 8.0, "vitamina_e_mg": 2.0, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.2, "vitamina_b2_mg": 0.15, "vitamina_b3_mg": 8.5, "vitamina_b6_mg": 0.8, "folatos_b9_ug": 25.0, "vitamina_b12_ug": 4.0
    },
    {
        "id": 30,
        "nombre": "Atún claro al natural (en conserva)",
        "familia": "Pescados Azules (Omega-3)",
        "kcal": 105.0, "energia_kj": 444.0, "proteina_g": 24.5, "carbohidratos_g": 0.0, "grasa_g": 0.8, "fibra_g": 0.0, "agua_g": 73.5,
        "grasa_sat_g": 0.2, "grasa_mono_g": 0.15, "grasa_poli_g": 0.3, "colesterol_mg": 45.0,
        "calcio_mg": 8.0, "hierro_mg": 1.3, "magnesio_mg": 28.0, "potasio_mg": 300.0, "sodio_mg": 350.0, "fosforo_mg": 210.0, "zinc_mg": 0.8, "selenio_ug": 68.0,
        "vitamina_a_ug": 15.0, "vitamina_d_ug": 2.5, "vitamina_e_mg": 0.5, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.03, "vitamina_b2_mg": 0.08, "vitamina_b3_mg": 13.0, "vitamina_b6_mg": 0.5, "folatos_b9_ug": 12.0, "vitamina_b12_ug": 3.5
    },
    {
        "id": 31,
        "nombre": "Merluza fresca o congelada",
        "familia": "Pescados Blancos Magros",
        "kcal": 71.0, "energia_kj": 300.0, "proteina_g": 16.5, "carbohidratos_g": 0.0, "grasa_g": 0.8, "fibra_g": 0.0, "agua_g": 82.0,
        "grasa_sat_g": 0.2, "grasa_mono_g": 0.15, "grasa_poli_g": 0.3, "colesterol_mg": 60.0,
        "calcio_mg": 33.0, "hierro_mg": 0.9, "magnesio_mg": 23.0, "potasio_mg": 295.0, "sodio_mg": 80.0, "fosforo_mg": 190.0, "zinc_mg": 0.5, "selenio_ug": 27.0,
        "vitamina_a_ug": 12.0, "vitamina_d_ug": 0.5, "vitamina_e_mg": 0.3, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.08, "vitamina_b2_mg": 0.07, "vitamina_b3_mg": 5.2, "vitamina_b6_mg": 0.25, "folatos_b9_ug": 11.0, "vitamina_b12_ug": 1.1
    },
    {
        "id": 32,
        "nombre": "Bacalao fresco / al punto de sal",
        "familia": "Pescados Blancos Magros",
        "kcal": 78.0, "energia_kj": 331.0, "proteina_g": 17.5, "carbohidratos_g": 0.0, "grasa_g": 0.7, "fibra_g": 0.0, "agua_g": 81.0,
        "grasa_sat_g": 0.15, "grasa_mono_g": 0.1, "grasa_poli_g": 0.3, "colesterol_mg": 50.0,
        "calcio_mg": 24.0, "hierro_mg": 0.4, "magnesio_mg": 25.0, "potasio_mg": 360.0, "sodio_mg": 90.0, "fosforo_mg": 210.0, "zinc_mg": 0.4, "selenio_ug": 30.0,
        "vitamina_a_ug": 10.0, "vitamina_d_ug": 1.0, "vitamina_e_mg": 0.4, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.06, "vitamina_b2_mg": 0.05, "vitamina_b3_mg": 2.5, "vitamina_b6_mg": 0.2, "folatos_b9_ug": 10.0, "vitamina_b12_ug": 1.4
    },
    {
        "id": 33,
        "nombre": "Sepia limpia / Calamar",
        "familia": "Moluscos / Cefalópodos Magros",
        "kcal": 79.0, "energia_kj": 335.0, "proteina_g": 16.1, "carbohidratos_g": 0.8, "grasa_g": 1.2, "fibra_g": 0.0, "agua_g": 81.5,
        "grasa_sat_g": 0.3, "grasa_mono_g": 0.15, "grasa_poli_g": 0.45, "colesterol_mg": 110.0,
        "calcio_mg": 27.0, "hierro_mg": 1.2, "magnesio_mg": 32.0, "potasio_mg": 270.0, "sodio_mg": 150.0, "fosforo_mg": 180.0, "zinc_mg": 1.4, "selenio_ug": 44.0,
        "vitamina_a_ug": 20.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 1.5, "vitamina_c_mg": 4.0, "vitamina_b1_mg": 0.07, "vitamina_b2_mg": 0.14, "vitamina_b3_mg": 2.2, "vitamina_b6_mg": 0.15, "folatos_b9_ug": 16.0, "vitamina_b12_ug": 2.8
    },
    {
        "id": 34,
        "nombre": "Mejillón al vapor",
        "familia": "Moluscos / Cefalópodos Magros",
        "kcal": 86.0, "energia_kj": 364.0, "proteina_g": 14.5, "carbohidratos_g": 3.4, "grasa_g": 1.9, "fibra_g": 0.0, "agua_g": 79.0,
        "grasa_sat_g": 0.4, "grasa_mono_g": 0.3, "grasa_poli_g": 0.6, "colesterol_mg": 65.0,
        "calcio_mg": 45.0, "hierro_mg": 4.5, "magnesio_mg": 34.0, "potasio_mg": 320.0, "sodio_mg": 290.0, "fosforo_mg": 230.0, "zinc_mg": 2.2, "selenio_ug": 56.0,
        "vitamina_a_ug": 54.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 1.8, "vitamina_c_mg": 8.0, "vitamina_b1_mg": 0.16, "vitamina_b2_mg": 0.21, "vitamina_b3_mg": 3.0, "vitamina_b6_mg": 0.1, "folatos_b9_ug": 42.0, "vitamina_b12_ug": 8.0
    },

    # 6. AVES, CARNES Y HUEVOS
    {
        "id": 35,
        "nombre": "Pechuga de pollo sin piel",
        "familia": "Aves y Carnes Blancas Magras",
        "kcal": 120.0, "energia_kj": 505.0, "proteina_g": 22.5, "carbohidratos_g": 0.0, "grasa_g": 2.6, "fibra_g": 0.0, "agua_g": 74.0,
        "grasa_sat_g": 0.7, "grasa_mono_g": 0.9, "grasa_poli_g": 0.6, "colesterol_mg": 65.0,
        "calcio_mg": 14.0, "hierro_mg": 1.1, "magnesio_mg": 25.0, "potasio_mg": 330.0, "sodio_mg": 65.0, "fosforo_mg": 210.0, "zinc_mg": 1.0, "selenio_ug": 22.0,
        "vitamina_a_ug": 16.0, "vitamina_d_ug": 0.1, "vitamina_e_mg": 0.2, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.08, "vitamina_b2_mg": 0.1, "vitamina_b3_mg": 11.2, "vitamina_b6_mg": 0.5, "folatos_b9_ug": 10.0, "vitamina_b12_ug": 0.4
    },
    {
        "id": 36,
        "nombre": "Pechuga de pavo",
        "familia": "Aves y Carnes Blancas Magras",
        "kcal": 110.0, "energia_kj": 464.0, "proteina_g": 24.0, "carbohidratos_g": 0.0, "grasa_g": 1.5, "fibra_g": 0.0, "agua_g": 74.5,
        "grasa_sat_g": 0.4, "grasa_mono_g": 0.5, "grasa_poli_g": 0.4, "colesterol_mg": 60.0,
        "calcio_mg": 15.0, "hierro_mg": 1.4, "magnesio_mg": 28.0, "potasio_mg": 350.0, "sodio_mg": 60.0, "fosforo_mg": 220.0, "zinc_mg": 1.5, "selenio_ug": 25.0,
        "vitamina_a_ug": 0.0, "vitamina_d_ug": 0.1, "vitamina_e_mg": 0.1, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.06, "vitamina_b2_mg": 0.12, "vitamina_b3_mg": 9.5, "vitamina_b6_mg": 0.6, "folatos_b9_ug": 8.0, "vitamina_b12_ug": 0.8
    },
    {
        "id": 37,
        "nombre": "Huevo de gallina entero (crudo/cocido)",
        "familia": "Huevos y Ovoproductos",
        "kcal": 147.0, "energia_kj": 615.0, "proteina_g": 12.8, "carbohidratos_g": 0.7, "grasa_g": 10.6, "fibra_g": 0.0, "agua_g": 75.0,
        "grasa_sat_g": 3.1, "grasa_mono_g": 4.1, "grasa_poli_g": 1.8, "colesterol_mg": 410.0,
        "calcio_mg": 56.0, "hierro_mg": 2.2, "magnesio_mg": 12.0, "potasio_mg": 140.0, "sodio_mg": 140.0, "fosforo_mg": 215.0, "zinc_mg": 1.3, "selenio_ug": 31.0,
        "vitamina_a_ug": 227.0, "vitamina_d_ug": 1.8, "vitamina_e_mg": 1.9, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.09, "vitamina_b2_mg": 0.37, "vitamina_b3_mg": 3.3, "vitamina_b6_mg": 0.14, "folatos_b9_ug": 50.0, "vitamina_b12_ug": 2.1
    },
    {
        "id": 38,
        "nombre": "Clara de huevo pasteurizada",
        "familia": "Huevos y Ovoproductos",
        "kcal": 48.0, "energia_kj": 204.0, "proteina_g": 11.0, "carbohidratos_g": 0.7, "grasa_g": 0.2, "fibra_g": 0.0, "agua_g": 88.0,
        "grasa_sat_g": 0.03, "grasa_mono_g": 0.02, "grasa_poli_g": 0.05, "colesterol_mg": 0.0,
        "calcio_mg": 7.0, "hierro_mg": 0.1, "magnesio_mg": 11.0, "potasio_mg": 160.0, "sodio_mg": 165.0, "fosforo_mg": 15.0, "zinc_mg": 0.1, "selenio_ug": 20.0,
        "vitamina_a_ug": 0.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.0, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.01, "vitamina_b2_mg": 0.44, "vitamina_b3_mg": 0.1, "vitamina_b6_mg": 0.01, "folatos_b9_ug": 4.0, "vitamina_b12_ug": 0.1
    },
    {
        "id": 39,
        "nombre": "Ternera magra (solomillo / lomo bajo)",
        "familia": "Carnes Rojas y Derivados",
        "kcal": 135.0, "energia_kj": 568.0, "proteina_g": 21.8, "carbohidratos_g": 0.0, "grasa_g": 5.2, "fibra_g": 0.0, "agua_g": 72.0,
        "grasa_sat_g": 2.2, "grasa_mono_g": 2.3, "grasa_poli_g": 0.3, "colesterol_mg": 65.0,
        "calcio_mg": 8.0, "hierro_mg": 2.5, "magnesio_mg": 21.0, "potasio_mg": 350.0, "sodio_mg": 60.0, "fosforo_mg": 195.0, "zinc_mg": 4.5, "selenio_ug": 15.0,
        "vitamina_a_ug": 0.0, "vitamina_d_ug": 0.2, "vitamina_e_mg": 0.2, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.07, "vitamina_b2_mg": 0.18, "vitamina_b3_mg": 5.5, "vitamina_b6_mg": 0.4, "folatos_b9_ug": 8.0, "vitamina_b12_ug": 2.2
    },
    {
        "id": 40,
        "nombre": "Lomo de cerdo magro",
        "familia": "Carnes Rojas y Derivados",
        "kcal": 150.0, "energia_kj": 632.0, "proteina_g": 22.0, "carbohidratos_g": 0.0, "grasa_g": 6.8, "fibra_g": 0.0, "agua_g": 70.0,
        "grasa_sat_g": 2.4, "grasa_mono_g": 3.2, "grasa_poli_g": 0.8, "colesterol_mg": 70.0,
        "calcio_mg": 9.0, "hierro_mg": 1.2, "magnesio_mg": 24.0, "potasio_mg": 370.0, "sodio_mg": 65.0, "fosforo_mg": 220.0, "zinc_mg": 2.4, "selenio_ug": 28.0,
        "vitamina_a_ug": 0.0, "vitamina_d_ug": 0.3, "vitamina_e_mg": 0.3, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.75, "vitamina_b2_mg": 0.16, "vitamina_b3_mg": 5.0, "vitamina_b6_mg": 0.45, "folatos_b9_ug": 6.0, "vitamina_b12_ug": 0.8
    },

    # 7. LÁCTEOS Y DERIVADOS
    {
        "id": 41,
        "nombre": "Yogur natural entero",
        "familia": "Lácteos y Derivados",
        "kcal": 61.0, "energia_kj": 257.0, "proteina_g": 3.5, "carbohidratos_g": 4.7, "grasa_g": 3.3, "fibra_g": 0.0, "agua_g": 88.0,
        "grasa_sat_g": 2.1, "grasa_mono_g": 0.9, "grasa_poli_g": 0.1, "colesterol_mg": 12.0,
        "calcio_mg": 125.0, "hierro_mg": 0.1, "magnesio_mg": 13.0, "potasio_mg": 170.0, "sodio_mg": 50.0, "fosforo_mg": 98.0, "zinc_mg": 0.6, "selenio_ug": 2.5,
        "vitamina_a_ug": 30.0, "vitamina_d_ug": 0.06, "vitamina_e_mg": 0.06, "vitamina_c_mg": 0.7, "vitamina_b1_mg": 0.04, "vitamina_b2_mg": 0.18, "vitamina_b3_mg": 0.2, "vitamina_b6_mg": 0.05, "folatos_b9_ug": 12.0, "vitamina_b12_ug": 0.4
    },
    {
        "id": 42,
        "nombre": "Yogur griego natural",
        "familia": "Lácteos y Derivados",
        "kcal": 115.0, "energia_kj": 481.0, "proteina_g": 6.5, "carbohidratos_g": 4.2, "grasa_g": 8.0, "fibra_g": 0.0, "agua_g": 80.5,
        "grasa_sat_g": 5.2, "grasa_mono_g": 2.2, "grasa_poli_g": 0.3, "colesterol_mg": 25.0,
        "calcio_mg": 140.0, "hierro_mg": 0.1, "magnesio_mg": 15.0, "potasio_mg": 180.0, "sodio_mg": 55.0, "fosforo_mg": 130.0, "zinc_mg": 0.7, "selenio_ug": 3.0,
        "vitamina_a_ug": 65.0, "vitamina_d_ug": 0.1, "vitamina_e_mg": 0.1, "vitamina_c_mg": 0.5, "vitamina_b1_mg": 0.04, "vitamina_b2_mg": 0.22, "vitamina_b3_mg": 0.3, "vitamina_b6_mg": 0.06, "folatos_b9_ug": 14.0, "vitamina_b12_ug": 0.6
    },
    {
        "id": 43,
        "nombre": "Kéfir natural de leche",
        "familia": "Lácteos y Derivados",
        "kcal": 55.0, "energia_kj": 230.0, "proteina_g": 3.4, "carbohidratos_g": 4.0, "grasa_g": 3.0, "fibra_g": 0.0, "agua_g": 89.0,
        "grasa_sat_g": 1.9, "grasa_mono_g": 0.8, "grasa_poli_g": 0.1, "colesterol_mg": 10.0,
        "calcio_mg": 130.0, "hierro_mg": 0.1, "magnesio_mg": 12.0, "potasio_mg": 165.0, "sodio_mg": 45.0, "fosforo_mg": 100.0, "zinc_mg": 0.5, "selenio_ug": 2.8,
        "vitamina_a_ug": 28.0, "vitamina_d_ug": 0.08, "vitamina_e_mg": 0.08, "vitamina_c_mg": 1.0, "vitamina_b1_mg": 0.04, "vitamina_b2_mg": 0.17, "vitamina_b3_mg": 0.2, "vitamina_b6_mg": 0.05, "folatos_b9_ug": 15.0, "vitamina_b12_ug": 0.5
    },
    {
        "id": 44,
        "nombre": "Leche entera de vaca",
        "familia": "Lácteos y Derivados",
        "kcal": 63.0, "energia_kj": 265.0, "proteina_g": 3.2, "carbohidratos_g": 4.7, "grasa_g": 3.6, "fibra_g": 0.0, "agua_g": 88.0,
        "grasa_sat_g": 2.3, "grasa_mono_g": 1.0, "grasa_poli_g": 0.15, "colesterol_mg": 14.0,
        "calcio_mg": 120.0, "hierro_mg": 0.1, "magnesio_mg": 12.0, "potasio_mg": 150.0, "sodio_mg": 48.0, "fosforo_mg": 95.0, "zinc_mg": 0.4, "selenio_ug": 2.0,
        "vitamina_a_ug": 38.0, "vitamina_d_ug": 0.08, "vitamina_e_mg": 0.1, "vitamina_c_mg": 1.5, "vitamina_b1_mg": 0.04, "vitamina_b2_mg": 0.18, "vitamina_b3_mg": 0.8, "vitamina_b6_mg": 0.05, "folatos_b9_ug": 5.0, "vitamina_b12_ug": 0.4
    },
    {
        "id": 45,
        "nombre": "Leche desnatada de vaca",
        "familia": "Lácteos y Derivados",
        "kcal": 35.0, "energia_kj": 147.0, "proteina_g": 3.4, "carbohidratos_g": 4.9, "grasa_g": 0.2, "fibra_g": 0.0, "agua_g": 91.0,
        "grasa_sat_g": 0.1, "grasa_mono_g": 0.05, "grasa_poli_g": 0.02, "colesterol_mg": 2.0,
        "calcio_mg": 125.0, "hierro_mg": 0.1, "magnesio_mg": 12.0, "potasio_mg": 155.0, "sodio_mg": 52.0, "fosforo_mg": 98.0, "zinc_mg": 0.4, "selenio_ug": 2.2,
        "vitamina_a_ug": 2.0, "vitamina_d_ug": 0.01, "vitamina_e_mg": 0.01, "vitamina_c_mg": 1.0, "vitamina_b1_mg": 0.04, "vitamina_b2_mg": 0.18, "vitamina_b3_mg": 0.8, "vitamina_b6_mg": 0.05, "folatos_b9_ug": 5.0, "vitamina_b12_ug": 0.4
    },
    {
        "id": 46,
        "nombre": "Queso fresco tipo Burgos",
        "familia": "Lácteos y Derivados",
        "kcal": 175.0, "energia_kj": 732.0, "proteina_g": 12.0, "carbohidratos_g": 3.5, "grasa_g": 12.5, "fibra_g": 0.0, "agua_g": 70.0,
        "grasa_sat_g": 8.1, "grasa_mono_g": 3.5, "grasa_poli_g": 0.4, "colesterol_mg": 40.0,
        "calcio_mg": 185.0, "hierro_mg": 0.2, "magnesio_mg": 14.0, "potasio_mg": 110.0, "sodio_mg": 380.0, "fosforo_mg": 160.0, "zinc_mg": 1.1, "selenio_ug": 4.0,
        "vitamina_a_ug": 110.0, "vitamina_d_ug": 0.2, "vitamina_e_mg": 0.3, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.03, "vitamina_b2_mg": 0.25, "vitamina_b3_mg": 0.4, "vitamina_b6_mg": 0.07, "folatos_b9_ug": 18.0, "vitamina_b12_ug": 1.1
    },
    {
        "id": 47,
        "nombre": "Queso cottage / requesón",
        "familia": "Lácteos y Derivados",
        "kcal": 98.0, "energia_kj": 412.0, "proteina_g": 12.5, "carbohidratos_g": 3.2, "grasa_g": 4.0, "fibra_g": 0.0, "agua_g": 79.5,
        "grasa_sat_g": 2.5, "grasa_mono_g": 1.1, "grasa_poli_g": 0.2, "colesterol_mg": 15.0,
        "calcio_mg": 85.0, "hierro_mg": 0.1, "magnesio_mg": 10.0, "potasio_mg": 125.0, "sodio_mg": 360.0, "fosforo_mg": 150.0, "zinc_mg": 0.6, "selenio_ug": 9.5,
        "vitamina_a_ug": 40.0, "vitamina_d_ug": 0.1, "vitamina_e_mg": 0.1, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.03, "vitamina_b2_mg": 0.18, "vitamina_b3_mg": 0.2, "vitamina_b6_mg": 0.06, "folatos_b9_ug": 12.0, "vitamina_b12_ug": 0.6
    },

    # 8. FRUTOS SECOS, SEMILLAS Y ACEITES
    {
        "id": 48,
        "nombre": "Aceite de oliva virgen extra (AOVE)",
        "familia": "Aceites y Grasas Saludables",
        "kcal": 884.0, "energia_kj": 3700.0, "proteina_g": 0.0, "carbohidratos_g": 0.0, "grasa_g": 100.0, "fibra_g": 0.0, "agua_g": 0.0,
        "grasa_sat_g": 14.0, "grasa_mono_g": 75.0, "grasa_poli_g": 9.0, "colesterol_mg": 0.0,
        "calcio_mg": 1.0, "hierro_mg": 0.1, "magnesio_mg": 0.0, "potasio_mg": 1.0, "sodio_mg": 2.0, "fosforo_mg": 0.0, "zinc_mg": 0.0, "selenio_ug": 0.0,
        "vitamina_a_ug": 0.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 14.3, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.0, "vitamina_b2_mg": 0.0, "vitamina_b3_mg": 0.0, "vitamina_b6_mg": 0.0, "folatos_b9_ug": 0.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 49,
        "nombre": "Nueces de California",
        "familia": "Frutos Secos y Semillas",
        "kcal": 654.0, "energia_kj": 2738.0, "proteina_g": 15.2, "carbohidratos_g": 13.7, "grasa_g": 65.2, "fibra_g": 6.7, "agua_g": 4.0,
        "grasa_sat_g": 6.1, "grasa_mono_g": 8.9, "grasa_poli_g": 47.2, "colesterol_mg": 0.0,
        "calcio_mg": 98.0, "hierro_mg": 2.9, "magnesio_mg": 158.0, "potasio_mg": 441.0, "sodio_mg": 2.0, "fosforo_mg": 346.0, "zinc_mg": 3.1, "selenio_ug": 5.0,
        "vitamina_a_ug": 2.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.7, "vitamina_c_mg": 1.3, "vitamina_b1_mg": 0.34, "vitamina_b2_mg": 0.15, "vitamina_b3_mg": 1.1, "vitamina_b6_mg": 0.54, "folatos_b9_ug": 98.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 50,
        "nombre": "Almendras crudas",
        "familia": "Frutos Secos y Semillas",
        "kcal": 579.0, "energia_kj": 2420.0, "proteina_g": 21.2, "carbohidratos_g": 21.6, "grasa_g": 49.9, "fibra_g": 12.5, "agua_g": 4.5,
        "grasa_sat_g": 3.8, "grasa_mono_g": 31.5, "grasa_poli_g": 12.3, "colesterol_mg": 0.0,
        "calcio_mg": 269.0, "hierro_mg": 3.7, "magnesio_mg": 270.0, "potasio_mg": 733.0, "sodio_mg": 1.0, "fosforo_mg": 481.0, "zinc_mg": 3.1, "selenio_ug": 4.1,
        "vitamina_a_ug": 1.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 25.6, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.21, "vitamina_b2_mg": 1.1, "vitamina_b3_mg": 3.6, "vitamina_b6_mg": 0.14, "folatos_b9_ug": 44.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 51,
        "nombre": "Crema de cacahuete 100% natural",
        "familia": "Frutos Secos y Semillas",
        "kcal": 588.0, "energia_kj": 2460.0, "proteina_g": 25.0, "carbohidratos_g": 16.0, "grasa_g": 50.0, "fibra_g": 8.0, "agua_g": 1.5,
        "grasa_sat_g": 7.0, "grasa_mono_g": 24.5, "grasa_poli_g": 15.5, "colesterol_mg": 0.0,
        "calcio_mg": 43.0, "hierro_mg": 2.1, "magnesio_mg": 168.0, "potasio_mg": 650.0, "sodio_mg": 15.0, "fosforo_mg": 350.0, "zinc_mg": 2.9, "selenio_ug": 6.0,
        "vitamina_a_ug": 0.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 9.0, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.15, "vitamina_b2_mg": 0.1, "vitamina_b3_mg": 13.5, "vitamina_b6_mg": 0.45, "folatos_b9_ug": 85.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 52,
        "nombre": "Semillas de chía",
        "familia": "Frutos Secos y Semillas",
        "kcal": 486.0, "energia_kj": 2034.0, "proteina_g": 16.5, "carbohidratos_g": 42.1, "grasa_g": 30.7, "fibra_g": 34.4, "agua_g": 5.8,
        "grasa_sat_g": 3.3, "grasa_mono_g": 2.3, "grasa_poli_g": 23.7, "colesterol_mg": 0.0,
        "calcio_mg": 631.0, "hierro_mg": 7.7, "magnesio_mg": 335.0, "potasio_mg": 407.0, "sodio_mg": 16.0, "fosforo_mg": 860.0, "zinc_mg": 4.6, "selenio_ug": 55.0,
        "vitamina_a_ug": 54.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.5, "vitamina_c_mg": 1.6, "vitamina_b1_mg": 0.62, "vitamina_b2_mg": 0.17, "vitamina_b3_mg": 8.8, "vitamina_b6_mg": 0.0, "folatos_b9_ug": 49.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 53,
        "nombre": "Aguacate Hass",
        "familia": "Frutas Frescas",
        "kcal": 160.0, "energia_kj": 670.0, "proteina_g": 2.0, "carbohidratos_g": 8.5, "grasa_g": 14.7, "fibra_g": 6.7, "agua_g": 73.0,
        "grasa_sat_g": 2.1, "grasa_mono_g": 9.8, "grasa_poli_g": 1.8, "colesterol_mg": 0.0,
        "calcio_mg": 12.0, "hierro_mg": 0.6, "magnesio_mg": 29.0, "potasio_mg": 485.0, "sodio_mg": 7.0, "fosforo_mg": 52.0, "zinc_mg": 0.6, "selenio_ug": 0.4,
        "vitamina_a_ug": 7.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 2.1, "vitamina_c_mg": 10.0, "vitamina_b1_mg": 0.07, "vitamina_b2_mg": 0.13, "vitamina_b3_mg": 1.7, "vitamina_b6_mg": 0.26, "folatos_b9_ug": 81.0, "vitamina_b12_ug": 0.0
    },

    # 9. BÁSICOS Y SUPLEMENTOS
    {
        "id": 54,
        "nombre": "Cacao puro en polvo desgrasado (100%)",
        "familia": "Condimentos, Especias y Dulces",
        "kcal": 315.0, "energia_kj": 1318.0, "proteina_g": 25.0, "carbohidratos_g": 14.0, "grasa_g": 11.0, "fibra_g": 33.0, "agua_g": 3.0,
        "grasa_sat_g": 6.8, "grasa_mono_g": 3.6, "grasa_poli_g": 0.4, "colesterol_mg": 0.0,
        "calcio_mg": 130.0, "hierro_mg": 14.0, "magnesio_mg": 500.0, "potasio_mg": 1500.0, "sodio_mg": 20.0, "fosforo_mg": 650.0, "zinc_mg": 6.8, "selenio_ug": 14.0,
        "vitamina_a_ug": 0.0, "vitamina_d_ug": 0.0, "vitamina_e_mg": 0.3, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.1, "vitamina_b2_mg": 0.3, "vitamina_b3_mg": 2.2, "vitamina_b6_mg": 0.15, "folatos_b9_ug": 38.0, "vitamina_b12_ug": 0.0
    },
    {
        "id": 55,
        "nombre": "Proteína Whey aislada / concentrada (polvo)",
        "familia": "Preparaciones Mixtas y Varios",
        "kcal": 380.0, "energia_kj": 1600.0, "proteina_g": 80.0, "carbohidratos_g": 5.0, "grasa_g": 3.5, "fibra_g": 0.0, "agua_g": 5.0,
        "grasa_sat_g": 2.0, "grasa_mono_g": 0.8, "grasa_poli_g": 0.4, "colesterol_mg": 45.0,
        "calcio_mg": 460.0, "hierro_mg": 0.5, "magnesio_mg": 60.0, "potasio_mg": 480.0, "sodio_mg": 180.0, "fosforo_mg": 320.0, "zinc_mg": 0.8, "selenio_ug": 25.0,
        "vitamina_a_ug": 25.0, "vitamina_d_ug": 0.5, "vitamina_e_mg": 0.2, "vitamina_c_mg": 0.0, "vitamina_b1_mg": 0.1, "vitamina_b2_mg": 0.8, "vitamina_b3_mg": 0.5, "vitamina_b6_mg": 0.2, "folatos_b9_ug": 20.0, "vitamina_b12_ug": 2.5
    }
]

def recreate_and_seed_diet_foods():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Eliminar tabla anterior para actualizar esquema completo con micronutrientes
    cursor.execute("DROP TABLE IF EXISTS diet_foods")

    cursor.execute("""
    CREATE TABLE diet_foods (
        id INTEGER PRIMARY KEY,
        nombre TEXT NOT NULL,
        familia TEXT,
        kcal REAL DEFAULT 0,
        energia_kj REAL DEFAULT 0,
        proteina_g REAL DEFAULT 0,
        carbohidratos_g REAL DEFAULT 0,
        grasa_g REAL DEFAULT 0,
        fibra_g REAL DEFAULT 0,
        agua_g REAL DEFAULT 0,
        grasa_sat_g REAL DEFAULT 0,
        grasa_mono_g REAL DEFAULT 0,
        grasa_poli_g REAL DEFAULT 0,
        colesterol_mg REAL DEFAULT 0,
        calcio_mg REAL DEFAULT 0,
        hierro_mg REAL DEFAULT 0,
        magnesio_mg REAL DEFAULT 0,
        potasio_mg REAL DEFAULT 0,
        sodio_mg REAL DEFAULT 0,
        fosforo_mg REAL DEFAULT 0,
        zinc_mg REAL DEFAULT 0,
        selenio_ug REAL DEFAULT 0,
        vitamina_a_ug REAL DEFAULT 0,
        vitamina_d_ug REAL DEFAULT 0,
        vitamina_e_mg REAL DEFAULT 0,
        vitamina_c_mg REAL DEFAULT 0,
        vitamina_b1_mg REAL DEFAULT 0,
        vitamina_b2_mg REAL DEFAULT 0,
        vitamina_b3_mg REAL DEFAULT 0,
        vitamina_b6_mg REAL DEFAULT 0,
        folatos_b9_ug REAL DEFAULT 0,
        vitamina_b12_ug REAL DEFAULT 0,
        fuente_datos TEXT DEFAULT 'BEDCA Oficial'
    )""")

    # 1. Insertar primero los alimentos básicos canónicos curados
    inserted_ids = set()
    for f in BEDCA_STAPLE_FOODS:
        cursor.execute("""
        INSERT INTO diet_foods (
            id, nombre, familia, kcal, energia_kj, proteina_g, carbohidratos_g, grasa_g, fibra_g, agua_g,
            grasa_sat_g, grasa_mono_g, grasa_poli_g, colesterol_mg, calcio_mg, hierro_mg, magnesio_mg,
            potasio_mg, sodio_mg, fosforo_mg, zinc_mg, selenio_ug, vitamina_a_ug, vitamina_d_ug,
            vitamina_e_mg, vitamina_c_mg, vitamina_b1_mg, vitamina_b2_mg, vitamina_b3_mg, vitamina_b6_mg,
            folatos_b9_ug, vitamina_b12_ug, fuente_datos
        ) VALUES (
            :id, :nombre, :familia, :kcal, :energia_kj, :proteina_g, :carbohidratos_g, :grasa_g, :fibra_g, :agua_g,
            :grasa_sat_g, :grasa_mono_g, :grasa_poli_g, :colesterol_mg, :calcio_mg, :hierro_mg, :magnesio_mg,
            :potasio_mg, :sodio_mg, :fosforo_mg, :zinc_mg, :selenio_ug, :vitamina_a_ug, :vitamina_d_ug,
            :vitamina_e_mg, :vitamina_c_mg, :vitamina_b1_mg, :vitamina_b2_mg, :vitamina_b3_mg, :vitamina_b6_mg,
            :folatos_b9_ug, :vitamina_b12_ug, 'BEDCA (Ministerio de Sanidad / AESAN)'
        )""", f)
        inserted_ids.add(f["id"])

    # 2. Cargar alimentos adicionales reales del consolidado (descartando los placeholder "Alimento_XXX")
    imported_from_csv = 0
    if os.path.exists(CSV_LOCAL):
        with open(CSV_LOCAL, mode="r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f, delimiter=";")
            for r in reader:
                name = (r.get("nombre") or "").strip().strip('"')
                if not name or "alimento_" in name.lower() or len(name) < 3:
                    continue

                fid = int(float(r.get("id_ingrediente") or r.get("\ufeffid_ingrediente") or 0))
                # Ajustar id si colisiona con los staple
                if fid in inserted_ids or fid < 100:
                    fid += 2000

                def pf(val, default=0.0):
                    try:
                        v = str(val).replace(",", ".").strip()
                        return float(v) if v else default
                    except:
                        return default

                kcal = pf(r.get("energia_kcal"))
                # Corregir si kcal era en kJ (> 900 para un alimento que no sea aceite puro)
                if kcal > 950 and "aceite" not in name.lower() and "manteca" not in name.lower():
                    kcal = round(kcal / 4.184, 1)

                cursor.execute("""
                INSERT OR REPLACE INTO diet_foods (
                    id, nombre, familia, kcal, energia_kj, proteina_g, carbohidratos_g, grasa_g, fibra_g,
                    grasa_sat_g, grasa_mono_g, grasa_poli_g, calcio_mg, hierro_mg, magnesio_mg,
                    potasio_mg, sodio_mg, fosforo_mg, zinc_mg, selenio_ug, vitamina_a_ug, vitamina_d_ug,
                    vitamina_e_mg, vitamina_c_mg, vitamina_b1_mg, vitamina_b2_mg, vitamina_b3_mg, vitamina_b6_mg,
                    folatos_b9_ug, vitamina_b12_ug, fuente_datos
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    fid, name, (r.get("grupo_bedca") or "General").strip().strip('"'),
                    kcal, pf(r.get("energia_kj")), pf(r.get("proteina_g")), pf(r.get("carbohidratos_g")), pf(r.get("grasa_total_g")), pf(r.get("fibra_g")),
                    pf(r.get("grasa_sat_g")), pf(r.get("grasa_mono_g")), pf(r.get("grasa_poli_g")),
                    pf(r.get("calcio_mg")), pf(r.get("hierro_mg")), pf(r.get("magnesio_mg")), pf(r.get("potasio_mg")), pf(r.get("sodio_mg")),
                    pf(r.get("fosforo_mg")), pf(r.get("zinc_mg")), pf(r.get("selenio_ug")),
                    pf(r.get("vitamina_a_ug")), pf(r.get("vitamina_d_ug")), pf(r.get("vitamina_e_mg")), pf(r.get("vitamina_c_mg")),
                    pf(r.get("vitamina_b1_mg")), pf(r.get("vitamina_b2_mg")), pf(r.get("vitamina_b3_mg")), pf(r.get("vitamina_b6_mg")),
                    pf(r.get("folatos_b9_ug")), pf(r.get("vitamina_b12_ug")),
                    "BEDCA Consolidado"
                ))
                inserted_ids.add(fid)
                imported_from_csv += 1

    conn.commit()

    cursor.execute("SELECT count(*) FROM diet_foods")
    total = cursor.fetchone()[0]
    conn.close()

    print(f"Base de datos de alimentos actualizada con éxito:")
    print(f" - {len(BEDCA_STAPLE_FOODS)} alimentos básicos canónicos de consulta con micronutrientes completos.")
    print(f" - {imported_from_csv} alimentos adicionales limpios de BEDCA.")
    print(f" - Total en diet_foods: {total} alimentos activos.")

    # Exportar CSV maestro consolidado limpio
    export_clean_foods_csv()

def export_clean_foods_csv():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM diet_foods ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    if not rows: return
    fieldnames = list(rows[0].keys())

    for path in [CSV_LOCAL, CSV_GDRIVE]:
        if path == CSV_GDRIVE and not os.path.exists(os.path.dirname(CSV_GDRIVE)):
            continue
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, mode="w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
                writer.writeheader()
                for r in rows:
                    writer.writerow(r)
            print(f"CSV de alimentos guardado en: {path}")
        except Exception as e:
            print(f"Error escribiendo CSV en {path}: {e}")

if __name__ == "__main__":
    recreate_and_seed_diet_foods()
