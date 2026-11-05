#!/usr/bin/env python3
"""Markdown convertido -> Trechos limpos em JSONL, prontos para indexação no RAG.

Não altera os .md convertidos, o manifesto nem os status de revisão. Cada Trecho
pertence a uma única página física do PDF, para que a citação aponte a página exata.
Os status de revisão e aprovação são copiados do manifesto: quem indexa decide se
aceita fontes pendentes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "corpus/nutricao/rag"
CONFIG_PATH = ROOT / "corpus/scripts/config/rag.yaml"
TARGET_CHARS = 1000
MAX_CHARS = 1400
MIN_CHARS = 80
RUNNING_HEADER_MAX_CHARS = 200
RUNNING_HEADER_MIN_PAGES = 4

# Seções sem conteúdo científico a recuperar. Descartadas até o próximo título.
# Aceita numeração antes do título ("9. BIBLIOGRAFIA", "9.BIBLIOGRAFIA").
SKIPPED_SECTIONS = re.compile(
    r"^(\d+(\.\d+)*\.?\s*)?"
    r"(refer[eê]ncias( bibliogr[aá]ficas)?|bibliografia|colaboradores|abstract|resumen|[ií]ndice|sum[aá]rio)$",
    re.I,
)
# Linhas de cabeçalho/rodapé de periódico e numeração solta.
NOISE_LINE = re.compile(
    r"^(\d{1,4}|DOI:?\s*\S+|Artigos? Originais?|artigo article"
    r"|Rev Saúde Pública \d{4};.*|Ciênc\.? Saúde Colet.*)$",
    re.I,
)
PAGE_MARK = re.compile(r"<!-- PDF_PAGE: (\d+) -->")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def repo_path(value: str) -> Path:
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"Caminho fora do repositório: {value}")
    return path


def split_pages(markdown: str) -> list[tuple[int, str]]:
    """Separa por marcador de página, descartando o cabeçalho de conversão."""
    parts = PAGE_MARK.split(markdown)
    return [(int(parts[i]), parts[i + 1]) for i in range(1, len(parts), 2)]


def clean_inline(line: str) -> str:
    line = re.sub(r"<sup>.*?</sup>", "", line)
    line = re.sub(r"<br\s*/?>", " ", line)
    line = re.sub(r"</?[a-z][^>]*>", "", line)
    line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)
    line = re.sub(r"[*_`]{1,3}", "", line)
    # Ligaturas quebradas pela extração do PDF ("signifi cativo" -> "significativo").
    line = re.sub(r"(?<=[A-Za-zà-ú])(ffi|ffl|fi|fl) (?=[a-zà-ú]+\b)", r"\1", line)
    line = re.sub(r"(?<![A-Za-zà-ú])(fi|fl) (?=[a-zà-ú]{3,})", r"\1", line)
    line = re.sub(r"\s+", " ", line).strip()
    return unicodedata.normalize("NFC", line)


def clean_page(raw: str, skipping: bool, section: str) -> tuple[list[tuple[str, str, bool]], bool, str]:
    """Devolve (seção, parágrafo, é_linha_de_tabela), se segue em seção descartada e a seção corrente."""
    paragraphs: list[tuple[str, str, bool]] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            paragraphs.append((section, " ".join(current), False))
            current.clear()

    for line in raw.splitlines():
        stripped = line.strip()
        if (not stripped or stripped == "---" or stripped.startswith("<a id=")
                or stripped.startswith("<!--") or stripped.startswith("> **Nota de conversão")
                or stripped.startswith("[Conferir no original]")
                or re.match(r"^##\s+Página PDF \d+\s*$", stripped)):
            flush()
            continue
        heading = re.match(r"^#{1,6}\s+(.*)$", stripped)
        if heading:
            flush()
            title = clean_inline(heading.group(1))
            skipping = bool(SKIPPED_SECTIONS.match(title.strip(" .:")))
            if title and not skipping:
                section = title
            continue
        if skipping:
            continue
        if re.match(r"^\|[\s:|-]+\|?$", stripped):  # separador de tabela
            continue
        if stripped.startswith("|"):  # linha de tabela: uma por linha, sem barras
            flush()
            cells = [clean_inline(c) for c in stripped.strip("|").split("|")]
            row = " | ".join(c for c in cells if c)
            if row:
                paragraphs.append((section, row, True))
            continue
        text = clean_inline(stripped)
        if not text or NOISE_LINE.match(text):
            continue
        current.append(text)
    flush()
    return paragraphs, skipping, section


def split_long(paragraph: str) -> list[str]:
    """Divide parágrafos maiores que MAX_CHARS em fronteiras de frase."""
    if len(paragraph) <= MAX_CHARS:
        return [paragraph]
    sentences = re.split(r"(?<=[.!?;])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9])", paragraph)
    pieces: list[str] = []
    buffer = ""
    for sentence in sentences:
        if buffer and len(buffer) + 1 + len(sentence) > TARGET_CHARS:
            pieces.append(buffer)
            buffer = sentence
        else:
            buffer = f"{buffer} {sentence}".strip()
    if buffer:
        pieces.append(buffer)
    return pieces


def chunk_page(paragraphs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Junta parágrafos curtos até ~TARGET_CHARS, sem atravessar página nem seção."""
    chunks: list[tuple[str, str]] = []
    buffer, buffer_section = "", ""
    for section, paragraph in paragraphs:
        for piece in split_long(paragraph):
            if buffer and (section != buffer_section or len(buffer) + 2 + len(piece) > TARGET_CHARS):
                chunks.append((buffer_section, buffer))
                buffer = piece
            else:
                buffer = f"{buffer}\n\n{piece}".strip()
            buffer_section = section
    if buffer:
        chunks.append((buffer_section, buffer))
    return chunks


def prepare(source: dict) -> dict:
    markdown_path = repo_path(source["markdown_path"])
    markdown = markdown_path.read_text(encoding="utf-8")
    report = json.loads(repo_path(source["report_path"]).read_text(encoding="utf-8"))
    if sha256_text(markdown) != report["markdown_sha256"]:
        raise ValueError(f"Markdown mudou após a conversão: {markdown_path.name}")

    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    drop = [re.compile(p) for p in config.get(source["id"], {}).get("drop_paragraphs", [])]
    records: list[dict] = []
    skipping, section = False, ""
    discarded_short = 0
    cleaned = []
    for page, raw in split_pages(markdown):
        paragraphs, skipping, section = clean_page(raw, skipping, section)
        cleaned.append((page, [(s, p, t) for s, p, t in paragraphs if not any(rx.search(p) for rx in drop)]))
    # Cabeçalhos e rodapés correntes: parágrafo curto que se repete em várias páginas.
    # Linhas de tabela ficam de fora: cabeçalhos de coluna repetidos são conteúdo.
    pages_by_text: dict[str, set[int]] = {}
    for page, paragraphs in cleaned:
        for _, paragraph, is_table in paragraphs:
            if not is_table and len(paragraph) < RUNNING_HEADER_MAX_CHARS:
                pages_by_text.setdefault(paragraph, set()).add(page)
    running = {text for text, pages in pages_by_text.items() if len(pages) >= RUNNING_HEADER_MIN_PAGES}
    for page, paragraphs in cleaned:
        paragraphs = [(s, p) for s, p, t in paragraphs if t or p not in running]
        for number, (chunk_section, text) in enumerate(chunk_page(paragraphs), 1):
            if len(text) < MIN_CHARS:
                discarded_short += 1
                continue
            records.append({
                "id": f"{source['id']}-p{page:03d}-{number:02d}",
                "fonte_id": source["id"],
                "titulo_fonte": source["title"],
                "pagina_pdf": page,
                "secao": chunk_section,
                "texto": text,
                "licenca": source["license"],
                "review_status": source["review_status"],
                "approval_status": source["approval_status"],
            })

    output = OUTPUT_DIR / f"{markdown_path.stem}.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8"
    )
    sizes = sorted(len(r["texto"]) for r in records)
    return {
        "arquivo": str(output.relative_to(ROOT)),
        "trechos": len(records),
        "descartados_curtos": discarded_short,
        "paginas_com_trecho": len({r["pagina_pdf"] for r in records}),
        "tamanho_min_mediana_max": [sizes[0], sizes[len(sizes) // 2], sizes[-1]] if sizes else [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="corpus/manifest.yaml")
    parser.add_argument("--source", help="Processa somente o identificador informado")
    args = parser.parse_args()
    try:
        manifest = yaml.safe_load(repo_path(args.manifest).read_text(encoding="utf-8"))
        sources = [s for s in manifest["sources"] if not args.source or s["id"] == args.source]
        if not sources:
            raise ValueError("Nenhuma fonte selecionada.")
        for source in sources:
            print(f"{source['id']}: {json.dumps(prepare(source), ensure_ascii=False)}")
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
