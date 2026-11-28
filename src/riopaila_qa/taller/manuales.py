"""Manuales técnicos del taller: catálogo, extracción por página, búsqueda híbrida y foto de la página.

Cada página de cada PDF es un documento. Se busca con BM25 (con un glosario español → inglés /
portugués, porque la mayoría de manuales no están en español) y, si hay embeddings, con Qdrant;
ambas listas se fusionan con RRF (k=60), igual que en el Módulo 2. La respuesta va acompañada de
la **imagen de la página** (pypdfium2, licencia Apache/BSD) con los términos de la búsqueda
resaltados, que el puente de WhatsApp envía como foto.

Los PDF tienen derechos de autor: viven solo en el servidor (``MANUALES_DIR``) y nunca en Git.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from riopaila_qa.corpus import BM25, tokenize

TIPOS = ("operador", "servicio", "partes", "diagnostico", "diagrama")


@dataclass(frozen=True)
class Manual:
    id: str
    titulo: str
    marca: str
    modelos: tuple[str, ...]
    familia: str
    tipo: str
    idioma: str
    descripcion: str = ""  # palabras clave en español: ayudan a encontrar planos casi sin texto
    ocr: bool = False  # escaneado: se lee con Tesseract

    @property
    def archivo(self) -> str:
        return f"{self.id}.pdf"


KW = ("KENWORTH", "T800", "T370", "MULA", "TRACTOMULA")
CATALOGO: tuple[Manual, ...] = (
    # --- Tractores Case IH Puma ------------------------------------------------------------------
    Manual(
        "puma165-operador",
        "Manual del operador Case IH Puma 165",
        "Case IH",
        ("PUMA 165", "PUMA"),
        "Tractor",
        "operador",
        "es",
    ),
    Manual(
        "puma165-210-operador-pt",
        "Manual do operador Case IH Puma 165/180/195/210",
        "Case IH",
        ("PUMA 165", "PUMA 180", "PUMA 195", "PUMA 210", "PUMA"),
        "Tractor",
        "operador",
        "pt",
    ),
    Manual(
        "puma190-230-servicio",
        "Manual de servicio Case IH Puma (165–230)",
        "Case IH",
        ("PUMA 165", "PUMA 180", "PUMA 200", "PUMA 230", "PUMA"),
        "Tractor",
        "servicio",
        "es",
    ),
    Manual(
        "puma-calibracion-codigos",
        "Case IH Puma · calibraciones y códigos de falla",
        "Case IH",
        ("PUMA 165", "PUMA 180", "PUMA 200", "PUMA"),
        "Tractor",
        "diagnostico",
        "es",
        "códigos de error falla calibración diagnóstico",
    ),
    # --- John Deere ------------------------------------------------------------------------------
    Manual(
        "jd6165j-tecnico",
        "Manual técnico John Deere 6165J/6180J",
        "John Deere",
        ("6165J", "6180J", "6165", "6180"),
        "Tractor",
        "servicio",
        "pt",
    ),
    Manual(
        "jd2254-operador",
        "Manual del operador · Alzadora (cargadora de caña) John Deere 2254",
        "John Deere",
        ("2254", "ALZADORA", "CARGADORA"),
        "Alzadora",
        "operador",
        "es",
    ),
    Manual(
        "jd2254-partes",
        "Catálogo de partes · Alzadora John Deere 2254 (2009)",
        "John Deere",
        ("2254", "ALZADORA", "CARGADORA"),
        "Alzadora",
        "partes",
        "en",
        "despiece repuestos referencia número de parte",
    ),
    # --- Tractores GAME --------------------------------------------------------------------------
    Manual(
        "game77atx-partes",
        "Manual de partes · Tractor GAME 77ATX (2015)",
        "GAME",
        ("77ATX", "GAME"),
        "Tractor",
        "partes",
        "en",
        "despiece repuestos",
    ),
    # --- Tractomulas Kenworth ----------------------------------------------------------------------
    Manual(
        "kenworth-electrico",
        "Kenworth · Manual eléctrico (KM815070)",
        "Kenworth",
        KW,
        "Tractomula",
        "servicio",
        "en",
        "sistema eléctrico arneses circuitos diagnóstico cortos",
    ),
    Manual(
        "kw-bit-1014-cecu",
        "Boletín BIT-1014 · Solución de problemas tablero CECU y nodo de chasis (Namux III)",
        "Kenworth",
        KW,
        "Tractomula",
        "diagnostico",
        "es",
        "CECU tablero instrumentos nodo chasis Namux",
    ),
    Manual(
        "kw-fusibles",
        "Kenworth · Caja de fusibles y relés de la cabina (mulas)",
        "Kenworth",
        KW,
        "Tractomula",
        "diagrama",
        "en",
        "fusibles fuse relés relay caja de fusibles amperaje radio luces pito limpiaparabrisas cabina mulas",
        ocr=True,
    ),
    Manual(
        "kw-cecu-plano",
        "Kenworth · Plano CECU 3 (unidad electrónica de cabina) Q21-1076",
        "Kenworth",
        KW,
        "Tractomula",
        "diagrama",
        "en",
        "CECU entradas salidas tablero testigos alarmas",
    ),
    Manual(
        "kw-p94-1476",
        "Kenworth T370 · Diagrama del sistema motor Cummins ISC (P94-1476)",
        "Kenworth",
        ("KENWORTH", "T370", "ISC", "CUMMINS"),
        "Tractomula",
        "diagrama",
        "en",
        "diagrama eléctrico motor Cummins ISC ECM sensores",
        ocr=True,
    ),
    Manual(
        "kw-p94-1456",
        "Kenworth T800 · Instrumentación NBI/Namux de cabina, Cat/Cummins (P94-1456)",
        "Kenworth",
        ("KENWORTH", "T800"),
        "Tractomula",
        "diagrama",
        "en",
        "diagrama cabina instrumentación tablero conectores",
        ocr=True,
    ),
    Manual(
        "kw-p94-1585",
        "Kenworth · Diagrama de instrumentación y luces de parqueo (P94-1585)",
        "Kenworth",
        KW,
        "Tractomula",
        "diagrama",
        "en",
        "instrumentación medidores luces de parqueo alimentación cabina testigos",
    ),
    Manual(
        "kw-p94-1896",
        "Kenworth · Diagrama PTO y acelerador remoto, Cummins ISX (P94-1896)",
        "Kenworth",
        ("KENWORTH", "ISX", "CUMMINS"),
        "Tractomula",
        "diagrama",
        "en",
        "toma de fuerza PTO acelerador remoto",
    ),
    Manual(
        "kw-p94-1458",
        "Kenworth · Diagrama de controles de puertas y espejos (P94-1458)",
        "Kenworth",
        KW,
        "Tractomula",
        "diagrama",
        "en",
        "puertas vidrios eléctricos espejos seguros",
    ),
    Manual(
        "kw-p94-1398",
        "Kenworth · Diagrama de luces de reversa, cola y nivel de combustible (P94-1398)",
        "Kenworth",
        KW,
        "Tractomula",
        "diagrama",
        "en",
        "luces de reversa cola stop nivel de combustible",
    ),
    Manual(
        "kw-p94-1389",
        "Kenworth · Diagrama de la bocina eléctrica (pito) (P94-1389)",
        "Kenworth",
        KW,
        "Tractomula",
        "diagrama",
        "en",
        "pito bocina corneta",
    ),
    Manual(
        "kw-p94-1383",
        "Kenworth · Diagrama de distribución de potencia y relés de repuesto (P94-1383)",
        "Kenworth",
        KW,
        "Tractomula",
        "diagrama",
        "en",
        "distribución de potencia relés batería ignición accesorios",
    ),
    Manual(
        "kw-p94-1469",
        "Kenworth · Diagrama de luces interiores de cabina (P94-1469)",
        "Kenworth",
        KW,
        "Tractomula",
        "diagrama",
        "en",
        "luces interiores cabina domo",
    ),
    Manual(
        "kw-c97-1077",
        "Kenworth · Instalación suspensión Primaax EX 462 tándem (C97-1077)",
        "Kenworth",
        KW,
        "Tractomula",
        "diagrama",
        "en",
        "suspensión Primaax tándem torque pernos ejes",
    ),
)
POR_ID = {m.id: m for m in CATALOGO}

# Glosario mínimo español → inglés/portugués para que BM25 cruce idiomas (determinista y explicable).
GLOSARIO: dict[str, str] = {
    "filtro": "filter",
    "aceite": "oil oleo",
    "hidraulico": "hydraulic",
    "motor": "engine",
    "fusible": "fuse",
    "fusibles": "fuse fuses",
    "rele": "relay",
    "reles": "relay relays",
    "bomba": "pump",
    "freno": "brake freio",
    "frenos": "brake brakes freios",
    "transmision": "transmission transmissao",
    "puerta": "door",
    "puertas": "door doors",
    "luz": "lamp light",
    "luces": "lamps lights",
    "pito": "horn",
    "bocina": "horn",
    "corneta": "horn",
    "combustible": "fuel combustivel",
    "refrigerante": "coolant",
    "correa": "belt correia",
    "valvula": "valve",
    "cilindro": "cylinder",
    "rodamiento": "bearing",
    "eje": "axle",
    "llanta": "tire wheel",
    "embrague": "clutch embreagem",
    "arranque": "starter",
    "bateria": "battery",
    "alternador": "alternator",
    "presion": "pressure pressao",
    "temperatura": "temperature",
    "nivel": "level",
    "cambio": "replace change troca",
    "ajuste": "adjust",
    "cadena": "chain",
    "cuchilla": "knife blade",
    "pluma": "boom",
    "cabina": "cab cabine",
    "diagrama": "diagram wiring",
    "electrico": "electrical",
    "codigo": "code",
    "error": "error fault",
    "falla": "fault",
    "mantenimiento": "maintenance service",
    "engrase": "grease lubrication",
    "lubricacion": "lubrication",
    "intervalo": "interval",
    "capacidad": "capacity",
    "tanque": "tank",
    "manguera": "hose",
    "espejo": "mirror",
    "espejos": "mirror mirrors",
    "limpiaparabrisas": "wiper",
    "radio": "radio",
    "reversa": "backup reverse",
    "parqueo": "park",
    "direccionales": "turn signal",
    "suspension": "suspension",
    "sensor": "sensor",
    "agua": "water",
    "aire": "air ar",
    "acondicionado": "conditioning hvac",
    "garra": "grab",
    "grua": "loader crane",
    "toma": "pto",
    "fuerza": "pto power",
    "acelerador": "throttle",
    "tablero": "dash gauge panel",
    "instrumentos": "gauge instrumentation",
    "testigo": "telltale",
    "despiece": "parts",
    "repuesto": "part",
    "repuestos": "parts",
    "alzadora": "loader",
    "cargadora": "loader",
    "tornillo": "bolt screw",
    "torque": "torque",
    "apriete": "torque",
}


def _sin_tildes(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def expandir(consulta: str) -> str:
    """Añade la traducción técnica de cada palabra conocida (``filtro`` → ``filtro filter``)."""
    extra = [GLOSARIO[w] for w in re.findall(r"[a-z0-9]+", _sin_tildes(consulta)) if w in GLOSARIO]
    return " ".join([consulta, *extra])


class PaginaManual(BaseModel):
    id: str
    manual_id: str
    titulo: str
    pagina: int  # 1-based, como la ve un humano
    tipo: str
    idioma: str
    familia: str
    modelos: list[str]
    texto: str
    pagina_figura: int | None = None  # en catálogos de partes: la lámina que acompaña la lista
    ocr: bool = False


class ResultadoManual(BaseModel):
    manual_id: str
    titulo: str
    pagina: int
    pagina_figura: int | None
    tipo: str
    idioma: str
    extracto: str
    score: float
    rank_lexico: int | None = None
    rank_denso: int | None = None


# --------------------------------------------------------------------------- extracción
def _ocr(imagen: Path, idioma: str = "eng") -> str:
    try:
        r = subprocess.run(
            ["tesseract", str(imagen), "-", "-l", idioma, "--psm", "11"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        return r.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def _render(pdf, i: int, max_px: int = 2400):
    page = pdf[i]
    w, h = page.get_size()
    return page.render(scale=max_px / max(w, h)).to_pil()


def extraer_paginas(
    manuales_dir: Path,
    catalogo: Iterable[Manual] = CATALOGO,
    min_palabras: int = 8,
    on_progress: Callable[[str, int], None] | None = None,
) -> list[PaginaManual]:
    import pypdfium2 as pdfium

    paginas: list[PaginaManual] = []
    for m in catalogo:
        ruta = Path(manuales_dir) / m.archivo
        if not ruta.exists():
            continue
        pdf = pdfium.PdfDocument(str(ruta))
        conteos: list[int] = []
        for i in range(len(pdf)):
            texto = pdf[i].get_textpage().get_text_range()
            ocr = False
            if m.ocr and len(texto.split()) < 40:
                with tempfile.TemporaryDirectory() as d:
                    img = Path(d) / "p.png"
                    _render(pdf, i, 3000).save(img)
                    texto, ocr = _ocr(img, "eng+spa"), True
            texto = " ".join(texto.split())
            conteos.append(len(texto.split()))
            if m.tipo == "diagrama":  # planos: el título y la descripción en español son lo buscable
                texto = f"{m.titulo}. {m.descripcion}. {texto}"[:6000]
            elif len(texto.split()) < min_palabras:
                continue
            figura = i if (m.tipo == "partes" and i > 0 and conteos[i - 1] < 60 and conteos[i] >= 60) else None
            paginas.append(
                PaginaManual(
                    id=f"{m.id}:{i + 1}",
                    manual_id=m.id,
                    titulo=m.titulo,
                    pagina=i + 1,
                    tipo=m.tipo,
                    idioma=m.idioma,
                    familia=m.familia,
                    modelos=list(m.modelos),
                    texto=texto[:12000],
                    pagina_figura=figura,
                    ocr=ocr,
                )
            )
        if on_progress:
            on_progress(m.id, len(pdf))
        pdf.close()
    return paginas


def guardar_paginas(paginas: list[PaginaManual], destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8") as f:
        for p in paginas:
            f.write(p.model_dump_json() + "\n")


def cargar_paginas(origen: Path) -> list[PaginaManual]:
    if not Path(origen).exists():
        return []
    with Path(origen).open(encoding="utf-8") as f:
        return [PaginaManual.model_validate_json(linea) for linea in f if linea.strip()]


# --------------------------------------------------------------------------- índice denso (Qdrant)
def _texto_embedding(p: PaginaManual) -> str:
    return f"{p.titulo} · página {p.pagina}\n{p.texto[:1800]}"


def indexar(
    paginas: list[PaginaManual],
    embeddings,
    dims: int,
    client,
    alias: str,
    batch: int = 32,
    on_progress: Callable[[int, int], None] | None = None,
) -> str:
    """Colección versionada nueva + alias (blue/green), como el índice del Módulo 2."""
    import uuid
    from datetime import UTC, datetime

    from qdrant_client import models as qm

    nombre = f"{alias}_{datetime.now(UTC):%Y%m%d%H%M%S}"
    client.create_collection(nombre, vectors_config=qm.VectorParams(size=dims, distance=qm.Distance.COSINE))
    for i in range(0, len(paginas), batch):
        lote = paginas[i : i + batch]
        vecs = embeddings.embed_documents([_texto_embedding(p) for p in lote])
        client.upsert(
            nombre,
            points=[
                qm.PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, p.id)),
                    vector=v,
                    payload={
                        "id": p.id,
                        "manual_id": p.manual_id,
                        "tipo": p.tipo,
                        "familia": p.familia,
                        "modelos": p.modelos,
                    },
                )
                for p, v in zip(lote, vecs, strict=True)
            ],
        )
        if on_progress:
            on_progress(min(i + batch, len(paginas)), len(paginas))
    anterior = next((a.collection_name for a in client.get_aliases().aliases if a.alias_name == alias), None)
    ops = []
    if anterior:
        ops.append(qm.DeleteAliasOperation(delete_alias=qm.DeleteAlias(alias_name=alias)))
    ops.append(qm.CreateAliasOperation(create_alias=qm.CreateAlias(collection_name=nombre, alias_name=alias)))
    client.update_collection_aliases(change_aliases_operations=ops)
    return nombre


# --------------------------------------------------------------------------- búsqueda
def _coincide_modelo(p: PaginaManual, modelo: str | None) -> bool:
    if not modelo:
        return True
    m = re.sub(r"[^A-Z0-9]", "", modelo.upper())
    return any(m in re.sub(r"[^A-Z0-9]", "", x) or re.sub(r"[^A-Z0-9]", "", x) in m for x in p.modelos)


@dataclass
class BuscadorManuales:
    paginas: list[PaginaManual]
    embeddings: object | None = None
    client: object | None = None
    alias: str | None = None
    rrf_k: int = 60
    _bm25: BM25 | None = field(default=None, init=False, repr=False)
    _por_id: dict[str, PaginaManual] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._bm25 = BM25([f"{p.titulo} {' '.join(p.modelos)} {p.texto}" for p in self.paginas])
        self._por_id = {p.id: p for p in self.paginas}

    def _denso(self, consulta: str, permitidos: set[str], limite: int) -> list[str]:
        """Top-k denso en Qdrant con filtro de *payload* por manual (los mismos que deja pasar el filtro léxico)."""
        if not (self.embeddings and self.client and self.alias):
            return []
        try:
            from qdrant_client import models as qm

            manuales = sorted({self._por_id[pid].manual_id for pid in permitidos})
            filtro = qm.Filter(must=[qm.FieldCondition(key="manual_id", match=qm.MatchAny(any=manuales))])
            vec = self.embeddings.embed_query(consulta)
            res = self.client.query_points(self.alias, query=vec, limit=limite, query_filter=filtro, with_payload=True)
        except Exception:  # noqa: BLE001 — sin Qdrant se sigue con la búsqueda léxica
            return []
        return [p.payload["id"] for p in res.points if p.payload.get("id") in permitidos][:limite]

    def buscar(
        self,
        consulta: str,
        modelo: str | None = None,
        tipo: str | None = None,
        k: int = 3,
        candidatos: int = 30,
        modo: str = "hibrida",
    ) -> list[ResultadoManual]:
        """Búsqueda por página. ``modo``: hibrida (BM25+glosario y densa con RRF) | lexica | lexica_sin_glosario | densa."""
        idx = [i for i, p in enumerate(self.paginas) if _coincide_modelo(p, modelo) and (not tipo or p.tipo == tipo)]
        if not idx and modelo:  # el modelo no tiene manual propio: se busca en todo
            idx = [i for i, p in enumerate(self.paginas) if not tipo or p.tipo == tipo]
        permitidos = {self.paginas[i].id for i in idx}
        lex: list[str] = []
        if modo != "densa":
            # Multi-consulta léxica: BM25 de la pregunta tal cual + BM25 con el glosario (inglés/portugués),
            # fusionados con RRF. El glosario rescata los manuales en otro idioma sin diluir los que están en español.
            consultas = [consulta] if modo == "lexica_sin_glosario" else [consulta, expandir(consulta)]
            votos: dict[str, float] = {}
            for c in dict.fromkeys(consultas):
                puntajes = self._bm25.scores(c)
                orden = [self.paginas[i].id for i in sorted(idx, key=lambda i: -puntajes[i]) if puntajes[i] > 0]
                for r, pid in enumerate(orden[:candidatos], 1):
                    votos[pid] = votos.get(pid, 0) + 1 / (self.rrf_k + r)
            lex = sorted(votos, key=lambda pid: -votos[pid])[:candidatos]
        den = self._denso(consulta, permitidos, candidatos) if modo in ("hibrida", "densa") else []
        fusion: dict[str, float] = {}
        for lista in (lex, den):
            for r, pid in enumerate(lista, 1):
                fusion[pid] = fusion.get(pid, 0) + 1 / (self.rrf_k + r)
        orden = sorted(fusion, key=lambda pid: -fusion[pid])[:k]
        terminos = set(tokenize(expandir(consulta)))
        res = []
        for pid in orden:
            p = self._por_id[pid]
            res.append(
                ResultadoManual(
                    manual_id=p.manual_id,
                    titulo=p.titulo,
                    pagina=p.pagina,
                    pagina_figura=p.pagina_figura,
                    tipo=p.tipo,
                    idioma=p.idioma,
                    extracto=_extracto(p.texto, terminos),
                    score=round(fusion[pid], 5),
                    rank_lexico=lex.index(pid) + 1 if pid in lex else None,
                    rank_denso=den.index(pid) + 1 if pid in den else None,
                )
            )
        return res


def _extracto(texto: str, terminos: set[str], largo: int = 700) -> str:
    palabras = texto.split()
    mejor, pos = -1, 0
    for i in range(0, max(1, len(palabras) - 40), 10):
        n = sum(1 for w in palabras[i : i + 60] if tokenize(w) and tokenize(w)[0] in terminos)
        if n > mejor:
            mejor, pos = n, i
    return " ".join(palabras[pos : pos + 110])[:largo]


# --------------------------------------------------------------------------- la foto de la página
def renderizar_pagina(
    manuales_dir: Path, manual_id: str, pagina: int, destino_dir: Path, resaltar: str | None = None, max_px: int = 2200
) -> Path:
    """PNG de la página (en caché). Si se da ``resaltar``, marca en amarillo las palabras buscadas."""
    import pypdfium2 as pdfium
    from PIL import Image, ImageDraw

    m = POR_ID.get(manual_id) or Manual(manual_id, manual_id, "", (), "", "", "")
    clave = re.sub(r"[^a-z0-9]+", "-", _sin_tildes(resaltar or ""))[:40].strip("-")
    destino = Path(destino_dir) / f"{manual_id}_p{pagina}{'_' + clave if clave else ''}.png"
    if destino.exists():
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(Path(manuales_dir) / m.archivo))
    page = pdf[pagina - 1]
    w, h = page.get_size()
    escala = max_px / max(w, h)
    img = page.render(scale=escala).to_pil().convert("RGB")
    if resaltar:
        terminos = {t for t in tokenize(expandir(resaltar)) if len(t) >= 3}
        cajas = _cajas_texto(page, terminos, escala, h) or (_cajas_ocr(img, terminos) if m.ocr else [])
        if cajas:
            capa = img.copy()
            dib = ImageDraw.Draw(capa)
            for x0, y0, x1, y1 in cajas:
                dib.rectangle((x0 - 3, y0 - 3, x1 + 3, y1 + 3), fill=(255, 221, 0))
            img = Image.blend(img, capa, 0.38)
            dib = ImageDraw.Draw(img)
            for x0, y0, x1, y1 in cajas:
                dib.rectangle((x0 - 4, y0 - 4, x1 + 4, y1 + 4), outline=(214, 40, 40), width=3)
    img.save(destino, optimize=True)
    pdf.close()
    return destino


def _cajas_texto(page, terminos: set[str], escala: float, alto: float) -> list[tuple[float, float, float, float]]:
    tp = page.get_textpage()
    texto = tp.get_text_range()
    cajas = []
    for mt in re.finditer(r"[A-Za-zÀ-ÿ0-9]+", texto):
        tok = tokenize(mt.group())
        if not tok or tok[0] not in terminos:
            continue
        x0 = y0 = 1e9
        x1 = y1 = -1e9
        for c in range(mt.start(), mt.end()):
            try:
                a, b, cc, d = tp.get_charbox(c)
            except Exception:  # noqa: BLE001
                continue
            x0, y0, x1, y1 = min(x0, a), min(y0, b), max(x1, cc), max(y1, d)
        if x1 > x0:
            cajas.append((x0 * escala, (alto - y1) * escala, x1 * escala, (alto - y0) * escala))
        if len(cajas) >= 60:
            break
    return cajas


def _cajas_ocr(img, terminos: set[str]) -> list[tuple[float, float, float, float]]:
    with tempfile.TemporaryDirectory() as d:
        ruta = Path(d) / "p.png"
        img.save(ruta)
        try:
            tsv = subprocess.run(
                ["tesseract", str(ruta), "-", "-l", "eng", "--psm", "11", "tsv"],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            ).stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []
    cajas = []
    for linea in tsv.splitlines()[1:]:
        c = linea.split("\t")
        if len(c) < 12 or not c[11].strip():
            continue
        tok = tokenize(c[11])
        if tok and tok[0] in terminos:
            x, y, w, h = map(float, c[6:10])
            cajas.append((x, y, x + w, y + h))
    return cajas


def resumen_catalogo(paginas: list[PaginaManual] | None = None) -> list[dict]:
    n: dict[str, int] = {}
    for p in paginas or []:
        n[p.manual_id] = n.get(p.manual_id, 0) + 1
    return [
        {
            "id": m.id,
            "titulo": m.titulo,
            "familia": m.familia,
            "tipo": m.tipo,
            "idioma": m.idioma,
            "modelos": list(m.modelos),
            "paginas_indexadas": n.get(m.id, 0),
        }
        for m in CATALOGO
    ]


def guardar_json(datos, destino: Path) -> None:
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
