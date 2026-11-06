"""Utilidades de texto compartidas: tokens, hashes, slugs y normalización."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from functools import lru_cache

_WS_RE = re.compile(r"[ \t ]+")
_MANY_NL_RE = re.compile(r"\n{3,}")


@lru_cache(maxsize=1)
def _encoder():
    """Carga el tokenizador cl100k de tiktoken; ``None`` si no hay red/caché."""
    try:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base")
    except Exception:  # noqa: BLE001 - sin red el conteo cae a la heurística
        return None


def count_tokens(text: str) -> int:
    """Cuenta tokens con cl100k (BPE); si no está disponible, usa ~4 chars/token."""
    if not text:
        return 0
    enc = _encoder()
    if enc is None:
        return max(1, round(len(text) / 4))
    return len(enc.encode(text, disallowed_special=()))


def sha256(text: str | bytes) -> str:
    """Hash SHA-256 en hexadecimal de un texto o bytes."""
    data = text.encode("utf-8") if isinstance(text, str) else text
    return hashlib.sha256(data).hexdigest()


def short_hash(text: str | bytes, n: int = 12) -> str:
    """Primeros ``n`` caracteres del SHA-256 (identificador legible)."""
    return sha256(text)[:n]


def slugify(value: str, max_len: int = 80) -> str:
    """Convierte un texto o ruta de URL en un nombre de archivo seguro."""
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return (value or "inicio")[:max_len].strip("-")


def normalize_text(text: str) -> str:
    """Normaliza espacios, saltos de línea y caracteres invisibles."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("​", "")
    lines = [_WS_RE.sub(" ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    return _MANY_NL_RE.sub("\n\n", text).strip()


def paragraph_key(paragraph: str) -> str:
    """Clave canónica de un párrafo para detectar boilerplate repetido."""
    p = unicodedata.normalize("NFKD", paragraph.lower())
    p = "".join(c for c in p if not unicodedata.combining(c))
    return re.sub(r"[\W_]+", " ", p).strip()
