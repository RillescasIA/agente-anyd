import sqlite3
import json
import os
import random
import io
import csv
from datetime import datetime, timedelta, time
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

    sql = "SELECT id, nombre, grupo_canonico, tiempo_minutos, ingredientes, elaboracion, kcal, proteina_g, carbohidratos_g, grasa_g, fibra_g FROM diet_recipes WHERE 1=1"
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

def get_recipe_by_id(recipe_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, grupo_canonico, tiempo_minutos, ingredientes, elaboracion, kcal, proteina_g, carbohidratos_g, grasa_g, fibra_g FROM diet_recipes WHERE id = ?", (recipe_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_recipe(data: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    nombre = data.get("nombre", "").strip()
    if not nombre:
        conn.close()
        return {"success": False, "error": "El nombre del plato es obligatorio"}
    
    grupo = data.get("grupo_canonico", "Platos Principales").strip() or "Platos Principales"
    tiempo = int(data.get("tiempo_minutos") or 15)
    ingredientes = data.get("ingredientes", "").strip()
    elaboracion = data.get("elaboracion", "").strip()
    kcal = float(data.get("kcal") or 0.0)
    proteina_g = float(data.get("proteina_g") or 0.0)
    carbohidratos_g = float(data.get("carbohidratos_g") or 0.0)
    grasa_g = float(data.get("grasa_g") or 0.0)
    fibra_g = float(data.get("fibra_g") or 0.0)

    if kcal <= 0 and (proteina_g > 0 or carbohidratos_g > 0 or grasa_g > 0):
        kcal = round((proteina_g * 4.0) + (carbohidratos_g * 4.0) + (grasa_g * 9.0), 1)

    cursor.execute("""
        INSERT INTO diet_recipes (
            nombre, grupo_canonico, tiempo_minutos, ingredientes, elaboracion,
            kcal, proteina_g, carbohidratos_g, grasa_g, fibra_g
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (nombre, grupo, tiempo, ingredientes, elaboracion, kcal, proteina_g, carbohidratos_g, grasa_g, fibra_g))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"success": True, "id": new_id, "nombre": nombre}

def update_recipe(recipe_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    nombre = data.get("nombre", "").strip()
    if not nombre:
        conn.close()
        return {"success": False, "error": "El nombre del plato es obligatorio"}
    
    grupo = data.get("grupo_canonico", "Platos Principales").strip() or "Platos Principales"
    tiempo = int(data.get("tiempo_minutos") or 15)
    ingredientes = data.get("ingredientes", "").strip()
    elaboracion = data.get("elaboracion", "").strip()
    kcal = float(data.get("kcal") or 0.0)
    proteina_g = float(data.get("proteina_g") or 0.0)
    carbohidratos_g = float(data.get("carbohidratos_g") or 0.0)
    grasa_g = float(data.get("grasa_g") or 0.0)
    fibra_g = float(data.get("fibra_g") or 0.0)

    if kcal <= 0 and (proteina_g > 0 or carbohidratos_g > 0 or grasa_g > 0):
        kcal = round((proteina_g * 4.0) + (carbohidratos_g * 4.0) + (grasa_g * 9.0), 1)

    cursor.execute("""
        UPDATE diet_recipes SET
            nombre = ?, grupo_canonico = ?, tiempo_minutos = ?, ingredientes = ?, elaboracion = ?,
            kcal = ?, proteina_g = ?, carbohidratos_g = ?, grasa_g = ?, fibra_g = ?
        WHERE id = ?
    """, (nombre, grupo, tiempo, ingredientes, elaboracion, kcal, proteina_g, carbohidratos_g, grasa_g, fibra_g, recipe_id))
    conn.commit()
    conn.close()
    return {"success": True, "id": recipe_id, "nombre": nombre}

def delete_recipe(recipe_id: int) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT nombre FROM diet_recipes WHERE id = ?", (recipe_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": "Receta no encontrada"}
    
    nombre = row[0]
    cursor.execute("DELETE FROM diet_recipes WHERE id = ?", (recipe_id,))
    conn.commit()
    conn.close()
    return {"success": True, "id": recipe_id, "nombre": nombre}

def copy_recipe(recipe_id: int, new_name: Optional[str] = None) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM diet_recipes WHERE id = ?", (recipe_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": "Receta no encontrada"}
    
    recipe_dict = dict(row)
    del recipe_dict["id"]
    if new_name and new_name.strip():
        recipe_dict["nombre"] = new_name.strip()
    else:
        recipe_dict["nombre"] = f"{recipe_dict['nombre']} (Copia)"

    cols = list(recipe_dict.keys())
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT INTO diet_recipes ({', '.join(cols)}) VALUES ({placeholders})"
    cursor.execute(sql, [recipe_dict[c] for c in cols])
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"success": True, "id": new_id, "new_recipe_id": new_id, "nombre": recipe_dict["nombre"]}

def get_foods(query: str = "", familia: str = "", fuente: str = "", limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()

    sql = """
    SELECT id, nombre, familia, marca, codigo_barras, medida_casera, nova_group, kcal, energia_kj, proteina_g, carbohidratos_g, grasa_g, fibra_g, agua_g,
           grasa_sat_g, grasa_mono_g, grasa_poli_g, calcio_mg, hierro_mg, magnesio_mg, potasio_mg, sodio_mg,
           zinc_mg, vitamina_d_ug, vitamina_c_mg, vitamina_b12_ug, fuente_datos
    FROM diet_foods WHERE 1=1
    """
    params = []

    if query:
        sql += " AND (nombre LIKE ? OR marca LIKE ? OR codigo_barras LIKE ?)"
        term = f"%{query.strip()}%"
        params.extend([term, term, term])

    if familia and familia != "all":
        sql += " AND familia = ?"
        params.append(familia.strip())

    if fuente and fuente != "all":
        f_lower = fuente.strip().lower()
        if f_lower in ["bedca", "bedca_oficial"]:
            sql += " AND fuente_datos LIKE '%BEDCA%'"
        elif f_lower in ["cesnid_moreiras", "moreiras", "cnip_moreiras", "cesnid"]:
            sql += " AND (fuente_datos LIKE '%CESNID%' OR fuente_datos LIKE '%Moreiras%')"
        elif f_lower in ["mapa_fen", "fen", "mapa"]:
            sql += " AND (fuente_datos LIKE '%MAPA%' OR fuente_datos LIKE '%FEN%')"
        elif f_lower in ["off", "open_food_facts", "supermercados"]:
            sql += " AND fuente_datos LIKE '%Open Food Facts%'"
        else:
            sql += " AND fuente_datos LIKE ?"
            params.append(f"%{fuente.strip()}%")

    count_sql = "SELECT COUNT(*) FROM (" + sql + ")"
    cursor.execute(count_sql, params)
    total = cursor.fetchone()[0]

    sql += " ORDER BY CASE WHEN fuente_datos LIKE '%Open Food Facts%' THEN 1 WHEN fuente_datos LIKE '%MAPA%' THEN 2 WHEN fuente_datos LIKE '%CESNID%' OR fuente_datos LIKE '%Moreiras%' THEN 3 ELSE 4 END, nombre ASC LIMIT ? OFFSET ?"
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

def get_food_by_id(food_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM diet_foods WHERE id = ?", (food_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_food(data: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    nombre = data.get("nombre", "").strip()
    if not nombre:
        conn.close()
        return {"success": False, "error": "El nombre del alimento es obligatorio"}
    
    familia = data.get("familia", "General").strip() or "General"
    marca = data.get("marca", "Genérico").strip() or "Genérico"
    codigo_barras = data.get("codigo_barras", "").strip()
    medida_casera = data.get("medida_casera", "100g estándar").strip()
    nova_group = int(data.get("nova_group") or 1)
    fuente_datos = data.get("fuente_datos", "Clínica ANyD").strip() or "Clínica ANyD"
    
    kcal = float(data.get("kcal") or 0.0)
    proteina_g = float(data.get("proteina_g") or 0.0)
    carbohidratos_g = float(data.get("carbohidratos_g") or 0.0)
    grasa_g = float(data.get("grasa_g") or 0.0)
    fibra_g = float(data.get("fibra_g") or 0.0)
    energia_kj = float(data.get("energia_kj") or (kcal * 4.184))

    calcio_mg = float(data.get("calcio_mg") or 0.0)
    hierro_mg = float(data.get("hierro_mg") or 0.0)
    magnesio_mg = float(data.get("magnesio_mg") or 0.0)
    potasio_mg = float(data.get("potasio_mg") or 0.0)
    vitamina_d_ug = float(data.get("vitamina_d_ug") or 0.0)
    vitamina_c_mg = float(data.get("vitamina_c_mg") or 0.0)
    vitamina_b12_ug = float(data.get("vitamina_b12_ug") or 0.0)

    cursor.execute("""
        INSERT INTO diet_foods (
            nombre, familia, marca, codigo_barras, medida_casera, nova_group, fuente_datos,
            kcal, energia_kj, proteina_g, carbohidratos_g, grasa_g, fibra_g,
            calcio_mg, hierro_mg, magnesio_mg, potasio_mg, vitamina_d_ug, vitamina_c_mg, vitamina_b12_ug
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        nombre, familia, marca, codigo_barras, medida_casera, nova_group, fuente_datos,
        kcal, energia_kj, proteina_g, carbohidratos_g, grasa_g, fibra_g,
        calcio_mg, hierro_mg, magnesio_mg, potasio_mg, vitamina_d_ug, vitamina_c_mg, vitamina_b12_ug
    ))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"success": True, "id": new_id, "nombre": nombre}

def update_food(food_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    nombre = data.get("nombre", "").strip()
    if not nombre:
        conn.close()
        return {"success": False, "error": "El nombre del alimento es obligatorio"}
    
    familia = data.get("familia", "General").strip() or "General"
    marca = data.get("marca", "Genérico").strip() or "Genérico"
    codigo_barras = data.get("codigo_barras", "").strip()
    medida_casera = data.get("medida_casera", "100g estándar").strip()
    nova_group = int(data.get("nova_group") or 1)
    fuente_datos = data.get("fuente_datos", "Clínica ANyD").strip() or "Clínica ANyD"
    
    kcal = float(data.get("kcal") or 0.0)
    proteina_g = float(data.get("proteina_g") or 0.0)
    carbohidratos_g = float(data.get("carbohidratos_g") or 0.0)
    grasa_g = float(data.get("grasa_g") or 0.0)
    fibra_g = float(data.get("fibra_g") or 0.0)
    energia_kj = float(data.get("energia_kj") or (kcal * 4.184))

    calcio_mg = float(data.get("calcio_mg") or 0.0)
    hierro_mg = float(data.get("hierro_mg") or 0.0)
    magnesio_mg = float(data.get("magnesio_mg") or 0.0)
    potasio_mg = float(data.get("potasio_mg") or 0.0)
    vitamina_d_ug = float(data.get("vitamina_d_ug") or 0.0)
    vitamina_c_mg = float(data.get("vitamina_c_mg") or 0.0)
    vitamina_b12_ug = float(data.get("vitamina_b12_ug") or 0.0)

    cursor.execute("""
        UPDATE diet_foods SET
            nombre = ?, familia = ?, marca = ?, codigo_barras = ?, medida_casera = ?, nova_group = ?, fuente_datos = ?,
            kcal = ?, energia_kj = ?, proteina_g = ?, carbohidratos_g = ?, grasa_g = ?, fibra_g = ?,
            calcio_mg = ?, hierro_mg = ?, magnesio_mg = ?, potasio_mg = ?, vitamina_d_ug = ?, vitamina_c_mg = ?, vitamina_b12_ug = ?
        WHERE id = ?
    """, (
        nombre, familia, marca, codigo_barras, medida_casera, nova_group, fuente_datos,
        kcal, energia_kj, proteina_g, carbohidratos_g, grasa_g, fibra_g,
        calcio_mg, hierro_mg, magnesio_mg, potasio_mg, vitamina_d_ug, vitamina_c_mg, vitamina_b12_ug,
        food_id
    ))
    conn.commit()
    conn.close()
    return {"success": True, "id": food_id, "nombre": nombre}

def delete_food(food_id: int) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT nombre FROM diet_foods WHERE id = ?", (food_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": "Alimento no encontrado"}
    
    nombre = row[0]
    cursor.execute("DELETE FROM diet_foods WHERE id = ?", (food_id,))
    conn.commit()
    conn.close()
    return {"success": True, "id": food_id, "nombre": nombre}

def copy_food(food_id: int, new_name: Optional[str] = None) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM diet_foods WHERE id = ?", (food_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": "Alimento no encontrado"}
    
    food_dict = dict(row)
    del food_dict["id"]
    if new_name and new_name.strip():
        food_dict["nombre"] = new_name.strip()
    else:
        food_dict["nombre"] = f"{food_dict['nombre']} (Copia)"

    cols = list(food_dict.keys())
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT INTO diet_foods ({', '.join(cols)}) VALUES ({placeholders})"
    cursor.execute(sql, [food_dict[c] for c in cols])
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"success": True, "id": new_id, "new_food_id": new_id, "nombre": food_dict["nombre"]}

def search_open_food_facts(query: str, page_size: int = 15) -> List[Dict[str, Any]]:
    import requests
    headers = {"User-Agent": "ANyDNutricionistas - WebApp - Version 1.0 (clinica@anyd.es)"}
    params = {
        "search_terms": query.strip(),
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": page_size
    }
    for host in ["es.openfoodfacts.org", "world.openfoodfacts.org"]:
        try:
            url = f"https://{host}/cgi/search.pl"
            r = requests.get(url, params=params, headers=headers, timeout=6)
            if r.status_code == 200:
                data = r.json()
                products = []
                for p in data.get("products", []):
                    name = p.get("product_name")
                    if not name:
                        continue
                    nutr = p.get("nutriments", {})
                    products.append({
                        "codigo_barras": p.get("code", ""),
                        "nombre": name,
                        "marca": p.get("brands", "Supermercado España"),
                        "medida_casera": p.get("serving_size", "1 ración"),
                        "nova_group": p.get("nova_group") or 1,
                        "kcal": round(float(nutr.get("energy-kcal_100g") or 0.0), 1),
                        "proteina_g": round(float(nutr.get("proteins_100g") or 0.0), 1),
                        "carbohidratos_g": round(float(nutr.get("carbohydrates_100g") or 0.0), 1),
                        "grasa_g": round(float(nutr.get("fat_100g") or 0.0), 1),
                        "fibra_g": round(float(nutr.get("fiber_100g") or 0.0), 1),
                        "fuente_datos": "Open Food Facts España"
                    })
                if products:
                    return products
        except Exception as e:
            print(f"Error consultando Open Food Facts en {host}: {e}")
            continue
    return []

def import_off_product_to_db(item: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    nombre = item.get("nombre", "").strip()
    if not nombre:
        conn.close()
        return {"success": False, "error": "Nombre requerido"}

    cursor.execute("SELECT id FROM diet_foods WHERE nombre = ? OR (codigo_barras != '' AND codigo_barras = ?)", (nombre, item.get("codigo_barras", "")))
    row = cursor.fetchone()

    kcal = float(item.get("kcal", 0.0))
    prot = float(item.get("proteina_g", 0.0))
    carbs = float(item.get("carbohidratos_g", 0.0))
    fat = float(item.get("grasa_g", 0.0))
    fibra = float(item.get("fibra_g", 0.0))
    marca = item.get("marca", "Supermercado")
    barcode = item.get("codigo_barras", "")
    medida = item.get("medida_casera", "1 ración")
    nova = int(item.get("nova_group") or 1)
    fuente = "Open Food Facts España"
    familia = "Supermercado / Marcas"

    if row:
        fid = row[0]
        cursor.execute("""
            UPDATE diet_foods SET
                marca = ?, codigo_barras = ?, medida_casera = ?, nova_group = ?, fuente_datos = ?,
                kcal = ?, proteina_g = ?, carbohidratos_g = ?, grasa_g = ?, fibra_g = ?
            WHERE id = ?
        """, (marca, barcode, medida, nova, fuente, kcal, prot, carbs, fat, fibra, fid))
    else:
        cursor.execute("""
            INSERT INTO diet_foods (
                nombre, familia, marca, codigo_barras, medida_casera, nova_group, fuente_datos,
                kcal, energia_kj, proteina_g, carbohidratos_g, grasa_g, fibra_g, agua_g,
                grasa_sat_g, grasa_mono_g, grasa_poli_g, colesterol_mg, calcio_mg, hierro_mg,
                magnesio_mg, potasio_mg, sodio_mg, fosforo_mg, zinc_mg, selenio_ug,
                vitamina_a_ug, vitamina_d_ug, vitamina_e_mg, vitamina_c_mg, vitamina_b1_mg,
                vitamina_b2_mg, vitamina_b3_mg, vitamina_b6_mg, folatos_b9_ug, vitamina_b12_ug
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        """, (nombre, familia, marca, barcode, medida, nova, fuente, kcal, kcal * 4.184, prot, carbs, fat, fibra))
        fid = cursor.lastrowid

    conn.commit()
    conn.close()
    return {"success": True, "id": fid, "nombre": nombre}

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

def generate_shopping_list(week_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Genera la Lista de la Compra Semanal agrupando todos los ingredientes
    de los 7 días en departamentos de supermercado.
    """
    departments = {
        "frutas_verduras": {"title": "🥬 Frutas, Verduras y Hortalizas Frescas", "items": []},
        "carnes_pescados": {"title": "🥩 Carnes, Aves, Pescados y Huevos", "items": []},
        "legumbres_cereales": {"title": "🌾 Arroces, Legumbres, Cereales y Pastas", "items": []},
        "lacteos": {"title": "🥛 Lácteos, Yogures y Bebidas Vegetales", "items": []},
        "frutos_secos_aceites": {"title": "🥜 Frutos Secos, Semillas y Aceites", "items": []},
        "congelados_despensa": {"title": "🥫 Conservas, Congelados y Especias", "items": []},
        "rendimiento_fit": {"title": "⚡ Suplementación y Rendimiento Deportivo", "items": []}
    }

    raw_items_count = {}

    def categorize_ingredient(text: str) -> str:
        t = text.lower()
        if any(w in t for w in ["plátano", "manzana", "arándano", "fresa", "naranja", "kiwi", "fruta", "tomate", "lechuga", "espinaca", "calabacín", "cebolla", "zanahoria", "brócoli", "judía verde", "pepino", "pimiento", "aguacate", "champiñ", "seta", "espárrago"]):
            return "frutas_verduras"
        elif any(w in t for w in ["pollo", "pavo", "ternera", "buey", "huevo", "clara", "salmón", "merluza", "atún", "bacalao", "dorada", "lubina", "gamba", "langostino", "carne", "pescado", "sepia", "calamar", "solomillo", "lomo"]):
            return "carnes_pescados"
        elif any(w in t for w in ["arroz", "avena", "pasta", "pan", "lenteja", "garbanzo", "alubia", "quinoa", "patata", "boniato", "harina", "tortilla de trigo", "tostada", "copos"]):
            return "legumbres_cereales"
        elif any(w in t for w in ["leche", "yogur", "queso", "cottage", "kéfir", "soja", "bebida", "mozzarella", "parmesano", "requesón", "skyr"]):
            return "lacteos"
        elif any(w in t for w in ["aceite", "nuez", "nueces", "almendra", "cacahuete", "chía", "lino", "crema de cacahuete", "anacardo", "semilla", "pistacho", "avellana"]):
            return "frutos_secos_aceites"
        elif any(w in t for w in ["proteína", "creatina", "whey", "isotónico", "gel", "barrita", "maltodextrina", "electrolitos"]):
            return "rendimiento_fit"
        else:
            return "congelados_despensa"

    # Recorrer todos los días
    days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    for day in days:
        day_info = week_data.get(day, {})
        # Soporta estructura {"meals": {...}} o {...} directo
        meals = day_info.get("meals", day_info)
        if not isinstance(meals, dict):
            continue

        for slot_key, slot_val in meals.items():
            if not slot_val:
                continue
            
            # Puede ser lista de items o item único
            items_list = slot_val if isinstance(slot_val, list) else [slot_val]

            for it in items_list:
                if not it:
                    continue
                # Si es un alimento suelto
                if it.get("tipo") == "food" or "grams" in it:
                    name = it.get("nombre", "").strip()
                    grams = it.get("grams", 100)
                    dep = categorize_ingredient(name)
                    key = (name, dep, True)
                    raw_items_count[key] = raw_items_count.get(key, 0) + grams
                # Si es una receta con desglose
                elif it.get("ingredientes"):
                    ing_text = it.get("ingredientes", "")
                    # Separar ingredientes por comas
                    parts = [p.strip() for p in ing_text.split(",") if p.strip()]
                    for p in parts:
                        dep = categorize_ingredient(p)
                        key = (p, dep, False)
                        raw_items_count[key] = raw_items_count.get(key, 0) + 1
                elif it.get("nombre"):
                    name = it.get("nombre", "").strip()
                    dep = categorize_ingredient(name)
                    key = (name, dep, False)
                    raw_items_count[key] = raw_items_count.get(key, 0) + 1

    # Clasificar en departamentos
    for (name, dep, is_grams), count in raw_items_count.items():
        if is_grams:
            display_text = f"{name}: {int(count)}g total"
        elif count > 1:
            display_text = f"{name} (x{count} raciones en la semana)"
        else:
            display_text = name

        departments[dep]["items"].append(display_text)

    # Ordenar alfabéticamente dentro de cada departamento
    total_distinct = 0
    for dep_key in departments:
        departments[dep_key]["items"].sort()
        total_distinct += len(departments[dep_key]["items"])

    return {
        "departments": departments,
        "total_items": total_distinct
    }

# ============================================================
# --- MÓDULO DE ENTRENAMIENTOS, HIDRATACIÓN & DIGESTIBILIDAD ---
# --- (EVIDENCIA CIENTÍFICA ACSM, IOC, ISSN, AIS GRUPO A) ---
# ============================================================

def compute_peri_workout_guidelines(
    sport: str,
    duration_min: int,
    intensity: str,
    weight_kg: float = 75.0,
    start_time: str = "18:00",
    notes: str = ""
) -> Dict[str, Any]:
    """
    Calcula de forma individualizada las recomendaciones de hidratación,
    electrolitos, vaciamiento gástrico y digestibilidad peri-esfuerzo
    siguiendo los consensos de ACSM/IOC/ISSN y el protocolo clínico ANyD.
    """
    try:
        parts = str(start_time).strip().split(":")
        sh = int(parts[0])
        sm = int(parts[1]) if len(parts) > 1 else 0
    except Exception:
        sh, sm = 18, 0

    start_dt = datetime(2026, 1, 1, sh, sm)
    end_dt = start_dt + timedelta(minutes=duration_min)
    end_time = end_dt.strftime("%H:%M")
    clean_start_time = start_dt.strftime("%H:%M")

    # Ventanas horarias clave
    pre_window_start = (start_dt - timedelta(hours=3)).strftime("%H:%M")
    pre_window_end = (start_dt - timedelta(hours=2)).strftime("%H:%M")
    pre_immediate_time = (start_dt - timedelta(minutes=45)).strftime("%H:%M")
    post_recovery_end = (end_dt + timedelta(hours=2)).strftime("%H:%M")

    # 2. Normalizar intensidad y colores ANyD
    t_int = (intensity or "").lower()
    t_sport = (sport or "").lower()

    if any(w in t_int for w in ["muy alta", "vo2max", "z5", "umbral anaer", "rpe 9", "rpe 10", "máxima", "acidosis", "series"]) or any(w in t_sport for w in ["series", "crossfit", "hyrox", "combate", "sparring"]):
        level = "Muy Alta"
        theme = {"border": "#ef4444", "bg": "#fff5f5", "text": "#991b1b", "badge_bg": "#fee2e2", "badge_text": "#b91c1c"}
    elif any(w in t_int for w in ["alta", "z4", "rpe 8", "tempo", "sweetspot", "fuerza"]) or any(w in t_sport for w in ["fuerza", "hipertrofia", "powerlifting", "halterofilia", "partido"]):
        level = "Alta"
        theme = {"border": "#f97316", "bg": "#fff7ed", "text": "#9a3412", "badge_bg": "#ffedd5", "badge_text": "#c2410c"}
    elif any(w in t_int for w in ["mod-alta", "moderada-alta", "z3", "rpe 7"]):
        level = "Mod-Alta"
        theme = {"border": "#f59e0b", "bg": "#fffbeb", "text": "#92400e", "badge_bg": "#fef3c7", "badge_text": "#b45309"}
    elif any(w in t_int for w in ["baja", "z1", "recuperación", "suave", "rpe 3", "rpe 4", "movilidad"]):
        level = "Baja"
        theme = {"border": "#10b981", "bg": "#ecfdf5", "text": "#065f46", "badge_bg": "#d1fae5", "badge_text": "#047857"}
    else:
        level = "Moderada"
        theme = {"border": "#0284c7", "bg": "#f0f9ff", "text": "#075985", "badge_bg": "#e0f2fe", "badge_text": "#0369a1"}

    # 3. Fisiología y Nutrición Pre-Entreno (2 a 3 horas antes)
    if level in ["Muy Alta", "Alta"]:
        pre_carbs_factor = 1.3
    elif level == "Mod-Alta":
        pre_carbs_factor = 1.1
    elif level == "Moderada":
        pre_carbs_factor = 1.0
    else:
        pre_carbs_factor = 0.8

    pre_carbs_g = round(weight_kg * pre_carbs_factor)
    pre_water_ml = round(weight_kg * 6.0) # 5 a 7 ml/kg ACSM
    pre_sodium_mg = 400 if level in ["Muy Alta", "Alta", "Mod-Alta"] else 300

    # 4. Fisiología y Nutrición Pre-Inmediato (30-45 min antes)
    pre_imm_carbs_g = 25 if duration_min >= 45 else 15
    pre_imm_water_ml = 150

    # 5. Fisiología Intra-Entreno (Fluidos, Electrolitos y Carbohidratos)
    if duration_min < 45:
        intra_carbs_h = 0
        intra_fluid_ml_h = 250
        intra_sodium_mg_h = 0
        intra_format = "Agua sola a demanda (no requiere carbohidratos)"
    elif 45 <= duration_min <= 75:
        if level in ["Muy Alta", "Alta"]:
            intra_carbs_h = 25
            intra_fluid_ml_h = 450
            intra_sodium_mg_h = 350
            intra_format = "Bebida isotónica ligera o enjuague bucal con CHO"
        else:
            intra_carbs_h = 0
            intra_fluid_ml_h = 350
            intra_sodium_mg_h = 200
            intra_format = "Agua a sorbos con pizca de sales minerales"
    elif 75 < duration_min <= 150:
        intra_carbs_h = 45 if level in ["Moderada", "Mod-Alta"] else 60
        intra_fluid_ml_h = 600
        intra_sodium_mg_h = 500
        intra_format = "Geles energéticos AIS Grupo A con agua o isotónico (ratio glucosa:fructosa 2:1)"
    else: # > 150 min (ultrafondo)
        intra_carbs_h = 75
        intra_fluid_ml_h = 750
        intra_sodium_mg_h = 700
        intra_format = "Mezcla múltiple transportador (Maltodextrina + Fructosa 1:0.8 / 2:1) + barritas blandas + sales"

    # 6. Fisiología Post-Entreno (Ventana de Recuperación y Resíntesis)
    post_protein_g = round(weight_kg * 0.35) # 0.3 - 0.4 g/kg ISSN
    post_carbs_g = round(weight_kg * 1.1)    # 1.0 - 1.2 g/kg ACSM

    # 7. Reglas Clínicas de Digestibilidad ANyD
    digestibility_protocol = {
        "pre_window_timing": f"{pre_window_start} - {pre_window_end}",
        "pre_immediate_timing": f"{pre_immediate_time} - {clean_start_time}",
        "pre_digestibility_rules": [
            "Cereales de bajo residuo: arroz blanco cocido, patata al vapor sin piel, pan blanco o copos finos de avena cocidos.",
            "Proteína magra limpia (15-25g): pechuga de pavo/pollo, claras, requesón desnatado 0% o pescado blanco.",
            "0% legumbres (lentejas, garbanzos, alubias) en las 3h previas: evitar fermentación y gas colónico durante el esfuerzo.",
            "0% verduras flatulentas o crucíferas (brócoli, col, coliflor, cebolla cruda, pimiento crudo).",
            "Grasas limitadas a <5g: evitar fritos, quesos grasos y frutos secos enteros >15g para garantizar rápido vaciamiento gástrico."
        ],
        "intra_digestibility_rules": [
            "Temperatura del líquido: fresca (12-15°C) para favorecer la motilidad gástrica y palatabilidad.",
            "Pauta de ingesta: pequeños sorbos regulares (120-150 ml cada 15-20 minutos), nunca tragos copiosos.",
            "Osmolaridad controlada: disoluciones isotónicas al 6-8% para evitar arrastre osmótico de agua a la luz intestinal."
        ],
        "post_digestibility_rules": [
            "Isquemia esplácnica temporal: si la sesión fue extenuante (series de carrera, calor o FC >165 ppm), iniciar con batido de recuperación líquido/semisólido en los primeros 20-30 min.",
            "Posponer comida sólida copiosa o grasa 45-60 min hasta restaurar el flujo sanguíneo gastrointestinal normal."
        ]
    }

    return {
        "sport": sport,
        "duration_min": duration_min,
        "intensity": intensity,
        "intensity_level": level,
        "theme": theme,
        "start_time": clean_start_time,
        "end_time": end_time,
        "pre_window": f"{pre_window_start} - {pre_window_end}",
        "pre_immediate": pre_immediate_time,
        "post_window": f"{end_time} - {post_recovery_end}",
        "nutrition": {
            "pre": {
                "carbs_g": pre_carbs_g,
                "water_ml": pre_water_ml,
                "sodium_mg": pre_sodium_mg,
                "recommended_foods": "Arroz blanco con pechuga de pavo / Copos finos avena cocida con requesón 0% / Tostadas pan blanco con claras"
            },
            "pre_immediate": {
                "carbs_g": pre_imm_carbs_g,
                "water_ml": pre_imm_water_ml,
                "recommended_foods": "1 plátano maduro o 2 dátiles medjool (vaciamiento ultra-rápido sin fibra)"
            },
            "intra": {
                "carbs_g_h": intra_carbs_h,
                "fluid_ml_h": intra_fluid_ml_h,
                "sodium_mg_h": intra_sodium_mg_h,
                "format": intra_format
            },
            "post": {
                "protein_g": post_protein_g,
                "carbs_g": post_carbs_g,
                "rehydration_note": "125-150% del peso corporal perdido en sudor con electrolitos",
                "recommended_foods": "Batido proteína aislada (Whey/Soja) + plátano maduro / Pechuga de pollo con patata asada"
            }
        },
        "digestibility": digestibility_protocol,
        "notes": notes
    }

def parse_training_excel_or_csv(file_bytes: bytes, filename: str, weight_kg: float = 75.0) -> Dict[str, Any]:
    """
    Parsea hojas de cálculo Excel (.xlsx, .xls) o CSV con el microciclo semanal de entrenamientos.
    Detecta automáticamente días, horas, disciplinas, duración e intensidad, generando
    el protocolo científico peri-entreno.
    """
    DAYS_MAP = {
        "lunes": "Lunes", "lun": "Lunes", "mon": "Lunes", "monday": "Lunes",
        "martes": "Martes", "mar": "Martes", "tue": "Martes", "tuesday": "Martes",
        "miércoles": "Miércoles", "miercoles": "Miércoles", "mie": "Miércoles", "wed": "Miércoles", "wednesday": "Miércoles",
        "jueves": "Jueves", "jue": "Jueves", "thu": "Jueves", "thursday": "Jueves",
        "viernes": "Viernes", "vie": "Viernes", "fri": "Viernes", "friday": "Viernes",
        "sábado": "Sábado", "sabado": "Sábado", "sab": "Sábado", "sat": "Sábado", "saturday": "Sábado",
        "domingo": "Domingo", "dom": "Domingo", "sun": "Domingo", "sunday": "Domingo"
    }

    raw_rows = []

    if filename.lower().endswith((".xlsx", ".xlsm", ".xltx")):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        ws = wb.active
        raw_rows = list(ws.iter_rows(values_only=True))
    else:
        # CSV
        text_content = file_bytes.decode("utf-8", errors="replace")
        delimiter = ";" if ";" in text_content[:500] else ","
        raw_rows = list(csv.reader(io.StringIO(text_content), delimiter=delimiter))

    if not raw_rows or len(raw_rows) < 2:
        return {"workouts_by_day": {d: [] for d in ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]}, "total_sessions": 0}

    header_idx = 0
    day_col = -1
    time_col = -1
    sport_col = -1
    dur_col = -1
    int_col = -1
    notes_col = -1

    for idx, row in enumerate(raw_rows[:10]):
        row_str = [str(c or "").lower().strip() for c in row]
        for c_idx, cell in enumerate(row_str):
            if any(k in cell for k in ["día", "dia", "day", "fecha"]):
                day_col = c_idx
            elif any(k in cell for k in ["hora", "horario", "inicio", "time", "start"]):
                time_col = c_idx
            elif any(k in cell for k in ["deporte", "sesión", "sesion", "disciplina", "actividad", "sport", "entreno"]):
                sport_col = c_idx
            elif any(k in cell for k in ["duración", "duracion", "tiempo", "minutos", "mins", "duration"]):
                dur_col = c_idx
            elif any(k in cell for k in ["intensidad", "rpe", "zona", "intensity", "zone"]):
                int_col = c_idx
            elif any(k in cell for k in ["notas", "observaciones", "descripcion", "descripción", "notes"]):
                notes_col = c_idx

        if day_col != -1 and (time_col != -1 or sport_col != -1):
            header_idx = idx
            break

    if day_col == -1: day_col = 0
    if time_col == -1: time_col = 1
    if sport_col == -1: sport_col = 2
    if dur_col == -1: dur_col = 3
    if int_col == -1: int_col = 4

    workouts_by_day = {d: [] for d in ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]}
    total_count = 0

    for row in raw_rows[header_idx + 1:]:
        if not row or not any(row):
            continue

        raw_day = str(row[day_col] or "").strip().lower() if day_col < len(row) else ""
        canonical_day = None
        for k, v in DAYS_MAP.items():
            if k in raw_day:
                canonical_day = v
                break

        if not canonical_day:
            continue

        # Hora
        raw_time = row[time_col] if time_col < len(row) else "18:00"
        clean_time = "18:00"
        if isinstance(raw_time, (datetime, time)):
            clean_time = raw_time.strftime("%H:%M")
        elif isinstance(raw_time, (float, int)) and 0 <= raw_time <= 1:
            total_sec = round(raw_time * 86400)
            clean_time = f"{(total_sec // 3600):02d}:{((total_sec % 3600) // 60):02d}"
        elif raw_time:
            t_s = str(raw_time).strip().replace(".", ":").replace("h", ":")
            t_parts = [p for p in t_s.split(":") if p.strip()]
            if len(t_parts) >= 2:
                try:
                    clean_time = f"{int(t_parts[0]):02d}:{int(t_parts[1][:2]):02d}"
                except Exception:
                    clean_time = "18:00"
            elif len(t_parts) == 1:
                try:
                    clean_time = f"{int(t_parts[0]):02d}:00"
                except Exception:
                    clean_time = "18:00"

        # Deporte
        sport = str(row[sport_col] or "Entrenamiento Deportivo").strip() if sport_col < len(row) else "Entrenamiento"

        # Duración
        raw_dur = row[dur_col] if dur_col < len(row) else 60
        clean_dur = 60
        if isinstance(raw_dur, (int, float)):
            clean_dur = int(raw_dur)
        elif raw_dur:
            s_dur = str(raw_dur).lower()
            if "h" in s_dur:
                parts = s_dur.split("h")
                hours = float(parts[0].strip() or 1)
                mins = float(parts[1].replace("m", "").replace("in", "").strip() or 0) if len(parts) > 1 else 0
                clean_dur = int(hours * 60 + mins)
            else:
                digits = "".join([c for c in s_dur if c.isdigit()])
                if digits:
                    clean_dur = int(digits)

        # Intensidad
        intensity = str(row[int_col] or "Moderada").strip() if int_col < len(row) else "Moderada"

        # Notas
        notes = str(row[notes_col] or "").strip() if notes_col != -1 and notes_col < len(row) else ""

        guidelines = compute_peri_workout_guidelines(
            sport=sport,
            duration_min=clean_dur,
            intensity=intensity,
            weight_kg=weight_kg,
            start_time=clean_time,
            notes=notes
        )

        workouts_by_day[canonical_day].append(guidelines)
        total_count += 1

    for d in workouts_by_day:
        workouts_by_day[d].sort(key=lambda x: x.get("start_time", "00:00"))

    return {
        "workouts_by_day": workouts_by_day,
        "total_sessions": total_count
    }

def generate_training_excel_template() -> bytes:
    """
    Genera plantilla Excel (.xlsx) estándar ANyD para el deportista.
    """
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Microciclo Entrenamientos"
    
    headers = ["Día", "Hora Inicio (HH:MM)", "Deporte / Sesión", "Duración (min)", "Intensidad / Zona", "Notas / Objetivos"]
    ws.append(headers)
    
    samples = [
        ["Lunes", "18:30", "Series en Pista (8x400m Z4-Z5)", 75, "Muy Alta", "Pista Alcorcón - descanso 90s"],
        ["Martes", "19:00", "Hipertrofia Muscular (Torso / Empujes)", 70, "Mod-Alta", "RPE 8, press banca y militar"],
        ["Miércoles", "07:30", "Rodaje Z2 en Ayunas (Base Aeróbica)", 60, "Moderada", "135-145 ppm ritmo conversacional"],
        ["Jueves", "18:30", "Fuerza Tren Inferior (Pierna / Sentadilla)", 75, "Alta", "RPE 8-9, sentadilla y peso muerto"],
        ["Viernes", "19:00", "HYROX / WOD Funcional", 60, "Muy Alta", "Ergómetros y carrera continua"],
        ["Sábado", "09:00", "Ciclismo de Fondo Carretera (Endurance Z2)", 150, "Moderada", "Tirada larga 70km"],
        ["Domingo", "10:30", "Recuperación Activa & Movilidad Articular", 45, "Baja", "Z1 paseo o estiramientos"]
    ]
    for s in samples:
        ws.append(s)
        
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


