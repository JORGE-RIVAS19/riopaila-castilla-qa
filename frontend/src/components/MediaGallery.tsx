import type { ChatMessage, MediaItem } from "../types";

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";

/** Todas las imágenes y PDF que generaron las herramientas del turno (sin repetir). */
export function mediaDelMensaje(m: ChatMessage): MediaItem[] {
  const vistos = new Set<string>();
  const out: MediaItem[] = [];
  for (const t of m.tools ?? []) {
    for (const item of t.artifact?.media ?? []) {
      if (item.url && !vistos.has(item.url)) {
        vistos.add(item.url);
        out.push(item);
      }
    }
  }
  return out;
}

const src = (url: string) => (url.startsWith("http") ? url : `${BASE}${url}`);

/** Módulo 3: muestra en el chat web lo mismo que llega por WhatsApp (página del manual, gráfica o PDF). */
export function MediaGallery({ message }: { message: ChatMessage }) {
  const items = mediaDelMensaje(message);
  if (items.length === 0) return null;
  return (
    <div className="media-gallery">
      {items.map((it) =>
        it.tipo === "imagen" ? (
          <figure key={it.url} className="media-item">
            <a href={src(it.url!)} target="_blank" rel="noreferrer">
              <img src={src(it.url!)} alt={it.pie} loading="lazy" />
            </a>
            <figcaption className="muted small">{it.pie}</figcaption>
          </figure>
        ) : (
          <a key={it.url} className="media-doc" href={src(it.url!)} target="_blank" rel="noreferrer">
            📄 {it.pie}
          </a>
        ),
      )}
    </div>
  );
}
