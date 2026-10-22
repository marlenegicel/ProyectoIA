import os
import requests
from dotenv import load_dotenv
import time
import json
import re

load_dotenv()

MODELO="gemini-3.5-flash-lite"
URL_BASE="https://generativelanguage.googleapis.com/v1beta/models/"
API_KEY=os.getenv("GEMINI_API_KEY")

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
    

def obtener_dato_de_prueba(pregunta): # pregunta ="confirma la conexión"

    response_schema={
        "type":"OBJECT",
        "properties":{
            "categoria":{"type":"STRING"},
            "confianza":{"type":"NUMBER"}
        },
        "required":["categoria","confianza"]
    }

    system_instruction="Eres un asistente amigable y respondes  en máximo  2 palabras.'"
    url,body =armar_peticion(MODELO,pregunta,system_instruction,response_schema)

    inicio= time.perf_counter() #empezar contador
    
    datos=enviar_peticion(url,body)
    fin=time.perf_counter()#termina el contador
    latencia=fin-inicio
    print(f"Latencia : {latencia:.2f} segundos")
    costo=calcular_costo(datos,0.00000075,0.00000375)
    print(f"Costo de la petición : ${costo:.6f} USD")
    texto=extraer_texto(datos)
    datos_formateados=parsear_respuesta_json(texto, ["categoria", "confianza"])
    return datos_formateados

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


try:
    print (obtener_dato_de_prueba("confirma en una frase corta que esta conexion funciona"))

except (ValueError,RuntimeError) as error:
    print("No se pudo completar  la operación: ", error )

