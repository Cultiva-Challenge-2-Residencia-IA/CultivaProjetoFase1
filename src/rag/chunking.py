from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    source_id: str
    section: str
    text: str
    chunk_id: str


def normalize_markdown(raw: str) -> str:
    """Remove PDF conversion noise and normalize Markdown without destroying headings."""
    if raw is None:
        return ""

    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    cleaned_lines: list[str] = []

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("[Imagem:") or line.startswith("[Imagem"):
            continue
        if re.fullmatch(r"(Página|Page)\s+\d+", line, flags=re.IGNORECASE):
            continue
        if re.fullmatch(r"\d+", line):
            continue

        cleaned_lines.append(re.sub(r"\s+", " ", line))

    normalized = "\n\n".join(cleaned_lines).strip()
    return re.sub(r"\n{3,}", "\n\n", normalized)


def _split_sections(text: str) -> list[tuple[str, str]]:
    if not text.strip():
        return []

    blocks = re.split(r"(?=^#+\s)", text, flags=re.MULTILINE)
    sections: list[tuple[str, str]] = []
    current_title = "documento"
    current_body: list[str] = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        heading_match = re.match(r"^(#+)\s+(.*)$", block, flags=re.MULTILINE)
        if heading_match:
            if current_body:
                section_text = "\n\n".join(current_body).strip()
                if section_text:
                    sections.append((current_title, section_text))
                current_body = []
            current_title = heading_match.group(2).strip() or "documento"
            rest = block[heading_match.end():].strip()
            if rest:
                current_body.append(rest)
            continue

        if block:
            current_body.append(block)

    if current_body:
        section_text = "\n\n".join(current_body).strip()
        if section_text:
            sections.append((current_title, section_text))

    if not sections:
        sections.append(("documento", text.strip()))

    return sections


def _section_text(title: str, body: str) -> str:
    if title and title.lower() != "documento":
        return f"## {title}\n\n{body}".strip()
    return body.strip()


def chunk_markdown(source_id: str, text: str, max_chars: int = 1200, overlap: int = 180) -> list[Chunk]:
    normalized = normalize_markdown(text)
    if not normalized:
        return []

    sections = _split_sections(normalized)
    chunks: list[Chunk] = []

    for title, body in sections:
        working_text = _section_text(title, body)
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", working_text) if part.strip()]
        current_buffer: list[str] = []
        current_length = 0

        for paragraph in paragraphs:
            paragraph_length = len(paragraph)
            if current_buffer and current_length + paragraph_length > max_chars:
                chunk_text = "\n\n".join(current_buffer).strip()
                if chunk_text:
                    chunks.append(_build_chunk(source_id, title, chunk_text))
                current_buffer = [paragraph]
                current_length = paragraph_length
            else:
                current_buffer.append(paragraph)
                current_length += paragraph_length

        if current_buffer:
            chunk_text = "\n\n".join(current_buffer).strip()
            if chunk_text:
                chunks.append(_build_chunk(source_id, title, chunk_text))

    if not chunks:
        chunks.append(_build_chunk(source_id, "documento", normalized))

    return chunks


def _build_chunk(source_id: str, section: str, text: str) -> Chunk:
    digest = hashlib.sha256(f"{source_id}:{section}:{text}".encode("utf-8")).hexdigest()[:16]
    return Chunk(source_id=source_id, section=section, text=text, chunk_id=f"{source_id}-{digest}")
