"""Validação determinística do golden set de Saúde Física."""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator
import yaml

from src.config import CORPUS_MANIFEST_PATH, CORPUS_RAG_DIR_SAUDE_FISICA, PROJECT_ROOT
from src.retrieval.hybrid_retriever import normalize_text

GOLDEN_SAUDE_FISICA_DIR = PROJECT_ROOT / "eval" / "golden" / "saude_fisica"
SCHEMA_PATH = GOLDEN_SAUDE_FISICA_DIR / "caso.schema.json"

# Limiares de similaridade para detectar vazamento/quase-duplicatas entre dev e test.
# Justificativa: Jaccard >= 0.65 sobre tokens sem stopwords ou SequenceMatcher >= 0.78
# capturam paráfrases muito próximas sem gerar falsos positivos por termos comuns de domínio
# (ex.: "atividade física", "dor lombar", "adultos").
LIMIAR_JACCARD_DUPLICATA = 0.65
LIMIAR_SEQUENCIA_DUPLICATA = 0.78

STOPWORDS_PT = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "na", "no",
    "nas", "nos", "para", "pra", "por", "com", "sem", "um", "uma", "uns", "umas",
    "que", "qual", "quais", "como", "quando", "onde", "se", "ou", "ao", "aos",
    "eu", "meu", "minha", "meus", "minhas", "voce", "pode", "podem", "deve", "devem",
    "fazer", "faz", "sobre", "quem", "tem", "ter", "mais", "menos", "muito",
}


@dataclass
class ResultadoValidacao:
    erros: List[str] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)
    casos_por_split: Dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.erros


def _normalizar_espacos(texto: str) -> str:
    limpo = texto.replace("\r\n", "\n").replace("<br>", " ")
    limpo = re.sub(r"[*_`|]+", " ", limpo)
    return re.sub(r"\s+", " ", limpo).strip()


def _extrair_bloco_pagina(markdown: str, pagina: int) -> Optional[str]:
    marcador = f"<!-- PDF_PAGE: {pagina} -->"
    idx = markdown.find(marcador)
    if idx == -1:
        return None
    inicio = idx + len(marcador)
    proximo = re.search(r"<!-- PDF_PAGE: \d+ -->", markdown[inicio:])
    if proximo:
        return markdown[inicio : inicio + proximo.start()]
    return markdown[inicio:]


def _carregar_manifesto(manifest_path: Path = CORPUS_MANIFEST_PATH) -> Dict[str, Dict[str, Any]]:
    dados = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    return {s["id"]: s for s in dados.get("sources", [])}


def _carregar_trechos_saude_fisica(rag_dir: Path = CORPUS_RAG_DIR_SAUDE_FISICA) -> Dict[str, Dict[str, Any]]:
    trechos: Dict[str, Dict[str, Any]] = {}
    if not rag_dir.exists():
        return trechos
    for arquivo in sorted(rag_dir.glob("*.jsonl")):
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            if linha.strip():
                t = json.loads(linha)
                trechos[t["id"]] = t
    return trechos


def _tokens_conteudo(texto: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]+", normalize_text(texto)))
    return {t for t in tokens if len(t) > 2 and t not in STOPWORDS_PT}


def verificar_sobreposicao_splits(
    casos_dev: List[Dict[str, Any]],
    casos_test: List[Dict[str, Any]],
    limiar_jaccard: float = LIMIAR_JACCARD_DUPLICATA,
    limiar_seq: float = LIMIAR_SEQUENCIA_DUPLICATA,
) -> List[str]:
    erros: List[str] = []
    for c_dev in casos_dev:
        t_dev = _tokens_conteudo(c_dev["pergunta"])
        n_dev = _normalizar_espacos(normalize_text(c_dev["pergunta"]))
        for c_test in casos_test:
            t_test = _tokens_conteudo(c_test["pergunta"])
            n_test = _normalizar_espacos(normalize_text(c_test["pergunta"]))
            uniao = t_dev | t_test
            jaccard = (len(t_dev & t_test) / len(uniao)) if uniao else 0.0
            seq = SequenceMatcher(None, n_dev, n_test).ratio()
            if jaccard >= limiar_jaccard or seq >= limiar_seq:
                erros.append(
                    f"Sobreposição dev/test entre {c_dev['id']} e {c_test['id']}: "
                    f"jaccard={jaccard:.2f}, seq={seq:.2f}"
                )
    return erros


def serializar_split_deterministico(dados: Dict[str, Any]) -> str:
    copia = {
        "versao": dados["versao"],
        "split": dados["split"],
        "casos": sorted(dados["casos"], key=lambda c: c["id"]),
    }
    return json.dumps(copia, ensure_ascii=False, indent=2) + "\n"


def carregar_split(split: str, diretorio: Path = GOLDEN_SAUDE_FISICA_DIR) -> Dict[str, Any]:
    caminho = diretorio / f"{split}.json"
    return json.loads(caminho.read_text(encoding="utf-8"))


def validar_golden(
    diretorio: Path = GOLDEN_SAUDE_FISICA_DIR,
    incluir_test: bool = False,
    schema_path: Path = SCHEMA_PATH,
    manifest_path: Path = CORPUS_MANIFEST_PATH,
    rag_dir: Path = CORPUS_RAG_DIR_SAUDE_FISICA,
) -> ResultadoValidacao:
    res = ResultadoValidacao()
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validador = Draft202012Validator(schema)

    manifesto = _carregar_manifesto(manifest_path)
    trechos = _carregar_trechos_saude_fisica(rag_dir)
    cache_md: Dict[str, str] = {}

    splits = ("dev", "test") if incluir_test else ("dev",)
    todos_ids: List[str] = []
    por_split: Dict[str, List[Dict[str, Any]]] = {}

    for split in splits:
        caminho = diretorio / f"{split}.json"
        if not caminho.exists():
            res.erros.append(f"Arquivo ausente: {caminho}")
            continue
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        for erro in validador.iter_errors(dados):
            local = ".".join(str(p) for p in erro.path) or "<raiz>"
            res.erros.append(f"{split}.json [{local}]: {erro.message}")

        if dados.get("split") != split:
            res.erros.append(f"{split}.json: campo raiz 'split'={dados.get('split')!r} diverge do arquivo")

        casos = dados.get("casos", [])
        por_split[split] = casos
        res.casos_por_split[split] = len(casos)

        for caso in casos:
            cid = caso.get("id", "<sem-id>")
            todos_ids.append(cid)
            if not cid.startswith(f"fis-{split}-"):
                res.erros.append(f"{cid}: prefixo incompatível com split={split}")
            if caso.get("split") != split:
                res.erros.append(f"{cid}: caso['split']={caso.get('split')!r} diverge de {split}")

            tipo = caso.get("tipo")
            rec = caso.get("recuperacao")
            rot = caso.get("roteamento_esperado")

            if tipo == "recuperacao":
                if rec is None:
                    res.erros.append(f"{cid}: tipo 'recuperacao' exige bloco 'recuperacao'")
                else:
                    for idx, ev in enumerate(rec.get("evidencias", []), 1):
                        sid = ev["source_id"]
                        status_ev = ev["approval_status"]
                        if status_ev == "nao_catalogada":
                            if sid in manifesto:
                                res.erros.append(f"{cid} ev#{idx}: {sid} está no manifesto, não é 'nao_catalogada'")
                            continue
                        if sid not in manifesto:
                            res.erros.append(f"{cid} ev#{idx}: source_id {sid!r} ausente no manifesto")
                            continue
                        status_real = manifesto[sid].get("approval_status")
                        if status_ev != status_real:
                            res.erros.append(
                                f"{cid} ev#{idx}: approval_status={status_ev!r} diverge do manifesto ({status_real!r})"
                            )
                        md_rel = manifesto[sid].get("markdown_path")
                        if not md_rel:
                            res.erros.append(f"{cid} ev#{idx}: fonte {sid} sem markdown_path no manifesto")
                            continue
                        if sid not in cache_md:
                            md_path = PROJECT_ROOT / md_rel
                            if not md_path.exists():
                                res.erros.append(f"{cid} ev#{idx}: Markdown ausente em {md_rel}")
                                continue
                            cache_md[sid] = md_path.read_text(encoding="utf-8")
                        md_texto = cache_md[sid]
                        trecho_lit = _normalizar_espacos(ev["trecho_literal"])
                        pag = ev["localizador"]["pagina_pdf"]
                        if pag is not None:
                            bloco = _extrair_bloco_pagina(md_texto, pag)
                            if bloco is None:
                                res.erros.append(f"{cid} ev#{idx}: página {pag} não encontrada em {md_rel}")
                            elif trecho_lit not in _normalizar_espacos(bloco):
                                res.erros.append(
                                    f"{cid} ev#{idx}: trecho_literal não encontrado na página {pag} de {sid}"
                                )
                        else:
                            if trecho_lit not in _normalizar_espacos(md_texto):
                                res.erros.append(
                                    f"{cid} ev#{idx}: trecho_literal não encontrado no Markdown de {sid}"
                                )

                        tid = ev.get("trecho_id")
                        if tid is not None:
                            if tid not in trechos:
                                res.erros.append(f"{cid} ev#{idx}: trecho_id {tid!r} não encontrado no RAG")
                            else:
                                texto_rag = _normalizar_espacos(trechos[tid]["texto"])
                                if trecho_lit not in texto_rag:
                                    res.avisos.append(
                                        f"{cid} ev#{idx}: trecho_literal não está contido integralmente em {tid}"
                                    )
            else:
                if rec is not None:
                    res.erros.append(f"{cid}: tipo {tipo!r} não deve ter bloco 'recuperacao' (sem citação artificial)")

            if tipo == "entre_abas":
                if rot is None:
                    res.erros.append(f"{cid}: tipo 'entre_abas' exige 'roteamento_esperado'")
            elif rot is not None:
                res.erros.append(f"{cid}: 'roteamento_esperado' deve ser null fora de 'entre_abas'")

    repetidos = sorted({i for i in todos_ids if todos_ids.count(i) > 1})
    if repetidos:
        res.erros.append(f"IDs repetidos: {', '.join(repetidos)}")

    if incluir_test and "dev" in por_split and "test" in por_split:
        res.erros.extend(verificar_sobreposicao_splits(por_split["dev"], por_split["test"]))

    return res
