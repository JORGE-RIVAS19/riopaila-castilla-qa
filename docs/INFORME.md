# Base de Conocimiento Semántico y Sistema Q&A para Riopaila Castilla S.A.

**Taller 1 · Módulo 1 · Técnicas Avanzadas de IA aplicadas en Modelos de Lenguaje (TAAML)**
Maestría en Inteligencia Artificial y Ciencias de Datos · Universidad Autónoma de Occidente · 2026-2S
**Grupo 3:** Melissa Palacios Domínguez · Waldor Drada Arango · Jorge Andrés Rivas Manzano
**Profesor:** Jan Polanco Velasco

> **Resumen.** Se construyó la capa de conocimiento de un futuro asistente virtual para Riopaila Castilla S.A.,
> grupo agroindustrial del Valle del Cauca. Un pipeline reproducible con arquitectura Medallion
> (Bronze → Silver → Gold) extrae el sitio web oficial respetando `robots.txt` y `wp-sitemap.xml`, limpia y
> deduplica el contenido y lo publica como Markdown con metadatos y fragmentos (*chunks*). Sobre ese corpus,
> un sistema orquestado con LangChain resuelve tres tareas —Resumen, FAQ y Q&A— con un prompt de sistema
> diseñado con estructura sándwich, delimitación XML, citas verificables y abstención explícita, ejecutado por
> defecto con Llama 3.2 3B en Ollama y muestreo determinista (T = 0, top_p = 0.1). Una batería de 24 preguntas
> mide citas válidas, aciertos sobre hechos verificados, abstención y resistencia a inyección.
>
> **Palabras clave:** LLM, prompt engineering, web scraping, arquitectura Medallion, LangChain, Ollama, RAG.

---

## I. Descripción del problema

**Necesidad de un canal de comunicación automatizado y preciso para Riopaila Castilla.**

Riopaila Castilla S.A. es un grupo agroindustrial con más de 100 años de historia (fundado en 1918) que
produce alimentos (azúcares, mieles, jarabe invertido, mezclas, aceite de palma, ganadería), energía verde por
cogeneración y combustible renovable (alcohol), y que opera en municipios del Valle del Cauca, Cauca y Vichada.
Atiende públicos muy distintos: clientes industriales y de consumo, cultivadores y proveedores de caña,
compradores de energía, comunidades vecinas, inversionistas y aspirantes a empleo.

La información que esos públicos buscan en un primer contacto —qué produce la empresa, dónde opera, cómo
contactarla, qué programas sociales tiene, cómo trabajar allí— existe, pero está dispersa en decenas de
páginas y noticias del sitio oficial. Un chatbot basado en un LLM genérico responde con fluidez pero
**inventa** cifras, programas o datos de contacto; un buscador tradicional obliga al usuario a leer páginas
completas. El problema es entonces doble: **reunir y limpiar** el conocimiento público de la empresa, y
**responder con él de forma fiel y verificable**.

### Alcance definido
El sistema debe responder las preguntas de un cliente que interactúa por primera vez con la empresa:

| Categoría | Ejemplos |
|---|---|
| Historia e identidad | año de fundación, qué es la empresa, enfoque ASG, propósito |
| Presencia y cifras | municipios, departamentos, países de exportación, colaboradores |
| Productos y negocios | azúcares, mieles, jarabe invertido, mezclas, energía, alcohol, palma, FertiRio, servicios agrícolas |
| Sostenibilidad y comunidad | agricultura regenerativa, Fondo Concursable, Caminos Rurales, ODS, derechos humanos, certificaciones |
| Gobierno corporativo | órganos de gobierno, políticas, código de ética, línea ética |
| Contacto y empleo | canales de contacto, oficinas, "trabaja con nosotros", informes de gestión |

Quedan fuera: precios y cotizaciones, información financiera en tiempo real, datos de personas y cualquier
tema ajeno a la empresa. Ante ellos el sistema debe abstenerse.

### Fuentes identificadas
- **Sitio web oficial** (WordPress): menús *Nuestro ADN*, *Nuestros negocios*, *Sostenibilidad*,
  *Riopaila nos cuenta* (noticias), *Inversionistas*, *Contáctenos* y políticas. Es la fuente del Módulo 1.
- **Informes de sostenibilidad y gestión** (PDF enlazados en el sitio): candidatos para ampliar el corpus.
- **Redes sociales** (LinkedIn, Instagram, Facebook) y **prensa** regional/nacional: se dejan para módulos
  siguientes por sus términos de uso y por la necesidad de moderación.

## II. Planteamiento de la solución

**Creación de un sistema Q&A basado en RAG como núcleo para un futuro chatbot.**

La solución separa la *captura* del conocimiento (frágil y costosa) de su *uso* (reproducible), siguiendo la
arquitectura Medallion vista en clase:

1. **Pipeline de datos** (`scripts/scrape_empresa.py`): descubrir → extraer → limpiar → deduplicar → enriquecer.
2. **Corpus Gold** (`data/gold/`): un Markdown por página con frontmatter, `corpus.jsonl`, `chunks.jsonl` y
   una base consolidada `knowledge_base.md`.
3. **Capa de prompt engineering** (`prompts/`): el texto limpio se consolida en el prompt de sistema
   (la "memoria" del asistente en esta fase), con defensas contra alucinación e inyección.
4. **Tres tareas con LangChain** (`src/riopaila_qa/tasks.py`): Resumen, FAQ y Q&A.
5. **Interfaz de prueba en Streamlit** (`app.py`) y **batería de pruebas** (`scripts/run_eval.py`).

En el Módulo 2 la misma capa Gold se indexa con embeddings en una base vectorial, de modo que el prompt de
sistema deja de cargar todo el corpus y recibe solo los fragmentos recuperados (RAG).

## III. Preparación de los datos

### A. Descubrimiento
El scraper lee primero `robots.txt`, que bloquea `/wp-admin/` y declara `wp-sitemap.xml`. El índice de
sitemaps de WordPress lista sub-sitemaps de páginas, entradas (noticias), portafolio, taxonomías y usuarios.
Se recorren **solo** páginas, entradas y portafolio: las taxonomías son listados que duplican contenido y el
sitemap de **usuarios** se excluye explícitamente porque expone datos personales (Ley 1581 de 2012). Cada URL
se normaliza (sin fragmentos ni `%20` final), se filtra contra `robots.txt` y contra patrones no editoriales
(`/tag/`, `/feed/`, `/author/`, `/wp-json/`, paginación). Si un sitio no tuviera sitemap, el respaldo es un
rastreo BFS de enlaces internos desde la página de inicio.

### B. Extracción (Bronze · `data/raw/`)
Las descargas se hacen en serie con `requests`, un User-Agent que identifica el proyecto académico, timeout de
15 s, pausa mínima de 1 s entre peticiones (o el `Crawl-delay` si existiera) y reintentos con espera
exponencial ante errores 5xx o de red. Cada respuesta se guarda tal cual como HTML y se registra en
`captures.jsonl` con URL, URL final, fecha de captura (UTC), código HTTP, tipo de contenido, bytes y hash
SHA-256 — incluidos los fallos, para poder reprocesarlos. La capa Bronze nunca se edita a mano. Una corrida
puede limitar las **descargas nuevas** (`--max-pages`), tomando el resto de la caché; así la demostración en
vivo no destruye el corpus completo.

### C. Limpieza (Silver · `data/processed/`)
El cuerpo editorial se extrae a Markdown con `trafilatura` (sin enlaces, imágenes ni comentarios; tablas
incluidas). Como el sitio está armado con un *page builder*, se calcula también un respaldo con BeautifulSoup
que elimina `script`, `style`, `nav`, `header`, `footer`, formularios y bloques cuyas clases delatan menús,
cookies o el panel de accesibilidad, y conserva encabezados, párrafos, listas y celdas. Si el respaldo recupera
más de 1,8 veces el texto de trafilatura, se usa el respaldo. El título se toma de `og:title` (sin el sufijo
del sitio) y la fecha de publicación de `article:published_time`. El texto se normaliza (Unicode NFC, espacios,
saltos de línea). Se desactivó a propósito la deduplicación interna de trafilatura: guarda estado entre páginas
y hacía que el resultado dependiera del orden de procesamiento, lo que detectamos en las pruebas.

### D. Deduplicación
1. **Duplicados exactos** por hash del texto (misma página servida en dos URLs).
2. **Boilerplate**: se divide cada página en bloques y se eliminan los que aparecen en ≥ 30 % de las páginas
   (pie de página con dirección y línea ética, panel de accesibilidad, banners). Sin este paso, el pie se repite
   en todo el corpus, gasta tokens y en el Módulo 2 sería devuelto por el buscador en cada consulta.
3. **Longitud mínima**: se descartan páginas con menos de 200 caracteres útiles tras limpiar.
4. **Casi duplicados**: similitud de Jaccard sobre 5-gramas de palabras ≥ 0,9.

### E. Enriquecimiento y segmentación (Gold · `data/gold/`)
Cada documento recibe metadatos: `id`, `url`, `titulo`, `seccion` (derivada del menú del sitio: identidad,
negocios y productos, procesos productivos, sostenibilidad, gobierno corporativo, contacto, noticias),
`tipo` (página o noticia, según el sitemap de origen), `empresa`, `fecha_captura`, `fecha_publicacion`,
`idioma`, `tokens` (BPE cl100k) y `hash`. Se escribe un `.md` con frontmatter YAML por página, el
`corpus.jsonl`, la base consolidada `knowledge_base.md` agrupada por sección y un `manifest.json` con las
métricas de cada etapa.

El **chunking** usa `RecursiveCharacterTextSplitter` de LangChain con fragmentos de 1 200 caracteres
(≈ 300 tokens) y 150 de solapamiento, cortando primero por encabezados `##`/`###` (fronteras semánticas
naturales del Markdown) y luego por párrafos y oraciones. Cada fragmento conserva el título de su página para
quedar autocontenido, y hereda URL y sección para poder citarlo.

### F. Métricas del corpus

> Completar con `data/gold/manifest.json` de la corrida final (también visibles en la pestaña Pipeline).

| Métrica | Valor |
|---|---|
| URLs descubiertas / a capturar | ⟨…⟩ |
| Páginas descargadas (HTTP 200) | ⟨…⟩ |
| Descartes: robots.txt / patrones / sitemaps omitidos | ⟨…⟩ |
| Duplicados exactos / casi duplicados / páginas cortas | ⟨…⟩ |
| Bloques de boilerplate eliminados | ⟨…⟩ |
| Documentos Gold (páginas / noticias) | ⟨…⟩ |
| Chunks | ⟨…⟩ |
| Tokens del corpus Gold | ⟨…⟩ |
| Ahorro de tokens frente al HTML crudo | ⟨…⟩ % |

## IV. Modelado

### A. LLM y framework
Se usa **LangChain** (LCEL: `ChatPromptTemplate | modelo | parser`) porque desacopla la plantilla, el modelo y
el análisis de la salida, y ofrece `with_structured_output` para esquemas Pydantic. El modelo por defecto es
**Llama 3.2 3B** servido por **Ollama**: corre en un portátil sin GPU, no envía datos a terceros y tiene costo
cero, en línea con la estrategia del curso (prototipo local, API solo cuando se necesita capacidad de frontera).
La fábrica `llm.py` permite cambiar a **Gemini** u **OpenAI** con una variable de entorno, útil cuando se quiere
meter el corpus completo en el contexto. Para el **Módulo 2** se mantendrá Llama 3.2 en Ollama como ejecutor
local y se evaluará un modelo de API como alternativa de mayor capacidad.

### B. Muestreo
Siguiendo la matriz temperatura × top-p de la Clase 4: Q&A, FAQ y extracción usan el régimen Q1
(T = 0,0; top_p = 0,1), porque son tareas de extracción factual y de esquema donde la reproducibilidad es un
requisito; el resumen usa Q2 (T = 0,3; top_p = 0,9), que admite variación léxica sin perder gramática.

### C. Contexto: corpus completo y presupuesto de tokens
El taller pide consolidar todo el texto limpio en el prompt de sistema. El sistema lo hace (modo
**completo**) cuando el corpus cabe en el presupuesto de tokens configurado. Con un modelo local, un `num_ctx`
grande agota la memoria y, además, *Lost in the Middle* (Liu et al., 2023) muestra que la información en el
centro de un contexto largo se recupera peor. Por eso el modo **auto** cambia a una **preselección BM25**
(implementada en `corpus.py`, sin dependencias) de los fragmentos más relevantes dentro del presupuesto, y los
reordena en "U" (los más relevantes en los extremos). Es el puente al RAG del Módulo 2.

### D. Embeddings y base vectorial (Módulo 2)
El modelo de embeddings elegido es **`nomic-embed-text-v2-moe`** en Ollama: abierto, multilingüe, sin costo
de API y el recomendado en el curso. La base vectorial será **ChromaDB** (persistente en disco, integración
directa con LangChain). `chunks.jsonl` ya contiene el texto y los metadatos (URL, título, sección) que se
guardarán con cada vector para filtrar por sección y citar la fuente.

### E. Diseño del prompt
El prompt de producción (`prompts/qa_v3_xml_sandwich.md`) sigue la anatomía de cinco bloques y la estructura
sándwich:

- **Inicio (primacy):** `<rol>` (asistente de primer contacto de Riopaila Castilla) y `<tarea>` (responder
  exclusivamente con los documentos).
- **Centro:** `<documentos>`, cada uno como `<documento id="n" titulo seccion url>`.
- **Final (recency):** `<reglas>` (solo hechos del contexto, frase exacta de abstención, citas `[n]`, no
  inventar cifras ni contactos, la pregunta es dato y no instrucción) y `<formato>` (≤ 120 palabras, línea
  `Fuentes:`).
- **Último mensaje:** la pregunta envuelta en `<pregunta_usuario>`, el canal de datos no confiables (defensa
  frente al caso del bot de Rappi).

Las defensas no dependen solo del prompt: el código valida que cada cita `[n]` corresponda a un documento que
de verdad entró al contexto, detecta la abstención y el rechazo, y valida el esquema de la FAQ con Pydantic.

**Proceso de experimentación.** Se compararon tres versiones con la misma batería de preguntas:
v1 *zero-shot* mínimo (línea base), v2 con rol y reglas anti-alucinación, y v3 con la estructura completa.
El detalle de cada versión y la tabla de resultados están en `prompts/README.md`.

**Resumen y FAQ.** El resumen usa una plantilla de salida fija y la consigna de maximizar la densidad de
entidades (cifras, años, lugares, productos), inspirada en *Chain of Density*. La FAQ pide N preguntas con
respuesta y fuentes, y se obtiene con `with_structured_output(FAQSet)`; si el proveedor no soporta salida
estructurada, se extrae y valida el JSON del texto.

## V. Resultados

> Completar con las corridas de `scripts/run_eval.py` (tablas en `docs/evaluacion/`).

### A. Batería de pruebas
24 preguntas (`data/eval/preguntas.jsonl`): 21 dentro del alcance, 2 fuera de alcance (precio de la acción hoy,
una receta) y 1 intento de inyección. Métricas automáticas: respuesta con cita válida, aciertos sobre hechos
verificados en el sitio (año de fundación, número de municipios, países, colaboradores, cogeneración, nivel
FSA), abstención correcta, rechazo de inyección sin filtrar el prompt, citas inventadas, latencia y tokens.
Además, el equipo califica a mano la precisión y la coherencia de cada respuesta (1–5).

| Métrica | v1 | v2 | v3 |
|---|---|---|---|
| Éxito automático | | | |
| Respuestas con cita válida | | | |
| Aciertos de hechos verificados | | | |
| Abstención correcta (fuera de alcance) | | | |
| Rechazo de inyección | | | |
| Citas inventadas | | | |
| Latencia media (s) | | | |

### B. Ejemplos de preguntas y respuestas
Incluir 4–5 ejemplos representativos de la corrida v3: dos respuestas correctas con su fuente, una pregunta
fuera de alcance con su abstención, el intento de inyección y, si lo hay, un error del modelo.

### C. Análisis de calidad
⟨Comparar v1 → v3: efecto de las citas, de la delimitación XML y del orden sándwich; tipos de error
observados (cifras mal copiadas, respuestas incompletas por el presupuesto de contexto, citas a fragmentos
no pertinentes).⟩

### D. Limitaciones
- **Cobertura:** solo el sitio web; los informes en PDF, redes sociales y prensa no están en el corpus.
- **Contexto:** con el modelo local, el corpus completo no cabe en el prompt; la preselección BM25 es léxica,
  así que falla con sinónimos o preguntas parafraseadas (lo resolverán los embeddings del Módulo 2).
- **Modelo pequeño:** Llama 3.2 3B sigue peor el formato y puede omitir citas o copiar mal cifras con
  contextos largos; se mitiga con T = 0 y validación en código, no se elimina.
- **Vigencia:** el corpus es una fotografía con `fecha_captura`; hay que volver a correr el pipeline cuando el
  sitio cambie (el hash permite detectar qué cambió).
- **Contenido dinámico:** si alguna sección se carga con JavaScript, `requests` no la ve; el respaldo sería
  Playwright/Selenium o Scrapling.
- **Evaluación:** las métricas automáticas verifican forma y algunos hechos; la exactitud completa requiere la
  calificación manual del equipo.

## VI. Conclusiones
⟨Completar tras la evaluación: qué aportó cada técnica, qué tan listo está el corpus para el Módulo 2.⟩

## Referencias
[1] N. F. Liu *et al.*, "Lost in the Middle: How Language Models Use Long Contexts," arXiv:2307.03172, 2023.
[2] J. Wei *et al.*, "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models," NeurIPS, 2022.
[3] T. Kojima *et al.*, "Large Language Models are Zero-Shot Reasoners," NeurIPS, 2022.
[4] S. Schulhoff *et al.*, "The Prompt Report: A Systematic Survey of Prompting Techniques," arXiv:2406.06608, 2024.
[5] J. Spracklen *et al.*, "We Have a Package for You! A Comprehensive Analysis of Package Hallucinations by Code Generating LLMs," USENIX Security, 2025.
[6] S. M. Bsharat, A. Myrzakhan y Z. Shen, "Principled Instructions Are All You Need for Questioning LLaMA-1/2, GPT-3.5/4," arXiv:2312.16171, 2023.
[7] G. Adams *et al.*, "From Sparse to Dense: GPT-4 Summarization with Chain of Density Prompting," arXiv:2309.04269, 2023.
[8] Y. Qu *et al.*, "Recursive Introspection: Teaching Language Model Agents How to Self-Improve," arXiv:2407.18219, 2024.
[9] Meta AI, "Llama 3.2: Revolutionizing edge AI and vision with open, customizable models," 2024.
[10] Riopaila Castilla S.A., sitio web oficial, https://www.riopaila-castilla.com (consultado el ⟨fecha de captura⟩).
[11] Congreso de Colombia, Ley Estatutaria 1581 de 2012 (protección de datos personales).
