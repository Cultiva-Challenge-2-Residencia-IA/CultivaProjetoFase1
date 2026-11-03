import json
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from agents.nutricao import PROMPT_VERSAO
from avaliacao.checagens import aplicar
from dominio.exemplos import PERFIL_EXEMPLO, REGISTROS_EXEMPLO
from modelo.base import ModeloDeLinguagem
from orquestracao import Cultiva
from rag.chunking import RAIZ

# Tipos em que qualquer falha reprova a execução (definição de pronto da fase).
TIPOS_CRITICOS = frozenset({"risco", "fora_de_escopo", "adversarial"})


@dataclass
class ResultadoCaso:
    id: str
    tipo: str
    entrada: str
    ok: bool
    falhas: list[str]
    resposta: str
    sinais: dict[str, Any]
    segundos: float


@dataclass
class Relatorio:
    modelo: str
    prompt_versao: str
    corpus_versao: int
    inicio: str
    casos: list[ResultadoCaso] = field(default_factory=list)

    def por_tipo(self) -> dict[str, dict[str, int]]:
        resumo: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "ok": 0})
        for c in self.casos:
            resumo[c.tipo]["total"] += 1
            resumo[c.tipo]["ok"] += int(c.ok)
        return dict(resumo)

    @property
    def aprovado(self) -> bool:
        return all(c.ok for c in self.casos if c.tipo in TIPOS_CRITICOS)


def carregar_casos(pasta: Path) -> list[dict[str, Any]]:
    casos: list[dict[str, Any]] = []
    for arquivo in sorted(pasta.glob("*.yaml")):
        dados = yaml.safe_load(arquivo.read_text(encoding="utf-8")) or []
        casos.extend(dados)
    ids = [c["id"] for c in casos]
    repetidos = {i for i in ids if ids.count(i) > 1}
    if repetidos:
        raise ValueError(f"IDs repetidos no golden set: {sorted(repetidos)}")
    return casos


def _versao_corpus() -> int:
    manifesto = yaml.safe_load((RAIZ / "corpus" / "manifest.yaml").read_text(encoding="utf-8"))
    return manifesto["version"]


def executar(modelo: ModeloDeLinguagem, pasta: Path) -> Relatorio:
    cultiva = Cultiva(modelo)
    relatorio = Relatorio(
        modelo=modelo.nome,
        prompt_versao=PROMPT_VERSAO,
        corpus_versao=_versao_corpus(),
        inicio=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    for caso in carregar_casos(pasta):
        t0 = time.perf_counter()
        resposta = cultiva.responder(caso["entrada"], PERFIL_EXEMPLO, REGISTROS_EXEMPLO)
        falhas = aplicar(resposta, caso["esperado"], cultiva.ids_corpus)
        relatorio.casos.append(
            ResultadoCaso(
                id=caso["id"],
                tipo=caso["tipo"],
                entrada=caso["entrada"],
                ok=not falhas,
                falhas=falhas,
                resposta=resposta.texto,
                sinais=resposta.sinais,
                segundos=round(time.perf_counter() - t0, 2),
            )
        )
    return relatorio


def salvar(relatorio: Relatorio, pasta_saida: Path) -> Path:
    pasta_saida.mkdir(parents=True, exist_ok=True)
    carimbo = relatorio.inicio.replace(":", "").replace("-", "")
    caminho = pasta_saida / f"{carimbo}_{relatorio.modelo.replace(':', '-')}.json"
    conteudo = asdict(relatorio) | {
        "por_tipo": relatorio.por_tipo(),
        "aprovado": relatorio.aprovado,
    }
    caminho.write_text(json.dumps(conteudo, ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho
