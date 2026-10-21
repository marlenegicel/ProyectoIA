import time
import consumir_gemini


def evaluar_modelo(nombre_modelo, pregunta, precio_entrada, precio_salida, repeticiones=4):
    latencias = []
    costos = []

    # Le indicamos al módulo base qué modelo usar
    consumir_gemini.MODELO = nombre_modelo

    for i in range(1, repeticiones + 1):
        # 1. Armar petición
        url, body = consumir_gemini.armar_peticion(pregunta)

        # 2. Medir latencia
        inicio = time.perf_counter()
        datos = consumir_gemini.enviar_peticion(url, body)
        fin = time.perf_counter()

        latencia = fin - inicio
        latencias.append(latencia)

        # 3. Calcular costo
        costo = consumir_gemini.calcular_costo(datos, precio_entrada, precio_salida)
        costos.append(costo)

        # 4. Extraer respuesta
        respuesta = consumir_gemini.extraer_texto(datos)

        # 5. Imprimir resultados de la petición actual
        print(f"Latencia:  {latencia:.2f} segundos")
        print(f"Costo:     ${costo:.6f} USD")
        print(f"Respuesta: {respuesta}")

    # Resumen acumulado del modelo
    latencia_promedio = sum(latencias) / len(latencias)
    costo_total = sum(costos)

    print("\n" + "-" * 40)
    print(f" RESUMEN {nombre_modelo}:")
    print(f" Latencia promedio: {latencia_promedio:.2f} segundos")
    print(f" Costo acumulado ({repeticiones} peticiones): ${costo_total:.6f} USD")
    print("-" * 40 + "\n")


pregunta_prueba = "Confirma la conexion"
modelos = [
    {
        "nombre": "gemini-3.6-flash",
        "precio_entrada": 0.00000010,
        "precio_salida": 0.00000030
    },
    {
        "nombre": "gemini-3.1-flash-lite",
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
    except (RuntimeError, KeyError) as error:
        print(f"Falló {config['nombre']}: {error}\n")