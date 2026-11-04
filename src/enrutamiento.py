from dotenv import  load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser #parsea la respuesta y la transforma en solo texto
from langchain_core.runnables import (RunnableBranch, RunnablePassthrough)

load_dotenv()

modelo=ChatGoogleGenerativeAI(model="gemini-3.8-flash")

plantilla_clasificacion= PromptTemplate.from_template(
    "Clasifica el siguiente mensaje de soporte en una sola palabra:"
    "pregunta,queja o sugerencia.Responde solo con esa palabra. \n\n {mensaje}"
)

paso_clasificacion=(
    plantilla_clasificacion
    | modelo
    | StrOutputParser()
    |(lambda texto: texto.strip().lower())
)
mensaje_prueba="Mi telefono no está funcionando"

clasificacion=paso_clasificacion.invoke(
    {"mensaje": mensaje_prueba}
)
print(clasificacion)


cadena_pregunta=(
    PromptTemplate.from_template("Responde esta pregunta técnica con precisión: \n\n {mensaje}")
    | modelo
    | StrOutputParser()
    )

cadena_queja=(
    PromptTemplate.from_template("Responde esta queja con empatía, reconociendo el problema antes de ofrecer una soluición \n\n {mensaje}")
    | modelo
    | StrOutputParser()
    )


cadena_sugerencia=(
    PromptTemplate.from_template("Agradece esta sugerencia y explica cómo se evaluará dentro del producto \n\n {mensaje}")
    | modelo
    | StrOutputParser()
    )


# caminos=RunnableBranch(
#     (condicion1,rama1)if
#     (condicion2,rama2)if
#     (condicion3,rama3)elif
#     rama_por_defecto 
# ) #Cada  condición debe ser una función; suele ser un lambda

bifurcacion=RunnableBranch(
    (lambda x:  x["clasificacion"]=="queja", cadena_queja),
    (lambda x:  x["clasificacion"]=="sugerencia", cadena_sugerencia),
    cadena_pregunta
)

cadena_con_enrutamiento=(
    RunnablePassthrough.assign(clasificacion=paso_clasificacion)
    | bifurcacion
    

)
resultado=cadena_con_enrutamiento.invoke(
    {"mensaje": "Deberían tener más agentes disponibles"}
)

print(resultado)