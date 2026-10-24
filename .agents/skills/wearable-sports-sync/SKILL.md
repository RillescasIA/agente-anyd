---
name: wearable-sports-sync
description: >-
  Conector y sincronizador de métricas de entrenamiento deportivo desde Strava, Garmin Connect y TrainingPeaks
  para ANyD Nutricionistas (Román Illescas Quiroga, Col. MAD00274). Lee y procesa Training Stress Score (TSS),
  kilómetros, desnivel acumulado, potencia en vatios (Avg/NP), frecuencia cardíaca y gasto calórico real medido.
  Recalibra de forma reactiva y en tiempo real la periodización de carbohidratos (ACSM/IOC) y la ventana de recuperación.
---

# Wearable & Sports Activity Synchronizer (ANyD Nutricionistas)

Módulo de integración fisiológica de dispositivos de entrenamiento (Garmin Connect, Strava API, TrainingPeaks, Wahoo, Polar) para **ANyD Nutricionistas** (Román Illescas Quiroga, Col. MAD00274).

---

## 1. Métricas Clave de Entrenamiento Capturadas

1. **Carga de Entrenamiento (TSS - Training Stress Score):**
   - $\text{TSS} < 100$: Recuperación o fatiga baja. Requerimiento glucogénico basal ($3\text{--}4\text{ g CHO/kg}$).
   - $\text{TSS } 100\text{--}200$: Carga moderada. Requerimiento estándar ($5\text{--}6\text{ g CHO/kg}$).
   - $\text{TSS } 200\text{--}300$: Carga alta / Tirada larga de fin de semana. Requerimiento elevado ($7\text{--}8\text{ g CHO/kg}$).
   - $\text{TSS} > 300$: Carga extrema (competición o ultramaratón). Protocolo de supercompensación ($8\text{--}10+\text{ g CHO/kg}$).
2. **Potencia Mecánica en Vatios (Ciclismo / Triatlón):**
   - Potencia Media vs Potencia Normalizada (NP) e Índice de Variabilidad ($VI = NP / Avg$).
   - Trabajo total en Kilojulios ($kJ$), donde $1\text{ kJ} \approx 1.0\text{ a }1.1\text{ kcal}$ de gasto metabólico real (asumiendo una eficiencia bruta del $22\text{--}24\%$).
3. **Frecuencia Cardíaca y Zonas de Intensidad (Z1 a Z5):**
   - Tiempo en Zona 2 (metabolismo oxidativo lipídico).
   - Tiempo en Zona 4/5 (umbral anaeróbico y consumo exclusivo de glucógeno muscular y hepático).

---

## 2. Motor de Recalibración Dinámica de Carbohidratos

Cuando se recibe una sesión de entrenamiento real del atleta:

| Escenario Detectado | Gasto Calórico Real | Ajuste Nutricional Dinámico ANyD |
| :--- | :--- | :--- |
| **Día de descanso que se convirtió en entreno** | $+800\text{ a }1.500\text{ kcal}$ | Aumentar automáticamente $+1.5\text{ a }2.5\text{ g CHO/kg}$ en la cena y añadir colación de recuperación. |
| **Entrenamiento suspendido o acortado** | Reducción de gasto | Mantener el menú de descanso con ración base de hidratos ($70\text{ g}$ crudo arroz/pasta) para evitar superávit indeseado. |
| **Tirada Larga / Fondo ($>2.5\text{ horas}$)** | $+1.800\text{ a }2.500\text{ kcal}$ | Inyectar ratio de recuperación **$4:1\text{ (CHO:PRO)}$** en los primeros 60 min ($1.2\text{ g CHO/kg} + 0.3\text{ g PRO/kg}$). |

---

## 3. Protocolo de Hidratación según Potencia y Ritmo Cardiaco

* En sesiones de interior (rodillo / smart trainer indoor) la pérdida de sudor se duplica por ausencia de viento convectivo.
* Se incrementa la recomendación de fluidos a **$750\text{--}1.000\text{ mL/h}$** con **$700\text{ mg/h}$ de Sodio** para evitar calambres y drop de potencia por deshidratación celular.
