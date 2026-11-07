#!/usr/bin/env python3
"""PDFs públicos -> Markdown por página + relatório auditável, sem exportar imagens.

Não modifica PDFs, manifesto ou status de revisão. Não usa LLM generativo.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata

import pymupdf
import yaml
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
OCR_URL = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/por.traineddata"
OCR_SHA256 = "c4932b937207a9514b7514d518b931a99938c02a28a5a5a553f8599ed58b7deb"
SPARSE_LIMIT = 150


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repo_path(value: str) -> Path:
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"Caminho fora do repositório: {value}")
    return path


def relative_link(target: Path, parent: Path) -> str:
    return Path(os.path.relpath(target, parent)).as_posix()


def read_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def download(url: str, target: Path, expected_sha: str | None, *, pdf=False) -> None:
    """Baixa para arquivo temporário; valida antes de criar o destino, sem substituir."""
    if target.exists():
        raise FileExistsError(target)
    if not url.startswith("https://"):
        raise ValueError("Downloads exigem HTTPS.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cultiva-download-") as temporary:
        candidate = Path(temporary) / "download"
        subprocess.run(
            ["curl", "--fail", "--location", "--silent", "--show-error",
             "--proto", "=https", "--proto-redir", "=https", "--retry", "2",
             "--connect-timeout", "20", "--max-time", "180", url,
             "--output", str(candidate)], check=True,
        )
        if expected_sha and sha256(candidate) != expected_sha:
            raise ValueError(f"SHA-256 divergente em {url}; não substituir a edição catalogada.")
        if pdf:
            validate_pdf(candidate)
        with target.open("xb") as destination, candidate.open("rb") as source:
            shutil.copyfileobj(source, destination)


def validate_pdf(path: Path) -> None:
    with path.open("rb") as stream:
        if not stream.read(5) == b"%PDF-":
            raise ValueError(f"Não é PDF (possível página de login/erro): {path}")
    with pymupdf.open(path) as doc:
        if not doc.is_pdf or doc.needs_pass or not doc.page_count:
            raise ValueError(f"PDF vazio, protegido ou inválido: {path}")


def tokens(text: str) -> Counter:
    """Auditoria lexical, NÃO medida de fidelidade semântica ou ordem de leitura."""
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<[^>]*>|[_*~`]", " ", text)
    return Counter(re.findall(r"[^\W_]+", text))


def clean_markdown(text: str) -> str:
    # Só espaços de fim de linha e excesso de linhas vazias. Sem reescrever frases.
    return re.sub(r"\n{3,}", "\n\n", "\n".join(line.rstrip() for line in text.splitlines())).strip()


def ocr_region(page, region: dict, tessdata: Path) -> tuple[str, bytes]:
    """OCR local via Tesseract integrado ao MuPDF; original permanece intocado."""
    clip = pymupdf.Rect(region.get("bbox", page.rect))
    pix = page.get_pixmap(clip=clip, dpi=300, colorspace=pymupdf.csRGB)
    if region.get("rotation") or region.get("invert"):
        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        if region.get("invert"):
            im = ImageOps.invert(im.convert("L"))
        if region.get("rotation"):
            im = im.rotate(region["rotation"], expand=True, fillcolor=255)
        buffer = io.BytesIO()
        im.save(buffer, format="PNG")
        pix = pymupdf.Pixmap(buffer.getvalue())
    pix.set_dpi(300, 300)
    data = pix.pdfocr_tobytes(language="por", tessdata=str(tessdata))
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return doc[0].get_text(), data


def convert(source: dict, args) -> dict:
    original = repo_path(source["original_path"])
    markdown = repo_path(source["markdown_path"])
    report_path = repo_path(source["report_path"])
    if original in [markdown, report_path] or markdown == report_path:
        raise ValueError("Caminhos de originais e derivados não podem se sobrepor.")
    if not original.exists():
        if not args.download:
            raise FileNotFoundError(f"PDF ausente: {original}. Use --download.")
        download(source.get("download_url", source["source"]), original,
                 source.get("sha256"), pdf=True)
    validate_pdf(original)
    digest = sha256(original)
    if source.get("sha256") and source["sha256"] != digest:
        raise ValueError(f"SHA-256 do original diverge do manifesto: {source['id']}")
    destinations = [markdown, report_path]
    if any(path.exists() for path in destinations) and not args.overwrite:
        raise FileExistsError("Saídas já existem; use --overwrite somente para regenerar derivados.")
    if source.get("approval_status", "pendente") != "pendente":
        raise ValueError("Conversão requer approval_status pendente no manifesto: fonte aprovada fica fixada.")
    config = read_yaml(repo_path(source["conversion_config"])) if source.get("conversion_config") else {}
    if config and config.get("sha256") != digest:
        raise ValueError("Ajustes não correspondem ao SHA-256 deste PDF.")

    with pymupdf.open(original) as doc:
        if source.get("pdf_pages") and source["pdf_pages"] != len(doc):
            raise ValueError("Quantidade de páginas diverge do manifesto.")
        # Valida também páginas de ajustes para não ignorar silenciosamente erros de configuração.
        configured_pages = set(config.get("page_overrides", {})) | set(config.get("sparse_page_decisions", {}))
        configured_pages |= set(config.get("page_notes", {})) | set(config.get("strip_false_strikethrough_pages", []))
        configured_pages |= {item["page"] for item in config.get("ocr_regions", []) + config.get("replacements", [])}
        if any(not isinstance(n, int) or n < 1 or n > len(doc) for n in configured_pages):
            raise ValueError("Página de ajuste fora do PDF.")
        native = [page.get_text() for page in doc]
        sparse_pages = [n for n, text in enumerate(native, 1) if len(text.strip()) < SPARSE_LIMIT]
        auto_ocr_pages = [n for n in sparse_pages if n not in config.get("sparse_page_decisions", {})]
        requires_ocr = bool(auto_ocr_pages or config.get("ocr_regions"))
        tessdata = Path(args.tessdata).resolve()
        traineddata = tessdata / "por.traineddata"
        if requires_ocr:
            if not traineddata.exists() and args.download_ocr:
                download(OCR_URL, traineddata, OCR_SHA256)
            if not traineddata.exists() or sha256(traineddata) != OCR_SHA256:
                raise ValueError("Modelo OCR ausente ou divergente; use --download-ocr e --tessdata.")
        chunks = doc.to_markdown(
            page_chunks=True, use_ocr=False, header=True, footer=True,
            force_text=True, write_images=False,
        )
        if len(chunks) != len(doc):
            raise ValueError("Extração não retornou todas as páginas.")
        original_link = relative_link(original, markdown.parent)
        report_link = relative_link(report_path, markdown.parent)
        report = {
            "source_id": source["id"], "source_sha256": digest,
            "pdf_pages": len(doc), "conversion_status": "concluida_com_ressalvas",
            "script_sha256": sha256(Path(__file__)),
            "config_sha256": sha256(repo_path(source["conversion_config"])) if config else None,
            "versions": {name: importlib.metadata.version(name) for name in
                         ["PyMuPDF", "pymupdf4llm", "PyYAML", "Pillow", "onnxruntime", "numpy"]},
            "method": "PyMuPDF Layout local; texto nativo, OCR pontual e ajustes explícitos; imagens consultadas no PDF",
            "sparse_threshold_characters": SPARSE_LIMIT,
            "ocr_model": {"url": OCR_URL, "sha256": OCR_SHA256} if requires_ocr else None,
            "limitations": [
                "Cobertura lexical não prova fidelidade, ordem, semântica ou ausência de erros.",
                "Hierarquia de títulos, capitalização, colunas e composição gráfica são aproximadas.",
                "Fotos e diagramas permanecem no PDF original, acessível pelos links de página; nenhum PNG é exportado.",
                "A detecção de pouco texto é heurística; documentos mistos também exigem inspeção visual.",
                "Conversão e conferência amostral não aprovam a fonte nem substituem revisão integral.",
            ], "pages": [],
        }
        output = [
            "---", yaml.safe_dump({"source_id": source["id"], "title": source["title"],
                "source": source["source"], "license": source["license"],
                "source_sha256": digest},
                allow_unicode=True, sort_keys=False).strip(), "---", "",
            f"# {source['title']}", "",
            f"Instituição(ões): {', '.join(source['institutions'])}. Edição: {source['version']}.", "",
            f"[PDF original preservado]({original_link}) · [Relatório por página]({report_link})", "",
            "> Conversão documental para revisão. As orientações abaixo pertencem à publicação original. "
            "Não constituem recomendações produzidas pelo CULTIVA. Revisão e aprovação da fonte pendentes.", "",
            "Marcadores usam a posição física no PDF, começando em 1; a numeração impressa pode diferir. "
            "Notas de conversão são identificadas como acréscimos editoriais. "
            "Figuras e composição visual podem ser conferidas no PDF pelos links de página.", "",
        ]
        for number, chunk in enumerate(chunks, 1):
            if chunk["metadata"]["page_number"] != number:
                raise ValueError("Páginas retornadas fora de ordem.")
            text = chunk["text"]
            page = doc[number - 1]
            item = {"pdf_page": number, "native_characters": len(native[number - 1]),
                    "method": "native", "tables_detected": sum(
                        box["class"] == "table" for box in chunk["page_boxes"]),
                    "warnings": [], "adjustments": [], "ocr": []}
            if number in sparse_pages:
                item["sparse_page_decision"] = config.get("sparse_page_decisions", {}).get(number, "OCR automático por pouco texto nativo")
            if number in auto_ocr_pages:
                raw, data = ocr_region(page, {}, tessdata)
                with pymupdf.open(stream=data, filetype="pdf") as ocr_doc:
                    text = ocr_doc.to_markdown(use_ocr=False, force_text=True, write_images=False)
                item["method"] = "ocr_full_page"
                item["ocr"].append({"label": "Página inteira", "raw_text": raw})
                item["warnings"].append("OCR automático: conferir integralmente; pode haver fotografia ou página sem texto.")
            for region in config.get("ocr_regions", []):
                if region["page"] != number:
                    continue
                raw, _ = ocr_region(page, region, tessdata)
                item["ocr"].append({"label": region["label"], "bbox": region["bbox"],
                                    "raw_text": raw, "verified_text": region.get("verified_text"),
                                    "note": region["note"]})
                item["warnings"].append(region["note"])
                if region.get("verified_text"):
                    text += "\n\n<!-- Transcrição pontual de elemento visual; ver relatório OCR. -->\n\n"
                    text += region["verified_text"] + "\n"
                # OCR auxiliar impreciso permanece no relatório, nunca misturado à orientação.
            for replacement in config.get("replacements", []):
                if replacement["page"] != number:
                    continue
                count = text.count(replacement["old"])
                if count != replacement.get("count", 1):
                    raise ValueError(f"Ajuste da página {number}: esperado 1 trecho, encontrados {count}.")
                text = text.replace(replacement["old"], replacement["new"])
                item["adjustments"].append(replacement)
            if number in config.get("strip_false_strikethrough_pages", []):
                item["adjustments"].append({"removed_false_strikethrough_markers": text.count("~~")})
                text = text.replace("~~", "")
            override = config.get("page_overrides", {}).get(number)
            if override:
                text = repo_path(override).read_text(encoding="utf-8")
                item["adjustments"].append({"page_override": override, "sha256": sha256(repo_path(override))})
            note = config.get("page_notes", {}).get(number)
            if note:
                item["warnings"].append(note)
            raw_tokens = tokens(native[number - 1])
            missing = raw_tokens - tokens(text)
            item["native_word_coverage"] = round(1 - sum(missing.values()) / max(1, sum(raw_tokens.values())), 5)
            item["missing_native_tokens"] = dict(sorted(missing.items()))
            if item["native_word_coverage"] < 0.98:
                item["warnings"].append("Cobertura lexical inferior a 98%: conferir perdas, palavras partidas ou texto não visível na camada nativa.")
            text = clean_markdown(text)
            item["markdown_characters"] = len(text)
            output.extend([f'<a id="pagina-pdf-{number:03d}"></a>', f"<!-- PDF_PAGE: {number} -->",
                           f"## Página PDF {number}", "", f"[Conferir no original]({original_link}#page={number})", ""])
            for warning in item["warnings"]:
                output.extend([f"> **Nota de conversão — página {number}:** {warning}", ""])
            output.extend([text or "<!-- Página sem texto extraível; consultar PDF original. -->", "", "---", ""])
            report["pages"].append(item)
        rendered = "\n".join(output).rstrip() + "\n"
        report["markdown_sha256"] = hashlib.sha256(rendered.encode()).hexdigest()
        report["summary"] = {
            "pages_converted": len(chunks), "sparse_pages": sparse_pages,
            "ocr_pages": [p["pdf_page"] for p in report["pages"] if p["ocr"]],
            "pages_with_tables_detected": [p["pdf_page"] for p in report["pages"] if p["tables_detected"]],
            "pages_with_warnings": [p["pdf_page"] for p in report["pages"] if p["warnings"]],
            "pages_with_adjustments": [p["pdf_page"] for p in report["pages"] if p["adjustments"]],
        }
        if sha256(original) != digest:
            raise ValueError("Original alterado durante a conversão.")
        # Só publica os derivados após concluir todas as páginas e os ajustes estritos.
        markdown.parent.mkdir(parents=True, exist_ok=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(rendered, encoding="utf-8")
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report["summary"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="corpus/manifest.yaml")
    parser.add_argument("--source", help="Converte somente o identificador informado")
    parser.add_argument("--download", action="store_true", help="Baixa originais ausentes; nunca substitui existentes")
    parser.add_argument("--download-ocr", action="store_true", help="Baixa modelo OCR português ausente, validando SHA-256")
    parser.add_argument("--tessdata", default=str(ROOT / "corpus/.cache/tessdata"))
    parser.add_argument("--overwrite", action="store_true", help="Regenera Markdown e relatórios; preserva PDFs")
    args = parser.parse_args()
    try:
        manifest = read_yaml(repo_path(args.manifest))
        if manifest.get("version") != 1 or not isinstance(manifest.get("sources"), list):
            raise ValueError("Manifesto precisa ter version: 1 e sources como lista.")
        sources = [s for s in manifest["sources"] if not args.source or s["id"] == args.source]
        if not sources:
            raise ValueError("Nenhuma fonte selecionada.")
        if len({s["id"] for s in sources}) != len(sources):
            raise ValueError("Identificadores de fonte duplicados.")
        for source in sources:
            summary = convert(source, args)
            print(f"{source['id']}: {json.dumps(summary, ensure_ascii=False)}", flush=True)
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
