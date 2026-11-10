"""Máscara de dados pessoais antes de qualquer chamada a LLM (RNF05, issue #9).

Substitui contato e documentos por marcadores fixos. Nome próprio só é mascarado quando a pessoa
se apresenta ("meu nome é ..."): detectar nomes soltos exigiria um modelo de NER, fora do escopo.
"""

import re
from typing import List, Tuple

_SEM_UNIDADE = r"(?!\s*(?:kcal|cal|calorias|kg|g|mg|mcg|ug|µg|ui|ml|l|%)\b)"
_NOME = r"[A-ZÀ-Ý][a-zà-ÿ]+(?:\s+(?:d[aeo]s?\s+)?[A-ZÀ-Ý][a-zà-ÿ]+)*"

PADROES_PII: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[EMAIL]"),
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[CPF]"),
    (re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"), "[CNPJ]"),
    (re.compile(r"\b\d{3}\s?\d{4}\s?\d{4}\s?\d{4}\b"), "[CNS]"),
    # Telefone com DDD, ou celular com 9 inicial e hífen. Número seguido de unidade de medida não é
    # telefone: "1500-2000 kcal" e "1000 2000 UI" precisam chegar intactos ao LLM.
    (re.compile(r"(?:\+?55\s?)?\(\d{2}\)\s?9?\d{4}[-\s]?\d{4}\b" + _SEM_UNIDADE), "[TELEFONE]"),
    (re.compile(r"(?<![\d.,])(?:\+?55\s?)?\d{2}\s9?\d{4}-\d{4}\b" + _SEM_UNIDADE), "[TELEFONE]"),
    (re.compile(r"(?<![\d.,])9\d{4}-\d{4}\b" + _SEM_UNIDADE), "[TELEFONE]"),
    (re.compile(r"\b\d{5}-\d{3}\b"), "[CEP]"),
    (re.compile(r"\b((?:meu nome (?:é|e)|me chamo|eu sou (?:o|a))\s+)" + _NOME, re.I), r"\1[NOME]"),
]


def mascarar_dados_pessoais(texto: str) -> str:
    for padrao, marcador in PADROES_PII:
        texto = padrao.sub(marcador, texto)
    return texto
