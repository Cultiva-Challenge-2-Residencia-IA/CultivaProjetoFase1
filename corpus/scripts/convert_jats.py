#!/usr/bin/env python3
"""Converte artigos em JATS XML (texto integral do Europe PMC/PMC) para Markdown candidato à revisão.

Usado quando o PDF e a página HTML do editor bloqueiam o acesso automático, mas o texto integral de
acesso aberto está na API oficial do Europe PMC (issue #99). Cada `<sec>` vira um título (nível 2
nas seções de topo), parágrafos viram parágrafos, tabelas viram linhas de tabela Markdown e figuras
viram uma linha com a legenda. Só a biblioteca padrão (`xml.etree`), sem parser extra.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

import yaml

from convert_html import relative_link
from convert_pdfs import ROOT, read_yaml, repo_path, sha256


def _texto(el: ET.Element) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def _tabela(wrap: ET.Element) -> list[str]:
    linhas = []
    rotulo = " ".join(_texto(e) for e in (wrap.find("label"), wrap.find("caption")) if e is not None)
    if rotulo:
        linhas += [f"**{rotulo}**", ""]
    for tr in wrap.iter("tr"):
        celulas = [_texto(c).replace("|", "/") for c in tr if c.tag in ("td", "th")]
        if any(celulas):
            linhas.append("| " + " | ".join(celulas) + " |")
    return linhas + [""]


def _bloco(el: ET.Element, nivel: int) -> list[str]:
    saida: list[str] = []
    for filho in el:
        if filho.tag == "title":
            continue
        if filho.tag == "sec":
            titulo = filho.find("title")
            if titulo is not None and _texto(titulo):
                saida += [f"{'#' * min(nivel, 6)} {_texto(titulo)}", ""]
            saida += _bloco(filho, nivel + 1)
        elif filho.tag == "p":
            # Tabelas e figuras dentro do parágrafo saem depois dele.
            internos = [e for e in filho if e.tag in ("table-wrap", "fig")]
            for interno in internos:
                filho.remove(interno)
            if _texto(filho):
                saida += [_texto(filho), ""]
            for interno in internos:
                saida += _tabela(interno) if interno.tag == "table-wrap" else _figura(interno)
        elif filho.tag == "table-wrap":
            saida += _tabela(filho)
        elif filho.tag == "fig":
            saida += _figura(filho)
        elif filho.tag == "list":
            saida += [f"- {_texto(item)}" for item in filho.iter("list-item")] + [""]
    return saida


def _figura(fig: ET.Element) -> list[str]:
    legenda = " ".join(_texto(e) for e in (fig.find("label"), fig.find("caption")) if e is not None)
    return [f"> Figura: {legenda or 'sem legenda'} (consulte o original)", ""]


def convert(source: dict, *, overwrite: bool = False) -> dict:
    original = repo_path(source["original_path"])
    markdown = repo_path(source["markdown_path"])
    report_path = repo_path(source["report_path"])
    if sha256(original) != source["sha256"]:
        raise ValueError(f"SHA-256 do original diverge do manifesto: {source['id']}")
    if any(p.exists() for p in (markdown, report_path)) and not overwrite:
        raise FileExistsError(f"Saídas já existem para {source['id']}; use --overwrite.")
    if source.get("approval_status", "pendente") != "pendente":
        raise ValueError("Conversão requer approval_status pendente.")
    raiz = ET.parse(original).getroot()
    corpo = raiz.find("body")
    if corpo is None:
        raise ValueError(f"JATS sem <body> (texto integral ausente): {source['id']}")
    resumo = raiz.find("front/article-meta/abstract")
    linhas: list[str] = []
    if resumo is not None:
        linhas += ["## Abstract", ""] + _bloco(resumo, 3)
    linhas += _bloco(corpo, 2)
    corpo_md = re.sub(r"\n{3,}", "\n\n", "\n".join(linhas)).strip()
    digest = sha256(original)
    frontmatter = {"source_id": source["id"], "title": source["title"], "source": source["source"],
                   "license": source["license"], "source_sha256": digest}
    rendered = "\n".join([
        "---", yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip(), "---", "",
        f"# {source['title']}", "",
        f"Instituição(ões): {', '.join(source['institutions'])}. Edição: {source['version']}.", "",
        f"[Original JATS XML preservado]({relative_link(original, markdown.parent)}) · "
        f"[Relatório de conversão]({relative_link(report_path, markdown.parent)})", "",
        "> Conversão documental para revisão. O conteúdo pertence à publicação original e não é uma recomendação "
        "produzida pelo CULTIVA.", "",
        "> Confira no original as tabelas, figuras e a estrutura do documento; a conversão não garante fidelidade "
        "semântica.", "",
        corpo_md, "",
    ])
    report = {
        "source_id": source["id"], "source_sha256": digest,
        "markdown_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
        "script_sha256": sha256(Path(__file__)), "converter": "xml.etree (JATS)",
        "jats_secoes": len(list(corpo.iter("sec"))), "jats_tabelas": len(list(raiz.iter("table-wrap"))),
        "jats_figuras": len(list(raiz.iter("fig"))),
        "limitations": [
            "Tabelas viram linhas de texto; células mescladas e notas de rodapé de tabela podem perder estrutura.",
            "Figuras não são copiadas; só a legenda é mantida.",
            "Referências bibliográficas do <back> não são convertidas.",
        ],
    }
    markdown.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text(rendered, encoding="utf-8")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", required=True, help="Identificador da fonte no manifesto (kind: jats)")
    parser.add_argument("--overwrite", action="store_true", help="Regenera Markdown e relatório")
    args = parser.parse_args()
    try:
        fontes = [s for s in read_yaml(ROOT / "corpus/manifest.yaml")["sources"] if s["id"] == args.source]
        if len(fontes) != 1 or fontes[0].get("kind") != "jats":
            raise ValueError(f"Fonte não encontrada ou não é kind: jats: {args.source}")
        print(f"{args.source}: {json.dumps(convert(fontes[0], overwrite=args.overwrite), ensure_ascii=False)[:300]}")
        return 0
    except (OSError, ValueError, KeyError, ET.ParseError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
