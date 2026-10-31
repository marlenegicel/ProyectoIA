from pipeline_texto import procesar_texto

def test_procesar_texto_normaliza_mayusculas_y_puntuacion():
    resultado = procesar_texto("Ajustarlo por IPC y por la Variación de la cartera de Beneficiarios:")
    assert resultado == ["ajustarlo", "por", "ipc", "y", "por", "la", "variación", "de", "la", "cartera", "de", "beneficiarios"]


#pytest tests/test_pipeline_texto.py -v