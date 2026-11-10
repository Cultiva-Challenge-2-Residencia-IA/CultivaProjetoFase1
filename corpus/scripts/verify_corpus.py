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
