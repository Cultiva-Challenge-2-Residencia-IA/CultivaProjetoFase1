import sys
import threading
from typing import Optional
from typing import List

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from src.agent.consultant_baseline import NutritionConsultantBaseline
from src.rag.corpus_loader import inventario_de_fontes
from src.config import TOP_K_FINAL
from src.models.schemas import ConsultantResponse
from src.agent.traceability import register_incorrect_feedback, save_response_trace
from src.observabilidade import registrar_feedback_incorreto
from src.chat.autenticacao import (
    AutenticacaoNaoConfigurada,
    TokenInvalido,
    configuracao_do_ambiente,
    verificar_token,
)
from src.chat.servico import CHATS, ConversaDeOutroUsuario, RespostaDoChat, ServicoDeChat
from src.multimodal.imagem import (MAX_BYTES_IMAGEM, MAX_FOTOS, ImagemInvalida, ler_rotulo, perguntar_fotos,
                                   resumir_fotos)
from src.multimodal.pdf import MAX_BYTES, PDFInvalido, perguntar_pdf, resumir_pdf

app = FastAPI(
    title="Consultor Científico de Nutrição Baseado em Evidências (Fase 1 - Baseline RAG Híbrido)",
    description=(
        "Sistema de apoio informativo baseado em diretrizes científicas e literatura (RAG Híbrido: BM25 + "
        "Vetorial Local + RRF + Reranker), em conformidade com a Lei Federal nº 8.234/1991 (CFN)."
    ),
    version="0.1.0",
)

_consultant_instance: Optional[NutritionConsultantBaseline] = None


def get_consultant() -> NutritionConsultantBaseline:
    global _consultant_instance
    if _consultant_instance is None:
        _consultant_instance = NutritionConsultantBaseline(enable_ollama=True)
    return _consultant_instance


_servico_de_chat: Optional[ServicoDeChat] = None
_trava_do_servico = threading.Lock()


def get_servico_de_chat() -> ServicoDeChat:
    """Serviço do Chat geral e dos Chats de área (issue #99), montado na primeira chamada."""
    global _servico_de_chat
    with _trava_do_servico:  # endpoints síncronos rodam em threads: monta uma vez só
        if _servico_de_chat is None:
            from src.chat.fabrica import criar_servico

            _servico_de_chat = criar_servico(enable_ollama=True)
    return _servico_de_chat


_portador = HTTPBearer(auto_error=False, description="Token do Usuário emitido pelo App (issue #108).")


def usuario_autenticado(
    credenciais: Optional[HTTPAuthorizationCredentials] = Depends(_portador),
) -> Optional[str]:
    """Id do Usuário tirado do token `Authorization: Bearer ...` (issue #108).

    Devolve None só no modo de desenvolvimento explícito (`CULTIVA_AUTH_DESLIGADA=true` sem segredo),
    em que o `usuario_id` vem do cliente. O token não vai para log nem para a mensagem de erro.
    """
    try:
        configuracao = configuracao_do_ambiente()
    except AutenticacaoNaoConfigurada as erro:
        raise HTTPException(status_code=503, detail=str(erro)) from None
    if configuracao.modo == "desligada":
        return None
    if configuracao.modo == "nao_configurada":
        raise HTTPException(status_code=503, detail=(
            "Autenticação não configurada: defina CULTIVA_AUTH_SEGREDO (ou, só para uso local com dados "
            "sintéticos, CULTIVA_AUTH_DESLIGADA=true)."))
    if credenciais is None or credenciais.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Token ausente.", headers={"WWW-Authenticate": "Bearer"})
    try:
        return verificar_token(credenciais.credentials, configuracao.segredo)
    except TokenInvalido as erro:
        raise HTTPException(status_code=401, detail=str(erro), headers={"WWW-Authenticate": "Bearer"}) from None


def _usuario_do_pedido(autenticado: Optional[str], informado: Optional[str]) -> str:
    """O Usuário vem do token; o id informado no corpo ou na URL, se houver, precisa ser o mesmo."""
    if autenticado is None:  # modo de desenvolvimento
        if not informado:
            raise HTTPException(status_code=422, detail="Sem autenticação, informe o usuario_id.")
        return informado
    if informado is not None and informado != autenticado:
        raise HTTPException(status_code=403, detail="O usuario_id não corresponde ao token.")
    return autenticado


class MensagemDoChat(BaseModel):
    # Com autenticação, o Usuário vem do token; o campo fica por compatibilidade e, se vier, precisa
    # ser igual ao do token (issue #108).
    usuario_id: Optional[str] = Field(default=None, min_length=1, max_length=200)
    conversa_id: str = Field(..., min_length=1, max_length=200)
    mensagem: str = Field(..., min_length=1, max_length=4000)
    top_k: int = Field(default=TOP_K_FINAL, ge=1, le=10)


class ConsultRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Dúvida geral de consulta nutricional")
    top_k: int = Field(default=TOP_K_FINAL, ge=1, le=10)


class IncorrectAnswerFeedback(BaseModel):
    response_id: str = Field(..., min_length=1)
    detail: Optional[str] = Field(default=None, max_length=2000)


@app.get("/health")
def health_check() -> dict:
    consultant = get_consultant()
    graph_stats = (
        consultant.graph_engine.get_graph_stats()
        if consultant.graph_engine is not None
        else {}
    )
    vector_stats = (
        consultant.retriever.vector_store.get_stats()
        if consultant.retriever.vector_store is not None
        else {}
    )
    sources_inventory = inventario_de_fontes(consultant.chunks)
    return {
        "status": "ok",
        "phase": "PHASE_2_HYBRID_RAG_CHROMADB_PLUS_4LAYER_GRAPH_AND_TACO",
        "indexed_chunks": len(consultant.chunks),
        "curated_source_documents_count": len(sources_inventory),
        "vector_store": vector_stats,
        "taco_foods_loaded": len(consultant.taco_tool.foods) if consultant.taco_tool else 0,
        "knowledge_graph_stats": graph_stats,
        "llm_provider": consultant.llm_client.provider,
        "groq_configured": consultant.llm_client.is_groq_available(),
        "groq_model": consultant.llm_client.groq_model,
        "ollama_available": consultant.llm_client.is_ollama_available(),
        "primary_local_model": consultant.llm_client.primary_model,
    }


@app.post("/consult", response_model=ConsultantResponse)
def consult_endpoint(request: ConsultRequest) -> ConsultantResponse:
    consultant = get_consultant()
    response = consultant.consult(request.query, top_k=request.top_k)
    # Rastreabilidade (#11): grava o registro aqui, onde o botão de "resposta incorreta" o usa.
    save_response_trace(response)
    return response


@app.post("/feedback/incorrect")
def incorrect_answer_feedback(request: IncorrectAnswerFeedback) -> dict:
    if not register_incorrect_feedback(request.response_id, request.detail):
        raise HTTPException(status_code=404, detail="Resposta não encontrada para este response_id.")
    # RF-IA15: com o Langfuse ligado, o feedback vira o score "resposta_incorreta" no trace da resposta.
    registrar_feedback_incorreto(request.response_id, request.detail)
    return {"status": "registrado", "response_id": request.response_id}


@app.post("/chat/{chat}", response_model=RespostaDoChat)
def chat_endpoint(chat: str, pedido: MensagemDoChat,
                  autenticado: Optional[str] = Depends(usuario_autenticado)) -> RespostaDoChat:
    """Chat geral (`geral`) ou Chat de área (`nutricao`, `saude-fisica`), com Histórico da Conversa."""
    usuario_id = _usuario_do_pedido(autenticado, pedido.usuario_id)
    chat = chat.replace("-", "_")
    if chat not in CHATS:
        raise HTTPException(status_code=404, detail=f"Chat desconhecido. Use: {', '.join(CHATS)}.")
    try:
        resposta = get_servico_de_chat().enviar(chat, usuario_id, pedido.conversa_id, pedido.mensagem,
                                                top_k=pedido.top_k)
    except ConversaDeOutroUsuario:
        raise HTTPException(status_code=403, detail="Esta conversa_id pertence a outro Usuário.") from None
    # RF-IA15: cada resposta de Agente de área entra no registro, como no /consult, para aceitar feedback.
    for resposta_da_area in resposta.respostas.values():
        save_response_trace(resposta_da_area)
    return resposta


@app.delete("/chat/usuarios/{usuario_id}/conversas/{conversa_id}")
def apagar_conversa(usuario_id: str, conversa_id: str,
                    autenticado: Optional[str] = Depends(usuario_autenticado)) -> dict:
    """Apaga uma Conversa do Usuário (LGPD). Conversa de outro Usuário não é apagada (0 mensagens)."""
    usuario_id = _usuario_do_pedido(autenticado, usuario_id)
    return {"apagadas": get_servico_de_chat().apagar_conversa(usuario_id, conversa_id)}


@app.delete("/chat/usuarios/{usuario_id}")
def apagar_usuario(usuario_id: str, autenticado: Optional[str] = Depends(usuario_autenticado)) -> dict:
    """Apaga todas as Conversas do Usuário (LGPD); o id da URL precisa ser o do token."""
    usuario_id = _usuario_do_pedido(autenticado, usuario_id)
    return {"apagadas": get_servico_de_chat().apagar_usuario(usuario_id)}


class ConsentimentoDaMemoria(BaseModel):
    """Aceite dos Fatos do Usuário (issue #112): memória e, à parte, condição de saúde (LGPD, art. 11)."""

    memoria: bool
    saude: bool = False


@app.put("/chat/usuarios/{usuario_id}/memoria")
def definir_memoria(usuario_id: str, pedido: ConsentimentoDaMemoria,
                    autenticado: Optional[str] = Depends(usuario_autenticado)) -> dict:
    """Registra ou revoga o aceite; revogar para a extração e o uso dos Fatos do Usuário."""
    usuario_id = _usuario_do_pedido(autenticado, usuario_id)
    servico = get_servico_de_chat()
    servico.definir_consentimento(usuario_id, pedido.memoria, pedido.saude)
    memoria, saude = servico.consentimento(usuario_id)
    return {"memoria": memoria, "saude": saude}


@app.get("/chat/usuarios/{usuario_id}/fatos")
def listar_fatos(usuario_id: str, autenticado: Optional[str] = Depends(usuario_autenticado)) -> dict:
    """Fatos do Usuário guardados e em vigor (LGPD, art. 9º), com o consentimento atual."""
    usuario_id = _usuario_do_pedido(autenticado, usuario_id)
    servico = get_servico_de_chat()
    memoria, saude = servico.consentimento(usuario_id)
    return {"memoria": memoria, "saude": saude, "fatos": [f.como_dict() for f in servico.listar_fatos(usuario_id)]}


@app.delete("/chat/usuarios/{usuario_id}/fatos/{fato_id}")
def apagar_fato(usuario_id: str, fato_id: int, autenticado: Optional[str] = Depends(usuario_autenticado)) -> dict:
    """Apaga um Fato do Usuário (LGPD, art. 18); fato de outro Usuário não é apagado."""
    usuario_id = _usuario_do_pedido(autenticado, usuario_id)
    return {"apagados": get_servico_de_chat().apagar_fato(usuario_id, fato_id)}


async def _ler_pdf(arquivo: UploadFile) -> bytes:
    """Lê o PDF só em memória (RNF26: o original não é gravado)."""
    if arquivo.content_type not in (None, "", "application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=415, detail="Envie um arquivo PDF.")
    dados = await arquivo.read(MAX_BYTES + 1)
    if len(dados) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="PDF grande demais.")
    return dados


def _buscar_por_area(pergunta: str) -> list:
    """Trechos do corpus da área da pergunta (roteamento por regras do #100); sem termo de área, Nutrição."""
    from src.orquestrador.roteamento import AREA_NUTRICAO, rotear_por_regras

    agentes = get_servico_de_chat().agentes
    areas = rotear_por_regras(pergunta).areas or [AREA_NUTRICAO]
    return [t for area in areas if area in agentes for t in agentes[area].retriever.retrieve(pergunta, top_k=3)]


def _perguntar_pdf(dados: bytes, pergunta: str):
    return perguntar_pdf(dados, pergunta, buscar=_buscar_por_area, risco_llm=get_consultant().risco_llm)


@app.post("/multimodal/pdf/resumo")
async def resumo_de_pdf(arquivo: UploadFile = File(...)) -> dict:
    """Resumo do PDF enviado, com página e citação literal em cada frase (issue #95, RF-IA14).
    Nada é salvo: a resposta vai para confirmação (RF-A10)."""
    dados = await _ler_pdf(arquivo)
    try:
        # PyMuPDF e a chamada ao modelo são bloqueantes: no threadpool, para não parar a API inteira.
        return (await run_in_threadpool(resumir_pdf, dados)).como_dict()
    except PDFInvalido as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro


@app.post("/multimodal/pdf/pergunta")
async def pergunta_sobre_pdf(arquivo: UploadFile = File(...), pergunta: str = Form(..., min_length=3)) -> dict:
    """Pergunta sobre o PDF enviado; a resposta cita o documento e, quando útil, Trechos do corpus."""
    dados = await _ler_pdf(arquivo)
    try:
        return (await run_in_threadpool(_perguntar_pdf, dados, pergunta)).como_dict()
    except PDFInvalido as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro


async def _ler_imagem(arquivo: UploadFile) -> bytes:
    """Lê a foto só em memória (RNF26)."""
    if arquivo.content_type not in (None, "", "image/png", "image/jpeg", "application/octet-stream"):
        raise HTTPException(status_code=415, detail="Envie uma foto em PNG ou JPEG.")
    dados = await arquivo.read(MAX_BYTES_IMAGEM + 1)
    if len(dados) > MAX_BYTES_IMAGEM:
        raise HTTPException(status_code=413, detail="Imagem grande demais.")
    return dados


@app.post("/multimodal/imagem/rotulo")
async def rotulo_por_foto(arquivo: UploadFile = File(...)) -> dict:
    """Tabela nutricional lida da foto (issue #96): só valores em que o OCR e a visão do modelo
    concordam, selo "ALTO EM" como está no rótulo e o que o corpus diz sobre o tema, com citação."""
    dados = await _ler_imagem(arquivo)
    try:
        # OCR, preparo da imagem e chamada de visão são bloqueantes: no threadpool, para não parar a API.
        return (await run_in_threadpool(ler_rotulo, dados, _buscar_por_area)).como_dict()
    except ImagemInvalida as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro


def _perguntar_fotos(fotos: List[bytes], pergunta: str):
    return perguntar_fotos(fotos, pergunta, buscar=_buscar_por_area, risco_llm=get_consultant().risco_llm)


async def _ler_fotos(arquivos: List[UploadFile]) -> List[bytes]:
    if len(arquivos) > MAX_FOTOS:
        raise HTTPException(status_code=422, detail=f"Envie no máximo {MAX_FOTOS} fotos.")
    return [await _ler_imagem(a) for a in arquivos]


@app.post("/multimodal/imagem/documento/resumo")
async def resumo_de_fotos(arquivos: List[UploadFile] = File(...)) -> dict:
    """Resumo de um documento impresso fotografado (uma foto por página), pelo fluxo do PDF."""
    try:
        return (await run_in_threadpool(resumir_fotos, await _ler_fotos(arquivos))).como_dict()
    except ImagemInvalida as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro


@app.post("/multimodal/imagem/documento/pergunta")
async def pergunta_sobre_fotos(arquivos: List[UploadFile] = File(...), pergunta: str = Form(..., min_length=3)) -> dict:
    dados = await _ler_fotos(arquivos)
    try:
        return (await run_in_threadpool(_perguntar_fotos, dados, pergunta)).como_dict()
    except ImagemInvalida as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro


def cli_main() -> None:
    query = (
        " ".join(sys.argv[1:])
        if len(sys.argv) > 1
        else "Como a fibra solúvel da aveia age para reduzir o colesterol LDL e a glicemia?"
    )
    consultant = get_consultant()
    res = consultant.consult(query)
    print("=" * 76)
    print(f"PERGUNTA ORIGINAL : {res.original_query}")
    if res.guardrail_triggered:
        print(f"GUARDRAIL ATIVADO : {res.intent_category}")
        print(f"QUERY REENQUADRADA: {res.effective_query}")
        print(f"AVISO LEGAL       : {res.legal_compliance_notice}")
    print("-" * 76)
    print(f"MODELO UTILIZADO  : {res.model_used} | GRAU DE EVIDÊNCIA: {res.evidence_grade}")
    print("\n[0] CHUNKS MAIS RELEVANTES RECUPERADOS (BANCO VETORIAL CHROMADB + BM25 + RRF):")
    for idx, rc in enumerate(res.retrieved_chunks, start=1):
        c = rc.chunk
        snippet = c.raw_text[:220].replace("\n", " ") + ("..." if len(c.raw_text) > 220 else "")
        print(
            f"  {idx}. [{c.chunk_id}] {c.doc_id} | Seção: {c.section_path}\n"
            f"     Scores -> Rerank: {rc.rerank_score:.4f} | RRF: {rc.rrf_score:.4f} | "
            f"Vetorial (ChromaDB): {rc.vector_score:.4f} (rank={rc.vector_rank}) | "
            f"BM25: {rc.bm25_score:.4f} (rank={rc.bm25_rank})\n"
            f"     Trecho: \"{snippet}\""
        )
    print(f"\n[1] SÍNTESE DA EVIDÊNCIA:\n{res.evidence_summary}")
    print(f"\n[2] MECANISMO FISIOLÓGICO:\n{res.physiological_mechanism}")
    if res.graph_paths:
        print("\n[2.1] GRAFO DE CONHECIMENTO DE 4 CAMADAS (Alimento ➔ Composto ➔ Mecanismo ➔ Desfecho GRADE):")
        for gp in res.graph_paths:
            flag = "⚠️ CONTRAINDICADO" if gp.is_contraindicated_for_query else f"✅ {gp.evidence_grade}"
            print(
                f"  • [{flag}] {gp.food_node} ➔ {gp.compound_node} ➔ "
                f"{gp.mechanism_node} ➔ [{gp.effect_direction}] {gp.outcome_node}"
            )
    print(f"\n[3] ACHADOS DOS PROTOCOLOS CLÍNICOS:\n{res.protocol_findings}")
    if res.taco_records:
        print("\n[3.1] COMPOSIÇÃO DETERMINÍSTICA (TABELA TACO 4ª ED. / TBCA — POR 100g):")
        for rec in res.taco_records:
            nutr_str = ", ".join(f"{k}: {v}" for k, v in rec.nutrients_per_100g.items())
            print(
                f"  • {rec.description} ({rec.category}): {rec.energy_kcal} kcal, "
                f"Proteína: {rec.protein_g}g, Fibra: {rec.fiber_g}g | {nutr_str}"
            )
    print("\n[4] ALIMENTOS / COMPOSTOS RELACIONADOS:\n  • " + "\n  • ".join(res.food_sources_or_compounds))
    print("\n[5] CITAÇÕES RECUPERADAS (RAG HÍBRIDO):")
    for cite in res.citations:
        print(f"  - {cite}")
    print("=" * 76)


if __name__ == "__main__":
    cli_main()
