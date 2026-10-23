ROL = (
    "Eres un analista financiero senior de FP&A en una Isapre. "
    "Responde en español, claro y práctico."
)

METODOLOGIA = """
METODOLOGÍA OBLIGATORIA: Driver-Based Budgeting desagregado por Frecuencia y Severidad (Costo Unitario) Normalizado.
- Para cada combinación de la apertura, descompón el gasto en:
    * Frecuencia/Volumen: cantidad de prestaciones / beneficiarios.
    * Costo Unitario Medio: costo total / cantidad de prestaciones.
- Toma la base mensual 2026 depurada de atípicos.
- Proyecta el volumen 2027 aplicando la variación estimada de la cartera de beneficiarios.
- Escala el costo unitario medio con la expectativa de inflación (IPC / inflación médica) y los acuerdos arancelarios vigentes.
- Mantén separado el efecto cartera (demográfico) del efecto precio (IPC / aranceles).

DETECCIÓN DE ATÍPICOS (técnicas y umbrales):
1. MAD / Z-Score robusto: |Z robusto| > 2.5 o 3.0 sobre la serie 2023-2026. Aplica a costo medio unitario y frecuencia mensual.
2. IQR por mes calendario: fuera de [Q1 - 1.5*IQR, Q3 + 1.5*IQR] comparando el mismo mes entre 2023 y 2026. Útil con alta estacionalidad.
3. Bandas de tolerancia sobre tasa de uso per cápita: variación > +/- 15% vs el promedio móvil trimestral del año previo ajustado por cartera. Detecta cambios de cobertura, migración de planes o rezagos de liquidación.

TRATAMIENTO DE ATÍPICOS:
1. Normalizar (base homogénea): cuando la causa es un cambio conocido, cuantificable y permanente (renegociación de convenio, atrasos masivos de facturación, cambios normativos de copago). Se recalcula el mes como si el nuevo esquema hubiera operado todo el año.
2. Excluir: cuando es un evento extraordinario no replicable (provisión por litigio único, cierre temporal de prestador clave, regularización contable retroactiva, error de carga).
3. Reemplazar por mediana / promedio histórico: cuando hay un salto o caída puntual sin causa estructural identificable. Se usa la mediana del mismo mes de años previos (ajustada por cartera e IPC) o el promedio móvil centrado sin el punto atípico.

SALIDA (proyecciones 2027):
Entrega las proyecciones como valores numéricos, una fila por cada combinación de la apertura:
- PMI: prestador, división, especialidad y plan.
- PME: especialidad, división y plan.
Para cada fila, en este orden:
1. Prestaciones por beneficiario 2027.
2. Costo promedio por prestación 2027.

REGLAS:
- NO inventes datos, cifras, filas ni valores de IPC, cartera o aranceles. Si falta un dato, indícalo.
- Si no hay datos para calcular una fila, deja sus valores en null y anótalo en 'puntos_a_confirmar'.
- Si no hay una tendencia clara, o no puedes determinar cuál tratamiento aplicar a un atípico, NO tomes la decisión por tu cuenta: descríbela en 'puntos_a_confirmar' y espera mi confirmación.
- No definas el lineamiento final: yo te lo indicaré después de revisar tus puntos a confirmar.
"""

SYSTEM_INSTRUCTION = ROL + "\n" + METODOLOGIA

# ---------------------------------------------------------------------------
# Esquema de salida: una fila por apertura, con los 2 valores proyectados 2027
# ---------------------------------------------------------------------------
TEXTO = {"type": "STRING"}
VALOR = {"type": "NUMBER", "nullable": True}  # null si no hay datos

FILA_PMI = {
    "type": "OBJECT",
    "properties": {
        "prestador": TEXTO,
        "division": TEXTO,
        "especialidad": TEXTO,
        "plan": TEXTO,
        "prestaciones_por_beneficiario": VALOR,
        "costo_promedio_por_prestacion": VALOR
    },
    "required": [
        "prestador", "division", "especialidad", "plan",
        "prestaciones_por_beneficiario", "costo_promedio_por_prestacion"
    ]
}

FILA_PME = {
    "type": "OBJECT",
    "properties": {
        "especialidad": TEXTO,
        "division": TEXTO,
        "plan": TEXTO,
        "prestaciones_por_beneficiario": VALOR,
        "costo_promedio_por_prestacion": VALOR
    },
    "required": [
        "especialidad", "division", "plan",
        "prestaciones_por_beneficiario", "costo_promedio_por_prestacion"
    ]
}

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "unidad_costo": TEXTO,  # ej: CLP o UF (la misma de los datos entregados)
        "pmi": {"type": "ARRAY", "items": FILA_PMI},
        "pme": {"type": "ARRAY", "items": FILA_PME},
        "puntos_a_confirmar": {"type": "ARRAY", "items": TEXTO}
    },
    "required": ["unidad_costo", "pmi", "pme", "puntos_a_confirmar"]
}

CLAVES_ESPERADAS = ["unidad_costo", "pmi", "pme", "puntos_a_confirmar"]

# ---------------------------------------------------------------------------
# Banco de prompts
# ---------------------------------------------------------------------------
BANCO_DE_PROMPT = [
    {
        "nombre": "costos_ambulatorios_2027",
        "system_instruction": SYSTEM_INSTRUCTION,
        "ejemplo_usuario": (
            "Necesito proyectar el costo ambulatorio de 2027, usando como base el mismo período de 2026. "
            "La base solo es válida si no hay desviaciones anómalas.\n"
            "Datos: costos mensuales ambulatorios desde 2023, con IPC y cartera de beneficiarios como factores conocidos para 2027.\n"
            "Apertura PMI: prestador, división, especialidad y plan.\n"
            "Apertura PME: especialidad, división y plan.\n"
            "Entrégame, para cada apertura de PMI y PME, la proyección 2027 de prestaciones por beneficiario y de costo promedio por prestación."
        ),
        "claves_esperadas": CLAVES_ESPERADAS,
        "response_schema": RESPONSE_SCHEMA
    },
    {
        "nombre": "costos_hospitalarios_2027",
        "system_instruction": SYSTEM_INSTRUCTION,
        "ejemplo_usuario": (
            "Necesito proyectar el costo hospitalario de 2027, usando como base el mismo período de 2026. "
            "La base solo es válida si no hay desviaciones anómalas.\n"
            "Datos: costos mensuales hospitalarios desde 2023, con IPC y cartera de beneficiarios como factores conocidos para 2027.\n"
            "Apertura PMI: prestador, división, especialidad y plan.\n"
            "Apertura PME: especialidad, división y plan.\n"
            "Entrégame, para cada apertura de PMI y PME, la proyección 2027 de prestaciones por beneficiario y de costo promedio por prestación."
        ),
        "claves_esperadas": CLAVES_ESPERADAS,
        "response_schema": RESPONSE_SCHEMA
    },
    {
        "nombre": "costos_total_2027",
        "system_instruction": SYSTEM_INSTRUCTION,
        "ejemplo_usuario": (
            "Ya tengo proyectados los costos 2027 ambulatorios y hospitalarios, ambos con apertura PMI y PME.\n"
            "Únelos en un total 2027 para cada apertura: las prestaciones por beneficiario se suman y el costo promedio por prestación se pondera por el número de prestaciones.\n"
            "Apertura PMI: prestador, división, especialidad y plan.\n"
            "Apertura PME: especialidad, división y plan."
        ),
        "claves_esperadas": CLAVES_ESPERADAS,
        "response_schema": RESPONSE_SCHEMA
    },
]