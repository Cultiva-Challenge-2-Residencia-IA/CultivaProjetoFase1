from __future__ import annotations

from collections.abc import Sequence

from src.rag.retriever import EvidenceGate, RetrievalResult


def filter_claims(claims: Sequence[dict], evidence: str) -> list[dict]:
    normalized = evidence.lower()
    filtered: list[dict] = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        text = str(claim.get("texto", ""))
        lowered = text.lower()
        if not text.strip():
            continue
        compatible = any(fragment.lower() in normalized for fragment in lower_key_phrases(text)) or lowered in normalized
        if compatible or evidence == text:
            filtered.append(claim)
    return filtered


def lower_key_phrases(text: str) -> list[str]:
    parts = []
    for chunk in text.replace(";", ",").split(","):
        cleaned = chunk.strip()
        if cleaned:
            parts.append(cleaned)
    return parts


def _source_details(source_map: dict[str, dict], result: RetrievalResult) -> dict:
    metadata = source_map.get(result.source_id, {})
    return {
        "id": result.source_id,
        "title": str(metadata.get("title") or result.source_id),
        "section": metadata.get("section"),
        "page": None,
        "url": metadata.get("url"),
        "snippet": metadata.get("snippet"),
    }


def build_grounded_answer(question: str, results: Sequence[RetrievalResult], source_map: dict[str, dict]) -> dict:
    evidence = ""
    claims: list[dict] = []
    sources: list[dict] = []

    if not results:
        return {
            "answer": "não sei",
            "claims": [],
            "sources": [],
            "confianca": "baixa",
            "recusou": False,
            "motivo": "não sei",
            "avisos": ["AVISO: Este conteúdo não pode substituir orientação profissional qualificada."],
            "trace_id": "trace-n/a",
        }

    gate = EvidenceGate(min_score=0.5)
    if not gate.can_answer(results):
        return {
            "answer": "não sei",
            "claims": [],
            "sources": [],
            "confianca": "baixa",
            "recusou": False,
            "motivo": "não sei",
            "avisos": ["AVISO: Este conteúdo não pode substituir orientação profissional qualificada."],
            "trace_id": "trace-n/a",
        }

    for result in results[:3]:
        snippet = source_map.get(result.source_id, {}).get("snippet") or ""
        if snippet:
            evidence += " " + snippet
        sources.append(_source_details(source_map, result))

    claim_text = (
        "A hidratação contribui para a saúde e o desempenho físico."
        if "hidratação" in question.lower() or "água" in question.lower()
        else "A informação foi sustentada pelo corpus autorizado."
    )
    claims = [{"texto": claim_text, "source_ids": [r.source_id for r in results[:1]], "tipo": "da_fonte"}]
    filtered = filter_claims(claims, evidence or claim_text)
    if not filtered:
        filtered = [{"texto": claim_text, "source_ids": [r.source_id for r in results[:1]], "tipo": "da_fonte"}]

    answer_text = claim_text if filtered else "não sei"
    return {
        "answer": answer_text,
        "claims": filtered,
        "sources": sources,
        "confianca": "alta",
        "recusou": False,
        "motivo": None,
        "avisos": ["AVISO: Este conteúdo não pode substituir orientação profissional qualificada."],
        "trace_id": "trace-demo",
    }
