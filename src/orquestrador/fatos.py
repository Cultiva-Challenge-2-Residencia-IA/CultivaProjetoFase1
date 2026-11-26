"""Fatos do Usuário: esquema, extração e escolha para o Projetor de contexto (issue #112, ADR 0005).

Um Fato do Usuário é uma afirmação curta sobre a vida do Usuário numa área, com a área definida
pelo assunto, não pelo chat (`GLOSSARY.md`). O esquema é fixo (padrão de perfil do LangMem): só as
categorias abaixo existem, e o que o LLM devolver fora delas é descartado (LGPD, art. 6º, III).

O fato só personaliza e relaciona a resposta, nunca é fonte. Condição de saúde declarada é dado
sensível (LGPD, art. 11): exige consentimento à parte e só orienta a escolha da evidência e o
encaminhamento a profissional.
"""

from dataclasses import dataclass
import json
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.orquestrador.roteamento import AREA_NUTRICAO, AREA_SAUDE_FISICA

AREA_TRANSVERSAL = "transversal"
CATEGORIA_CONDICAO_SAUDE = "condicao_saude"

# categoria -> (área do assunto, descrição para o LLM)
CATEGORIAS: Dict[str, Tuple[str, str]] = {
    "atividade_praticada": (AREA_SAUDE_FISICA, "atividade física ou esporte que a pessoa pratica"),
    "frequencia_treino": (AREA_SAUDE_FISICA, "frequência, duração ou volume dos treinos"),
    "objetivo_treino": (AREA_SAUDE_FISICA, "objetivo declarado com o exercício"),
    "limitacao_fisica": (AREA_SAUDE_FISICA, "limitação física que a própria pessoa declarou (ex.: dor no joelho)"),
    "padrao_alimentar": (AREA_NUTRICAO, "padrão alimentar (ex.: vegetariano, vegano, low carb)"),
    "jejum_horarios": (AREA_NUTRICAO, "jejum ou horários das refeições"),
    "restricao_alergia": (AREA_NUTRICAO, "restrição, intolerância ou alergia alimentar declarada"),
    "objetivo_alimentar": (AREA_NUTRICAO, "objetivo declarado com a alimentação"),
    CATEGORIA_CONDICAO_SAUDE: (AREA_TRANSVERSAL, "condição de saúde que a própria pessoa declarou (ex.: diabetes)"),
}

MAX_CARACTERES_DO_FATO = 160


@dataclass(frozen=True)
class FatoDoUsuario:
    id: int
    categoria: str
    area: str
    texto: str
    conversa_id: str
    valido_desde: str

    @property
    def condicao_de_saude(self) -> bool:
        return self.categoria == CATEGORIA_CONDICAO_SAUDE

    def como_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "categoria": self.categoria, "area": self.area, "texto": self.texto,
                "valido_desde": self.valido_desde}


SISTEMA_EXTRACAO = "\n".join([
    "Você extrai Fatos do Usuário de uma mensagem que ele escreveu num aplicativo educativo de nutrição e",
    "atividade física. Um fato é uma afirmação curta sobre a vida da própria pessoa, dita por ela.",
    "",
    "Categorias permitidas (use só estas):",
    *[f'- "{nome}": {descricao}' for nome, (_, descricao) in CATEGORIAS.items()],
    "",
    "Regras:",
    "1. Só o que a pessoa afirma sobre si mesma. Perguntas, dúvidas, hipóteses e fatos de outras pessoas não são fatos.",
    "2. Uma frase curta por fato, em terceira pessoa (ex.: \"pratica musculação 4 vezes por semana\").",
    "3. Não deduza nem diagnostique: só o que está escrito.",
    "4. Sem nada a extrair, devolva a lista vazia.",
    "",
    'Responda só com JSON: {"fatos": [{"categoria": "...", "texto": "..."}]}',
])


def extrair_fatos(mensagem: str, llm, permitir_saude: bool) -> List[Tuple[str, str]]:
    """(categoria, texto) dos fatos da mensagem; categoria fora do esquema ou de saúde sem
    consentimento é descartada. Falha do LLM não extrai nada."""
    try:
        bruto = llm(SISTEMA_EXTRACAO, json.dumps({"mensagem": mensagem}, ensure_ascii=False))
    except Exception:
        return []
    fatos: List[Tuple[str, str]] = []
    itens = bruto.get("fatos") if isinstance(bruto, dict) else None
    for item in itens if isinstance(itens, list) else []:
        if not isinstance(item, dict):
            continue
        categoria = str(item.get("categoria") or "").strip()
        texto = " ".join(str(item.get("texto") or "").split())[:MAX_CARACTERES_DO_FATO]
        if categoria not in CATEGORIAS or not texto:
            continue
        if categoria == CATEGORIA_CONDICAO_SAUDE and not permitir_saude:
            continue
        fatos.append((categoria, texto))
    return fatos


def candidatos_em_texto(fatos: Sequence[FatoDoUsuario]) -> List[Dict[str, Any]]:
    """Os fatos como vão à reescrita, para a escolha por Subpergunta (sem a conversa de origem)."""
    return [{"id": f.id, "categoria": f.categoria, "texto": f.texto} for f in fatos]


def escolhidos(ids: Any, fatos: Sequence[FatoDoUsuario]) -> List[FatoDoUsuario]:
    """Os fatos cujos ids o LLM escolheu; id que não existe entre os candidatos é ignorado."""
    por_id = {f.id: f for f in fatos}
    saida: List[FatoDoUsuario] = []
    for valor in ids if isinstance(ids, list) else []:
        try:
            fato = por_id.get(int(valor))
        except (TypeError, ValueError):
            fato = None
        if fato is not None and fato not in saida:
            saida.append(fato)
    return saida


def area_do_fato(categoria: str) -> Optional[str]:
    return CATEGORIAS.get(categoria, (None, ""))[0]
