"""Máscara de dados pessoais antes de qualquer chamada a LLM (RNF05, issue #9).

Substitui contato e documentos por marcadores fixos. Nome próprio só é mascarado quando a pessoa
se apresenta ("meu nome é ..."): detectar nomes soltos exigiria um modelo de NER, fora do escopo.
"""

import re
from typing import List, Tuple

_NOME = r"[A-ZÀ-Ý][a-zà-ÿ]+(?:\s+(?:d[aeo]s?\s+)?[A-ZÀ-Ý][a-zà-ÿ]+)*"

PADROES_PII: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[EMAIL]"),
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[CPF]"),
    (re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"), "[CNPJ]"),
    (re.compile(r"\b\d{3}\s?\d{4}\s?\d{4}\s?\d{4}\b"), "[CNS]"),
    (re.compile(r"(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?9?\d{4}[-\s]?\d{4}\b"), "[TELEFONE]"),
    (re.compile(r"\b\d{5}-\d{3}\b"), "[CEP]"),
    (re.compile(r"\b((?:meu nome (?:é|e)|me chamo|eu sou (?:o|a))\s+)" + _NOME, re.I), r"\1[NOME]"),
]


def mascarar_dados_pessoais(texto: str) -> str:
    for padrao, marcador in PADROES_PII:
        texto = padrao.sub(marcador, texto)
    return texto
