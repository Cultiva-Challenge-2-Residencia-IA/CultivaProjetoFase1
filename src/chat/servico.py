"""Serviço do Chat geral e dos Chats de área (issue #99, ADR 0005).

Para cada mensagem:

1. **Portões** (iguais nos três chats): risco (RF-IA03, léxico e a camada LLM opcional), sinal de
   alerta e prompt injection. Encerram com mensagem fixa, sem Agente de área.
2. **Histórico:** a Conversa atual e, no Chat geral, também os Chats de área do mesmo Usuário.
3. **Reescrita** (`src/orquestrador/reescrita.py`): com o LLM, pergunta completa, Subperguntas por
   área e trecho hipotético; sem LLM, a mensagem e as regras.
4. **Roteamento:** as regras decidem quando só uma área tem termo; senão vale a decomposição do LLM;
   sem LLM, as áreas das regras (as duas, se as duas tiverem termo) e, sem nenhuma, o Agente de
   Nutrição, que dá o "não sei" fora do domínio, como antes.
5. **Agentes de área:** cada um recebe a sua Subpergunta, o trecho hipotético como consulta extra e
   só o Histórico da área dele (RF-IA09). Um Chat de área responde só a parte da sua área e indica o
   chat certo para o resto (RF-IA06).
6. **Sincronizador** (Chat geral com duas áreas): resposta única cruzada, ou lado a lado.
"""

import hashlib
from typing import Dict, List, Mapping, Optional, Protocol, Sequence

from pydantic import BaseModel, Field

from src.config import JANELA_HISTORICO, TOP_K_FINAL
from src.guardrails.alerta import MENSAGEM_ALERTA, detectar_sinal_de_alerta
from src.guardrails.injection import MENSAGEM_INJECAO, has_prompt_injection
from src.guardrails.pii import mascarar_dados_pessoais
from src.guardrails.risco import MENSAGEM_ACOLHIMENTO, detectar_risco
from src.models.schemas import ConsultantResponse
from src.observabilidade import atributos_do_trace, observacao
from src.orquestrador.reescrita import LLMJson, Mensagem, Subpergunta, reescrever
from src.orquestrador.roteamento import AREA_NUTRICAO, AREAS, rotear_por_regras
from src.orquestrador.sincronizador import NOMES_DAS_AREAS, RespostaDeArea, sincronizar
from src.rag.verificador.citacoes import FRASE_SEM_BASE

CHAT_GERAL = "geral"
CHATS = (CHAT_GERAL,) + AREAS

MENSAGEM_FORA_DAS_AREAS = (
    "Não consigo ajudar com essa pergunta. O CULTIVA responde sobre Nutrição e Saúde Física, "
    "sempre com base em fontes verificadas."
)
MENSAGEM_ESTUDOS = (
    "A área de Estudos ainda não tem agente no CULTIVA. Por enquanto, eu respondo sobre Nutrição e "
    "Saúde Física, sempre com base em fontes verificadas."
)


def mensagem_outra_area(area: str) -> str:
    nome = NOMES_DAS_AREAS[area]
    return (f"Essa parte da pergunta é da área de {nome}. Pergunte no chat de {nome} ou no chat geral, "
            "que reúne as duas áreas.")


class AgenteDeArea(Protocol):
    def responder(self, pergunta: str, top_k: int, consultas_extras: List[str],
                  historico: List[Mensagem]) -> ConsultantResponse: ...


class RespostaDoChat(BaseModel):
    chat: str
    conversa_id: str
    # "risco", "alerta", "prompt_injection", "fora_das_areas", "outra_area", "agente" ou "sincronizada"
    tipo: str
    texto: str
    areas: List[str] = Field(default_factory=list)
    respostas: Dict[str, ConsultantResponse] = Field(default_factory=dict)
    modo_sincronizacao: Optional[str] = None
    citacoes: List[str] = Field(default_factory=list)
    redirecionamento: Optional[str] = None
    reescrita: Optional[str] = None  # origem da reescrita: "llm" ou "regras"


def texto_da_resposta(resposta: ConsultantResponse) -> str:
    """Texto do Agente de área, com os marcadores [T#], sem a frase fixa de campo sem base."""
    campos = (resposta.evidence_summary, resposta.physiological_mechanism, resposta.protocol_findings)
    return "\n\n".join(c.strip() for c in campos if c and c.strip() and c.strip() != FRASE_SEM_BASE)


def _id_anonimo(usuario_id: str) -> str:
    return hashlib.sha256(usuario_id.encode("utf-8")).hexdigest()[:16]


class ServicoDeChat:
    def __init__(
        self,
        agentes: Mapping[str, AgenteDeArea],
        historico,
        llm: Optional[LLMJson] = None,
        risco_llm=None,
        janela: int = JANELA_HISTORICO,
    ) -> None:
        self.agentes = dict(agentes)
        self.historico = historico
        self.llm = llm
        self.risco_llm = risco_llm
        self.janela = janela

    # Exclusão (LGPD): o Usuário apaga uma Conversa ou todas as dele.
    def apagar_conversa(self, usuario_id: str, conversa_id: str) -> int:
        return self.historico.apagar_conversa(usuario_id, conversa_id)

    def apagar_usuario(self, usuario_id: str) -> int:
        return self.historico.apagar_usuario(usuario_id)

    def enviar(self, chat: str, usuario_id: str, conversa_id: str, mensagem: str,
               top_k: int = TOP_K_FINAL) -> RespostaDoChat:
        if chat not in CHATS:
            raise ValueError(f"Chat desconhecido: {chat!r} (aceitos: {', '.join(CHATS)})")
        with atributos_do_trace(trace_name=f"chat_{chat}", tags=["chat", chat], session_id=conversa_id,
                                user_id=_id_anonimo(usuario_id)):
            fixa = self._portoes(chat, usuario_id, conversa_id, mensagem)
            if fixa is not None:
                return fixa
            with observacao("chat", input={"chat": chat, "mensagem": mensagem}) as raiz:
                resposta = self._responder(chat, usuario_id, conversa_id, mensagem, top_k)
                raiz.update(output={"tipo": resposta.tipo, "areas": resposta.areas, "texto": resposta.texto},
                            metadata={"modo_sincronizacao": resposta.modo_sincronizacao,
                                      "reescrita": resposta.reescrita})
                return resposta

    def _fixa(self, chat: str, usuario_id: str, conversa_id: str, tipo: str, guardada: str,
              texto: str) -> RespostaDoChat:
        self.historico.adicionar(usuario_id, conversa_id, chat, "usuario", guardada)
        self.historico.adicionar(usuario_id, conversa_id, chat, "assistente", texto)
        return RespostaDoChat(chat=chat, conversa_id=conversa_id, tipo=tipo, texto=texto)

    def _portoes(self, chat: str, usuario_id: str, conversa_id: str, mensagem: str) -> Optional[RespostaDoChat]:
        risco = detectar_risco(mensagem)
        categorias = list(risco.categorias)
        if not categorias and self.risco_llm is not None:
            resultado = self.risco_llm.classificar(mensagem)
            if resultado is not None and resultado.risco:
                categorias = list(resultado.categorias)
        if categorias:
            # A mensagem de risco não é guardada nem registrada: ficam só as categorias.
            with observacao("portao_risco", tipo="guardrail", input={"risco_categorias": categorias}):
                pass
            return self._fixa(chat, usuario_id, conversa_id, "risco",
                              f"[mensagem de risco: {', '.join(categorias)}]", MENSAGEM_ACOLHIMENTO)
        sinais = detectar_sinal_de_alerta(mensagem)
        if sinais:
            return self._fixa(chat, usuario_id, conversa_id, "alerta", mensagem, MENSAGEM_ALERTA)
        if has_prompt_injection(mensagem):
            return self._fixa(chat, usuario_id, conversa_id, "prompt_injection",
                              "[tentativa de prompt injection]", MENSAGEM_INJECAO)
        return None

    def _historico(self, chat: str, usuario_id: str, conversa_id: str) -> List[Mensagem]:
        proprio = self.historico.recentes(usuario_id, conversa_id, self.janela)
        if chat != CHAT_GERAL:
            return proprio
        dos_chats_de_area = self.historico.recentes_de_chats(usuario_id, AREAS, self.janela, conversa_id)
        return dos_chats_de_area + proprio

    def _rotear(self, chat: str, mensagem: str, historico: Sequence[Mensagem]):
        if self.llm is not None:
            mascarado = [Mensagem(m.papel, mascarar_dados_pessoais(m.texto), m.area) for m in historico]
            reescrita = reescrever(mascarar_dados_pessoais(mensagem), mascarado, self.llm)
        else:
            reescrita = reescrever(mensagem, historico, None)
        regras = rotear_por_regras(reescrita.pergunta_completa)
        por_area = {s.area: s for s in reescrita.subperguntas}
        if regras.decidida:
            area = regras.areas[0]
            subperguntas = [por_area.get(area) or Subpergunta(area, reescrita.pergunta_completa)]
        elif reescrita.origem == "llm":
            subperguntas = list(reescrita.subperguntas)
        else:
            subperguntas = [Subpergunta(a, reescrita.pergunta_completa) for a in regras.areas]
        return reescrita, regras, subperguntas

    def _responder(self, chat: str, usuario_id: str, conversa_id: str, mensagem: str,
                   top_k: int) -> RespostaDoChat:
        historico = self._historico(chat, usuario_id, conversa_id)
        reescrita, regras, subperguntas = self._rotear(chat, mensagem, historico)
        redirecionamento = None

        if not subperguntas:
            sem_llm = reescrita.origem == "regras"
            if regras.estudos:
                return self._fixa(chat, usuario_id, conversa_id, "fora_das_areas", mensagem, MENSAGEM_ESTUDOS)
            if chat == CHAT_GERAL and not sem_llm:
                return self._fixa(chat, usuario_id, conversa_id, "fora_das_areas", mensagem,
                                  MENSAGEM_FORA_DAS_AREAS)
            # Sem termo de área e sem LLM: o agente do chat (no geral, o de Nutrição) responde ou dá o
            # "não sei" fora do domínio, como antes da issue #99.
            area = chat if chat != CHAT_GERAL else AREA_NUTRICAO
            subperguntas = [Subpergunta(area, reescrita.pergunta_completa)]

        if chat != CHAT_GERAL:
            proprias = [s for s in subperguntas if s.area == chat]
            outras = [s.area for s in subperguntas if s.area != chat]
            if not proprias:
                texto = mensagem_outra_area(outras[0])
                return self._fixa(chat, usuario_id, conversa_id, "outra_area", mensagem, texto)
            if outras:
                redirecionamento = mensagem_outra_area(outras[0])
            subperguntas = proprias

        respostas: Dict[str, ConsultantResponse] = {}
        for sub in subperguntas:
            extras = [t for t in (sub.trecho_hipotetico,) if t]
            if sub.texto.strip() != reescrita.pergunta_completa.strip():
                extras.append(reescrita.pergunta_completa)
            historico_da_area = [m for m in historico if m.area == sub.area]
            respostas[sub.area] = self.agentes[sub.area].responder(sub.texto, top_k, extras, historico_da_area)

        areas = list(respostas)
        self.historico.adicionar(usuario_id, conversa_id, chat, "usuario", mensagem, areas)
        for area, resposta in respostas.items():
            self.historico.adicionar(usuario_id, conversa_id, chat, "assistente", texto_da_resposta(resposta), [area])

        if len(respostas) > 1:
            sinc = sincronizar(
                reescrita.pergunta_completa,
                [RespostaDeArea(a, texto_da_resposta(r), list(r.retrieved_chunks)) for a, r in respostas.items()],
                self.llm,
            )
            texto, tipo, modo = sinc.texto, "sincronizada", sinc.modo
        else:
            unica = next(iter(respostas.values()))
            texto, tipo, modo = texto_da_resposta(unica), "agente", None
        if redirecionamento:
            texto = f"{texto}\n\n{redirecionamento}"
        citacoes = [c for r in respostas.values() for c in r.citations]
        return RespostaDoChat(
            chat=chat, conversa_id=conversa_id, tipo=tipo, texto=texto, areas=areas, respostas=respostas,
            modo_sincronizacao=modo, citacoes=citacoes, redirecionamento=redirecionamento,
            reescrita=reescrita.origem,
        )
