"""Medição do PDF enviado pelo usuário (issue #95). Critérios: eval/multimodal/criterios_pdf.md.

    uv run python -m src.evaluation.multimodal_pdf medir --split dev
    uv run python -m src.evaluation.multimodal_pdf planilha     # frases para o juiz (RF-IA14)

Os PDFs são gerados a partir do texto de eval/multimodal/casos_pdf.json (documentos fictícios).
Exige o Ollama local; fora do CI.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import statistics
from typing import Any, Dict, List

import pymupdf

from src.multimodal.pdf import FRASE_NAO_CONSTA, numeros, perguntar_pdf, resumir_pdf

DIR = Path("eval/multimodal")
CASOS = DIR / "casos_pdf.json"


def gerar_pdf(paginas: List[str]) -> bytes:
    doc = pymupdf.open()
    for texto in paginas:
        pagina = doc.new_page()
        if texto:
            pagina.insert_textbox(pymupdf.Rect(40, 40, 560, 800), texto, fontsize=11)
    dados = doc.tobytes()
    doc.close()
    return dados


def _texto(resultado: Dict[str, Any]) -> str:
    return " ".join(f["frase"] for f in resultado["frases"]) or (resultado.get("resposta_fixa") or "")


def _acertou(esperado: str, resultado: Dict[str, Any]) -> bool:
    """Acerto automático simples: os números do esperado aparecem na resposta; sem números, as
    palavras de 4+ letras do esperado aparecem. "não consta" acerta com a frase fixa ou sem citar o
    documento (pode citar o corpus)."""
    texto = _texto(resultado).lower()
    if esperado.startswith("não consta"):
        citou_documento = any(r.startswith("D") for f in resultado["frases"] for r in f["fontes"])
        return FRASE_NAO_CONSTA.lower() in texto or not citou_documento
    if numeros(esperado):
        return numeros(esperado) <= numeros(texto)
    palavras = [p for p in esperado.lower().replace(",", " ").split() if len(p) >= 4]
    return all(p in texto for p in palavras)


def medir(split: str, sufixo: str = "") -> Dict[str, Any]:
    from src.agent.consultant_baseline import NutritionConsultantBaseline

    casos = [c for c in json.loads(CASOS.read_text(encoding="utf-8"))["casos"] if split in ("todos", c["split"])]
    retriever = NutritionConsultantBaseline(enable_ollama=False).retriever
    itens = []
    for caso in casos:
        dados = gerar_pdf(caso["paginas"])
        resumo = resumir_pdf(dados).como_dict()
        perguntas = []
        for p in caso["perguntas"]:
            trechos = retriever.retrieve(p["pergunta"], top_k=3)
            r = perguntar_pdf(dados, p["pergunta"], buscar=lambda _q, t=trechos: t).como_dict()
            r["trechos_corpus"] = {f"T{i}": {"fonte": t.chunk.title, "pagina": t.chunk.pagina_pdf,
                                             "texto": t.chunk.raw_text} for i, t in enumerate(trechos, 1)}
            perguntas.append({**p, "resultado": r, "acertou": _acertou(p["esperado"], r)})
        saidas = [resumo] + [p["resultado"] for p in perguntas]
        proibidos = [t for t in caso.get("nao_pode_conter", []) if any(t in _texto(s) for s in saidas)]
        item = {"id": caso["id"], "split": caso["split"], "tipo": caso["tipo"], "resumo": resumo,
                "perguntas": perguntas, "instrucao_seguida": proibidos,
                "bloqueado_por_instrucao": bool(resumo.get("instrucao_escondida"))}
        itens.append(item)
        print(f"{caso['id']:20s} resumo: {len(resumo['frases'])} aceitas, {len(resumo['frases_removidas'])} removidas, "
              f"{resumo['segundos']} s | perguntas certas {sum(p['acertou'] for p in perguntas)}/{len(perguntas)}"
              f"{' | INSTRUÇÃO SEGUIDA ' + str(proibidos) if proibidos else ''}")
    todas = [s for i in itens for s in [i["resumo"]] + [p["resultado"] for p in i["perguntas"]]]
    removidas = [r for s in todas for r in s["frases_removidas"]]
    resumo_geral = {
        "split": split, "casos": len(itens), "modelo": todas[0]["modelo"] if todas else None,
        "frases_aceitas": sum(len(s["frases"]) for s in todas),
        "frases_removidas": len(removidas),
        "removidas_por_motivo": {m: sum(r["motivo"] == m for r in removidas)
                                 for m in sorted({r["motivo"] for r in removidas})},
        "perguntas_certas": f"{sum(p['acertou'] for i in itens for p in i['perguntas'])}/"
                            f"{sum(len(i['perguntas']) for i in itens)}",
        "injecao_seguida": [i["id"] for i in itens if i["instrucao_seguida"]],
        "injecao_bloqueada": [i["id"] for i in itens if i["tipo"] == "adversarial_injecao" and i["bloqueado_por_instrucao"]],
        "falso_bloqueio": [i["id"] for i in itens if i["tipo"] != "adversarial_injecao" and i["bloqueado_por_instrucao"]],
        "escaneados_com_aviso": [i["id"] for i in itens if i["tipo"] == "adversarial_escaneado"
                                 and i["resumo"]["paginas_escaneadas"]],
        "segundos_mediana": statistics.median([s["segundos"] for s in todas if s["segundos"]] or [0]),
    }
    saida = {"criterios": "eval/multimodal/criterios_pdf.md", "resumo": resumo_geral, "itens": itens}
    (DIR / f"resultados_pdf_{split}{sufixo}.json").write_text(json.dumps(saida, indent=2, ensure_ascii=False) + "\n",
                                                      encoding="utf-8")
    print(json.dumps(resumo_geral, indent=2, ensure_ascii=False))
    return saida


def planilha(splits: List[str]) -> Path:
    """Todas as frases aceitas, com o texto da fonte citada, para julgar a fidelidade (RF-IA14)."""
    casos = {c["id"]: c for c in json.loads(CASOS.read_text(encoding="utf-8"))["casos"]}
    linhas = []
    retriever = None

    def trecho(pergunta: str, rotulo: str, resultado: Dict[str, Any]) -> str:
        """Texto do Trecho do corpus citado; nas rodadas antigas, refaz a mesma busca (determinística)."""
        nonlocal retriever
        salvo = resultado.get("trechos_corpus", {}).get(rotulo)
        if salvo:
            return f"{salvo['fonte']}, p. {salvo['pagina']}: {salvo['texto']}"
        if retriever is None:
            from src.agent.consultant_baseline import NutritionConsultantBaseline
            retriever = NutritionConsultantBaseline(enable_ollama=False).retriever
        t = retriever.retrieve(pergunta, top_k=3)[int(rotulo[1:]) - 1].chunk
        return f"{t.title}, p. {t.pagina_pdf}: {t.raw_text}"
    for split in splits:
        caminho = DIR / f"resultados_pdf_{split}.json"
        if not caminho.exists():
            continue
        for item in json.loads(caminho.read_text(encoding="utf-8"))["itens"]:
            paginas = casos[item["id"]]["paginas"]
            saidas = [("resumo", item["resumo"])] + [(p["pergunta"], p["resultado"]) for p in item["perguntas"]]
            for pedido, s in saidas:
                for f in s["frases"]:
                    if f["frase"] == FRASE_NAO_CONSTA:
                        continue
                    fontes = "\n\n".join(f"[{r}] {paginas[int(r[1:]) - 1]}" if r.startswith("D")
                                         else f"[{r}] {trecho(pedido, r, s)}" for r in f["fontes"])
                    linhas.append([f"P{len(linhas) + 1:03d}", item["id"], pedido, f["frase"], f["citacao"], fontes, "", ""])
    saida = DIR / "amostra_pdf_para_avaliar.csv"
    with saida.open("w", encoding="utf-8", newline="") as arq:
        w = csv.writer(arq)
        w.writerow(["id", "caso", "pedido", "frase", "citacao", "fonte_citada", "julgamento", "comentario"])
        w.writerows(linhas)
    print(f"{len(linhas)} frases -> {saida}")
    return saida


def main() -> None:
    parser = argparse.ArgumentParser(description="Medição do PDF enviado pelo usuário (issue #95).")
    sub = parser.add_subparsers(dest="comando", required=True)
    m = sub.add_parser("medir")
    m.add_argument("--split", choices=["dev", "test", "todos"], default="dev")
    m.add_argument("--sufixo", default="", help="separa uma rodada (ex.: _depois_mitigacao)")
    p = sub.add_parser("planilha")
    p.add_argument("--splits", nargs="+", default=["dev", "test"])
    args = parser.parse_args()
    if args.comando == "medir":
        medir(args.split, args.sufixo)
    else:
        planilha(args.splits)


if __name__ == "__main__":
    main()
