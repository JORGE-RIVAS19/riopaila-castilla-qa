"""Memoria: Store de largo plazo por namespace y registro de hilos (SQLite en disco)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from riopaila_qa.agent import memory
from riopaila_qa.agent.settings import AgentSettings


def _settings(tmp_path: Path) -> AgentSettings:
    return replace(AgentSettings(), memory_dir=tmp_path / "memory")


def test_perfil_persiste_en_disco(tmp_path: Path):
    s = _settings(tmp_path)
    store = memory.open_store(s)
    memory.save_fact(store, "ana", "Empresa", "Carvajal", "hilo-1")
    otra = memory.open_store(s)  # otra conexión = otro proceso
    facts = memory.load_profile(otra, "ana")
    assert facts[0]["clave"] == "empresa" and facts[0]["valor"] == "Carvajal"
    assert memory.load_profile(otra, "otro-usuario") == []


def test_registro_de_hilos(tmp_path: Path):
    store = memory.open_store(_settings(tmp_path))
    memory.touch_thread(store, "ana", "t1", "¿Qué es RioCas?")
    memory.touch_thread(store, "ana", "t1", "segundo")
    hilos = memory.list_threads(store, "ana")
    assert hilos[0]["titulo"] == "¿Qué es RioCas?" and hilos[0]["turnos"] == 2


def test_normaliza_user_id():
    assert (
        memory.normalize_user_id("  Ana María ") == "ana-maría"
        or memory.normalize_user_id("  Ana María ") == "ana-mar-a"
    )
    assert memory.normalize_user_id("") == "invitado"


def test_checkpointer_crea_archivo(tmp_path: Path):
    s = _settings(tmp_path)
    memory.open_checkpointer(s)
    assert s.checkpoints_db.exists()
