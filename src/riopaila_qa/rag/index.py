"""Índice vectorial en Qdrant (Clase 7): colecciones versionadas, *payload* y alias.

* **Modo embebido** (por defecto, ``QDRANT_PATH``): Qdrant corre dentro del
  proceso de Python y guarda en disco; no necesita Docker. En este modo la
  búsqueda es **exacta** (fuerza bruta), suficiente para ~640 vectores.
* **Modo servidor** (``QDRANT_URL``, p. ej. ``docker run -p 6333:6333 qdrant/qdrant``):
  la colección se crea con índice **HNSW** (``m=16``, ``ef_construct=128``) y se
  consulta con ``hnsw_ef``; ``exact=True`` permite comparar ANN contra exacto.
* **Blue/green**: cada indexación crea ``<alias>_<modelo>_<fecha>`` y el alias
  ``riopaila_chunks`` se mueve de forma atómica a la nueva colección. Si algo sale
  mal, se vuelve a apuntar el alias a la anterior sin reindexar.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from langchain_core.embeddings import Embeddings
from qdrant_client import QdrantClient
from qdrant_client import models as qm

from riopaila_qa.agent.settings import AgentSettings
from riopaila_qa.rag.documents import RagChunk

PAYLOAD_INDEXES = {
    "seccion": qm.PayloadSchemaType.KEYWORD,
    "tipo": qm.PayloadSchemaType.KEYWORD,
    "origen": qm.PayloadSchemaType.KEYWORD,
    "anio": qm.PayloadSchemaType.INTEGER,
}
HNSW = qm.HnswConfigDiff(m=16, ef_construct=128)
KEEP_COLLECTIONS = 2  # la activa (green) y la anterior (blue) para poder hacer rollback

_CLIENTS: dict[str, QdrantClient] = {}


def get_client(settings: AgentSettings) -> QdrantClient:
    """Cliente único por destino (el modo embebido bloquea la carpeta: un proceso a la vez)."""
    key = settings.qdrant_url or str(settings.qdrant_path)
    if key not in _CLIENTS:
        if settings.qdrant_url:
            _CLIENTS[key] = QdrantClient(url=settings.qdrant_url)
        else:
            settings.qdrant_path.mkdir(parents=True, exist_ok=True)
            try:
                _CLIENTS[key] = QdrantClient(path=str(settings.qdrant_path))
            except RuntimeError as exc:
                if "already accessed" not in str(exc):
                    raise
                raise QdrantOcupadoError(settings.qdrant_path) from exc
    return _CLIENTS[key]


class QdrantOcupadoError(RuntimeError):
    """El modo embebido bloquea la carpeta: otro proceso (backend viejo o build_index) la tiene abierta."""

    def __init__(self, path: object):
        super().__init__(
            f"La carpeta de Qdrant ({path}) está en uso por otro proceso: un backend anterior que sigue "
            "corriendo o build_index.py. Detén ese proceso con Ctrl+C en su terminal; si no lo encuentras, "
            "en PowerShell: Get-Process python* | Stop-Process -Force. Para varios procesos a la vez, "
            "usa Qdrant en modo servidor (QDRANT_URL)."
        )


def close_clients() -> None:
    for client in _CLIENTS.values():
        client.close()
    _CLIENTS.clear()


def point_id(chunk_id: str) -> str:
    """ID determinista: reindexar el mismo chunk sobrescribe el punto, no lo duplica."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def embed_text(chunk: RagChunk) -> str:
    """Texto que se vectoriza: título + sección + cuerpo (el título aporta mucho contexto)."""
    return f"{chunk.titulo}. Sección {chunk.seccion}.\n{chunk.texto}"


@dataclass
class IndexReport:
    collection: str
    alias: str
    points: int
    dims: int
    embed_model: str
    mode: str
    previous: str | None
    deleted: list[str]


def _stamp(name: str) -> str:
    """Marca de tiempo al final del nombre (``..._20261113193428``): ordena por antigüedad real."""
    return name.rsplit("_", 1)[-1]


def our_collections(client: QdrantClient, alias: str) -> list[str]:
    """Colecciones versionadas de este alias, de la más vieja a la más nueva."""
    names = [c.name for c in client.get_collections().collections if c.name.startswith(alias + "_")]
    return sorted(names, key=_stamp)


def resolve_alias(client: QdrantClient, alias: str) -> str | None:
    for a in client.get_aliases().aliases:
        if a.alias_name == alias:
            return a.collection_name
    return None


def build_index(
    chunks: Sequence[RagChunk],
    embeddings: Embeddings,
    dims: int,
    embed_model: str,
    settings: AgentSettings,
    batch_size: int = 32,
    on_progress: Callable[[int, int], None] | None = None,
) -> IndexReport:
    """Indexación offline: vectoriza los chunks, crea una colección nueva y mueve el alias (blue/green)."""
    client = get_client(settings)
    tag = re.sub(r"[^a-z0-9]+", "-", embed_model.lower()).strip("-")[:40]
    name = f"{settings.collection_alias}_{tag}_{datetime.now(UTC):%Y%m%d%H%M%S%f}"
    client.create_collection(
        collection_name=name,
        vectors_config=qm.VectorParams(size=dims, distance=qm.Distance.COSINE),
        hnsw_config=HNSW,
    )
    if settings.qdrant_url:  # los índices de payload solo aplican en servidor
        for field_name, schema in PAYLOAD_INDEXES.items():
            client.create_payload_index(name, field_name=field_name, field_schema=schema)

    total = len(chunks)
    for start in range(0, total, batch_size):
        batch = list(chunks[start : start + batch_size])
        vectors = embeddings.embed_documents([embed_text(c) for c in batch])
        if vectors and len(vectors[0]) != dims:
            raise ValueError(f"El modelo devolvió {len(vectors[0])} dimensiones y EMBED_DIMS={dims}")
        client.upsert(
            collection_name=name,
            points=[
                qm.PointStruct(id=point_id(c.chunk_id), vector=v, payload=c.payload())
                for c, v in zip(batch, vectors, strict=True)
            ],
        )
        if on_progress:
            on_progress(min(start + batch_size, total), total)

    previous = resolve_alias(client, settings.collection_alias)
    ops: list = []
    if previous:
        ops.append(qm.DeleteAliasOperation(delete_alias=qm.DeleteAlias(alias_name=settings.collection_alias)))
    ops.append(
        qm.CreateAliasOperation(create_alias=qm.CreateAlias(collection_name=name, alias_name=settings.collection_alias))
    )
    client.update_collection_aliases(change_aliases_operations=ops)

    # Limpieza: se conservan la activa y la anterior; las más viejas se borran.
    ours = our_collections(client, settings.collection_alias)
    deleted = []
    for old in ours[:-KEEP_COLLECTIONS]:
        client.delete_collection(old)
        deleted.append(old)
    return IndexReport(
        name,
        settings.collection_alias,
        total,
        dims,
        embed_model,
        "servidor (HNSW)" if settings.qdrant_url else "embebido (exacto)",
        previous,
        deleted,
    )


def rollback(settings: AgentSettings) -> str:
    """Vuelve a apuntar el alias a la colección anterior (blue/green)."""
    client = get_client(settings)
    current = resolve_alias(client, settings.collection_alias)
    ours = our_collections(client, settings.collection_alias)
    older = [c for c in ours if c != current and (current is None or _stamp(c) < _stamp(current))]
    if not older:
        raise RuntimeError("No hay una colección anterior para hacer rollback")
    target = older[-1]
    client.update_collection_aliases(
        change_aliases_operations=[
            qm.DeleteAliasOperation(delete_alias=qm.DeleteAlias(alias_name=settings.collection_alias)),
            qm.CreateAliasOperation(
                create_alias=qm.CreateAlias(collection_name=target, alias_name=settings.collection_alias)
            ),
        ]
    )
    return target


def index_info(settings: AgentSettings) -> dict:
    """Estado del índice para la API y la app."""
    client = get_client(settings)
    current = resolve_alias(client, settings.collection_alias)
    if not current:
        return {"disponible": False, "alias": settings.collection_alias}
    info = client.get_collection(current)
    params = info.config.params.vectors
    return {
        "disponible": True,
        "alias": settings.collection_alias,
        "coleccion": current,
        "puntos": info.points_count,
        "dimensiones": getattr(params, "size", None),
        "distancia": str(getattr(params, "distance", "")),
        "modo": "servidor (HNSW)" if settings.qdrant_url else "embebido (exacto)",
        "colecciones": our_collections(client, settings.collection_alias),
    }


def build_filter(
    seccion: str | None = None,
    tipo: str | None = None,
    anio: int | None = None,
    include_adversarial: bool = True,
) -> qm.Filter | None:
    """Filtro de *payload* (single-stage filtering: Qdrant filtra mientras recorre el índice)."""
    must: list = []
    must_not: list = []
    if seccion:
        must.append(qm.FieldCondition(key="seccion", match=qm.MatchValue(value=seccion)))
    if tipo:
        must.append(qm.FieldCondition(key="tipo", match=qm.MatchValue(value=tipo)))
    if anio:
        must.append(qm.FieldCondition(key="anio", match=qm.MatchValue(value=anio)))
    if not include_adversarial:
        must_not.append(qm.FieldCondition(key="origen", match=qm.MatchValue(value="sintetico")))
    if not must and not must_not:
        return None
    return qm.Filter(must=must or None, must_not=must_not or None)


def dense_search(
    query_vector: list[float],
    settings: AgentSettings,
    limit: int,
    query_filter: qm.Filter | None = None,
    exact: bool = False,
) -> list[tuple[RagChunk, float]]:
    """Búsqueda densa top-k por similitud coseno, con filtro de payload."""
    client = get_client(settings)
    res = client.query_points(
        collection_name=settings.collection_alias,
        query=query_vector,
        limit=limit,
        query_filter=query_filter,
        with_payload=True,
        # En modo embebido la búsqueda ya es exacta; los parámetros HNSW solo aplican al servidor.
        search_params=qm.SearchParams(hnsw_ef=128, exact=exact) if settings.qdrant_url else None,
    )
    return [(RagChunk.model_validate(p.payload), float(p.score)) for p in res.points]
