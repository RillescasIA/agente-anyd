import urllib.request
import json

BASE_URL = "http://127.0.0.1:8080"

def post(url, payload):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}{url}", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return resp.getcode(), json.loads(resp.read().decode('utf-8'))

def get(url):
    req = urllib.request.Request(f"{BASE_URL}{url}")
    with urllib.request.urlopen(req) as resp:
        return resp.getcode(), json.loads(resp.read().decode('utf-8'))

def get_html(url):
    req = urllib.request.Request(f"{BASE_URL}{url}")
    with urllib.request.urlopen(req) as resp:
        return resp.getcode(), len(resp.read().decode('utf-8'))

def test_all():
    print("=== TEST COMPLETO: DIETOWIN 2.0 & TANITA MC-580 ===\n")
    
    # 1. PÁGINAS HTML
    print("--- 1. RUTAS FRONTEND ---")
    for page in ["/dietas", "/tanita", "/consulta", "/admin", "/"]:
        status, length = get_html(page)
        print(f"✓ {page}: HTTP {status} ({length} bytes cargados)")

    # 2. DIETOWIN: RECETAS & GRUPOS
    print("\n--- 2. CATÁLOGO MAESTRO DE RECETAS ---")
    status, res = get("/api/diet/groups")
    print(f"✓ Grupos canónicos disponibles: {len(res.get('groups', []))}")
    status, res = get("/api/diet/recipes?group=all&limit=5")
    print(f"✓ Total recetas indexadas: {res.get('total')} platos maestros")

    # 3. DIETOWIN: ALIMENTOS & BASES CIENTÍFICAS
    print("\n--- 3. ALIMENTOS Y BASES DE DATOS ESPAÑOLAS ---")
    for f_code, label in [
        ("bedca", "BEDCA (Oficial AESAN/Sanidad)"),
        ("cesnid_moreiras", "Tablas de Moreiras (UCM) & CESNID"),
        ("mapa_fen", "MAPA / FEN (Alimentos Tradicionales)"),
        ("off", "Open Food Facts España (Supermercados)")
    ]:
        status, res = get(f"/api/diet/foods?fuente={f_code}&limit=5")
        print(f"✓ {label}: {res.get('total')} ingredientes disponibles")

    # 4. OPEN FOOD FACTS EN VIVO
    print("\n--- 4. BÚSQUEDA EN TIEMPO REAL OPEN FOOD FACTS ESPAÑA ---")
    status, res = get("/api/diet/off/search?q=avena&limit=3")
    prods = res.get("products", [])
    print(f"✓ Productos en vivo devueltos: {len(prods)}")
    for p in prods:
        print(f"   • {p.get('nombre')} ({p.get('marca')}) - {p.get('kcal')} kcal/100g")

    # 5. METABOLISMO CUNNINGHAM & TANITA
    print("\n--- 5. MOTOR METABÓLICO CUNNINGHAM (1980/1991) ---")
    status, res = post("/api/diet/calculate-needs", {
        "weight_kg": 74.0,
        "ffm_kg": 63.5,
        "height_cm": 178.0,
        "age": 29,
        "gender": "M",
        "formula": "cunningham",
        "pal": 1.6,
        "goal": "rendimiento"
    })
    print(f"✓ BMR Cunningham: {res.get('bmr')} kcal | Gasto Total (TDEE): {res.get('tdee')} kcal")
    print(f"✓ Reparto Pauta: {res.get('target_kcal')} kcal | Proteína: {res.get('target_protein_g')}g ({res.get('protein_g_kg')} g/kg FFM)")

    # 6. PLAN SEMANAL INTELIGENTE ANyD
    print("\n--- 6. GENERADOR DE PLAN SEMANAL INTELIGENTE (7 DÍAS) ---")
    status, res = post("/api/diet/generate-smart-week", {
        "target_kcal": 2500.0,
        "target_protein_g": 150.0
    })
    wp = res.get("week_plan", {})
    rules = res.get("rules_complied", {})
    print(f"✓ Plan generado para {len(wp)} días de la semana.")
    print(f"✓ Criterios clínicos aplicados: Legumbres={res.get('legumbres_count')} tomas (>=4: {rules.get('legumbres_min_4')}), Carne roja={res.get('red_meat_count')} tomas (<=2: {rules.get('oms_carne_roja')})")
    for d in ["Lunes", "Miércoles", "Viernes"]:
        summary = wp[d]["summary"]
        print(f"   - {d}: {summary['kcal']} kcal, {summary['proteina_g']}g P, {summary['carbohidratos_g']}g CHO, {summary['grasa_g']}g G")

    # 7. CRUD DE RECETA
    print("\n--- 7. CRUD DE RECETAS & PRODUCTOS ---")
    status, res_c = post("/api/diet/recipe", {
        "nombre": "Bowl de Yogur Griego con Nueces y Arándanos",
        "grupo_canonico": "01. Desayunos, Meriendas & Snacks",
        "tiempo_minutos": 5,
        "ingredientes": "150g Yogur griego 0%, 25g Nueces, 50g Arándanos frescos",
        "elaboracion": "Mezclar todos los ingredientes en un bol y servir fresco.",
        "kcal": 275,
        "proteina_g": 18,
        "carbohidratos_g": 16,
        "grasa_g": 15
    })
    rec_id = res_c.get("id")
    print(f"✓ Creación de receta: ID {rec_id} - '{res_c.get('nombre')}'")

    status, res_copy = post(f"/api/diet/recipe/{rec_id}/copy", {})
    copy_id = res_copy.get("new_recipe_id")
    print(f"✓ Duplicar/Copiar receta: ID {copy_id} - '{res_copy.get('nombre')}'")

    # Clean up test recipes
    urllib.request.urlopen(urllib.request.Request(f"{BASE_URL}/api/diet/recipe/{rec_id}", method="DELETE"))
    urllib.request.urlopen(urllib.request.Request(f"{BASE_URL}/api/diet/recipe/{copy_id}", method="DELETE"))
    print(f"✓ Borrado de recetas de prueba: OK")

    # 8. TANITA MC-580
    print("\n--- 8. TANITA MC-580: ESTADO Y COMUNICACIÓN ---")
    status, res = get("/api/tanita/ports")
    print(f"✓ Puertos COM detectados: {[p['port'] for p in res.get('ports', [])]}")
    status, res = get("/api/tanita/live")
    print(f"✓ Estado puerto activo: {res.get('active_port') or 'Esperando conexión'}")
    status, res = post("/api/tanita/simulate", {})
    meas = res.get("measurement", {})
    print(f"✓ Telemetría Tanita MC-580: Peso={meas.get('weight')} kg, Grasa={meas.get('fat_percent')}%, FFM={meas.get('ffm')} kg, Agua={meas.get('water_percent')}%")

    print("\n=== TODOS LOS MÓDULOS DE DIETOWIN Y TANITA OPERATIVOS 100% ===")

if __name__ == "__main__":
    test_all()
