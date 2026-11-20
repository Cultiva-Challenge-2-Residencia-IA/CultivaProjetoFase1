#!/usr/bin/env python3
"""Converte originais HTML selecionados para Markdown candidato à revisão."""

from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import sys

from bs4 import BeautifulSoup, NavigableString
from markdownify import MarkdownConverter
import yaml

from convert_pdfs import ROOT, read_yaml, repo_path, sha256


class HTMLMarkdownConverter(MarkdownConverter):
    """Mantém texto alternativo de figuras sem exportar arquivos de imagem."""

    def convert_img(self, el, text, parent_tags):
        alt = el.get("alt", "").strip()
        src = el.get("src", "").strip()
        label = alt or "imagem sem descrição textual"
        if src:
            return f"\n> Figura: {label} (imagem no original HTML: {src})\n\n"
        return f"\n> Figura: {label} (consulte o original HTML)\n\n"


def relative_link(target: Path, parent: Path) -> str:
    return Path(os.path.relpath(target, parent)).as_posix()


def convert(source: dict, *, overwrite: bool = False) -> dict:
    original = repo_path(source["original_path"])
    markdown = repo_path(source["markdown_path"])
    report_path = repo_path(source["report_path"])
    if original.suffix.lower() not in {".html", ".htm"}:
        raise ValueError(f"Original não é HTML: {source['id']}")
    if not original.exists():
        raise FileNotFoundError(original)
    if sha256(original) != source["sha256"]:
        raise ValueError(f"SHA-256 do original diverge do manifesto: {source['id']}")
    if any(path.exists() for path in (markdown, report_path)) and not overwrite:
        raise FileExistsError(f"Saídas já existem para {source['id']}; use --overwrite.")
    if source.get("approval_status", "pendente") != "pendente":
        raise ValueError("Conversão requer approval_status pendente.")

    html = original.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    selector = source["content_selector"]
    content = soup.select_one(selector)
    if content is None:
        raise ValueError(f"Seletor de conteúdo não encontrado ({selector}): {source['id']}")
    tables = len(content.find_all("table"))
    images = len(content.find_all("img"))
    for inline in content.find_all(["strong", "b", "em", "i"]):
        if inline.get_text() and inline.get_text().isspace():
            inline.replace_with(NavigableString(" "))
    for element in content.select("script, style, noscript, nav, footer, .share, .social-media"):
        element.decompose()
    body = HTMLMarkdownConverter(
        heading_style="ATX", bullets="-",
        escape_underscores=False, escape_asterisks=False,
    ).convert(str(content))
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(line.rstrip() for line in body.splitlines())).strip()

    digest = sha256(original)
    original_link = relative_link(original, markdown.parent)
    report_link = relative_link(report_path, markdown.parent)
    frontmatter = {
        "source_id": source["id"], "title": source["title"],
        "source": source["source"], "license": source["license"],
        "source_sha256": digest,
    }
    output = [
        "---", yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip(), "---", "",
        f"# {source['title']}", "",
        f"Instituição(ões): {', '.join(source['institutions'])}. Edição: {source['version']}.", "",
        f"[Original HTML preservado]({original_link}) · [Relatório de conversão]({report_link})", "",
        "> Conversão documental para revisão. O conteúdo pertence à publicação original e não é uma recomendação produzida pelo CULTIVA. "
        "A conversão e a aprovação da fonte permanecem pendentes.", "",
        "> Confira no original as tabelas, figuras, links e a estrutura do documento; a conversão não garante fidelidade semântica.", "",
        body, "",
    ]
    rendered = "\n".join(output)
    report = {
        "source_id": source["id"], "source_sha256": digest,
        "markdown_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
        "script_sha256": sha256(Path(__file__)),
        "converter": "markdownify",
        "converter_version": version("markdownify"),
        "beautifulsoup_version": version("beautifulsoup4"),
        "content_selector": selector, "html_tables": tables, "html_images": images,
        "limitations": [
            "Cabeçalhos, tabelas e links podem perder estrutura ou relações semânticas durante a conversão.",
            "Figuras não são copiadas; o texto alternativo e a referência ao HTML original são mantidos quando disponíveis.",
            "A conversão estrutural e a checagem de hashes não substituem conferência integral contra o original.",
            "A fonte continua pendente de revisão e aprovação.",
        ],
    }
    if sha256(original) != digest:
        raise ValueError("Original HTML alterado durante a conversão.")
    markdown.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text(rendered, encoding="utf-8")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Identificador da fonte no manifesto")
    parser.add_argument("--overwrite", action="store_true", help="Regenera somente Markdown e relatório")
    args = parser.parse_args()
    try:
        manifest = read_yaml(ROOT / "corpus/manifest.yaml")
        sources = [s for s in manifest["sources"] if s["id"] == args.source]
        if len(sources) != 1:
            raise ValueError(f"Fonte não encontrada ou identificador duplicado: {args.source}")
        report = convert(sources[0], overwrite=args.overwrite)
        print(f"{args.source}: {json.dumps(report, ensure_ascii=False)}")
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
