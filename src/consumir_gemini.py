import os
import requests
from dotenv import load_dotenv
import time
import json
import re

load_dotenv()

MODELO="gemini-3.8-flash"
URL_BASE="https://generativelanguage.googleapis.com/v1beta/models/"
API_KEY=os.getenv("GEMINI_API_KEY")

SYSTEM_INSTRUCTION = """Eres un analista financiero senior especializado en planificación y control de gestión (FP&A).
Responde en español, con lenguaje claro y práctico."""

PREGUNTA = """Necesito proyectar los costos del año 2027 usando como base el mismo período del año anterior (2026).
Esta base solo es válida si no hay desviaciones anómalas (eventos extraordinarios, cambios de precios, cierres, compras no recurrentes, etc.).

Datos disponibles:
- Costos mensuales desde 2023 de prestaciones de salud,aperturadas por división, plan  y tipo de prestacion
- Industria: Salud, Isapre
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
        respuesta=requests.post(url,json=body, timeout=30)
    except requests.exceptions.ConnectionError:
        raise RuntimeError("No se pudo conectar con el servicio.Intenta de nuevo en unos momentos")
    except requests.exceptions.Timeout:
        raise RuntimeError("Se agotó el tiempo.Intenta de nuevo en unos momentos")

    if respuesta.status_code in (401,403):
        raise ValueError("Credencial inválida o sin permiso.Revisa tu GEMINI_API_KEY")
    if respuesta.status_code>=500:
        raise TimeoutError("El proveedor no puedo procesar la petición.Hay que esperar y reintentar")

    if respuesta.status_code==429:
        segundos=respuesta.headers.get("Retry-After")
        mensaje=f"Limite excedido.Reintentar en {segundos}." if segundos else "Límite excedido"
        raise TimeoutError (mensaje)

    

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
    

def obtener_dato_de_prueba(pregunta): # pregunta ="confirma la conexión"

    response_schema={
        "type":"OBJECT",
        "properties":{
            "categoria":{"type":"STRING"},
            "confianza":{"type":"NUMBER"}
        },
        "required":["categoria","confianza"]
    }

    system_instruction="""Eres un analista financiero senior especializado en planificación y control de gestión (FP&A). Responde en español, con lenguaje claro y práctico."""
    url,body =armar_peticion(MODELO,PREGUNTA,SYSTEM_INSTRUCTION,RESPONSE_SCHEMA)

    inicio= time.perf_counter() #empezar contador
    
    datos=enviar_peticion(url,body)
    fin=time.perf_counter()#termina el contador
    latencia=fin-inicio
    print(f"Latencia : {latencia:.2f} segundos")
    costo=calcular_costo(datos,0.00000075,0.00000375)
    print(f"Costo de la petición : ${costo:.6f} USD")
    texto = extraer_texto(datos)
    return parsear_respuesta_json(texto, CLAVES_REQUERIDAS)

def calcular_costo(datos, precio_entrada, precio_salida):
    uso = datos["usageMetadata"]
    tokens_entrada = uso.get("promptTokenCount", 0)
    tokens_salida = uso.get("candidatesTokenCount", 0)
    tokens_razonamiento = uso.get("thoughtsTokenCount", 0)
    costo = (tokens_entrada * precio_entrada) + ((tokens_salida + tokens_razonamiento) * precio_salida)
    return costo

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


if __name__ == "__main__":
    try:
        print(obtener_dato_de_prueba("confirma en una frase corta que esta conexion funciona"))
    except (ValueError, RuntimeError,TimeoutError) as error:
        print("No se pudo completar la operación:", error)

