"""Checagem de exagero depois da geração (issue #86, RNF27): avaliação offline, fora do produto.

A citação literal (`filtrar_citacoes_literais`, #67) pega invenção, não exagero: a citação existe,
mas a frase perde a condição, o público ou a dose do Trecho, ou fica mais categórica que ele. Aqui
uma segunda chamada ao LLM local recebe cada frase com o texto dos Trechos que ela cita e decide se
eles sustentam tudo o que a frase afirma. O verificador roda sobre as 120 frases já julgadas pelo
ChatGPT, com critérios definidos antes da medição (`eval/fundamentacao/exagero_criterios.md`).

Resultado (`eval/fundamentacao/resultado_exagero.md`): com o `gemma4:e4b`, ele não achou as
parciais (0 de 5 no `test`), e por isso **não está ligado no produto**. Fica aqui para repetir a
medição com outro modelo ou outro prompt.

    uv run python -m src.evaluation.exagero --split dev
    uv run python -m src.evaluation.exagero --split test
    uv run --group modelo-local python -m src.evaluation.exagero --verificador nli --split dev
    uv run --group modelo-local python -m src.evaluation.exagero --verificador nli --split test --limiar <do dev>

Exige o Ollama local (ADR 0003). Qualquer falha do verificador devolve veredito `None`, que conta
como frase mantida. Grava `eval/fundamentacao/exagero_<versão>_<split>.json`.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import statistics
import time
from typing import Dict, List, Optional

import httpx

from src.config import OLLAMA_BASE_URL, OLLAMA_MODEL

EXAGERO_TIMEOUT = float(os.getenv("EXAGERO_TIMEOUT", "20.0"))
KEEP_ALIVE = "30m"
SEMENTE = 42

# v2 é a versão final: a v3 (o mesmo prompt com `think`) levou mais de 45 s por frase e foi abandonada.
PROMPT_VERSAO = "exagero-v2"
PROMPT = """Você confere se uma FRASE de uma resposta de Nutrição é sustentada pelos TRECHOS que ela cita.
A FRASE é sustentada só se os TRECHOS afirmam tudo o que ela afirma, com as mesmas condições.

Faça nesta ordem:
1. "afirmacao": a afirmação central da FRASE, em poucas palavras.
2. "ressalvas_do_trecho": no ponto dos TRECHOS que trata dessa afirmação, liste TODAS as palavras
   ou expressões que limitam ou qualificam a afirmação: público ou grupo (quem foi estudado, quem
   recebeu o quê), condição clínica ou situação (por exemplo, "após cirurgia", "no tratamento de"),
   dose ou quantidade ligada ao efeito, duração, tipo de produto, palavras como "adicionais",
   "outros", "alguns estudos", "pode", "sugere", "em geral", exceções ("exceto", "salvo"), e se o
   trecho descreve um fato ou dá uma orientação.
3. "ressalvas_perdidas": das ressalvas do item 2, as que a FRASE omite, troca por algo mais amplo ou
   contradiz. Também conta como perdida: a FRASE transformar descrição ou benefício em orientação
   ("deve", "é preciso"), afirmar com mais certeza que o trecho, atribuir a algo ou alguém que o
   trecho não indica, ou acrescentar número, efeito ou conclusão que não está nos TRECHOS.
4. "sustentada": true só se "ressalvas_perdidas" estiver vazia.

Sinônimos e resumo que mantêm todas as ressalvas continuam sustentados. Não use conhecimento próprio.

Responda só com JSON:
{"afirmacao": "...", "ressalvas_do_trecho": ["..."], "ressalvas_perdidas": ["..."], "sustentada": true | false}"""

_MARCADOR = re.compile(r"\s*\[(?:T\d+|GRAFO|TACO)\]")


@dataclass
class Veredito:
    sustentada: Optional[bool]
    problema: str = ""
    segundos: float = 0.0
    erro: Optional[str] = None


def sem_marcadores(frase: str) -> str:
    return _MARCADOR.sub("", frase).strip()


class VerificadorExagero:
    """Uma chamada ao Ollama por frase; `verificar` nunca levanta exceção."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL, modelo: str = OLLAMA_MODEL,
                 timeout: float = EXAGERO_TIMEOUT, cliente: Optional[httpx.Client] = None) -> None:
        self.base_url, self.modelo, self.timeout = base_url, modelo, timeout
        self._cliente = cliente

    def _post(self, payload: dict) -> dict:
        if self._cliente is not None:
            resposta = self._cliente.post(f"{self.base_url}/api/chat", json=payload)
        else:
            with httpx.Client(timeout=self.timeout) as cliente:
                resposta = cliente.post(f"{self.base_url}/api/chat", json=payload)
        resposta.raise_for_status()
        return resposta.json()

    def verificar(self, frase: str, trechos: List[str]) -> Veredito:
        inicio = time.perf_counter()
        textos = "\n\n".join(f"TRECHO {i}:\n{t}" for i, t in enumerate(trechos, 1)) or "(nenhum trecho)"
        payload = {
            "model": self.modelo, "stream": False, "format": "json", "think": False,
            "keep_alive": KEEP_ALIVE,
            "messages": [
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": f"TRECHOS:\n{textos}\n\nFRASE:\n{sem_marcadores(frase)}"},
            ],
            "options": {"temperature": 0, "seed": SEMENTE, "num_predict": 768},
        }
        try:
            dados = json.loads(self._post(payload)["message"]["content"])
            sustentada = dados.get("sustentada")
            if not isinstance(sustentada, bool):
                raise ValueError(f"campo 'sustentada' inválido: {sustentada!r}")
            perdidas = dados.get("ressalvas_perdidas") or []
            problema = "; ".join(map(str, perdidas)) if isinstance(perdidas, list) else str(perdidas)
            return Veredito(sustentada, problema.strip(), time.perf_counter() - inicio)
        except Exception as e:  # noqa: BLE001 - qualquer falha mantém a frase
            return Veredito(None, segundos=time.perf_counter() - inicio, erro=f"{type(e).__name__}: {e}")


PASTA = Path(__file__).resolve().parents[2] / "eval" / "fundamentacao"
AMOSTRAS = ("v4", "v5")


def carregar(split: str) -> List[Dict]:
    """Frases das amostras v4 e v5 do `gemma4:e4b` com o julgamento do ChatGPT."""
    frases = []
    for versao in AMOSTRAS:
        amostra = json.loads((PASTA / f"amostra_{versao}_gemma4.json").read_text(encoding="utf-8"))
        with (PASTA / f"amostra_{versao}_gemma4_para_avaliar.csv").open(encoding="utf-8") as f:
            julgadas = list(csv.DictReader(f))
        for item, julgada in zip(amostra, julgadas, strict=True):
            if item["frase"] != julgada["frase"]:
                raise ValueError(f"Amostra {versao} e planilha fora de ordem em {julgada['id']}")
            if split != "todos" and item["split"] != split:
                continue
            frases.append({
                "id": f"{versao}-{julgada['id']}", "split": item["split"], "frase": item["frase"],
                "trechos": [t["texto"] for t in item["trechos_citados"]],
                "julgamento": julgada["julgamento"],
            })
    return frases


def resumir(resultados: List[Dict]) -> Dict:
    sust = [r for r in resultados if r["julgamento"] == "sustentada"]
    parc = [r for r in resultados if r["julgamento"] != "sustentada"]
    marcada = lambda r: r["veredito"] is False  # noqa: E731 - sem veredito, a frase fica
    s_mantidas = sum(not marcada(r) for r in sust)
    p_mantidas = sum(not marcada(r) for r in parc)
    return {
        "frases": len(resultados), "sustentadas": len(sust), "parciais": len(parc),
        "parciais_achadas": sum(map(marcada, parc)),
        "taxa_parciais_achadas": round(sum(map(marcada, parc)) / max(1, len(parc)), 3),
        "remocao_indevida": sum(map(marcada, sust)),
        "taxa_remocao_indevida": round(sum(map(marcada, sust)) / max(1, len(sust)), 3),
        "taxa_sustentadas_antes": round(len(sust) / max(1, len(resultados)), 3),
        "taxa_projetada": round(s_mantidas / max(1, s_mantidas + p_mantidas), 3),
        "falhas": sum(r["veredito"] is None for r in resultados),
        "segundos_mediana": round(statistics.median(r["segundos"] for r in resultados), 2) if resultados else 0,
    }


MODELO_NLI = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
REMOCAO_MAXIMA_DEV = 0.10


class VerificadorNLI:
    """Modelo de inferência textual no processador (adendo dos critérios): só pontua, não decide.

    A pontuação da frase é a maior probabilidade de `entailment` entre os Trechos que ela cita;
    a frase é marcada quando ela fica abaixo do limiar escolhido no `dev`.
    Exige `uv sync --group modelo-local` (PyTorch para CPU e transformers).
    """

    def __init__(self, modelo: str = MODELO_NLI) -> None:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(modelo)
        self.modelo = AutoModelForSequenceClassification.from_pretrained(modelo).eval()
        rotulos = {v.lower(): int(k) for k, v in self.modelo.config.id2label.items()}
        self.indice_entailment = rotulos["entailment"]

    def pontuar(self, frase: str, trechos: List[str]) -> float:
        import torch

        hipotese = sem_marcadores(frase)
        entrada = self.tokenizer(list(trechos), [hipotese] * len(trechos), truncation="only_first",
                                 max_length=512, padding=True, return_tensors="pt")
        with torch.no_grad():
            probs = torch.softmax(self.modelo(**entrada).logits, dim=-1)
        return float(probs[:, self.indice_entailment].max())


def escolher_limiar(pontuadas: List[Dict], remocao_maxima: float = REMOCAO_MAXIMA_DEV) -> float:
    """Maior limiar com remoção indevida <= `remocao_maxima` (frase marcada quando pontuação < limiar)."""
    sust = sorted(r["pontuacao"] for r in pontuadas if r["julgamento"] == "sustentada")
    candidatos = sorted({r["pontuacao"] for r in pontuadas} | {0.0, 1.0 + 1e-9})
    melhor = 0.0
    for limiar in candidatos:
        if sum(s < limiar for s in sust) / max(1, len(sust)) <= remocao_maxima:
            melhor = limiar
    return melhor


def _salvar(nome: str, dados: Dict) -> Path:
    saida = PASTA / nome
    saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return saida


def main_nli(split: str, limiar: Optional[float]) -> int:
    if split == "test" and limiar is None:
        raise SystemExit("No test, passe o --limiar escolhido no dev (critérios: o test roda uma vez).")
    verificador = VerificadorNLI()
    resultados = []
    for frase in carregar(split):
        inicio = time.perf_counter()
        pontuacao = verificador.pontuar(frase["frase"], frase["trechos"])
        resultados.append({**{k: frase[k] for k in ("id", "split", "julgamento", "frase")},
                           "pontuacao": round(pontuacao, 4), "segundos": round(time.perf_counter() - inicio, 2)})
        print(f"{frase['id']:10} {frase['julgamento']:10} {pontuacao:.3f}", flush=True)
    if limiar is None:
        limiar = escolher_limiar(resultados)
    for r in resultados:
        r["veredito"] = r["pontuacao"] >= limiar
    resumo = {"limiar": limiar, **resumir(resultados)}
    saida = _salvar(f"exagero_nli_{split}.json", {"modelo": MODELO_NLI, "split": split, "resumo": resumo,
                                                  "frases": resultados})
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    print(f"Resultado: {saida}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=["dev", "test", "todos"], required=True)
    parser.add_argument("--verificador", choices=["llm", "nli"], default="llm")
    parser.add_argument("--limiar", type=float, help="Só NLI: limiar congelado do dev, obrigatório no test")
    args = parser.parse_args()
    if args.verificador == "nli":
        return main_nli(args.split, args.limiar)
    verificador = VerificadorExagero()
    resultados = []
    for frase in carregar(args.split):
        v = verificador.verificar(frase["frase"], frase["trechos"])
        resultados.append({**{k: frase[k] for k in ("id", "split", "julgamento", "frase")},
                           "veredito": v.sustentada, "problema": v.problema,
                           "segundos": round(v.segundos, 2), "erro": v.erro})
        print(f"{frase['id']:10} {frase['julgamento']:10} -> {v.sustentada}", flush=True)
    resumo = resumir(resultados)
    saida = PASTA / f"exagero_{PROMPT_VERSAO}_{args.split}.json"
    saida.write_text(json.dumps({"prompt": PROMPT_VERSAO, "split": args.split, "resumo": resumo,
                                 "frases": resultados}, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8", newline="\n")
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    print(f"Resultado: {saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
