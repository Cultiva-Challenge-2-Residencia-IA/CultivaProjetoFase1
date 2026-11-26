"""Reranker cross-encoder multilíngue, local pelo fastembed (issue #105).

O cross-encoder lê a pergunta e o Trecho juntos e devolve uma nota de relevância, o que a busca
híbrida não faz: o BM25 só casa termos, e o vetor denso compara a pergunta e o Trecho separados.
Em Saúde Física, 16 das 18 fontes estão em inglês, e um modelo multilíngue julga "treinar perna"
contra "lower body resistance training".

A nota é a sigmoide da saída do modelo (0 a 1). Ela serve para duas coisas:

- reordenar os candidatos da busca híbrida (`HybridRetriever`, com `reranker`);
- o filtro de relevância antes da síntese (`src/rag/relevancia.py`), que compara a nota com um
  limiar absoluto.

O modelo é carregado na primeira chamada e fica em memória; as notas ficam num cache por pergunta e
Trecho, porque o filtro julga de novo os Trechos que o reranker já julgou. Na primeira vez na
máquina, o fastembed baixa o modelo (cerca de 1,1 GB no jina), e a primeira pergunta de Saúde
Física demora. Para baixar antes, por exemplo antes de uma demonstração:

    uv run python -m src.retrieval.reranker_cruzado

Licença: o `jinaai/jina-reranker-v2-base-multilingual` (padrão) é CC BY-NC 4.0, só para pesquisa e
avaliação; uso comercial exige outra licença da Jina AI. O `BAAI/bge-reranker-v2-m3` é Apache-2.0.
O projeto é acadêmico; antes de qualquer uso comercial, troque o `RERANKER_MODELO`.
"""

from collections import OrderedDict
import math
import sys
import threading
import time
from typing import Any, Dict, List, Sequence, Tuple

_MODELOS: Dict[str, Any] = {}
# O Chat geral roda os Agentes de área em paralelo (#107), e a API atende requisições em threads:
# a carga do modelo e o cache são protegidos por travas. A inferência roda fora da trava.
_TRAVA_CARGA = threading.Lock()


def _modelo(nome: str) -> Any:
    if nome in _MODELOS:
        return _MODELOS[nome]
    with _TRAVA_CARGA:
        if nome in _MODELOS:  # outra thread carregou enquanto esta esperava
            return _MODELOS[nome]
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        from src.retrieval.vector_store import provedores_onnx

        print(f"Carregando o reranker {nome}; na primeira vez na máquina, o download tem cerca de 1 GB.",
              file=sys.stderr, flush=True)
        inicio = time.perf_counter()
        _MODELOS[nome] = TextCrossEncoder(model_name=nome, providers=provedores_onnx())
        print(f"Reranker carregado em {time.perf_counter() - inicio:.1f} s.", file=sys.stderr, flush=True)
        return _MODELOS[nome]


def _sigmoide(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


class RerankerCruzado:
    """Nota de relevância (0 a 1) de cada par (pergunta, texto)."""

    def __init__(self, modelo: str, tamanho_cache: int = 4096, lote: int = 8) -> None:
        self.modelo = modelo
        self.lote = lote
        self._tamanho_cache = tamanho_cache
        self._cache: "OrderedDict[Tuple[str, str], float]" = OrderedDict()
        self._trava = threading.Lock()

    def _pontuar_modelo(self, consulta: str, textos: Sequence[str]) -> List[float]:
        brutos = _modelo(self.modelo).rerank(consulta, list(textos), batch_size=self.lote)
        return [_sigmoide(float(b)) for b in brutos]

    def pontuar(self, consulta: str, textos: Sequence[str], chaves: Sequence[str] = ()) -> List[float]:
        """Notas na ordem dos textos. `chaves` (o id de cada texto) ativa o cache."""
        chaves = list(chaves) or [None] * len(textos)
        notas: List[float] = [0.0] * len(textos)
        faltam = []
        with self._trava:
            for i, chave in enumerate(chaves):
                nota = self._cache.get((consulta, chave)) if chave is not None else None
                if nota is None:
                    faltam.append(i)
                else:
                    self._cache.move_to_end((consulta, chave))
                    notas[i] = nota
        if faltam:
            novas = self._pontuar_modelo(consulta, [textos[i] for i in faltam])
            with self._trava:
                for i, nota in zip(faltam, novas):
                    notas[i] = nota
                    if chaves[i] is not None:
                        self._cache[(consulta, chaves[i])] = nota
                        if len(self._cache) > self._tamanho_cache:
                            self._cache.popitem(last=False)
        return notas


if __name__ == "__main__":
    # Baixa e carrega o modelo do RERANKER_MODELO (ou o nome passado) antes da primeira pergunta.
    from src.config import RERANKER_MODELO

    nome = sys.argv[1] if len(sys.argv) > 1 else RERANKER_MODELO
    print(RerankerCruzado(nome).pontuar("aquecimento antes do treino", ["Warm up before exercising."]))
