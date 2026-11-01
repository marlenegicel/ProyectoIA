
import json
import os
import time
from collections import Counter

from cliente import consultar_modelo
from pipeline_core import procesar_texto




def contar_coincidencias(
    tokens_referencia: list[str],
    tokens_respuesta: list[str],
) -> int:
    """Cuenta las coincidencias entre referencia y respuesta."""
    interseccion = Counter(tokens_referencia) & Counter(tokens_respuesta)
    return sum(interseccion.values())


def calcular_precision_cobertura_f1(
    tokens_referencia: list[str],
    tokens_respuesta: list[str],
) -> dict[str, float]:
    """Calcula precisión, cobertura y F1 de dos listas de tokens."""
    if not tokens_respuesta or not tokens_referencia:
        return {"precision": 0.0, "cobertura": 0.0, "f1": 0.0}
    coincidencias = contar_coincidencias(tokens_referencia, tokens_respuesta)
    precision = coincidencias / len(tokens_respuesta)
    cobertura = coincidencias / len(tokens_referencia)
    if precision + cobertura == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * cobertura / (precision + cobertura)
    return {"precision": precision, "cobertura": cobertura, "f1": f1}


def calcular_metricas(texto_referencia: str, texto_respuesta: str) -> dict[str, float]:
    return calcular_precision_cobertura_f1(
        procesar_texto(texto_referencia),
        procesar_texto(texto_respuesta),
    )



PREGUNTA = """Necesito proyectar los costos del año 2027 usando como base el mismo período del año anterior (2026).
Esta base solo es válida si no hay desviaciones anómalas (eventos extraordinarios, cambios de precios, cierres, compras no recurrentes, etc.).

Datos disponibles:
- Costos mensuales desde 2023 de prestaciones de salud,aperturadas por división, plan  y tipo de prestacion
- Industria: Salud, Isapre
- Factores conocidos para 2027: IPC y cartera de beneficiarios

Indícame:
1. La metodología recomendada y por qué es la más adecuada.
2. Cómo detectar desviaciones anómalas (técnicas y umbrales) y cómo tratarlas (normalizar, excluir o reemplazar por promedio)."""

INSTRUCCIONES = (
    "Eres un analista financiero senior especializado en FP&A. "
    "Responde en español, claro y práctico. "
    "Responde en una o dos oraciones, máximo 50 palabras, sin listas ni títulos. "
    "Contexto del proyecto:\n" + PREGUNTA
)



casos = [
    (
        "¿Qué base se usa para proyectar los costos de 2027?",
        "Se usa como base el costo del mismo mes de 2026, normalizado y sin desviaciones anómalas.",
    ),
    (
        "¿Cuál es la fórmula para proyectar el costo 2027 con IPC y cartera?",
        "Costo 2027 = costo 2026 normalizado × (1 + IPC) × (beneficiarios 2027 / beneficiarios 2026).",
    ),
    (
        "¿Por qué conviene proyectar mes a mes y no el año completo?",
        "Porque proyectar por mes respeta la estacionalidad de las prestaciones de salud.",
    ),
    (
        "¿Por qué conviene trabajar con el costo por beneficiario?",
        "Porque aísla el efecto del tamaño de la cartera y permite comparar períodos con distinta cantidad de beneficiarios.",
    ),
    (
        "¿En qué componentes se descompone el costo por beneficiario?",
        "Se descompone en frecuencia de uso de prestaciones y costo medio por prestación.",
    ),
    (
        "¿Con qué nivel de apertura conviene proyectar los costos?",
        "Conviene proyectar por división, plan y tipo de prestación.",
    ),
    (
        "¿Contra qué se compara cada mes de 2026 para detectar anomalías?",
        "Se compara cada mes de 2026 con el mismo mes de 2023, 2024 y 2025.",
    ),
    (
        "¿Qué umbral se usa con el z-score para marcar una anomalía?",
        "Se considera anómalo un valor con z-score mayor a 2 o 3 desviaciones estándar.",
    ),
    (
        "¿Cómo se usa el rango intercuartílico para detectar anomalías?",
        "Es anómalo un valor bajo Q1 menos 1,5 veces el IQR o sobre Q3 más 1,5 veces el IQR.",
    ),
    (
        "¿Qué umbral de variación porcentual indica una desviación anómala?",
        "Una variación mayor a 15% o 20% sobre el promedio histórico del mismo mes.",
    ),
    (
        "¿Cómo ayuda la descomposición de la serie a detectar anomalías?",
        "Separa la serie en tendencia, estacionalidad y residuo; los residuos grandes indican anomalías.",
    ),
    (
        "¿Cuándo conviene normalizar un dato anómalo?",
        "Se normaliza cuando la causa es conocida y cuantificable, como un cambio de precios.",
    ),
    (
        "¿Cuándo conviene excluir un dato anómalo?",
        "Se excluyen los eventos no recurrentes, como compras extraordinarias o cierres.",
    ),
    (
        "¿Cuándo conviene reemplazar un dato anómalo por un promedio?",
        "Cuando el dato no es representativo, se reemplaza por el promedio o la mediana del mismo mes de años anteriores, ajustado por IPC.",
    ),
    (
        "¿Por qué se ajusta la proyección por IPC?",
        "Porque el IPC refleja el aumento esperado de precios de las prestaciones en 2027.",
    ),
    (
        "¿Qué pasa si no se ajusta la proyección por la cartera de beneficiarios?",
        "La proyección queda sesgada, porque el costo total depende de la cantidad de beneficiarios.",
    ),
    (
        "¿Por qué usar la mediana en vez del promedio al reemplazar datos?",
        "Porque la mediana es menos sensible a valores extremos que el promedio.",
    ),
    (
        "¿Qué ejemplo de evento extraordinario puede distorsionar los costos de una Isapre?",
        "Una pandemia, un brote estacional atípico o un cambio regulatorio que altere el uso de prestaciones.",
    ),
    (
        "¿Cómo se valida la metodología de proyección?",
        "Con un backtest: proyectar 2026 usando 2025 como base y comparar contra el costo real de 2026.",
    ),
    (
        "¿Por qué esta metodología es la más adecuada?",
        "Porque mantiene la estacionalidad, usa los factores conocidos y es simple de explicar.",
    ),
]



CARPETA_DOCS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs"
)
os.makedirs(CARPETA_DOCS, exist_ok=True)

ARCHIVO_RESULTADOS = os.path.join(CARPETA_DOCS, "resultados_metricas.json")
ARCHIVO_MUESTRA = os.path.join(CARPETA_DOCS, "muestra_para_revisar.json")
ARCHIVO_REVISION = os.path.join(CARPETA_DOCS, "revision_manual.json")
# True: borra lo guardado y consulta los 20 casos desde cero.
# False: retoma desde donde quedó; solo consulta los casos que faltan.
REGENERAR = False

# Pausa entre llamadas para no exceder el límite de peticiones del servicio.
PAUSA_SEGUNDOS = 5

# Carga lo que ya esté guardado (los registros sin "id" son del Bloque 16 y se ignoran).
resultados = []
if not REGENERAR and os.path.exists(ARCHIVO_RESULTADOS):
    with open(ARCHIVO_RESULTADOS, encoding="utf-8") as archivo:
        resultados = [r for r in json.load(archivo) if "id" in r]

ids_hechos = {r["id"] for r in resultados}

for i, (consulta, referencia) in enumerate(casos, start=1):
    if i in ids_hechos:
        continue
    respuesta = consultar_modelo(consulta, INSTRUCCIONES)
    metricas = calcular_metricas(referencia, respuesta)
    resultados.append({
        "id": i,
        "consulta": consulta,
        "referencia": referencia,
        "respuesta": respuesta,
        **metricas,
    })
    resultados.sort(key=lambda r: r["id"])
    # Se guarda después de cada caso: si el servicio falla, no se pierde lo avanzado.
    with open(ARCHIVO_RESULTADOS, "w", encoding="utf-8") as archivo:
        json.dump(resultados, archivo, indent=2, ensure_ascii=False)
    print(f"[{i:02d}/{len(casos)}] f1={metricas['f1']:.2f}  {consulta}")
    time.sleep(PAUSA_SEGUNDOS)

print(f"\n{len(resultados)}/{len(casos)} casos guardados en {ARCHIVO_RESULTADOS}")



N_POR_EXTREMO = 5
ordenados = sorted(resultados, key=lambda r: r["f1"])
peores = ordenados[:N_POR_EXTREMO]
mejores = ordenados[-N_POR_EXTREMO:]

muestra_para_revisar = (
    [{**r, "grupo": "f1_bajo"} for r in peores]
    + [{**r, "grupo": "f1_alto"} for r in mejores]
)

with open(ARCHIVO_MUESTRA, "w", encoding="utf-8") as archivo:
    json.dump(muestra_para_revisar, archivo, indent=2, ensure_ascii=False)

print("\n=== Muestra para revisar ===")
for r in muestra_para_revisar:
    print(f"\n#{r['id']} [{r['grupo']}] f1={r['f1']:.2f}  "
        f"(p={r['precision']:.2f}, c={r['cobertura']:.2f})")
    print(f"  Consulta:   {r['consulta']}")
    print(f"  Referencia: {r['referencia']}")
    print(f"  Respuesta:  {r['respuesta']}")


#selección a partir de los casos generados anteriormente

revision_manual = [
    # ---------------- f1 bajo ----------------
    {
        "id": 20,
        "consulta": "¿Por qué esta metodología es la más adecuada?",
        "f1": 0.09,
        "grupo": "f1_bajo",
        "correccion_factual": "si",
        "completitud": "no",
        "contradiccion": "no",
        "nota": (
            "No dice nada falso, pero no menciona estacionalidad ni simplicidad, "
            "que son las razones de la referencia. Usa la mitad de la respuesta "
            "en detección de anomalías, que no se preguntó."
        ),
    },
    {
        "id": 2,
        "consulta": "¿Cuál es la fórmula para proyectar el costo 2027 con IPC y cartera?",
        "f1": 0.14,
        "grupo": "f1_bajo",
        "correccion_factual": "si",
        "completitud": "no",
        "contradiccion": "no",
        "nota": (
            "Describe la misma lógica (base 2026 × IPC × crecimiento de cartera) "
            "pero en palabras, sin la fórmula explícita ni el término 'normalizado'. "
            "Usa sinónimos ('per cápita', 'siniestralidad') que la métrica no reconoce."
        ),
    },
    {
        "id": 13,
        "consulta": "¿Cuándo conviene excluir un dato anómalo?",
        "f1": 0.16,
        "grupo": "f1_bajo",
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "si",
        "nota": (
            "Primero dice correctamente que se excluyen los eventos no recurrentes, "
            "pero cierra diciendo que se reemplazan por el promedio: mezcla "
            "excluir con reemplazar dentro de la misma respuesta."
        ),
    },
    {
        "id": 11,
        "consulta": "¿Cómo ayuda la descomposición de la serie a detectar anomalías?",
        "f1": 0.19,
        "grupo": "f1_bajo",
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": (
            "Respuesta correcta y completa: tendencia, estacionalidad, componente "
            "irregular y residuos grandes. El f1 bajo se explica por el sinónimo "
            "'componente irregular' y el texto extra sobre IPC y beneficiarios."
        ),
    },
    {
        "id": 18,
        "consulta": "¿Qué ejemplo de evento extraordinario puede distorsionar los costos de una Isapre?",
        "f1": 0.19,
        "grupo": "f1_bajo",
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": (
            "Da un ejemplo válido y más específico de Isapre (judicializaciones, "
            "GES masivas), distinto al de la referencia (pandemia). La métrica "
            "castiga un ejemplo correcto solo por no ser el mismo."
        ),
    },
    # ---------------- f1 alto ----------------
    {
        "id": 10,
        "consulta": "¿Qué umbral de variación porcentual indica una desviación anómala?",
        "f1": 0.31,
        "grupo": "f1_alto",
        "correccion_factual": "si",
        "completitud": "no",
        "contradiccion": "no",
        "nota": (
            "Menciona 15% pero no 20%, y compara contra el mismo mes del año "
            "anterior en vez del promedio histórico del mismo mes. Además llama "
            "'normalizar' a reemplazar por promedio, que son tratamientos distintos."
        ),
    },
    {
        "id": 14,
        "consulta": "¿Cuándo conviene reemplazar un dato anómalo por un promedio?",
        "f1": 0.31,
        "grupo": "f1_alto",
        "correccion_factual": "no",
        "completitud": "no",
        "contradiccion": "si",
        "nota": (
            "Dice que se reemplaza cuando el evento es 'irrepetible', pero los "
            "eventos no recurrentes se excluyen (caso 13). No menciona mediana, "
            "mismo mes ni ajuste por IPC. Está en el grupo alto y es el peor caso."
        ),
    },
    {
        "id": 7,
        "consulta": "¿Contra qué se compara cada mes de 2026 para detectar anomalías?",
        "f1": 0.31,
        "grupo": "f1_alto",
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": (
            "Correcta: compara con 2023 a 2025. Agrega ponderación y ajuste por "
            "inflación y cartera, que es razonable aunque no está en la referencia."
        ),
    },
    {
        "id": 3,
        "consulta": "¿Por qué conviene proyectar mes a mes y no el año completo?",
        "f1": 0.36,
        "grupo": "f1_alto",
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": (
            "Responde bien (estacionalidad, cobertura 0.92). El f1 baja por la "
            "segunda oración sobre anomalías, no pedida, que además llama "
            "'análisis de varianza' a un umbral de desviaciones estándar."
        ),
    },
    {
        "id": 5,
        "consulta": "¿En qué componentes se descompone el costo por beneficiario?",
        "f1": 0.47,
        "grupo": "f1_alto",
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": (
            "Respuesta perfecta: frecuencia de uso y costo medio (severidad). "
            "Aun así el f1 es 0.47, porque la respuesta explica cada componente "
            "y eso baja la precisión. Es el f1 más alto de los 20 casos."
        ),
    },
]

with open(ARCHIVO_REVISION, "w", encoding="utf-8") as archivo:
    json.dump(revision_manual, archivo, indent=2, ensure_ascii=False)