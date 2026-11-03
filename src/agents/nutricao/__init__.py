"""Agente da Aba Nutrição: responde só com os Trechos recebidos, sempre citando."""

from broker.context_broker import ContextoDoAgente
from dominio.modelos import Trecho
from modelo.base import ModeloDeLinguagem

PROMPT_VERSAO = "nutricao-v1"
MARCADOR_NAO_SEI = "NAO_SEI"

SISTEMA = f"""Você é o agente da Aba Nutrição do CULTIVA, um apoio educativo e organizacional.
Regras obrigatórias:
- Responda em português do Brasil, em no máximo 4 frases, com tom acolhedor e sem culpa.
- Use SOMENTE as informações dos Trechos fornecidos. Não use conhecimento próprio.
- Depois de cada afirmação, cite o id do Trecho entre colchetes, exatamente como aparece,
  por exemplo [guia-2014-p050-a].
- Se os Trechos não respondem à pergunta, responda apenas: {MARCADOR_NAO_SEI}
- Nunca indique medicamentos, suplementos, doses, dietas fechadas, quantidades exatas de
  calorias nem faça diagnósticos.
- Considere as preferências e restrições do usuário quando forem relevantes."""

LEMBRETE_CITACAO = (
    "Sua resposta anterior não citou corretamente os Trechos. Responda de novo citando o id "
    f"de cada Trecho usado entre colchetes, ou responda apenas {MARCADOR_NAO_SEI}."
)


def montar_mensagem(pergunta: str, contexto: ContextoDoAgente, trechos: list[Trecho]) -> str:
    linhas = []
    if contexto.perfil:
        partes = [f"{campo}: {', '.join(v) or 'nenhuma'}" for campo, v in contexto.perfil.items()]
        linhas.append("Perfil do usuário: " + "; ".join(partes))
    if contexto.registros:
        linhas.append("Registros recentes da Aba Nutrição:")
        linhas += [f"- {r.data.isoformat()}: {r.descricao}" for r in contexto.registros]
    linhas.append("Trechos:")
    linhas += [f"[{t.id}] {t.texto}" for t in trechos]
    linhas.append(f"Pergunta: {pergunta}")
    return "\n".join(linhas)


class AgenteNutricao:
    nome = "nutricao"

    def __init__(self, modelo: ModeloDeLinguagem):
        self._modelo = modelo

    def responder(
        self,
        pergunta: str,
        contexto: ContextoDoAgente,
        trechos: list[Trecho],
        lembrar_citacao: bool = False,
    ) -> str:
        mensagem = montar_mensagem(pergunta, contexto, trechos)
        if lembrar_citacao:
            mensagem = f"{mensagem}\n\n{LEMBRETE_CITACAO}"
        return self._modelo.gerar(SISTEMA, mensagem)
