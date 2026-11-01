# Límites de la métrica de evaluación

## Qué mide

Compara los tokens de la respuesta del modelo con los de una referencia corta relacionada, y cuenta cuántos coinciden. Lo resume en precisión , cobertura y F1. No mide si la respuesta es correcta, si responde lo preguntado ni si se contradice.

## Modos de falla conocidos

- **Sinónimos correctos puntúan bajo.** La métrica solo reconoce palabras idénticas.
  Caso 11, f1=0.19: la respuesta es correcta y completa, pero dice "componente irregular" donde la referencia dice "residuo".
- **Un ejemplo válido distinto al de la referencia se castiga.** En preguntas abiertas hay más de una respuesta correcta.
  Caso 18, f1=0.19: propone judicializaciones y GES masivas en vez de una pandemia; ambos son ejemplos válidos para una Isapre.
- **Un F1 alto no garantiza una respuesta correcta.** Compartir vocabulario con la referencia sube el puntaje aunque el razonamiento esté mal.
  Caso 14, f1=0.31 (grupo alto): único caso con error factual. Dice que se reemplazan por el promedio los eventos "irrepetibles".
- **No detecta contradicciones.** Las palabras correctas suman aunque la respuesta diga lo contrario después.
  Caso 13, f1=0.16: dice que se excluyen los eventos no recurrentes y luego propone reemplazarlos por el promedio.
- **No detecta umbrales incompletos o cambiados.** Un número faltante pesa lo mismo que cualquier otra palabra.
  Caso 10, f1=0.31: da 15% pero omite 20%, y compara contra el mes anterior en vez del promedio histórico.
- **El texto extra baja el puntaje, aunque sea correcto.** El modelo agrega detección de anomalías a casi todas las respuestas, porque las instrucciones incluyen la pregunta original completa.
  Caso 3, f1=0.36 con cobertura 0.92: responde bien, pero la oración extra reduce la precisión a 0.22.
- **El techo del F1 es bajo.** Las referencias tienen una oración y las respuestas hasta 50 palabras.
  Caso 5, f1=0.47: es una respuesta perfecta y aun así es el máximo de los 20 casos (rango 0.09–0.47).

## Muestra revisada

Revisé  10 de los 20 casos: los 5 con f1 más bajo (0.09–0.19) y los 5 con f1 más alto (0.31–0.47). Califiqué cada uno con la rúbrica de corrección factual, completitud y contradicción, con una nota que justifica la calificación.

| Grupo | Correctos y completos | Incompletos | Con contradicción | Con error factual |
|---|---|---|---|---|
| f1 bajo | 2 (casos 11, 18) | 2 (casos 20, 2) | 1 (caso 13) | 0 |
| f1 alto | 3 (casos 7, 3, 5) | 2 (casos 10, 14) | 1 (caso 14) | 1 (caso 14) |

La diferencia entre grupos es pequeña: hay respuestas buenas con f1 bajo, y el peor caso está en el grupo alto. En este pipeline, el F1 no separa bien las respuestas buenas de las malas.

## Recomendación de uso

- **No usar el F1 como umbral de aprobación.** Con referencias de una oración, un F1 de 0.2 no indica una mala respuesta (casos 11 y 18).
- **Usarlo solo para comparar ejecuciones del mismo pipeline.** Sirve para ver si un cambio de prompt o de modelo baja el promedio (hoy 0.25).
- **Mirar la cobertura junto al F1.** Le afecta menos el texto extra, aunque tampoco detecta contradicciones (caso 13, cobertura 0.45).
- **Revisar siempre** las preguntas sobre tratamiento de anomalías (normalizar, excluir, reemplazar) y las que incluyen umbrales o fórmulas.
- **Para mejorar la métrica:** quitar la pregunta original de las instrucciones y escribir referencias de un largo similar al de las respuestas.