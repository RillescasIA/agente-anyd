import sqlite3
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import drive_manager

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "anyd_booking.db"))

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_today_agenda() -> str:
    conn = get_db()
    cursor = conn.cursor()
    today_str = datetime.now().strftime("%Y-%m-%d")
    tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    cursor.execute("""
    SELECT id, client_name, client_email, client_phone, appointment_time, duration_minutes, modality, status, notes
    FROM appointments
    WHERE appointment_date = ? AND status != 'Cancelada'
    ORDER BY appointment_time ASC
    """, (today_str,))
    today_rows = cursor.fetchall()

    cursor.execute("""
    SELECT id, client_name, appointment_time, duration_minutes, modality, status
    FROM appointments
    WHERE appointment_date = ? AND status != 'Cancelada'
    ORDER BY appointment_time ASC
    """, (tomorrow_str,))
    tomorrow_rows = cursor.fetchall()
    conn.close()

    lines = [f"### 📋 Agenda de Hoy ({datetime.now().strftime('%d/%m/%Y')}):"]
    if not today_rows:
        lines.append("• *No hay consultas programadas para el día de hoy.*")
    else:
        for r in today_rows:
            dur = r["duration_minutes"] or 30
            st_color = "🟢" if r["status"] == "Completada" else "🔵"
            lines.append(f"• **{r['appointment_time']}** ({dur} min) — **{r['client_name']}** [{r['modality']}] {st_color} *{r['status']}*")
            if r["notes"]:
                lines.append(f"  └ 📝 *{r['notes']}*")

    lines.append(f"\n### 📅 Citas Mañana ({(datetime.now() + timedelta(days=1)).strftime('%d/%m/%Y')}):")
    if not tomorrow_rows:
        lines.append("• *Sin citas agendadas para mañana.*")
    else:
        for r in tomorrow_rows:
            dur = r["duration_minutes"] or 30
            lines.append(f"• **{r['appointment_time']}** ({dur} min) — **{r['client_name']}** [{r['modality']}]")

    return "\n".join(lines)

def get_bono_alerts() -> str:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, order_id, client_name, client_email, tipo_bono, total_sessions, used_sessions
    FROM bonos
    WHERE status = 'Activo' AND (total_sessions - used_sessions) <= 1
    ORDER BY (total_sessions - used_sessions) ASC, id DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return "✅ **Todo al día**: No hay bonos activos en riesgo o con solo 1 sesión pendiente."

    lines = [f"### ⚠️ Alertas de Bonos por Agotar ({len(rows)} deportistas):"]
    for r in rows:
        rem = r["total_sessions"] - r["used_sessions"]
        warning_icon = "🔴" if rem == 0 else "🟠"
        lines.append(f"• {warning_icon} **{r['client_name']}** — {r['tipo_bono']} (Pedido #{r['order_id']})")
        lines.append(f"  └ Saldo: **{r['used_sessions']}/{r['total_sessions']}** consumidas (**{rem} restantes**). Email: {r['client_email'] or 'N/A'}")

    return "\n".join(lines)

def get_latest_tanita_summary() -> str:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, client_name, measurement_date, weight, fat_percent, ffm, muscle_mass, visceral_fat, bmr_cunningham, created_at
    FROM tanita_measurements
    ORDER BY id DESC LIMIT 5
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return "ℹ️ *No se han registrado mediciones en la báscula Tanita MC-580 todavía.*"

    lines = ["### ⚖️ Últimos Pesajes en Tanita MC-580:"]
    for r in rows:
        date_display = r["measurement_date"] or str(r["created_at"])[:10]
        cunningham = r["bmr_cunningham"] or "--"
        lines.append(f"• **{r['client_name']}** ({date_display}):")
        lines.append(f"  └ Peso: **{r['weight']} kg** | % Grasa: **{r['fat_percent']}%** | FFM: **{r['ffm']} kg** | BMR Cunningham: **{cunningham} kcal**")

    return "\n".join(lines)

def calculate_cunningham_tdee(weight: float, fat_percent: float) -> str:
    fat_mass = round(weight * (fat_percent / 100.0), 2)
    ffm = round(weight - fat_mass, 2)
    bmr = round(500 + 22 * ffm)

    tdee_rest = round(bmr * 1.25)
    tdee_mod = round(bmr * 1.40)
    tdee_intense = round(bmr * 1.60)

    # Raciones recomendadas ANyD
    carbs_rest = round(ffm * 2.5)
    carbs_mod = round(ffm * 4.0)
    carbs_intense = round(ffm * 6.0)

    return f"""### 📊 Cálculo Fisiológico Cunningham (ANyD Nutricionistas)
• **Peso:** {weight} kg | **Grasa:** {fat_percent}%
• **Masa Grasa:** {fat_mass} kg | **Masa Libre de Grasa (FFM):** **{ffm} kg**
• **Gasto Metabólico Basal (BMR Cunningham):** **{bmr} kcal/día**
  $$\\text{{BMR}} = 500 + 22 \\times {ffm} = {bmr}\\text{{ kcal}}$$

#### ⚡ Periodización Energética Total (TDEE Conservador):
1. **Día de Descanso / Regeneración (PAL 1.25):** **~{tdee_rest} kcal** (CHO ~{carbs_rest}g)
2. **Día Entrenamiento Moderado (PAL 1.40):** **~{tdee_mod} kcal** (CHO ~{carbs_mod}g)
3. **Día Entrenamiento Intenso / Partido (PAL 1.60):** **~{tdee_intense} kcal** (CHO ~{carbs_intense}g)

*Regla de Oro ANyD:* Proteína magra ~1.8-2.0 g/kg FFM (~{round(ffm * 1.9)}g PRO/día). Aceite de oliva virgen extra medido estrictamente por cucharas (5g / 10g).
"""

def search_client_dossier(query: str) -> str:
    clean_q = query.strip().lower()
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, fullname, email, phone, note FROM clients
    WHERE LOWER(fullname) LIKE ? OR LOWER(email) LIKE ? OR phone LIKE ?
    LIMIT 3
    """, (f"%{clean_q}%", f"%{clean_q}%", f"%{clean_q}%"))
    clients = cursor.fetchall()

    if not clients:
        conn.close()
        return f"🔍 No se encontró ningún deportista con el término *«{query}»*."

    output = []
    for c in clients:
        c_name = c["fullname"]
        c_id = c["id"]

        # Bonos
        cursor.execute("SELECT tipo_bono, total_sessions, used_sessions, status FROM bonos WHERE client_id = ? OR LOWER(client_name) LIKE ?", (c_id, f"%{c_name.lower()}%"))
        bonos = cursor.fetchall()

        # Citas
        cursor.execute("SELECT appointment_date, appointment_time, modality, status FROM appointments WHERE client_id = ? OR LOWER(client_name) LIKE ? ORDER BY appointment_date DESC LIMIT 3", (c_id, f"%{c_name.lower()}%"))
        appts = cursor.fetchall()

        # Tanita
        cursor.execute("SELECT weight, fat_percent, ffm, bmr_cunningham, measurement_date FROM tanita_measurements WHERE client_id = ? OR LOWER(client_name) LIKE ? ORDER BY id DESC LIMIT 1", (c_id, f"%{c_name.lower()}%"))
        tanita = cursor.fetchone()

        drive_info = drive_manager.get_athlete_folder_info(c_name)
        drive_status = f"✅ Carpeta en Drive activa ({drive_info['files_count']} archivos)" if drive_info["exists"] else "📁 Sin carpeta en Drive (se crea en 1 clic)"

        card = [f"### 👤 {c_name}"]
        card.append(f"• **Email:** {c['email'] or 'N/A'} | **Tel:** {c['phone'] or 'N/A'}")
        card.append(f"• **Google Drive:** {drive_status}")

        if bonos:
            for b in bonos:
                rem = b["total_sessions"] - b["used_sessions"]
                card.append(f"• 🎟️ **Bono:** {b['tipo_bono']} — {b['used_sessions']}/{b['total_sessions']} consumidas (**{rem} restantes**, {b['status']})")
        else:
            card.append("• 🎟️ *Sin bonos registrados.*")

        if tanita:
            card.append(f"• ⚖️ **Último pesaje ({tanita['measurement_date']}):** {tanita['weight']}kg | {tanita['fat_percent']}% Grasa | FFM {tanita['ffm']}kg | Cunningham: **{tanita['bmr_cunningham']} kcal**")

        if appts:
            card.append("• 📅 **Citas recientes:**")
            for a in appts:
                card.append(f"  └ {a['appointment_date']} {a['appointment_time']} [{a['modality']}] — *{a['status']}*")

        output.append("\n".join(card))

    conn.close()
    return "\n\n---\n\n".join(output)

def get_clinical_guidelines_response() -> str:
    return """### 🥗 Criterios Clínicos & Nutricionales ANyD Nutricionistas
*(Román Illescas Quiroga · Col. MAD00274)*

1. **Carne Roja (Criterio OMS/IARC):**
   - Máximo **1 a 2 tomas semanales** (<500g cocida semanal).
   - Cortes magros (ternera magra, solomillo, lomo desgrasado).
   - **Tolerancia CERO** a embutidos grasos, salchichas o procesados con nitritos (carcinógenos Grupo 1).

2. **Legumbres Obligatorias:**
   - Mínimo **4 tomas a la semana** (garbanzos, lentejas, alubias, edamame).
   - Aporte clave de almidón resistente, fibra soluble prebiótica, hierro no hemo, potasio y magnesio.

3. **Cereales 100% Integrales y Excepción Peri-Entreno:**
   - Base diaria: grano entero (pan 100% integral, avena, arroz integral, quinoa).
   - Excepción: en ventana pre/post entreno inmediato se autorizan refinados (arroz blanco, patata cocida) para vaciamiento gástrico rápido sin residuo digestivo.

4. **Consistencia de Hidratos (Regla ±10g ANyD):**
   - Cereales secos: **70 g** en crudo (rango 60-80g).
   - Legumbres cocidas / Patata: **250 g** en crudo o cocido (rango 240-260g).
   - Pan integral: **60 g** (rango 50-70g).

5. **Grasas Saludables:**
   - Grasa principal: Aceite de Oliva Virgen Extra (AOVE). Medición estricta por cuchara:
     * Cuchara postre = 5g (45 kcal)
     * Cuchara sopera = 10-12g (90-100 kcal)
"""

import html as html_lib

def markdown_to_html(md: str) -> str:
    # 1. Blindaje Anti-XSS: Escapar etiquetas HTML maliciosas de inicio (<script>, <iframe>, <img>)
    safe_text = html_lib.escape(md)
    safe_text = re.sub(r'#### (.*)', r'<div style="font-weight:700; color:#0369a1; margin-top:6px; margin-bottom:2px; font-size:12px;">\1</div>', safe_text)
    safe_text = re.sub(r'### (.*)', r'<div style="font-weight:700; color:#0284C7; margin-top:8px; margin-bottom:4px; font-size:13px;">\1</div>', safe_text)
    safe_text = re.sub(r'## (.*)', r'<div style="font-weight:700; color:#1E293B; margin-top:10px; margin-bottom:6px; font-size:14px;">\1</div>', safe_text)
    safe_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', safe_text)
    safe_text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', safe_text)
    safe_text = re.sub(r'`(.*?)`', r'<code style="background:#f1f5f9; padding:2px 4px; border-radius:4px; font-size:11px; color:#0f172a;">\1</code>', safe_text)
    safe_text = safe_text.replace('---', '<hr style="border:none; border-top:1px solid #E2E8F0; margin:8px 0;">')
    
    lines = safe_text.split('\n')
    formatted_lines = []
    for line in lines:
        line_s = line.strip()
        if line_s.startswith('&gt; ') or line_s.startswith('> '):
            clean_gt = line_s.split(' ', 1)[1] if ' ' in line_s else ''
            formatted_lines.append(f'<div style="background:#f8fafc; border-left:3px solid #0284c7; padding:4px 8px; margin:4px 0; font-size:11px; color:#475569;">{clean_gt}</div>')
        elif line_s.startswith('• ') or line_s.startswith('- '):
            formatted_lines.append(f'<div style="margin-left:8px; margin-bottom:3px;">• {line_s[2:]}</div>')
        elif re.match(r'^\d+\.\s', line_s):
            formatted_lines.append(f'<div style="margin-left:8px; margin-bottom:3px;">{line_s}</div>')
        elif line_s.startswith('└ '):
            formatted_lines.append(f'<div style="margin-left:20px; font-size:12px; color:#64748B;">└ {line_s[2:]}</div>')
        else:
            formatted_lines.append(line)
    return '<br>'.join([l for l in formatted_lines if l != ''])

def process_copilot_query(prompt: str, active_athlete_name: Optional[str] = None) -> Dict[str, Any]:
    text = prompt.strip().lower()

    # Comprobación de Habilidades Clínicas Especializadas ANyD
    try:
        import clinical_skills
        if any(k in text for k in ["ferritina", "analitica", "analítica", "sangre", "hierro", "vitamina d", "cpk", "transaminasas", "reds", "biomarcador"]):
            c_res = clinical_skills.analyze_blood_biomarkers(prompt, active_athlete_name)
            if c_res.get("success"):
                reply_text = c_res["reply_markdown"]
                return {"success": True, "reply": reply_text, "response": reply_text, "reply_html": markdown_to_html(reply_text), "type": "blood_biomarkers", "data": c_res}

        if any(k in text for k in ["sudor", "sudoracion", "sudoración", "sweat", "tasa sudor", "tasa de sudor"]):
            c_res = clinical_skills.calculate_sweat_rate_hydration(prompt, active_athlete_name)
            if c_res.get("success"):
                reply_text = c_res["reply_markdown"]
                return {"success": True, "reply": reply_text, "response": reply_text, "reply_html": markdown_to_html(reply_text), "type": "sweat_rate", "data": c_res}

        if any(k in text for k in ["wearable", "strava", "garmin", "trainingpeaks", "tss", "kilojulio", "kj"]):
            c_res = clinical_skills.sync_wearable_tss(prompt, active_athlete_name)
            if c_res.get("success"):
                reply_text = c_res["reply_markdown"]
                return {"success": True, "reply": reply_text, "response": reply_text, "reply_html": markdown_to_html(reply_text), "type": "wearable_sync", "data": c_res}

        if any(k in text for k in ["mercadona", "lidl", "supermercado", "nova", "ultraprocesado", "comprar", "open food facts"]):
            c_res = clinical_skills.audit_supermarket_product(prompt)
            if c_res.get("success"):
                reply_text = c_res["reply_markdown"]
                return {"success": True, "reply": reply_text, "response": reply_text, "reply_html": markdown_to_html(reply_text), "type": "supermarket_audit", "data": c_res}

        if any(k in text for k in ["whatsapp", "mensaje al paciente", "recordatorio tanita", "mensaje tanita", "mensaje seguimiento", "mensaje pauta", "mensaje dossier"]):
            c_res = clinical_skills.generate_whatsapp_patient_message(prompt, active_athlete_name)
            if c_res.get("success"):
                reply_text = c_res["reply_markdown"]
                return {"success": True, "reply": reply_text, "response": reply_text, "reply_html": markdown_to_html(reply_text), "type": "whatsapp_message", "data": c_res}
    except Exception as e:
        print(f"[COPILOT ERROR] Error en clinical_skills: {e}")

    # 0. Comprobar si es una consulta sobre gasto energético, deporte, METs o pautas ISSN / suplementación
    sport_keywords = [
        "coste", "gasto", "caloria", "caloría", "kcal", "mets", "actividad", "ejercicio",
        "pilates", "reformer", "cadillac", "yoga", "fuerza", "pesas", "crossfit", "carrera",
        "correr", "running", "bici", "ciclismo", "spinning", "futbol", "fútbol", "natacion",
        "nadar", "padel", "pádel", "boxeo", "taekwondo", "judo", "bjj", "mma", "bombero",
        "policia", "proteina", "proteína", "issn", "leucina", "creatina", "cafeina", "cafeína",
        "beta alanina", "hidratos", "peri-entreno", "pre-entreno", "post-entreno", "intra-entreno",
        "sodio", "electrolitos"
    ]
    if any(k in text for k in sport_keywords):
        try:
            import sports_assistant
            res = sports_assistant.process_assistant_query(prompt, active_athlete_name)
            if res.get("success"):
                reply_text = res["reply_markdown"]
                return {
                    "success": True,
                    "reply": reply_text,
                    "response": reply_text,
                    "reply_html": markdown_to_html(reply_text),
                    "type": res.get("type", "sports_assistant"),
                    "data": res
                }
        except Exception as e:
            print(f"[COPILOT ERROR] Error en sports_assistant: {e}")

    if any(k in text for k in ["agenda", "hoy", "manana", "mañana", "citas de hoy", "horario"]):
        content = get_today_agenda()
        return {"success": True, "reply": content, "response": content, "reply_html": markdown_to_html(content), "type": "agenda"}

    if any(k in text for k in ["bono", "alertas", "agotar", "quedan", "saldo"]):
        content = get_bono_alerts()
        return {"success": True, "reply": content, "response": content, "reply_html": markdown_to_html(content), "type": "bonos"}

    if any(k in text for k in ["tanita", "pesaje", "bascula", "báscula", "peso", "bioimpedancia"]):
        content = get_latest_tanita_summary()
        return {"success": True, "reply": content, "response": content, "reply_html": markdown_to_html(content), "type": "tanita"}

    if any(k in text for k in ["norma", "criterio", "pauta", "guia", "directriz", "carne roja", "legumbres"]):
        content = get_clinical_guidelines_response()
        return {"success": True, "reply": content, "response": content, "reply_html": markdown_to_html(content), "type": "guidelines"}

    # Comprobar si pide cálculo Cunningham con números (ej: "calcula 75 kg y 14%")
    num_matches = re.findall(r'(\d+[\.,]?\d*)', text)
    if "cunningham" in text or "tdee" in text or ("calcula" in text and len(num_matches) >= 2):
        try:
            val1 = float(num_matches[0].replace(',', '.'))
            val2 = float(num_matches[1].replace(',', '.'))
            weight = max(val1, val2)
            fat_pct = min(val1, val2)
            content = calculate_cunningham_tdee(weight, fat_pct)
            return {"success": True, "reply": content, "response": content, "reply_html": markdown_to_html(content), "type": "calculator"}
        except:
            pass

    # Si menciona buscar a un deportista
    words_to_strip = ["busca", "buscar", "deportista", "paciente", "quien", "quién", "dime", "info", "sobre"]
    search_q = text
    for w in words_to_strip:
        search_q = search_q.replace(w, "").strip()

    if len(search_q) >= 3:
        client_res = search_client_dossier(search_q)
        if "No se encontró" not in client_res:
            return {"success": True, "reply": client_res, "response": client_res, "reply_html": markdown_to_html(client_res), "type": "client"}

    # Respuesta general inteligente
    agenda = get_today_agenda()
    alerts = get_bono_alerts()
    fallback_response = f"""👋 ¡Hola Román! Soy el **Copiloto Clínico y de Gestión de ANyD Nutricionistas**.

{agenda}

---

{alerts}

---
💡 **¿Qué deseas consultar?**
• Escribe el **nombre de cualquier deportista** para ver su expediente, bono, citas y pesajes Tanita.
• Escribe *"Calcula 74 kg y 13%"* para obtener el gasto Cunningham y periodización TDEE.
• O consulta pautas clínicas ANyD sobre legumbres, carne roja o hidratos peri-entreno.
"""
    return {"success": True, "reply": fallback_response, "response": fallback_response, "reply_html": markdown_to_html(fallback_response), "type": "general"}
