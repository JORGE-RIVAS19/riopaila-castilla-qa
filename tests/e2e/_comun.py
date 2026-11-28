"""Constantes compartidas por las pruebas end-to-end."""

from __future__ import annotations

import os
from pathlib import Path

ARTEFACTOS = Path(__file__).parent / "artifacts"
DESPLEGADO = bool(os.environ.get("E2E_BASE_URL"))
EVAL_RETRIEVAL = Path(__file__).parents[2] / "docs" / "evaluacion" / "retrieval_latest.json"
