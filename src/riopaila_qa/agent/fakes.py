"""Modelo de chat simulado con *tool calling* para pruebas y CI (sin red ni API).

Imita el bucle razonamiento → acción → observación de un LLM real con reglas
simples: si el turno tiene herramientas y aún no hay observación, pide la
herramienta adecuada; cuando recibe la observación, redacta la respuesta citando
el primer documento. Nunca se usa en la demo.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class ScriptedToolModel(BaseChatModel):
    """LLM falso que llama herramientas de forma determinista."""

    bound_tools: list[str] = []
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted-tool-model"

    def bind_tools(self, tools: list, **kwargs: Any) -> ScriptedToolModel:
        names = [getattr(t, "name", None) or (t.get("name") if isinstance(t, dict) else None) for t in tools]
        return self.model_copy(update={"bound_tools": [n for n in names if n]})

    def _reply(self, messages: list[BaseMessage]) -> AIMessage:
        human = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
        text = (human.content if human else "") if isinstance(human.content if human else "", str) else ""
        last = messages[-1]
        system = next((m for m in messages if isinstance(m, SystemMessage)), None)
        if isinstance(last, ToolMessage):
            content = str(last.content)
            if last.name == "buscar_documentos":
                m = re.search(r'titulo="([^"]+)" url="([^"]+)"', content)
                titulo, url = (m.group(1), m.group(2)) if m else ("documento", "")
                warn = (
                    " El documento traía una instrucción sospechosa y la ignoré."
                    if "contenido_sospechoso" in content
                    else ""
                )
                return AIMessage(f"Según los documentos, {titulo.lower()} [1].{warn}\n\nFuentes: [1] {titulo} — {url}")
            if last.name == "consultar_indicadores":
                data = json.loads(content)
                if not data["filas"]:
                    return AIMessage("No encuentro esa cifra en los indicadores públicos de Riopaila Castilla.")
                f = data["filas"][0]
                return AIMessage(
                    f"El dato es {f['valor_legible']} ({f['indicador']}, {f['anio']}-{f['periodo']}). Fuente: {f['fuente_url']}"
                )
            if last.name == "recordar_dato_usuario":
                return AIMessage("Listo, lo recordaré en tus próximas conversaciones.")
            if last.name == "registrar_novedad":
                data = json.loads(content)
                return AIMessage(data.get("mensaje") or data.get("error") or "Listo.")
            return AIMessage(f"Resultado: {content[:200]}")
        taller = self._taller(text)
        if taller:
            return AIMessage("", tool_calls=[{**taller, "id": f"c{self.calls}"}])
        vitrina = self._vitrina(text)
        if vitrina:
            return AIMessage("", tool_calls=[{**vitrina, "id": f"c{self.calls}"}])
        if "buscar_documentos" in self.bound_tools:
            return AIMessage(
                "", tool_calls=[{"name": "buscar_documentos", "args": {"consulta": text}, "id": f"c{self.calls}"}]
            )
        if "consultar_indicadores" in self.bound_tools:
            year = re.search(r"20[12]\d", text)
            args: dict = {"indicador": "ventas_energia" if "energ" in text.lower() else "utilidad_neta"}
            if year:
                args["anio"] = int(year.group())
            if "tercer trimestre" in text.lower():
                args["periodo"] = "T3"
            return AIMessage("", tool_calls=[{"name": "consultar_indicadores", "args": args, "id": f"c{self.calls}"}])
        if "recordar_dato_usuario" in self.bound_tools:
            calls = []
            m = re.search(r"me llamo (\w+)", text, re.I)
            if m:
                calls.append(
                    {"name": "recordar_dato_usuario", "args": {"clave": "nombre", "valor": m.group(1)}, "id": "n1"}
                )
            m = re.search(r"trabajo en (\w+)", text, re.I)
            if m:
                calls.append(
                    {"name": "recordar_dato_usuario", "args": {"clave": "empresa", "valor": m.group(1)}, "id": "e1"}
                )
            if calls:
                return AIMessage("", tool_calls=calls)
        perfil = str(system.content) if system else ""
        m = re.search(r"- empresa: (.+)", perfil)
        if m and "trabajo" in text.lower():
            return AIMessage(f"Trabajas en {m.group(1).strip()}.")
        return AIMessage("¡Hola! Soy el asistente de Riopaila Castilla. ¿En qué te ayudo?")

    def _vitrina(self, text: str) -> dict | None:
        """Perfil visitante: infografía o serie de cifras públicas (solo si el router las habilitó)."""
        t = text.lower()
        b = set(self.bound_tools)
        if "grafica_indicador" in b and re.search(r"gr[aá]fica", t):
            ind = "utilidad_neta" if "utilidad" in t else "ingresos_operacionales"
            return {"name": "grafica_indicador", "args": {"indicador": ind}}
        if "infografia_riopaila" in b and re.search(r"en cifras|infograf|qu[eé] es riopaila", t):
            tema = "energia" if "energ" in t else "etanol" if "etanol" in t else "panorama"
            return {"name": "infografia_riopaila", "args": {"tema": tema}}
        return None

    def _taller(self, text: str) -> dict | None:
        """Módulo 3: elige la herramienta del taller por palabras clave (solo si el router la habilitó)."""
        t = text.lower()
        codigo = re.search(r"\b\d{4,6}\b", t)
        b = set(self.bound_tools)
        if "registrar_novedad" in b and codigo:
            return {
                "name": "registrar_novedad",
                "args": {"equipo": codigo.group(), "descripcion": text, "prioridad": "alta"},
            }
        if "identificar_repuesto_por_foto" in b and "[foto adjunta]" in t:
            return {"name": "identificar_repuesto_por_foto", "args": {"nota": text}}
        if "buscar_manual" in b:
            return {"name": "buscar_manual", "args": {"consulta": text}}
        if "detectar_anomalias" in b and re.search(r"anomal|raro|alerta", t):
            return {"name": "detectar_anomalias", "args": {"dias": 30}}
        if "grafica_gasto" in b and re.search(r"gr[aá]fica|tendencia", t):
            return {"name": "grafica_gasto", "args": {"equipo": codigo.group() if codigo else None}}
        if "ficha_equipo" in b and codigo:
            return {"name": "ficha_equipo", "args": {"equipo": codigo.group()}}
        if "ranking_gasto_equipos" in b:
            return {"name": "ranking_gasto_equipos", "args": {"dias": 90}}
        return None

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=self._reply(messages))])
