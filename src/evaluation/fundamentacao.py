"""Citações por frase e fundamentação (issue #12, RNF27).

Três passos (critérios em eval/fundamentacao/criterios.md):

    # 1. Mede, com o LLM local, quantas respostas passam na checagem de citações (antes do bloqueio)
    uv run python -m src.evaluation.fundamentacao medir --split dev
    # 2. Sorteia as frases para a amostra humana (planilha para um colega preencher)
    uv run python -m src.evaluation.fundamentacao amostra
    # 3. Calcula a fidelidade a partir da planilha preenchida (meta do RNF27: 95% sustentadas)
    uv run python -m src.evaluation.fundamentacao calcular
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
import random
import time
from typing import Any, Dict, List, Optional

from src.evaluation import benchmark_v2
from src.rag.verificador.citacoes import (
    CAMPOS_DO_LLM,
    FRASE_SEM_BASE,
    MARCADOR,
    eh_trecho,
    normalizar_frases_citadas,
    dividir_frases,
)

DIR = Path("eval/fundamentacao")
TAMANHO_AMOSTRA = 60
MAX_POR_RESPOSTA = 3
SEMENTE = 12
JULGAMENTOS = ("sustentada", "parcial", "nao_sustentada")


def _resultado_path(split: str, rotulo: str = "") -> Path:
    """`rotulo` separa os resultados de outro modelo (ex.: "gemma4_e4b") dos do modelo padrão."""
    return DIR / (f"resultados_{split}_{rotulo}.json" if rotulo else f"resultados_{split}.json")


def medir(split: str, rotulo: str = "") -> Dict[str, Any]:
    from src.agent.consultant_baseline import NutritionConsultantBaseline

    consultor = NutritionConsultantBaseline(enable_ollama=True)
    cliente = consultor.llm_client
    if not cliente.is_ollama_available():
        raise SystemExit("Ollama indisponível: a medição precisa do LLM local (ADR 0003).")

    # Guarda a saída crua do LLM, antes da mistura com a síntese extrativa, para a amostra humana.
    bruto: Dict[str, Any] = {}
    chamar_original = cliente._call_ollama_model

    def chamar(modelo: str, prompt: str) -> Optional[Dict[str, Any]]:
        bruto["resposta"] = chamar_original(modelo, prompt)
        return bruto["resposta"]

    cliente._call_ollama_model = chamar

    casos = [c for c in benchmark_v2.carregar_casos() if split == "todos" or c["split"] == split]
    itens = []
    for caso in casos:
        bruto.clear()
        inicio = time.perf_counter()
        r = consultor.consult(caso["pergunta"])
        segundos = round(time.perf_counter() - inicio, 1)
        llm = bruto.get("resposta")
        if llm is not None:
            llm = normalizar_frases_citadas(llm)  # formato estruturado -> texto com marcadores
        item: Dict[str, Any] = {
            "id": caso["id"], "split": caso["split"], "pergunta": caso["pergunta"],
            "modelo": r.model_used, "fundamentacao_status": r.fundamentacao_status,
            "fundamentacao_problemas": r.fundamentacao_problemas, "segundos": segundos,
            "chegou_ao_llm": llm is not None,
        }
        # A mesma checagem que decidiu o bloqueio na produção (não recalculada aqui).
        v = cliente.ultima_verificacao
        if llm is not None and v is None:
            item["chegou_ao_llm"] = True
            item.update({"citacoes_validas": None, "problemas": [], "frases": 0, "frases_sem_citacao": [],
                         "marcadores_invalidos": [], "texto_llm": {c: llm.get(c, "") for c in CAMPOS_DO_LLM},
                         "trechos": []})
        if llm is not None and v is not None:
            # Texto que segue para a resposta: já sem as frases removidas por citação literal (#67).
            aceito = cliente.ultima_resposta_aceita or llm
            removidas = list(cliente.ultimas_frases_removidas)
            corrigidas = list(cliente.ultimos_rotulos_corrigidos)
            item.update({
                "citacoes_validas": v.valida, "problemas": v.problemas, "frases": v.frases,
                "frases_sem_citacao": v.frases_sem_citacao, "marcadores_invalidos": v.marcadores_invalidos,
                "frases_removidas": removidas, "rotulos_corrigidos": corrigidas,
                "texto_llm": {campo: aceito.get(campo, "") for campo in CAMPOS_DO_LLM},
                "trechos": [
                    {"marcador": f"T{i}", "chunk_id": rc.chunk.chunk_id, "fonte": rc.chunk.title,
                     "pagina_pdf": rc.chunk.pagina_pdf, "texto": rc.chunk.raw_text}
                    for i, rc in enumerate(r.retrieved_chunks, 1)
                ],
            })
        itens.append(item)
        print(f"{caso['id']:12s} {item['fundamentacao_status'] or '-':32s} {segundos:5.1f} s "
              f"removidas={len(item.get('frases_removidas', []))} corrigidas={len(item.get('rotulos_corrigidos', []))} "
              f"{' '.join(item.get('problemas', []))}")

    # Respostas do LLM que passaram pela checagem; "llm_sem_base" (o LLM disse que os Trechos não
    # respondem) não é checada e vira "não sei", então fica contada à parte.
    avaliadas = [i for i in itens if i.get("citacoes_validas") is not None]
    sem_base = [i for i in itens if i["fundamentacao_status"] == "llm_sem_base"]
    tipos = Counter(p.split(":")[0] for i in avaliadas for p in i["problemas"])
    resumo = {
        "split": split, "modelo": cliente.primary_model, "casos": len(itens),
        "chegaram_ao_llm": sum(i["chegou_ao_llm"] for i in itens),
        "checadas": len(avaliadas),
        "llm_sem_base_vira_nao_sei": len(sem_base),
        "conformidade_citacao_llm": round(sum(i["citacoes_validas"] for i in avaliadas) / max(len(avaliadas), 1), 4),
        "taxa_fallback": round(
            sum(i["fundamentacao_status"] == "extrativa_apos_citacao_invalida" for i in avaliadas)
            / max(len(avaliadas), 1), 4),
        "problemas_por_tipo": dict(tipos),
        # Citação literal (#67): frases do LLM descartadas e respostas que mantiveram ao menos uma.
        "frases_removidas": sum(len(i.get("frases_removidas", [])) for i in avaliadas),
        "frases_mantidas": sum(i["frases"] for i in avaliadas if i["citacoes_validas"]),
        "respostas_com_frase_removida": sum(1 for i in avaliadas if i.get("frases_removidas")),
        "rotulos_corrigidos": sum(len(i.get("rotulos_corrigidos", [])) for i in avaliadas),
        "segundos_mediana": sorted(i["segundos"] for i in itens)[len(itens) // 2] if itens else None,
    }
    saida = {"criterios": str(DIR / "criterios.md"), "resumo": resumo, "itens": itens}
    DIR.mkdir(parents=True, exist_ok=True)
    _resultado_path(split, rotulo).write_text(json.dumps(saida, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(resumo, indent=2, ensure_ascii=False))
    return saida


def frases_elegiveis(itens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Frases do LLM, de respostas que passaram na checagem, que citam ao menos um Trecho."""
    frases = []
    for item in itens:
        if not item.get("citacoes_validas"):
            continue
        trechos = {t["marcador"]: t for t in item["trechos"]}
        for campo in CAMPOS_DO_LLM:
            for frase in dividir_frases(str(item["texto_llm"].get(campo) or "")):
                citados = [m for m in MARCADOR.findall(frase) if eh_trecho(m)]
                if frase == FRASE_SEM_BASE or not citados:
                    continue
                frases.append({
                    "caso": item["id"], "split": item["split"], "pergunta": item["pergunta"], "campo": campo,
                    "frase": frase, "trechos_citados": [trechos[m] for m in dict.fromkeys(citados) if m in trechos],
                })
    return frases


def sortear(frases: List[Dict[str, Any]], n: int = TAMANHO_AMOSTRA, semente: int = SEMENTE) -> List[Dict[str, Any]]:
    rng = random.Random(semente)
    por_caso: Dict[str, List[Dict[str, Any]]] = {}
    for f in frases:
        por_caso.setdefault(f["caso"], []).append(f)
    candidatas = []
    for caso in sorted(por_caso):
        grupo = list(por_caso[caso])
        rng.shuffle(grupo)
        candidatas.extend(grupo[:MAX_POR_RESPOSTA])
    rng.shuffle(candidatas)
    return candidatas[:n]


def amostra(splits: List[str], prefixo: str = "amostra", rotulo: str = "") -> List[Dict[str, Any]]:
    itens = []
    for s in splits:
        caminho = _resultado_path(s, rotulo)
        if caminho.exists():
            itens.extend(json.loads(caminho.read_text(encoding="utf-8"))["itens"])
    escolhidas = sortear(frases_elegiveis(itens))
    for i, f in enumerate(escolhidas, 1):
        f["id"] = f"F{i:03d}"
    (DIR / f"{prefixo}.json").write_text(json.dumps(escolhidas, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (DIR / f"{prefixo}_para_avaliar.csv").open("w", encoding="utf-8", newline="") as arq:
        w = csv.writer(arq)
        w.writerow(["id", "pergunta", "frase", "trechos_citados", "julgamento", "comentario"])
        for f in escolhidas:
            trechos = "\n\n".join(f"[{t['marcador']}] {t['fonte']}, p. {t['pagina_pdf']}: {t['texto']}"
                                  for t in f["trechos_citados"])
            w.writerow([f["id"], f["pergunta"], f["frase"], trechos, "", ""])
    print(f"{len(escolhidas)} frases sorteadas de {len({f['caso'] for f in escolhidas})} respostas "
          f"-> {DIR / (prefixo + '_para_avaliar.csv')}")
    return escolhidas


def wilson(sucessos: int, n: int, z: float = 1.96) -> List[float]:
    if n == 0:
        return [0.0, 0.0]
    p = sucessos / n
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    margem = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(centro - margem, 4), round(centro + margem, 4)]


def calcular(caminho: Path) -> Dict[str, Any]:
    with caminho.open(encoding="utf-8", newline="") as arq:
        linhas = list(csv.DictReader(arq))
    julgadas = [linha for linha in linhas if linha["julgamento"].strip()]
    invalidos = [linha["id"] for linha in julgadas if linha["julgamento"].strip() not in JULGAMENTOS]
    if invalidos:
        raise SystemExit(f"Julgamento fora da rubrica ({', '.join(JULGAMENTOS)}): {', '.join(invalidos)}")
    contagem = Counter(linha["julgamento"].strip() for linha in julgadas)
    n = len(julgadas)
    sustentadas = contagem["sustentada"]
    resultado = {
        "frases_na_amostra": len(linhas), "frases_julgadas": n, "contagem": dict(contagem),
        "fidelidade": round(sustentadas / n, 4) if n else None,
        "ic95_wilson": wilson(sustentadas, n),
        "meta_rnf27": 0.95,
        "atinge_meta": (sustentadas / n >= 0.95) if n else None,
    }
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    return resultado


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Citações por frase e fundamentação (issue #12).")
    sub = parser.add_subparsers(dest="comando", required=True)
    m = sub.add_parser("medir")
    m.add_argument("--split", choices=["dev", "test", "todos"], default="dev")
    m.add_argument("--rotulo", default="", help="sufixo dos arquivos de resultado (ex.: gemma4_e4b)")
    a = sub.add_parser("amostra")
    a.add_argument("--splits", nargs="+", default=["dev", "test"])
    a.add_argument("--prefixo", default="amostra", help="nome dos arquivos (ex.: amostra_v4)")
    a.add_argument("--rotulo", default="", help="lê os resultados com esse sufixo")
    c = sub.add_parser("calcular")
    c.add_argument("--planilha", type=Path, default=DIR / "amostra_para_avaliar.csv")
    args = parser.parse_args(argv)
    if args.comando == "medir":
        medir(args.split, args.rotulo)
    elif args.comando == "amostra":
        amostra(args.splits, args.prefixo, args.rotulo)
    else:
        calcular(args.planilha)


if __name__ == "__main__":
    main()
