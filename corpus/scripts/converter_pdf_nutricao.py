from __future__ import annotations

import argparse
import re
from pathlib import Path

import pymupdf


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "corpus/nutricao/posicionamento_2022-alterado-nov-22-1.pdf"
TARGET = ROOT / "src/agents/nutricao/posicionamento_2022-alterado-nov-22-1.md"
def clean_text(value: str) -> str:
    value = value.replace("\u00a0", " ").replace("\u00ad", "")
    value = value.replace("ﬁ", "fi").replace("ﬂ", "fl").replace("ﬃ", "ffi")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def render_line(line: dict) -> str:
    fragments: list[str] = []
    previous_right: float | None = None
    previous_size = 10.0
    previous_trailing_space = False
    for span in line["spans"]:
        raw_text = span["text"]
        text = clean_text(raw_text)
        if not text:
            continue
        x0 = span["bbox"][0]
        if fragments and previous_right is not None:
            if (
                previous_trailing_space
                or raw_text[:1].isspace()
                or x0 - previous_right > max(0.7, previous_size * 0.08)
            ):
                fragments.append(" ")
        flags = span["flags"]
        if flags & 16 and flags & 2:
            text = f"***{text}***"
        elif flags & 16:
            text = f"**{text}**"
        elif flags & 2:
            text = f"*{text}*"
        fragments.append(text)
        previous_right = span["bbox"][2]
        previous_size = span["size"]
        previous_trailing_space = raw_text[-1:].isspace()
    return clean_text("".join(fragments))


def table_of_contents(page: pymupdf.Page) -> list[dict]:
    clip = pymupdf.Rect(20, 40, page.rect.width - 25, page.rect.height - 60)
    raw_lines = page.get_text("text", clip=clip, flags=pymupdf.TEXT_DEHYPHENATE).splitlines()
    entries = []
    pending_number = ""
    for raw_line in raw_lines:
        line = clean_text(raw_line).strip()
        if not line or line.upper() in {"ÍNDICE", "SUMÁRIO"}:
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?", line):
            pending_number = line
            continue
        page_match = re.search(r"\.{2,}\s*(\d{1,3})\s*$", line)
        has_number = bool(page_match)
        if page_match:
            line = line[:page_match.start()].strip()
        else:
            line = re.sub(r"\.{2,}\s*$", "", line).strip()
        if pending_number:
            line = f"{pending_number} {line}"
            pending_number = ""
        line = re.sub(r"^\d{1,2}\s+(?=\d+\.\s)", "", line)
        if not line:
            continue
        # Linhas sem número no início geralmente continuam o título anterior no índice.
        if entries and not re.match(r"(?:\d+(?:\.\d+)*\.?\s+|Apresentação|Métodos|Introdução|Considerações)", line):
            entries[-1]["text"] += " " + line
            continue
        match = re.match(r"^(\d+(?:\.\d+)*)\.?\s+", line)
        depth = max(0, match.group(1).count(".")) if match else 0
        entries.append({"bbox": pymupdf.Rect(0, len(entries), 1, len(entries) + 1), "kind": "text", "text": f"{'  ' * depth}- {line}"})
    return entries


def heading_level(text: str, spans: list[dict]) -> int | None:
    plain = re.sub(r"\*{1,3}", "", text).strip()
    chapter = re.match(r"^CAP[IÍ]TULO\s+\d+(?:\.(\d+))?\b", plain, re.I)
    if chapter:
        return 3 if chapter.group(1) else 2

    normalized = clean_text(plain).strip(" .:").upper()
    major_titles = {
        "INTRODUÇÃO", "APRESENTAÇÃO", "MÉTODOS", "METODOLOGIA",
        "CONSIDERAÇÕES FINAIS", "CONCLUSÃO", "CONCLUSÕES",
        "REFERÊNCIAS", "ÍNDICE", "SUMÁRIO",
    }
    if normalized in major_titles:
        return 2

    sizes = [span["size"] for span in spans]
    letters = [char for char in plain if char.isalpha()]
    uppercase_ratio = sum(char.isupper() for char in letters) / max(len(letters), 1)
    if max(sizes, default=0) >= 18 and len(plain) < 120:
        return 2
    if len(plain) < 140 and uppercase_ratio > 0.82 and max(sizes, default=0) >= 10.5:
        return 3
    if len(plain) < 110 and max(sizes, default=0) >= 12 and all(span["flags"] & 16 for span in spans):
        return 4
    return None


def extract_table(page: pymupdf.Page, table: pymupdf.table.Table) -> str:
    words = page.get_text("words", flags=pymupdf.TEXT_DEHYPHENATE)
    rows: list[list[str]] = []
    for table_row in table.rows:
        cells: list[str] = []
        for cell_box in table_row.cells:
            if cell_box is None:
                cells.append("")
                continue
            rect = pymupdf.Rect(cell_box)
            contained = [
                word for word in words
                if rect.contains(pymupdf.Point((word[0] + word[2]) / 2, (word[1] + word[3]) / 2))
            ]
            contained.sort(key=lambda word: (round(word[1] / 3), word[0]))
            lines: list[tuple[int, list[str]]] = []
            for word in contained:
                y = round(word[1] / 3)
                if not lines or lines[-1][0] != y:
                    lines.append((y, []))
                lines[-1][1].append(word[4])
            cells.append("<br>".join(" ".join(parts) for _, parts in lines))
        rows.append(cells)

    if not rows:
        return ""
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    nonempty_columns = [column for column in range(width) if any(row[column] for row in rows)]
    rows = [[row[column] for column in nonempty_columns] for row in rows]
    if not rows or not rows[0]:
        return ""

    def escape(value: str) -> str:
        return value.replace("|", "\\|").strip()

    headers = rows[0]
    output = ["| " + " | ".join(escape(value) for value in headers) + " |"]
    output.append("| " + " | ".join("---" for _ in headers) + " |")
    output.extend("| " + " | ".join(escape(value) for value in row) + " |" for row in rows[1:])
    return "\n".join(output)


def extract_recommendation_table(page: pymupdf.Page) -> dict | None:
    anchors = page.search_for("Recomendação diária para ingestão adequada")
    if not anchors:
        return None

    table_box = pymupdf.Rect(76, 222, 610, 398)
    words = [
        word for word in page.get_text("words", flags=pymupdf.TEXT_DEHYPHENATE)
        if table_box.contains(pymupdf.Point((word[0] + word[2]) / 2, (word[1] + word[3]) / 2))
        and word[1] >= 245
    ]
    grouped_rows: list[tuple[float, list[tuple]]] = []
    for word in sorted(words, key=lambda value: (value[1], value[0])):
        if not grouped_rows or word[1] - grouped_rows[-1][0] > 2:
            grouped_rows.append((word[1], []))
        grouped_rows[-1][1].append(word)

    rows = []
    for _, row_words in grouped_rows:
        cells = [[], [], [], []]
        for word in sorted(row_words, key=lambda value: value[0]):
            x = word[0]
            column = 0 if x < 260 else 1 if x < 395 else 2 if x < 500 else 3
            cells[column].append(word[4])
        values = [" ".join(cell).strip() for cell in cells]
        if any(values):
            rows.append(values)

    if not rows:
        return None

    headers = [
        "Faixa etária",
        "Água total (alimentos e bebidas, L/dia)",
        "Bebidas (incluindo água, L/dia)",
        "Bebidas (copos/dia)",
    ]
    escape = lambda value: value.replace("|", "\\|").strip()
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    output.extend("| " + " | ".join(escape(value) for value in row) + " |" for row in rows)
    return {"bbox": table_box, "kind": "table", "text": "\n".join(output)}


def extract_water_balance_table(page: pymupdf.Page) -> dict | None:
    if not page.search_for("Tabela 2: Balanço hídrico"):
        return None

    rows = [
        ("Fonte", "Produção (mL/dia)", "Perda (mL/dia)"),
        ("Respiratória", "", "250 a 350"),
        ("Urinária", "", "1.000 a 2.000"),
        ("Fecal", "", "100 a 200"),
        ("Insensíveis/suor", "", "450 a 900"),
        ("Produção metabólica", "250 a 350", ""),
        ("Total (aproximado)", "250 a 350", "1.800 a 3.450"),
        ("Balanço", "", "-1.500 a -3.100"),
    ]
    output = ["| " + " | ".join(rows[0]) + " |", "| --- | --- | --- |"]
    output.extend("| " + " | ".join(row) + " |" for row in rows[1:])
    return {
        "bbox": pymupdf.Rect(78, 290, 335, 510),
        "kind": "table",
        "text": "\n".join(output),
    }


def page_items(page: pymupdf.Page) -> list[dict]:
    data = page.get_text("dict", flags=pymupdf.TEXT_DEHYPHENATE)
    raw_page_text = page.get_text("text", flags=pymupdf.TEXT_DEHYPHENATE)
    dotted_lines = sum("...." in line for line in raw_page_text.splitlines())
    if dotted_lines >= 5 and re.search(r"\b(?:ÍNDICE|SUMÁRIO)\b", raw_page_text, re.I):
        return table_of_contents(page)

    tables = []
    recommendation_table = extract_recommendation_table(page)
    if recommendation_table:
        tables.append(recommendation_table)
    water_balance_table = extract_water_balance_table(page)
    if water_balance_table:
        tables.append(water_balance_table)
    try:
        for table in page.find_tables(strategy="lines").tables:
            if any(pymupdf.Rect(table.bbox).intersects(existing["bbox"]) for existing in tables):
                continue
            text = extract_table(page, table)
            if text:
                tables.append({"bbox": pymupdf.Rect(table.bbox), "kind": "table", "text": text})
    except Exception:
        pass

    diagram_rects = []
    if not tables:
        for drawing in page.get_drawings():
            rect = pymupdf.Rect(drawing["rect"])
            area = rect.width * rect.height
            if 60000 <= area <= page.rect.width * page.rect.height * 0.75 and rect.y0 >= 400:
                diagram_rects.append(rect)

    texts = []
    for block in data["blocks"]:
        if "lines" not in block:
            continue
        bbox = pymupdf.Rect(block["bbox"])
        lines = []
        kept_spans = []
        for line in block["lines"]:
            spans = []
            raw_line = clean_text("".join(span["text"] for span in line["spans"]))
            line_box = pymupdf.Rect(line["spans"][0]["bbox"]) if line["spans"] else pymupdf.Rect(0, 0, 0, 0)
            if (
                re.search(r"\.indd\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b", raw_line, re.I)
                or (
                    re.fullmatch(r"\d{1,3}", raw_line)
                    and (line_box.y0 < 80 or line_box.y1 > page.rect.height - 80)
                )
            ):
                continue
            for span in line["spans"]:
                span_box = pymupdf.Rect(span["bbox"])
                center = pymupdf.Point((span_box.x0 + span_box.x1) / 2, (span_box.y0 + span_box.y1) / 2)
                if span_box.x0 < 20 or span_box.x1 > page.rect.width - 20:
                    continue
                if center.y < 45 or center.y > page.rect.height - 28:
                    continue
                if any(table["bbox"].contains(center) for table in tables):
                    continue
                if any(rect.contains(center) for rect in diagram_rects):
                    continue
                spans.append(span)
                kept_spans.append(span)
            if spans:
                value = render_line({"spans": spans})
                if value:
                    lines.append(value)
        if not lines:
            continue
        text = re.sub(r"\s+([,.;:!?%)\]])", r"\1", " ".join(lines))
        text = clean_text(text)
        text = re.sub(r"\*([^*]+)-\*\s+\*([a-zà-ÿ][^*]*)\*", r"*\1\2*", text)
        text = re.sub(r"(?<=[A-Za-zÀ-ÿ])[-‐]\s+(?=[a-zà-ÿ])", "", text)
        if not text:
            continue
        level = heading_level(text, kept_spans)
        if level:
            text = re.sub(r"\*{1,3}", "", text)
            text = f"{'#' * level} {text}"
        texts.append({"bbox": bbox, "kind": "text", "text": text})

    visuals = []
    page_has_image = False
    for image in page.get_images(full=True):
        for rect_tuple in page.get_image_rects(image[0]):
            rect = pymupdf.Rect(rect_tuple)
            if rect.width * rect.height > 5000:
                page_has_image = True
                break
        if page_has_image:
            break
    if page_has_image:
        visuals.append({
            "bbox": pymupdf.Rect(0, page.rect.height - 1, 1, page.rect.height),
            "kind": "visual",
            "text": "[Imagem: ilustração ou fotografia presente nesta página.]",
        })

    if not tables:
        for rect in diagram_rects:
            labels = []
            for block in data["blocks"]:
                if "lines" not in block or not rect.intersects(pymupdf.Rect(block["bbox"])):
                    continue
                label = clean_text(" ".join(
                    span["text"] for line in block["lines"] for span in line["spans"]
                ))
                if label and label not in labels:
                    labels.append(label)
            if len(labels) >= 4:
                visuals.append({
                    "bbox": rect,
                    "kind": "visual",
                    "text": f"[Diagrama: {'; '.join(labels[:8])}.]",
                })
                break

    # Uma letra capitular é o início ampliado de um parágrafo, não um subtítulo.
    filtered_texts = []
    for index, item in enumerate(texts):
        plain = re.sub(r"\*{1,3}", "", item["text"]).strip()
        plain = re.sub(r"^#+\s*", "", plain)
        spans = [
            span
            for block in data["blocks"]
            if "lines" in block and pymupdf.Rect(block["bbox"]).intersects(item["bbox"])
            for line in block["lines"]
            for span in line["spans"]
        ]
        if len(plain) == 1 and plain.isalpha() and max((span["size"] for span in spans), default=0) >= 20:
            next_item = next((
                candidate for candidate in texts[index + 1:]
                if candidate["kind"] == "text" and not candidate["text"].startswith("#")
            ), None)
            if next_item:
                separator = " " if next_item["text"][:1].isupper() else ""
                next_item["text"] = plain + separator + next_item["text"]
                continue
        filtered_texts.append(item)
    texts = filtered_texts

    items = texts + tables + visuals
    if not items:
        if page.get_images() or page.get_drawings():
            return [{
                "bbox": pymupdf.Rect(0, 0, page.rect.width, page.rect.height),
                "kind": "visual",
                "text": "[Imagem: página ilustrada sem texto extraível.]",
            }]
        return []

    center = page.rect.width / 2
    left = [item for item in texts if item["bbox"].x1 < center + 8]
    right = [item for item in texts if item["bbox"].x0 > center - 8]
    two_columns = len(left) >= 2 and len(right) >= 2
    if not two_columns:
        return sorted(items, key=lambda item: (item["bbox"].y0, item["bbox"].x0))

    separators = tables + visuals + [item for item in texts if item not in left and item not in right]
    separators.sort(key=lambda item: item["bbox"].y0)
    ordered = []
    previous_y = 0.0
    for separator in separators:
        y = separator["bbox"].y0
        ordered.extend(sorted(
            [item for item in left if previous_y <= item["bbox"].y0 < y],
            key=lambda item: item["bbox"].y0,
        ))
        ordered.extend(sorted(
            [item for item in right if previous_y <= item["bbox"].y0 < y],
            key=lambda item: item["bbox"].y0,
        ))
        ordered.append(separator)
        previous_y = separator["bbox"].y1
    ordered.extend(sorted([item for item in left if item["bbox"].y0 >= previous_y], key=lambda item: item["bbox"].y0))
    ordered.extend(sorted([item for item in right if item["bbox"].y0 >= previous_y], key=lambda item: item["bbox"].y0))
    ordered.extend(item for item in items if item not in left and item not in right and item not in separators)
    return ordered


def document_title(document: pymupdf.Document, fallback: str) -> str:
    first_page = document[0]
    spans = [
        span
        for block in first_page.get_text("dict")["blocks"]
        if "lines" in block
        for line in block["lines"]
        for span in line["spans"]
        if clean_text(span["text"])
    ]
    if not spans:
        return fallback
    largest_size = max(span["size"] for span in spans)
    title_spans = sorted(
        (span for span in spans if span["size"] >= largest_size * 0.9),
        key=lambda span: (span["bbox"][1], span["bbox"][0]),
    )
    title = clean_text(" ".join(span["text"] for span in title_spans))
    return title or fallback


def main(source: Path = SOURCE, target: Path | None = None) -> None:
    source = source.expanduser().resolve()
    if target is None:
        target = ROOT / "src/agents/nutricao" / f"{source.stem}.md"
    else:
        target = target.expanduser().resolve()
    document = pymupdf.open(source)
    title = document_title(document, source.stem.replace("_", " "))
    output = [
        f"# {title}",
        "",
        "*Transcrição estruturada a partir do PDF fornecido. Quebras de linha artificiais e elementos repetitivos de paginação foram removidos; páginas ilustradas sem texto extraível recebem marcadores.*",
        "",
    ]
    table_count = 0
    for page_number, page in enumerate(document, start=1):
        items = page_items(page)
        if not items:
            continue
        page_output = []
        for item in items:
            text = item["text"].strip()
            if not text:
                continue
            if page_number == 1 and clean_text(re.sub(r"^#+\s*", "", text)).casefold() == title.casefold():
                continue
            if page_number == 1 and text.startswith("#### "):
                text = f"**Autores:** {text[5:]}"
            if item["kind"] == "table":
                table_count += 1
                page_output.extend(["", text, ""])
            else:
                page_output.append(text)
        if page_output:
            output.append("\n".join(page_output).strip())
    result = re.sub(r"\n{3,}", "\n\n", "\n\n".join(output)).strip() + "\n"
    result = re.sub(r"\*\*([A-Za-zÀ-ÿ])\*\*(?=[a-zà-ÿ])", r"\1", result)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result, encoding="utf-8")
    try:
        displayed_target = target.relative_to(ROOT)
    except ValueError:
        displayed_target = target
    print(f"Arquivo criado: {displayed_target}")
    print(f"Páginas processadas: {len(document)} | Tabelas convertidas: {table_count}")
    print(f"Caracteres: {len(result):,} | Bytes: {target.stat().st_size:,}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Converte um PDF de nutrição para Markdown.")
    parser.add_argument("source", nargs="?", type=Path, default=SOURCE)
    parser.add_argument("--output", "-o", type=Path)
    arguments = parser.parse_args()
    main(arguments.source, arguments.output)
