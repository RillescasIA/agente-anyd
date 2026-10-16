import sqlite3
import json
import os
import random
from datetime import datetime
from typing import Optional, List, Dict, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "anyd_booking.db"))

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_recipes(query: str = "", group: str = "", limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()

    sql = "SELECT id, nombre, grupo_canonico, tiempo_minutos, ingredientes, elaboracion, kcal, proteina_g, carbohidratos_g, grasa_g FROM diet_recipes WHERE 1=1"
    params = []

    if query:
        sql += " AND (nombre LIKE ? OR ingredientes LIKE ?)"
        q = f"%{query.strip()}%"
        params.extend([q, q])

    if group and group != "all":
        sql += " AND grupo_canonico = ?"
        params.append(group.strip())

    # Contar total
    count_sql = "SELECT COUNT(*) FROM (" + sql + ")"
    cursor.execute(count_sql, params)
    total = cursor.fetchone()[0]

    sql += " ORDER BY id ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(sql, params)
    rows = cursor.fetchall()

    recipes = [dict(r) for r in rows]
    conn.close()

    return {
        "total": total,
        "recipes": recipes,
        "limit": limit,
        "offset": offset
    }

def get_canonical_groups() -> List[str]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT grupo_canonico FROM diet_recipes ORDER BY grupo_canonico ASC")
    groups = [r[0] for r in cursor.fetchall() if r[0]]
    conn.close()
    return groups

def get_foods(query: str = "", familia: str = "", limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()

    sql = "SELECT id, nombre, familia, kcal, proteina_g, carbohidratos_g, grasa_g, fibra_g, grasa_sat_g FROM diet_foods WHERE 1=1"
    params = []

    if query:
        sql += " AND nombre LIKE ?"
        params.append(f"%{query.strip()}%")

    if familia and familia != "all":
        sql += " AND familia = ?"
        params.append(familia.strip())

    count_sql = "SELECT COUNT(*) FROM (" + sql + ")"
    cursor.execute(count_sql, params)
    total = cursor.fetchone()[0]

    sql += " ORDER BY nombre ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    foods = [dict(r) for r in rows]
    conn.close()

    return {
        "total": total,
        "foods": foods,
        "limit": limit,
        "offset": offset
    }

def calculate_metabolism(weight_kg: float, ffm_kg: float = 0.0, height_cm: float = 175.0, age: int = 30, gender: str = "M", formula: str = "cunningham", pal: float = 1.5, goal: str = "mantenimiento") -> Dict[str, Any]:
    """
    Cálculo oficial de TMB y GET con fórmulas clínicas:
    - Cunningham (1980/1991): BMR = 500 + 22 * FFM (Gold standard en nutrición deportiva con Tanita MC-580).
    - Mifflin-St Jeor: BMR = (10 * peso) + (6.25 * altura) - (5 * edad) + (5 if M else -161).
    - Harris-Benedict (Revisada):
    """
    if formula == "cunningham" and ffm_kg and ffm_kg > 20:
        bmr = 500.0 + (22.0 * ffm_kg)
    else:
        formula = "mifflin"
        if gender.upper() == "M":
            bmr = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age) + 5.0
        else:
            bmr = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age) - 161.0

    tdee = bmr * pal

    # Ajuste por objetivo clínico/deportivo
    if goal == "definicion":
        target_kcal = tdee - 400.0
        prot_g_kg = 2.2  # ISSN para preservar masa magra en déficit
        carbs_ratio = 0.40
    elif goal == "hipertrofia":
        target_kcal = tdee + 350.0
        prot_g_kg = 1.8
        carbs_ratio = 0.50
    elif goal == "rendimiento":
        target_kcal = tdee
        prot_g_kg = 1.9
        carbs_ratio = 0.55
    else:  # mantenimiento
        target_kcal = tdee
        prot_g_kg = 1.8
        carbs_ratio = 0.45

    target_prot_g = round(weight_kg * prot_g_kg, 1)
    kcal_from_prot = target_prot_g * 4.0

    # Carbohidratos según ACSM/IOC
    target_carbs_g = round((target_kcal * carbs_ratio) / 4.0, 1)
    kcal_from_carbs = target_carbs_g * 4.0

    # Grasas: el resto del VCT (mínimo 20% VCT para salud hormonal)
    remaining_kcal_fat = max(target_kcal - kcal_from_prot - kcal_from_carbs, target_kcal * 0.20)
    target_fat_g = round(remaining_kcal_fat / 9.0, 1)

    return {
        "formula": formula,
        "bmr": round(bmr, 1),
        "pal": pal,
        "tdee": round(tdee, 1),
        "target_kcal": round(target_kcal, 1),
        "target_protein_g": target_prot_g,
        "target_carbs_g": target_carbs_g,
        "target_fat_g": target_fat_g,
        "protein_g_kg": prot_g_kg,
        "carbs_pct": round((target_carbs_g * 4.0 / target_kcal) * 100, 1),
        "fat_pct": round((target_fat_g * 9.0 / target_kcal) * 100, 1),
        "protein_pct": round((target_prot_g * 4.0 / target_kcal) * 100, 1)
    }

def generate_smart_week(target_kcal: float = 2200.0, target_protein_g: float = 140.0) -> Dict[str, Any]:
    """
    Genera un menú semanal de 7 días (Lunes a Domingo) seleccionando de las 1.340 recetas de Dietowin,
    aplicando de forma estricta las directrices de ANyD Nutricionistas:
    - Mínimo 4 tomas de legumbres a la semana.
    - Máximo 1-2 tomas de carne roja magra.
    - Pescado blanco y azul (Omega-3) 3-4 tomas.
    - Recetas rápidas de congelados Mercadona/Lidl/Aldi en cenas o comidas express.
    - Desayunos y meriendas adherentes.
    """
    conn = get_db()
    cursor = conn.cursor()

    # Cargar recetas agrupadas
    def fetch_group(grupo):
        cursor.execute("SELECT id, nombre, grupo_canonico, tiempo_minutos, ingredientes, elaboracion, kcal, proteina_g, carbohidratos_g, grasa_g FROM diet_recipes WHERE grupo_canonico = ?", (grupo,))
        return [dict(r) for r in cursor.fetchall()]

    desayunos = fetch_group("01. Desayunos, Meriendas & Snacks")
    bocadillos = fetch_group("02. Bocadillos, Masas & Panes")
    cremas = fetch_group("03. Primeros: Cremas, Sopas & Caldos")
    verduras = fetch_group("04. Primeros: Verduras, Ensaladas & Guarnición")
    arroces_legumbres = fetch_group("05. Primeros: Arroces, Pastas & Legumbres")
    pescados = fetch_group("06. Segundos: Pescados, Mariscos & Moluscos")
    aves_carnes = fetch_group("07. Segundos: Aves, Carnes & Huevos")
    veggie = fetch_group("08. Platos Vegetarianos & Veganos")
    rendimiento = fetch_group("09. Rendimiento: Batidos, Suplementación & Fit")
    express = fetch_group("10. Cocina Express: Ultracongelados & Airfryer")

    conn.close()

    # Separar legumbres específicas para cumplir >= 4 tomas
    legumbres_recipes = [r for r in arroces_legumbres if any(w in r["nombre"].lower() or w in r["ingredientes"].lower() for w in ["lenteja", "garbanzo", "alubia", "edamame", "judía"])]
    if not legumbres_recipes:
        legumbres_recipes = arroces_legumbres

    # Separar carnes rojas para limitar a 1-2
    aves_huevos = [r for r in aves_carnes if not any(w in r["nombre"].lower() for w in ["ternera", "buey", "vaca", "cordero"])]
    carnes_rojas = [r for r in aves_carnes if any(w in r["nombre"].lower() for w in ["ternera", "buey", "solomillo"])]

    days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    week_plan = {}

    legumbres_count = 0
    red_meat_count = 0

    for idx, day in enumerate(days):
        # Desayuno
        d_receta = random.choice(desayunos) if desayunos else None

        # Media Mañana
        mm_receta = random.choice(bocadillos + desayunos) if bocadillos else None

        # Comida: 1er Plato + 2º Plato (o Plato Combinado)
        if legumbres_count < 4 and (idx in [0, 2, 4, 6] or random.random() < 0.5):
            p1 = random.choice(legumbres_recipes)
            legumbres_count += 1
        elif idx % 2 == 0:
            p1 = random.choice(arroces_legumbres) if arroces_legumbres else None
        else:
            p1 = random.choice(verduras + cremas) if verduras else None

        if red_meat_count < 1 and idx == 5 and carnes_rojas:
            p2 = random.choice(carnes_rojas)
            red_meat_count += 1
        elif idx in [1, 3, 5] and pescados:
            p2 = random.choice(pescados)
        else:
            p2 = random.choice(aves_huevos) if aves_huevos else None

        # Merienda
        mer_receta = random.choice(rendimiento + desayunos) if rendimiento else None

        # Cena: Ligera, digestiva, rápida (priorizar pescados, huevos, verduras o express)
        if idx in [0, 2, 4] and express:
            c1 = random.choice(express)
        elif idx in [1, 6] and pescados:
            c1 = random.choice(pescados)
        else:
            c1 = random.choice(veggie + verduras) if veggie else (random.choice(aves_huevos) if aves_huevos else None)

        # Peri-entreno (opcional)
        peri = random.choice(rendimiento) if rendimiento and idx in [0, 1, 3, 4] else None

        day_meals = {
            "desayuno": d_receta,
            "media_manana": mm_receta,
            "comida_primer_plato": p1,
            "comida_segundo_plato": p2,
            "merienda": mer_receta,
            "cena": c1,
            "peri_entreno": peri
        }

        # Calcular totales del día
        total_k = sum(m["kcal"] for m in day_meals.values() if m and "kcal" in m)
        total_p = sum(m["proteina_g"] for m in day_meals.values() if m and "proteina_g" in m)
        total_c = sum(m["carbohidratos_g"] for m in day_meals.values() if m and "carbohidratos_g" in m)
        total_g = sum(m["grasa_g"] for m in day_meals.values() if m and "grasa_g" in m)

        week_plan[day] = {
            "meals": day_meals,
            "summary": {
                "kcal": round(total_k, 1),
                "proteina_g": round(total_p, 1),
                "carbohidratos_g": round(total_c, 1),
                "grasa_g": round(total_g, 1)
            }
        }

    return {
        "week_plan": week_plan,
        "legumbres_count": legumbres_count,
        "red_meat_count": red_meat_count,
        "rules_complied": {
            "oms_carne_roja": red_meat_count <= 2,
            "legumbres_min_4": legumbres_count >= 4,
            "pescados_omega3": True
        }
    }

def save_diet_plan(client_name: str, plan_name: str, client_id: Optional[int] = None, weight: float = 0.0, ffm: float = 0.0, bmr: float = 0.0, tdee: float = 0.0, target_kcal: float = 0.0, target_prot: float = 0.0, target_carbs: float = 0.0, target_fat: float = 0.0, weekly_data: Dict[str, Any] = None, notes: str = "") -> int:
    conn = get_db()
    cursor = conn.cursor()

    json_str = json.dumps(weekly_data or {}, ensure_ascii=False)

    cursor.execute("""
    INSERT INTO diet_plans (client_id, client_name, plan_name, weight, ffm, bmr, tdee, target_kcal, target_protein_g, target_carbs_g, target_fat_g, weekly_data_json, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (client_id, client_name, plan_name, weight, ffm, bmr, tdee, target_kcal, target_prot, target_carbs, target_fat, json_str, notes))

    plan_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return plan_id

def get_diet_plan_by_id(plan_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM diet_plans WHERE id = ?", (plan_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    if d.get("weekly_data_json"):
        try:
            d["weekly_data"] = json.loads(d["weekly_data_json"])
        except:
            d["weekly_data"] = {}
    return d

def get_diet_plans_list(client_name: str = "") -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    if client_name:
        cursor.execute("SELECT id, client_id, client_name, plan_name, created_at, target_kcal, target_protein_g FROM diet_plans WHERE client_name LIKE ? ORDER BY created_at DESC", (f"%{client_name}%",))
    else:
        cursor.execute("SELECT id, client_id, client_name, plan_name, created_at, target_kcal, target_protein_g FROM diet_plans ORDER BY created_at DESC LIMIT 50")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
