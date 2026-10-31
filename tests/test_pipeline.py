"""Prueba de punta a punta del pipeline Medallion contra el sitio simulado."""

from __future__ import annotations

import json

import yaml

from riopaila_qa.scraping import STAGES, run_pipeline


def test_pipeline_end_to_end(test_settings):
    events: list[tuple[str, str]] = []
    manifest = run_pipeline(test_settings, on_event=lambda s, st, m, d: events.append((s, st)))
    paths = test_settings.paths

    # Todas las etapas se anuncian y se cierran, en orden.
    done = [s for s, st in events if st == "done"]
    assert done == STAGES

    # robots.txt: /privado/ no se toca; el sitemap de usuarios se omite (Ley 1581).
    assert manifest["descubrir"]["descartes"]["robots_disallow"] == 1
    assert any("users" in s for s in manifest["descubrir"]["sitemaps_omitidos"])
    assert manifest["descubrir"]["descartes"]["patrones_excluidos"] == 1  # /tag/algo/

    # Bronze: HTML crudo + JSONL de captura con hash.
    captures = [json.loads(line) for line in paths.captures.read_text().splitlines()]
    assert all(c["hash"] and c["status"] == 200 for c in captures)

    # Deduplicación: copia exacta y página corta descartadas; footer eliminado.
    assert manifest["deduplicar"]["duplicados_exactos"] == 1
    assert manifest["deduplicar"]["muy_cortas"] == 1
    corpus = [json.loads(line) for line in paths.corpus.read_text().splitlines()]
    assert len(corpus) == 3
    assert all("Línea ética" not in d["markdown"] for d in corpus)
    assert all("epilepsia" not in d["markdown"] for d in corpus)

    # Gold: frontmatter con metadatos obligatorios y noticia clasificada.
    md_files = sorted(paths.gold_pages.glob("*.md"))
    assert len(md_files) == 3
    front = yaml.safe_load(md_files[0].read_text().split("---")[1])
    for key in ("url", "titulo", "seccion", "fecha_captura", "hash", "tokens"):
        assert key in front
    assert {d["tipo"] for d in corpus} == {"pagina", "noticia"}
    assert paths.knowledge_base.exists()
    chunks = [json.loads(line) for line in paths.chunks.read_text().splitlines()]
    assert chunks and all(c["url"] and c["texto"] for c in chunks)
    assert manifest["enriquecer"]["chunks"] == len(chunks)
    assert paths.manifest.exists()


def test_offline_reprocess_uses_bronze(test_settings):
    run_pipeline(test_settings)
    manifest = run_pipeline(test_settings, offline=True)
    assert manifest["extraer"]["peticiones_http"] == 0
    assert manifest["enriquecer"]["documentos"] == 3


def test_live_demo_with_small_budget_keeps_full_corpus(test_settings):
    run_pipeline(test_settings)
    manifest = run_pipeline(test_settings, max_pages=1, refresh=True)
    # Solo una petición de página nueva (más robots y sitemaps); el corpus sigue completo.
    assert manifest["extraer"]["desde_cache"] == 4
    assert manifest["enriquecer"]["documentos"] == 3


def test_offline_network_does_not_wipe_corpus(test_settings):
    import dataclasses

    import pytest

    run_pipeline(test_settings)
    before = test_settings.paths.corpus.read_text()
    dead = dataclasses.replace(test_settings.scraper, base_url="http://127.0.0.1:9", timeout_s=0.5)
    broken = dataclasses.replace(test_settings, scraper=dead)
    with pytest.raises(RuntimeError):
        run_pipeline(broken)
    assert test_settings.paths.corpus.read_text() == before
