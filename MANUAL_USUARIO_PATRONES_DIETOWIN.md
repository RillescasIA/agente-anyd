# 📖 Manual de Usuario: Patrones Nutricionales, Integración Dietowin & Evolutivos Clínicos
### **ANyD Nutricionistas · Román Illescas Quiroga (Col. MAD00274)**

---

## 🚀 1. Acceso a la Estación de Trabajo
1. Abre tu navegador web habitual (Google Chrome, Microsoft Edge, etc.).
2. Accede a la URL local de la estación de trabajo:
   👉 **[http://localhost:8001/patrones-nutricionales](http://localhost:8001/patrones-nutricionales)**
3. Si el sistema te solicita credenciales de seguridad:
   - **Usuario:** `admin` (o tu usuario de consulta).
   - **Contraseña:** Tu clave habitual de ANyD.

---

## 🔍 2. Carga y Alta Automática de Deportistas / Pacientes

En la parte superior del Planificador Semanal encontrarás el campo **Deportista / Paciente** con autocompletado y el botón **`🔍 Cargar / Alta`**.

### ¿Cómo funciona la carga automática?
1. **Seleccionar o Escribir:**
   - Escribe el nombre o apellido del deportista (ejemplo: `Carol`, `Carol Escolar`, `Carolina Garrote`, `Alejandro Gil`, `Ines De Benito`, etc.).
   - Al seleccionarlo en la lista desplegable o pulsar el botón **`🔍 Cargar / Alta`**:
     1. **Comprobación CRM:** El sistema busca al paciente en la base de datos de ANyD. Si no existe, lo da de alta automáticamente con su ficha clínica base.
     2. **Composición Corporal Tanita MC-580 / FFM:** Extrae de forma autónoma el último pesaje registrado en Dietowin / Google Drive (peso, masa magra FFM, % de grasa, masa muscular y agua).
     3. **Tasa Metabólica Basal Cunningham:** Calcula el gasto energético basal exacto mediante la masa magra medida:
        $$\text{BMR}_{\text{Cunningham}} = 500 + 22 \times \text{FFM (kg)}$$
     4. **Carga del Último Patrón Dietowin:** Localiza el último archivo `.DW11W` exportado en `C:\SuiteBiológica11\DietaWeb\` y carga directamente los 7 días de la semana con todas las tomas (Desayuno, Media Mañana, Almuerzo, Merienda, Cena, Recena), alimentos, recetas, gramajes y sesiones de entrenamiento.
     5. **Notas & Consejos Particulares:** Agrega en el banner clínico las indicaciones dietéticas de Dietowin, la anamnesis de inicio de Drive y las observaciones del CRM.

---

## 📈 3. Historial de Consultas, Evolutivo & Curvas de Variación

Junto a los datos clínicos del deportista, en el banner superior, verás el botón destacado en color oscuro:
👉 **`📈 Evolutivo & Consultas`**

Al pulsar sobre él, se abre la ventana modal de **Historial Evolutivo Clínico**:

### Características del Módulo Evolutivo:
1. **Línea Temporal de Consultas:**
   - Muestra de forma cronológica todas las revisiones y pesajes del deportista ordenados por fecha.
   - Indica en cada visita: Peso, % de Grasa, FFM, Masa Muscular, Agua y Grasa Visceral.
2. **Badges de Variación ($\Delta$ Deltas):**
   - Compara de forma automática cada consulta con la anterior e indica con insignias de color la variación:
     - $\Delta\text{ Peso: } +0.6\text{ kg}$ o $-0.3\text{ kg}$.
     - $\Delta\text{ Grasa: } -0.5\%$.
     - $\Delta\text{ FFM / Músculo: } +0.4\text{ kg}$.
3. **Gráficos Interactivos de Evolución:**
   - **Curva 1:** Evolución de **Peso Total vs. Masa Magra (FFM)** a lo largo del tiempo.
   - **Curva 2:** Evolución del **% de Grasa Corporal vs. Masa Muscular (kg)**.
   - Permite visualizar con total claridad el progreso del atleta en fases de definición, ganancia muscular o preparación competitiva.

---

## ➕ 4. Introducir Nuevos Valores de Consulta (Agente como Gestor Principal)

Cuando realices una nueva consulta presencial o telemática con el deportista:
1. En la ventana del Historial Evolutivo, pulsa el botón verde:
   👉 **`+ Registrar Nueva Consulta`**
2. Se desplegará el formulario para introducir los datos del nuevo pesaje:
   - **Fecha de la Consulta:** Por defecto la fecha actual (o la que selecciones en el calendario).
   - **Peso (kg):** Obligatorio.
   - **% Grasa Corporal:** Opcional (estimará masa grasa).
   - **Masa Muscular (kg) y Masa Magra FFM (kg):** Si se deja vacío, el sistema calculará la masa magra y el gasto basal Cunningham automáticamente.
   - **Agua % y Perímetro Cintura (cm):** Métricas antropométricas adicionales.
   - **Notas Clínicas de la Consulta:** Observaciones subjetivas sobre sensaciones, entrenamientos, digestiones o cambios pautados.
3. Pulsa **`💾 Guardar Consulta en Evolutivo`**:
   - El sistema guardará el registro en `tanita_measurements` y `clinical_notes`.
   - Se recalcularán de inmediato todas las variaciones y las curvas gráficas quedarán actualizadas en tiempo real.

---

## 🏃 5. Gestión de Entrenamientos y Microciclo Semanal

El agente permite incorporar entrenamientos al cuadrante de tres formas complementarias:
1. **Pegar Entrenamientos (Copy-Paste):**
   - Pulsa el botón verde **`📋 Pegar Entrenamientos`**.
   - Pega el texto plano recibido del deportista o entrenador (por WhatsApp, email o TrainingPeaks).
   - Selecciona los días aplicables y pulsa procesar: el agente detectará el deporte, la hora y situará el entrenamiento en el hueco correspondiente del cuadrante, aplicando la periodización de hidratos ACSM.
2. **Cargar de su Carpeta Drive (ACSM):**
   - Pulsa el botón naranja **`🏃 Cargar Entrenamientos de su Carpeta`**.
   - El agente leerá los Excels de cuadrantes de Google Drive del deportista.
3. **Desplazar y Reordenar Tomas:**
   - En cada fila del cuadrante puedes desplazar tomas hacia arriba (⬆) o hacia abajo (⬇), ordenar cronológicamente por hora o añadir nuevos huecos personalizados (ej: tomas intra-entreno).

---

## 🛡️ 6. Normas de Integridad y Respaldo
- **Modo Solo Lectura con Dietowin de Escritorio:** El escaneo y extracción desde SuiteBiológica 11 se realiza de forma 100% autónoma y no intrusiva, sin modificar los ficheros internos del programa.
- **Terminología Oficial:** La plataforma emplea estrictamente la denominación **"Patrón Nutricional"**, cumpliendo con la filosofía clínica de ANyD Nutricionistas.
