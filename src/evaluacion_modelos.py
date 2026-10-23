import os
import requests
from dotenv import load_dotenv
import time
import json
import re

load_dotenv()

URL_BASE="https://generativelanguage.googleapis.com/v1beta/models/"
API_KEY=os.getenv("GEMINI_API_KEY")

SYSTEM_INSTRUCTION = """Eres un analista financiero senior especializado en planificación y control de gestión (FP&A).
Responde en español, con lenguaje claro y práctico."""

PREGUNTA = """Necesito proyectar los costos del año 2027 usando como base el mismo período del año anterior (2026).
Esta base solo es válida si no hay desviaciones anómalas (eventos extraordinarios, cambios de precios, cierres, compras no recurrentes, etc.).

Datos disponibles:
- Costos mensuales desde 2023 de prestaciones de salud,aperturadas por división, plan  y tipo de prestacion
- Industria: Salud, Isapre
-Cantidad de prestaciones de salud
- Factores conocidos para 2027: IPC y cartera de beneficiarios

Indícame:
1. La metodología recomendada y por qué es la más adecuada.
2. Cómo detectar desviaciones anómalas (técnicas y umbrales) y cómo tratarlas (normalizar, excluir o reemplazar por promedio)."""

CLAVES_REQUERIDAS = ["metodologia", "deteccion_anomalias"]

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "metodologia": {
            "type": "OBJECT",
            "properties": {
                "nombre": {"type": "STRING"},
                "descripcion": {"type": "STRING"},
                "por_que_es_adecuada": {"type": "STRING"}
            },
            "required": ["nombre", "descripcion", "por_que_es_adecuada"]
        },
        "deteccion_anomalias": {
            "type": "OBJECT",
            "properties": {
                "tecnicas": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "tecnica": {"type": "STRING"},
                            "umbral_sugerido": {"type": "STRING"},
                            "cuando_usarla": {"type": "STRING"}
                        },
                        "required": ["tecnica", "umbral_sugerido", "cuando_usarla"]
                    }
                },
                "tratamientos": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "opcion": {"type": "STRING"},
                            "cuando_aplicar": {"type": "STRING"}
                        },
                        "required": ["opcion", "cuando_aplicar"]
                    }
                }
            },
            "required": ["tecnicas", "tratamientos"]
        }
    },
    "required": CLAVES_REQUERIDAS
}


#funcion para crear la solicitud
def armar_peticion(modelo,pregunta,system_instruction,response_schema):
    if not pregunta:
        raise ValueError("La pregunta no puede estar vacia")
    url= f"{URL_BASE}{modelo}:generateContent?key={API_KEY}"
    body={  "systemInstruction":{
                "parts":[{"text":system_instruction}]
            },
            "contents": 
            [{"parts": [{"text": pregunta}]}]
        }

    if response_schema is not None:
        body["generationConfig"]={
            "responseMimeType":"application/json",
            "responseSchema": response_schema
        }
    return url,body

#función envia la petición
def enviar_peticion(url,body):
    try:
        respuesta=requests.post(url,json=body)
    except requests.exceptions.ConnectionError:
        raise RuntimeError("No se pudo conectar con el servicio.Intenta de nuevo en unos momentos")
    except requests.exceptions.Timeout:
        raise RuntimeError("Se agotó el tiempo.Intenta de nuevo en unos momentos")
    if respuesta.status_code !=200:
            raise RuntimeError(f"Error en la petición.Status code:{respuesta.status_code}")
    try:
        return respuesta.json()
    except requests.exceptions.JSONDecodeError:
        raise RuntimeError ("La respuesta del servicio no llegó en el formato esperado")


#funcion procesa y extrae
def extraer_texto(datos):
    try:
        return datos ["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError,IndexError):
        raise  RuntimeError("La respuesta no recibe el texto generado en el lugar definido")
    

def parsear_respuesta_json(texto,claves_requeridas):

    """
    claves_requeridas=["categoria","confianza"]
    """
    texto_limpio=texto.strip() #quita espacios
    texto_limpio = re.sub(r"^```(?:json)?\s*", "", texto_limpio)
    texto_limpio = re.sub(r"\s*```$", "", texto_limpio)
    try:
        datos= json.loads(texto_limpio)
    except json.JSONDecodeError:
        raise ValueError("La respuesta del modelo no es JSON válido")

    if claves_requeridas:
        faltantes=[clave for clave in claves_requeridas if clave not in datos]
        if faltantes:
            raise ValueError ("La respuesta no tiene la estructura esperada")
        
    return datos


def enviar_con_reintentos(url, body, max_intentos=4):
    """Reintenta ante 429 (límite de cuota) y 503 (servicio saturado)."""
    for intento in range(max_intentos):
        try:
            return enviar_peticion(url, body)
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


def evaluar_modelo(nombre_modelo, pregunta, precio_entrada, precio_salida, repeticiones=1):
    latencias = []
    costos = []

    for i in range(1, repeticiones + 1):
        try:
            # 1. Armar petición (misma pregunta y estructura de salida de consumir_gemini)
            url, body = armar_peticion(
                nombre_modelo,
                pregunta,
                SYSTEM_INSTRUCTION,
                RESPONSE_SCHEMA,
            )

            # 2. Medir latencia
            inicio = time.perf_counter()
            datos = enviar_con_reintentos(url, body)
            latencia = time.perf_counter() - inicio

            # 3. Calcular costo
            costo = calcular_costo_seguro(datos, precio_entrada, precio_salida)

            # 4. Extraer respuesta y convertirla al JSON esperado
            texto = extraer_texto(datos)
            respuesta = parsear_respuesta_json(texto, CLAVES_REQUERIDAS)
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
            print(f"Respuesta de {nombre_modelo}:\n{json.dumps(respuesta, indent=2, ensure_ascii=False)}")

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


modelos =  [
    {
        "nombre": "gemini-3.6-flash",
        "precio_entrada": 0.00000075,
        "precio_salida": 0.00000375
    },
    {
        "nombre": "gemini-3.5-flash-lite",
        "precio_entrada": 0.00000030,
        "precio_salida": 0.0000025
    },
    {
        "nombre": "gemini-3.8-flash",
        "precio_entrada": 0.00000075,
        "precio_salida": 0.00000375
    },
    {
        "nombre": "gemini-2.5-flash",
        "precio_entrada": 0.00000030,
        "precio_salida": 0.0000025
    },
    {
        "nombre": "gemini-3.1-flash-lite",
        "precio_entrada": 0.00000025,
        "precio_salida": 0.0000015
    }
]

# Procesar los 3 modelos consecutivamente
for config in modelos:
    try:
        evaluar_modelo(
            nombre_modelo=config["nombre"],
            pregunta=PREGUNTA,
            precio_entrada=config["precio_entrada"],
            precio_salida=config["precio_salida"],
            repeticiones=1
        )
    except Exception as error:
        print(f"Falló {config['nombre']}: {error}\n")