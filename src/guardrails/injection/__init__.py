"""Defesa contra prompt injection (RNF04).

Duas camadas:
- `has_prompt_injection`: detecta, na pergunta do usuário, tentativas de mudar as regras do
  assistente, extrair o prompt ou encenar um papel sem restrições; o consultor responde com uma
  mensagem fixa, sem busca e sem LLM.
- `delimitar_como_dado`: envolve texto de terceiros (Trechos recuperados, TACO, grafo) num bloco
  delimitado que o prompt de sistema manda tratar como dado, nunca como instrução.
"""

import re

from src.retrieval.hybrid_retriever import normalize_text

# Aplicadas ao texto em minúsculas e sem acentos.
PROMPT_INJECTION_PATTERNS = [
    r"\b(ignore|ignora|ignorar|esqueca|esquece|desconsidere|desconsidera)\b.{0,40}\b(instrucoes|regras|orientacoes|restricoes|prompt|limites)\b",
    r"\b(finja|finge|fingir|imagine|faz de conta)\b.{0,30}\b(que )?(voce|vc)\b.{0,20}\b(e|seja|fosse)\b.{0,10}\b(um|uma|meu|minha)?\s*(nutricionista|medic[oa]|doutor[a]?)\b",
    r"\b(voce|vc) (e|agora e|sera) (um|uma|meu|minha) .{0,30}\bsem (restricoes|regras|limites|filtros)\b",
    r"\bsem (restricoes|regras|limites|filtros)\b.{0,40}\b(responda|responde|me diga|diga)\b",
    r"\bvamos (brincar|fingir|jogar)\b.{0,60}\b(nutricionista|medic[oa]|sem (restricoes|regras|limites))\b",
    r"\bmodo (desenvolvedor|developer|dan|jailbreak|deus)\b",
    r"\b(desative|desativa|desligue|desliga|remova|remove)\b.{0,20}\b(guardrail|filtro|restricoes|regras)\b",
    r"\besque[cs]a a lei( 8\.?234)?\b",
    r"\b(mostre|mostra|revele|revela|imprima|repita|repete)\b.{0,30}\b(seu|o) (prompt|instrucoes|instrucoes do sistema|system prompt)\b",
    r"\bsystem prompt\b",
]

MENSAGEM_INJECAO = (
    "Não consigo mudar minhas regras de funcionamento nem atuar como nutricionista. "
    "Posso explicar o que as diretrizes e os estudos dizem sobre o tema, em nível populacional. "
    "Para uma orientação individual, procure um nutricionista."
)

_DELIMITADOR = re.compile(r"</?\s*dados_de_referencia\s*>", re.I)


def has_prompt_injection(query: str) -> bool:
    """True se a pergunta tenta manipular as regras do assistente (RNF04)."""
    normalizado = normalize_text(query)
    return any(re.search(padrao, normalizado) for padrao in PROMPT_INJECTION_PATTERNS)


def delimitar_como_dado(texto: str) -> str:
    """Envolve texto de terceiros num bloco de dados; remove delimitadores falsos de dentro dele."""
    return f"<dados_de_referencia>\n{_DELIMITADOR.sub('', texto)}\n</dados_de_referencia>"
