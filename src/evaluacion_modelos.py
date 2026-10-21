import time
import consumir_gemini


def enviar_con_reintentos(url, body, max_intentos=4):
    """Reintenta ante 429 (límite de cuota) y 503 (servicio saturado)."""
    for intento in range(max_intentos):
        try:
            return consumir_gemini.enviar_peticion(url, body)
        except RuntimeError as e:
            transitorio = "429" in str(e) or "503" in str(e)
            if transitorio and intento < max_intentos - 1:
                espera = 5 * 2 ** intento  # 5s, 10s, 20s
                print(f"  Reintentando en {espera}s ({e})")
                time.sleep(espera)
            else:
                raise


def calcular_costo_seguro(datos, precio_entrada, precio_salida):
    """Reemplaza calcular_costo: no falla si falta thoughtsTokenCount."""
    usage = datos.get("usageMetadata", {})
    entrada = usage.get("promptTokenCount", 0)
    salida = usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)
    return entrada * precio_entrada + salida * precio_salida


def evaluar_modelo(nombre_modelo, pregunta, precio_entrada, precio_salida, repeticiones=4):
    latencias = []
    costos = []

    # Le indicamos al módulo base qué modelo usar
    consumir_gemini.MODELO = nombre_modelo

    for i in range(1, repeticiones + 1):
        try:
            # 1. Armar petición
            url, body = consumir_gemini.armar_peticion(pregunta)

            # 2. Medir latencia
            inicio = time.perf_counter()
            datos = enviar_con_reintentos(url, body)
            latencia = time.perf_counter() - inicio

            # 3. Calcular costo
            costo = calcular_costo_seguro(datos, precio_entrada, precio_salida)

            # 4. Extraer respuesta
            respuesta = consumir_gemini.extraer_texto(datos)
        except Exception as e:
            print(f"[{nombre_modelo}] intento {i} falló: {e}")
            continue

        latencias.append(latencia)
        costos.append(costo)

        # 5. Imprimir resultados de la petición actual
        print(f"[{nombre_modelo}] #{i}")
        print(f"Latencia:  {latencia:.2f} segundos")
        print(f"Costo:     ${costo:.6f} USD")
        if i == 1:  # solo la primera respuesta, para no llenar la pantalla
            print(f"Respuesta: {respuesta}")

        time.sleep(3)  # pausa para no superar el límite por minuto

    if not latencias:
        print(f"\nSin resultados válidos para {nombre_modelo}\n")
        return

    # Resumen acumulado del modelo
    print("\n" + "-" * 40)
    print(f" RESUMEN {nombre_modelo} ({len(latencias)}/{repeticiones} exitosas):")
    print(f" Latencia promedio: {sum(latencias) / len(latencias):.2f} segundos")
    print(f" Costo acumulado: ${sum(costos):.6f} USD")
    print("-" * 40 + "\n")


pregunta_prueba = """Actúa como un analista financiero senior especializado en planificación y control de gestión (FP&A).

Contexto:
Necesito proyectar los costos de año 2027 usando como base el mismo período del año anterior. Esta base solo es válida si no hay desviaciones anómalas (eventos extraordinarios, cambios de precios, cierres, compras no recurrentes, etc.).

Datos disponibles:
- costos desde 2023
- Granularidad mensual
- Industria o tipo de negocio: Salud Isapre
- Factores conocidos que afectarán el próximo período: IPC, cartera de beneficiarios

Necesito que me indiques:
1. La metodología recomendada para proyectar costos con base en el mismo período del año anterior (ej.: base año anterior + ajuste por inflación y volumen, estacionalidad, presupuesto base cero comparado, etc.), explicando por qué es la más adecuada.
2. Cómo detectar y definir desviaciones anómalas (umbrales sugeridos, ej.: ±10% vs. promedio histórico, desviación estándar, z-score, análisis de varianza), y cómo tratarlas: normalizarlas, excluirlas o reemplazarlas por un promedio.
3. Un paso a paso aplicable, con las fórmulas clave (por ejemplo: Costo proyectado = Costo base normalizado × (1 + inflación) × (1 + variación de volumen)).
4. Riesgos, limitaciones de este método y cuándo conviene cambiar a otro (promedio móvil, regresión, suavizamiento exponencial, etc.).

Formato: respuesta estructurada con títulos, fórmulas y una tabla de ejemplo. Lenguaje claro y práctico."""


modelos = [
    {
        "nombre": "gemini-3.6-flash",
        "precio_entrada": 0.00000010,
        "precio_salida": 0.00000030
    },
    {
        "nombre": "gemini-3.5-flash-lite",
        "precio_entrada": 0.00000075,
        "precio_salida": 0.00000375
    },
    {
        "nombre": "gemini-3.8-flash",
        "precio_entrada": 0.00000250,
        "precio_salida": 0.00001000
    }
]

# Procesar los 3 modelos consecutivamente
for config in modelos:
    try:
        evaluar_modelo(
            nombre_modelo=config["nombre"],
            pregunta=pregunta_prueba,
            precio_entrada=config["precio_entrada"],
            precio_salida=config["precio_salida"],
            repeticiones=4
        )
    except Exception as error:
        print(f"Falló {config['nombre']}: {error}\n")