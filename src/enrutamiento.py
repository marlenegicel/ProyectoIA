import csv
import logging
import random
import statistics
import unicodedata

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableBranch, RunnablePassthrough, RunnableLambda
from langchain_google_genai import ChatGoogleGenerativeAI

# ---------------------------------------------------------------------------
# LOG DE ERRORES
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",  # 2026-11-04 16:40:00 [WARNING] __main__: ...
    datefmt="%Y-%m-%d %H:%M:%S",
    filename="error.log",
    filemode="a",
    force=True,
)
logger = logging.getLogger(__name__)

load_dotenv()

# ---------------------------------------------------------------------------
# SUPUESTOS
# ---------------------------------------------------------------------------
IPC_2027 = 0.035
IPC_HISTORICO = 0.040          # referencia para separar el crecimiento real del costo medio
UMBRAL_Z = 3.0
UMBRAL_DESVIO = 0.05           # 5 puntos porcentuales
CREC_MAX = 0.05                # tope para los crecimientos que propone el LLM
ULTIMO_MES_CERRADO_2026 = 8    # datos reales hasta agosto 2026; sep-dic 2026 se proyectan
ARCHIVO_SALIDA = "proyeccion_2026_2027_mensual.csv"
MESES = list(range(1, 13))
ANIOS_HIST = [2023, 2024, 2025, 2026]
NOMBRE_MES = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
NOMBRE_DRIVER = {"frec": "frecuencia", "cmed": "costo medio"}

SYSTEM_INSTRUCTION = """Eres un analista financiero senior especializado en planificación y control de gestión (FP&A)
en la industria de salud (Isapre). Responde en español, con lenguaje claro y práctico."""


# ---------------------------------------------------------------------------
# DATOS FICTICIOS
# ---------------------------------------------------------------------------
def generar_datos() -> dict:
    rng = random.Random(42)
    estacionalidad = {
        "AMBULATORIA":  [0.90, 0.85, 1.00, 1.05, 1.10, 1.12, 1.10, 1.05, 1.00, 1.00, 0.95, 0.88],
        "HOSPITALARIA": [0.92, 0.88, 0.98, 1.02, 1.10, 1.18, 1.20, 1.08, 0.98, 0.95, 0.90, 0.85],
    }
    config = [
        {"id": "NORTE|PLAN_A|AMBULATORIA", "benef": 9400, "benef_crec": 0.0025,
        "frec": 0.50, "crec_frec": {2024: 0.018, 2025: 0.019, 2026: 0.020},
        "cmed": 18.0, "crec_cmed": {2024: 0.050, 2025: 0.050, 2026: 0.051},
        "anomalias": [(2026, 8, "frec", 0.60)]},            # cierre temporal de prestador
        {"id": "NORTE|PLAN_A|HOSPITALARIA", "benef": 9400, "benef_crec": 0.0025,
        "frec": 0.026, "crec_frec": {2024: 0.020, 2025: 0.030, 2026: 0.040},   # la frecuencia ACELERA
        "cmed": 2500.0, "crec_cmed": {2024: 0.048, 2025: 0.046, 2026: 0.047},
        "anomalias": [(2025, 5, "cmed", 1.25),              # reliquidación de convenio may-2025 (histórica)
                    (2026, 6, "frec", 1.35), (2026, 7, "frec", 1.30)]},      # brote respiratorio
        {"id": "SUR|PLAN_B|AMBULATORIA", "benef": 6200, "benef_crec": -0.0008,
        "frec": 0.42, "crec_frec": {2024: 0.010, 2025: 0.010, 2026: 0.009},
        "cmed": 17.0, "crec_cmed": {2024: 0.035, 2025: 0.033, 2026: 0.032},
        "anomalias": [(2025, 9, "frec", 1.30),              # campaña preventiva sep-2025 (histórica)
                    (2026, 3, "cmed", 1.90)]},            # compra no recurrente
    ]
    macro = {}
    for c in config:
        tipo = c["id"].split("|")[2]
        serie = {"beneficiarios": {}, "prestaciones": {}, "costo": {}}
        nivel_f = nivel_c = 1.0
        for anio in ANIOS_HIST + [2027]:
            if anio in c["crec_frec"]:
                nivel_f *= 1 + c["crec_frec"][anio]
                nivel_c *= 1 + c["crec_cmed"][anio]
            for mes in MESES:
                t = (anio - 2023) * 12 + mes - 1
                benef = round(c["benef"] * (1 + c["benef_crec"]) ** t)
                serie["beneficiarios"][(anio, mes)] = benef
                if anio == 2027 or (anio == 2026 and mes > ULTIMO_MES_CERRADO_2026):
                    continue  # 2027 y los meses abiertos de 2026 se proyectan
                frec = c["frec"] * nivel_f * estacionalidad[tipo][mes - 1] * rng.uniform(0.985, 1.015)
                cmed = c["cmed"] * nivel_c * rng.uniform(0.99, 1.01)
                for (a, m, driver, mult) in c["anomalias"]:
                    if (a, m) == (anio, mes):
                        frec *= mult if driver == "frec" else 1
                        cmed *= mult if driver == "cmed" else 1
                prest = round(benef * frec)
                serie["prestaciones"][(anio, mes)] = prest
                serie["costo"][(anio, mes)] = round(prest * cmed / 1000, 2)
        macro[c["id"]] = serie

    detalle = [
        {"id_detalle": "NORTE|PLAN_A|AMBULATORIA|CONSULTA|CLINICA_X",  "peso_prest": 0.62, "peso_costo": 0.55},
        {"id_detalle": "NORTE|PLAN_A|AMBULATORIA|EXAMEN|CLINICA_Y",    "peso_prest": 0.38, "peso_costo": 0.45},
        {"id_detalle": "NORTE|PLAN_A|HOSPITALARIA|CIRUGIA|CLINICA_X",  "peso_prest": 0.35, "peso_costo": 0.55},
        {"id_detalle": "NORTE|PLAN_A|HOSPITALARIA|DIA_CAMA|CLINICA_Y", "peso_prest": 0.65, "peso_costo": 0.45},
        {"id_detalle": "SUR|PLAN_B|AMBULATORIA|CONSULTA|CLINICA_Z",    "peso_prest": 0.65, "peso_costo": 0.60},
        {"id_detalle": "SUR|PLAN_B|AMBULATORIA|EXAMEN|CLINICA_Z",      "peso_prest": 0.35, "peso_costo": 0.40},
    ]
    return {"macro": macro, "detalle": detalle}


datos = generar_datos()


# ---------------------------------------------------------------------------
# PREPARACIÓN (Python): drivers mensuales + detección de anomalías en todo el período
# ---------------------------------------------------------------------------
def calcular_drivers(serie: dict) -> dict:
    frec, cmed = {}, {}
    for k, prest in serie["prestaciones"].items():
        frec[k] = prest / serie["beneficiarios"][k]
        cmed[k] = serie["costo"][k] * 1000 / prest
    return {"frec": frec, "cmed": cmed}


def detectar_anomalias(valores: dict) -> dict:
    yoy = {(a, m): valores[(a, m)] / valores[(a - 1, m)] - 1
        for (a, m) in valores if (a - 1, m) in valores}
    mediana = statistics.median(yoy.values())
    mad = statistics.median(abs(v - mediana) for v in yoy.values()) * 1.4826 or 1e-9
    z = {k: (v - mediana) / mad for k, v in yoy.items()}

    # Clasificación en orden cronológico: anomalía, rebote o normal
    estado = {}
    for (a, m) in sorted(yoy):
        alerta = abs(z[(a, m)]) > UMBRAL_Z and abs(yoy[(a, m)] - mediana) > UMBRAL_DESVIO
        if alerta and estado.get((a - 1, m)) == "anomalia" and (a - 2, m) in valores:
            crec_2_anios = (valores[(a, m)] / valores[(a - 2, m)]) ** 0.5 - 1
            estado[(a, m)] = "rebote" if abs(crec_2_anios - mediana) <= UMBRAL_DESVIO else "anomalia"
        else:
            estado[(a, m)] = "anomalia" if alerta else "normal"

    normales = {k: v for k, v in yoy.items() if estado[k] == "normal"}
    yoy_por_anio = {a: statistics.median([v for (aa, _), v in normales.items() if aa == a])
                    for a in sorted({a for a, _ in normales})}
    historicas = [(a, m, yoy[(a, m)], z[(a, m)]) for (a, m) in sorted(yoy) if a < 2026 and estado[(a, m)] == "anomalia"]

    meses_2026 = {}
    for m in MESES:
        if (2026, m) not in valores:
            meses_2026[m] = {"yoy": None, "z": None, "alerta": "sin_dato"}
        else:
            e = estado[(2026, m)]
            meses_2026[m] = {"yoy": yoy[(2026, m)], "z": z[(2026, m)],
                            "alerta": {"anomalia": "ANOMALIA", "rebote": "rebote (2025 anómalo)"}.get(e, "")}
    return {"meses": meses_2026, "estado": estado, "yoy_tipico": statistics.median(normales.values()),
            "yoy_por_anio": yoy_por_anio, "historicas": historicas}


analisis = {}
for id_macro, serie in datos["macro"].items():
    drv = calcular_drivers(serie)
    analisis[id_macro] = {"drivers": drv,
                        "frec": detectar_anomalias(drv["frec"]),
                        "cmed": detectar_anomalias(drv["cmed"])}


def fmt(v, patron):
    return "  -  " if v is None else format(v, patron)


def tabla_para_llm() -> str:
    bloques = []
    for id_macro, a in analisis.items():
        d = a["drivers"]
        filas = [f"ID: {id_macro}"]
        for k in ("frec", "cmed"):
            por_anio = " | ".join(f"{anio}{' (ene-' + NOMBRE_MES[ULTIMO_MES_CERRADO_2026] + ')' if anio == 2026 else ''} {v:+.1%}"
                                for anio, v in a[k]["yoy_por_anio"].items())
            hist = ", ".join(f"{NOMBRE_MES[m]}-{an} {y:+.0%} (z {zz:+.0f})" for an, m, y, zz in a[k]["historicas"]) or "ninguna"
            filas.append(f"{NOMBRE_DRIVER[k]}: variación típica total {a[k]['yoy_tipico']:+.1%} | por año: {por_anio} "
                        f"| anomalías históricas 2024-2025: {hist}")
        filas.append("mes 2026 | frec | YoY frec | z frec | alerta frec || costo medio | YoY cmed | z cmed | alerta cmed")
        for m in MESES:
            f, c = a["frec"]["meses"][m], a["cmed"]["meses"][m]
            filas.append(
                f"{m:>2} {NOMBRE_MES[m]} | {fmt(d['frec'].get((2026, m)), '.4f')} | {fmt(f['yoy'], '+.1%')} | "
                f"{fmt(f['z'], '+.1f')} | {f['alerta']} || {fmt(d['cmed'].get((2026, m)), ',.1f')} | "
                f"{fmt(c['yoy'], '+.1%')} | {fmt(c['z'], '+.1f')} | {c['alerta']}")
        bloques.append("\n".join(filas))
    return "\n\n".join(bloques)


tabla_drivers = tabla_para_llm()

# ---------------------------------------------------------------------------
# MODELO
# ---------------------------------------------------------------------------
modelo = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")  # cambia el modelo si se agota la cuota

# ---------------------------------------------------------------------------
# PASO 1 (LLM): tendencia por año, crecimiento, tratamientos y justificación
# ---------------------------------------------------------------------------
plantilla_analisis = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_INSTRUCTION),
    ("human", """Vamos a proyectar el cierre 2026 y el año 2027 usando como base el mismo mes de 2026, driver por driver.
Analiza cada ID (división|plan|tipo de prestación) revisando sus dos drivers EN ESTE ORDEN:
1) frecuencia: prestaciones por beneficiario.
2) costo_medio: costo promedio por prestación.

Para cada driver tienes la variación típica total y POR AÑO (2024, 2025, 2026), y las anomalías históricas.
Las alertas de 2026 ya vienen calculadas (z robusto de la variación vs el mismo mes del año anterior,
|z| > {umbral_z} y desvío > {umbral_desvio:.0%}). "rebote" significa que el mes es normal y solo se ve raro porque el
mismo mes de 2025 fue anómalo: NO lo trates. Los meses "sin_dato" se proyectan automáticamente, no los incluyas.

Para cada mes con ANOMALIA elige un tratamiento:
- normalizar: usar el mismo mes del último año normal x variación típica. Conserva estacionalidad.
Para eventos puntuales (brotes, cierres temporales).
- reemplazar_promedio: promedio de los meses normales de 2026. Para costo medio (ej. compras no recurrentes).
No usar para frecuencia.
- excluir: interpolar con los meses vecinos normales.
- mantener: no es una anomalía real y debe seguir en la base.

Crecimiento 2027 (decimal, entre -{crec_max} y {crec_max}) mirando la variación POR AÑO:
si la tendencia acelera o desacelera, proyecta en línea con el último año; si es estable, usa la típica.
- frecuencia: crecimiento esperado de prestaciones por beneficiario.
- costo_medio: crecimiento REAL por sobre el IPC (el IPC 2027 de {ipc:.1%} se agrega aparte).
Réstale el IPC histórico (~{ipc_hist:.1%}) a la variación del costo medio.

Responde SOLO con 2 líneas por ID (una por driver), sin encabezado ni texto adicional, con este formato exacto:
ID;driver;tendencia;crecimiento_2027;tratamientos;motivo_tratamientos;justificacion_crecimiento
- driver: frecuencia o costo_medio
- tendencia: creciente, estable, decreciente, acelerando o desacelerando
- tratamientos: lista mes:tratamiento separada por comas (ej: 6:normalizar,7:normalizar), o - si no hay
- motivo_tratamientos: por qué se trataron esos meses (o "sin anomalías")
- justificacion_crecimiento: por qué ese crecimiento, citando la variación por año. Máximo 25 palabras.

Datos:
{tabla}"""),
])


# ---------------------------------------------------------------------------
# PASO 2 (Python): aplicar tratamientos, proyectar, puente, subgrupos y justificación
# ---------------------------------------------------------------------------
SIN_DECISION = {"tendencia": "s/i", "crecimiento": 0.0, "tratamientos": {},
                "motivo": "sin decisión del modelo", "justificacion": "sin decisión del modelo: crecimiento 0"}


def leer_decisiones(respuesta_llm: str) -> dict:
    clave_driver = {"frecuencia": "frec", "costo_medio": "cmed"}
    decisiones = {}
    for linea in respuesta_llm.strip().splitlines():
        p = [x.strip() for x in linea.split(";")]
        if len(p) < 7 or p[0] not in analisis or p[1] not in clave_driver:
            continue
        tratamientos = {}
        if p[4] != "-":
            for item in p[4].split(","):
                mes, _, trat = item.partition(":")
                if mes.strip().isdigit():
                    tratamientos[int(mes)] = trat.strip()
        try:
            crec = max(-CREC_MAX, min(CREC_MAX, float(p[3])))
        except ValueError:
            crec = 0.0
        decisiones.setdefault(p[0], {})[clave_driver[p[1]]] = {
            "tendencia": p[2], "crecimiento": crec, "tratamientos": tratamientos,
            "motivo": p[5], "justificacion": "; ".join(p[6:])}
    return decisiones


def base_2026(valores: dict, det: dict, tratamientos: dict):
    """Driver mensual 2026 sin anomalías. Devuelve (base, tratamiento por mes, año de referencia por mes)."""
    trat = {m: t for m, t in tratamientos.items() if t != "mantener" and det["meses"][m]["alerta"] != "sin_dato"}
    for m, info in det["meses"].items():
        if info["alerta"] == "sin_dato":
            trat[m] = "proyectar"                 # mes abierto de 2026
        elif info["alerta"] == "ANOMALIA" and m not in tratamientos:
            trat[m] = "normalizar"                # alerta sin decisión del modelo
    normales = [valores[(2026, m)] for m in MESES if m not in trat and (2026, m) in valores]
    base, referencia = {}, {}
    for m in MESES:
        t = trat.get(m)
        if t is None:
            base[m] = valores[(2026, m)]
        elif t == "reemplazar_promedio":
            base[m] = statistics.mean(normales)
        elif t == "excluir":
            base[m] = None
        else:  # normalizar o proyectar: último año normal de ese mes x variación típica
            anio_ref = next(a for a in (2025, 2024, 2023)
                            if (a, m) in valores and det["estado"].get((a, m), "normal") != "anomalia")
            referencia[m] = anio_ref
            base[m] = valores[(anio_ref, m)] * (1 + det["yoy_tipico"]) ** (2026 - anio_ref)
    for m in MESES:   # excluir: interpolar con los vecinos válidos
        if base[m] is None:
            prev = next((base[k] for k in range(m - 1, 0, -1) if base[k] is not None), None)
            sig = next((base[k] for k in range(m + 1, 13) if base[k] is not None), None)
            base[m] = statistics.mean([v for v in (prev, sig) if v is not None])
    return base, trat, referencia


# ---------------------------------------------------------------------------
# JUSTIFICACIÓN EN LENGUAJE SIMPLE (una frase corta por decisión, con los % aplicados)
# ---------------------------------------------------------------------------
MES_LARGO = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
            "septiembre", "octubre", "noviembre", "diciembre"]
PALABRA = {"frec": "uso (atenciones por beneficiario)", "cmed": "precio promedio por atención"}
TENDENCIA_SIMPLE = {"creciente": "viene subiendo", "decreciente": "viene bajando",
                    "acelerando": "sube cada año más rápido", "desacelerando": "sube cada año más lento"}


def tendencia_simple(tendencia: str, tipica: float) -> str:
    if tendencia == "estable":   # estable = ritmo parejo; si ese ritmo es alza, se dice
        return "sube a un ritmo parejo cada año" if tipica > 0.01 else "se mantiene estable"
    return TENDENCIA_SIMPLE.get(tendencia, tendencia)


def pct(v: float) -> str:
    return f"{v:+.1%}".replace(".", ",")


def explicar_correccion(k: str, m: int, trat: dict, ref: dict, dec: dict, a_k: dict):
    """Frase de por qué se corrigió un mes anómalo de 2026, o None si se usó el dato real."""
    t = trat.get(m)
    if t in (None, "proyectar"):
        return None
    info = a_k["meses"][m]
    causa = (f"El {PALABRA[k]} de {MES_LARGO[m]} 2026 fue anormal ({pct(info['yoy'])} vs {MES_LARGO[m]} 2025, "
            f"{dec['motivo']})")
    if t == "normalizar":
        return f"{causa}; se usó {MES_LARGO[m]} {ref[m]} más su alza habitual ({pct(a_k['yoy_tipico'])} al año)."
    if t == "reemplazar_promedio":
        return f"{causa}; se usó el promedio de los meses normales de 2026."
    return f"{causa}; se usó el promedio de los meses vecinos."


def explicar_estimacion(m: int, refs: dict, a: dict) -> str:
    """Frase de cómo se estimó un mes de 2026 que aún no cierra."""
    rf, rc = refs["frec"][m], refs["cmed"][m]
    origen = (f"{MES_LARGO[m]} {rf}" if rf == rc
            else f"el uso de {MES_LARGO[m]} {rf} y el precio de {MES_LARGO[m]} {rc}")
    aviso = "".join(f" Se usó {r} porque {MES_LARGO[m]} 2025 fue anormal en {PALABRA[k].split(' (')[0]}."
                    for k, r in (("frec", rf), ("cmed", rc)) if r != 2025)
    return (f"{MES_LARGO[m].capitalize()} 2026 aún no cierra: se estimó con {origen}, más el alza habitual de uso "
            f"({pct(a['frec']['yoy_tipico'])}) y de precio ({pct(a['cmed']['yoy_tipico'])}).{aviso}")


def calcular_proyeccion(respuesta_llm: str) -> dict:
    decisiones = leer_decisiones(respuesta_llm)
    resumen, puentes, tratados, historicas, filas_csv, filas_sub = [], [], [], [], [], []
    decisiones_txt = []
    total = {}

    for id_macro, a in analisis.items():
        serie, drv = datos["macro"][id_macro], a["drivers"]
        dec = {k: decisiones.get(id_macro, {}).get(k, SIN_DECISION) for k in ("frec", "cmed")}

        bases, trats, refs = {}, {}, {}
        for k in ("frec", "cmed"):
            bases[k], trats[k], refs[k] = base_2026(drv[k], a[k], dec[k]["tratamientos"])
            for m, t in sorted(trats[k].items()):
                motivo = "mes 2026 sin cierre" if t == "proyectar" else dec[k]["motivo"]
                origen = f" desde {NOMBRE_MES[m]}-{refs[k][m]}" if m in refs[k] else ""
                tratados.append(f"{id_macro} | {NOMBRE_DRIVER[k]} | {NOMBRE_MES[m]} 2026 | {t}{origen} | {motivo}")
            for an, m, y, zz in a[k]["historicas"]:
                historicas.append(f"{id_macro} | {NOMBRE_DRIVER[k]} | {NOMBRE_MES[m]}-{an} | YoY {y:+.0%} | z {zz:+.0f}")
        frec_b, cmed_b = bases["frec"], bases["cmed"]

        # Bitácora de decisiones por driver (para el informe)
        for k in ("frec", "cmed"):
            por_anio = ", ".join(f"{an} {v:+.1%}" for an, v in a[k]["yoy_por_anio"].items())
            trat_txt = ", ".join(f"{NOMBRE_MES[m]}: {t}" for m, t in sorted(trats[k].items()) if t != "proyectar") or "ninguno"
            alertas = ", ".join(f"{NOMBRE_MES[m]} ({i['alerta']})" for m, i in a[k]["meses"].items()
                                if i["alerta"] not in ("", "sin_dato")) or "ninguna"
            crec_txt = f"{dec[k]['crecimiento']:+.1%}" + (f" real + IPC {IPC_2027:.1%}" if k == "cmed" else "")
            decisiones_txt.append(
                f"{id_macro} | {NOMBRE_DRIVER[k]} | variación por año: {por_anio} | típica {a[k]['yoy_tipico']:+.1%} "
                f"| tendencia: {dec[k]['tendencia']} | crecimiento 2027: {crec_txt} | alertas 2026: {alertas} "
                f"| tratamientos: {trat_txt} | motivo: {dec[k]['motivo']} | justificación: {dec[k]['justificacion']}")

        b26 = {m: serie["beneficiarios"][(2026, m)] for m in MESES}
        b27 = {m: serie["beneficiarios"][(2027, m)] for m in MESES}
        g_f, g_c = dec["frec"]["crecimiento"], dec["cmed"]["crecimiento"]
        cerrado = {m: (2026, m) in serie["costo"] for m in MESES}

        # --- CIERRE 2026: real en meses cerrados + proyección en meses abiertos ---
        prest26 = {m: serie["prestaciones"][(2026, m)] if cerrado[m] else b26[m] * frec_b[m] for m in MESES}
        costo26 = {m: serie["costo"][(2026, m)] if cerrado[m] else b26[m] * frec_b[m] * cmed_b[m] / 1000 for m in MESES}
        real_26 = sum(costo26[m] for m in MESES if cerrado[m])
        estimado_26 = sum(costo26[m] for m in MESES if not cerrado[m])
        cierre_26 = real_26 + estimado_26

        # --- 2027 con puente secuencial, en el orden de los drivers ---
        base = sum(b26[m] * frec_b[m] * cmed_b[m] / 1000 for m in MESES)
        p_cart = sum(b27[m] * frec_b[m] * cmed_b[m] / 1000 for m in MESES)
        p_frec = sum(b27[m] * frec_b[m] * (1 + g_f) * cmed_b[m] / 1000 for m in MESES)
        p_ipc = p_frec * (1 + IPC_2027)
        proy = p_ipc * (1 + g_c)
        puentes.append(
            f"{id_macro} | cierre 2026 {cierre_26:,.0f} | efecto normalización anomalías {base - cierre_26:+,.0f} "
            f"| base 2026 normalizada {base:,.0f} | efecto cartera {p_cart - base:+,.0f} "
            f"| efecto frecuencia {p_frec - p_cart:+,.0f} | efecto IPC {p_ipc - p_frec:+,.0f} "
            f"| efecto costo medio real {proy - p_ipc:+,.0f} | proyección 2027 {proy:,.0f}")
        resumen.append(
            f"{id_macro} | frecuencia: {dec['frec']['tendencia']}, crec. {g_f:+.1%} ({dec['frec']['justificacion']}) "
            f"| costo medio: {dec['cmed']['tendencia']}, crec. real {g_c:+.1%} + IPC {IPC_2027:.1%} ({dec['cmed']['justificacion']}) "
            f"| real 2026 ene-{NOMBRE_MES[ULTIMO_MES_CERRADO_2026]} {real_26:,.0f} | proyectado resto 2026 {estimado_26:,.0f} "
            f"| cierre 2026 {cierre_26:,.0f} | proy 2027 {proy:,.0f} | var vs cierre 2026 {proy / cierre_26 - 1:+.1%}")
        for k, v in (("real", real_26), ("estimado", estimado_26), ("cierre", cierre_26), ("proy", proy)):
            total[k] = total.get(k, 0) + v

        # --- Bajada mensual a subgrupos (ID 5 campos) + justificación por fila ---
        subgrupos = [s for s in datos["detalle"] if s["id_detalle"].startswith(id_macro + "|")]
        anual_sub = {s["id_detalle"]: {"c26": 0, "p27": 0, "c27": 0} for s in subgrupos}
        for m in MESES:
            prest27 = b27[m] * frec_b[m] * (1 + g_f)
            costo27 = prest27 * cmed_b[m] * (1 + IPC_2027) * (1 + g_c) / 1000
            # Justificación corta y en lenguaje simple
            correcciones = [c for c in (explicar_correccion(k, m, trats[k], refs[k], dec[k], a[k]) for k in ("frec", "cmed")) if c]
            if not cerrado[m]:
                just_26 = explicar_estimacion(m, refs, a)
                base_txt = f"Base: {MES_LARGO[m]} 2026 estimado, porque aún no cierra."
            elif correcciones:
                just_26 = "Dato real. " + " ".join(correcciones).replace("se usó", "para proyectar 2027 se usó")
                base_txt = f"Base: {MES_LARGO[m]} 2026 corregido. " + " ".join(correcciones)
            else:
                just_26 = "Dato real."
                base_txt = f"Base: {MES_LARGO[m]} 2026 real (mes normal)."
            factor_cart = b27[m] / b26[m] - 1
            var_total = costo27 / costo26[m] - 1
            just_27 = (f"{base_txt} Se aplica: {pct(factor_cart)} por {'más' if factor_cart >= 0 else 'menos'} beneficiarios, "
                    f"{pct(g_f)} de uso (el uso {tendencia_simple(dec['frec']['tendencia'], a['frec']['yoy_tipico'])}), "
                    f"{pct(IPC_2027)} de IPC y {pct(g_c)} de precio por sobre el IPC "
                    f"(el precio {tendencia_simple(dec['cmed']['tendencia'], a['cmed']['yoy_tipico'])}). "
                    f"Resultado: {pct(var_total)} vs {MES_LARGO[m]} 2026"
                    + (", variación grande porque el mes base 2026 fue anormal." if correcciones and abs(var_total) > 0.15 else "."))
            # Columnas de diagnóstico del mes 2026 (alerta) y de decisión 2027 (tendencia, crecimiento, factores)
            diag = {}
            for k in ("frec", "cmed"):
                mi = a[k]["meses"][m]
                diag[f"alerta_{k}_2026"] = mi["alerta"] or "normal"
                diag[f"yoy_{k}_2026"] = round(mi["yoy"], 4) if mi["yoy"] is not None else ""
                diag[f"z_{k}_2026"] = round(mi["z"], 2) if mi["z"] is not None else ""
            decision = {
                "base_trat_frec": trats["frec"].get(m, ""), "anio_ref_frec": refs["frec"].get(m, ""),
                "frec_base_2026": round(frec_b[m], 5), "tendencia_frec": dec["frec"]["tendencia"],
                "tipica_frec": round(a["frec"]["yoy_tipico"], 4), "crec_frec_2027": round(g_f, 4),
                "base_trat_cmed": trats["cmed"].get(m, ""), "anio_ref_cmed": refs["cmed"].get(m, ""),
                "cmed_base_2026": round(cmed_b[m], 3), "tendencia_cmed": dec["cmed"]["tendencia"],
                "tipica_cmed": round(a["cmed"]["yoy_tipico"], 4), "crec_real_cmed_2027": round(g_c, 4),
                "factor_cartera": round(b27[m] / b26[m], 4), "factor_frec": round(1 + g_f, 4),
                "factor_ipc": round(1 + IPC_2027, 4), "factor_real_cmed": round(1 + g_c, 4),
            }
            for s in subgrupos:
                p26, c26 = prest26[m] * s["peso_prest"], costo26[m] * s["peso_costo"]
                p27, c27 = prest27 * s["peso_prest"], costo27 * s["peso_costo"]
                comun = {"id_macro": id_macro, "id_detalle": s["id_detalle"], "mes": m, **diag}
                filas_csv.append({**comun, "anio": 2026, "tipo": "real" if cerrado[m] else "proyectado",
                                "beneficiarios_macro": b26[m],
                                  "prestaciones": round(p26), "costo_medio": round(c26 * 1000 / p26, 2),
                                "costo": round(c26, 2), "factor_vs_2026": "", "justificacion": just_26})
                filas_csv.append({**comun, **decision, "anio": 2027, "tipo": "proyectado",
                                "beneficiarios_macro": b27[m],
                                  "prestaciones": round(p27), "costo_medio": round(c27 * 1000 / p27, 2),
                                "costo": round(c27, 2), "factor_vs_2026": round(c27 / c26, 4), "justificacion": just_27})
                acc = anual_sub[s["id_detalle"]]
                acc["c26"] += c26; acc["p27"] += p27; acc["c27"] += c27
        for id_det, acc in anual_sub.items():
            filas_sub.append(f"{id_det} | cierre 2026 {acc['c26']:,.0f} | prestaciones 2027 {acc['p27']:,.0f} "
                            f"| costo medio 2027 {acc['c27'] * 1000 / acc['p27']:,.1f} | costo 2027 {acc['c27']:,.0f} "
                            f"| var {acc['c27'] / acc['c26'] - 1:+.1%}")

    # CSV para Excel en español: separador ";" y coma decimal. Ordenado por subgrupo, año y mes.
    def coma(v):
        return str(v).replace(".", ",") if isinstance(v, float) else v
    columnas = [
        # identificación y resultado
        "id_macro", "id_detalle", "anio", "mes", "tipo", "beneficiarios_macro",
        "prestaciones", "costo_medio", "costo", "factor_vs_2026",
        # driver 1: frecuencia (diagnóstico del mes 2026 -> decisión)
        "alerta_frec_2026", "yoy_frec_2026", "z_frec_2026", "base_trat_frec", "anio_ref_frec", "frec_base_2026",
        "tendencia_frec", "tipica_frec", "crec_frec_2027",
        # driver 2: costo medio
        "alerta_cmed_2026", "yoy_cmed_2026", "z_cmed_2026", "base_trat_cmed", "anio_ref_cmed", "cmed_base_2026",
        "tendencia_cmed", "tipica_cmed", "crec_real_cmed_2027",
        # factores aplicados en 2027 y explicación
        "factor_cartera", "factor_frec", "factor_ipc", "factor_real_cmed", "justificacion",
    ]
    filas_csv.sort(key=lambda r: (r["id_detalle"], r["anio"], r["mes"]))
    with open(ARCHIVO_SALIDA, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=columnas, delimiter=";")
        w.writeheader()
        w.writerows({k: coma(r.get(k, "")) for k in columnas} for r in filas_csv)

    resumen.append(f"TOTAL | real 2026 {total['real']:,.0f} | proyectado resto 2026 {total['estimado']:,.0f} "
                f"| cierre 2026 {total['cierre']:,.0f} | proy 2027 {total['proy']:,.0f} "
                f"| var vs cierre 2026 {total['proy'] / total['cierre'] - 1:+.1%}")
    return {"decisiones": "\n".join(decisiones_txt), "resumen": "\n".join(resumen), "puente": "\n".join(puentes),
            "tratados": "\n".join(tratados) or "ninguno", "historicas": "\n".join(historicas) or "ninguna",
            "subgrupos": "\n".join(filas_sub)}


# ---------------------------------------------------------------------------
# PASO 3 (LLM): informe
# ---------------------------------------------------------------------------
plantilla_informe = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_INSTRUCTION),
    ("human", """Con estos resultados ya calculados (NO cambies ningún número; montos en millones de $), redacta un informe breve:
1. Tabla markdown "Decisiones de proyección": una fila por ID y driver con las columnas
ID | driver | variación 2024 | variación 2025 | variación 2026 | típica | tendencia | crecimiento 2027 |
alertas 2026 | tratamientos | justificación.
2. Tabla markdown resumen por macrogrupo (ID 3 campos): real 2026, proyectado resto de 2026, cierre 2026,
proyección 2027 y variación vs cierre 2026.
3. Tabla markdown del puente por macrogrupo: cierre 2026 -> normalización de anomalías -> base 2026 normalizada
-> cartera -> frecuencia -> IPC -> costo medio real -> 2027.
4. Tabla markdown de los meses 2026 tratados (sin incluir los "proyectar"): ID, driver, mes, tratamiento, origen y motivo.
5. Tabla markdown de anomalías históricas 2024-2025 detectadas.
6. Tabla markdown por subgrupo (ID 5 campos).
7. Máximo 4 viñetas de conclusiones: qué driver explica la variación y qué riesgos revisar. Sin introducción.

Decisiones:
{decisiones}

Resumen:
{resumen}

Puente:
{puente}

Meses tratados:
{tratados}

Anomalías históricas:
{historicas}

Subgrupos:
{subgrupos}"""),
])

# ---------------------------------------------------------------------------
# CADENA DE 3 PASOS (con fallback en el paso 3)
# ---------------------------------------------------------------------------
def informe_basico(x: dict) -> str:
    """Si falla la redacción del LLM, se entregan los resultados ya calculados en Python."""
    logger.warning("Falló el paso 3 (informe LLM). Se entrega informe sin redacción. Error: %s", x.get("error"))
    secciones = [("Decisiones de proyección", "decisiones"), ("Resumen por macrogrupo", "resumen"),
                ("Puente 2026 -> 2027", "puente"), ("Meses 2026 tratados", "tratados"),
                ("Anomalías históricas", "historicas"), ("Subgrupos", "subgrupos")]
    return "\n\n".join(f"## {titulo}\n{x[clave]}" for titulo, clave in secciones)


paso_calculo = (
    plantilla_analisis
    | modelo
    | StrOutputParser()
    | RunnableLambda(calcular_proyeccion)   # paso 2: Python. Entra texto, sale dict
)
paso_informe = (
    plantilla_informe | modelo | StrOutputParser()
).with_fallbacks([RunnableLambda(informe_basico)], exception_key="error")

cadena_tres_pasos = paso_calculo | paso_informe


# ---------------------------------------------------------------------------
# OTRAS RAMAS
# ---------------------------------------------------------------------------
cadena_anomalias = (
    ChatPromptTemplate.from_messages([
        ("system", SYSTEM_INSTRUCTION),
        ("human", """Responde la solicitud usando SOLO la tabla de drivers. NO proyectes ni inventes números.
Explica en lenguaje simple qué meses de 2026 tienen ANOMALIA, en qué driver (frecuencia o costo medio),
cuánto se desvían y qué podría explicarlas. Ignora los meses "rebote" y "sin_dato".

Solicitud: {mensaje}

Datos:
{tabla}"""),
    ])
    | modelo
    | StrOutputParser()
)

cadena_consulta = (
    ChatPromptTemplate.from_messages([
        ("system", SYSTEM_INSTRUCTION),
        ("human", """Responde esta consulta sobre la metodología de proyección de forma breve y clara.
Supuestos del modelo:
- Costo = beneficiarios x frecuencia x costo medio.
- Base: mismo mes de 2026; datos reales hasta {ultimo_mes}, el resto de 2026 se proyecta.
- Anomalías: z robusto > {umbral_z} y desvío > {umbral_desvio:.0%} vs el mismo mes del año anterior.
- IPC 2027: {ipc:.1%}. El costo medio crece IPC + crecimiento real.
- Crecimientos 2027 acotados entre -{crec_max:.0%} y +{crec_max:.0%}.

Consulta: {mensaje}"""),
    ])
    | modelo
    | StrOutputParser()
)


# ---------------------------------------------------------------------------
# ENRUTAMIENTO
# ---------------------------------------------------------------------------
ETIQUETAS = {"proyeccion", "anomalias", "consulta"}

plantilla_clasificacion = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_INSTRUCTION),
    ("human", """Clasifica la solicitud en una sola palabra:
- proyeccion: pide proyectar, calcular el cierre 2026, el presupuesto 2027 o el informe completo.
- anomalias: pregunta por meses atípicos, alertas o datos anormales, sin pedir proyección.
- consulta: pregunta sobre metodología, supuestos o conceptos (IPC, frecuencia, costo medio).
Responde solo con esa palabra.

Solicitud: {mensaje}"""),
])


def normalizar_etiqueta(texto: str) -> str:
    """Quita tildes, mayúsculas y símbolos. Si la etiqueta no es válida, usa 'consulta'."""
    limpio = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    limpio = limpio.strip().lower().strip(".:*\"' ")
    if limpio not in ETIQUETAS:
        logger.warning("Clasificación no reconocida: '%s'. Se usa 'consulta'.", texto)
        return "consulta"
    return limpio


paso_clasificacion = (
    plantilla_clasificacion
    | modelo
    | StrOutputParser()
    | RunnableLambda(normalizar_etiqueta)
)

bifurcacion = RunnableBranch(
    (lambda x: x["clasificacion"] == "proyeccion", cadena_tres_pasos),
    (lambda x: x["clasificacion"] == "anomalias", cadena_anomalias),
    cadena_consulta,   # por defecto: la ruta más barata
)

cadena_con_enrutamiento = (
    RunnablePassthrough.assign(clasificacion=paso_clasificacion)
    | bifurcacion
)


# ---------------------------------------------------------------------------
# FALLBACK GENERAL Y EJECUCIÓN SEGURA
# ---------------------------------------------------------------------------
def fallback_con_log(x):
    logger.warning("Cadena principal falló. Activando respuesta genérica. Error: %s", x.get("error"))
    return "No fue posible generar la respuesta en este momento. El equipo de FP&A revisará la solicitud."


cadena_robusta = cadena_con_enrutamiento.with_fallbacks(
    [RunnableLambda(fallback_con_log)], exception_key="error"
)

PARAMETROS = {
    "tabla": tabla_drivers, "umbral_z": UMBRAL_Z, "umbral_desvio": UMBRAL_DESVIO,
    "crec_max": CREC_MAX, "ipc": IPC_2027, "ipc_hist": IPC_HISTORICO,
    "ultimo_mes": MES_LARGO[ULTIMO_MES_CERRADO_2026],
}


def procesar_mensaje_seguro(cadena, mensaje: str) -> str:
    try:
        return cadena.invoke({"mensaje": mensaje, **PARAMETROS})
    except Exception as error:
        logger.error("Error procesando mensaje: %s", error)
        return "No pudimos procesar tu solicitud en este momento. Intenta de nuevo más tarde."


if __name__ == "__main__":
    mensaje = "Necesito la proyección del cierre 2026 y el presupuesto 2027 por macrogrupo."

    print(procesar_mensaje_seguro(cadena_robusta, mensaje))
    print(f"\n(Si la ruta fue 'proyeccion', el detalle mensual quedó en: {ARCHIVO_SALIDA})")