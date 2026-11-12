"""Benchmark v2 como experimento no Langfuse.

Uso:
    uv run python -m src.evaluation.langfuse_experimento [--config CONFIG] [--no-ollama]
        [--split dev|test] [--nome NOME]

Espelha o golden set v2 (`eval/golden/v2/`) num dataset do Langfuse e roda o consultor em cada
caso. As métricas são as mesmas do `benchmark_v2.py` (`avaliar_caso` e `agregar`): cada caso
recebe as suas como scores, e a execução recebe as médias. Assim dá para comparar configurações
(ranking, modelo, prompt) lado a lado na interface do Langfuse.

Ablação (`--config`): compara o LLM sozinho com o LLM mais cada fonte de contexto.

- `llm-puro`: só a pergunta, sem Trechos, grafo nem TACO (linha de base, não é modo do produto);
- `llm-rag`: com os Trechos;
- `llm-rag-grafo`: com os Trechos e o grafo causal;
- `completo`: com Trechos, grafo e TACO (o sistema atual, padrão).

Os guardrails ficam ligados em todas. Cada execução só recebe as métricas que se aplicam aos
componentes ligados: sem RAG não há métrica de recuperação nem de citação, que dariam 0 por
definição. Como a resposta final mistura o texto do LLM com o texto extraído dos Trechos e a
tabela da TACO, as métricas de texto saem em duas versões: a da resposta final (`cobertura_termos`,
`tamanho_resposta`) e a só do texto devolvido pelo LLM (`cobertura_termos_llm`,
`tamanho_resposta_llm`). Não há juiz LLM por enquanto.

Classificação: proposta técnica. O golden set do repositório continua sendo a fonte da verdade:
o dataset é sobrescrito a cada execução e os casos removidos do repositório são arquivados.
Isto não substitui o benchmark nem o gate do CI, e só roda com CULTIVA_LANGFUSE=true e as chaves
do Langfuse no `.env`.
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from src import config, observabilidade
from src.evaluation.benchmark_v2 import (
    METRICAS,
    METRICAS_INFORMATIVAS,
    agregar,
    avaliar_caso,
    carregar_casos,
    cobertura,
)
from src.retrieval.hybrid_retriever import normalize_text

DATASET = "cultiva-nutricao-golden-v2"

# Componentes de contexto ligados em cada configuração da ablação.
CONFIGURACOES: Dict[str, Dict[str, bool]] = {
    "llm-puro": {"rag": False, "grafo": False, "taco": False},
    "llm-rag": {"rag": True, "grafo": False, "taco": False},
    "llm-rag-grafo": {"rag": True, "grafo": True, "taco": False},
    "completo": {"rag": True, "grafo": True, "taco": True},
}
# Campos de `avaliar_caso` que só têm sentido com o componente ligado.
CAMPOS_POR_COMPONENTE = {
    "rag": {"acerto_trecho", "acerto_completo", "ndcg_trecho", "recall_trecho", "rr_trecho",
            "acerto_pagina", "acerto_fonte", "citacoes_validas"},
    "grafo": {"cadeia_encontrada", "composto_proibido_ausente"},
    "taco": {"taco_correto"},
}
# Métricas de texto próprias dos experimentos (nome = campo).
METRICAS_DE_TEXTO = {
    "cobertura_termos_llm": "cobertura_termos_llm",
    "tamanho_resposta": "tamanho_resposta",
    "tamanho_resposta_llm": "tamanho_resposta_llm",
}
# 1 quando o caso foi respondido pelo modelo fixado na execução (ver `fixar_modelo`).
METRICAS_DE_TEXTO["llm_respondeu"] = "llm_respondeu"
# Métricas que dependem do texto gerado: saem do caso quando o modelo fixado não respondeu.
CAMPOS_DEPENDENTES_DO_LLM = {"cobertura_termos", "cobertura_termos_llm", "tamanho_resposta",
                             "tamanho_resposta_llm", "citacoes_validas"}
# Em caracteres, não em proporção.
METRICAS_ABSOLUTAS = {"tamanho_resposta", "tamanho_resposta_llm"}
# Esperas (s) antes de cada nova tentativa quando o modelo fixado falha (ex.: limite do Groq).
ESPERAS_ENTRE_TENTATIVAS = (20, 60)
CAMPOS_DA_RESPOSTA = ("evidence_summary", "physiological_mechanism", "protocol_findings")

TODAS_AS_METRICAS = {**METRICAS, **METRICAS_INFORMATIVAS, **METRICAS_DE_TEXTO}
# Campo de `avaliar_caso` -> nome da métrica no relatório (ex.: "rr_trecho" -> "mrr_trecho").
NOME_DA_METRICA = {campo: nome for nome, campo in TODAS_AS_METRICAS.items()}


def id_do_item(caso_id: str) -> str:
    return f"golden-v2-{caso_id}"


def item_do_caso(caso: Dict[str, Any]) -> Dict[str, Any]:
    """Item do dataset: a pergunta como entrada e o caso inteiro como saída esperada."""
    return {
        "id": id_do_item(caso["id"]),
        "input": {"pergunta": caso["pergunta"]},
        "expected_output": caso,
        "metadata": {
            "caso_id": caso["id"],
            "tipo": caso["tipo"],
            "split": caso["split"],
            "comportamento_esperado": caso["comportamento_esperado"],
        },
    }


def _campo(item: Any, nome: str) -> Any:
    return item.get(nome) if isinstance(item, dict) else getattr(item, nome)


def _status(item: Any) -> str:
    status = _campo(item, "status") if not isinstance(item, dict) else item.get("status", "ACTIVE")
    return str(getattr(status, "value", status))


def sincronizar_dataset(cliente: Any, casos: List[Dict[str, Any]]) -> Any:
    """Cria ou atualiza o dataset a partir do golden set e arquiva os itens que saíram dele."""
    try:
        cliente.get_dataset(DATASET)
    except Exception:
        cliente.create_dataset(
            name=DATASET,
            description="Espelho de eval/golden/v2 (benchmark v2, issue #13). Não edite aqui.",
        )
    for caso in casos:
        cliente.create_dataset_item(dataset_name=DATASET, **item_do_caso(caso))

    atuais = {id_do_item(c["id"]) for c in casos}
    for item in cliente.get_dataset(DATASET).items:
        if item.id not in atuais and _status(item) != "ARCHIVED":
            cliente.create_dataset_item(
                dataset_name=DATASET,
                id=item.id,
                input=item.input,
                expected_output=item.expected_output,
                metadata=item.metadata,
                status="ARCHIVED",
            )
    return cliente.get_dataset(DATASET)


def avaliacoes_do_caso(avaliacao: Dict[str, Any]) -> List[Any]:
    """Converte as métricas de `avaliar_caso` em scores do Langfuse, com os nomes do relatório."""
    from langfuse import Evaluation

    return [
        Evaluation(name=NOME_DA_METRICA[campo], value=float(valor), data_type="NUMERIC")
        for campo, valor in avaliacao.items()
        if campo in NOME_DA_METRICA and valor is not None
    ]


def avaliacoes_da_execucao(resultados: List[Dict[str, Any]]) -> List[Any]:
    """Médias da execução, calculadas pelo mesmo `agregar` do benchmark v2."""
    from langfuse import Evaluation

    agregado = agregar(resultados, TODAS_AS_METRICAS)
    return [
        Evaluation(
            name=nome,
            value=agregado[nome],
            comment=f"n={agregado[f'n_{nome}']}",
            data_type="NUMERIC",
        )
        for nome in TODAS_AS_METRICAS
        if agregado[nome] is not None
    ]


def metricas_de_texto(
    caso: Dict[str, Any], resposta_final: Dict[str, Any], sintese_llm: Optional[Dict[str, Any]]
) -> Dict[str, float]:
    """Tamanho da resposta final e, quando houve LLM, tamanho e cobertura do texto só do LLM."""
    final = " ".join(str(resposta_final.get(c) or "") for c in CAMPOS_DA_RESPOSTA)
    metricas: Dict[str, float] = {"tamanho_resposta": float(len(final))}
    if sintese_llm is None:
        return metricas
    texto_llm = " ".join(str(sintese_llm.get(c) or "") for c in CAMPOS_DA_RESPOSTA)
    metricas["tamanho_resposta_llm"] = float(len(texto_llm))
    termos = (caso.get("geracao") or {}).get("termos_obrigatorios")
    if termos:
        metricas["cobertura_termos_llm"] = cobertura(termos, normalize_text(texto_llm))
    return metricas


def filtrar_por_componentes(avaliacao: Dict[str, Any], componentes: Dict[str, bool]) -> Dict[str, Any]:
    """Remove as métricas dos componentes desligados, que dariam 0 por definição."""
    fora = set().union(*(campos for nome, campos in CAMPOS_POR_COMPONENTE.items() if not componentes[nome]))
    return {campo: valor for campo, valor in avaliacao.items() if campo not in fora}


def fixar_modelo(llm_client: Any) -> str:
    """Desliga os modelos reserva para a execução inteira usar um só modelo.

    Sem isso, quando o Groq recusa uma chamada (limite de requisições), o caso cai no modelo
    reserva ou no Ollama local, e a comparação entre configurações passa a misturar modelos.
    Devolve o `model_used` esperado.
    """
    if llm_client.provider == "ollama":
        llm_client.enable_groq = False
        llm_client.fallback_model = ""
        return f"ollama:{llm_client.primary_model}"
    llm_client.groq_fallback_model = ""
    llm_client.enable_ollama = False
    return f"groq:{llm_client.groq_model}"


def criar_tarefa(
    consultor: Any,
    top_k: int,
    componentes: Dict[str, bool],
    modelo_esperado: Optional[str] = None,
    esperas: tuple = ESPERAS_ENTRE_TENTATIVAS,
):
    def tarefa(*, item: Any, **_: Any) -> Dict[str, Any]:
        caso = _campo(item, "expected_output")
        resposta = consultor.consult(caso["pergunta"], top_k=top_k)
        for espera in esperas:
            if modelo_esperado is None or resposta.model_used == modelo_esperado:
                break
            time.sleep(espera)
            resposta = consultor.consult(caso["pergunta"], top_k=top_k)
        sintese_llm = consultor.llm_client.ultima_sintese_llm
        avaliacao = avaliar_caso(caso, resposta, top_k)
        avaliacao.update(metricas_de_texto(caso, resposta.model_dump(), sintese_llm))
        if modelo_esperado is not None:
            respondeu = resposta.model_used == modelo_esperado
            avaliacao["llm_respondeu"] = float(respondeu)
            if not respondeu:
                avaliacao = {k: v for k, v in avaliacao.items() if k not in CAMPOS_DEPENDENTES_DO_LLM}
        return {
            "model_used": resposta.model_used,
            "guardrail_triggered": resposta.guardrail_triggered,
            "evidence_summary": resposta.evidence_summary,
            "physiological_mechanism": resposta.physiological_mechanism,
            "protocol_findings": resposta.protocol_findings,
            "citations": resposta.citations,
            "sintese_llm": sintese_llm,
            "avaliacao": filtrar_por_componentes(avaliacao, componentes),
        }

    return tarefa


def avaliador_do_caso(*, output: Any, **_: Any) -> List[Any]:
    return avaliacoes_do_caso(output["avaliacao"]) if output else []


def avaliador_da_execucao(*, item_results: List[Any], **_: Any) -> List[Any]:
    resultados = [r.output["avaliacao"] for r in item_results if r.output]
    return avaliacoes_da_execucao(resultados)


def configuracao_da_execucao(enable_llm: bool, top_k: int, nome_config: str = "completo") -> Dict[str, str]:
    """Parâmetros que mudam as métricas, gravados como metadata para comparar execuções."""
    componentes = CONFIGURACOES[nome_config]
    return {
        "config": nome_config,
        "rag": str(componentes["rag"]),
        "grafo": str(componentes["grafo"]),
        "taco": str(componentes["taco"]),
        "sintese": f"llm ({config.LLM_PROVIDER})" if enable_llm else "extrativa",
        "groq_model": config.GROQ_MODEL,
        "top_k": str(top_k),
        "modo_denso": config.MODO_DENSO,
        "rrf_k": str(config.RRF_K),
        "rerank_peso_sobreposicao": str(config.RERANK_PESO_SOBREPOSICAO),
        "rerank_bonus_evidencia": str(config.RERANK_BONUS_EVIDENCIA),
        "embedding": config.EMBEDDING_MODEL_NAME,
        "incluir_pendentes": str(config.INCLUDE_PENDING_SOURCES),
    }


def executar(
    enable_llm: bool = True,
    split: Optional[str] = None,
    nome: Optional[str] = None,
    top_k: int = config.TOP_K_FINAL,
    nome_config: str = "completo",
    permitir_fallback: bool = False,
) -> Any:
    componentes = CONFIGURACOES[nome_config]
    if not enable_llm and not componentes["rag"]:
        raise SystemExit("A configuração llm-puro precisa do LLM: rode sem --no-ollama.")
    cliente = observabilidade.cliente()
    if cliente is None:
        raise SystemExit(
            "Langfuse desligado: defina CULTIVA_LANGFUSE=true, LANGFUSE_PUBLIC_KEY e "
            "LANGFUSE_SECRET_KEY no .env."
        )
    from src.agent.consultant_baseline import NutritionConsultantBaseline

    casos = carregar_casos()
    dataset = sincronizar_dataset(cliente, casos)
    itens = [
        item
        for item in dataset.items
        if _status(item) != "ARCHIVED" and (split is None or (item.metadata or {}).get("split") == split)
    ]

    modo = "llm" if enable_llm else "extrativo"
    sufixo = f"-{split}" if split else ""
    run_name = nome or f"v2-{nome_config}-{modo}{sufixo}-{datetime.now():%Y%m%d-%H%M%S}"
    consultor = NutritionConsultantBaseline(
        enable_ollama=enable_llm,
        enable_rag=componentes["rag"],
        enable_graph_engine=componentes["grafo"],
        enable_taco_tool=componentes["taco"],
    )
    modelo_esperado = fixar_modelo(consultor.llm_client) if enable_llm and not permitir_fallback else None
    resultado = cliente.run_experiment(
        name=DATASET,
        run_name=run_name,
        description=f"Benchmark v2, config {nome_config} ({len(itens)} casos, síntese {modo})",
        data=itens,
        task=criar_tarefa(consultor, top_k, componentes, modelo_esperado),
        evaluators=[avaliador_do_caso],
        run_evaluators=[avaliador_da_execucao],
        # Em série: o consultor é compartilhado e o Groq tem limite de requisições.
        max_concurrency=1,
        metadata={
            **configuracao_da_execucao(enable_llm, top_k, nome_config),
            "modelo_fixado": modelo_esperado or "nao (com reservas)",
        },
    )
    observabilidade.flush()
    # O Langfuse deixa fora de `item_results` os casos em que a tarefa levantou exceção.
    falhas = len(itens) - len(resultado.item_results)
    if falhas:
        print(f"ATENÇÃO: {falhas} caso(s) falharam com erro e ficaram fora das métricas; veja os traces.")
    return resultado


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Benchmark v2 como experimento no Langfuse.")
    parser.add_argument("--no-ollama", action="store_true",
                        help="Síntese extrativa determinística local, sem chamar LLM.")
    parser.add_argument("--config", choices=list(CONFIGURACOES), default="completo",
                        help="Componentes de contexto do LLM (ablação). Padrão: completo.")
    parser.add_argument("--split", choices=["dev", "test"], help="Roda só um split do golden set.")
    parser.add_argument("--permitir-fallback", action="store_true",
                        help="Deixa o caso cair no modelo reserva ou no Ollama quando o principal falha.")
    parser.add_argument("--nome", help="Nome da execução no Langfuse (padrão: modo, split e data).")
    args = parser.parse_args(argv)

    resultado = executar(
        enable_llm=not args.no_ollama, split=args.split, nome=args.nome, nome_config=args.config,
        permitir_fallback=args.permitir_fallback,
    )
    print(f"Execução: {resultado.run_name} ({len(resultado.item_results)} casos concluídos)")
    for avaliacao in resultado.run_evaluations:
        valor = (f"{avaliacao.value:7.0f} car." if avaliacao.name in METRICAS_ABSOLUTAS
                 else f"{avaliacao.value * 100:6.1f}%")
        print(f"  {avaliacao.name:32s} {valor} ({avaliacao.comment})")
    modelos = sorted({str((r.output or {}).get("model_used")) for r in resultado.item_results})
    print(f"Modelos usados: {', '.join(modelos)}")
    if resultado.experiment_url:
        print(f"Langfuse: {resultado.experiment_url}")


if __name__ == "__main__":
    main()
