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
Trecho, porque o filtro julga de novo os Trechos que o reranker já julgou.
"""

from collections import OrderedDict
import math
from typing import Any, Dict, List, Sequence, Tuple

_MODELOS: Dict[str, Any] = {}


def _modelo(nome: str) -> Any:
    if nome not in _MODELOS:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        _MODELOS[nome] = TextCrossEncoder(model_name=nome)
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

    def _pontuar_modelo(self, consulta: str, textos: Sequence[str]) -> List[float]:
        brutos = _modelo(self.modelo).rerank(consulta, list(textos), batch_size=self.lote)
        return [_sigmoide(float(b)) for b in brutos]

    def pontuar(self, consulta: str, textos: Sequence[str], chaves: Sequence[str] = ()) -> List[float]:
        """Notas na ordem dos textos. `chaves` (o id de cada texto) ativa o cache."""
        chaves = list(chaves) or [None] * len(textos)
        notas: List[float] = [0.0] * len(textos)
        faltam = []
        for i, chave in enumerate(chaves):
            if chave is not None and (consulta, chave) in self._cache:
                self._cache.move_to_end((consulta, chave))
                notas[i] = self._cache[(consulta, chave)]
            else:
                faltam.append(i)
        if faltam:
            novas = self._pontuar_modelo(consulta, [textos[i] for i in faltam])
            for i, nota in zip(faltam, novas):
                notas[i] = nota
                if chaves[i] is not None:
                    self._cache[(consulta, chaves[i])] = nota
                    if len(self._cache) > self._tamanho_cache:
                        self._cache.popitem(last=False)
        return notas
