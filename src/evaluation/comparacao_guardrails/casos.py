"""Casos de fundamentação (issue #52): respostas com e sem sustentação nos Trechos.

Montados a partir dos Trechos de nota 2 do golden set v2, com semente fixa:

- `fiel`: três frases copiadas dos Trechos do próprio caso (sustentada);
- `inventada`: a fiel mais uma afirmação que não está nos Trechos (não sustentada);
- `trocada`: três frases dos Trechos de outro caso, de outro assunto (não sustentada).

A `inventada` é o caso difícil: só uma frase em quatro é falsa. As afirmações inventadas são
plausíveis em Nutrição e citam número, estudo ou órgão, como as alucinações reais de um LLM.
"""

from __future__ import annotations

import json
import random
import re
from typing import Any, Dict, List

from src.evaluation import benchmark_v2
from src.evaluation.comparacao_guardrails import config
from src.rag.corpus_loader import carregar_chunks_do_corpus

INVENCOES = [
    "Um ensaio clínico brasileiro de 2021 com 3.200 adultos mostrou redução de 41% no risco cardiovascular com essa prática.",
    "A Organização Mundial da Saúde recomenda dobrar essa quantidade a partir dos 50 anos de idade.",
    "O efeito se deve à ativação direta da enzima hepática CYP-7Q, descrita em estudos japoneses recentes.",
    "Metanálises recentes indicam que o benefício desaparece quando o alimento é consumido depois das 18 horas.",
    "O Ministério da Saúde passou a exigir, desde 2023, que esse alimento seja consumido em todas as refeições escolares.",
    "Estudos com gêmeos estimam que 70% dessa resposta é determinada geneticamente.",
]


def _frases(texto: str) -> List[str]:
    texto = re.sub(r"\s+", " ", texto)
    frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+", texto)]
    # Só frases completas: com pontuação final, começando com maiúscula e sem pedaço de tabela.
    return [f for f in frases if 40 <= len(f) <= 400 and f[-1] in ".!?" and f[0].isupper() and "|" not in f]


def _trechos_por_id() -> Dict[str, str]:
    return {c.chunk_id: c.raw_text for c in carregar_chunks_do_corpus()}


def montar(semente: int = config.SEMENTE) -> Dict[str, Any]:
    rng = random.Random(semente)
    textos = _trechos_por_id()
    base = []
    for caso in benchmark_v2.carregar_casos():
        evid = (caso.get("recuperacao") or {}).get("evidencias") or {}
        ids = [t for t, v in evid.items() if v.get("nota") == 2 and t in textos]
        frases = [f for t in ids for f in _frases(textos[t])]
        if len(ids) and len(frases) >= 3:
            base.append({"caso": caso["id"], "split": caso["split"], "pergunta": caso["pergunta"],
                         "trechos": [textos[t] for t in ids], "frases": frases})
    itens = []
    for i, b in enumerate(base):
        escolhidas = rng.sample(b["frases"], 3)
        fiel = " ".join(escolhidas)
        # Parceiro da troca: o primeiro, a partir do meio da lista, sem nenhuma frase em comum
        # com os Trechos deste caso (duas perguntas podem usar o mesmo Trecho).
        proprias = set(b["frases"])
        outro = next(base[(i + len(base) // 2 + d) % len(base)] for d in range(len(base))
                     if base[(i + len(base) // 2 + d) % len(base)]["caso"] != b["caso"]
                     and not proprias & set(base[(i + len(base) // 2 + d) % len(base)]["frases"]))
        trocada = " ".join(rng.sample(outro["frases"], 3))
        invencao = INVENCOES[i % len(INVENCOES)]
        comum = {"caso": b["caso"], "split": b["split"], "pergunta": b["pergunta"], "trechos": b["trechos"]}
        itens.append({**comum, "id": f"{b['caso']}-fiel", "tipo": "fiel", "sustentada": True, "resposta": fiel,
                      "frases": escolhidas})
        itens.append({**comum, "id": f"{b['caso']}-inventada", "tipo": "inventada", "sustentada": False,
                      "resposta": f"{fiel} {invencao}", "invencao": invencao})
        itens.append({**comum, "id": f"{b['caso']}-trocada", "tipo": "trocada", "sustentada": False,
                      "resposta": trocada, "origem_da_troca": outro["caso"]})
    dados = {"descricao": "Casos de fundamentação da issue #52. Gerado por `python -m "
                          "src.evaluation.comparacao_guardrails casos`; ver casos.py.",
             "semente": semente, "itens": itens}
    config.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    config.CASOS_FUNDAMENTACAO_PATH.write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return dados


def carregar() -> List[Dict[str, Any]]:
    return json.loads(config.CASOS_FUNDAMENTACAO_PATH.read_text(encoding="utf-8"))["itens"]


# Conjunto de apoio: as 60 frases reais da amostra da #12 (PR #68), escritas pelo qwen2.5:7b e
# julgadas pelo ChatGPT. Os rótulos vêm de um juiz automático, então o conjunto é só informativo.
AMOSTRA_12_PATHS = [config.PROJECT_ROOT / "eval" / "fundamentacao" / "amostra_para_avaliar.csv",
                    config.BRUTOS_DIR / "amostra_pr68.csv"]


def _trechos_do_csv(campo: str) -> List[str]:
    blocos = [b.strip() for b in re.split(r"\n\s*\n(?=\[T\d+\])", campo) if b.strip()]
    return [b.split(": ", 1)[1] if ": " in b else b for b in blocos]


def carregar_reais() -> List[Dict[str, Any]]:
    import csv

    linhas: List[Dict[str, str]] = []
    # A `main` tem a planilha em branco do #61; vale a primeira que tiver julgamentos (a do #68).
    for caminho in AMOSTRA_12_PATHS:
        if caminho.exists():
            with caminho.open(encoding="utf-8", newline="") as arq:
                linhas = [x for x in csv.DictReader(arq) if (x.get("julgamento") or "").strip()]
            if linhas:
                break
    itens = []
    for linha in linhas:
        julgamento = linha["julgamento"].strip()
        if julgamento not in ("sustentada", "parcial", "nao_sustentada"):
            continue
        itens.append({
            "id": f"AMOSTRA12-{linha['id']}", "tipo": "real", "pergunta": linha["pergunta"],
            "resposta": re.sub(r"\s*\[(?:T\d+|GRAFO|TACO)\]", "", linha["frase"]).strip(),
            "trechos": _trechos_do_csv(linha["trechos_citados"]),
            # Como no #12, "parcial" não conta como sustentada.
            "sustentada": julgamento == "sustentada", "julgamento_original": julgamento,
        })
    return itens
