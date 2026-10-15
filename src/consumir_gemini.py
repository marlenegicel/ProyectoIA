import os
import requests
from dotenv import load_dotenv

load_dotenv()

MODELO="gemini-flash-latest"
URL_BASE="https://generativelanguage.googleapis.com/v1beta/models/"
API_KEY=os.getenv("GEMINI_API_KEY")

#funcion para crear la solicitud
def armar_peticion(pregunta):
    url= f"{URL_BASE}{MODELO}:generateContent?key={API_KEY}"
    body={
            "contents": 
            [{"parts": [{"text": pregunta}]}]
        }
    return url,body

#función envia la petición
def enviar_peticion(url,body):
    respuesta=requests.post(url,json=body)
    return respuesta.json()

#funcion procesa y extrae
def extraer_texto(datos):
    return datos ["candidates"][0]["content"]["parts"][0]["text"]

def obtener_dato_de_prueba(pregunta): # pregunta ="confirma la conexión"
    url,body =armar_peticion(pregunta)
    datos=enviar_peticion(url,body)
    return extraer_texto(datos)

print (obtener_dato_de_prueba("confirma en una frase corta que esta conexion funciona"))

