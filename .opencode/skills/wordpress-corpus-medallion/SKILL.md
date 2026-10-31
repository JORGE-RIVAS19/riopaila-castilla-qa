---
name: wordpress-corpus-medallion
description: Construye un corpus Medallion (Bronze, Silver, Gold) a partir de un sitio corporativo en WordPress respetando robots.txt y wp-sitemap.xml. Úsala cuando haya que extraer el contenido público de una empresa a Markdown con frontmatter para un prompt de sistema o un RAG.
---

# WordPress → Corpus Medallion

## Cuándo usarla
- El sitio de la empresa es WordPress (busca `wp-content` o `wp-sitemap.xml`).
- Necesitas un corpus limpio, citable y reproducible para un LLM.

## Procedimiento
1. **Descubrir**: lee `/robots.txt`; toma los `Sitemap:` declarados o `/wp-sitemap.xml`.
   Recorre solo `wp-sitemap-posts-page`, `posts-post` y `posts-portfolio`.
   **Nunca** `wp-sitemap-users` (datos personales) ni taxonomías (listados duplicados).
2. **Extraer (Bronze)**: `requests` con User-Agent identificable, `timeout=15`, ≥1 s entre peticiones
   (o el `Crawl-delay`). Guarda el HTML crudo y un JSONL con url, fecha, status y hash SHA-256.
3. **Limpiar (Silver)**: `trafilatura.extract(output_format="markdown", favor_recall=True, deduplicate=False)`;
   si trae mucho menos texto que un respaldo con BeautifulSoup (page builders), usa el respaldo.
4. **Deduplicar**: hash exacto, Jaccard de 5-gramas ≥ 0.9 y bloques presentes en ≥30 % de las páginas
   (pie de página, panel de accesibilidad, menús).
5. **Enriquecer (Gold)**: un `.md` por página con frontmatter `url, titulo, seccion, fecha_captura, hash, tokens`;
   `corpus.jsonl` y `chunks.jsonl` (cortar primero por `##`).

## Verificación
- `manifest.json` debe mostrar descartes por robots, duplicados y páginas cortas.
- Ningún `.md` de Gold debe contener el pie de página.
- `--offline` regenera Silver y Gold con 0 peticiones HTTP.

## Referencia
Implementación completa: `src/riopaila_qa/scraping/` de este repositorio.
