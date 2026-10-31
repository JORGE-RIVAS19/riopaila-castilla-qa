"""Corre la batería de 24 preguntas contra el Q&A y guarda los resultados.

Uso:
    uv run python scripts/run_eval.py                              # prompt v3 (producción)
    uv run python scripts/run_eval.py --prompt qa_v1_zero_shot     # línea base para comparar
    uv run python scripts/run_eval.py --provider gemini --mode completo
"""

from __future__ import annotations

import argparse
import sys

from riopaila_qa.config import get_settings
from riopaila_qa.corpus import CorpusStore
from riopaila_qa.evaluation import run_evaluation, to_markdown
from riopaila_qa.prompts import QA_VARIANTS


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluación del sistema Q&A")
    parser.add_argument("--prompt", default="qa_v3_xml_sandwich", choices=list(QA_VARIANTS))
    parser.add_argument("--provider", default=None, choices=["ollama", "gemini", "openai"])
    parser.add_argument("--model", default=None)
    parser.add_argument("--mode", default="auto", choices=["auto", "completo", "bm25"])
    parser.add_argument("--limit", type=int, default=None, help="solo las primeras N preguntas")
    parser.add_argument("--pause", type=float, default=None, help="segundos entre preguntas (API: 6 por defecto)")
    args = parser.parse_args()

    settings = get_settings()
    provider = args.provider or settings.llm.provider
    store = CorpusStore(settings.paths)
    if not store.available:
        print("❌ No hay corpus Gold. Ejecuta primero: uv run python scripts/scrape_empresa.py")
        return 1

    def progress(i: int, n: int, row: dict) -> None:
        mark = "✅" if row.get("exito_auto") else "❌"
        print(f"{mark} {i:>2}/{n} [{row['id']}] {row['pregunta'][:70]} · {row.get('latencia_s', 0)} s")
        if str(row.get("respuesta", "")).startswith("ERROR"):
            print(f"      ↳ {row['respuesta'][:160]}")

    rows, summary, out = run_evaluation(
        store,
        settings.paths,
        settings.llm,
        args.prompt,
        args.provider,
        args.model,
        args.mode,
        limit=args.limit,
        on_progress=progress,
        pause_s=args.pause if args.pause is not None else (0.0 if provider == "ollama" else 6.0),
        on_wait=lambda msg: print(f"      ⏳ {msg}"),
    )
    md = settings.paths.root / "docs" / "evaluacion" / f"{out.stem}.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(to_markdown(summary, rows), encoding="utf-8")
    print("\n📊 Resumen")
    for key, value in summary.items():
        print(f"   {key:<32} {value}")
    print(f"\nResultados: {out}\nTabla para el informe: {md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
