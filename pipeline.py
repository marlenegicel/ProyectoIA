import re


def limpiar_texto(texto: str) -> str:
    texto = texto.lower()
    texto = re.sub(r"[^\w\s]", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto

def tokenizar(texto_limpio: str) -> list[str]:
    return texto_limpio.split()
referencia = "El cielo es azul."
respuesta = "el cielo es azul"
tokens_referencia = referencia.split()
tokens_respuesta = respuesta.split()

comunes = set(tokens_referencia) & set(tokens_respuesta)
if tokens_referencia:
    proporcion = len(comunes) / len(set(tokens_referencia))
else:
    proporcion = 0.0

print(f"Coincidencia: {proporcion:.0%}")

#############################################################################################
def procesar_texto(texto):
    texto_limpio = limpiar_texto(texto)
    return tokenizar(texto_limpio)
tokens_referencia = procesar_texto(referencia)
tokens_respuesta = procesar_texto(respuesta)
comunes = set(tokens_referencia) & set(tokens_respuesta)

if tokens_referencia:
    proporcion = len(comunes) / len(set(tokens_referencia))
else:
    proporcion = 0.0

print(f"Coincidencia: {proporcion:.0%}")