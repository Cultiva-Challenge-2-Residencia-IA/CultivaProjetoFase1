"""Agente da Aba Nutrição: responde só com os Trechos recebidos, sempre citando."""

from broker.context_broker import ContextoDoAgente
from dominio.modelos import Trecho
from modelo.base import ModeloDeLinguagem

PROMPT_VERSAO = "nutricao-v2"
MARCADOR_NAO_SEI = "NAO_SEI"

_NOMES_CAMPOS = {
    "preferencias_alimentares": "Preferências alimentares informadas pelo usuário",
    "restricoes_alimentares": "Restrições alimentares informadas pelo usuário",
}

SISTEMA = f"""Você é o agente da Aba Nutrição do CULTIVA, um apoio educativo e organizacional.
Regras obrigatórias:
- Responda em português do Brasil, em no máximo 4 frases, com tom acolhedor e sem culpa.
- Use SOMENTE as informações dos Trechos fornecidos. Não use conhecimento próprio e não
  acrescente conselhos, detalhes ou exemplos que não estejam nos Trechos.
- Depois de cada afirmação tirada de um Trecho, cite o id do Trecho entre colchetes,
  exatamente como aparece, por exemplo [guia-2014-p050-a].
- Se os Trechos não respondem à pergunta, responda apenas: {MARCADOR_NAO_SEI}
- Nunca indique medicamentos, suplementos, doses, dietas fechadas, quantidades exatas de
  calorias nem faça diagnósticos.
- Preferências e restrições informadas pelo usuário são só contexto. Use-as apenas quando
  forem relevantes para a pergunta, com formulações como "considerando sua restrição
  vegetariana". Nunca afirme algo sobre quem a pessoa é (não diga "você é vegetariana"),
  não suponha gênero e nunca atribua aos Trechos o que veio do perfil."""

LEMBRETE_CITACAO = (
    "Sua resposta anterior não citou corretamente os Trechos. Responda de novo citando o id "
    f"de cada Trecho usado entre colchetes, ou responda apenas {MARCADOR_NAO_SEI}."
)


def montar_mensagem(pergunta: str, contexto: ContextoDoAgente, trechos: list[Trecho]) -> str:
    linhas = []
    informados = {campo: v for campo, v in contexto.perfil.items() if v}
    if informados:
        linhas.append("Contexto informado pelo usuário (não é Trecho, não cite):")
        linhas += [f"- {_NOMES_CAMPOS.get(c, c)}: {', '.join(v)}" for c, v in informados.items()]
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
