import csv
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "anyd_booking.db"))
DATA_DIR = os.path.join(BASE_DIR, "data")
RECETAS_CSV = os.path.join(DATA_DIR, "Dietowin_Recetas_Platos_Maestro.csv") if os.path.exists(os.path.join(DATA_DIR, "Dietowin_Recetas_Platos_Maestro.csv")) else r"G:\Mi unidad\1.- ANyD\Dietowin_Recetas_Platos_Maestro.csv"
ALIMENTOS_CSV = os.path.join(DATA_DIR, "Dietowin_Alimentos_Maestro_Consolidado.csv") if os.path.exists(os.path.join(DATA_DIR, "Dietowin_Alimentos_Maestro_Consolidado.csv")) else r"G:\Mi unidad\1.- ANyD\Dietowin_Alimentos_Maestro_Consolidado.csv"

def parse_float(val, default=0.0):
    if not val:
        return default
    try:
        s = str(val).replace(",", ".").strip()
        return float(s)
    except:
        return default

def import_dietowin_to_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Crear tablas si no existen
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS diet_foods (
        id INTEGER PRIMARY KEY,
        nombre TEXT NOT NULL,
        familia TEXT,
        kcal REAL DEFAULT 0,
        proteina_g REAL DEFAULT 0,
        carbohidratos_g REAL DEFAULT 0,
        grasa_g REAL DEFAULT 0,
        fibra_g REAL DEFAULT 0,
        grasa_sat_g REAL DEFAULT 0
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
        grasa_g REAL DEFAULT 0
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

    # 2. Importar Alimentos (971)
    foods_count = 0
    if os.path.exists(ALIMENTOS_CSV):
        cursor.execute("DELETE FROM diet_foods")
        with open(ALIMENTOS_CSV, mode="r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f, delimiter=";")
            for r in reader:
                fid = int(parse_float(r.get("id_ingrediente") or r.get("\ufeffid_ingrediente") or 0))
                name = (r.get("nombre") or "").strip().strip('"')
                familia = (r.get("grupo_bedca") or r.get("familia_bromatologica") or "General").strip().strip('"')
                if not name:
                    continue
                kcal = parse_float(r.get("energia_kcal"))
                prot = parse_float(r.get("proteina_g"))
                carbs = parse_float(r.get("carbohidratos_g"))
                grasa = parse_float(r.get("grasa_total_g"))
                fibra = parse_float(r.get("fibra_g"))
                grasa_sat = parse_float(r.get("grasa_sat_g"))

                cursor.execute("""
                INSERT OR REPLACE INTO diet_foods (id, nombre, familia, kcal, proteina_g, carbohidratos_g, grasa_g, fibra_g, grasa_sat_g)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (fid, name, familia, kcal, prot, carbs, grasa, fibra, grasa_sat))
                foods_count += 1

    # 3. Importar Recetas Maestras (1.340)
    recipes_count = 0
    if os.path.exists(RECETAS_CSV):
        cursor.execute("DELETE FROM diet_recipes")
        with open(RECETAS_CSV, mode="r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f, delimiter=";")
            for r in reader:
                rid = int(parse_float(r.get("id_receta") or r.get("\ufeffid_receta") or 0))
                nombre = (r.get("nombre_receta") or "").strip().strip('"')
                grupo = (r.get("grupo_canonico") or "General").strip().strip('"')
                tiempo = int(parse_float(r.get("tiempo_minutos"), 10))
                ingredientes = (r.get("ingredientes_desglose") or "").strip().strip('"')
                elaboracion = (r.get("elaboracion_concisa") or "").strip().strip('"')
                if not nombre:
                    continue
                kcal = parse_float(r.get("kcal"))
                prot = parse_float(r.get("proteina_g"))
                carbs = parse_float(r.get("carbohidratos_g"))
                grasa = parse_float(r.get("grasas_g"))

                cursor.execute("""
                INSERT OR REPLACE INTO diet_recipes (id, nombre, grupo_canonico, tiempo_minutos, ingredientes, elaboracion, kcal, proteina_g, carbohidratos_g, grasa_g)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (rid, nombre, grupo, tiempo, ingredientes, elaboracion, kcal, prot, carbs, grasa))
                recipes_count += 1

    conn.commit()
    conn.close()
    print(f"Importación completada con éxito: {foods_count} alimentos y {recipes_count} recetas importadas a SQLite.")
    return {"foods": foods_count, "recipes": recipes_count}

if __name__ == "__main__":
    import_dietowin_to_db()
