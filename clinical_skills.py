# -*- coding: utf-8 -*-
"""
Módulo de Habilidades Clínicas Especializadas ANyD Nutricionistas (Román Illescas, Col. MAD00274).
Implementa los 5 motores clínicos requeridos:
1. blood_biomarkers: Analizador de biomarcadores sanguíneos (ferritina, IST, vit D, CPK, transaminasas, REDs).
2. wearable_sports_sync: Sincronizador y modulador de TSS/kJ (Garmin/Strava/TrainingPeaks a CH g/kg FFM).
3. open_food_facts_spain: Auditor de productos y supermercados (NOVA 1-3, grasas sat <7-8%, recetas 10-15 min).
4. sweat_rate_hydration: Calculadora de tasa de sudoración (L/h), sodio (500-700 mg) y reposición 150%.
5. whatsapp_patient_assistant: Generador de mensajes clínicos de WhatsApp (Tanita 24h, Entrega Dossier, D+7).
"""

import re
from typing import Dict, Any, Optional

def analyze_blood_biomarkers(prompt: str, athlete_name: Optional[str] = None) -> Dict[str, Any]:
    text = prompt.lower()
    name_str = f" para **{athlete_name}**" if athlete_name else ""
    
    # Extraer valores numéricos si los hay
    ferritin_match = re.search(r'ferritina\s*[:=]?\s*(\d+[\.,]?\d*)', text)
    vitd_match = re.search(r'vitamina\s*d\s*[:=]?\s*(\d+[\.,]?\d*)', text)
    cpk_match = re.search(r'cpk\s*[:=]?\s*(\d+[\.,]?\d*)', text)
    ist_match = re.search(r'ist\s*[:=]?\s*(\d+[\.,]?\d*)', text)
    
    lines = [f"### 🩸 Informe de Biomarcadores Sanguíneos Deportivos{name_str}"]
    lines.append("*(Criterios Clínicos ANyD · Consensos SEEN / AIS / IOC)*\n")
    
    if ferritin_match:
        val = float(ferritin_match.group(1).replace(',', '.'))
        if val < 20:
            lines.append(f"• 🔴 **Ferritina: {val} ng/mL — FERROPENIA SEVERA (Estadio 2-3)**")
            lines.append("  └ *Acción inmediata:* Derivación médica para suplementación con hierro bisglicinato (Grupo A AIS) en días alternos en ayunas junto a 200mg Vit C. Separar ≥2h de lácteos, café o té. Comprobar IST y hemoglobina.")
        elif val < 35:
            lines.append(f"• 🟠 **Ferritina: {val} ng/mL — ALERTA FERROPENIA SUBCLÍNICA (Estadio 1)**")
            lines.append("  └ *Acción:* Riesgo de caída en VO2max y fatiga crónica. Aumentar legumbres combinadas con cítricos, moluscos (almejas/mejillones) y valorar suplementación oral profiláctica.")
        else:
            lines.append(f"• 🟢 **Ferritina: {val} ng/mL — Nivel óptimo en deportista (>35 ng/mL)**")
    else:
        lines.append("• 📌 **Metabolismo del Hierro (Ferritina + IST):**")
        lines.append("  └ *Ferritina óptima:* >35 ng/mL (>50 ng/mL en deportes de impacto/resistencia). Si <30 ng/mL y Hemoglobina normal = *Pseudoanemia del deportista o depleción de depósitos*. IST diana: >20-25%.")

    if vitd_match:
        val = float(vitd_match.group(1).replace(',', '.'))
        if val < 30:
            lines.append(f"• 🔴 **Vitamina D (25-OH): {val} ng/mL — INSUFICIENCIA (<30 ng/mL)**")
            lines.append("  └ *Impacto:* Disminución de síntesis proteica muscular, mayor riesgo de fracturas por estrés y bajada inmune. Pauta: Vit D3 2.000-4.000 UI/día con comida grasa + exposición solar.")
        elif val < 40:
            lines.append(f"• 🟡 **Vitamina D (25-OH): {val} ng/mL — Rango aceptable pero subóptimo para alto rendimiento (Deseable >40 ng/mL)**")
        else:
            lines.append(f"• 🟢 **Vitamina D (25-OH): {val} ng/mL — Nivel óptimo deportivo (40-60 ng/mL)**")
    else:
        lines.append("• ☀️ **Vitamina D (25-OH-D):** Nivel objetivo en deportistas ANyD: **40 - 50 ng/mL**. Si <30 ng/mL, pautar colecalciferol.")

    if cpk_match:
        val = float(cpk_match.group(1).replace(',', '.'))
        if val > 1000:
            lines.append(f"• 🔴 **CPK (Creatina Quinasa): {val} U/L — ALERTA DAÑO MUSCULAR SEVERO / SOBREENTRENAMIENTO**")
            lines.append("  └ *Acción:* Descanso activo inmediato, hidratación con suero isotónico (150% de pérdidas) y monitorización renal (orina oscura / mioglobina).")
        elif val > 400:
            lines.append(f"• 🟠 **CPK (Creatina Quinasa): {val} U/L — Daño muscular post-ejercicio elevado**")
            lines.append("  └ *Acción:* Optimizar ventana post-entreno (0.3g PRO/kg + 0.8g CHO/kg) y sueño.")
        else:
            lines.append(f"• 🟢 **CPK: {val} U/L — Daño muscular bajo control (<350 U/L)**")
    else:
        lines.append("• ⚡ **Marcadores de Daño & Adaptación (CPK y AST/ALT):**")
        lines.append("  └ CPK basal normal: <250 U/L. Tras carreras o fuerza intensa puede llegar a 400-600 U/L transitoriamente. Comprobar que transaminasas altas no son de origen hepático sino muscular.")

    lines.append("\n#### 🚨 Protocolo de Prevención REDs (Deficiencia Energética Relativa):")
    lines.append("Si coexisten ferritina <30 ng/mL + amenorrea/oligomenorrea o testosterona baja + bajada de rendimiento, asegurar disponibilidad energética mínima de **≥45 kcal / kg FFM / día**.")
    
    md_reply = "\n".join(lines)
    return {
        "success": True,
        "type": "blood_biomarkers",
        "reply": md_reply,
        "reply_markdown": md_reply
    }

def calculate_sweat_rate_hydration(prompt: str, athlete_name: Optional[str] = None) -> Dict[str, Any]:
    text = prompt.lower()
    name_str = f" para **{athlete_name}**" if athlete_name else ""
    
    # Intentar extraer pesos y tiempo
    numbers = [float(x.replace(',', '.')) for x in re.findall(r'(\d+[\.,]?\d*)', text)]
    
    # Heurística: si hay al menos 2 números > 30 son pesos pre y post
    pre_w = None
    post_w = None
    duration_h = 1.0
    fluid_l = 0.5
    
    weights = [n for n in numbers if 35.0 <= n <= 160.0]
    if len(weights) >= 2:
        pre_w = max(weights[0], weights[1])
        post_w = min(weights[0], weights[1])
    
    durations = [n for n in numbers if 0.25 <= n <= 8.0 and n not in weights]
    if durations:
        duration_h = durations[0]

    lines = [f"### 💧 Calculadora Científica de Tasa de Sudoración e Hidratación{name_str}"]
    lines.append("*(Consensos ACSM / AIS Grupo A · Ecuación de Balance Hídrico)*\n")
    
    if pre_w and post_w:
        weight_diff_kg = round(pre_w - post_w, 2)
        pct_dehydration = round((weight_diff_kg / pre_w) * 100, 1)
        sweat_rate_lh = round((weight_diff_kg + fluid_l) / duration_h, 2)
        rehydration_vol_l = round(weight_diff_kg * 1.5, 2)
        target_sodium_mg = round(sweat_rate_lh * 600)
        
        lines.append(f"• **Peso Pre-Entreno:** {pre_w} kg | **Peso Post-Entreno:** {post_w} kg")
        lines.append(f"• **Pérdida de Masa Corporal:** **{weight_diff_kg} kg** ({pct_dehydration}% de deshidratación)")
        lines.append(f"• **Duración:** {duration_h} h | **Líquido ingerido estimado:** {fluid_l} L")
        lines.append(f"\n#### ⚡ Resultados de Hidratación:")
        lines.append(f"1. **Tasa de Sudoración:** **{sweat_rate_lh} L / hora**")
        lines.append(f"2. **Reposición Intra-Entreno Recomendada:** **{round(sweat_rate_lh * 0.75 * 1000)} - {round(sweat_rate_lh * 1000)} mL/h**")
        lines.append(f"3. **Sodio Intra-Entreno:** **500 - 700 mg Na+ / hora** (o ~{target_sodium_mg} mg/h en este deportista)")
        lines.append(f"4. **Regla de Reposición Post-Entreno (150% de las pérdidas):**")
        lines.append(f"   └ Ingerir **{rehydration_vol_l} L** de líquido en las siguientes 2-4 horas junto a alimentos con sodio o caldo para retener el agua sin inducir diuresis.")
        
        if pct_dehydration > 2.0:
            lines.append("\n⚠️ **Alerta Clínica:** Deshidratación superior al 2% del peso corporal. Se compromete la función cognitiva, el gasto cardíaco y la termorregulación.")
    else:
        lines.append("#### 📐 Ecuación Estándar:")
        lines.append("$$\\text{Tasa Sudor (L/h)} = \\frac{(\\text{Peso Pre (kg)} - \\text{Peso Post (kg)}) + \\text{Líquido (L)} - \\text{Orina (L)}}{\\text{Tiempo (horas)}}$$")
        lines.append("\n#### 🎯 Pautas Prácticas ANyD:")
        lines.append("• **Pre-Entreno (2-3h antes):** 5-7 mL/kg de agua + 1 pizca de sal marina.")
        lines.append("• **Intra-Entreno (>60 min):** 400-800 mL/h con **500-700 mg de Sodio/L** (isotónico con 6-8% de hidratos).")
        lines.append("• **Post-Entreno:** Ingerir el **150% del peso perdido** en las siguientes 2-4 horas.")
        lines.append("\n*Tip:* Puedes escribir por ejemplo: *«Calcula sudor con peso pre 74.2 kg, post 72.8 kg y 1.5 horas»*")
        
    md_reply = "\n".join(lines)
    return {
        "success": True,
        "type": "sweat_rate",
        "reply": md_reply,
        "reply_markdown": md_reply
    }

def sync_wearable_tss(prompt: str, athlete_name: Optional[str] = None) -> Dict[str, Any]:
    text = prompt.lower()
    name_str = f" para **{athlete_name}**" if athlete_name else ""
    
    # Extraer TSS o kJ
    tss_match = re.search(r'tss\s*[:=]?\s*(\d+[\.,]?\d*)', text)
    kj_match = re.search(r'(\d+[\.,]?\d*)\s*(?:kj|kilojulios)', text)
    
    lines = [f"### ⌚ Sincronización Wearables & Recalibración Nutricional{name_str}"]
    lines.append("*(Garmin Connect · Strava · TrainingPeaks · Consenso IOC/ACSM)*\n")
    
    tss_val = float(tss_match.group(1).replace(',', '.')) if tss_match else None
    kj_val = float(kj_match.group(1).replace(',', '.')) if kj_match else None
    
    if kj_val:
        # 1 kJ mecánico en ciclismo equivale aproximadamente a 1 kcal gastada (eficiencia metabólica humana ~20-25%)
        kcal_est = round(kj_val)
        lines.append(f"• **Trabajo Mecánico Registrado:** **{kj_val} kJ**")
        lines.append(f"• **Gasto Energético Activo Real:** **~{kcal_est} kcal** (eficiencia muscular ~22-24%)")
        lines.append(f"• **Reajuste Nutricional Directo:** Sumar **{kcal_est} kcal** al BMR Cunningham de base.")

    if tss_val is not None:
        lines.append(f"• **Training Stress Score (TSS):** **{tss_val} puntos**")
        if tss_val < 50:
            zone = "Recuperación Activa / Baja Carga"
            cho_target = "3.0 - 4.0 g/kg FFM"
            rec = "Mantener hidratos moderados. Priorizar legumbres (4 tomas/sem) y verduras saciantes."
        elif tss_val <= 100:
            zone = "Carga Moderada (Tempo / Rodaje Medio)"
            cho_target = "5.0 - 6.5 g/kg FFM"
            rec = "Añadir 1 toma extra de 70g arroz/avena en seco o 250g patata post-entreno."
        elif tss_val <= 150:
            zone = "Carga Alta (Intervalos / Tirada Larga)"
            cho_target = "7.0 - 8.5 g/kg FFM"
            rec = "Protocolo de recarga de glucógeno: 1.2 g CHO/kg en las primeras 4h tras finalizar."
        else:
            zone = "Carga Extrema / Competición"
            cho_target = "9.0 - 11.0 g/kg FFM"
            rec = "Priorizar hidratos de absorción rápida en las primeras horas para no sobrecargar el tracto digestivo."
            
        lines.append(f"• **Zona de Carga Fisiológica:** **{zone}**")
        lines.append(f"• **Diana de Hidratos de Carbono:** **{cho_target}**")
        lines.append(f"• **Directriz ANyD:** {rec}")
    else:
        lines.append("#### 📊 Escala de Modulación Dinámica de Hidratos según TSS:")
        lines.append("1. **TSS < 50 (Descanso/Suave):** 3 - 4 g CHO / kg FFM")
        lines.append("2. **TSS 50 - 100 (Moderado):** 5 - 6.5 g CHO / kg FFM")
        lines.append("3. **TSS 100 - 150 (Intenso):** 7 - 8.5 g CHO / kg FFM")
        lines.append("4. **TSS > 150 (Competición/Doble sesión):** 9 - 11 g CHO / kg FFM")
        lines.append("\n*Tip:* Puedes escribir: *«Sincroniza entreno con TSS 120 y 1400 kJ»*")

    md_reply = "\n".join(lines)
    return {
        "success": True,
        "type": "wearable_sync",
        "reply": md_reply,
        "reply_markdown": md_reply
    }

def audit_supermarket_product(prompt: str) -> Dict[str, Any]:
    lines = ["### 🛒 Auditor Clínico de Supermercado & Clasificación NOVA"]
    lines.append("*(Criterios ANyD Nutricionistas · Mercadona, Lidl, Aldi, Carrefour)*\n")
    
    lines.append("#### 🚫 Filtro Estricto de Exclusión:")
    lines.append("• **NOVA 4 (Ultraprocesados):** RECHAZO CLÍNICO ABSOLUTO. Grasas hidrogenadas, azúcares añadidos, emulgentes agresivos y nitritos.")
    lines.append("• **Grasas Saturadas:** Deben ser **<7-8% del Valor Calórico Total**.")
    lines.append("• **Sal:** Máximo **1.0 - 1.2 g / 100g** de producto.")
    
    lines.append("\n#### 🏆 Productos de Alta Conveniencia Recomendados (Cocina en 10-15 min):")
    lines.append("1. **Mercadona (Hacendado):**")
    lines.append("   - Bote de garbanzos / lentejas cocidas (lavar para eliminar exceso de sodio).")
    lines.append("   - Edamame ultracongelado (5 min al microondas, fuente de proteína completa).")
    lines.append("   - Tofu firme o soja texturizada fina.")
    lines.append("   - Pan 100% integral de centeno o masa madre (comprobar primer ingrediente 100% harina de grano entero).")
    lines.append("2. **Lidl (Bio Organic / Milbona):**")
    lines.append("   - Copos de avena integral finos (gachas en 3 min).")
    lines.append("   - Yogur natural desnatado o queso fresco batido 0% (20g proteína por ración).")
    lines.append("   - Bolsas de verduras al vapor para microondas (brócoli, judías verdes, zanahoria).")
    
    lines.append("\n#### ⏱️ Regla ANyD de Preparación Adherente:")
    lines.append("Comidas principales listas en **máximo 15 minutos**: base de legumbre en conserva + verduras al vapor/salteadas en AOVE (medido por cuchara) + fuente magra (huevo, pollo de corral, pescado o tofu).")

    md_reply = "\n".join(lines)
    return {
        "success": True,
        "type": "supermarket_audit",
        "reply": md_reply,
        "reply_markdown": md_reply
    }

def generate_whatsapp_patient_message(prompt: str, athlete_name: Optional[str] = None) -> Dict[str, Any]:
    text = prompt.lower()
    name = athlete_name if athlete_name else "Deportista"
    first_name = name.split()[0]
    
    if "tanita" in text or "pesaje" in text or "recordatorio" in text or "24h" in text:
        msg_title = "Recordatorio Protocolo 24h Previo a Tanita MC-580"
        msg_body = f"""¡Hola {first_name}! 👋 Te escribo desde ANyD Nutricionistas para recordarte las pautas que debemos seguir en las 24 horas previas a tu pesaje con la báscula bioimpedancia Tanita MC-580 para garantizar la máxima precisión clínica:

1. 💧 Mantén una hidratación normal y constante a lo largo del día previo.
2. 🍽️ Ven con un ayuno de 2 a 3 horas de comida sólida y líquidos abundantes.
3. ☕ Evita tomar café, bebidas energéticas, té o suplementos estimulantes en las 12 horas previas.
4. 🍷 Cero alcohol en las 24 horas anteriores a la consulta.
5. 🏃 No realices entrenamientos extenuantes en las 12-24 horas previas.
6. 🚻 Ve al baño justo antes de subir a la báscula para vaciar la vejiga.

¡Nos vemos en la consulta! Un abrazo, Román Illescas (Col. MAD00274)."""
    elif "dossier" in text or "pdf" in text or "entrega" in text or "patron" in text or "pauta" in text:
        msg_title = "Entrega Oficial de Patrón Nutricional ANyD (PDF 20 páginas)"
        msg_body = f"""¡Hola {first_name}! 👋 Ya tienes listo tu Patrón Nutricional Oficial de 7 días elaborado a medida con los datos de tu última valoración antropométrica.

📄 Puedes consultar y descargar tu Dossier Clínico completo en tu carpeta privada de Google Drive:
👉 [Enlace a tu Carpeta ANyD en Google Drive]

Puntos clave a recordar esta semana:
• 🍚 Consistencia de hidratos: mantén estables las raciones de cereales (70g en seco) y legumbres/patatas (250g).
• 🫒 AOVE medido con cuchara (1 cuchara de postre = 5g, sopera = 10g).
• 🥗 Mínimo 4 tomas de legumbres a la semana y cero ultraprocesados.
• ⚡ En los días de entrenamiento intenso, sigue la pauta peri-entreno para maximizar la digestión y el vaciamiento gástrico.

Cualquier duda que te surja con las recetas o adaptaciones, escríbeme por aquí. ¡A por ello! 💪
Román Illescas Quiroga (Col. MAD00274)"""
    else:
        msg_title = "Seguimiento Clínico de Tolerancia y Adherencia (Día +7 / +10)"
        msg_body = f"""¡Hola {first_name}! 👋 ¿Cómo van estos primeros días con tu nuevo patrón nutricional?

Quería hacer un chequeo rápido de sensaciones:
1. 消化 ¿Qué tal la tolerancia digestiva y el vaciamiento gástrico antes de los entrenamientos?
2. ⚡ ¿Cómo te estás sintiendo de niveles de energía durante las sesiones?
3. 🍳 ¿Te está resultando cómoda y ágil la preparación de las comidas de 10-15 minutos?

Si hay algún ingrediente o preparación que quieras que adaptemos, dímelo y lo ajustamos de inmediato. ¡Seguimos sumando!
Román Illescas (Col. MAD00274)"""

    lines = [f"### 📱 Mensaje Clínico de WhatsApp: {msg_title}"]
    lines.append(f"*(Personalizado para **{name}** — Listo para copiar y pegar en WhatsApp Web)*\n")
    lines.append("```text")
    lines.append(msg_body)
    lines.append("```")
    lines.append("\n💡 *Puedes hacer clic en el botón de copiar inferior para pegarlo directamente en el chat con el deportista.*")

    md_reply = "\n".join(lines)
    return {
        "success": True,
        "type": "whatsapp_message",
        "title": msg_title,
        "raw_message": msg_body,
        "reply": md_reply,
        "reply_markdown": md_reply
    }
