#!/usr/bin/env python3
"""Confere se os Trechos JSONL correspondem ao manifesto e à origem atual; não aprova conteúdo.

Falha quando um JSONL falta, foi editado à mão, ficou para trás em relação ao Markdown
(ou ao JSON do PubMed), ao `prepare_rag.py` ou à seção da fonte no `rag.yaml`, ou quando
um Trecho diverge dos campos do manifesto ou aponta página fora do PDF. Só usa a
biblioteca padrão e o PyYAML, para rodar também no pytest.
"""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import sys

import yaml

from prepare_rag import (
    GENERATION_PATH,
    OUTPUT_DIR,
    ROOT,
    SCRIPT_PATH,
    load_rag_config,
    sha256_file,
    source_config_sha256,
)

MANIFEST_PATH = ROOT / "corpus/manifest.yaml"
COMANDO = "corpus/.venv/bin/python corpus/scripts/prepare_rag.py --source {id}"


def _campos_do_manifesto(source: dict) -> dict:
    """Campos do Trecho copiados do manifesto, com as mesmas regras do prepare_rag.py."""
    url = str(source["source"])
    if source.get("kind", "pdf") == "pdf" and not url.startswith(("http://", "https://")):
        url = None
    return {
        "fonte_id": source["id"],
        "titulo_fonte": source["title"],
        "instituicoes": list(source["institutions"]),
        "ano": int(source["year"]),
        "tipo_fonte": source.get("source_type"),
        "fonte_url": url,
        "doi": source.get("doi"),
        "licenca": source["license"],
        "approval_status": source["approval_status"],
    }


def _ler_jsonl(path: Path) -> list[dict]:
    return [json.loads(linha) for linha in path.read_text(encoding="utf-8").splitlines() if linha.strip()]


def _conferir_trechos(source: dict, trechos: list[dict], esperado: int) -> list[str]:
    problemas: list[str] = []
    campos = _campos_do_manifesto(source)
    e_pdf = source.get("kind", "pdf") == "pdf"
    if not trechos:
        problemas.append("nenhum Trecho no JSONL")
    if len(trechos) != esperado:
        problemas.append(f"{len(trechos)} Trechos no JSONL, {esperado} registrados em geracao.json")
    divergentes: dict[str, int] = defaultdict(int)
    ids: set[str] = set()
    for trecho in trechos:
        for campo, valor in campos.items():
            if trecho.get(campo) != valor:
                divergentes[campo] += 1
        tid = trecho.get("id", "")
        if tid in ids:
            problemas.append(f"id repetido: {tid}")
        ids.add(tid)
        pagina = trecho.get("pagina_pdf")
        if e_pdf:
            if not isinstance(pagina, int) or not 1 <= pagina <= source["pdf_pages"]:
                problemas.append(f"{tid}: pagina_pdf {pagina!r} fora de 1..{source['pdf_pages']}")
            elif not tid.startswith(f"{source['id']}-p{pagina:03d}-"):
                problemas.append(f"{tid}: id não corresponde à fonte e à página {pagina}")
        else:
            if pagina is not None:
                problemas.append(f"{tid}: resumo sem PDF com pagina_pdf {pagina!r}")
            if not tid.startswith(f"{source['id']}-resumo-"):
                problemas.append(f"{tid}: id não corresponde à fonte")
    for campo, quantos in sorted(divergentes.items()):
        problemas.append(f"{campo} diverge do manifesto em {quantos} Trecho(s) (manifesto: {campos[campo]!r})")
    return problemas


def problemas_dos_trechos(manifest: dict, root: Path = ROOT,
                          generation_path: Path = GENERATION_PATH,
                          rag_dir: Path = OUTPUT_DIR) -> dict[str, list[str]]:
    """Problemas encontrados, agrupados por id de fonte (ou pelo caminho de um JSONL órfão)."""
    if not generation_path.exists():
        return {"geracao.json": [f"{generation_path.relative_to(root)} ausente; rode prepare_rag.py sem --source"]}
    geracao = json.loads(generation_path.read_text(encoding="utf-8"))["fontes"]
    config = load_rag_config()
    script_sha = sha256_file(SCRIPT_PATH)
    problemas: dict[str, list[str]] = defaultdict(list)
    cache_jsonl: dict[Path, list[dict]] = {}
    ids_manifesto = {s["id"] for s in manifest["sources"]}

    for source in manifest["sources"]:
        sid = source["id"]
        entrada = geracao.get(sid)
        if entrada is None:
            problemas[sid].append("fonte sem registro em geracao.json (JSONL nunca gerado)")
            continue
        jsonl = root / entrada["jsonl_path"]
        if not jsonl.exists():
            problemas[sid].append(f"JSONL ausente: {entrada['jsonl_path']}")
            continue
        if sha256_file(jsonl) != entrada["jsonl_sha256"]:
            problemas[sid].append("JSONL editado depois da geração")
        if source.get("kind", "pdf") == "pdf":
            atual = sha256_file(root / source["markdown_path"])
            if entrada.get("markdown_sha256") != atual:
                problemas[sid].append("Markdown mudou depois da geração dos Trechos")
        elif entrada.get("raw_sha256") != source["raw_sha256"]:
            problemas[sid].append("JSON de origem do PubMed mudou depois da geração dos Trechos")
        if entrada["prepare_rag_sha256"] != script_sha:
            problemas[sid].append("prepare_rag.py mudou depois da geração dos Trechos")
        if entrada["rag_config_sha256"] != source_config_sha256(config, sid):
            problemas[sid].append("seção da fonte no rag.yaml mudou depois da geração dos Trechos")
        if jsonl not in cache_jsonl:
            cache_jsonl[jsonl] = _ler_jsonl(jsonl)
        trechos = [t for t in cache_jsonl[jsonl] if t.get("fonte_id") == sid]
        problemas[sid].extend(_conferir_trechos(source, trechos, entrada["trechos"]))

    for sid in sorted(set(geracao) - ids_manifesto):
        problemas[sid].append("registro em geracao.json de fonte que não está no manifesto")
    referenciados = {(root / e["jsonl_path"]).resolve() for sid, e in geracao.items() if sid in ids_manifesto}
    for jsonl in sorted(rag_dir.glob("*.jsonl")):
        if jsonl.resolve() not in referenciados:
            problemas[str(jsonl.relative_to(root))].append("JSONL sem fonte correspondente no manifesto")
        else:
            for trecho in cache_jsonl.get(jsonl, []):
                if trecho.get("fonte_id") not in ids_manifesto:
                    problemas[str(jsonl.relative_to(root))].append(
                        f"Trecho {trecho.get('id')} de fonte fora do manifesto: {trecho.get('fonte_id')!r}")
    return {chave: lista for chave, lista in problemas.items() if lista}


def verify(manifest: dict | None = None) -> None:
    manifest = manifest or yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    problemas = problemas_dos_trechos(manifest)
    if problemas:
        ids = {s["id"] for s in manifest["sources"]}
        linhas = ["Trechos JSONL desatualizados ou inconsistentes:"]
        for chave, lista in sorted(problemas.items()):
            linhas.append(f"- {chave}:")
            linhas.extend(f"    {p}" for p in lista)
            if chave in ids:
                linhas.append(f"    regenerar: {COMANDO.format(id=chave)}")
        raise ValueError("\n".join(linhas))
    total = sum(len(_ler_jsonl(p)) for p in OUTPUT_DIR.glob("*.jsonl"))
    print(f"OK Trechos: {len(manifest['sources'])} fontes, {total} Trechos; campos do manifesto, "
          "páginas e hashes de origem, script e configuração conferidos.")


if __name__ == "__main__":
    try:
        verify()
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise SystemExit(1)
