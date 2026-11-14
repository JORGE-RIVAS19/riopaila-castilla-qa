"""Verificador de cifras: el LLM no puede presentar números que no salieron de una herramienta.

La regla 3 del prompt pide usar ``comparar_cifras`` para toda aritmética, pero un prompt es solo una
petición. Este módulo la vuelve verificable: extrae los números de la respuesta y comprueba que cada
uno aparece en la evidencia del turno (resultados de herramientas o mensajes del usuario). Un número
que no está en la evidencia es, casi siempre, una resta o un porcentaje calculado "de memoria".
"""

from __future__ import annotations

import re

_URL = re.compile(r"https?://\S+")
_CITA = re.compile(r"\[\d+\]")
_FECHA = re.compile(
    r"\b\d{1,2} de (enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)",
    re.IGNORECASE,
)
_NUM = re.compile(r"(?<![\w.,])-?\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?(?![\w])|(?<![\w.,])-?\d+(?:[.,]\d+)?(?![\w])")


def _interpretaciones(token: str) -> set[float]:
    """Valores posibles de un número escrito en formato colombiano (30.241 / 11,5) o inglés (30,241 / 11.5)."""
    t = token.strip()
    out: set[float] = set()
    if "." in t and "," in t:  # el último separador es el decimal
        dec = "," if t.rfind(",") > t.rfind(".") else "."
        miles = "." if dec == "," else ","
        out.add(float(t.replace(miles, "").replace(dec, ".")))
        return out
    for sep in (".", ","):
        if sep in t:
            partes = t.split(sep)
            if len(partes) > 2 or (len(partes[-1]) == 3 and partes[0].lstrip("-") != "0"):
                out.add(float(t.replace(sep, "")))  # separador de miles
            if len(partes) == 2:
                out.add(float(t.replace(sep, ".")))  # separador decimal
            return out
    out.add(float(t))
    return out


def numeros(texto: str) -> list[tuple[str, set[float]]]:
    """Números de un texto con sus interpretaciones; ignora URLs y citas [n]."""
    limpio = _FECHA.sub(" ", _CITA.sub(" ", _URL.sub(" ", texto or "")))
    return [(m.group(0), _interpretaciones(m.group(0))) for m in _NUM.finditer(limpio)]


def _decimales(token: str) -> int:
    m = re.search(r"[.,](\d{1,2})$", token)
    return len(m.group(1)) if m else 0


def _irrelevante(token: str, valores: set[float]) -> bool:
    """Años, conteos pequeños y ordinales no son cifras de negocio."""
    if any(float(v).is_integer() and 1900 <= v <= 2100 for v in valores) and re.fullmatch(r"\d{4}", token):
        return True
    return all(float(v).is_integer() and abs(v) <= 10 for v in valores)


def cifras_sin_respaldo(respuesta: str, evidencia: list[str]) -> list[str]:
    """Números de la respuesta que no aparecen en ninguna evidencia (con tolerancia de redondeo)."""
    disponibles: set[float] = set()
    for texto in evidencia:
        for _, vals in numeros(texto):
            disponibles |= {abs(v) for v in vals}
    faltan: list[str] = []
    for token, vals in numeros(respuesta):
        if _irrelevante(token, vals):
            continue
        tol = 0.5 * 10 ** (-_decimales(token)) + 1e-9
        ok = any(abs(abs(v) - d) <= max(tol, abs(d) * 1e-9) for v in vals for d in disponibles)
        if not ok and token not in faltan:
            faltan.append(token)
    return faltan
