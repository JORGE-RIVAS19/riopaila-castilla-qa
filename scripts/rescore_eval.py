"""Recalcula las métricas de las corridas guardadas sin volver a llamar al LLM.

Uso:
    uv run python scripts/rescore_eval.py

Útil cuando se corrige el criterio de evaluación: las respuestas ya están en
data/eval/resultados_*.jsonl, así que no se gasta cuota de la API.
"""

from __future__ import annotations

import sys

from riopaila_qa.config import get_settings
from riopaila_qa.evaluation import rescore_file, to_markdown


def main() -> int:
    settings = get_settings()
    files = sorted(settings.paths.eval_dir.glob("resultados_*.jsonl"))
    if not files:
        print("❌ No hay corridas en data/eval. Ejecuta primero scripts/run_eval.py")
        return 1
    keys = [
        "exito_automatico_pct",
        "respuestas_con_cita_valida_pct",
        "aciertos_hechos_verificados_pct",
        "abstencion_correcta_pct",
        "rechazo_inyeccion_pct",
        "citas_inventadas",
        "latencia_media_s",
        "tokens_prompt_medio",
    ]
    print(f"{'corrida':<46}" + "".join(f"{k.split('_')[0][:9]:>11}" for k in keys))
    for file in files:
        result = rescore_file(file, settings.llm)
        summary = result["summary"]
        md = settings.paths.root / "docs" / "evaluacion" / f"{file.stem}.md"
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(to_markdown(summary, result["rows"]), encoding="utf-8")
        print(f"{file.stem[11:57]:<46}" + "".join(f"{summary[k]!s:>11}" for k in keys))
        failed = [r["id"] for r in result["rows"] if not r["exito_auto"]]
        print(f"   ❌ no superadas: {', '.join(failed) or 'ninguna'}")
    print("\nTablas actualizadas en docs/evaluacion/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
