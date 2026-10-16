import sqlite3
import re
import os
import csv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "anyd_booking.db"))
CSV_LOCAL = os.path.join(BASE_DIR, "data", "Dietowin_Recetas_Platos_Maestro.csv")
CSV_GDRIVE = r"G:\Mi unidad\1.- ANyD\Dietowin_Recetas_Platos_Maestro.csv"

# 1. Lista de actividades deportivas / entrenamientos que NO son alimentos
EXCLUDED_ACTIVITIES = [
    "taekwondo", "boxeo", "carrera", "andar", "crossfit", "pesas",
    "natación", "ciclismo", "halterofilia", "karate", "hyrox",
    "conditioning", "bicicleta estática", "entrenamiento", "pista"
]

def is_sport_activity(name: str, ingredients: str) -> bool:
    name_l = name.lower()
    ing_l = (ingredients or "").lower()

    # Si es fruta como "mandarinas", NO es actividad
    if "mandarina" in name_l:
        return False
    if "arroz basmati" in name_l:
        return False

    for act in EXCLUDED_ACTIVITIES:
        pattern = r"\b" + re.escape(act) + r"\b"
        if re.search(pattern, name_l):
            return True
        if re.search(pattern, ing_l) and not any(f in name_l for f in ["arroz", "pollo", "pescado", "ensalada", "manzana"]):
            return True
    return False

def extract_portion_grams(name: str, ingredients: str, default_grams: float = 150.0) -> float:
    # Buscar en el nombre primero: "80 g. de Tostadas", "150 g de Yogur", etc.
    m = re.search(r"(\d+)\s*g(?:\.|\b)", name, re.IGNORECASE)
    if m:
        try:
            val = float(m.group(1))
            if 5 <= val <= 1000:
                return val
        except:
            pass

    # Buscar en los ingredientes
    if ingredients:
        m2 = re.search(r"(\d+)\s*g(?:\.|\b)", ingredients, re.IGNORECASE)
        if m2:
            try:
                val = float(m2.group(1))
                if 5 <= val <= 1000:
                    return val
            except:
                pass

    return default_grams

def calculate_recipe_nutrients(name: str, group: str, ingredients: str):
    """
    Calcula de forma precisa Kcal, Proteínas (g), Carbohidratos (g) y Grasas (g)
    según la composición real de los alimentos (BEDCA / USDA / CESNID).
    """
    n = name.lower()
    ing = (ingredients or "").lower()
    full_text = f"{n} {ing}"

    # Suplementación específica
    if "creatina" in n:
        return 0.0, 0.0, 0.0, 0.0
    if "whey" in n or "proteína" in n and "polvo" in full_text:
        g = extract_portion_grams(name, ingredients, 30.0)
        # 30g de whey = ~114 kcal, 24g P, 1.5g C, 1g G
        ratio = g / 30.0
        return round(114.0 * ratio, 1), round(24.0 * ratio, 1), round(1.5 * ratio, 1), round(1.0 * ratio, 1)

    # 1. FRUTAS FRESCAS
    if any(k in n for k in ["plátano", "platano"]):
        g = extract_portion_grams(name, ingredients, 150.0)
        # Plátano: 89 kcal/100g, 1.1 P, 21.0 C, 0.2 G
        r = g / 100.0
        return round(89.0 * r, 1), round(1.1 * r, 1), round(21.0 * r, 1), round(0.2 * r, 1)

    if any(k in n for k in ["frutos rojos", "arándano", "arandano", "mora", "frambuesa", "fresa"]):
        g = extract_portion_grams(name, ingredients, 150.0)
        # Frutos rojos: 45 kcal/100g, 0.9 P, 8.5 C, 0.4 G
        r = g / 100.0
        return round(45.0 * r, 1), round(0.9 * r, 1), round(8.5 * r, 1), round(0.4 * r, 1)

    if any(k in n for k in ["manzana", "pera"]):
        g = extract_portion_grams(name, ingredients, 180.0)
        # Manzana/Pera: 52 kcal/100g, 0.4 P, 12.5 C, 0.2 G
        r = g / 100.0
        return round(52.0 * r, 1), round(0.4 * r, 1), round(12.5 * r, 1), round(0.2 * r, 1)

    if any(k in n for k in ["naranja", "mandarina"]):
        g = extract_portion_grams(name, ingredients, 160.0)
        r = g / 100.0
        return round(44.0 * r, 1), round(0.8 * r, 1), round(9.5 * r, 1), round(0.2 * r, 1)

    if any(k in n for k in ["kiwi", "piña", "pina", "melocotón", "melocoton", "sandía", "sandia", "melón", "melon", "fruta al gusto", "pieza de fruta", "macedonia"]):
        g = extract_portion_grams(name, ingredients, 180.0)
        r = g / 100.0
        return round(50.0 * r, 1), round(0.8 * r, 1), round(11.0 * r, 1), round(0.2 * r, 1)

    # 2. CAFÉ Y LÁCTEOS
    if "café" in n or "cafe" in n:
        g = extract_portion_grams(name, ingredients, 200.0)
        if any(k in n for k in ["con leche entera", "leche entera"]):
            r = g / 100.0
            # Café con leche entera: ~55 kcal/100g, 3.1 P, 4.7 C, 2.8 G
            return round(55.0 * r, 1), round(3.1 * r, 1), round(4.7 * r, 1), round(2.8 * r, 1)
        elif any(k in n for k in ["con leche", "cortado"]):
            r = g / 100.0
            return round(40.0 * r, 1), round(2.5 * r, 1), round(4.0 * r, 1), round(1.5 * r, 1)
        else:
            return 2.0, 0.2, 0.3, 0.0

    if "yogur" in n or "yogurt" in n:
        g = extract_portion_grams(name, ingredients, 125.0)
        r = g / 100.0
        if "nueces" in n or "frutos secos" in n:
            # 125g yogur + 20g nueces = ~160 kcal/100g de mezcla
            return round(155.0 * r, 1), round(5.5 * r, 1), round(6.5 * r, 1), round(12.5 * r, 1)
        elif "kiwi" in n or "fruta" in n:
            return round(72.0 * r, 1), round(3.8 * r, 1), round(11.5 * r, 1), round(1.6 * r, 1)
        elif "chocolate" in n:
            return round(105.0 * r, 1), round(4.0 * r, 1), round(16.0 * r, 1), round(3.0 * r, 1)
        elif "griego" in n:
            return round(115.0 * r, 1), round(7.0 * r, 1), round(4.5 * r, 1), round(7.5 * r, 1)
        elif "desnatado" in n or "0%" in n:
            return round(42.0 * r, 1), round(4.5 * r, 1), round(5.0 * r, 1), round(0.2 * r, 1)
        else:
            # Yogur natural estándar
            return round(61.0 * r, 1), round(3.5 * r, 1), round(4.7 * r, 1), round(3.3 * r, 1)

    if "leche" in n:
        g = extract_portion_grams(name, ingredients, 250.0)
        r = g / 100.0
        if "avena" in n:
            # Leche con copos de avena (ej. 200ml leche + 40g avena)
            return round(105.0 * r, 1), round(4.8 * r, 1), round(15.5 * r, 1), round(2.8 * r, 1)
        elif "desnatada" in n:
            return round(36.0 * r, 1), round(3.4 * r, 1), round(4.8 * r, 1), round(0.2 * r, 1)
        else:
            return round(63.0 * r, 1), round(3.2 * r, 1), round(4.7 * r, 1), round(3.6 * r, 1)

    # 3. PANES, TOSTADAS Y DESAYUNOS
    if "tostada" in n or "tostadas" in n:
        g = extract_portion_grams(name, ingredients, 60.0)
        r = g / 100.0
        if "aceite" in n or "tomate" in n:
            # Tostadas int con tomate y aceite: ~320 kcal/100g, 7.8 P, 44 C, 12.5 G
            return round(320.0 * r, 1), round(7.8 * r, 1), round(44.0 * r, 1), round(12.5 * r, 1)
        elif "mermelada" in n or "miel" in n:
            return round(280.0 * r, 1), round(6.5 * r, 1), round(58.0 * r, 1), round(2.0 * r, 1)
        elif "pavo" in n or "jamón" in n or "jamon" in n:
            return round(260.0 * r, 1), round(16.0 * r, 1), round(36.0 * r, 1), round(5.5 * r, 1)
        else:
            return round(260.0 * r, 1), round(8.5 * r, 1), round(48.0 * r, 1), round(3.0 * r, 1)

    if "pan integral" in n or "rebanada" in n:
        g = extract_portion_grams(name, ingredients, 40.0)
        r = g / 100.0
        if "aceite" in n:
            # 40g pan + 10g AOVE
            return round(340.0 * r, 1), round(7.0 * r, 1), round(38.0 * r, 1), round(17.0 * r, 1)
        else:
            return round(245.0 * r, 1), round(9.0 * r, 1), round(46.0 * r, 1), round(2.2 * r, 1)

    if "bocadillo" in n or "sandwich" in n or "fajita" in n:
        g = extract_portion_grams(name, ingredients, 160.0)
        r = g / 100.0
        # Bocadillos completos con proteína y vegetales
        return round(220.0 * r, 1), round(12.0 * r, 1), round(28.0 * r, 1), round(6.5 * r, 1)

    if "avena" in n or "porridge" in n:
        g = extract_portion_grams(name, ingredients, 180.0)
        r = g / 100.0
        return round(110.0 * r, 1), round(5.0 * r, 1), round(17.5 * r, 1), round(2.4 * r, 1)

    if "frutos secos" in n or "nueces" in n or "almendra" in n:
        g = extract_portion_grams(name, ingredients, 30.0)
        r = g / 100.0
        return round(610.0 * r, 1), round(16.0 * r, 1), round(11.0 * r, 1), round(56.0 * r, 1)

    # 4. LEGUMBRES (Cocidas / Servidas)
    if any(k in n for k in ["garbanzo", "lenteja", "alubia", "judía blanca", "edamame"]):
        g = extract_portion_grams(name, ingredients, 250.0)
        r = g / 100.0
        if "garbanzo" in n:
            # Garbanzos cocidos: 125 kcal/100g, 7.5 P, 18.5 C, 2.6 G
            return round(125.0 * r, 1), round(7.5 * r, 1), round(18.5 * r, 1), round(2.6 * r, 1)
        elif "lenteja" in n:
            # Lentejas cocidas: 110 kcal/100g, 8.5 P, 17.5 C, 1.0 G
            return round(110.0 * r, 1), round(8.5 * r, 1), round(17.5 * r, 1), round(1.0 * r, 1)
        elif "alubia" in n:
            return round(115.0 * r, 1), round(8.0 * r, 1), round(17.5 * r, 1), round(1.0 * r, 1)
        elif "edamame" in n:
            return round(122.0 * r, 1), round(11.5 * r, 1), round(8.5 * r, 1), round(5.0 * r, 1)

    # 5. ARROCES, PASTAS Y PATATAS
    if "arroz" in n or "risotto" in n or "paella" in n:
        g = extract_portion_grams(name, ingredients, 220.0)
        r = g / 100.0
        if "pollo" in n or "pescado" in n or "marisco" in n:
            return round(160.0 * r, 1), round(7.5 * r, 1), round(25.0 * r, 1), round(3.5 * r, 1)
        else:
            return round(130.0 * r, 1), round(2.7 * r, 1), round(28.0 * r, 1), round(0.5 * r, 1)

    if "pasta" in n or "macarrón" in n or "macarron" in n or "espagueti" in n or "fideos" in n:
        g = extract_portion_grams(name, ingredients, 220.0)
        r = g / 100.0
        if "boloñesa" in n or "bolonesa" in n or "carne" in n:
            return round(170.0 * r, 1), round(9.0 * r, 1), round(24.5 * r, 1), round(4.2 * r, 1)
        elif "atún" in n or "atun" in n:
            return round(155.0 * r, 1), round(8.5 * r, 1), round(24.0 * r, 1), round(2.8 * r, 1)
        else:
            return round(140.0 * r, 1), round(5.0 * r, 1), round(28.0 * r, 1), round(1.0 * r, 1)

    if "patata" in n or "patatas" in n or "pure" in n or "puré" in n:
        g = extract_portion_grams(name, ingredients, 180.0)
        r = g / 100.0
        if "horno" in n or "asada" in n or "asadas" in n:
            return round(120.0 * r, 1), round(2.2 * r, 1), round(20.0 * r, 1), round(3.8 * r, 1)
        elif "frita" in n or "fritas" in n:
            return round(280.0 * r, 1), round(3.5 * r, 1), round(35.0 * r, 1), round(14.0 * r, 1)
        else:
            # Patata cocida / puré
            return round(85.0 * r, 1), round(2.0 * r, 1), round(18.0 * r, 1), round(0.5 * r, 1)

    # 6. PESCADOS Y MARISCOS
    if any(k in n for k in ["merluza", "bacalao", "lubina", "dorada", "lenguado", "pescadilla"]):
        g = extract_portion_grams(name, ingredients, 180.0)
        r = g / 100.0
        # Pescado blanco: 85 kcal/100g, 17.5 P, 0 C, 1.5 G
        return round(85.0 * r, 1), round(17.5 * r, 1), 0.0, round(1.5 * r, 1)

    if any(k in n for k in ["salmón", "salmon", "atún", "atun", "sardina", "caballa", "emperador", "bonito"]):
        g = extract_portion_grams(name, ingredients, 160.0)
        r = g / 100.0
        # Pescado azul: 175 kcal/100g, 20.5 P, 0 C, 10.5 G
        return round(175.0 * r, 1), round(20.5 * r, 1), 0.0, round(10.5 * r, 1)

    if any(k in n for k in ["sepia", "calamar", "pulpo", "gamba", "gambón", "gambon", "langostino", "mejillón", "mejillon"]):
        g = extract_portion_grams(name, ingredients, 180.0)
        r = g / 100.0
        return round(85.0 * r, 1), round(16.5 * r, 1), round(1.0 * r, 1), round(1.2 * r, 1)

    # 7. AVES, CARNES Y HUEVOS
    if any(k in n for k in ["pollo", "pavo"]):
        g = extract_portion_grams(name, ingredients, 180.0)
        r = g / 100.0
        return round(125.0 * r, 1), round(26.0 * r, 1), 0.0, round(2.2 * r, 1)

    if any(k in n for k in ["ternera", "buey", "solomillo"]):
        g = extract_portion_grams(name, ingredients, 180.0)
        r = g / 100.0
        return round(145.0 * r, 1), round(22.0 * r, 1), 0.0, round(6.0 * r, 1)

    if any(k in n for k in ["cerdo", "lomo"]):
        g = extract_portion_grams(name, ingredients, 160.0)
        r = g / 100.0
        return round(155.0 * r, 1), round(23.0 * r, 1), 0.0, round(6.8 * r, 1)

    if "tortilla" in n:
        g = extract_portion_grams(name, ingredients, 180.0)
        r = g / 100.0
        if "patata" in n:
            return round(165.0 * r, 1), round(6.0 * r, 1), round(14.0 * r, 1), round(9.5 * r, 1)
        elif "francesa" in n:
            return round(150.0 * r, 1), round(11.0 * r, 1), round(0.5 * r, 1), round(11.5 * r, 1)
        else:
            return round(155.0 * r, 1), round(8.0 * r, 1), round(6.0 * r, 1), round(11.0 * r, 1)

    if "huevo" in n or "huevos" in n:
        g = extract_portion_grams(name, ingredients, 120.0)
        r = g / 100.0
        return round(145.0 * r, 1), round(12.5 * r, 1), round(0.6 * r, 1), round(10.5 * r, 1)

    # 8. VERDURAS, ENSALADAS Y CREMAS
    if any(k in n for k in ["ensalada", "lechuga", "cogollo", "tomate"]):
        g = extract_portion_grams(name, ingredients, 250.0)
        r = g / 100.0
        # Ensalada con aliño moderado
        return round(60.0 * r, 1), round(1.2 * r, 1), round(4.0 * r, 1), round(4.5 * r, 1)

    if any(k in n for k in ["crema", "puré", "pure", "sopa", "caldo"]):
        g = extract_portion_grams(name, ingredients, 280.0)
        r = g / 100.0
        return round(50.0 * r, 1), round(1.8 * r, 1), round(6.5 * r, 1), round(2.0 * r, 1)

    if any(k in n for k in ["brócoli", "brocoli", "judías verdes", "judias verdes", "espinaca", "acelga", "calabacín", "calabacin", "champiñón", "champinon", "verdura"]):
        g = extract_portion_grams(name, ingredients, 250.0)
        r = g / 100.0
        return round(45.0 * r, 1), round(2.5 * r, 1), round(5.0 * r, 1), round(1.5 * r, 1)

    # 9. FALLBACK POR GRUPO CANÓNICO (Con raciones reales y diferenciadas)
    g = extract_portion_grams(name, ingredients, 150.0)
    r = g / 100.0

    if "01." in group:
        return round(160.0 * r, 1), round(5.0 * r, 1), round(25.0 * r, 1), round(4.5 * r, 1)
    elif "02." in group:
        return round(220.0 * r, 1), round(11.0 * r, 1), round(28.0 * r, 1), round(6.5 * r, 1)
    elif "03." in group:
        return round(45.0 * r, 1), round(1.8 * r, 1), round(6.0 * r, 1), round(1.5 * r, 1)
    elif "04." in group:
        return round(55.0 * r, 1), round(2.0 * r, 1), round(5.5 * r, 1), round(3.0 * r, 1)
    elif "05." in group:
        return round(130.0 * r, 1), round(5.5 * r, 1), round(22.0 * r, 1), round(2.0 * r, 1)
    elif "06." in group:
        return round(110.0 * r, 1), round(18.0 * r, 1), 0.0, round(4.0 * r, 1)
    elif "07." in group:
        return round(140.0 * r, 1), round(22.0 * r, 1), 0.0, round(5.5 * r, 1)
    elif "09." in group:
        return round(120.0 * r, 1), round(15.0 * r, 1), round(10.0 * r, 1), round(2.0 * r, 1)
    else:
        return round(120.0 * r, 1), round(7.0 * r, 1), round(15.0 * r, 1), round(3.5 * r, 1)

def run_recalibration():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, nombre, grupo_canonico, tiempo_minutos, ingredientes, elaboracion FROM diet_recipes")
    rows = cursor.fetchall()
    print(f"Iniciando calibración sobre {len(rows)} recetas...")

    cleaned_recipes = []
    deleted_sports_count = 0

    for r in rows:
        rid, nombre, grupo, tiempo, ing, elab = r

        # Comprobar si es un entrenamiento / actividad
        if is_sport_activity(nombre, ing):
            cursor.execute("DELETE FROM diet_recipes WHERE id = ?", (rid,))
            deleted_sports_count += 1
            continue

        kcal, prot, carbs, fat = calculate_recipe_nutrients(nombre, grupo, ing)

        # Actualizar en BD
        cursor.execute("""
        UPDATE diet_recipes
        SET kcal = ?, proteina_g = ?, carbohidratos_g = ?, grasa_g = ?
        WHERE id = ?
        """, (kcal, prot, carbs, fat, rid))

        cleaned_recipes.append({
            "id_receta": rid,
            "nombre_receta": nombre,
            "grupo_canonico": grupo,
            "tiempo_minutos": tiempo,
            "ingredientes_desglose": ing,
            "elaboracion_concisa": elab,
            "kcal": kcal,
            "proteina_g": prot,
            "carbohidratos_g": carbs,
            "grasas_g": fat
        })

    conn.commit()
    conn.close()

    print(f"Recalibración completada:")
    print(f" - {deleted_sports_count} actividades deportivas eliminadas del catálogo de platos.")
    print(f" - {len(cleaned_recipes)} recetas maestras actualizadas con macros y calorías reales.")

    # Guardar en CSV local y en Google Drive si existe
    fieldnames = ["id_receta", "nombre_receta", "grupo_canonico", "tiempo_minutos", "ingredientes_desglose", "elaboracion_concisa", "kcal", "proteina_g", "carbohidratos_g", "grasas_g"]

    def write_csv(path):
        if not path: return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode="w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            for row in cleaned_recipes:
                writer.writerow(row)
        print(f"CSV guardado con éxito en: {path}")

    write_csv(CSV_LOCAL)
    if os.path.exists(os.path.dirname(CSV_GDRIVE)):
        try:
            write_csv(CSV_GDRIVE)
        except Exception as e:
            print(f"No se pudo escribir en Google Drive: {e}")

if __name__ == "__main__":
    run_recalibration()
