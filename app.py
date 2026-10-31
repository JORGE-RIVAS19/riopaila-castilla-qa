"""Dashboard de prueba del Módulo 1 · Riopaila Castilla (TAAML · Grupo 3).

Ejecutar con:  uv run streamlit run app.py
"""

from __future__ import annotations

import json
import time

import pandas as pd
import requests
import streamlit as st

from riopaila_qa.config import get_settings
from riopaila_qa.corpus import SECTION_ORDER, CorpusStore
from riopaila_qa.evaluation import load_questions, load_runs, run_evaluation, to_markdown
from riopaila_qa.llm import PROVIDERS, TASK_SAMPLING, model_name
from riopaila_qa.prompts import QA_VARIANTS, load_prompt
from riopaila_qa.scraping import STAGES, run_pipeline
from riopaila_qa.tasks import TaskResult, answer_question, generate_faq, summarize

st.set_page_config(page_title="Riopaila Castilla · Asistente Q&A", page_icon="🌾", layout="wide")

st.markdown(
    """
<style>
:root { --rc-green:#0f6b3a; --rc-leaf:#2e9d5b; --rc-cane:#e9b949; }
.block-container { padding-top: 1.6rem; }
.rc-hero { background: linear-gradient(120deg, var(--rc-green), var(--rc-leaf)); color: #fff;
  border-radius: 16px; padding: 18px 24px; margin-bottom: 12px; }
.rc-hero h1 { color:#fff; font-size: 1.7rem; margin: 0; }
.rc-hero p { margin: 4px 0 0 0; opacity: .92; }
.rc-stage { border: 1px solid rgba(15,107,58,.25); border-radius: 12px; padding: 10px 12px;
  background: rgba(46,157,91,.06); min-height: 168px; }
.rc-stage b { color: var(--rc-green); }
.rc-src { border-left: 4px solid var(--rc-cane); padding: 6px 10px; margin: 6px 0;
  background: rgba(233,185,73,.10); border-radius: 6px; font-size: .92rem; }
.rc-pill { display:inline-block; padding:2px 10px; border-radius:999px; font-size:.8rem;
  background: rgba(15,107,58,.12); color: var(--rc-green); margin-right:6px; }
</style>
""",
    unsafe_allow_html=True,
)

settings = get_settings()
paths = settings.paths
STAGE_INFO = {
    "descubrir": ("🗺️", "robots.txt + sitemap.xml", "Qué se puede leer y dónde está todo"),
    "extraer": ("🌐", "Bronze · data/raw/", "HTML crudo + JSONL de captura (url, fecha, status, hash)"),
    "limpiar": ("🧹", "Silver · data/processed/", "Cuerpo editorial a Markdown (trafilatura / BS4)"),
    "deduplicar": ("♻️", "Duplicados y boilerplate", "Copias exactas, casi duplicados y pie de página"),
    "enriquecer": ("🥇", "Gold · data/gold/", "Frontmatter YAML, corpus.jsonl y chunks"),
}


def corpus_version() -> float:
    """Marca de tiempo del corpus: invalida la caché cuando el pipeline lo regenera."""
    return paths.corpus.stat().st_mtime if paths.corpus.exists() else 0.0


@st.cache_resource(show_spinner=False)
def load_store(version: float) -> CorpusStore:  # noqa: ARG001 - la versión solo invalida la caché
    return CorpusStore(paths)


def ollama_models(base_url: str) -> list[str] | None:
    """Lista los modelos de Ollama, o ``None`` si el servidor no responde."""
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=1.5)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except requests.RequestException:
        return None


def show_sources(result: TaskResult) -> None:
    """Tarjetas con las fuentes citadas y verificadas."""
    if result.citations:
        st.markdown("**📎 Fuentes citadas (verificadas contra el contexto)**")
        for c in result.citations:
            st.markdown(
                f"<div class='rc-src'>[{c.n}] <b>{c.titulo}</b><br><a href='{c.url}' target='_blank'>{c.url}</a></div>",
                unsafe_allow_html=True,
            )
    if result.invalid_citations:
        st.warning(
            f"El modelo citó ids que no estaban en el contexto: {result.invalid_citations} (posible alucinación)."
        )


def show_trace(result: TaskResult) -> None:
    """Métricas y trazabilidad del prompt para defender cada respuesta."""
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Latencia", f"{result.latency_s} s")
    c2.metric("Tokens del prompt", f"{result.prompt_tokens:,}")
    c3.metric("Modo de contexto", result.context.mode if result.context else "-")
    c4.metric("Fragmentos en contexto", len(result.context.pieces) if result.context else 0)
    with st.expander("🔍 Ver el prompt exacto enviado al modelo"):
        st.code(
            result.rendered_prompt[:30000]
            + ("\n…(recortado en pantalla)" if len(result.rendered_prompt) > 30000 else ""),
            language="xml",
        )
    if result.context:
        with st.expander("🧩 Documentos que entraron al contexto"):
            for note in result.context.notes:
                st.caption(note)
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "id": p.n,
                            "titulo": p.titulo,
                            "seccion": p.seccion,
                            "tokens": p.tokens,
                            "bm25": p.score,
                            "url": p.url,
                        }
                        for p in result.context.pieces
                    ]
                ),
                hide_index=True,
                width="stretch",
            )


store = load_store(corpus_version())
manifest = store.manifest()

# ---------------------------------------------------------------- Sidebar
with st.sidebar:
    st.markdown("### ⚙️ Modelo")
    provider = st.selectbox(
        "Proveedor",
        PROVIDERS,
        index=PROVIDERS.index(settings.llm.provider) if settings.llm.provider in PROVIDERS else 0,
        format_func={"ollama": "🦙 Ollama (local)", "gemini": "✨ Gemini (API)", "openai": "🤖 OpenAI (API)"}.get,
    )
    model = st.text_input("Modelo", value=model_name(settings.llm, provider))
    if provider == "ollama":
        models = ollama_models(settings.llm.ollama_base_url)
        if models is None:
            st.error("Ollama no responde. Ábrelo o ejecuta `ollama serve`.")
        elif model not in models and f"{model}:latest" not in models:
            st.warning(f"Falta el modelo: `ollama pull {model}`")
        else:
            st.success("Ollama listo ✅")
    st.markdown("### 🧠 Contexto")
    mode = st.radio(
        "Cómo entra el corpus al prompt",
        ["auto", "completo", "bm25"],
        format_func={
            "auto": "Auto (completo si cabe)",
            "completo": "Corpus completo en el system prompt",
            "bm25": "Preselección BM25 (puente a RAG)",
        }.get,
    )
    budget = st.slider(
        "Presupuesto de tokens del contexto",
        2000,
        200000,
        settings.llm.max_context_tokens,
        1000,
        help="Llama 3.2 local: 8k–16k. Gemini admite >100k (todo el corpus).",
    )
    prompt_id = st.selectbox("Versión del prompt Q&A", list(QA_VARIANTS), format_func=QA_VARIANTS.get)
    st.markdown("### 🎛️ Muestreo por tarea")
    st.dataframe(
        pd.DataFrame([{"tarea": t, "T": s.temperature, "top_p": s.top_p} for t, s in TASK_SAMPLING.items()]),
        hide_index=True,
        width="stretch",
    )
    st.caption("Q1 (T=0, p=0.1) para hechos y JSON · Q2 (T=0.3, p=0.9) para resúmenes.")

# ---------------------------------------------------------------- Header
st.markdown(
    "<div class='rc-hero'><h1>🌾 Riopaila Castilla · Base de conocimiento y Q&A</h1>"
    "<p>Módulo 1 · Técnicas Avanzadas de IA en Modelos de Lenguaje · UAO · Grupo 3</p></div>",
    unsafe_allow_html=True,
)
if store.available:
    g = manifest.get("enriquecer", {})
    d = manifest.get("descubrir", {})
    dd = manifest.get("deduplicar", {})
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("URLs descubiertas", d.get("urls_descubiertas", "-"))
    m2.metric("Páginas capturadas", manifest.get("extraer", {}).get("paginas_descargadas", "-"))
    m3.metric("Documentos Gold", g.get("documentos", len(store.docs)))
    m4.metric("Chunks", g.get("chunks", len(store.chunks)))
    m5.metric("Tokens corpus", f"{store.total_tokens:,}")
    discards = (
        sum(d.get("descartes", {}).values())
        + dd.get("duplicados_exactos", 0)
        + dd.get("casi_duplicados", 0)
        + dd.get("muy_cortas", 0)
    )
    m6.metric("Descartes", discards, help="robots.txt, patrones excluidos, externas, duplicados y páginas cortas")
else:
    st.info("Aún no hay corpus Gold. Ve a la pestaña **🕷️ Pipeline** y ejecuta el scraping en línea.")

tabs = st.tabs(["🏢 Contexto", "🕷️ Pipeline", "💬 Q&A", "📝 Resumen", "❓ FAQ", "🧪 Evaluación", "📚 Corpus"])

# ---------------------------------------------------------------- Contexto
with tabs[0]:
    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.subheader("El problema")
        st.markdown(
            "Riopaila Castilla es un grupo agroindustrial del Valle del Cauca con muchos públicos: clientes de "
            "azúcar y mieles, compradores de energía y alcohol, proveedores de caña, comunidades, inversionistas "
            "y aspirantes a empleo. Su información pública está repartida en decenas de páginas y noticias. "
            "**Necesitamos un canal automatizado y preciso** que responda la primera consulta de cualquiera de "
            "ellos sin inventar datos."
        )
        st.subheader("La solución (Módulo 1)")
        st.markdown(
            "1. **Pipeline Medallion** reproducible que extrae el sitio oficial respetando robots.txt.\n"
            "2. **Corpus Gold** en Markdown con metadatos (URL, sección, fecha, hash, tokens) y chunks.\n"
            "3. **Prompt de sistema** que consolida el conocimiento, con defensa XML y citas verificadas.\n"
            "4. **Tres tareas con LangChain**: Resumen, FAQ (Pydantic) y Q&A.\n"
            "5. Base lista para el **RAG del Módulo 2** (embeddings + base vectorial)."
        )
        st.subheader("Alcance del Q&A")
        st.markdown(
            "<span class='rc-pill'>historia e identidad</span><span class='rc-pill'>presencia y cifras</span>"
            "<span class='rc-pill'>productos y negocios</span><span class='rc-pill'>energía y alcohol</span>"
            "<span class='rc-pill'>sostenibilidad</span><span class='rc-pill'>comunidades</span>"
            "<span class='rc-pill'>gobierno corporativo</span><span class='rc-pill'>contacto y empleo</span>",
            unsafe_allow_html=True,
        )
    with c2:
        st.subheader("Arquitectura")
        st.graphviz_chart(
            """digraph G { rankdir=TB; node [shape=box, style="rounded,filled", fillcolor="#eaf6ee",
            color="#0f6b3a", fontname="Helvetica"]; edge [color="#0f6b3a"];
            web [label="riopaila-castilla.com\\nrobots.txt · wp-sitemap.xml", fillcolor="#fff6dd"];
            bronze [label="🥉 Bronze · data/raw\\nHTML crudo + captures.jsonl"];
            silver [label="🥈 Silver · data/processed\\nMarkdown limpio"];
            gold [label="🥇 Gold · data/gold\\n.md + frontmatter · corpus.jsonl · chunks.jsonl"];
            ctx [label="Contexto del prompt\\ncompleto | BM25 (presupuesto de tokens)"];
            llm [label="LangChain + LLM\\nOllama Llama 3.2 · Gemini · OpenAI", fillcolor="#fff6dd"];
            ui [label="Streamlit\\nResumen · FAQ · Q&A con citas"];
            web -> bronze [label=" descubrir/extraer"]; bronze -> silver [label=" limpiar"];
            silver -> gold [label=" deduplicar/enriquecer"]; gold -> ctx -> llm -> ui; }"""
        )

# ---------------------------------------------------------------- Pipeline
with tabs[1]:
    st.subheader("Pipeline de scraping por etapas")
    cols = st.columns(5)
    for col, stage in zip(cols, STAGES, strict=True):
        icon, layer, desc = STAGE_INFO[stage]
        data = manifest.get(stage, {})
        if stage == "descubrir":
            figure = f"{data.get('urls_a_capturar', '–')} URLs"
        elif stage == "extraer":
            figure = f"{data.get('paginas_descargadas', '–')} páginas"
        elif stage == "limpiar":
            figure = f"{data.get('paginas_limpias', '–')} limpias"
        elif stage == "deduplicar":
            figure = f"{data.get('duplicados_exactos', 0) + data.get('casi_duplicados', 0)} dup · {data.get('bloques_boilerplate_eliminados', '–')} bloques"
        else:
            figure = f"{data.get('documentos', '–')} docs"
        col.markdown(
            f"<div class='rc-stage'>{icon} <b>{stage.upper()}</b><br><small>{layer}</small>"
            f"<h4 style='margin:.3rem 0'>{figure}</h4><small>{desc}</small></div>",
            unsafe_allow_html=True,
        )

    st.divider()
    left, right = st.columns([1, 1.4])
    with left:
        st.markdown("#### ▶️ Ejecutar")
        run_mode = st.radio(
            "Fuente",
            ["offline", "online"],
            horizontal=True,
            format_func={"offline": "Reprocesar desde Bronze (sin red)", "online": "Scraping en vivo del sitio"}.get,
        )
        max_new = None
        refresh = False
        if run_mode == "online":
            max_new = st.number_input(
                "Máximo de descargas nuevas",
                1,
                500,
                5,
                help="El resto de páginas sale de la caché Bronze: el corpus no se pierde.",
            )
            refresh = st.checkbox("Volver a descargar aunque estén en caché", value=True)
        go = st.button("Ejecutar pipeline", type="primary", width="stretch")
    with right:
        if go:
            boxes = {
                s: st.status(f"{STAGE_INFO[s][0]} {s} · en espera", state="running", expanded=False) for s in STAGES
            }
            bars: dict[str, object] = {}

            def on_event(stage: str, status: str, message: str, data: dict) -> None:
                box = boxes[stage]
                if status == "start":
                    box.update(label=f"{STAGE_INFO[stage][0]} {stage} · {message}", state="running", expanded=True)
                elif status == "progress":
                    if stage not in bars:
                        bars[stage] = box.progress(0.0)
                    if data.get("n"):
                        bars[stage].progress(data["i"] / data["n"], text=message[-90:])
                else:
                    box.update(label=f"{STAGE_INFO[stage][0]} {stage} · ✅ {message}", state="complete", expanded=False)
                    slim = {
                        k: v
                        for k, v in data.items()
                        if k not in ("detalle_descartes", "errores", "ejemplos_boilerplate")
                    }
                    box.json(slim, expanded=False)

            try:
                result = run_pipeline(
                    settings, max_pages=max_new, offline=run_mode == "offline", refresh=refresh, on_event=on_event
                )
                load_store.clear()
                st.success(
                    f"Corpus regenerado en {result['duracion_s']} s · {result['enriquecer']['documentos']} "
                    f"documentos · {result['enriquecer']['tokens_totales']:,} tokens. Recarga la página para "
                    "actualizar las métricas."
                )
            except (FileNotFoundError, RuntimeError) as exc:
                st.error(str(exc))
            except Exception as exc:  # noqa: BLE001
                st.exception(exc)
        elif manifest:
            st.markdown("#### 📊 Métricas de la última corrida")
            st.caption(
                f"{manifest.get('fecha_ejecucion')} · modo {manifest.get('modo')} · "
                f"{manifest.get('duracion_s')} s · User-Agent: `{manifest.get('user_agent')}`"
            )
            d, e, dd = manifest.get("descubrir", {}), manifest.get("extraer", {}), manifest.get("deduplicar", {})
            discard_rows = [
                {"motivo": "Bloqueadas por robots.txt", "cantidad": d.get("descartes", {}).get("robots_disallow", 0)},
                {
                    "motivo": "Patrones excluidos (tag, feed, autor…)",
                    "cantidad": d.get("descartes", {}).get("patrones_excluidos", 0),
                },
                {"motivo": "Sitemaps omitidos (usuarios/taxonomías)", "cantidad": len(d.get("sitemaps_omitidos", []))},
                {"motivo": "Errores HTTP", "cantidad": len(e.get("errores", []))},
                {"motivo": "Duplicados exactos", "cantidad": dd.get("duplicados_exactos", 0)},
                {"motivo": "Casi duplicados (Jaccard ≥ 0.9)", "cantidad": dd.get("casi_duplicados", 0)},
                {"motivo": "Muy cortas tras limpiar", "cantidad": dd.get("muy_cortas", 0)},
                {
                    "motivo": "Bloques de boilerplate eliminados",
                    "cantidad": dd.get("bloques_boilerplate_eliminados", 0),
                },
            ]
            st.dataframe(pd.DataFrame(discard_rows), hide_index=True, width="stretch")
            ahorro = manifest.get("ahorro_tokens_pct")
            st.metric(
                "Ahorro de tokens HTML crudo → Gold",
                f"{ahorro} %" if ahorro is not None else "–",
                help="≈ bytes HTML/4 frente a tokens cl100k del Markdown Gold",
            )
    if store.available:
        st.markdown("#### Documentos y tokens por sección")
        g = manifest.get("enriquecer", {})
        sec = pd.DataFrame({"documentos": g.get("docs_por_seccion", {}), "tokens": g.get("tokens_por_seccion", {})})
        if not sec.empty:
            st.bar_chart(sec["tokens"], horizontal=True, color="#2e9d5b")

# ---------------------------------------------------------------- Q&A
with tabs[2]:
    st.subheader("💬 Pregúntale al asistente")
    if not store.available:
        st.info("Primero genera el corpus en la pestaña Pipeline.")
    else:
        examples = (
            [q["pregunta"] for q in load_questions(paths)][:24] if (paths.eval_dir / "preguntas.jsonl").exists() else []
        )
        pick = st.selectbox("Ejemplos de la batería de pruebas (o escribe la tuya abajo)", ["—"] + examples)
        question = st.text_area(
            "Pregunta",
            value="" if pick == "—" else pick,
            height=80,
            placeholder="¿En qué año fue fundada Riopaila Castilla?",
        )
        if st.button("Responder", type="primary", disabled=not question.strip()):
            with st.spinner(f"Consultando {provider}:{model}…"):
                try:
                    res = answer_question(store, question, settings.llm, provider, model, prompt_id, mode, budget)
                    st.session_state["qa_last"] = res
                except RuntimeError as exc:
                    st.error(str(exc))
        res = st.session_state.get("qa_last")
        if res:
            badge = (
                "🛑 Rechazo de inyección" if res.refused else ("🤷 Abstención" if res.abstained else "✅ Respondida")
            )
            st.markdown(
                f"<span class='rc-pill'>{badge}</span><span class='rc-pill'>{res.prompt_id}</span>"
                f"<span class='rc-pill'>{res.provider}:{res.model}</span>",
                unsafe_allow_html=True,
            )
            st.markdown(res.output)
            show_sources(res)
            show_trace(res)

# ---------------------------------------------------------------- Resumen
with tabs[3]:
    st.subheader("📝 Resumen ejecutivo")
    if store.available:
        secs = [s for s in SECTION_ORDER if any(d.seccion == s for d in store.docs)]
        chosen = st.multiselect("Secciones (vacío = todo el corpus)", secs)
        if st.button("Generar resumen", type="primary"):
            with st.spinner("Resumiendo…"):
                try:
                    st.session_state["sum_last"] = summarize(
                        store, settings.llm, chosen or None, provider, model, budget
                    )
                except RuntimeError as exc:
                    st.error(str(exc))
        res = st.session_state.get("sum_last")
        if res:
            st.markdown(res.output)
            show_sources(res)
            show_trace(res)
    else:
        st.info("Primero genera el corpus en la pestaña Pipeline.")

# ---------------------------------------------------------------- FAQ
with tabs[4]:
    st.subheader("❓ Preguntas frecuentes generadas (salida estructurada con Pydantic)")
    if store.available:
        c1, c2 = st.columns([1, 2])
        n = c1.slider("Número de preguntas", 3, 12, 6)
        secs = [s for s in SECTION_ORDER if any(d.seccion == s for d in store.docs)]
        chosen_faq = c2.multiselect("Secciones (vacío = todo el corpus)", secs, key="faq_secs")
        if st.button("Generar FAQ", type="primary"):
            with st.spinner("Generando FAQ…"):
                try:
                    st.session_state["faq_last"] = generate_faq(
                        store, settings.llm, n, chosen_faq or None, provider, model, budget
                    )
                except RuntimeError as exc:
                    st.error(str(exc))
        res = st.session_state.get("faq_last")
        if res and res.structured:
            for row in res.structured:
                with st.expander(("⚠️ " if row["sin_fuente"] else "") + row["pregunta"]):
                    st.write(row["respuesta"])
                    for url in row["fuentes"]:
                        st.markdown(
                            f"<div class='rc-src'><a href='{url}' target='_blank'>{url}</a></div>",
                            unsafe_allow_html=True,
                        )
            st.download_button(
                "⬇️ Descargar FAQ (JSON)",
                json.dumps(res.structured, ensure_ascii=False, indent=2),
                "faq_riopaila.json",
                "application/json",
            )
            show_trace(res)
    else:
        st.info("Primero genera el corpus en la pestaña Pipeline.")

# ---------------------------------------------------------------- Evaluación
with tabs[5]:
    st.subheader("🧪 Pruebas: 24 preguntas (21 del alcance, 2 fuera de alcance, 1 inyección)")
    runs = load_runs(paths) if paths.eval_dir.exists() else []
    c1, c2 = st.columns([1, 2])
    limit = c1.number_input("Preguntas a correr ahora", 1, 24, 24)
    if c1.button("Correr batería con la configuración actual", type="primary", disabled=not store.available):
        bar = st.progress(0.0)
        log = st.empty()

        def progress(i: int, total: int, row: dict) -> None:
            bar.progress(i / total, text=f"{row['id']} · {'✅' if row.get('exito_auto') else '❌'}")
            log.caption(row["pregunta"])

        start = time.monotonic()
        rows, summary, out = run_evaluation(
            store, paths, settings.llm, prompt_id, provider, model, mode, budget, int(limit), progress
        )
        md = paths.root / "docs" / "evaluacion" / f"{out.stem}.md"
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(to_markdown(summary, rows), encoding="utf-8")
        st.success(f"Listo en {round(time.monotonic() - start)} s · guardado en {out.name}")
        runs = load_runs(paths)
    if runs:
        comp = pd.DataFrame([{**s, "archivo": f.name} for f, s, _ in runs])
        keep = [
            "prompt_id",
            "proveedor",
            "modelo",
            "modo_contexto",
            "preguntas",
            "exito_automatico_pct",
            "respuestas_con_cita_valida_pct",
            "aciertos_hechos_verificados_pct",
            "abstencion_correcta_pct",
            "rechazo_inyeccion_pct",
            "citas_inventadas",
            "latencia_media_s",
            "tokens_prompt_medio",
            "fecha",
        ]
        st.markdown("#### Comparación de corridas (experimentos de prompt)")
        st.dataframe(comp[[k for k in keep if k in comp.columns]], hide_index=True, width="stretch")
        names = [f.name for f, _, _ in runs]
        sel = st.selectbox("Detalle de la corrida", names)
        _, _, rows = runs[names.index(sel)]
        df = pd.DataFrame(rows)
        show = ["id", "categoria", "pregunta", "exito_auto", "respuesta", "fuentes", "latencia_s"]
        st.dataframe(df[[c for c in show if c in df.columns]], hide_index=True, width="stretch")
    else:
        st.caption("Aún no hay corridas guardadas: usa el botón o `uv run python scripts/run_eval.py`.")

# ---------------------------------------------------------------- Corpus
with tabs[6]:
    st.subheader("📚 Explorador del corpus Gold")
    if store.available:
        df = pd.DataFrame(
            [
                {
                    "titulo": d.titulo,
                    "seccion": d.seccion,
                    "tipo": d.tipo,
                    "tokens": d.tokens,
                    "fecha_captura": d.fecha_captura,
                    "hash": d.hash,
                    "url": d.url,
                }
                for d in store.docs
            ]
        )
        f1, f2 = st.columns([1, 2])
        sec_filter = f1.multiselect("Sección", sorted(df.seccion.unique()))
        text_filter = f2.text_input("Buscar en títulos/URLs")
        view = df[df.seccion.isin(sec_filter)] if sec_filter else df
        if text_filter:
            mask = view.titulo.str.contains(text_filter, case=False) | view.url.str.contains(text_filter, case=False)
            view = view[mask]
        st.dataframe(view, hide_index=True, width="stretch")
        pick_doc = st.selectbox("Ver documento", view.url.tolist())
        doc = next((d for d in store.docs if d.url == pick_doc), None)
        if doc:
            meta = doc.model_dump(exclude={"markdown"})
            st.json(meta, expanded=False)
            st.markdown(doc.markdown[:6000])
        with st.expander("Prompt de producción (v3) — plantilla"):
            spec = load_prompt("qa_v3_xml_sandwich")
            st.code(spec.system + "\n\n=== HUMAN ===\n" + spec.human, language="xml")
    else:
        st.info("Primero genera el corpus en la pestaña Pipeline.")
