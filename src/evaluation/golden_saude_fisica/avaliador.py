"""Avaliador de recuperação e qualidade de resposta para o golden set de Saúde Física."""

from __future__ import annotations

from pathlib import Path
import random
import re
from typing import Any, Callable, Dict, List, Optional

from src.evaluation.golden_saude_fisica.validador import (
    GOLDEN_SAUDE_FISICA_DIR,
    STOPWORDS_PT,
    carregar_split,
)
from src.retrieval.hybrid_retriever import normalize_text

# Palavras comuns em inglês para detectar respostas que apenas copiam trechos em inglês sem formular em pt-BR.
MARCADORES_INGLES = {
    "the", "and", "for", "with", "that", "this", "from", "are", "were", "have",
    "should", "adults", "exercise", "physical", "activity", "muscle", "training",
}
MARCADORES_PT = {
    "para", "com", "que", "uma", "como", "entre", "sobre", "pode", "devem",
    "segundo", "conforme", "recomenda", "atividade", "exercicio", "saude",
    "nao", "posso", "voce", "pelo", "pela", "mais", "cada", "pessoa",
    "orientacao", "avaliacao", "profissional", "fisica", "treino", "diretrizes",
}


def _tokens_conteudo_lista(texto: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9]+", normalize_text(texto))
    return [t for t in tokens if len(t) > 2 and t not in STOPWORDS_PT]


def f1_tokens_conteudo(resposta: str, referencia: str) -> float:
    """Similaridade F1 de tokens de conteúdo (unigramas) entre resposta gerada e modelo ideal."""
    r_set = set(_tokens_conteudo_lista(resposta))
    ref_set = set(_tokens_conteudo_lista(referencia))
    if not r_set or not ref_set:
        return 0.0
    inter = len(r_set & ref_set)
    if inter == 0:
        return 0.0
    prec = inter / len(r_set)
    rec = inter / len(ref_set)
    return 2 * prec * rec / (prec + rec)


def rouge_l_f1(resposta: str, referencia: str) -> float:
    """ROUGE-L F1 baseado na maior subsequência comum de tokens normalizados."""
    a = _tokens_conteudo_lista(resposta)
    b = _tokens_conteudo_lista(referencia)
    if not a or not b:
        return 0.0
    # DP em O(len(b)) de espaço
    prev = [0] * (len(b) + 1)
    for tok_a in a:
        curr = [0] * (len(b) + 1)
        for j, tok_b in enumerate(b, 1):
            if tok_a == tok_b:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = curr[j - 1] if curr[j - 1] >= prev[j] else prev[j]
        prev = curr
    lcs = prev[-1]
    if lcs == 0:
        return 0.0
    prec = lcs / len(a)
    rec = lcs / len(b)
    return 2 * prec * rec / (prec + rec)


def fluidez_linguagem_natural(resposta: str) -> float:
    """Heurística determinística (0 a 1) de formulação fluida em pt-BR (não apenas cópia bruta)."""
    texto = resposta.strip()
    if len(texto) < 40:
        return 0.0
    # Citações literais entre aspas podem estar em inglês (fontes originais); avaliamos a fluidez da
    # formulação fora das aspas.
    sem_citacoes = re.sub(r'"[^"]*"', " ", texto)
    tokens = re.findall(r"[a-z]+", normalize_text(sem_citacoes or texto))
    if not tokens:
        return 0.0
    qtd_pt = sum(1 for t in tokens if t in MARCADORES_PT)
    qtd_en = sum(1 for t in tokens if t in MARCADORES_INGLES)
    tem_pontuacao = "." in texto or "!" in texto
    nao_e_so_tabela = texto.count("|") < 4
    score = 0.0
    if qtd_pt >= 2 and qtd_pt >= qtd_en:
        score += 0.5
    if tem_pontuacao and len(texto) >= 80:
        score += 0.3
    if nao_e_so_tabela:
        score += 0.2
    return round(score, 4)


def _casa_token(tok_ponto: str, resp_tokens: set[str]) -> bool:
    if tok_ponto in resp_tokens:
        return True
    if len(tok_ponto) >= 5:
        pref = tok_ponto[:5]
        return any(r.startswith(pref) for r in resp_tokens)
    return False


def cobertura_pontos(pontos: List[str], resposta: str) -> float:
    """Fração dos pontos atendidos por sobreposição de tokens/radicais de conteúdo."""
    if not pontos:
        return 1.0
    resp_tokens = set(_tokens_conteudo_lista(resposta))
    resp_norm = normalize_text(resposta)
    atendidos = 0
    for ponto in pontos:
        p_norm = normalize_text(ponto)
        if p_norm in resp_norm:
            atendidos += 1
            continue
        p_tokens = set(_tokens_conteudo_lista(ponto))
        if p_tokens and sum(1 for t in p_tokens if _casa_token(t, resp_tokens)) / len(p_tokens) >= 0.4:
            atendidos += 1
    return atendidos / len(pontos)


def bootstrap_ic(valores: List[float], n_iter: int = 1000, seed: int = 42) -> Dict[str, Any]:
    """Média e intervalo de confiança 95% (bootstrap percentílico) com `n` explícito."""
    n = len(valores)
    if n == 0:
        return {"n": 0, "media": None, "ic95": None}
    media = sum(valores) / n
    if n == 1:
        return {"n": 1, "media": round(media, 4), "ic95": [round(media, 4), round(media, 4)]}
    rng = random.Random(seed)
    medias = sorted(sum(rng.choices(valores, k=n)) / n for _ in range(n_iter))
    low = medias[int(0.025 * n_iter)]
    high = medias[int(0.975 * n_iter)]
    return {"n": n, "media": round(media, 4), "ic95": [round(low, 4), round(high, 4)]}


def avaliar_caso_resposta(
    caso: Dict[str, Any],
    resposta_texto: str,
    fontes_recuperadas: Optional[List[str]] = None,
    trechos_recuperados: Optional[List[str]] = None,
    guardrail_acionado: Optional[bool] = None,
    abstencao: Optional[bool] = None,
    citacoes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Avalia recuperação, comportamento e compatibilidade com a resposta ideal do golden."""
    geracao = caso.get("geracao") or {}
    obrigatorios = geracao.get("pontos_obrigatorios", [])
    proibidos = geracao.get("pontos_proibidos", [])
    referencia = caso["resposta_referencia"]

    cob_obrig = cobertura_pontos(obrigatorios, resposta_texto)
    # Para pontos proibidos, exigimos que o padrão literal/majoritário NÃO apareça
    aus_proib = 1.0
    if proibidos:
        resp_norm = normalize_text(resposta_texto)
        violacoes = sum(1 for p in proibidos if normalize_text(p) in resp_norm)
        aus_proib = 1.0 - (violacoes / len(proibidos))

    f1_ref = f1_tokens_conteudo(resposta_texto, referencia)
    rl_ref = rouge_l_f1(resposta_texto, referencia)
    fluidez = fluidez_linguagem_natural(resposta_texto)

    rec_res: Dict[str, Optional[float]] = {
        "acerto_fonte": None,
        "acerto_trecho": None,
        "mrr_fonte": None,
        "citacoes_validas": None,
    }
    if caso["tipo"] == "recuperacao" and caso.get("recuperacao"):
        evs = caso["recuperacao"]["evidencias"]
        esp_fontes = {e["source_id"] for e in evs}
        esp_trechos = {e["trecho_id"] for e in evs if e.get("trecho_id")}
        if fontes_recuperadas is not None:
            rec_res["acerto_fonte"] = float(any(f in esp_fontes for f in fontes_recuperadas))
            rr = next((1.0 / i for i, f in enumerate(fontes_recuperadas, 1) if f in esp_fontes), 0.0)
            rec_res["mrr_fonte"] = rr
        if trechos_recuperados is not None and esp_trechos:
            rec_res["acerto_trecho"] = float(any(t in esp_trechos for t in trechos_recuperados))
        if citacoes is not None:
            rec_res["citacoes_validas"] = float(bool(citacoes))

    comp_ok: Optional[float] = None
    if caso["comportamento_esperado"] == "redirecionar_prescricao" and guardrail_acionado is not None:
        comp_ok = float(guardrail_acionado)
    elif caso["comportamento_esperado"] == "nao_sei" and abstencao is not None:
        comp_ok = float(abstencao)
    elif caso["comportamento_esperado"] == "responder" and guardrail_acionado is not None and abstencao is not None:
        comp_ok = float((not guardrail_acionado) and (not abstencao))

    return {
        "id": caso["id"],
        "tipo": caso["tipo"],
        "split": caso["split"],
        **rec_res,
        "comportamento_ok": comp_ok,
        "cobertura_pontos_obrigatorios": round(cob_obrig, 4),
        "ausencia_pontos_proibidos": round(aus_proib, 4),
        "f1_referencia": round(f1_ref, 4),
        "rouge_l_referencia": round(rl_ref, 4),
        "fluidez_pt_br": fluidez,
    }


def avaliar_golden(
    split: str = "dev",
    incluir_test: bool = False,
    diretorio: Path = GOLDEN_SAUDE_FISICA_DIR,
    executor: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    respostas_por_id: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Avalia um split (`dev` por padrão; `test` exige `incluir_test=True`) e retorna métricas com IC 95%."""
    if split == "test" and not incluir_test:
        raise ValueError("Leitura do split 'test' exige --incluir-test explícito.")
    casos = carregar_split(split, diretorio)["casos"]
    resultados: List[Dict[str, Any]] = []
    for caso in casos:
        if respostas_por_id is not None:
            saida = respostas_por_id.get(caso["id"], {"resposta": ""})
        elif executor is not None:
            saida = executor(caso)
        else:
            raise ValueError("Informe `executor` ou `respostas_por_id`.")

        resultados.append(
            avaliar_caso_resposta(
                caso=caso,
                resposta_texto=saida.get("resposta", ""),
                fontes_recuperadas=saida.get("fontes_recuperadas"),
                trechos_recuperados=saida.get("trechos_recuperados"),
                guardrail_acionado=saida.get("guardrail_acionado"),
                abstencao=saida.get("abstencao"),
                citacoes=saida.get("citacoes"),
            )
        )

    def vals(chave: str) -> List[float]:
        return [float(r[chave]) for r in resultados if r.get(chave) is not None]

    metricas = {
        "acerto_fonte": bootstrap_ic(vals("acerto_fonte")),
        "acerto_trecho": bootstrap_ic(vals("acerto_trecho")),
        "mrr_fonte": bootstrap_ic(vals("mrr_fonte")),
        "citacoes_validas": bootstrap_ic(vals("citacoes_validas")),
        "comportamento_ok": bootstrap_ic(vals("comportamento_ok")),
        "cobertura_pontos_obrigatorios": bootstrap_ic(vals("cobertura_pontos_obrigatorios")),
        "ausencia_pontos_proibidos": bootstrap_ic(vals("ausencia_pontos_proibidos")),
        "f1_referencia": bootstrap_ic(vals("f1_referencia")),
        "rouge_l_referencia": bootstrap_ic(vals("rouge_l_referencia")),
        "fluidez_pt_br": bootstrap_ic(vals("fluidez_pt_br")),
    }
    return {
        "split": split,
        "total_casos": len(resultados),
        "metricas": metricas,
        "por_caso": resultados,
    }
