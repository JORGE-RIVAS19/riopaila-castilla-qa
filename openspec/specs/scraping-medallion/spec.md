# Spec · Pipeline de scraping Medallion

## Purpose
Capturar de forma reproducible y ética el contenido público de riopaila-castilla.com y convertirlo en un
corpus Gold con metadatos, listo para el prompt de sistema (Módulo 1) y el RAG (Módulo 2).

## Requirements

### Requirement: Descubrimiento respetuoso
El sistema SHALL leer `robots.txt` antes de cualquier otra petición y descubrir URLs desde los sitemaps declarados.

#### Scenario: URL bloqueada por robots.txt
- WHEN una URL del sitemap coincide con una regla `Disallow`
- THEN no se descarga y se cuenta en `descartes.robots_disallow` del manifiesto

#### Scenario: Sitemap de usuarios de WordPress
- WHEN el índice incluye `wp-sitemap-users-*.xml`
- THEN se omite (datos personales, Ley 1581) y se registra en `sitemaps_omitidos`

#### Scenario: Sitio sin sitemap
- WHEN no hay sitemap válido
- THEN se rastrean enlaces internos desde la página de inicio (BFS) con el mismo filtro de robots

### Requirement: Cortesía HTTP
El sistema SHALL enviar un User-Agent identificable, usar timeout y esperar al menos 1 s
(o el `Crawl-delay`) entre peticiones, con reintentos exponenciales ante errores 5xx o de red.

### Requirement: Capa Bronze
El sistema SHALL guardar el HTML crudo de cada URL y una línea en `data/raw/captures.jsonl` con
url, fecha de captura, status, bytes y hash SHA-256, incluidos los fallos.

#### Scenario: Demo en vivo con pocas descargas
- WHEN se ejecuta con `--refresh --max-pages N`
- THEN solo se hacen N descargas nuevas y el resto del corpus se toma de la caché Bronze

### Requirement: Capa Silver
El sistema SHALL extraer el cuerpo editorial a Markdown con trafilatura y usar un respaldo con
BeautifulSoup cuando trafilatura recupere menos del 55 % del texto disponible.

### Requirement: Deduplicación
El sistema SHALL eliminar duplicados exactos (hash), casi duplicados (Jaccard de 5-gramas ≥ 0.9),
bloques de boilerplate presentes en ≥ 30 % de las páginas y páginas con menos de 200 caracteres útiles.

### Requirement: Capa Gold
El sistema SHALL escribir un `.md` por página con frontmatter (id, url, titulo, seccion, tipo, empresa,
fecha_captura, fecha_publicacion, idioma, tokens, hash), `corpus.jsonl`, `chunks.jsonl`,
`knowledge_base.md` y `manifest.json` con las métricas de cada etapa.

### Requirement: Reprocesamiento sin red
El sistema SHALL regenerar Silver y Gold desde Bronze con `--offline` sin hacer peticiones HTTP.
