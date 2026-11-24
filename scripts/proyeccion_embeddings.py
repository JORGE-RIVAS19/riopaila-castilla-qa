"""Proyección 2D de los embeddings (UMAP y t-SNE) para diagnosticar clústeres y fallos del retrieval (ítem 2.3).

Qué mide, además del dibujo:

* **Silueta coseno** por manual en el espacio original: ¿los manuales forman grupos separables?
* **Pureza kNN@10** por manual y por idioma: de los 10 vecinos de cada página, cuántos son del mismo manual o idioma.
  Si la pureza por idioma es mucho mayor que por familia de máquina, el modelo agrupa por idioma (riesgo para
  preguntas en español sobre manuales en inglés o portugués: justifica el glosario y la búsqueda híbrida).
* **Trustworthiness@10** de cada proyección: qué tanto respeta la 2D los vecinos del espacio original (1 = perfecto).

Fuentes: ``qdrant`` (vectores reales de la colección ``manuales_taller``, en el servidor) o ``tfidf`` (TF-IDF + LSA,
línea base léxica que corre en cualquier portátil).

    uv run python scripts/proyeccion_embeddings.py --fuente qdrant
    uv run python scripts/proyeccion_embeddings.py --fuente tfidf --max 2500
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from riopaila_qa.config import ROOT_DIR  # noqa: E402
from riopaila_qa.taller.config import get_taller_settings  # noqa: E402
from riopaila_qa.taller.manuales import POR_ID, PaginaManual, cargar_paginas  # noqa: E402

SALIDA = ROOT_DIR / "docs" / "evaluacion" / "proyeccion"
COLORES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
TINTA, TENUE, FONDO = "#0b0b0b", "#6b6a65", "#fcfcfb"


def _grupo(p: PaginaManual) -> str:
    """Grupo legible para colorear: familia + tipo de documento (máx. 8 categorías)."""
    idioma = {"es": "español", "pt": "portugués", "en": "inglés"}.get(p.idioma, p.idioma)
    if p.familia == "Tractomula":
        return "Kenworth (mulas) · inglés"
    if p.familia == "Alzadora":
        return f"Alzadora 2254 · {p.tipo} · {idioma}"
    if p.manual_id.startswith("jd6165"):
        return f"John Deere 6165J · {idioma}"
    if p.manual_id.startswith("game"):
        return f"GAME 77ATX · {idioma}"
    if p.tipo == "operador":
        return f"Case IH Puma · operador · {idioma}"
    return f"Case IH Puma · servicio · {idioma}"


def vectores_qdrant(paginas: list[PaginaManual]) -> tuple[np.ndarray, list[PaginaManual]]:
    from riopaila_qa.agent.settings import get_agent_settings
    from riopaila_qa.rag.index import get_client

    por_id = {p.id: p for p in paginas}
    client = get_client(get_agent_settings())
    alias = get_taller_settings().manuales_collection
    vecs, orden, offset = [], [], None
    while True:
        puntos, offset = client.scroll(alias, limit=512, offset=offset, with_vectors=True, with_payload=True)
        for pt in puntos:
            pid = pt.payload.get("id")
            if pid in por_id:
                vecs.append(pt.vector)
                orden.append(por_id[pid])
        if offset is None:
            break
    return np.asarray(vecs, dtype=np.float32), orden


def vectores_tfidf(paginas: list[PaginaManual], dims: int = 128) -> np.ndarray:
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer

    x = TfidfVectorizer(max_features=40000, sublinear_tf=True, min_df=2).fit_transform(
        [f"{p.titulo} {p.texto}" for p in paginas]
    )
    return TruncatedSVD(dims, random_state=28).fit_transform(x).astype(np.float32)


def pureza_knn(x: np.ndarray, etiquetas: list[str], k: int = 10) -> float:
    from sklearn.neighbors import NearestNeighbors

    nn = NearestNeighbors(n_neighbors=k + 1, metric="cosine").fit(x)
    _, idx = nn.kneighbors(x)
    eti = np.asarray(etiquetas)
    return float(np.mean([(eti[fila[1:]] == eti[fila[0]]).mean() for fila in idx]))


def dibujar(xy: np.ndarray, grupos: list[str], titulo: str, subtitulo: str, destino: Path) -> None:
    cats = [c for c, _ in Counter(grupos).most_common()][:8]
    fig, ax = plt.subplots(figsize=(11, 7.2), dpi=160, facecolor=FONDO)
    ax.set_facecolor(FONDO)
    for i, c in enumerate(cats):
        m = np.array([g == c for g in grupos])
        ax.scatter(xy[m, 0], xy[m, 1], s=9, c=COLORES[i], alpha=0.75, linewidths=0, label=f"{c} ({m.sum()})")
    ax.set_xticks([])
    ax.set_yticks([])
    for lado in ax.spines.values():
        lado.set_visible(False)
    ax.legend(
        loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False, fontsize=9, markerscale=2.2, labelcolor=TINTA
    )
    fig.text(0.02, 0.97, titulo, fontsize=15, fontweight="bold", color=TINTA, va="top")
    fig.text(0.02, 0.925, subtitulo, fontsize=10, color=TENUE, va="top")
    fig.subplots_adjust(top=0.88, left=0.02, right=0.66, bottom=0.03)
    fig.savefig(destino, facecolor=FONDO)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fuente", choices=["qdrant", "tfidf"], default="qdrant")
    ap.add_argument("--max", type=int, default=4000, help="Muestra estratificada de páginas (t-SNE es O(n log n))")
    a = ap.parse_args()

    import umap
    from sklearn.manifold import TSNE, trustworthiness
    from sklearn.metrics import silhouette_score

    paginas = cargar_paginas(get_taller_settings().paginas_jsonl)
    if not paginas:
        raise SystemExit("No hay páginas de manuales: corre scripts/preparar_manuales.py")
    if a.fuente == "qdrant":
        x, paginas = vectores_qdrant(paginas)
        nombre_fuente = "embeddings densos (Qdrant · manuales_taller)"
    else:
        x = vectores_tfidf(paginas)
        nombre_fuente = "TF-IDF + LSA 128d (línea base léxica)"
    # Muestra estratificada por manual: los manuales grandes no tapan a los planos de 2 páginas.
    rnd = random.Random(28)
    por_manual: dict[str, list[int]] = {}
    for i, p in enumerate(paginas):
        por_manual.setdefault(p.manual_id, []).append(i)
    cuota = max(30, a.max // max(len(por_manual), 1))
    idx = sorted(i for ids in por_manual.values() for i in (ids if len(ids) <= cuota else rnd.sample(ids, cuota)))
    x, paginas = x[idx], [paginas[i] for i in idx]
    x = x / np.linalg.norm(x, axis=1, keepdims=True).clip(1e-9)

    manual = [p.manual_id for p in paginas]
    idioma = [p.idioma for p in paginas]
    familia = [p.familia for p in paginas]
    grupos = [_grupo(p) for p in paginas]
    metricas = {
        "fuente": a.fuente,
        "paginas": len(paginas),
        "silueta_manual_coseno": round(float(silhouette_score(x, manual, metric="cosine")), 4),
        "pureza_knn10_manual": round(pureza_knn(x, manual), 4),
        "pureza_knn10_idioma": round(pureza_knn(x, idioma), 4),
        "pureza_knn10_familia": round(pureza_knn(x, familia), 4),
    }
    SALIDA.mkdir(parents=True, exist_ok=True)
    for nombre, modelo in [
        ("umap", umap.UMAP(n_neighbors=15, min_dist=0.1, metric="cosine", random_state=28)),
        ("tsne", TSNE(n_components=2, perplexity=30, metric="cosine", init="pca", random_state=28)),
    ]:
        xy = modelo.fit_transform(x)
        tw = trustworthiness(x, xy, n_neighbors=10, metric="cosine")
        metricas[f"trustworthiness10_{nombre}"] = round(float(tw), 4)
        dibujar(
            xy,
            grupos,
            f"{nombre.upper()} de {len(paginas)} páginas de manuales del taller",
            f"{nombre_fuente} · trustworthiness@10 = {tw:.3f} · pureza kNN@10: manual "
            f"{metricas['pureza_knn10_manual']:.2f}, idioma {metricas['pureza_knn10_idioma']:.2f}",
            SALIDA / f"{nombre}_{a.fuente}.png",
        )
        print(f"{nombre}: trustworthiness@10={tw:.3f}")
    metricas["manuales"] = {m: POR_ID[m].titulo for m in sorted(set(manual)) if m in POR_ID}
    (SALIDA / f"metricas_{a.fuente}.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps({k: v for k, v in metricas.items() if k != "manuales"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
