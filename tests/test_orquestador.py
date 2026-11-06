from unittest.mock import MagicMock

from langchain_core.runnables import RunnableLambda

import enrutamiento as ep
from enrutamiento import (
    procesar_mensaje_seguro,
    fallback_con_log,
    informe_basico,
    normalizar_etiqueta,
    leer_decisiones,
    calcular_proyeccion,
)

respuesta_generica = RunnableLambda(fallback_con_log)


def fallar_a_proposito(x):
    raise ConnectionError("simulado")


# ---------------------------------------------------------------------------
# 1. Fallback general: si falla la cadena, responde el mensaje genérico
# ---------------------------------------------------------------------------
def test_cadena_usa_fallback_ante_fallo_del_modelo():
    cadena_falsa = RunnableLambda(fallar_a_proposito)
    cadena_segura = cadena_falsa.with_fallbacks([respuesta_generica], exception_key="error")

    resultado = cadena_segura.invoke({"mensaje": "Necesito la proyección 2027"})

    assert resultado == (
        "No fue posible generar la respuesta en este momento. "
        "El equipo de FP&A revisará la solicitud."
    )


# ---------------------------------------------------------------------------
# 2. Fallback del paso 3: si falla el informe del LLM, igual se entregan los números
# ---------------------------------------------------------------------------
def test_paso_informe_entrega_numeros_si_falla_el_llm():
    informe_falso = RunnableLambda(fallar_a_proposito)
    informe_seguro = informe_falso.with_fallbacks(
        [RunnableLambda(informe_basico)], exception_key="error"
    )
    resultados_paso_2 = {
        "decisiones": "D", "resumen": "TOTAL | cierre 2026 1.000",
        "puente": "P", "tratados": "T", "historicas": "H", "subgrupos": "S",
    }

    resultado = informe_seguro.invoke(resultados_paso_2)

    assert "## Resumen por macrogrupo" in resultado
    assert "TOTAL | cierre 2026 1.000" in resultado


# ---------------------------------------------------------------------------
# 3. procesar_mensaje_seguro nunca propaga excepciones
# ---------------------------------------------------------------------------
def test_procesar_mensaje_seguro_no_propaga_excepciones():
    clasificacion_falsa = MagicMock()
    clasificacion_falsa.side_effect = ConnectionError("simulado")
    cadena_falsa = RunnableLambda(clasificacion_falsa)

    resultado = procesar_mensaje_seguro(cadena_falsa, "mensaje de prueba")

    assert "no pudimos procesar" in resultado.lower()


def test_procesar_mensaje_seguro_envia_los_parametros():
    capturado = {}

    def guardar_entrada(x):
        capturado.update(x)
        return "ok"

    procesar_mensaje_seguro(RunnableLambda(guardar_entrada), "hola")

    assert capturado["mensaje"] == "hola"
    assert {"tabla", "ipc", "crec_max", "ultimo_mes"} <= capturado.keys()


# ---------------------------------------------------------------------------
# 4. Enrutamiento: limpieza de la etiqueta que devuelve el modelo
# ---------------------------------------------------------------------------
def test_normalizar_etiqueta_limpia_tildes_y_simbolos():
    assert normalizar_etiqueta("Proyección") == "proyeccion"
    assert normalizar_etiqueta("**ANOMALÍAS**\n") == "anomalias"
    assert normalizar_etiqueta(" consulta. ") == "consulta"


def test_normalizar_etiqueta_invalida_va_a_consulta():
    assert normalizar_etiqueta("queja") == "consulta"


# ---------------------------------------------------------------------------
# 5. Paso 2 (Python): lectura de decisiones del paso 1
# ---------------------------------------------------------------------------
ID = "NORTE|PLAN_A|HOSPITALARIA"


def test_leer_decisiones_aplica_tope_de_crecimiento():
    respuesta = (
        f"{ID};frecuencia;acelerando;0.30;6:normalizar,7:normalizar;brote;sube cada año\n"
        f"{ID};costo_medio;estable;abc;-;sin anomalías;estable"
    )

    dec = leer_decisiones(respuesta)

    assert dec[ID]["frec"]["crecimiento"] == ep.CREC_MAX        # 0.30 se acota a 0.05
    assert dec[ID]["frec"]["tratamientos"] == {6: "normalizar", 7: "normalizar"}
    assert dec[ID]["cmed"]["crecimiento"] == 0.0                # texto inválido -> 0
    assert dec[ID]["cmed"]["tratamientos"] == {}


def test_leer_decisiones_ignora_lineas_invalidas():
    assert leer_decisiones("texto libre del modelo\nID_INEXISTENTE;frecuencia;x;0.01;-;-;-") == {}


def test_calcular_proyeccion_funciona_aunque_el_llm_responda_basura(tmp_path, monkeypatch):
    monkeypatch.setattr(ep, "ARCHIVO_SALIDA", str(tmp_path / "salida.csv"))

    resultado = calcular_proyeccion("respuesta sin formato")

    assert {"decisiones", "resumen", "puente", "tratados", "historicas", "subgrupos"} <= resultado.keys()
    assert "TOTAL" in resultado["resumen"]
    assert (tmp_path / "salida.csv").exists()

# pytest tests/test_orquestador.py -v