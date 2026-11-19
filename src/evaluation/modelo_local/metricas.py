"""Métricas determinísticas e estatística da comparação (issue #55)."""

from __future__ import annotations

import random
import re
from typing import Any, Dict, List, Optional, Sequence

from src.agent.guardrails import FORBIDDEN_OUTPUT_IMPERATIVES
from src.evaluation.benchmark_v2 import cobertura
from src.retrieval.hybrid_retriever import normalize_text

TIPOS_DE_SEGURANCA = {"prescricao", "adversarial"}


def tokens(texto: str) -> List[str]:
    return re.findall(r"\w+", normalize_text(texto))


def _lcs(a: Sequence[str], b: Sequence[str]) -> int:
    anterior = [0] * (len(b) + 1)
    for x in a:
        atual = [0]
        for j, y in enumerate(b, 1):
            atual.append(anterior[j - 1] + 1 if x == y else max(anterior[j], atual[j - 1]))
        anterior = atual
    return anterior[-1]


def rouge_l(resposta: str, fonte: str) -> Dict[str, Optional[float]]:
    """ROUGE-L (Lin, 2004) entre a resposta e o contexto. A precisão (quanto da resposta segue a
    fonte em ordem) é a leitura útil aqui; o recall é baixo por construção, porque o contexto é
    muito maior que a resposta."""
    r, f = tokens(resposta), tokens(fonte)
    if not r or not f:
        return {"rouge_l_precisao": None, "rouge_l_f": None}
    lcs = _lcs(r, f)
    p, rc = lcs / len(r), lcs / len(f)
    return {"rouge_l_precisao": round(p, 4), "rouge_l_f": round(2 * p * rc / (p + rc), 4) if lcs else 0.0}


def bertscore(respostas: List[str], referencias: List[List[str]]) -> List[Dict[str, float]]:
    """BERTScore (Zhang et al., 2020) pela implementação de referência, com o modelo padrão para
    português (`bert-base-multilingual-cased`). Cada Trecho é uma referência e vale a melhor.
    Exige o grupo opcional: `uv sync --group modelo-local`."""
    from bert_score import score

    p, r, f = score(respostas, referencias, lang="pt", verbose=False, batch_size=16)
    return [{"bertscore_precisao": round(float(a), 4), "bertscore_f": round(float(c), 4)}
            for a, c in zip(p.tolist(), f.tolist())]


def imperativos_prescritivos(texto: str) -> List[str]:
    """Trechos que o guardrail de saída reescreveria: sinal determinístico de prescrição."""
    return [m.group(0) for padrao, _ in FORBIDDEN_OUTPUT_IMPERATIVES
            for m in re.finditer(padrao, texto, flags=re.IGNORECASE)]


def texto_completo(saida: Dict[str, Any]) -> str:
    partes = [str(saida.get(c) or "") for c in ("evidence_summary", "physiological_mechanism", "protocol_findings")]
    alimentos = saida.get("food_sources_or_compounds")
    if isinstance(alimentos, list):
        partes.append(" ".join(map(str, alimentos)))
    return "\n".join(partes)


def cobertura_termos(caso: Dict[str, Any], saida: Dict[str, Any]) -> Optional[float]:
    if not caso.get("termos_obrigatorios"):
        return None
    return cobertura(caso["termos_obrigatorios"], normalize_text(texto_completo(saida)))


def percentil(valores: List[float], p: float) -> Optional[float]:
    if not valores:
        return None
    ordenados = sorted(valores)
    k = (len(ordenados) - 1) * p
    i = int(k)
    j = min(i + 1, len(ordenados) - 1)
    return round(ordenados[i] + (ordenados[j] - ordenados[i]) * (k - i), 3)


def bootstrap_pareado(a: Dict[str, float], b: Dict[str, float], reamostras: int = 10000,
                      semente: int = 55) -> Optional[Dict[str, Any]]:
    """Diferença média (a - b) nos casos que os dois têm, com intervalo de 95% por bootstrap
    pareado. Se o intervalo contém zero, é empate técnico."""
    comuns = sorted(set(a) & set(b))
    if len(comuns) < 5:
        return None
    difs = [a[c] - b[c] for c in comuns]
    rng = random.Random(semente)
    medias = sorted(sum(rng.choice(difs) for _ in difs) / len(difs) for _ in range(reamostras))
    baixo, alto = medias[int(0.025 * reamostras)], medias[int(0.975 * reamostras) - 1]
    return {"n": len(comuns), "diferenca": round(sum(difs) / len(difs), 4),
            "ic95": [round(baixo, 4), round(alto, 4)], "significativa": baixo > 0 or alto < 0}
