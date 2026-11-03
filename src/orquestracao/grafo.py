"""Grafo da Aba Nutrição.

Ordem: Portão de risco, guardrails de entrada, escopo, roteador, Context Broker,
recuperação, geração e guardrails de saída. Cada guardrail que bloqueia encerra o fluxo
com uma mensagem fixa e deixa um sinal no estado, que a avaliação usa para checar fatos
do fluxo em vez de interpretar texto.
"""

from dataclasses import dataclass, field
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.nutricao import MARCADOR_NAO_SEI, AgenteNutricao
from broker.context_broker import ContextBroker, ContextoDoAgente
from dominio.modelos import Aba, Perfil, Registro, Trecho
from guardrails import mensagens
from guardrails.injection import detectar_injecao
from guardrails.pii import mascarar_pii
from guardrails.prescricao import contem_prescricao, pedido_fora_de_escopo
from guardrails.risco import avaliar_risco
from modelo.base import ModeloDeLinguagem
from orquestracao.roteador import aba_de_destino
from rag.chunking import carregar_trechos
from rag.retriever import BuscaPorPalavras
from rag.verificador import citacoes_validas, remover_citacoes

MAX_TENTATIVAS_CITACAO = 2


class Estado(TypedDict, total=False):
    aba: Aba
    mensagem: str
    perfil: Perfil
    registros: tuple[Registro, ...]
    mensagem_mascarada: str
    contexto: ContextoDoAgente
    trechos: list[Trecho]
    resposta_modelo: str
    fontes: list[str]
    resposta: str
    # sinais do fluxo
    risco_disparado: bool
    categorias_risco: tuple[str, ...]
    injecao_detectada: bool
    fora_de_escopo: bool
    redirecionado_para: Aba | None
    nao_sei: bool
    prescricao_bloqueada: bool
    tentativas: int


@dataclass(frozen=True)
class RespostaCultiva:
    texto: str
    fontes: list[dict[str, Any]] = field(default_factory=list)
    sinais: dict[str, Any] = field(default_factory=dict)


class Cultiva:
    def __init__(
        self,
        modelo: ModeloDeLinguagem,
        trechos: tuple[Trecho, ...] | None = None,
        broker: ContextBroker | None = None,
    ):
        self.modelo = modelo
        self.trechos = trechos if trechos is not None else carregar_trechos()
        self._por_id = {t.id: t for t in self.trechos}
        self._busca = BuscaPorPalavras(self.trechos)
        self._broker = broker or ContextBroker()
        self._agente = AgenteNutricao(modelo)
        self._grafo = self._construir()

    @property
    def ids_corpus(self) -> frozenset[str]:
        return self._busca.ids

    # ---------------------------------------------------------------- nós

    def _portao_risco(self, estado: Estado) -> Estado:
        resultado = avaliar_risco(estado["mensagem"])
        if resultado.disparou:
            return {
                "risco_disparado": True,
                "categorias_risco": resultado.categorias,
                "resposta": mensagens.ACOLHIMENTO_RISCO,
            }
        return {"risco_disparado": False}

    def _entrada(self, estado: Estado) -> Estado:
        if detectar_injecao(estado["mensagem"]):
            return {"injecao_detectada": True, "resposta": mensagens.RECUSA_INJECAO}
        nomes = (estado["perfil"].nome,) if estado["perfil"].nome else ()
        return {
            "injecao_detectada": False,
            "mensagem_mascarada": mascarar_pii(estado["mensagem"], nomes),
        }

    def _escopo(self, estado: Estado) -> Estado:
        if pedido_fora_de_escopo(estado["mensagem"]):
            return {"fora_de_escopo": True, "resposta": mensagens.RECUSA_ESCOPO}
        return {"fora_de_escopo": False}

    def _roteador(self, estado: Estado) -> Estado:
        destino = aba_de_destino(estado["mensagem"], estado["aba"])
        if destino is not None:
            return {
                "redirecionado_para": destino,
                "resposta": mensagens.redirecionamento(destino.nome_exibicao),
            }
        return {"redirecionado_para": None}

    def _context_broker(self, estado: Estado) -> Estado:
        contexto = self._broker.contexto_para(
            self._agente.nome, estado["perfil"], estado["registros"]
        )
        return {"contexto": contexto}

    def _recuperar(self, estado: Estado) -> Estado:
        return {"trechos": self._busca.buscar(estado["mensagem"])}

    def _gerar(self, estado: Estado) -> Estado:
        trechos = estado["trechos"]
        if not trechos:
            return {"nao_sei": True, "tentativas": 0, "fontes": []}
        ids = {t.id for t in trechos}
        texto = ""
        for tentativa in range(1, MAX_TENTATIVAS_CITACAO + 1):
            texto = self._agente.responder(
                estado["mensagem_mascarada"],
                estado["contexto"],
                trechos,
                lembrar_citacao=tentativa > 1,
            )
            if MARCADOR_NAO_SEI in texto:
                return {"nao_sei": True, "tentativas": tentativa, "fontes": []}
            fontes = citacoes_validas(texto, ids)
            if fontes:
                return {
                    "nao_sei": False,
                    "tentativas": tentativa,
                    "resposta_modelo": texto,
                    "fontes": fontes,
                }
        return {
            "nao_sei": True,
            "tentativas": MAX_TENTATIVAS_CITACAO,
            "resposta_modelo": texto,
            "fontes": [],
        }

    def _saida(self, estado: Estado) -> Estado:
        if estado.get("nao_sei"):
            return {"prescricao_bloqueada": False, "resposta": mensagens.NAO_SEI}
        texto = estado["resposta_modelo"]
        if contem_prescricao(texto):
            return {
                "prescricao_bloqueada": True,
                "fontes": [],
                "resposta": mensagens.RECUSA_ESCOPO,
            }
        # Vários Trechos da mesma página viram uma linha só.
        linhas_fontes = list(
            dict.fromkeys(
                f"- {self._por_id[f].titulo_fonte}, página {self._por_id[f].pagina_pdf} do PDF"
                for f in estado["fontes"]
            )
        )
        resposta = "\n\n".join(
            [remover_citacoes(texto), "Fontes:\n" + "\n".join(linhas_fontes)]
            + [mensagens.AVISO_PROFISSIONAL]
        )
        return {"prescricao_bloqueada": False, "resposta": resposta}

    # ---------------------------------------------------------------- grafo

    def _construir(self):
        g = StateGraph(Estado)
        g.add_node("portao_risco", self._portao_risco)
        g.add_node("entrada", self._entrada)
        g.add_node("escopo", self._escopo)
        g.add_node("roteador", self._roteador)
        g.add_node("context_broker", self._context_broker)
        g.add_node("recuperar", self._recuperar)
        g.add_node("gerar", self._gerar)
        g.add_node("saida", self._saida)

        g.add_edge(START, "portao_risco")
        g.add_conditional_edges(
            "portao_risco", lambda e: END if e["risco_disparado"] else "entrada"
        )
        g.add_conditional_edges("entrada", lambda e: END if e["injecao_detectada"] else "escopo")
        g.add_conditional_edges("escopo", lambda e: END if e["fora_de_escopo"] else "roteador")
        g.add_conditional_edges(
            "roteador", lambda e: END if e["redirecionado_para"] else "context_broker"
        )
        g.add_edge("context_broker", "recuperar")
        g.add_edge("recuperar", "gerar")
        g.add_edge("gerar", "saida")
        g.add_edge("saida", END)
        return g.compile()

    # ---------------------------------------------------------------- uso

    def responder(
        self,
        mensagem: str,
        perfil: Perfil,
        registros: tuple[Registro, ...] = (),
        aba: Aba = Aba.NUTRICAO,
    ) -> RespostaCultiva:
        if aba is not Aba.NUTRICAO:
            raise NotImplementedError("Nesta fase só a Aba Nutrição tem agente.")
        estado = self._grafo.invoke(
            {"aba": aba, "mensagem": mensagem, "perfil": perfil, "registros": registros}
        )
        fontes = [
            {
                "id": f,
                "fonte": self._por_id[f].titulo_fonte,
                "pagina_pdf": self._por_id[f].pagina_pdf,
            }
            for f in estado.get("fontes", [])
        ]
        sinais = {
            "risco_disparado": estado.get("risco_disparado", False),
            "categorias_risco": list(estado.get("categorias_risco", ())),
            "injecao_detectada": estado.get("injecao_detectada", False),
            "fora_de_escopo": estado.get("fora_de_escopo", False),
            "redirecionado_para": (
                str(estado["redirecionado_para"]) if estado.get("redirecionado_para") else None
            ),
            "nao_sei": estado.get("nao_sei", False),
            "prescricao_bloqueada": estado.get("prescricao_bloqueada", False),
            "tentativas": estado.get("tentativas", 0),
            "trechos_recuperados": [t.id for t in estado.get("trechos", [])],
        }
        return RespostaCultiva(texto=estado["resposta"], fontes=fontes, sinais=sinais)
