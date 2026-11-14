"""Verificador de cifras: detecta aritmética hecha por el LLM fuera de las herramientas."""

from riopaila_qa.agent.numeros import cifras_sin_respaldo, numeros

EVIDENCIA = [
    '{"indicador": "utilidad_neta", "anio": 2022, "valor": 93241, "unidad": "millones_cop"}',
    '{"indicador": "utilidad_neta", "anio": 2023, "valor": 63000, "calificador": "mas_de"}',
    '{"indicador": "produccion_alcohol_carburante", "valor": 11.5, "periodo": "S1"}',
    '{"diferencia": -32.4, "variacion_pct": -32.43}',
]


def test_formatos_colombiano_e_ingles():
    vals = dict(numeros("93.241 millones, 11,5 litros, 1.600.000 y 8,4 %"))
    assert 93241 in vals["93.241"] and 11.5 in vals["11,5"] and 1600000 in vals["1.600.000"]


def test_cifras_de_las_herramientas_pasan():
    texto = "En 2022 la utilidad fue de 93.241 millones de COP y en 2023 de más de 63.000 [1]. S1 2023: 11,5."
    assert cifras_sin_respaldo(texto, EVIDENCIA) == []


def test_resta_mental_se_detecta():
    texto = "La utilidad bajó en 30.241 millones de COP entre 2022 y 2023."
    assert cifras_sin_respaldo(texto, EVIDENCIA) == ["30.241"]


def test_redondeo_de_porcentajes_y_urls_se_ignoran():
    texto = "Cayó un 32,4 % (https://www.riopaila-castilla.com/nota-2023-55555/) según 3 fuentes."
    assert cifras_sin_respaldo(texto, EVIDENCIA) == []


def test_fechas_y_anios_no_son_cifras():
    assert cifras_sin_respaldo("Hoy, 13 de noviembre de 2026, los datos de 2023 siguen vigentes.", EVIDENCIA) == []
