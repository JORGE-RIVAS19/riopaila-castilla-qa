"""Memoria del agente (Clase 6): corto plazo con checkpointer y largo plazo con Store.

* **Corto plazo** — ``SqliteSaver``: guarda el estado completo del grafo por
  ``thread_id`` en ``data/memory/checkpoints.sqlite``. Como vive en disco, el hilo
  sobrevive al reinicio del backend (no es memoria en la RAM del proceso).
* **Largo plazo** — ``SqliteStore``: hechos del usuario que cruzan hilos, en el
  namespace ``("usuarios", <user_id>, "perfil")``. Se recuperan con ``store.search()``
  en cualquier conversación nueva del mismo usuario.
* **Registro de hilos** — también en el Store, namespace ``("usuarios", <user_id>, "hilos")``,
  para que el frontend liste las conversaciones.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.base import BaseStore
from langgraph.store.sqlite import SqliteStore

from riopaila_qa.agent.settings import AgentSettings

PROFILE = "perfil"
THREADS = "hilos"
USER_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,40}$")


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def normalize_user_id(raw: str | None) -> str:
    """ID de usuario seguro para usarlo como namespace (minúsculas, sin espacios)."""
    value = re.sub(r"[^a-z0-9_.-]+", "-", (raw or "invitado").strip().lower()).strip("-") or "invitado"
    if not USER_ID_RE.match(value):
        value = value[:40]
    return value


def profile_ns(user_id: str) -> tuple[str, ...]:
    return ("usuarios", user_id, PROFILE)


def threads_ns(user_id: str) -> tuple[str, ...]:
    return ("usuarios", user_id, THREADS)


def open_checkpointer(settings: AgentSettings) -> SqliteSaver:
    """Checkpointer persistente en SQLite (un archivo, sin servidor)."""
    settings.memory_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.checkpoints_db, check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


def open_store(settings: AgentSettings) -> SqliteStore:
    """Store persistente en SQLite para la memoria de largo plazo."""
    settings.memory_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.store_db, check_same_thread=False, isolation_level=None)
    store = SqliteStore(conn)
    store.setup()
    return store


# --- Perfil (largo plazo) -----------------------------------------------------


def save_fact(store: BaseStore, user_id: str, clave: str, valor: str, thread_id: str | None = None) -> dict:
    """Guarda (o actualiza) un hecho del usuario en su namespace de perfil."""
    key = re.sub(r"[^a-z0-9_]+", "_", clave.strip().lower()).strip("_") or "dato"
    item = {"clave": key, "valor": valor.strip(), "hilo_origen": thread_id, "actualizado": now_iso()}
    store.put(profile_ns(user_id), key, item)
    return item


def load_profile(store: BaseStore, user_id: str, query: str | None = None, limit: int = 20) -> list[dict]:
    """Recupera el perfil con ``store.search()`` (desde cualquier hilo)."""
    items = store.search(profile_ns(user_id), query=query, limit=limit)
    return [dict(it.value) | {"key": it.key} for it in items]


def delete_fact(store: BaseStore, user_id: str, key: str) -> None:
    store.delete(profile_ns(user_id), key)


def profile_as_text(facts: list[dict]) -> str:
    if not facts:
        return "(sin datos guardados todavía)"
    return "\n".join(f"- {f['clave']}: {f['valor']}" for f in facts)


# --- Registro de hilos ----------------------------------------------------------


def touch_thread(store: BaseStore, user_id: str, thread_id: str, first_message: str | None = None) -> dict[str, Any]:
    """Crea o actualiza la ficha del hilo (título = primer mensaje)."""
    ns = threads_ns(user_id)
    current = store.get(ns, thread_id)
    data = dict(current.value) if current else {"thread_id": thread_id, "creado": now_iso(), "turnos": 0}
    if not data.get("titulo") and first_message:
        data["titulo"] = first_message.strip()[:60]
    data["turnos"] = int(data.get("turnos", 0)) + (1 if first_message is not None else 0)
    data["actualizado"] = now_iso()
    store.put(ns, thread_id, data)
    return data


def list_threads(store: BaseStore, user_id: str, limit: int = 50) -> list[dict]:
    items = store.search(threads_ns(user_id), limit=limit)
    threads = [dict(it.value) for it in items]
    return sorted(threads, key=lambda t: t.get("actualizado", ""), reverse=True)


def forget_thread(store: BaseStore, checkpointer: SqliteSaver, user_id: str, thread_id: str) -> None:
    store.delete(threads_ns(user_id), thread_id)
    checkpointer.delete_thread(thread_id)
