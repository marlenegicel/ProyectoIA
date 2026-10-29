from collections import Counter
from cliente import consultar_modelo
from  pipeline_core import procesar_texto
import json


def contar_coincidencias(
    tokens_referencia: list[str],
    tokens_respuesta: list[str],
) -> int:
    """Cuenta las coincidencias entre referencia y respuesta."""
    conteo_referencia = Counter(tokens_referencia)
    conteo_respuesta = Counter(tokens_respuesta)
    interseccion = conteo_referencia & conteo_respuesta
    return sum(interseccion.values())

def calcular_precision_cobertura_f1(
    tokens_referencia: list[str],
    tokens_respuesta: list[str],
) -> dict[str, float]:
    """Calcula precisión, cobertura y F1 de dos listas de tokens."""
    coincidencias = contar_coincidencias(
        tokens_referencia, tokens_respuesta
    )

    if not tokens_respuesta or not tokens_referencia:
        return {"precision": 0.0, "cobertura": 0.0, "f1": 0.0}
    precision = coincidencias / len(tokens_respuesta)
    cobertura = coincidencias / len(tokens_referencia)
    if precision + cobertura == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * cobertura / (precision + cobertura)
    resultado = {
        "precision": precision,
        "cobertura": cobertura,
        "f1": f1,
    }
    return resultado

def calcular_metricas(texto_referencia, texto_respuesta):

    tokens_referencia = procesar_texto(texto_referencia)
    tokens_respuesta = procesar_texto(texto_respuesta)
    return calcular_precision_cobertura_f1(
        tokens_referencia, tokens_respuesta
    )

casos = [

    (
        "¿Qué es Python?",
        "Python es un lenguaje de programación interpretado.",
    ),
    ("¿Cuándo se creó Python?", "Python fue creado en 1991."),
    (
        "¿Qué es una lista en Python?",
        "Una lista es una colección ordenada y modificable.",
    ),

]

resultados = []

for consulta, referencia in casos:
    respuesta = consultar_modelo(consulta,"utiliza una respuesta corta no más de 100 palabras")
    metricas = calcular_metricas(referencia, respuesta)
    print(consulta, metricas)

for consulta, referencia in casos:
    respuesta = consultar_modelo(consulta)
    metricas = calcular_metricas(referencia, respuesta)
    resultados.append({
        "consulta": consulta,
        "respuesta": respuesta,
        **metricas,
    })

with open(
    "resultados_metricas.json", "w", encoding="utf-8"
) as archivo:
    json.dump(resultados, archivo, indent=2, ensure_ascii=False)

peores_casos = sorted(resultados, key=lambda r: r["f1"])
for caso in peores_casos[:3]:
    print(caso["consulta"], caso["f1"])





# referencia_ =  """Necesito proyectar los costos del año 2027 usando como base el mismo período del año anterior (2026).
# Esta base solo es válida si no hay desviaciones anómalas (eventos extraordinarios, cambios de precios, cierres, compras no recurrentes, etc.).

# Datos disponibles:
# - Costos mensuales desde 2023 de prestaciones de salud,aperturadas por división, plan  y tipo de prestacion
# - Industria: Salud, Isapre
# - Factores conocidos para 2027: IPC y cartera de beneficiarios

# Indícame:
# 1. La metodología recomendada y por qué es la más adecuada.
# 2. Cómo detectar desviaciones anómalas (técnicas y umbrales) y cómo tratarlas (normalizar, excluir o reemplazar por promedio)."""

# respuesta_ = """La metodología recomendada es proyectar con base el mismo mes del año anterior, 
# normalizado, y ajustarlo por IPC y por la variación de la cartera de beneficiarios: 
# costo 2027 = costo 2026 normalizado × (1 + IPC) × (beneficiarios 2027 / beneficiarios 2026). 
# Conviene trabajar con el costo por beneficiario, separando frecuencia y costo medio, 
# y proyectar por división, plan y tipo de prestación para respetar la estacionalidad mensual. 
# Es adecuada porque mantiene la estacionalidad, usa los factores conocidos y es simple de explicar.

# Para detectar desviaciones anómalas se compara cada mes de 2026 con el mismo mes de 2023, 2024 y 2025. 
# Técnicas: z-score con umbral de 2 o 3 desviaciones estándar, rango intercuartílico (IQR) con 1,5 veces el IQR, 
# variación porcentual sobre el promedio histórico mayor a 15% o 20%, y descomposición de la serie 
# en tendencia, estacionalidad y residuo. 
# Tratamiento: normalizar cuando la causa es conocida y cuantificable, como un cambio de precios; 
# excluir los eventos no recurrentes, como compras extraordinarias o cierres; 
# y reemplazar por el promedio o la mediana del mismo mes de años anteriores, ajustado por IPC, 
# cuando el dato no es representativo."""

# referencia = procesar_texto(respuesta_)
# respuesta = procesar_texto(consultar_modelo(referencia_,"Eres un analista financiero senior especializado en FP&A. Responde en español, claro y práctico."))
# resultado = calcular_precision_cobertura_f1(referencia, respuesta)
# print(resultado)