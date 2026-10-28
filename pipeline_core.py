from cliente import consultar_modelo
from pipeline_texto import procesar_texto
from src.consumir_gemini import PREGUNTA


consulta = PREGUNTA
referencia = """La metodología recomendada es proyectar con base el mismo mes del año anterior, 
normalizado, y ajustarlo por IPC y por la variación de la cartera de beneficiarios: 
costo 2027 = costo 2026 normalizado × (1 + IPC) × (beneficiarios 2027 / beneficiarios 2026). 
Conviene trabajar con el costo por beneficiario, separando frecuencia y costo medio, 
y proyectar por división, plan y tipo de prestación para respetar la estacionalidad mensual. 
Es adecuada porque mantiene la estacionalidad, usa los factores conocidos y es simple de explicar.

Para detectar desviaciones anómalas se compara cada mes de 2026 con el mismo mes de 2023, 2024 y 2025. 
Técnicas: z-score con umbral de 2 o 3 desviaciones estándar, rango intercuartílico (IQR) con 1,5 veces el IQR, 
variación porcentual sobre el promedio histórico mayor a 15% o 20%, y descomposición de la serie 
en tendencia, estacionalidad y residuo. 
Tratamiento: normalizar cuando la causa es conocida y cuantificable, como un cambio de precios; 
excluir los eventos no recurrentes, como compras extraordinarias o cierres; 
y reemplazar por el promedio o la mediana del mismo mes de años anteriores, ajustado por IPC, 
cuando el dato no es representativo."""

respuesta = consultar_modelo(consulta)
crudo_ref = referencia.split()
crudo_resp = respuesta.split()
comunes_crudo = set(crudo_ref) & set(crudo_resp)
pct_crudo = len(comunes_crudo) / len(set(crudo_ref))
tokens_ref = procesar_texto(referencia)
tokens_resp = procesar_texto(respuesta)
comunes = set(tokens_ref) & set(tokens_resp)
pct_proc = len(comunes) / len(set(tokens_ref))

print(f"[Caso 1] Coincidencia texto crudo: {pct_crudo:.1%}")

print(f"[Caso 1] Coincidencia texto procesado: {pct_proc:.1%}")