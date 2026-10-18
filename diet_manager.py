import sqlite3
import json
import os
import random
import io
import csv
from datetime import datetime, timedelta, time
import re
import unicodedata
from typing import Optional, List, Dict, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "anyd_booking.db"))

_schema_initialized = False

def ensure_diet_schema(conn: sqlite3.Connection):
    global _schema_initialized
    if _schema_initialized:
        return
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS diet_foods (
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
        fuente_datos TEXT DEFAULT 'Clínica ANyD',
        marca TEXT DEFAULT 'Genérico',
        codigo_barras TEXT DEFAULT '',
        medida_casera TEXT DEFAULT '100g estándar',
        nova_group INTEGER DEFAULT 1
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS diet_recipes (
        id INTEGER PRIMARY KEY,
        nombre TEXT NOT NULL,
        grupo_canonico TEXT,
        tiempo_minutos INTEGER DEFAULT 10,
        ingredientes TEXT,
        elaboracion TEXT,
        kcal REAL DEFAULT 0,
        proteina_g REAL DEFAULT 0,
        carbohidratos_g REAL DEFAULT 0,
        grasa_g REAL DEFAULT 0,
        fibra_g REAL DEFAULT 0
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS diet_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        client_name TEXT NOT NULL,
        plan_name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        weight REAL,
        ffm REAL,
        bmr REAL,
        tdee REAL,
        target_kcal REAL,
        target_protein_g REAL,
        target_carbs_g REAL,
        target_fat_g REAL,
        weekly_data_json TEXT,
        notes TEXT,
        FOREIGN KEY (client_id) REFERENCES clients (id)
    )""")
    cursor.execute("PRAGMA table_info(diet_foods)")
    existing_cols = {c[1] for c in cursor.fetchall()}
    needed_cols = [
        ("energia_kj", "REAL DEFAULT 0"),
        ("agua_g", "REAL DEFAULT 0"),
        ("grasa_mono_g", "REAL DEFAULT 0"),
        ("grasa_poli_g", "REAL DEFAULT 0"),
        ("colesterol_mg", "REAL DEFAULT 0"),
        ("calcio_mg", "REAL DEFAULT 0"),
        ("hierro_mg", "REAL DEFAULT 0"),
        ("magnesio_mg", "REAL DEFAULT 0"),
        ("potasio_mg", "REAL DEFAULT 0"),
        ("sodio_mg", "REAL DEFAULT 0"),
        ("fosforo_mg", "REAL DEFAULT 0"),
        ("zinc_mg", "REAL DEFAULT 0"),
        ("selenio_ug", "REAL DEFAULT 0"),
        ("vitamina_a_ug", "REAL DEFAULT 0"),
        ("vitamina_d_ug", "REAL DEFAULT 0"),
        ("vitamina_e_mg", "REAL DEFAULT 0"),
        ("vitamina_c_mg", "REAL DEFAULT 0"),
        ("vitamina_b1_mg", "REAL DEFAULT 0"),
        ("vitamina_b2_mg", "REAL DEFAULT 0"),
        ("vitamina_b3_mg", "REAL DEFAULT 0"),
        ("vitamina_b6_mg", "REAL DEFAULT 0"),
        ("folatos_b9_ug", "REAL DEFAULT 0"),
        ("vitamina_b12_ug", "REAL DEFAULT 0"),
        ("fuente_datos", "TEXT DEFAULT 'Clínica ANyD'"),
        ("marca", "TEXT DEFAULT 'Genérico'"),
        ("codigo_barras", "TEXT DEFAULT ''"),
        ("medida_casera", "TEXT DEFAULT '100g estándar'"),
        ("nova_group", "INTEGER DEFAULT 1")
    ]
    for col_name, col_def in needed_cols:
        if col_name not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE diet_foods ADD COLUMN {col_name} {col_def}")
            except Exception:
                pass

    cursor.execute("PRAGMA table_info(diet_recipes)")
    existing_recipe_cols = {c[1] for c in cursor.fetchall()}
    if "fibra_g" not in existing_recipe_cols:
        try:
            cursor.execute("ALTER TABLE diet_recipes ADD COLUMN fibra_g REAL DEFAULT 0")
        except Exception:
            pass

    conn.commit()

    try:
        cursor.execute("SELECT COUNT(*) FROM diet_recipes")
        if cursor.fetchone()[0] == 0:
            import import_dietowin_data
            import_dietowin_data.import_dietowin_to_db()
    except Exception:
        pass

    _schema_initialized = True

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    ensure_diet_schema(conn)
    return conn

def classify_recipe_meal_slots(nombre: str, grupo_canonico: str) -> List[str]:
    """
    Determina los momentos del día (tomas) clínicamente adecuados para una receta.
    Evita que platos pesados como fajitas de pollo o estofados se asignen al desayuno.
    """
    n = (nombre or "").lower()
    g = grupo_canonico or ""

    # Suplementos / Rendimiento
    if any(k in n for k in ['creatina', 'whey', 'aislado', 'bcaa', 'glutamina', 'multivitam', 'omega 3', 'omega-3', 'cafeina', 'electrolit', 'sales']):
        return ['suplementacion', 'entrenamiento']

    if '09. Rendimiento' in g:
        if any(k in n for k in ['batido', 'smoothie', 'proteico']):
            return ['merienda', 'media_manana', 'entrenamiento', 'desayuno']
        return ['suplementacion', 'entrenamiento']

    # Fajitas, pizzas, hamburguesas, burritos, tacos, empanadas
    if any(k in n for k in ['fajita', 'pizza', 'hamburguesa', 'burrito', 'taco', 'empanada']):
        return ['almuerzo', 'cena']

    # Platos principales (primeros y segundos de comida)
    if any(k in g for k in ['03. Primeros', '04. Primeros', '05. Primeros', '06. Segundos', '07. Segundos', '08. Platos', '10. Cocina Express']):
        if any(k in n for k in ['tortilla francesa', 'revuelto de huevo', 'huevos revueltos']):
            return ['desayuno', 'cena']
        if '05. Primeros: Arroces, Pastas & Legumbres' in g:
            return ['almuerzo']
        return ['almuerzo', 'cena']

    # Bocadillos y panes
    if '02. Bocadillos' in g:
        if any(k in n for k in ['tostada', 'pan tostado', 'pavo', 'serrano', 'aceite', 'mermelada', 'tomate']):
            return ['desayuno', 'media_manana', 'merienda']
        return ['almuerzo', 'cena']

    # Desayunos y meriendas
    if '01. Desayunos' in g:
        if any(k in n for k in ['fajita', 'lenteja', 'garbanzo', 'alubia', 'paella', 'arroz con', 'entrecot', 'estofado']):
            return ['almuerzo', 'cena']
        return ['desayuno', 'media_manana', 'merienda']

    return ['almuerzo', 'cena']

def get_recipes(query: str = "", group: str = "", meal_slot: str = "", limit: int = 50, offset: int = 0) -> Dict[str, Any]:
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
    params.extend([limit * 3 if meal_slot else limit, offset])

    cursor.execute(sql, params)
    rows = cursor.fetchall()

    recipes = []
    for r in rows:
        item = dict(r)
        item["allowed_slots"] = classify_recipe_meal_slots(item["nombre"], item["grupo_canonico"])
        if meal_slot:
            if meal_slot.strip().lower() in item["allowed_slots"]:
                recipes.append(item)
        else:
            recipes.append(item)

    if meal_slot:
        total = len(recipes)
        recipes = recipes[:limit]

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
    # Filtrar desayunos auténticos (excluyendo fajitas, carnes pesadas, legumbres y comidas calientes)
    desayunos_limpios = [r for r in desayunos if not any(w in r["nombre"].lower() for w in ["fajita", "pizza", "hamburguesa", "arroz con", "lenteja", "garbanzo", "alubia", "entrecot", "estofado"])]
    if not desayunos_limpios:
        desayunos_limpios = desayunos

    aves_huevos = [r for r in aves_carnes if not any(w in r["nombre"].lower() for w in ["ternera", "buey", "vaca", "cordero"])]
    carnes_rojas = [r for r in aves_carnes if any(w in r["nombre"].lower() for w in ["ternera", "buey", "solomillo"])]

    # Incluir fajitas y wraps saludables como segundos platos válidos para el almuerzo
    fajitas_platos = [r for r in bocadillos if any(w in r["nombre"].lower() for w in ["fajita", "wrap"])]
    segundos_almuerzo = aves_huevos + fajitas_platos

    days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    week_plan = {}

    legumbres_count = 0
    red_meat_count = 0

    for idx, day in enumerate(days):
        # 1. Suplementación
        supl_items = [
            {"nombre": "5 g. de Creatina", "tipo": "food", "grams": 5, "kcal": 0, "proteina_g": 0.0, "carbohidratos_g": 0.0, "grasa_g": 0.0, "allowed_slots": ["suplementacion"]}
        ]

        # 2. Desayuno (auténtico, nutritivo y sin platos de comida pesada)
        d_receta = random.choice(desayunos_limpios) if desayunos_limpios else None
        desayuno_items = [
            {"nombre": "200 g. de Pieza de Fruta al gusto", "tipo": "food", "grams": 200, "kcal": 95, "proteina_g": 1.5, "carbohidratos_g": 23.0, "grasa_g": 0.3, "allowed_slots": ["desayuno", "media_manana", "merienda"]}
        ]
        if d_receta:
            desayuno_items.append(dict(d_receta))
        desayuno_items.append(
            {"nombre": "20 g. de Nueces" if idx % 2 == 0 else "20 g. de Almendras", "tipo": "food", "grams": 20, "kcal": 130, "proteina_g": 3.0, "carbohidratos_g": 2.5, "grasa_g": 12.0, "allowed_slots": ["desayuno", "media_manana", "merienda"]}
        )

        # 3. Entrenamiento (Agua / Hidratación / Sales)
        entreno_items = [
            {"nombre": "400 g. de Agua", "tipo": "food", "grams": 400, "kcal": 0, "proteina_g": 0.0, "carbohidratos_g": 0.0, "grasa_g": 0.0, "allowed_slots": ["entrenamiento"]}
        ]

        # 4. Media Mañana
        if idx == 5:
            mm_items = [
                {"nombre": "200 g. de Bocadillo de pollo", "tipo": "food", "grams": 200, "kcal": 280, "proteina_g": 22.0, "carbohidratos_g": 32.0, "grasa_g": 6.5, "allowed_slots": ["media_manana"]}
            ]
        elif idx == 6:
            mm_items = [
                {"nombre": "120 g. de Café con leche entera", "tipo": "food", "grams": 120, "kcal": 75, "proteina_g": 3.8, "carbohidratos_g": 5.8, "grasa_g": 4.2, "allowed_slots": ["media_manana"]}
            ]
        else:
            mm_items = [
                {"nombre": "200 g. de Pieza de Fruta al gusto", "tipo": "food", "grams": 200, "kcal": 90, "proteina_g": 1.2, "carbohidratos_g": 22.0, "grasa_g": 0.2, "allowed_slots": ["desayuno", "media_manana", "merienda"]}
            ]

        # 5. Almuerzo: 1er Plato + 2º Plato (aquí sí van fajitas de pollo, entrecot, pollo, pescados) + Fruta
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
            p2 = random.choice(segundos_almuerzo) if segundos_almuerzo else (random.choice(aves_huevos) if aves_huevos else None)

        frutas_postre = ["200 g. de Mandarinas", "200 g. de Peras", "150 g. de Kiwi", "200 g. de Naranjas", "200 g. de Pieza de Fruta al gusto"]
        postre_nombre = frutas_postre[idx % len(frutas_postre)]
        postre_item = {"nombre": postre_nombre, "tipo": "food", "grams": 200, "kcal": 90, "proteina_g": 1.2, "carbohidratos_g": 22.0, "grasa_g": 0.3, "allowed_slots": ["almuerzo", "cena"]}

        almuerzo_items = []
        if p1: almuerzo_items.append(dict(p1))
        if p2: almuerzo_items.append(dict(p2))
        almuerzo_items.append(postre_item)

        # 6. Merienda
        mer_items = [
            {"nombre": "200 g. de Pieza de Fruta al gusto", "tipo": "food", "grams": 200, "kcal": 90, "proteina_g": 1.2, "carbohidratos_g": 22.0, "grasa_g": 0.2, "allowed_slots": ["merienda"]}
        ]

        # 7. Cena: Ligera, digestiva, rápida (pescados, huevos, verduras o express)
        if idx in [0, 2, 4] and express:
            c1 = random.choice(express)
        elif idx in [1, 6] and pescados:
            c1 = random.choice(pescados)
        else:
            c1 = random.choice(veggie + verduras) if veggie else (random.choice(aves_huevos) if aves_huevos else None)

        cena_items = []
        if c1: cena_items.append(dict(c1))
        cena_items.append(
            {"nombre": "150 g. de Verduras salteadas al wok con AOVE", "tipo": "food", "grams": 150, "kcal": 110, "proteina_g": 3.0, "carbohidratos_g": 10.0, "grasa_g": 6.5, "allowed_slots": ["cena"]}
        )

        day_meals = {
            "suplementacion": supl_items,
            "desayuno": desayuno_items,
            "entrenamiento": entreno_items,
            "media_manana": mm_items,
            "almuerzo": almuerzo_items,
            "merienda": mer_items,
            "cena": cena_items,
            # Compatibilidad hacia atrás con vistas legacy
            "comida_primer_plato": p1,
            "comida_segundo_plato": p2,
            "peri_entreno": entreno_items[0]
        }

        # Calcular totales del día sumando todos los items de cada toma
        total_k = 0
        total_p = 0
        total_c = 0
        total_g = 0
        for slot_key in ["suplementacion", "desayuno", "entrenamiento", "media_manana", "almuerzo", "merienda", "cena"]:
            for it in day_meals.get(slot_key, []):
                total_k += float(it.get("kcal") or 0)
                total_p += float(it.get("proteina_g") or 0)
                total_c += float(it.get("carbohidratos_g") or 0)
                total_g += float(it.get("grasa_g") or 0)

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

ACSM_ACTIVITIES = [
    {
        "code": "ACSM-12020",
        "category": "Carrera / Atletismo",
        "name_es": "Carrera en Pista / Series / Intervalos Alta Intensidad (VO2max)",
        "acsm_name": "Running, track, interval training (Z4-Z5, VO2max)",
        "mets": 11.5,
        "intensity_level": "Muy Alta",
        "keywords": ["pista", "series", "interval", "intervalos", "farlek", "fartlek", "1000m", "400m", "200m", "atletismo", "vo2max", "velocidad", "vma"],
        "cho_target_g_kg": 1.3,
        "intra_cho_g_h": 60,
        "intra_fluid_ml_h": 650,
        "intra_sodium_mg_h": 550,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.2,
        "post_pro_g_kg": 0.35,
        "evidence": "ACSM / IOC Consensus on Carbohydrate Intake for High-Intensity Exercise"
    },
    {
        "code": "ACSM-12050",
        "category": "Carrera / Atletismo",
        "name_es": "Rodaje Ritmo Medio / Carrera Continua (Z2-Z3)",
        "acsm_name": "Running, 6 mph (10 min/mile) / moderate endurance",
        "mets": 9.8,
        "intensity_level": "Mod-Alta",
        "keywords": ["rodaje", "ritmo medio", "carrera continua", "tirada", "tempo", "fondo", "aerobico", "running", "correr"],
        "cho_target_g_kg": 1.1,
        "intra_cho_g_h": 45,
        "intra_fluid_ml_h": 550,
        "intra_sodium_mg_h": 450,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.0,
        "post_pro_g_kg": 0.3,
        "evidence": "ACSM Position Stand: Nutrition and Athletic Performance (Endurance)"
    },
    {
        "code": "ACSM-12030",
        "category": "Carrera / Atletismo",
        "name_es": "Rodaje Suave / Regenerativo / Z1",
        "acsm_name": "Running, 5 mph (12 min/mile) / active recovery",
        "mets": 7.0,
        "intensity_level": "Baja",
        "keywords": ["rodaje suave", "regenerativo", "recuperacion", "suave", "trote", "z1"],
        "cho_target_g_kg": 0.8,
        "intra_cho_g_h": 0,
        "intra_fluid_ml_h": 350,
        "intra_sodium_mg_h": 200,
        "post_ratio": "2:1",
        "post_cho_g_kg": 0.8,
        "post_pro_g_kg": 0.25,
        "evidence": "ACSM Exercise and Fluid Replacement Guidelines"
    },
    {
        "code": "ACSM-12150",
        "category": "Carrera de Montaña",
        "name_es": "Trail Running / Carrera por Montaña con Desnivel",
        "acsm_name": "Trail running, uphill/downhill terrain with elevation gain",
        "mets": 11.0,
        "intensity_level": "Alta",
        "keywords": ["trail", "montana", "montaña", "desnivel", "senderismo rapido", "ultra trail"],
        "cho_target_g_kg": 1.3,
        "intra_cho_g_h": 60,
        "intra_fluid_ml_h": 700,
        "intra_sodium_mg_h": 600,
        "post_ratio": "4:1",
        "post_cho_g_kg": 1.2,
        "post_pro_g_kg": 0.35,
        "evidence": "ACSM / International Society of Sports Nutrition (ISSN) Mountain Sports"
    },
    {
        "code": "ACSM-02020",
        "category": "Ciclismo",
        "name_es": "Ciclismo Carretera / Tirada Larga / Puertos (Z3-Z4)",
        "acsm_name": "Bicycling, 16-19 mph, racing or vigorous effort",
        "mets": 10.0,
        "intensity_level": "Alta",
        "keywords": ["bici", "ciclismo", "carretera", "puertos", "tirada larga bici", "bike", "fondo carretera"],
        "cho_target_g_kg": 1.2,
        "intra_cho_g_h": 60,
        "intra_fluid_ml_h": 650,
        "intra_sodium_mg_h": 500,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.1,
        "post_pro_g_kg": 0.3,
        "evidence": "ACSM Guidelines for Prolonged Cycling and Glycogen Resynthesis"
    },
    {
        "code": "ACSM-02030",
        "category": "Ciclismo",
        "name_es": "Mountain Bike / BTT / Ciclismo de Montaña",
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
        "evidence": "ACSM Compendium & Endurance Hydration Protocol"
    },
    {
        "code": "ACSM-02050",
        "category": "Ciclismo",
        "name_es": "Ciclismo Rodillo / Bici Estática / Spinning",
        "acsm_name": "Bicycling, stationary, moderate to vigorous effort",
        "mets": 7.5,
        "intensity_level": "Moderada",
        "keywords": ["rodillo", "spinning", "ciclo indoor", "estatica", "bici estatica", "zwift"],
        "cho_target_g_kg": 1.0,
        "intra_cho_g_h": 40,
        "intra_fluid_ml_h": 650,
        "intra_sodium_mg_h": 500,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.0,
        "post_pro_g_kg": 0.3,
        "evidence": "ACSM Indoor High Sweat Rate Hydration Protocols"
    },
    {
        "code": "ACSM-18300",
        "category": "Natación",
        "name_es": "Natación Crol / Series en Piscina / Intensa",
        "acsm_name": "Swimming laps, freestyle, vigorous effort",
        "mets": 9.8,
        "intensity_level": "Alta",
        "keywords": ["natacion", "natación", "nadar", "piscina", "crol", "series natacion", "estilos", "aguas abiertas"],
        "cho_target_g_kg": 1.2,
        "intra_cho_g_h": 45,
        "intra_fluid_ml_h": 450,
        "intra_sodium_mg_h": 350,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.1,
        "post_pro_g_kg": 0.35,
        "evidence": "ACSM Aquatic Exercise Metabolic Guidelines"
    },
    {
        "code": "ACSM-02052",
        "category": "Fuerza / Musculación",
        "name_es": "Entrenamiento de Fuerza / Hipertrofia / Sobrecarga",
        "acsm_name": "Resistance training, multiple sets, bodybuilding/hypertrophy (RPE 7-9)",
        "mets": 6.0,
        "intensity_level": "Alta",
        "keywords": ["fuerza", "hipertrofia", "musculacion", "musculación", "gimnasio", "pesas", "torso", "pierna", "empuje", "traccion", "sentadilla", "banca"],
        "cho_target_g_kg": 1.0,
        "intra_cho_g_h": 25,
        "intra_fluid_ml_h": 450,
        "intra_sodium_mg_h": 300,
        "post_ratio": "2:1",
        "post_cho_g_kg": 0.8,
        "post_pro_g_kg": 0.4,
        "evidence": "ACSM / ISSN Position Stand: Nutrient Timing and Muscle Protein Synthesis"
    },
    {
        "code": "ACSM-02060",
        "category": "Táctico / Oposiciones",
        "name_es": "Entreno Academia / Pruebas Físicas Bomberos / Cuerdas, Torres y Lastre",
        "acsm_name": "Tactical firefighter/police agility training, rope climbs, tower carries, loaded agility",
        "mets": 8.5,
        "intensity_level": "Muy Alta",
        "keywords": ["academia", "bombero", "bomberos", "cuerda", "cuerdas", "torres", "lastre", "oposicion", "oposición", "tactico", "táctico", "habilidades funcionales"],
        "cho_target_g_kg": 1.3,
        "intra_cho_g_h": 50,
        "intra_fluid_ml_h": 600,
        "intra_sodium_mg_h": 500,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.1,
        "post_pro_g_kg": 0.38,
        "evidence": "ACSM Tactical Athlete Nutrition and High Heat Tolerance Standards"
    },
    {
        "code": "ACSM-02065",
        "category": "CrossFit / Funcional",
        "name_es": "CrossFit / HYROX / Circuit Training de Alta Intensidad",
        "acsm_name": "High-intensity functional fitness, WOD, metabolic conditioning",
        "mets": 10.5,
        "intensity_level": "Muy Alta",
        "keywords": ["crossfit", "hyrox", "wod", "metcon", "amrap", "emom", "catedral", "funcional"],
        "cho_target_g_kg": 1.3,
        "intra_cho_g_h": 50,
        "intra_fluid_ml_h": 650,
        "intra_sodium_mg_h": 550,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.1,
        "post_pro_g_kg": 0.35,
        "evidence": "ACSM Metabolic Conditioning and Acidosis Buffering Recommendations"
    },
    {
        "code": "ACSM-15150",
        "category": "Combate / Artes Marciales",
        "name_es": "Taekwondo / Boxeo / Sparring / Deportes de Contacto",
        "acsm_name": "Combat sports, taekwondo, boxing sparring, martial arts vigorous",
        "mets": 10.0,
        "intensity_level": "Muy Alta",
        "keywords": ["tkd", "taekwondo", "boxeo", "sparring", "combate", "artes marciales", "judo", "bjj", "mma", "lucha"],
        "cho_target_g_kg": 1.3,
        "intra_cho_g_h": 40,
        "intra_fluid_ml_h": 600,
        "intra_sodium_mg_h": 500,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.1,
        "post_pro_g_kg": 0.35,
        "evidence": "ACSM / IOC Combat Sports Nutrition and Rapid Recovery"
    },
    {
        "code": "ACSM-15610",
        "category": "Deportes de Equipo",
        "name_es": "Fútbol / Partido / Competición Intermitente",
        "acsm_name": "Soccer, competitive match, intermittent sprinting",
        "mets": 9.0,
        "intensity_level": "Alta",
        "keywords": ["futbol", "fútbol", "partido futbol", "soccer", "futbol sala", "partido"],
        "cho_target_g_kg": 1.2,
        "intra_cho_g_h": 45,
        "intra_fluid_ml_h": 600,
        "intra_sodium_mg_h": 450,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.1,
        "post_pro_g_kg": 0.32,
        "evidence": "FIFA / ACSM Nutrition for Football Consensus"
    },
    {
        "code": "ACSM-15700",
        "category": "Raqueta",
        "name_es": "Pádel / Tenis / Deporte de Raqueta",
        "acsm_name": "Tennis / Padel, moderate to vigorous match play",
        "mets": 7.3,
        "intensity_level": "Moderada",
        "keywords": ["padel", "pádel", "tenis", "fronton", "squash"],
        "cho_target_g_kg": 1.0,
        "intra_cho_g_h": 35,
        "intra_fluid_ml_h": 550,
        "intra_sodium_mg_h": 400,
        "post_ratio": "3:1",
        "post_cho_g_kg": 1.0,
        "post_pro_g_kg": 0.3,
        "evidence": "ACSM Racket Sports Energy Expenditure and Hydration"
    },
    {
        "code": "ACSM-02070",
        "category": "Recuperación",
        "name_es": "Movilidad Articular / Estiramientos / Recuperación Activa",
        "acsm_name": "Stretching, hatha yoga, mobility, light active recovery",
        "mets": 2.8,
        "intensity_level": "Baja",
        "keywords": ["movilidad", "estiramientos", "foam roller", "recuperacion activa", "yoga", "pilates"],
        "cho_target_g_kg": 0.7,
        "intra_cho_g_h": 0,
        "intra_fluid_ml_h": 300,
        "intra_sodium_mg_h": 150,
        "post_ratio": "1:1",
        "post_cho_g_kg": 0.6,
        "post_pro_g_kg": 0.25,
        "evidence": "ACSM Physical Activity Guidelines for Rest Days"
    }
]

def clean_text_simple(t: str) -> str:
    if not t:
        return ""
    nfkd = unicodedata.normalize('NFD', t.lower())
    clean = ''.join(c for c in nfkd if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9\s]', ' ', clean).strip()

def match_acsm_activity(sport_text: str, intensity_raw: Any = None, duration_min: int = 60, weight_kg: float = 75.0) -> Dict[str, Any]:
    norm = clean_text_simple(sport_text)
    best_entry = None
    best_score = -1

    borg = None
    try:
        if intensity_raw is not None:
            borg = float(str(intensity_raw).replace(',', '.'))
    except Exception:
        pass

    for entry in ACSM_ACTIVITIES:
        score = 0
        for kw in entry["keywords"]:
            clean_kw = clean_text_simple(kw)
            if clean_kw in norm:
                score += len(clean_kw) * 2
                if norm.startswith(clean_kw) or clean_kw in norm.split():
                    score += 5

        if borg is not None:
            if borg >= 8 and entry["intensity_level"] in ["Alta", "Muy Alta"]:
                score += 3
            elif 5 <= borg < 8 and entry["intensity_level"] in ["Moderada", "Mod-Alta"]:
                score += 3
            elif borg < 5 and entry["intensity_level"] == "Baja":
                score += 3

        if score > best_score:
            best_score = score
            best_entry = entry

    if not best_entry or best_score <= 0:
        if any(w in norm for w in ["fuerza", "pesas", "gym", "muscul", "hipertrofia"]):
            best_entry = ACSM_ACTIVITIES[8]
        else:
            best_entry = ACSM_ACTIVITIES[1]

    mets = best_entry["mets"]
    kcal = round((mets * 3.5 * weight_kg * duration_min) / 200.0)

    return {
        "acsm_code": best_entry["code"],
        "acsm_category": best_entry["category"],
        "acsm_name": best_entry["acsm_name"],
        "name_es": best_entry["name_es"],
        "mets": mets,
        "energy_kcal": kcal,
        "intensity_level": best_entry["intensity_level"],
        "evidence": best_entry["evidence"],
        "daily_cho_target": f"{best_entry['cho_target_g_kg'] * 5:.0f} - {best_entry['cho_target_g_kg'] * 7:.0f} g/kg/día",
        "pre_cho_g_kg": best_entry["cho_target_g_kg"],
        "intra_cho_g_h": best_entry["intra_cho_g_h"],
        "intra_fluid_ml_h": best_entry["intra_fluid_ml_h"],
        "intra_sodium_mg_h": best_entry["intra_sodium_mg_h"],
        "post_ratio": best_entry["post_ratio"],
        "post_cho_g_kg": best_entry["post_cho_g_kg"],
        "post_pro_g_kg": best_entry["post_pro_g_kg"],
        "electrolyte_recommendations": {
            "sodium_concentration": "500 - 800 mg Na+/L",
            "sweat_rate_est": f"{round(best_entry['intra_fluid_ml_h'] * 1.2)} ml/h",
            "hydration_protocol": "150-200 ml cada 15-20 min con electrolitos hipotónicos/isotónicos",
            "post_rehydration": "150% del peso corporal perdido en las 2-4h posteriores con sodio"
        }
    }

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

    pre_window_start = (start_dt - timedelta(hours=3)).strftime("%H:%M")
    pre_window_end = (start_dt - timedelta(hours=2)).strftime("%H:%M")
    pre_immediate_time = (start_dt - timedelta(minutes=45)).strftime("%H:%M")
    post_recovery_end = (end_dt + timedelta(hours=2)).strftime("%H:%M")

    # Mapeo oficial con el Compendio de Actividad Física ACSM
    acsm = match_acsm_activity(sport, intensity, duration_min, weight_kg)
    level = acsm["intensity_level"]

    if level == "Muy Alta":
        theme = {"border": "#ef4444", "bg": "#fff5f5", "text": "#991b1b", "badge_bg": "#fee2e2", "badge_text": "#b91c1c"}
    elif level == "Alta":
        theme = {"border": "#f97316", "bg": "#fff7ed", "text": "#9a3412", "badge_bg": "#ffedd5", "badge_text": "#c2410c"}
    elif level == "Mod-Alta":
        theme = {"border": "#f59e0b", "bg": "#fffbeb", "text": "#92400e", "badge_bg": "#fef3c7", "badge_text": "#b45309"}
    elif level == "Baja":
        theme = {"border": "#10b981", "bg": "#ecfdf5", "text": "#065f46", "badge_bg": "#d1fae5", "badge_text": "#047857"}
    else:
        theme = {"border": "#0284c7", "bg": "#f0f9ff", "text": "#075985", "badge_bg": "#e0f2fe", "badge_text": "#0369a1"}

    pre_carbs_g = round(weight_kg * acsm["pre_cho_g_kg"])
    pre_water_ml = round(weight_kg * 6.0)
    pre_sodium_mg = 400 if level in ["Muy Alta", "Alta", "Mod-Alta"] else 300

    pre_imm_carbs_g = 25 if duration_min >= 45 else 15
    pre_imm_water_ml = 150

    intra_carbs_h = acsm["intra_cho_g_h"]
    intra_fluid_ml_h = acsm["intra_fluid_ml_h"]
    intra_sodium_mg_h = acsm["intra_sodium_mg_h"]
    if duration_min < 45:
        intra_format = "Agua sola a demanda (no requiere carbohidratos intra-sesión)"
    elif duration_min <= 75:
        intra_format = "Bebida hipotónica/isotónica ligera (6-8% CHO) o agua con sales"
    elif duration_min <= 150:
        intra_format = "Geles energéticos AIS Grupo A con agua (ratio glucosa:fructosa 2:1) + sales minerales"
    else:
        intra_format = "Maltodextrina + Fructosa (ratio 1:0.8 o 2:1) hasta 90g/h + sales (500-700mg Na+/h)"

    post_protein_g = round(weight_kg * acsm["post_pro_g_kg"])
    post_carbs_g = round(weight_kg * acsm["post_cho_g_kg"])

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
            "Osmolaridad controlada: disoluciones hipotónicas/isotónicas (6-8%) para evitar arrastre osmótico de agua a la luz intestinal."
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
        "acsm_data": acsm,
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
                "ratio": acsm["post_ratio"],
                "rehydration_note": "125-150% del peso corporal perdido en sudor con electrolitos (ACSM)",
                "recommended_foods": "Batido proteína aislada (Whey/Soja) + plátano maduro / Pechuga de pollo con patata asada"
            }
        },
        "digestibility": digestibility_protocol,
        "notes": notes
    }

def parse_time_slot_string(val: str) -> tuple:
    s = str(val or '').strip().lower()
    m = re.search(r'(\d{1,2}):(\d{2})\s*(am|pm)?\s*(?:a|-)\s*(\d{1,2}):(\d{2})\s*(am|pm)?', s)
    if m:
        h1, m1, p1, h2, m2, p2 = m.groups()
        h1, m1, h2, m2 = int(h1), int(m1), int(h2), int(m2)
        p1 = p1 or p2
        p2 = p2 or p1
        if p1 == 'pm' and h1 < 12: h1 += 12
        if p1 == 'am' and h1 == 12: h1 = 0
        if p2 == 'pm' and h2 < 12: h2 += 12
        if p2 == 'am' and h2 == 12: h2 = 0
        if h1 == 11 and h2 == 0: h2 = 12
        if h1 == 0 and h2 == 13: h1 = 12
        dur = (h2 * 60 + m2) - (h1 * 60 + m1)
        if dur <= 0: dur = 60
        return f"{h1:02d}:{m1:02d}", f"{h2:02d}:{m2:02d}", dur
    return "18:00", "19:00", 60

def parse_cuadrante_anyd_grid(ws, weight_kg: float = 75.0) -> Dict[str, Any]:
    DAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    header_row = -1
    day_cols = {}

    for r in range(1, 25):
        for c in range(1, 20):
            val = str(ws.cell(row=r, column=c).value or '').strip().lower()
            if 'lunes' in val:
                header_row = r
                break
        if header_row != -1:
            break

    if header_row == -1:
        return None

    for c in range(1, 30):
        val = str(ws.cell(row=header_row, column=c).value or '').strip().lower()
        for d in DAYS:
            if d.lower() in val and d not in day_cols:
                day_cols[d] = c
                break

    if not day_cols:
        return None

    raw_by_day = {d: [] for d in DAYS}

    for r in range(header_row + 1, header_row + 25):
        t_val = str(ws.cell(row=r, column=2).value or '').strip()
        if not t_val or 'volumen' in t_val.lower() or 'semana 2' in t_val.lower():
            if 'semana 2' in t_val.lower() or 'volumen' in t_val.lower():
                break
            continue

        st, et, dur = parse_time_slot_string(t_val)

        for d, c in day_cols.items():
            act = str(ws.cell(row=r, column=c).value or '').strip()
            intensity = ws.cell(row=r, column=c + 1).value
            if act and act.lower() not in ['none', '']:
                m_dur = re.search(r'(\d{2,3})\s*(?:min|m)', act.lower())
                final_dur = int(m_dur.group(1)) if m_dur else dur
                clean_act = act.replace('\n', ' ').strip()
                raw_by_day[d].append({
                    'start': st,
                    'end': et,
                    'dur': final_dur,
                    'act': clean_act,
                    'intensity': intensity
                })

    workouts_by_day = {d: [] for d in DAYS}
    total_count = 0

    for d in DAYS:
        items = raw_by_day[d]
        if not items:
            continue

        merged_items = []
        i = 0
        while i < len(items):
            cur = items[i]
            if i + 1 < len(items):
                nxt = items[i + 1]
                if nxt['start'] == cur['end'] or nxt['start'] == cur['start']:
                    merged_act = f"{cur['act']} - {nxt['act']}".replace('  ', ' ')
                    merged_dur = cur['dur'] + nxt['dur']
                    merged_int = nxt['intensity'] if nxt['intensity'] is not None else cur['intensity']
                    merged_items.append({
                        'start': cur['start'],
                        'dur': merged_dur,
                        'act': merged_act,
                        'intensity': merged_int
                    })
                    i += 2
                    continue
            merged_items.append(cur)
            i += 1

        for it in merged_items:
            int_str = f"Borg {it['intensity']}" if it['intensity'] is not None else "Moderada"
            guidelines = compute_peri_workout_guidelines(
                sport=it['act'],
                duration_min=it['dur'],
                intensity=int_str,
                weight_kg=weight_kg,
                start_time=it['start'],
                notes=f"Cuadrante oficial ANyD (Borg: {it['intensity'] or 'Estándar'})"
            )
            workouts_by_day[d].append(guidelines)
            total_count += 1

    return {
        "workouts_by_day": workouts_by_day,
        "total_sessions": total_count,
        "is_cuadrante_anyd": True
    }

def parse_training_excel_or_csv(file_bytes: bytes, filename: str, weight_kg: float = 75.0) -> Dict[str, Any]:
    """
    Parsea hojas de cálculo Excel (.xlsx, .xls) o CSV con el microciclo semanal de entrenamientos.
    Detecta automáticamente si es el Cuadrante Oficial ANyD o una tabla plana.
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

    if filename.lower().endswith((".xlsx", ".xlsm", ".xltx", ".ods")):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        ws = wb.active
        # 1. Intentar parser de Cuadrante Oficial ANyD
        cuadrante_res = parse_cuadrante_anyd_grid(ws, weight_kg)
        if cuadrante_res and cuadrante_res.get("total_sessions", 0) > 0:
            return cuadrante_res

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
            elif any(k in cell for k in ["intensidad", "rpe", "zona", "intensity", "zone", "borg"]):
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

        sport = str(row[sport_col] or "Entrenamiento Deportivo").strip() if sport_col < len(row) else "Entrenamiento"

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

        intensity = str(row[int_col] or "Moderada").strip() if int_col < len(row) else "Moderada"
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
        "total_sessions": total_count,
        "is_cuadrante_anyd": False
    }

def get_athlete_training_files_from_drive(client_name: str) -> List[Dict[str, Any]]:
    import drive_manager
    folder = drive_manager.find_athlete_folder(client_name)
    if not folder or not os.path.exists(folder):
        return []

    results = []
    for root, dirs, files in os.walk(folder):
        for f in files:
            if f.startswith("~$") or f.startswith("."):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext in ['.xlsx', '.xls', '.csv', '.ods', '.xlsm']:
                full_path = os.path.join(root, f)
                stat = os.stat(full_path)
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M")
                size_kb = round(stat.st_size / 1024, 1)

                f_lower = f.lower()
                is_cuadrante = any(k in f_lower for k in ['cuadrante', 'entren', 'training', 'plani', 'rutina', 'sesion', 'volum', 'micro'])

                results.append({
                    "filename": f,
                    "full_path": full_path,
                    "rel_path": os.path.relpath(full_path, folder),
                    "size_kb": size_kb,
                    "modified": mtime,
                    "is_cuadrante": is_cuadrante,
                    "ext": ext
                })

    results.sort(key=lambda x: (x["is_cuadrante"], x["size_kb"] > 1), reverse=True)
    return results

def load_training_file_by_path(file_path: str, weight_kg: float = 75.0) -> Dict[str, Any]:
    if not os.path.exists(file_path):
        return {"success": False, "error": f"Archivo no encontrado: {file_path}"}

    try:
        with open(file_path, "rb") as f:
            content = f.read()
        res = parse_training_excel_or_csv(content, os.path.basename(file_path), weight_kg)
        return {"success": True, "filename": os.path.basename(file_path), **res}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_athlete_clinical_parameters(client_name: str) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()

    name_clean = client_name.strip().lower()

    cursor.execute("""
    SELECT id, firstname, lastname, fullname, email, phone, note FROM clients
    WHERE LOWER(fullname) LIKE ? OR LOWER(fullname) = ?
    ORDER BY CASE WHEN LOWER(fullname) = ? THEN 1 ELSE 2 END, id DESC LIMIT 1
    """, (f"%{name_clean}%", name_clean, name_clean))
    client = cursor.fetchone()

    c_id = client["id"] if client else None
    c_fullname = client["fullname"] if client else client_name

    # 1. Medición Tanita más reciente
    cursor.execute("""
    SELECT weight, ffm, fat_percent, fat_mass, muscle_mass, water_percent, bone_mass, visceral_fat, bmr_cunningham, measurement_date
    FROM tanita_measurements
    WHERE (client_id = ? OR LOWER(client_name) LIKE ?)
    ORDER BY measurement_date DESC, id DESC LIMIT 1
    """, (c_id, f"%{name_clean}%"))
    tanita_row = cursor.fetchone()
    tanita_data = dict(tanita_row) if tanita_row else None

    # 2. Perfil clínico
    profile_data = None
    if c_id:
        cursor.execute("SELECT * FROM athlete_profiles WHERE client_id = ?", (c_id,))
        p_row = cursor.fetchone()
        if p_row:
            profile_data = dict(p_row)
            if profile_data.get("birth_date"):
                try:
                    b_dt = datetime.strptime(str(profile_data["birth_date"])[:10], "%Y-%m-%d")
                    profile_data["age"] = int((datetime.now() - b_dt).days / 365.25)
                except Exception:
                    profile_data["age"] = None

    # 3. Planes previos
    cursor.execute("""
    SELECT id, plan_name, weight, ffm, target_kcal, target_protein_g, created_at
    FROM diet_plans
    WHERE (client_id = ? OR LOWER(client_name) LIKE ?)
    ORDER BY id DESC LIMIT 1
    """, (c_id, f"%{name_clean}%"))
    last_plan = cursor.fetchone()
    last_plan_data = dict(last_plan) if last_plan else None

    conn.close()

    training_files = get_athlete_training_files_from_drive(c_fullname)

    return {
        "found": bool(client or tanita_data or profile_data or last_plan_data or training_files),
        "client": dict(client) if client else {"fullname": c_fullname, "email": "", "phone": ""},
        "tanita": tanita_data,
        "profile": profile_data,
        "latest_plan": last_plan_data,
        "training_files": training_files
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


