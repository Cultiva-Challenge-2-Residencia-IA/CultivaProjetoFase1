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

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import re
from typing import Callable, Dict, List, Mapping, Optional, Protocol, Sequence

from pydantic import BaseModel, Field

from src.chat.fatos import FatosSQLite
from src.config import (FATOS_PRAZO_DIAS, HYDE_NA_BUSCA, JANELA_HISTORICO, MEMORIA_PADRAO,
                        ORCAMENTO_HISTORICO_TOKENS, REDACAO_LLM, TOP_K_FINAL)
from src.guardrails.alerta import MENSAGEM_ALERTA, detectar_sinal_de_alerta
from src.guardrails.injection import MENSAGEM_INJECAO, has_prompt_injection
from src.guardrails.pii import mascarar_dados_pessoais
from src.guardrails.risco import MENSAGEM_ACOLHIMENTO, detectar_risco
from src.models.schemas import ConsultantResponse
from src.observabilidade import atributos_do_trace, observacao, ocultar_fatos
from src.orquestrador.conversa import APRESENTACOES, e_conversa_social
from src.orquestrador.fatos import FatoDoUsuario, candidatos_em_texto, escolhidos, extrair_fatos
from src.orquestrador.redator import encaminhamento, esclarecimento_valido, redigir
from src.orquestrador.reescrita import LLMJson, Mensagem, Subpergunta, reescrever
from src.orquestrador.roteamento import AREA_NUTRICAO, AREAS, rotear_por_regras
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
                  historico: List[Mensagem], fatos: Sequence[FatoDoUsuario] = ()) -> ConsultantResponse: ...


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
    # Fatos do Usuário entregues aos agentes nesta resposta (transparência, issue #112).
    fatos_usados: List[dict] = Field(default_factory=list)
    # Redação final (issue #104): "aceita", "recusada" (ficou o texto checado de antes) ou None.
    redacao: Optional[str] = None
    # Texto checado antes da redação, com os marcadores (auditoria e medição da #104); None sem redação aceita.
    texto_antes_da_redacao: Optional[str] = None


def _chave_da_frase(frase: str) -> str:
    """Só as palavras: marcador, pontuação e espaços não distinguem uma frase repetida ("frase [T1]."
    e "frase." são a mesma)."""
    return " ".join(re.findall(r"\w+", MARCADOR.sub(" ", frase))).casefold()


MARCA_ESCLARECIMENTO = "esclarecimento"  # nas áreas da mensagem do assistente, no Histórico


def texto_da_resposta(resposta: ConsultantResponse, com_nota_legal: bool = True) -> str:
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
            # Frase a frase: a repetição pode estar dentro do próprio bloco (o LLM repete uma frase
            # no mesmo item), e não só entre campos.
            novas = []
            for frase in dividir_frases(bloco):
                chave = _chave_da_frase(frase)
                if chave and chave not in vistas:
                    vistas.add(chave)
                    novas.append(frase)
            if novas:
                paragrafos.append(" ".join(novas))
    texto = "\n\n".join(paragrafos)
    # Pedido restrito pela lei da área (Lei 8.234/1991 ou 9.696/1998): a nota legal vem antes.
    if (com_nota_legal and resposta.guardrail_triggered and resposta.legal_compliance_notice
            and not resposta.prompt_injection_detected):
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
        limpo = re.sub(r"\s*\[(?:T\d+|CONTEXTO)\]", "", paragrafo).rstrip()
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


FRASES_DA_RESPOSTA_NO_HISTORICO = 2


def tokens_estimados(texto: str) -> int:
    """Estimativa de tokens (cerca de 4 caracteres por token em português), sem tokenizador do modelo."""
    return (len(texto) + 3) // 4


def encurtar_resposta(texto: str) -> str:
    """Resposta do assistente no Histórico: as primeiras frases, sem marcadores de citação.

    O que o modelo precisa para entender a continuação é o assunto, não a evidência inteira.
    """
    limpo = " ".join(MARCADOR.sub("", texto).split())
    return " ".join(dividir_frases(limpo)[:FRASES_DA_RESPOSTA_NO_HISTORICO]) or limpo


def no_orcamento(mensagens: Sequence[Mensagem], orcamento: int) -> List[Mensagem]:
    """As mensagens mais recentes que cabem no orçamento de tokens, na ordem original."""
    escolhidas: List[Mensagem] = []
    usados = 0
    for m in reversed(list(mensagens)):
        texto = encurtar_resposta(m.texto) if m.papel == "assistente" else m.texto
        custo = tokens_estimados(texto)
        if usados + custo > orcamento:
            break
        usados += custo
        escolhidas.append(Mensagem(m.papel, texto, m.area, list(m.areas)))
    return list(reversed(escolhidas))


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
        orcamento_historico: int = ORCAMENTO_HISTORICO_TOKENS,
        reescrita_com_llm: bool = True,
        hyde_na_busca: bool = HYDE_NA_BUSCA,
        fatos: Optional[FatosSQLite] = None,
        executar_em_segundo_plano: Optional[Callable[[Callable[[], None]], None]] = None,
        relogio: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        prazo_fatos_dias: int = FATOS_PRAZO_DIAS,
        memoria_padrao: str = MEMORIA_PADRAO,
        redacao: bool = REDACAO_LLM,
    ) -> None:
        self.agentes = dict(agentes)
        self.historico = historico
        self.llm = llm
        # A reescrita só usa o LLM se a medição permitir (CULTIVA_REESCRITA_LLM); o Sincronizador usa sempre.
        self.reescrita_com_llm = reescrita_com_llm
        # Trecho hipotético como consulta extra na busca: desligado por padrão (medição do dev).
        self.hyde_na_busca = hyde_na_busca
        self.risco_llm = risco_llm
        self.janela = janela
        self.orcamento_historico = orcamento_historico
        # Fatos do Usuário (issue #112): no mesmo arquivo do Histórico, em tabelas próprias.
        if fatos is None and getattr(historico, "caminho", None) is not None:
            fatos = FatosSQLite(historico.caminho)
        self.fatos = fatos
        self.relogio = relogio
        self.prazo_fatos_dias = prazo_fatos_dias
        self.memoria_padrao = memoria_padrao
        self.redacao = redacao
        # A extração roda depois da resposta, fora do caminho da latência; os testes passam um
        # executor síncrono.
        if executar_em_segundo_plano is None:
            executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="fatos")
            executar_em_segundo_plano = executor.submit
        self.executar_em_segundo_plano = executar_em_segundo_plano

    # Consentimento e Fatos do Usuário (issue #112, LGPD art. 11 e art. 18).
    def definir_consentimento(self, usuario_id: str, memoria: bool, saude: bool = False) -> None:
        if self.fatos is None:
            raise RuntimeError("Fatos do Usuário indisponíveis neste Histórico.")
        self.fatos.definir_consentimento(usuario_id, memoria, saude, self.relogio())

    def consentimento(self, usuario_id: str) -> tuple:
        """(memória, saúde): o registrado, ou o padrão de CULTIVA_MEMORIA_PADRAO para quem não respondeu."""
        registrado = self.fatos.consentimento(usuario_id) if self.fatos is not None else None
        if registrado is not None:
            return registrado
        if self.fatos is None:
            return (False, False)
        return (self.memoria_padrao in ("ligada", "ligada_com_saude"), self.memoria_padrao == "ligada_com_saude")

    def listar_fatos(self, usuario_id: str) -> List[FatoDoUsuario]:
        if self.fatos is None:
            return []
        _, saude = self.consentimento(usuario_id)
        # Transparência (LGPD, art. 9º): a pessoa vê tudo o que está guardado, mesmo sem consentimento.
        return self.fatos.validos(usuario_id, self.relogio(), self.prazo_fatos_dias, incluir_saude=True)

    def _candidatos(self, usuario_id: str) -> List[FatoDoUsuario]:
        """Fatos que podem ser entregues agora: só com consentimento, e saúde só com o aceite dela."""
        memoria, saude = self.consentimento(usuario_id)
        if not memoria or self.fatos is None:
            return []
        candidatos = self.fatos.validos(usuario_id, self.relogio(), self.prazo_fatos_dias, incluir_saude=saude)
        ocultar_fatos((f.texto, f.categoria) for f in candidatos)
        return candidatos

    def apagar_fato(self, usuario_id: str, fato_id: int) -> int:
        return self.fatos.apagar_fato(usuario_id, fato_id) if self.fatos is not None else 0

    def _extrair(self, usuario_id: str, conversa_id: str, mensagem: str) -> None:
        memoria, saude = self.consentimento(usuario_id)
        if not memoria or self.fatos is None or self.llm is None:
            return

        def tarefa() -> None:
            extraidos = extrair_fatos(mascarar_dados_pessoais(mensagem), self.llm, saude)
            ocultar_fatos((texto, categoria) for categoria, texto in extraidos)
            for categoria, texto in extraidos:
                self.fatos.registrar(usuario_id, conversa_id, categoria, texto, self.relogio())

        self.executar_em_segundo_plano(tarefa)

    # Exclusão (LGPD): o Usuário apaga uma Conversa ou todas as dele.
    def apagar_conversa(self, usuario_id: str, conversa_id: str) -> int:
        if self.fatos is not None:
            self.fatos.apagar_conversa(usuario_id, conversa_id)
        return self.historico.apagar_conversa(usuario_id, conversa_id)

    def apagar_usuario(self, usuario_id: str) -> int:
        if self.fatos is not None:
            self.fatos.apagar_usuario(usuario_id)
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
                # Só a mensagem que passou pelos Portões pode virar Fato do Usuário.
                self._extrair(usuario_id, conversa_id, mensagem)
                raiz.update(output={"tipo": resposta.tipo, "areas": resposta.areas, "texto": resposta.texto},
                            metadata={"modo_sincronizacao": resposta.modo_sincronizacao,
                                      "reescrita": resposta.reescrita,
                                      # Fatos do Usuário: só contagem e categorias, nunca o texto (#112).
                                      "fatos_entregues": len(resposta.fatos_usados),
                                      "categorias_dos_fatos": sorted({f["categoria"] for f in resposta.fatos_usados})})
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
        # A Conversa atual tem prioridade no orçamento; o que sobra vai aos Chats de área (Chat geral).
        proprio = no_orcamento(self.historico.recentes(usuario_id, conversa_id, self.janela), self.orcamento_historico)
        if chat != CHAT_GERAL:
            return proprio
        restante = self.orcamento_historico - sum(tokens_estimados(m.texto) for m in proprio)
        dos_chats_de_area = no_orcamento(
            self.historico.recentes_de_chats(usuario_id, AREAS, self.janela, conversa_id), restante)
        return dos_chats_de_area + proprio

    def _rotear(self, chat: str, mensagem: str, historico: Sequence[Mensagem],
                candidatos: Sequence[FatoDoUsuario] = ()):
        if self.llm is not None and self.reescrita_com_llm:
            mascarado = [Mensagem(m.papel, mascarar_dados_pessoais(m.texto), m.area) for m in historico]
            reescrita = reescrever(mascarar_dados_pessoais(mensagem), mascarado, self.llm,
                                   fatos_candidatos=candidatos_em_texto(candidatos))
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
        # Projetor de contexto (issue #112): os candidatos vão à reescrita, que escolhe por Subpergunta.
        candidatos = self._candidatos(usuario_id) if (self.llm is not None and self.reescrita_com_llm) else []
        reescrita, regras, subperguntas = self._rotear(chat, mensagem, historico, candidatos)
        redirecionamento = None

        # Pedido vago ou individual (issue #104): uma pergunta de esclarecimento antes dos agentes, uma
        # vez só; a mensagem seguinte segue o fluxo, com a pergunta de esclarecimento no Histórico.
        esclarecimento = esclarecimento_valido(reescrita.esclarecimento)
        ultima = self.historico.recentes(usuario_id, conversa_id, 1)
        ja_perguntou = bool(ultima) and MARCA_ESCLARECIMENTO in ultima[-1].areas
        if esclarecimento and not ja_perguntou:
            self.historico.adicionar(usuario_id, conversa_id, chat, "usuario", mensagem)
            self.historico.adicionar(usuario_id, conversa_id, chat, "assistente", esclarecimento,
                                     [MARCA_ESCLARECIMENTO])
            return RespostaDoChat(chat=chat, conversa_id=conversa_id, tipo="esclarecimento", texto=esclarecimento,
                                  texto_com_marcadores=esclarecimento, reescrita=reescrita.origem)

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
        fatos_usados: List[FatoDoUsuario] = []
        for sub in subperguntas:
            extras: List[str] = []
            if self.hyde_na_busca:
                extras = [t for t in (sub.trecho_hipotetico,) if t]
                if sub.texto.strip() != reescrita.pergunta_completa.strip():
                    extras.append(reescrita.pergunta_completa)
            fatos = escolhidos(sub.fatos_ids, candidatos)
            # Condição de saúde só orienta a busca para a evidência da população certa.
            extras += [f"{sub.texto} {f.texto}" for f in fatos if f.condicao_de_saude]
            if fatos:
                self.fatos.registrar_entregas(usuario_id, conversa_id, sub.area, fatos, self.relogio())
                fatos_usados += [f for f in fatos if f not in fatos_usados]
            # Pergunta de uma área só, sem Histórico desta Conversa: vai como o usuário escreveu, a mesma
            # busca medida como base no dev. Com continuação ou com mais de uma área, vai a Subpergunta.
            pergunta = mensagem if not varias_areas and not historico_proprio else sub.texto
            historico_da_area = [m for m in historico if m.e_da_area(sub.area)]
            respostas[sub.area] = self.agentes[sub.area].responder(pergunta, top_k, extras, historico_da_area,
                                                                   fatos=fatos)

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
            redacao, antes = None, None
            # Com nota legal no texto sincronizado, a redação não entra (a nota não pode ser reescrita).
            if self._pode_redigir(respostas) and not any(r.guardrail_triggered for r in respostas.values()):
                redigido = redigir(reescrita.pergunta_completa or mensagem, texto, self.llm, fatos=fatos_usados)
                redacao = "aceita" if redigido else "recusada"
                antes = texto if redigido else None
                texto = redigido or texto
            # Os marcadores do texto sincronizado contam os Trechos das duas áreas num só intervalo:
            # as citações saem da mesma lista (RN04).
            citacoes = citacoes_do_texto(texto, sinc.trechos)
        else:
            unica = next(iter(respostas.values()))
            tipo, modo = "agente", None
            corpo = texto_da_resposta(unica, com_nota_legal=False)
            texto = texto_da_resposta(unica)
            redacao, antes = None, None
            if self._pode_redigir(respostas):
                # Redação final (issue #104): só o corpo; a nota legal segue fixa, por código.
                redigido = redigir(reescrita.pergunta_completa or mensagem, corpo, self.llm, fatos=fatos_usados)
                redacao = "aceita" if redigido else "recusada"
                if redigido:
                    guardrail = getattr(self.agentes[areas[0]], "guardrail", None)
                    if guardrail is not None:
                        redigido = guardrail.sanitize_output_text(redigido)
                    antes = texto
                    texto = texto.replace(corpo, redigido) if corpo else redigido
            citacoes = citacoes_do_texto(texto, unica.retrieved_chunks)
            # TACO e grafo causal não são Trechos: entram como vieram do agente.
            citacoes += [c for c in unica.citations if c.startswith(("[KG_", "[TACO_"))]
        # Condição de saúde entregue (#112): o encaminhamento a profissional entra por código, também
        # quando não houve redação (o redator já o acrescenta quando a redação é aceita).
        final_fixo = encaminhamento(fatos_usados)
        if final_fixo and redacao != "aceita":
            texto = f"{texto}\n\n{final_fixo}"
        com_marcadores = texto
        texto = em_notas(texto)
        if redirecionamento:
            texto = f"{texto}\n\n{redirecionamento}"
            com_marcadores = f"{com_marcadores}\n\n{redirecionamento}"
        return RespostaDoChat(
            chat=chat, conversa_id=conversa_id, tipo=tipo, texto=texto, texto_com_marcadores=com_marcadores,
            areas=areas, respostas=respostas,
            modo_sincronizacao=modo, citacoes=citacoes, redirecionamento=redirecionamento,
            reescrita=reescrita.origem, fatos_usados=[f.como_dict() for f in fatos_usados], redacao=redacao,
            texto_antes_da_redacao=antes,
        )

    def _pode_redigir(self, respostas: Mapping[str, ConsultantResponse]) -> bool:
        """Redação só sobre texto do LLM já checado: a síntese extrativa não é reescrita (issue #104)."""
        return (self.redacao and self.llm is not None
                and all(r.fundamentacao_status == "llm_citacoes_validas" for r in respostas.values()))
