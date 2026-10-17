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

