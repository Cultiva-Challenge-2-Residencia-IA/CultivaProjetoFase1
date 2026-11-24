#!/usr/bin/env python3
"""Confere integridade e rastreabilidade dos derivados; não aprova seu conteúdo."""

import json
from pathlib import Path
import re
import sys

from convert_pdfs import ROOT, read_yaml, repo_path, sha256, validate_pdf
import pymupdf
import verify_trechos


def verify() -> None:
    manifest = read_yaml(ROOT / "corpus/manifest.yaml")
    for source in manifest["sources"]:
        if source.get("kind") == "original_only":
            if source.get("acquisition_status") != "original_obtido":
                print(f"PENDENTE {source['id']}: original não obtido; {source.get('acquisition_note', '')}".rstrip())
                continue
            original = repo_path(source["original_path"])
            if sha256(original) != source["sha256"]:
                raise ValueError(f"Original divergente: {source['id']}")
            if original.suffix.lower() == ".pdf":
                validate_pdf(original)
            elif original.suffix.lower() in {".html", ".htm"}:
                content = original.read_bytes().removeprefix(b"\xef\xbb\xbf").lstrip().lower()  # BOM UTF-8 é válido
                if not (content.startswith(b"<!doctype html") or content.startswith(b"<html")):
                    raise ValueError(f"Original HTML inválido: {source['id']}")
            else:
                raise ValueError(f"Formato original não reconhecido: {source['id']}")
            if source.get("markdown_path") or source.get("report_path"):
                if not source.get("markdown_path") or not source.get("report_path"):
                    raise ValueError(f"Derivados candidatos exigem Markdown e relatório: {source['id']}")
                markdown = repo_path(source["markdown_path"])
                report = json.loads(repo_path(source["report_path"]).read_text(encoding="utf-8"))
                if report["source_sha256"] != source["sha256"] or sha256(markdown) != report["markdown_sha256"]:
                    raise ValueError(f"Original ou Markdown divergente: {source['id']}")
                text = markdown.read_text(encoding="utf-8")
                if original.suffix.lower() == ".pdf":
                    if report["script_sha256"] != sha256(Path(__file__).with_name("convert_pdfs.py")):
                        raise ValueError("Script mudou após a conversão; regenere os candidatos com "
                                         "convert_pdfs.py --candidatos --overwrite.")
                    if (source.get("conversion_config")
                            and report["config_sha256"] != sha256(repo_path(source["conversion_config"]))):
                        raise ValueError(f"Configuração mudou após a conversão: {source['id']}")
                    with pymupdf.open(original) as doc:
                        count = len(doc)
                    pages = [int(n) for n in re.findall(r"<!-- PDF_PAGE: (\d+) -->", text)]
                    if (pages != list(range(1, count + 1)) or source.get("pdf_pages") != count
                            or report["pdf_pages"] != count
                            or report["summary"]["pages_converted"] != count
                            or [page["pdf_page"] for page in report["pages"]] != pages):
                        raise ValueError(f"Páginas ausentes ou divergentes: {source['id']}")
                    if re.search(r"!\[[^\]]*\]\(", text):
                        raise ValueError("Markdown contém imagem exportada; usar os links de página do PDF.")
                    for number in pages:
                        if f".pdf#page={number})" not in text:
                            raise ValueError(f"Link ao PDF ausente na página {number}.")
                    print(f"OK derivados candidatos {source['id']}: {count} páginas; hashes, marcadores e links conferidos; revisão pendente.")
                elif original.suffix.lower() in {".html", ".htm"}:
                    if report["script_sha256"] != sha256(Path(__file__).with_name("convert_html.py")):
                        raise ValueError("Script HTML mudou após a conversão; regenerar ou registrar revisão separadamente.")
                    if (report["content_selector"] != source.get("content_selector")
                            or original.name not in text or "Conversão documental para revisão" not in text):
                        raise ValueError(f"Metadados ou link do original ausentes no Markdown: {source['id']}")
                    print(f"OK derivados candidatos {source['id']}: HTML/Markdown e hashes conferidos; revisão pendente.")
                else:
                    raise ValueError(f"Formato com derivados candidato não suportado: {source['id']}")
            print(f"OK original {source['id']}: formato e SHA-256 conferidos; revisão pendente.")
            continue
        if source.get("kind") == "html":
            # Fonte HTML indexada (kind: html): mesmas conferências do candidato HTML; Trechos por seção.
            original = repo_path(source["original_path"])
            markdown = repo_path(source["markdown_path"])
            report = json.loads(repo_path(source["report_path"]).read_text(encoding="utf-8"))
            content = original.read_bytes().removeprefix(b"\xef\xbb\xbf").lstrip().lower()  # BOM UTF-8 é válido
            if not (content.startswith(b"<!doctype html") or content.startswith(b"<html")):
                raise ValueError(f"Original HTML inválido: {source['id']}")
            if sha256(original) != source["sha256"] or report["source_sha256"] != source["sha256"]:
                raise ValueError(f"Original divergente: {source['id']}")
            if sha256(markdown) != report["markdown_sha256"]:
                raise ValueError(f"Markdown mudou após a conversão: {markdown}")
            if report["script_sha256"] != sha256(Path(__file__).with_name("convert_html.py")):
                raise ValueError("Script HTML mudou após a conversão; regenere com convert_html.py --overwrite.")
            text = markdown.read_text(encoding="utf-8")
            if report["content_selector"] != source.get("content_selector") or original.name not in text:
                raise ValueError(f"Metadados ou link do original ausentes no Markdown: {source['id']}")
            print(f"OK {source['id']}: HTML; SHA-256 do original e do Markdown e script conferidos.")
            continue
        if source.get("kind") == "jats":
            # Artigo em JATS XML (texto integral do Europe PMC): Trechos por seção, como o HTML.
            original = repo_path(source["original_path"])
            markdown = repo_path(source["markdown_path"])
            report = json.loads(repo_path(source["report_path"]).read_text(encoding="utf-8"))
            inicio = original.read_bytes().lstrip()[:200]
            if not (inicio.startswith(b"<?xml") or inicio.startswith(b"<article")):
                raise ValueError(f"Original JATS inválido: {source['id']}")
            if sha256(original) != source["sha256"] or report["source_sha256"] != source["sha256"]:
                raise ValueError(f"Original divergente: {source['id']}")
            if sha256(markdown) != report["markdown_sha256"]:
                raise ValueError(f"Markdown mudou após a conversão: {markdown}")
            if report["script_sha256"] != sha256(Path(__file__).with_name("convert_jats.py")):
                raise ValueError("Script JATS mudou após a conversão; regenere com convert_jats.py --overwrite.")
            if original.name not in markdown.read_text(encoding="utf-8"):
                raise ValueError(f"Link do original ausente no Markdown: {source['id']}")
            print(f"OK {source['id']}: JATS XML; SHA-256 do original e do Markdown e script conferidos.")
            continue
        if source.get("kind", "pdf") == "resumo_pubmed":
            raw = repo_path(source["raw_path"])
            if sha256(raw) != source["raw_sha256"]:
                raise ValueError(f"JSON de origem divergente: {source['id']}")
            continue
        original = repo_path(source["original_path"])
        markdown = repo_path(source["markdown_path"])
        report = json.loads(repo_path(source["report_path"]).read_text(encoding="utf-8"))
        validate_pdf(original)
        if sha256(original) != source["sha256"] or report["source_sha256"] != source["sha256"]:
            raise ValueError(f"Original divergente: {source['id']}")
        if sha256(markdown) != report["markdown_sha256"]:
            raise ValueError(f"Markdown mudou após a conversão: {markdown}")
        if report["script_sha256"] != sha256(Path(__file__).with_name("convert_pdfs.py")):
            raise ValueError("Script mudou após a conversão; regenerar ou registrar revisão separadamente.")
        if source.get("conversion_config") and report["config_sha256"] != sha256(repo_path(source["conversion_config"])):
            raise ValueError("Configuração mudou após a conversão.")
        with pymupdf.open(original) as doc:
            count = len(doc)
        text = markdown.read_text(encoding="utf-8")
        pages = [int(n) for n in re.findall(r"<!-- PDF_PAGE: (\d+) -->", text)]
        if pages != list(range(1, count + 1)):
            raise ValueError("Páginas ausentes, duplicadas ou fora de ordem no Markdown.")
        if (source["pdf_pages"] != count or report["pdf_pages"] != count
                or report["summary"]["pages_converted"] != count
                or [p["pdf_page"] for p in report["pages"]] != pages):
            raise ValueError("Contagem de páginas divergente.")
        for page in report["pages"]:
            for adjustment in page["adjustments"]:
                if "page_override" in adjustment and sha256(repo_path(adjustment["page_override"])) != adjustment["sha256"]:
                    raise ValueError("Transcrição pontual mudou após a conversão.")
        if re.search(r"!\[[^\]]*\]\(", text):
            raise ValueError("Markdown contém imagem exportada; usar os links de página do PDF.")
        for number in pages:
            if f".pdf#page={number})" not in text:
                raise ValueError(f"Link ao PDF ausente na página {number}.")
        print(f"OK {source['id']}: {count} páginas; SHA-256, marcadores e links ao PDF conferidos; sem imagens exportadas.")
    resumos = [s for s in manifest["sources"] if s.get("kind", "pdf") == "resumo_pubmed"]
    if resumos:
        print(f"OK {len(resumos)} resumos do PubMed: SHA-256 do JSON de origem conferido.")
    verify_trechos.verify(manifest)
    print("Esta verificação estrutural não substitui revisão de fidelidade ou aprovação das fontes.")


if __name__ == "__main__":
    try:
        verify()
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise SystemExit(1)
