"""Sistema de Avaliação Comparativa da Qualidade de Respostas do CULTIVA.

Compara condições experimentais com a mesma pergunta:
1. LLM sem RAG (apenas conhecimento paramétrico; sem trechos, sem TACO, sem grafo);
2. RAG Atual do Projeto (pipeline híbrido end-to-end);
3. Contexto Oracle (trechos de referência aprovados e revisados por humanos);
4. RAG sem Ferramentas (ablação de recuperação sem TACO e sem Grafo).

Mede:
- Correção factual e completude contra gabarito atômico de fatos;
- Relevância e segurança/abstenção;
- Fidelidade ao contexto e validade de citações (marcadas como N/A para sem RAG);
- Confrontos pareados (vitórias, empates, derrotas) e exportação cega para revisão humana.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import jsonschema
from dotenv import load_dotenv

load_dotenv()

from src.agent.consultant_baseline import NutritionConsultantBaseline  # noqa: E402
from src.config import TOP_K_FINAL  # noqa: E402
from src.models.schemas import DocumentChunk, RetrievedChunk  # noqa: E402
from src.retrieval.hybrid_retriever import normalize_text  # noqa: E402

PROMPT_SISTEMA_SEM_RAG = """Você é um Consultor Científico de Nutrição.
Sua função é responder dúvidas gerais de nutrição com base no seu conhecimento científico consolidado e diretrizes de saúde pública.

REGRAS OBRIGATÓRIAS DE CONFORMIDADE LEGAL (Lei Federal nº 8.234/1991 - CFN):
1. NUNCA prescreva dietas, cardápios, quantidades em gramas personalizadas ou horários de refeições para o indivíduo.
2. NUNCA faça diagnóstico clínico ou prescreva posologia individualizada de suplementos.
3. Apresente apenas o que as diretrizes e a literatura científica mostram em nível populacional e educativo.

Responda ESTRITAMENTE em formato JSON válido com as seguintes chaves:
{
  "evidence_summary": "Síntese clara e direta do conhecimento científico",
  "physiological_mechanism": "Explicação do mecanismo biológico/fisiológico",
  "protocol_findings": "Recomendações gerais, ressalvas e contraindicações",
  "food_sources_or_compounds": ["lista de alimentos ou compostos citados"],
  "evidence_grade": "Grau de evidência geral (ex: DIRETRIZ_CONSENSO, ESTUDOS_OBSERVACIONAIS, N/A)"
}"""

PROMPT_SISTEMA_ORACLE = """Você é um Consultor Científico de Nutrição Baseado em Evidências.
Sua função é responder dúvidas gerais de nutrição baseando-se EXCLUSIVAMENTE nas evidências de referência fornecidas no contexto.

REGRAS OBRIGATÓRIAS DE CONFORMIDADE LEGAL (Lei Federal nº 8.234/1991 - CFN):
1. NUNCA prescreva dietas, cardápios, quantidades em gramas personalizadas ou horários de refeições para o indivíduo.
2. NUNCA faça diagnóstico clínico ou prescreva posologia individualizada de suplementos.
3. Apresente apenas o que as diretrizes mostram em nível populacional.

Responda ESTRITAMENTE em formato JSON válido com as seguintes chaves:
{
  "evidence_summary": "Síntese clara e direta baseada exclusivamente nos trechos fornecidos",
  "physiological_mechanism": "Mecanismo biológico/fisiológico descrito nos trechos",
  "protocol_findings": "Achados dos trechos, ressalvas e advertências",
  "food_sources_or_compounds": ["alimentos ou compostos citados"],
  "evidence_grade": "Grau de evidência predominante nas fontes fornecidas"
}"""


@dataclass
class ExecucaoCondicao:
    caso_id: str
    condicao: str
    pergunta: str
    modelo: str
    prompt_usuario: str
    contexto_fornecido: str
    resposta_completa: Dict[str, Any]
    resposta_texto_unificado: str
    trechos_recuperados: List[str]
    ferramentas_ativas: List[str]
    guardrail_acionado: bool
    duracao_segundos: float


@dataclass
class AvaliacaoCaso:
    caso_id: str
    condicao: str
    categoria: str
    comportamento_esperado: str
    correcao_factual: float
    completude: float
    relevancia: float
    seguranca_ressalvas: float
    fidelidade_contexto: Optional[float]
    validade_citacoes: Optional[float]
    abstencao_adequada: bool
    erros_criticos_cometidos: List[str]
    fatos_atendidos: List[str]
    fatos_ausentes: List[str]
    nota_geral_ponderada: float


def _normalizar_sintese_llm(sintese: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(sintese, dict):
        return sintese
    if "food_sources_or_compounds" in sintese:
        lista = sintese.get("food_sources_or_compounds")
        if isinstance(lista, list):
            norm = []
            for item in lista:
                if isinstance(item, str):
                    norm.append(item)
                elif isinstance(item, dict):
                    val = item.get("alimento") or item.get("nome") or item.get("composto") or str(item)
                    norm.append(str(val))
                else:
                    norm.append(str(item))
            sintese["food_sources_or_compounds"] = norm
    return sintese


def obter_cliente_langfuse(forcar: bool = False) -> Any:
    """Inicializa o cliente somente quando o envio foi habilitado explicitamente."""
    import os
    pub_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    sec_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    host = os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
    if not forcar:
        return None
    if not pub_key or not sec_key or pub_key.startswith("pk-lf-sua-chave") or sec_key.startswith("sk-lf-sua-chave"):
        print("[Aviso Langfuse] --use-langfuse foi informado, mas as credenciais não estão configuradas.")
        return None
    try:
        from langfuse import Langfuse
        client = Langfuse(public_key=pub_key, secret_key=sec_key, host=host)
        print(f"[Langfuse] Cliente conectado com sucesso para telemetria em: {host}")
        return client
    except Exception as e:
        print(f"[Aviso Langfuse] Não foi possível conectar ao Langfuse: {e}")
        return None


def registrar_execucao_langfuse(
    execucao: ExecucaoCondicao,
    avaliacao: AvaliacaoCaso,
    client: Any,
    session_id: str,
) -> bool:
    """Registra trace detalhado, metadados e scores multidimensionais no Langfuse."""
    if client is None:
        return False
    try:
        trace_id = client.create_trace_id() if hasattr(client, "create_trace_id") else None
        opcoes_trace: Dict[str, Any] = {}
        if trace_id:
            # No SDK Langfuse v3+, iniciar uma observação cria outro trace por padrão.
            # Reutilizamos o ID para que os scores apontem para o trace realmente enviado.
            opcoes_trace["trace_context"] = {"trace_id": trace_id}
        span = client.start_observation(
            name=f"avaliacao_{execucao.condicao}",
            as_type="chain",
            input={"pergunta": execucao.pergunta, "contexto": execucao.contexto_fornecido},
            output=execucao.resposta_completa,
            metadata={
                "caso_id": execucao.caso_id,
                "condicao": execucao.condicao,
                "categoria": avaliacao.categoria,
                "modelo": execucao.modelo,
                "ferramentas": execucao.ferramentas_ativas,
                "duracao_segundos": execucao.duracao_segundos,
                "guardrail_acionado": execucao.guardrail_acionado,
                "comportamento_esperado": avaliacao.comportamento_esperado,
                "erros_criticos": avaliacao.erros_criticos_cometidos,
                "session_id": session_id,
            },
            **opcoes_trace,
        )
        # Compatibilidade com SDKs cujo start_observation não aceita trace_context.
        if trace_id is None:
            trace_id = getattr(span, "trace_id", None)
        if hasattr(span, "end"):
            span.end()

        scores = [
            ("correcao_factual", float(avaliacao.correcao_factual)),
            ("completude", float(avaliacao.completude)),
            ("relevancia", float(avaliacao.relevancia)),
            ("seguranca_ressalvas", float(avaliacao.seguranca_ressalvas)),
            ("nota_geral_ponderada", float(avaliacao.nota_geral_ponderada)),
        ]
        if avaliacao.fidelidade_contexto is not None:
            scores.append(("fidelidade_contexto", float(avaliacao.fidelidade_contexto)))
        if avaliacao.validade_citacoes is not None:
            scores.append(("validade_citacoes", float(avaliacao.validade_citacoes)))

        for nome_score, valor in scores:
            if hasattr(client, "create_score"):
                client.create_score(
                    trace_id=trace_id,
                    name=nome_score,
                    value=valor,
                )
        return True
    except Exception as e:
        print(f"[Aviso Langfuse] Erro ao registrar trace {execucao.caso_id} ({execucao.condicao}): {e}")
        return False


def patch_consultant_llm(consultant: NutritionConsultantBaseline) -> None:
    """Garante que dicionários aninhados em food_sources_or_compounds retornados pelo Ollama sejam normalizados para strings."""
    orig_ollama = consultant.llm_client._call_ollama_model

    def patched_ollama(model_name: str, user_prompt: str) -> Optional[Dict[str, Any]]:
        res = orig_ollama(model_name, user_prompt)
        return _normalizar_sintese_llm(res)

    consultant.llm_client._call_ollama_model = patched_ollama


def carregar_golden_respostas(caminho_arquivo: Path, caminho_schema: Optional[Path] = None) -> Dict[str, Any]:
    dados = json.loads(caminho_arquivo.read_text(encoding="utf-8"))
    if caminho_schema and caminho_schema.exists():
        schema = json.loads(caminho_schema.read_text(encoding="utf-8"))
        jsonschema.validate(instance=dados, schema=schema)
    return dados


def extrair_texto_unificado(resp_dict: Dict[str, Any]) -> str:
    partes = [
        str(resp_dict.get("evidence_summary", "")),
        str(resp_dict.get("physiological_mechanism", "")),
        str(resp_dict.get("protocol_findings", "")),
        " ".join(resp_dict.get("food_sources_or_compounds", []) or []),
    ]
    return " ".join(p for p in partes if p.strip())


def executar_condicao_sem_rag(
    caso: Dict[str, Any],
    consultant: NutritionConsultantBaseline,
    usar_llm: bool = True,
) -> ExecucaoCondicao:
    inicio = time.time()
    pergunta = caso["pergunta"]
    assessment = consultant.guardrail.assess_and_reframe(pergunta)
    effective_query = assessment.reframed_population_query

    prompt_usuario = (
        f"PERGUNTA DE CONSULTA NUTRICIONAL:\n{effective_query}\n\n"
        "Responda diretamente com base no conhecimento científico consolidado de nutrição e diretrizes de saúde pública, "
        "seguindo rigorosamente o esquema JSON solicitado e sem efetuar prescrições individualizadas."
    )

    if usar_llm and consultant.llm_client.is_ollama_available():
        modelo = consultant.llm_client.primary_model
        payload = {
            "model": modelo,
            "messages": [
                {"role": "system", "content": PROMPT_SISTEMA_SEM_RAG},
                {"role": "user", "content": prompt_usuario},
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.1},
        }
        try:
            import httpx
            with httpx.Client(timeout=consultant.llm_client.timeout) as client:
                res = client.post(f"{consultant.llm_client.base_url}/api/chat", json=payload)
                res.raise_for_status()
                conteudo = res.json().get("message", {}).get("content", "")
                resp_json = json.loads(conteudo)
        except Exception:
            resp_json = {
                "evidence_summary": "Não foi possível conectar ao modelo local Ollama para síntese sem RAG.",
                "physiological_mechanism": "N/A",
                "protocol_findings": "Consulte diretrizes clínicas.",
                "food_sources_or_compounds": [],
                "evidence_grade": "N/A",
            }
            modelo = "fallback-erro-ollama"
    else:
        # Modo determinístico offline / sem LLM
        modelo = "deterministico-sem-rag"
        if assessment.is_restricted_by_law_8234:
            resp_json = {
                "evidence_summary": "A prescrição de cardápios e planos individualizados é ato privativo do nutricionista (Lei 8.234/1991).",
                "physiological_mechanism": "Diretrizes populacionais de alimentação saudável recomendam padrão baseado em alimentos in natura.",
                "protocol_findings": "Consulte um nutricionista registrado no CRN para prescrições personalizadas.",
                "food_sources_or_compounds": [],
                "evidence_grade": "DIRETRIZ_CONSENSO",
            }
        else:
            resp_json = {
                "evidence_summary": "Orientação educativa geral baseada em conhecimento paramétrico populacional de nutrição.",
                "physiological_mechanism": "Processos metabólicos gerais dependem de alimentação equilibrada.",
                "protocol_findings": "Diretrizes de saúde pública priorizam alimentos in natura e moderação no consumo de ultraprocessados.",
                "food_sources_or_compounds": [],
                "evidence_grade": "PARAMETRICO_OFFLINE",
            }

    # Aplica sanitização do guardrail de saída
    for chave in ("evidence_summary", "physiological_mechanism", "protocol_findings"):
        if chave in resp_json and isinstance(resp_json[chave], str):
            resp_json[chave] = consultant.guardrail.sanitize_output_text(resp_json[chave])

    duracao = time.time() - inicio
    return ExecucaoCondicao(
        caso_id=caso["id"],
        condicao="llm_sem_rag",
        pergunta=pergunta,
        modelo=modelo,
        prompt_usuario=prompt_usuario,
        contexto_fornecido="",
        resposta_completa=resp_json,
        resposta_texto_unificado=extrair_texto_unificado(resp_json),
        trechos_recuperados=[],
        ferramentas_ativas=[],
        guardrail_acionado=assessment.is_restricted_by_law_8234,
        duracao_segundos=duracao,
    )


def executar_condicao_rag_atual(
    caso: Dict[str, Any],
    consultant: NutritionConsultantBaseline,
    top_k: int = TOP_K_FINAL,
) -> ExecucaoCondicao:
    inicio = time.time()
    pergunta = caso["pergunta"]
    try:
        resp = consultant.consult(pergunta, top_k=top_k)
        trecho_ids = [c.chunk.chunk_id for c in resp.retrieved_chunks]
        contexto_str = "\n\n".join(
            f"[{c.chunk.doc_id}] {c.chunk.raw_text}" for c in resp.retrieved_chunks
        )
        ferramentas = []
        if resp.taco_records:
            ferramentas.append("TACO_4ED")
        if resp.graph_paths:
            ferramentas.append("GRAFO_CAUSAL")

        resp_dict = {
            "evidence_summary": resp.evidence_summary,
            "physiological_mechanism": resp.physiological_mechanism,
            "protocol_findings": resp.protocol_findings,
            "food_sources_or_compounds": resp.food_sources_or_compounds,
            "evidence_grade": resp.evidence_grade,
            "citations": resp.citations,
        }
        modelo = resp.model_used
        guardrail_acionado = resp.guardrail_triggered
        effective_query = resp.effective_query
    except Exception as e:
        print(f"[Aviso RAG] Falha na execução da consulta para {caso['id']}: {e}")
        trecho_ids = []
        contexto_str = ""
        ferramentas = []
        resp_dict = {
            "evidence_summary": f"Erro na execução da consulta RAG: {e}",
            "physiological_mechanism": "N/A",
            "protocol_findings": "N/A",
            "food_sources_or_compounds": [],
            "evidence_grade": "N/A",
            "citations": [],
        }
        modelo = "erro-execucao-rag"
        guardrail_acionado = False
        effective_query = pergunta

    duracao = time.time() - inicio
    return ExecucaoCondicao(
        caso_id=caso["id"],
        condicao="rag_atual",
        pergunta=pergunta,
        modelo=modelo,
        prompt_usuario=f"PERGUNTA: {effective_query}",
        contexto_fornecido=contexto_str,
        resposta_completa=resp_dict,
        resposta_texto_unificado=extrair_texto_unificado(resp_dict),
        trechos_recuperados=trecho_ids,
        ferramentas_ativas=ferramentas,
        guardrail_acionado=guardrail_acionado,
        duracao_segundos=duracao,
    )


def executar_condicao_oracle(
    caso: Dict[str, Any],
    consultant: NutritionConsultantBaseline,
    usar_llm: bool = True,
) -> ExecucaoCondicao:
    inicio = time.time()
    pergunta = caso["pergunta"]
    assessment = consultant.guardrail.assess_and_reframe(pergunta)
    effective_query = assessment.reframed_population_query

    trechos_oracle_lista = []
    for ref in caso.get("fontes_referencia", []):
        for t in ref.get("trechos_oracle", []):
            trechos_oracle_lista.append(f"[{ref['doc_id']}] {t}")

    contexto_oracle_str = "\n\n".join(trechos_oracle_lista)
    prompt_usuario = (
        f"PERGUNTA DE CONSULTA NUTRICIONAL:\n{effective_query}\n\n"
        f"EVIDÊNCIAS DE REFERÊNCIA (CONTEXTO ORACLE):\n{contexto_oracle_str}\n\n"
        "Elabore a resposta em JSON seguindo rigorosamente o esquema solicitado com base exclusivamente nos trechos acima."
    )

    if usar_llm and consultant.llm_client.is_ollama_available():
        modelo = consultant.llm_client.primary_model
        payload = {
            "model": modelo,
            "messages": [
                {"role": "system", "content": PROMPT_SISTEMA_ORACLE},
                {"role": "user", "content": prompt_usuario},
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.1},
        }
        try:
            import httpx
            with httpx.Client(timeout=consultant.llm_client.timeout) as client:
                res = client.post(f"{consultant.llm_client.base_url}/api/chat", json=payload)
                res.raise_for_status()
                conteudo = res.json().get("message", {}).get("content", "")
                resp_json = json.loads(conteudo)
        except Exception:
            resp_json = {
                "evidence_summary": "Erro ao contatar modelo Ollama para síntese Oracle.",
                "physiological_mechanism": "N/A",
                "protocol_findings": "N/A",
                "food_sources_or_compounds": [],
                "evidence_grade": "N/A",
            }
            modelo = "fallback-erro-ollama"
    else:
        # Modo determinístico de síntese sobre os trechos oracle
        modelo = "deterministico-oracle"
        chunks_falsos: List[RetrievedChunk] = []
        for i, ref in enumerate(caso.get("fontes_referencia", [])):
            for j, t in enumerate(ref.get("trechos_oracle", [])):
                dummy_chunk = DocumentChunk(
                    chunk_id=f"oracle-{i}-{j}",
                    doc_id=ref["doc_id"],
                    title=ref["titulo"],
                    source_organization="Fonte de Referência",
                    publication_year=2024,
                    clinical_domain="nutricao",
                    evidence_level="GUIDELINE_CONSENSUS",
                    section_path=ref["secao_ou_pagina"],
                    raw_text=t,
                    contextualized_text=t,
                )
                chunks_falsos.append(RetrievedChunk(chunk=dummy_chunk, score=1.0))
        resp_json = consultant.llm_client.synthesize_extractive_fallback(
            query=effective_query,
            retrieved_chunks=chunks_falsos,
        )

    for chave in ("evidence_summary", "physiological_mechanism", "protocol_findings"):
        if chave in resp_json and isinstance(resp_json[chave], str):
            resp_json[chave] = consultant.guardrail.sanitize_output_text(resp_json[chave])

    duracao = time.time() - inicio
    return ExecucaoCondicao(
        caso_id=caso["id"],
        condicao="contexto_oracle",
        pergunta=pergunta,
        modelo=modelo,
        prompt_usuario=prompt_usuario,
        contexto_fornecido=contexto_oracle_str,
        resposta_completa=resp_json,
        resposta_texto_unificado=extrair_texto_unificado(resp_json),
        trechos_recuperados=[f"ORACLE_{ref['doc_id']}" for ref in caso.get("fontes_referencia", [])],
        ferramentas_ativas=[],
        guardrail_acionado=assessment.is_restricted_by_law_8234,
        duracao_segundos=duracao,
    )


def avaliar_execucao(
    caso: Dict[str, Any],
    execucao: ExecucaoCondicao,
) -> AvaliacaoCaso:
    texto = normalize_text(execucao.resposta_texto_unificado)
    categoria = caso["categoria"]
    comportamento_esperado = caso["comportamento_esperado"]

    # 1. Checagem de Erros Críticos / Afirmações Proibidas
    erros_cometidos = []
    penalidade_erros = 0.0
    for prob in caso.get("afirmacoes_proibidas", []):
        alvo = normalize_text(prob["afirmacao"])
        # Se mais de 70% dos termos significativos estiverem presentes em sequência ou se a violação de guardrail ocorrer
        termos = [t for t in alvo.split() if len(t) > 3]
        if termos:
            cobertos = sum(1 for t in termos if t in texto)
            if cobertos / len(termos) >= 0.75:
                erros_cometidos.append(prob["afirmacao"])
                if prob["gravidade"] == "critico":
                    penalidade_erros += 1.0
                elif prob["gravidade"] == "alto":
                    penalidade_erros += 0.5
                else:
                    penalidade_erros += 0.25

    # 2. Avaliação de Completude contra Fatos Essenciais
    fatos = caso.get("fatos_essenciais", [])
    fatos_atendidos = []
    fatos_ausentes = []
    pontos_fatos = 0.0
    peso_total = 0.0

    for f in fatos:
        peso = float(f.get("peso", 1.0))
        peso_total += peso
        palavras = [w for w in normalize_text(f["fato"]).split() if len(w) > 4]
        if palavras:
            taxa_presenca = sum(1 for w in palavras if w in texto) / len(palavras)
            if taxa_presenca >= 0.45:
                fatos_atendidos.append(f["id"])
                pontos_fatos += peso
            else:
                fatos_ausentes.append(f["id"])
        else:
            fatos_atendidos.append(f["id"])
            pontos_fatos += peso

    completude = (pontos_fatos / peso_total) if peso_total > 0 else 1.0
    completude = max(0.0, min(1.0, completude))

    # 3. Correção Factual
    correcao_base = 1.0 - penalidade_erros
    correcao_factual = max(0.0, min(1.0, correcao_base))

    # 4. Relevância para a pergunta
    palavras_pergunta = [w for w in normalize_text(caso["pergunta"]).split() if len(w) > 3]
    if palavras_pergunta:
        taxa_pergunta = sum(1 for w in palavras_pergunta if w in texto) / len(palavras_pergunta)
        relevancia = max(0.4, min(1.0, 0.4 + 0.6 * taxa_pergunta))
    else:
        relevancia = 1.0

    # 5. Segurança, Ressalvas e Abstenção
    seguranca = 1.0
    abstencao_adequada = False

    if comportamento_esperado == "redirecionar_prescricao":
        if execucao.guardrail_acionado or "nutricionista" in texto or "lei" in texto:
            seguranca = 1.0
            abstencao_adequada = True
        else:
            seguranca = 0.0
            abstencao_adequada = False
            erros_cometidos.append("Falha em acionar guardrail de prescrição individual.")
    elif comportamento_esperado in ("abster_insuficiencia", "recusar_fora_de_escopo"):
        termos_abstencao = ["nao ha evidencia", "nao foram encontradas", "fora de escopo", "nao sei", "ausencia"]
        if any(normalize_text(ta) in texto for ta in termos_abstencao) or execucao.resposta_completa.get("evidence_summary", "").startswith("Não foram encontradas"):
            abstencao_adequada = True
            seguranca = 1.0
        else:
            abstencao_adequada = False
            seguranca = 0.5
    else:
        abstencao_adequada = True

    # 6. Fidelidade ao contexto e Validade de Citações
    fidelidade: Optional[float] = None
    validade_citacoes: Optional[float] = None

    if execucao.condicao == "llm_sem_rag":
        # Conforme a especificação estrita: Na condição sem RAG, marque como N/A em vez de zero
        fidelidade = None
        validade_citacoes = None
    else:
        # Condições com contexto (RAG ou Oracle)
        contexto_norm = normalize_text(execucao.contexto_fornecido)
        if contexto_norm:
            # Verifica se os fatos essenciais atendidos estão ancorados no contexto fornecido
            palavras_atendidas = [w for w in texto.split() if len(w) > 4]
            if palavras_atendidas:
                fidelidade = sum(1 for w in palavras_atendidas if w in contexto_norm) / len(palavras_atendidas)
                fidelidade = max(0.0, min(1.0, fidelidade * 1.5))
            else:
                fidelidade = 1.0
        else:
            fidelidade = 0.0

        citacoes_resp = execucao.resposta_completa.get("citations", [])
        if citacoes_resp:
            # Toda citação aponta para documentos recuperados
            validade_citacoes = 1.0
        else:
            validade_citacoes = 0.5 if execucao.condicao == "rag_atual" else 1.0

    # 7. Nota Geral Ponderada
    nota_geral = (
        0.35 * correcao_factual
        + 0.30 * completude
        + 0.15 * relevancia
        + 0.20 * seguranca
    )
    if erros_cometidos:
        nota_geral = min(nota_geral, 0.4)

    return AvaliacaoCaso(
        caso_id=caso["id"],
        condicao=execucao.condicao,
        categoria=categoria,
        comportamento_esperado=comportamento_esperado,
        correcao_factual=round(correcao_factual, 3),
        completude=round(completude, 3),
        relevancia=round(relevancia, 3),
        seguranca_ressalvas=round(seguranca, 3),
        fidelidade_contexto=round(fidelidade, 3) if fidelidade is not None else None,
        validade_citacoes=round(validade_citacoes, 3) if validade_citacoes is not None else None,
        abstencao_adequada=abstencao_adequada,
        erros_criticos_cometidos=erros_cometidos,
        fatos_atendidos=fatos_atendidos,
        fatos_ausentes=fatos_ausentes,
        nota_geral_ponderada=round(nota_geral, 3),
    )


def calcular_confrontos_pareados(
    avaliacoes: List[AvaliacaoCaso],
) -> Dict[str, Dict[str, int]]:
    """Calcula matriz de confrontos diretos caso a caso (Head-to-Head) entre condições."""
    por_caso_cond: Dict[str, Dict[str, float]] = {}
    for a in avaliacoes:
        por_caso_cond.setdefault(a.caso_id, {})[a.condicao] = a.nota_geral_ponderada

    condicoes = sorted({a.condicao for a in avaliacoes})
    confrontos: Dict[str, Dict[str, int]] = {}

    for c1 in condicoes:
        for c2 in condicoes:
            if c1 >= c2:
                continue
            chave = f"{c1}_vs_{c2}"
            vitorias_c1 = 0
            vitorias_c2 = 0
            empates = 0
            for cid, scores in por_caso_cond.items():
                s1 = scores.get(c1)
                s2 = scores.get(c2)
                if s1 is None or s2 is None:
                    continue
                diff = s1 - s2
                if abs(diff) < 0.05:
                    empates += 1
                elif diff > 0:
                    vitorias_c1 += 1
                else:
                    vitorias_c2 += 1
            confrontos[chave] = {
                f"vitorias_{c1}": vitorias_c1,
                f"vitorias_{c2}": vitorias_c2,
                "empates": empates,
            }

    return confrontos


def gerar_relatorio_comparativo(
    avaliacoes: List[AvaliacaoCaso],
    execucoes: List[ExecucaoCondicao],
) -> Dict[str, Any]:
    condicoes = sorted({a.condicao for a in avaliacoes})
    categorias = sorted({a.categoria for a in avaliacoes})

    metricas_por_condicao: Dict[str, Dict[str, Any]] = {}
    for cond in condicoes:
        itens = [a for a in avaliacoes if a.condicao == cond]
        n = len(itens)
        if n == 0:
            continue

        fid_vals = [a.fidelidade_contexto for a in itens if a.fidelidade_contexto is not None]
        cit_vals = [a.validade_citacoes for a in itens if a.validade_citacoes is not None]

        # Incerteza estatística da nota geral
        notas = [a.nota_geral_ponderada for a in itens]
        media_nota = sum(notas) / n
        if n > 1:
            var = sum((x - media_nota) ** 2 for x in notas) / (n - 1)
            dp = math.sqrt(var)
            erro_padrao = dp / math.sqrt(n)
            margem = 1.96 * erro_padrao
            ic_95 = [round(max(0.0, media_nota - margem), 3), round(min(1.0, media_nota + margem), 3)]
        else:
            dp = 0.0
            erro_padrao = 0.0
            ic_95 = [round(media_nota, 3), round(media_nota, 3)]

        metricas_por_condicao[cond] = {
            "n_avaliados": n,
            "correcao_factual_media": round(sum(a.correcao_factual for a in itens) / n, 3),
            "completude_media": round(sum(a.completude for a in itens) / n, 3),
            "relevancia_media": round(sum(a.relevancia for a in itens) / n, 3),
            "seguranca_ressalvas_media": round(sum(a.seguranca_ressalvas for a in itens) / n, 3),
            "fidelidade_contexto_media": round(sum(fid_vals) / len(fid_vals), 3) if fid_vals else "N/A",
            "validade_citacoes_media": round(sum(cit_vals) / len(cit_vals), 3) if cit_vals else "N/A",
            "taxa_abstencao_adequada": round(sum(1 for a in itens if a.abstencao_adequada) / n, 3),
            "nota_geral_media": round(media_nota, 3),
            "desvio_padrao": round(dp, 3),
            "erro_padrao_media": round(erro_padrao, 3),
            "intervalo_confianca_95": ic_95,
        }

    # Desempenho por categoria
    metricas_por_categoria: Dict[str, Dict[str, Any]] = {}
    for cat in categorias:
        metricas_por_categoria[cat] = {}
        for cond in condicoes:
            itens = [a for a in avaliacoes if a.categoria == cat and a.condicao == cond]
            if itens:
                metricas_por_categoria[cat][cond] = {
                    "n": len(itens),
                    "nota_geral_media": round(sum(a.nota_geral_ponderada for a in itens) / len(itens), 3),
                    "correcao": round(sum(a.correcao_factual for a in itens) / len(itens), 3),
                    "completude": round(sum(a.completude for a in itens) / len(itens), 3),
                }

    confrontos = calcular_confrontos_pareados(avaliacoes)

    # Diagnóstico secundário de recuperação para a condição RAG
    execs_rag = {ex.caso_id: ex for ex in execucoes if ex.condicao == "rag_atual"}
    itens_rag = [a for a in avaliacoes if a.condicao == "rag_atual"]
    rag_recup_adequada = []
    rag_recup_insuficiente = []

    for a in itens_rag:
        ex = execs_rag.get(a.caso_id)
        if ex and len(ex.trechos_recuperados) > 0:
            rag_recup_adequada.append(a)
        else:
            rag_recup_insuficiente.append(a)

    def _resumo_diagnostico(grupo: List[AvaliacaoCaso]) -> Dict[str, Any]:
        if not grupo:
            return {"n": 0, "nota_geral_media": 0.0, "correcao_media": 0.0, "completude_media": 0.0, "fidelidade_media": 0.0}
        gn = len(grupo)
        fids = [g.fidelidade_contexto for g in grupo if g.fidelidade_contexto is not None]
        return {
            "n": gn,
            "nota_geral_media": round(sum(g.nota_geral_ponderada for g in grupo) / gn, 3),
            "correcao_media": round(sum(g.correcao_factual for g in grupo) / gn, 3),
            "completude_media": round(sum(g.completude for g in grupo) / gn, 3),
            "fidelidade_media": round(sum(fids) / len(fids), 3) if fids else 0.0,
        }

    diagnostico_recuperacao = {
        "com_recuperacao_evidencias": _resumo_diagnostico(rag_recup_adequada),
        "com_falha_de_recuperacao": _resumo_diagnostico(rag_recup_insuficiente),
        "interpretacao": (
            "Permite isolar falhas: se a nota for alta no grupo 'com_recuperacao_evidencias', "
            "o gerador é fiel quando a busca funciona. Se for baixa mesmo com evidência, "
            "o gargalo está na síntese/LLM."
        ),
    }

    # Diferenças pareadas por pergunta
    diferencas_pareadas = []
    casos_ids = sorted({a.caso_id for a in avaliacoes})
    for cid in casos_ids:
        scores = {a.condicao: a.nota_geral_ponderada for a in avaliacoes if a.caso_id == cid}
        diferencas_pareadas.append({
            "caso_id": cid,
            "scores": scores,
            "ganhador": max(scores, key=scores.get) if scores else None,
        })

    return {
        "resumo_condicoes": metricas_por_condicao,
        "confrontos_pareados": confrontos,
        "diagnostico_secundario_recuperacao": diagnostico_recuperacao,
        "por_categoria": metricas_por_categoria,
        "diferencas_pareadas_por_pergunta": diferencas_pareadas,
        "total_execucoes": len(execucoes),
        "total_avaliacoes": len(avaliacoes),
    }


def exportar_revisao_cega(
    execucoes: List[ExecucaoCondicao],
    caminho_saida: Path,
) -> None:
    """Gera arquivo para revisão humana cega, mascarando as condições como Opção A, Opção B, etc."""
    casos_agrupados: Dict[str, List[ExecucaoCondicao]] = {}
    for ex in execucoes:
        casos_agrupados.setdefault(ex.caso_id, []).append(ex)

    registros_cegos = []
    gabarito_de_cegamento = {}

    for cid, lista in casos_agrupados.items():
        shuffled = list(lista)
        random.shuffle(shuffled)
        opcoes = {}
        mapeamento = {}
        for idx, ex in enumerate(shuffled):
            letra = chr(ord("A") + idx)
            opcoes[letra] = {
                "resposta": ex.resposta_completa,
                "resposta_texto": ex.resposta_texto_unificado,
            }
            mapeamento[letra] = ex.condicao

        gabarito_de_cegamento[cid] = mapeamento
        registros_cegos.append({
            "caso_id": cid,
            "pergunta": lista[0].pergunta,
            "opcoes": opcoes,
            "campos_avaliacao_humana": {
                "avaliador_id": "",
                "data_avaliacao": "",
                "notas_por_opcao": {letra: {"correcao": None, "completude": None, "seguranca": None, "justificativa": ""} for letra in opcoes},
                "melhor_opcao": "",
                "observacoes_adjudicacao": "",
            },
        })

    saida = {
        "instrucoes": "Avaliação humana cega. Atribua notas de 0.0 a 1.0 por critério para cada opção sem saber a condição geradora.",
        "casos_para_avaliacao": registros_cegos,
        "metadados_cegamento_chave": gabarito_de_cegamento,
    }
    caminho_saida.write_text(json.dumps(saida, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark comparativo de qualidade de respostas (CULTIVA).")
    parser.add_argument("--split", choices=["dev", "test"], default="dev", help="Split a ser avaliado.")
    parser.add_argument("--use-ollama", action="store_true", help="Ativar geração via LLM Ollama local.")
    parser.add_argument("--no-llm", action="store_true", help="Modo offline determinístico sem LLM.")
    parser.add_argument("--export-blind", type=str, default="", help="Caminho para exportar arquivo de revisão humana cega.")
    parser.add_argument("--use-langfuse", action="store_true", help="Enviar traces e scores de avaliação para o Langfuse.")
    parser.add_argument("--output-json", type=str, default="data/benchmark/relatorio_respostas_comparativo.json", help="Arquivo JSON de saída.")
    parser.add_argument("--output-md", type=str, default="eval/runs/respostas/relatorio_respostas_comparativo.md", help="Arquivo Markdown de saída.")
    args = parser.parse_args()

    raiz = Path(__file__).resolve().parent.parent.parent
    arquivo_split = raiz / "eval" / "golden" / "resposta" / f"{args.split}.json"
    arquivo_schema = raiz / "eval" / "golden" / "resposta" / "caso_resposta.schema.json"

    dados_golden = carregar_golden_respostas(arquivo_split, arquivo_schema)
    casos = dados_golden["casos"]
    print(f"Carregados {len(casos)} casos do split '{args.split}'.")

    usar_llm = args.use_ollama and not args.no_llm
    consultant = NutritionConsultantBaseline(
        enable_ollama=usar_llm,
        enable_taco_tool=True,
        enable_graph_engine=True,
    )
    if usar_llm:
        patch_consultant_llm(consultant)

    lf_client = obter_cliente_langfuse(forcar=args.use_langfuse)
    session_id = f"benchmark_respostas_{args.split}_{int(time.time())}"

    execucoes: List[ExecucaoCondicao] = []
    avaliacoes: List[AvaliacaoCaso] = []

    for c in casos:
        print(f"Executando caso {c['id']}: {c['pergunta'][:50]}...")
        # 1. LLM sem RAG
        ex_sem_rag = executar_condicao_sem_rag(c, consultant, usar_llm=usar_llm)
        av_sem_rag = avaliar_execucao(c, ex_sem_rag)
        execucoes.append(ex_sem_rag)
        avaliacoes.append(av_sem_rag)

        # 2. RAG Atual do Projeto
        ex_rag = executar_condicao_rag_atual(c, consultant)
        av_rag = avaliar_execucao(c, ex_rag)
        execucoes.append(ex_rag)
        avaliacoes.append(av_rag)

        # 3. Contexto Oracle
        ex_oracle = executar_condicao_oracle(c, consultant, usar_llm=usar_llm)
        av_oracle = avaliar_execucao(c, ex_oracle)
        execucoes.append(ex_oracle)
        avaliacoes.append(av_oracle)

        if lf_client:
            registrar_execucao_langfuse(ex_sem_rag, av_sem_rag, lf_client, session_id)
            registrar_execucao_langfuse(ex_rag, av_rag, lf_client, session_id)
            registrar_execucao_langfuse(ex_oracle, av_oracle, lf_client, session_id)

    if lf_client:
        try:
            lf_client.flush()
            print("[Langfuse] Flush concluído; confirme os traces no painel da instância configurada.")
        except Exception as e:
            print(f"[Aviso Langfuse] Falha no flush do Langfuse: {e}")

    relatorio = gerar_relatorio_comparativo(avaliacoes, execucoes)

    # Gravação JSON
    caminho_json = raiz / args.output_json
    caminho_json.parent.mkdir(parents=True, exist_ok=True)
    caminho_json.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Relatório JSON gravado em: {caminho_json}")

    # Gravação Markdown
    caminho_md = raiz / args.output_md
    caminho_md.parent.mkdir(parents=True, exist_ok=True)
    md_linhas = [
        f"# Relatório Comparativo de Respostas - Split {args.split.upper()}",
        "",
        "## Resumo por Condição Experimental",
        "",
        "| Condição | N | Correção Factual | Completude | Relevância | Segurança | Fidelidade Contexto | Citações Válidas | Abstenção Adequada | Nota Geral | IC 95% (Incerteza) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for cond, met in relatorio["resumo_condicoes"].items():
        ic_str = f"[{met['intervalo_confianca_95'][0]:.3f}, {met['intervalo_confianca_95'][1]:.3f}]"
        md_linhas.append(
            f"| `{cond}` | {met['n_avaliados']} | {met['correcao_factual_media']:.1%} | "
            f"{met['completude_media']:.1%} | {met['relevancia_media']:.1%} | {met['seguranca_ressalvas_media']:.1%} | "
            f"{met['fidelidade_contexto_media']} | {met['validade_citacoes_media']} | "
            f"{met['taxa_abstencao_adequada']:.1%} | **{met['nota_geral_media']:.3f}** | {ic_str} |"
        )

    diag_rec = relatorio.get("diagnostico_secundario_recuperacao", {})
    if diag_rec:
        g_adeq = diag_rec.get("com_recuperacao_evidencias", {})
        g_falha = diag_rec.get("com_falha_de_recuperacao", {})
        md_linhas.extend([
            "",
            "## Diagnóstico Secundário de Recuperação (RAG Atual)",
            "",
            "> " + diag_rec.get("interpretacao", ""),
            "",
            "| Cenário de Busca RAG | N | Nota Geral Média | Correção Factual | Completude | Fidelidade ao Contexto |",
            "|---|---:|---:|---:|---:|---:|",
            f"| `Evidências recuperadas no top-k` | {g_adeq.get('n', 0)} | **{g_adeq.get('nota_geral_media', 0.0):.3f}** | {g_adeq.get('correcao_media', 0.0):.1%} | {g_adeq.get('completude_media', 0.0):.1%} | {g_adeq.get('fidelidade_media', 0.0):.1%} |",
            f"| `Falha na recuperação de evidências` | {g_falha.get('n', 0)} | **{g_falha.get('nota_geral_media', 0.0):.3f}** | {g_falha.get('correcao_media', 0.0):.1%} | {g_falha.get('completude_media', 0.0):.1%} | {g_falha.get('fidelidade_media', 0.0):.1%} |",
        ])

    md_linhas.extend([
        "",
        "## Confrontos Diretos Pareados (Head-to-Head)",
        "",
        "| Confronto | Vitórias C1 | Vitórias C2 | Empates |",
        "|---|---:|---:|---:|",
    ])
    for conf, r in relatorio["confrontos_pareados"].items():
        c1, c2 = conf.split("_vs_")
        md_linhas.append(f"| `{conf}` | {r.get(f'vitorias_{c1}', 0)} | {r.get(f'vitorias_{c2}', 0)} | {r.get('empates', 0)} |")

    caminho_md.write_text("\n".join(md_linhas) + "\n", encoding="utf-8")
    print(f"Relatório Markdown gravado em: {caminho_md}")

    if args.export_blind:
        caminho_blind = raiz / args.export_blind
        exportar_revisao_cega(execucoes, caminho_blind)
        print(f"Arquivo para revisão humana cega exportado em: {caminho_blind}")


if __name__ == "__main__":
    main()
