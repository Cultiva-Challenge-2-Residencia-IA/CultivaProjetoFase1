"""Serviço do Chat geral e dos Chats de área (issue #99, ADR 0005).

Para cada mensagem:

1. **Portões** (iguais nos três chats): risco (RF-IA03, léxico e a camada LLM opcional), sinal de
   alerta e prompt injection. Encerram com mensagem fixa, sem Agente de área.
2. **Histórico:** a Conversa atual e, no Chat geral, também os Chats de área do mesmo Usuário.
3. **Reescrita** (`src/orquestrador/reescrita.py`): com o LLM, pergunta completa, Subperguntas por
   área e trecho hipotético; sem LLM, a mensagem e as regras.
4. **Roteamento:** as regras decidem sempre que alguma área tem termo (uma ou as duas); sem termo,
   decide o LLM (área, as duas ou fora das áreas); sem termo e sem LLM, o Agente de Nutrição, que dá
   o "não sei" fora do domínio, como antes.
5. **Agentes de área:** cada um recebe a sua Subpergunta, o trecho hipotético como consulta extra e
   só o Histórico da área dele (RF-IA09). Um Chat de área responde só a parte da sua área e indica o
   chat certo para o resto (RF-IA06).
6. **Sincronizador** (Chat geral com duas áreas): resposta única cruzada, ou lado a lado.
"""

import hashlib
import re
from typing import Dict, List, Mapping, Optional, Protocol, Sequence

from pydantic import BaseModel, Field

from src.config import HYDE_NA_BUSCA, HYDE_NA_BUSCA_SAUDE_FISICA, JANELA_HISTORICO, TOP_K_FINAL
from src.guardrails.alerta import MENSAGEM_ALERTA, detectar_sinal_de_alerta
from src.guardrails.injection import MENSAGEM_INJECAO, has_prompt_injection
from src.guardrails.pii import mascarar_dados_pessoais
from src.guardrails.risco import MENSAGEM_ACOLHIMENTO, detectar_risco
from src.models.schemas import ConsultantResponse
from src.observabilidade import atributos_do_trace, observacao
from src.orquestrador.conversa import APRESENTACOES, e_conversa_social
from src.orquestrador.reescrita import LLMJson, Mensagem, Subpergunta, reescrever
from src.orquestrador.roteamento import AREA_NUTRICAO, AREA_SAUDE_FISICA, AREAS, rotear_por_regras
from src.orquestrador.sincronizador import MARCADOR_T, NOMES_DAS_AREAS, RespostaDeArea, sincronizar
from src.rag.verificador.citacoes import FRASE_SEM_BASE, MARCADOR, dividir_frases

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
    texto: str  # para exibir: citações como notas (¹ ²) no fim de cada parágrafo
    texto_com_marcadores: str = ""  # o mesmo texto com os [T#] em cada frase, para auditoria (RN04)
    areas: List[str] = Field(default_factory=list)
    respostas: Dict[str, ConsultantResponse] = Field(default_factory=dict)
    modo_sincronizacao: Optional[str] = None
    citacoes: List[str] = Field(default_factory=list)
    redirecionamento: Optional[str] = None
    reescrita: Optional[str] = None  # origem da reescrita: "llm" ou "regras"


def _chave_da_frase(frase: str) -> str:
    return " ".join(MARCADOR.sub("", frase).split()).casefold()


def texto_da_resposta(resposta: ConsultantResponse) -> str:
    """Texto do Agente de área, com os marcadores [T#], sem a frase fixa de campo sem base.

    Os três campos da síntese podem repetir frases (a síntese extrativa usa os mesmos Trechos no
    resumo, no mecanismo e nos protocolos): cada frase aparece uma vez só.
    """
    vistas: set = set()
    paragrafos = []
    for campo in (resposta.evidence_summary, resposta.physiological_mechanism, resposta.protocol_findings):
        if not campo or not campo.strip() or campo.strip() == FRASE_SEM_BASE:
            continue
        for bloco in campo.strip().split("\n\n"):
            novas = [f for f in dividir_frases(bloco) if _chave_da_frase(f) not in vistas]
            vistas.update(_chave_da_frase(f) for f in novas)
            if novas:
                paragrafos.append(" ".join(novas))
    texto = "\n\n".join(paragrafos)
    # Pedido restrito pela lei da área (Lei 8.234/1991 ou 9.696/1998): a nota legal vem antes.
    if resposta.guardrail_triggered and resposta.legal_compliance_notice and not resposta.prompt_injection_detected:
        return f"{resposta.legal_compliance_notice}\n\n{texto}"
    return texto


_SOBRESCRITOS = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def nota(numero: int) -> str:
    return str(numero).translate(_SOBRESCRITOS)


def em_notas(texto: str) -> str:
    """Tira os [T#] de dentro das frases e põe as notas no fim de cada parágrafo (¹ ²)."""
    paragrafos = []
    for paragrafo in texto.split("\n\n"):
        numeros: List[int] = []
        for n in MARCADOR_T.findall(paragrafo):
            if int(n) not in numeros:
                numeros.append(int(n))
        limpo = re.sub(r"\s*\[T\d+\]", "", paragrafo).rstrip()
        paragrafos.append(f"{limpo} {' '.join(nota(n) for n in numeros)}" if numeros else limpo)
    return "\n\n".join(paragrafos)


def citacoes_do_texto(texto: str, trechos: Sequence) -> List[str]:
    """Uma citação por Trecho marcado [T#] no texto, com fonte, seção e página (ou seção, no HTML)."""
    numeros = sorted({int(n) for n in MARCADOR_T.findall(texto) if 1 <= int(n) <= len(trechos)})
    citacoes = []
    for n in numeros:
        c = trechos[n - 1].chunk
        onde = f"p. {c.pagina_pdf}" if c.pagina_pdf else f"seção '{c.section_path}'"
        link = c.fonte_url or (f"https://doi.org/{c.doi}" if c.doi else "")
        citacoes.append(f"{nota(n)} {c.title} — {c.source_organization} ({c.publication_year}), {onde}"
                        + (f" | Link: {link}" if link else ""))
    return citacoes


class ConversaDeOutroUsuario(PermissionError):
    """O `conversa_id` já pertence a outro Usuário (issue #108; a API responde 403)."""


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
        reescrita_com_llm: bool = True,
        hyde_na_busca: bool = HYDE_NA_BUSCA,
        hyde_na_busca_saude_fisica: bool = HYDE_NA_BUSCA_SAUDE_FISICA,
    ) -> None:
        self.agentes = dict(agentes)
        self.historico = historico
        self.llm = llm
        # A reescrita só usa o LLM se a medição permitir (CULTIVA_REESCRITA_LLM); o Sincronizador usa sempre.
        self.reescrita_com_llm = reescrita_com_llm
        # Trecho hipotético como consulta extra na busca das duas áreas: desligado por padrão (medição do
        # dev da #99, que piorou Nutrição).
        self.hyde_na_busca = hyde_na_busca
        # Só no Agente de Saúde Física (issue #105), cujas fontes estão quase todas em inglês.
        self.hyde_na_busca_saude_fisica = hyde_na_busca_saude_fisica
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
        # Posse antes de tudo, inclusive dos portões, que também gravam no Histórico (issue #108).
        if not self.historico.reservar_conversa(usuario_id, conversa_id):
            raise ConversaDeOutroUsuario("Esta Conversa pertence a outro Usuário.")
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
        return RespostaDoChat(chat=chat, conversa_id=conversa_id, tipo=tipo, texto=texto, texto_com_marcadores=texto)

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
            # Sintoma é dado de saúde: como no risco, ficam só os nomes dos sinais.
            return self._fixa(chat, usuario_id, conversa_id, "alerta",
                              f"[sinal de alerta: {', '.join(sinais)}]", MENSAGEM_ALERTA)
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
        if self.llm is not None and self.reescrita_com_llm:
            mascarado = [Mensagem(m.papel, mascarar_dados_pessoais(m.texto), m.area) for m in historico]
            reescrita = reescrever(mascarar_dados_pessoais(mensagem), mascarado, self.llm)
        else:
            reescrita = reescrever(mensagem, historico, None)
        # As regras olham a mensagem e a pergunta completa: a reescrita resolve a continuação, mas às
        # vezes tira o termo de uma das áreas (medição do dev, eval/multiagentes/).
        regras = rotear_por_regras(f"{mensagem}\n{reescrita.pergunta_completa}")
        por_area = {s.area: s for s in reescrita.subperguntas}
        if regras.areas:
            # Termo de alguma área (de uma ou das duas): as regras decidem; o LLM só contribui com a
            # Subpergunta e o trecho hipotético de cada área (medição do dev, eval/multiagentes/).
            subperguntas = [por_area.get(a) or Subpergunta(a, reescrita.pergunta_completa) for a in regras.areas]
        elif reescrita.origem == "llm":
            subperguntas = list(reescrita.subperguntas)
        else:
            subperguntas = [Subpergunta(a, reescrita.pergunta_completa) for a in regras.areas]
        return reescrita, regras, subperguntas

    def _responder(self, chat: str, usuario_id: str, conversa_id: str, mensagem: str,
                   top_k: int) -> RespostaDoChat:
        if e_conversa_social(mensagem) and not rotear_por_regras(mensagem).areas:
            return self._fixa(chat, usuario_id, conversa_id, "conversa", mensagem, APRESENTACOES[chat])
        historico = self._historico(chat, usuario_id, conversa_id)
        historico_proprio = self.historico.recentes(usuario_id, conversa_id, self.janela)
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

        varias_areas = len(subperguntas) > 1
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
            extras: List[str] = []
            if self.hyde_na_busca or (self.hyde_na_busca_saude_fisica and sub.area == AREA_SAUDE_FISICA):
                extras = [t for t in (sub.trecho_hipotetico,) if t]
                if sub.texto.strip() != reescrita.pergunta_completa.strip():
                    extras.append(reescrita.pergunta_completa)
            # Pergunta de uma área só, sem Histórico desta Conversa: vai como o usuário escreveu, a mesma
            # busca medida como base no dev. Com continuação ou com mais de uma área, vai a Subpergunta.
            pergunta = mensagem if not varias_areas and not historico_proprio else sub.texto
            historico_da_area = [m for m in historico if m.e_da_area(sub.area)]
            respostas[sub.area] = self.agentes[sub.area].responder(pergunta, top_k, extras, historico_da_area)

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
            # Os marcadores do texto sincronizado contam os Trechos das duas áreas num só intervalo:
            # as citações saem da mesma lista (RN04).
            citacoes = citacoes_do_texto(texto, sinc.trechos)
        else:
            unica = next(iter(respostas.values()))
            texto, tipo, modo = texto_da_resposta(unica), "agente", None
            citacoes = citacoes_do_texto(texto, unica.retrieved_chunks)
            # TACO e grafo causal não são Trechos: entram como vieram do agente.
            citacoes += [c for c in unica.citations if c.startswith(("[KG_", "[TACO_"))]
        com_marcadores = texto
        texto = em_notas(texto)
        if redirecionamento:
            texto = f"{texto}\n\n{redirecionamento}"
            com_marcadores = f"{com_marcadores}\n\n{redirecionamento}"
        return RespostaDoChat(
            chat=chat, conversa_id=conversa_id, tipo=tipo, texto=texto, texto_com_marcadores=com_marcadores,
            areas=areas, respostas=respostas,
            modo_sincronizacao=modo, citacoes=citacoes, redirecionamento=redirecionamento,
            reescrita=reescrita.origem,
        )
