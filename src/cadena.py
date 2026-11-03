from dotenv import  load_dotenv
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser #parsea la respuesta y la transforma en solo texto
from langchain_core.prompts import ChatPromptTemplate #plantilla que incluye rol de sistema e instrucción

load_dotenv()
#modelo=ChatGoogleGenerativeAI(model='gemini-3.6-flash',api_key=api_key)
modelo=ChatGoogleGenerativeAI(model='gemini-3.6-flash')
#respuesta=modelo.invoke("¿que es un token?")
#print(respuesta.content)

plantilla=PromptTemplate.from_template(
    "Explica el concepto de {tema} en un párrafo, para alguien que recién comienza en {area}"
)
# prompt=plantilla.invoke(
#     {"tema" :"tokenizacion","area":"procesamiento de texto" }
# )
# print(prompt.text)

cadena_simple= plantilla | modelo | StrOutputParser()
respuesta= cadena_simple.invoke(
    {"tema" :"tokenizacion","area":"procesamiento de texto" }
)

print(respuesta)

plantilla_conrol=ChatPromptTemplate.from_messages([
    ("system","Eres un experto en el área correspondiente, vas a responder siempre con texto simple para el usuario")
    ("human","Explica el concepto de {tema} en un párrafo,para alguien que recién comienza en {area}")
])


