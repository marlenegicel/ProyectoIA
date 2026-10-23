# Decisión de arquitectura: elección de modelo

## Modelo elegido

`gemini-3.8-flash` 

## Justificación

El presupuesto es uno de los procesos anuales más importantes de la compañía y conlleva decisiones importantes y responsabilidad, por lo que el criterio que más pesó fue la calidad de la respuesta. Luego de dar el contexto de como proyectar con los datos disponibles  solicité entregar:
1. La metodología recomendada y por qué es la más adecuada.
2. Cómo detectar desviaciones anómalas (técnicas y umbrales) y cómo tratarlas (normalizar, excluir o reemplazar por promedio).

 El Modelo propone una metodología que descompone el gasto en frecuencia (prestaciones por beneficiario) y severidad (costo unitario medio) por división, plan y tipo de prestación. Eso permite controlar el efecto demográfico de la cartera de forma independiente de la variación de precios (IPC y aranceles) y deja trazables los supuestos de la proyección. Además, entrega más técnicas de detección de anomalías, una de ellas orientada a la estacionalidad mensual, y criterios de tratamiento más detallados.

Esto se acepta a cambio de una mayor latencia y un mayor costo por petición. La latencia de 205,25 segundos incluye dos reintentos por error 503. Aun así, este uso no es interactivo, ya que el presupuesto se prepara una vez al año.
Dado el error 503 , como segunda opción tendré el modelo ` gemini-3.6-flash-lite`  que  sugiere técnicas similares pero con explicaciones mas breves.

Se descarta totalmente el modelo `gemini-3.1-flash-lite` por proponer una solución muy avanzada que no es necesaria para este caso, a pesar que en el contexto se le dió la metodología base.

## Arquitectura de la solución

La miniaplicación consume la API de Gemini a través de `consumir_gemini.py`, que organiza el flujo en funciones pequeñas, cada una con una responsabilidad.

### Flujo de una consulta

1. **Entrada.** La pregunta del usuario entra por `obtener_dato_de_prueba`, que coordina todo el flujo.
2. **`armar_peticion`.** Construye la url y el body de la solicitud. Si la pregunta está vacía, lanza `ValueError`. La credencial `GEMINI_API_KEY` se lee desde el archivo `.env` con `load_dotenv` y `os.getenv`, y se inserta en la url. El body incluye la instrucción de sistema y la pregunta y, cuando se indica un esquema, pide la respuesta en formato JSON según `RESPONSE_SCHEMA`.
3. **`enviar_peticion`.** Envía un POST con la url y el body al endpoint `generateContent` de la API de Gemini y recibe la respuesta en JSON. Con `try/except` captura los errores de conexión, el timeout, un status distinto de 200 y un JSON inválido, y en todos esos casos lanza `RuntimeError`. La latencia se mide con `time.perf_counter` alrededor de este paso y se imprime en segundos.
4. **Respuesta de la API.** El JSON recibido tiene dos partes que siguen caminos distintos:
   - **`usageMetadata`:** `calcular_costo` suma los tokens de entrada, multiplicados por el precio de entrada, y los tokens de salida y de razonamiento, multiplicados por el precio de salida. El resultado es el costo en USD de la petición, que se imprime.
   - **`candidates`:** `extraer_texto` obtiene el texto generado. Si la respuesta no trae el texto en el lugar esperado (`KeyError` o `IndexError`), lanza `RuntimeError`.
5. **`parsear_respuesta_json`.** Limpia el texto (espacios y bloques de código), lo convierte a JSON y verifica que existan las claves requeridas (`metodologia` y `deteccion_anomalias`). Si no es un JSON válido o faltan claves, lanza `ValueError`.
6. **Salida.** El resultado queda como un diccionario y se muestra por consola.



## Comparación de candidatos

| Criterio | `gemini-3.6-flash` | `gemini-3.5-flash-lite` | `gemini-3.8-flash` | `gemini-3.1-flash-lite` |
|---|---|---|---|---|
| Costo por 1000 tokens de entrada | 0,00075 USD | 0,0003 USD | 0,00075 USD | 0,00025 USD |
| Costo por 1000 tokens de salida | 0,00375 USD | 0,0025 USD | 0,00375 USD | 0,0015 USD |
| Latencia observada | 15,61 segundos | 3,53 segundos | 205,25 segundos (incluye 2 reintentos por error 503) | 26,86 segundos |
| Costo de la petición de prueba | 0,010069 USD | 0,001602 USD | 0,007117 USD | 0,000909 USD |
| Calidad de respuesta para el caso | Buena respuesta, utiliza drivers correctos para la metodología | Mala, sugiere umbrales sin la base estadistica explicita  | Muy buena, metodología clara, utilizando conceptos de salud y técnicas estadisticas para cada situación  | Mala, propone un modelo de series temporales, con técnicas de machine learning muy avanzadas para un problema que no sabe si realmente requiere ese nivel de comlejidad, ya que el negocio no siempre tiene  tendencia lineal|
| Fecha de medición | 2026-10-22 | 2026-10-22 | 2026-10-22 | 2026-10-22 |



## Alternativa descartada y por qué

Se descartó el modelo  `gemini-3.1-flash-lite` ya que la respuesta no estuvo acorde a las expectativas dado el contexto , a pesar de ser el modelo mas economico , pesa más el nivel de calidad de respuesta.