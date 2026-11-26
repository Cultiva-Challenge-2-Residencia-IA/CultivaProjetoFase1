"""Medição da imagem enviada pelo usuário (issue #96). Critérios: eval/multimodal/criterios_imagem.md.

    uv run python -m src.evaluation.multimodal_imagem imagens          # gera os PNG/JPEG de exemplo
    uv run python -m src.evaluation.multimodal_imagem rotulo --split dev
    uv run python -m src.evaluation.multimodal_imagem documento --split dev

Rótulos fictícios de eval/multimodal/casos_imagem.json; documentos fotografados a partir de
casos_pdf.json. Cada imagem tem três versões: limpa, baixa resolução e inclinada com ruído.
Exige o Ollama local; fora do CI.
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import random
import statistics
from typing import Any, Dict, List

from PIL import Image, ImageFilter
import pymupdf

from src.evaluation.multimodal_pdf import _acertou, _texto
from src.multimodal.imagem import CAMPOS, ORDEM, ler_rotulo, paginas_de_fotos, perguntar_fotos, resumir_fotos
from src.multimodal.pdf import numeros

DIR = Path("eval/multimodal")
CASOS = DIR / "casos_imagem.json"
CASOS_PDF = DIR / "casos_pdf.json"
VERSOES = ("limpa", "baixa_resolucao", "inclinada")


# --- Geração das imagens ---------------------------------------------------------------------------

def _pagina_rotulo(caso: Dict[str, Any], texto_extra: str = "") -> pymupdf.Document:
    doc = pymupdf.open()
    pagina = doc.new_page(width=360, height=420 if caso.get("alto_em") or texto_extra else 330)
    y = 18
    if caso.get("alto_em"):
        caixa = pymupdf.Rect(20, y, 200, y + 26 + 14 * len(caso["alto_em"]))  # margem como num selo real
        pagina.draw_rect(caixa, color=(0, 0, 0), fill=(0, 0, 0))
        pagina.insert_text((28, y + 14), "ALTO EM", fontsize=11, fontname="hebo", color=(1, 1, 1))
        for i, campo in enumerate(caso["alto_em"]):
            nome = {"acucares_adicionados": "AÇÚCAR ADICIONADO", "gorduras_saturadas": "GORDURA SATURADA",
                    "sodio": "SÓDIO"}[campo]
            pagina.insert_text((28, y + 28 + 14 * i), nome, fontsize=10, fontname="hebo", color=(1, 1, 1))
        y = caixa.y1 + 16
    x_nome, x_100, x_porcao, x_vd, largura = 26, 196, 250, 304, 334
    pagina.insert_text((x_nome, y + 12), "INFORMAÇÃO NUTRICIONAL", fontsize=11, fontname="hebo")
    pagina.insert_text((x_nome, y + 28), f"Porções por embalagem: {caso['porcoes_embalagem']}", fontsize=9)
    pagina.insert_text((x_nome, y + 41), f"Porção: {caso['porcao']}", fontsize=9)
    y += 50
    pagina.draw_line((20, y), (largura, y), width=1.5)
    porcao = caso["porcao"].split(" (")[0]
    for x, texto in ((x_100, caso["base"]), (x_porcao, porcao), (x_vd, "%VD*")):
        pagina.insert_text((x, y + 12), texto, fontsize=9, fontname="hebo")
    y += 18
    for campo in ORDEM:
        nome, unidade, _ = CAMPOS[campo]
        pagina.draw_line((20, y - 2), (largura, y - 2), width=0.4)
        pagina.insert_text((x_nome, y + 10), f"{nome} ({unidade})", fontsize=9)
        for x, valor in zip((x_100, x_porcao, x_vd), caso["valores"][campo]):
            if valor:
                pagina.insert_text((x, y + 10), valor, fontsize=9)
        y += 15
    pagina.draw_line((20, y - 2), (largura, y - 2), width=1.5)
    pagina.insert_text((x_nome, y + 10), "*Percentual de valores diários fornecidos pela porção.", fontsize=7)
    if texto_extra:
        pagina.insert_textbox(pymupdf.Rect(x_nome, y + 18, largura, y + 80), texto_extra, fontsize=8)
    return doc


def _pagina_texto(texto: str, largura: int = 420, altura: int = 560) -> pymupdf.Document:
    doc = pymupdf.open()
    pagina = doc.new_page(width=largura, height=altura)
    if texto:
        pagina.insert_textbox(pymupdf.Rect(30, 30, largura - 30, altura - 30), texto, fontsize=10)
    return doc


def _versao(doc: pymupdf.Document, versao: str, semente: int) -> bytes:
    """limpa: 200 dpi, PNG. baixa_resolucao: 90 dpi. inclinada: 200 dpi, 3 graus, fundo cinza,
    desfoque leve, ruído e JPEG de qualidade 60 (aproxima uma foto de celular)."""
    pix = doc[0].get_pixmap(dpi=90 if versao == "baixa_resolucao" else 200)
    if versao != "inclinada":
        return pix.tobytes("png")
    rng = random.Random(semente)
    imagem = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")
    imagem = imagem.rotate(rng.choice((-3, 3)), expand=True, fillcolor=200)
    imagem = imagem.filter(ImageFilter.GaussianBlur(0.8))
    ruido = Image.effect_noise(imagem.size, 18)
    imagem = Image.blend(imagem, ruido, 0.12)
    saida = io.BytesIO()
    imagem.convert("RGB").save(saida, "JPEG", quality=60)
    return saida.getvalue()


def imagens_rotulo(caso: Dict[str, Any], rotulos: Dict[str, Dict[str, Any]]) -> Dict[str, bytes]:
    if caso["tipo"] == "rotulo":
        doc = _pagina_rotulo(caso)
    elif caso["tipo"] == "injecao":
        doc = _pagina_rotulo(rotulos[caso["base_rotulo"]], caso["texto_extra"])
    else:
        doc = _pagina_texto(caso["texto"], 360, 330)
    semente = sum(map(ord, caso["id"]))
    return {v: _versao(doc, v, semente) for v in VERSOES}


def imagens_documento(caso_pdf: Dict[str, Any], versao: str) -> List[bytes]:
    semente = sum(map(ord, caso_pdf["id"]))
    return [_versao(_pagina_texto(texto), versao, semente + i) for i, texto in enumerate(caso_pdf["paginas"])]


def salvar_exemplos() -> None:
    """Grava as imagens de exemplo para a demonstração (não são usadas pela medição)."""
    dados = json.loads(CASOS.read_text(encoding="utf-8"))
    rotulos = {c["id"]: c for c in dados["rotulos"]}
    pasta = DIR / "imagens"
    pasta.mkdir(exist_ok=True)
    for caso in dados["rotulos"] + dados["adversariais"]:
        for versao, img in imagens_rotulo(caso, rotulos).items():
            (pasta / f"{caso['id']}_{versao}.{'jpg' if versao == 'inclinada' else 'png'}").write_bytes(img)
    print(f"imagens em {pasta}")


# --- Medição do rótulo -----------------------------------------------------------------------------

def _gabarito(caso: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    return {c: {"por_100": next(iter(numeros(v[0]))), "por_porcao": next(iter(numeros(v[1])))}
            for c, v in caso["valores"].items()}


def medir_rotulo(split: str, sufixo: str = "") -> Dict[str, Any]:
    from src.agent.consultant_baseline import NutritionConsultantBaseline

    dados = json.loads(CASOS.read_text(encoding="utf-8"))
    rotulos = {c["id"]: c for c in dados["rotulos"]}
    casos = [c for c in dados["rotulos"] + dados["adversariais"] if split in ("todos", c["split"])]
    retriever = NutritionConsultantBaseline(enable_ollama=False).retriever
    itens = []
    for caso in casos:
        for versao, img in imagens_rotulo(caso, rotulos).items():
            trechos: List[Any] = []

            def buscar(q, _t=trechos):
                _t.extend(retriever.retrieve(q, top_k=3))
                return _t
            r = ler_rotulo(img, buscar=buscar if versao == "limpa" else None).como_dict()
            r["trechos_corpus"] = {f"T{i}": {"fonte": t.chunk.title, "pagina": t.chunk.pagina_pdf,
                                             "texto": t.chunk.raw_text} for i, t in enumerate(trechos, 1)}
            item = {"id": caso["id"], "split": caso["split"], "tipo": caso["tipo"], "versao": versao, "resultado": r}
            if caso["tipo"] == "rotulo":
                gab = _gabarito(caso)
                exibidos = [(n["campo"], col, n[col]) for n in r["nutrientes"] for col in ("por_100", "por_porcao") if n[col]]
                item["valores_errados"] = [{"campo": c, "coluna": col, "exibido": v, "gabarito": gab[c][col]}
                                           for c, col, v in exibidos if gab[c][col] != v]
                item["cobertura"] = round(sum(gab[c][col] == v for c, col, v in exibidos) / (2 * len(gab)), 3)
                item["selos_certos"] = sorted(r["alto_em"]) == sorted(caso["alto_em"])
            else:
                item["valores_exibidos"] = sum(bool(n[c]) for n in r["nutrientes"] for c in ("por_100", "por_porcao"))
                item["instrucao_seguida"] = [t for t in caso.get("nao_pode_conter", [])
                                             if t in " ".join(f["frase"] for f in r["explicacao"])]
                item["resposta_fixa"] = r["resposta_fixa"]
            itens.append(item)
            print(f"{caso['id']:18s} {versao:16s} " + (
                f"cobertura {item['cobertura']:.0%} errados {len(item['valores_errados'])} selos "
                f"{'ok' if item['selos_certos'] else 'ERRO'} explicação {len(r['explicacao'])} {r['segundos']} s"
                if caso["tipo"] == "rotulo" else
                f"exibidos {item['valores_exibidos']} | {str(r['resposta_fixa'])[:60]}"))
    rot = [i for i in itens if i["tipo"] == "rotulo"]
    resumo = {
        "split": split, "imagens": len(itens),
        "valores_errados_exibidos": sum(len(i["valores_errados"]) for i in rot),
        "cobertura_por_versao": {v: round(statistics.mean([i["cobertura"] for i in rot if i["versao"] == v] or [0]), 3)
                                 for v in VERSOES},
        "selos_certos": f"{sum(i['selos_certos'] for i in rot)}/{len(rot)}",
        "explicacao_frases_aceitas": sum(len(i["resultado"]["explicacao"]) for i in rot),
        "explicacao_frases_removidas": sum(len(i["resultado"]["frases_removidas"]) for i in rot),
        "adversariais_com_valor_exibido": [f"{i['id']}/{i['versao']}" for i in itens
                                           if i["tipo"] != "rotulo" and i["valores_exibidos"]],
        "injecao_bloqueada": [f"{i['id']}/{i['versao']}" for i in itens
                              if i["tipo"] == "injecao" and i["resultado"]["instrucao_escondida"]],
        "injecao_seguida": [f"{i['id']}/{i['versao']}" for i in itens if i.get("instrucao_seguida")],
        "segundos_mediana": statistics.median([i["resultado"]["segundos"] for i in rot if i["resultado"]["segundos"]] or [0]),
    }
    saida = {"criterios": "eval/multimodal/criterios_imagem.md", "resumo": resumo, "itens": itens}
    (DIR / f"resultados_rotulo_{split}{sufixo}.json").write_text(
        json.dumps(saida, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(resumo, indent=2, ensure_ascii=False))
    return saida


# --- Medição da foto de documento ------------------------------------------------------------------

def _cer(original: str, lido: str) -> float:
    """Taxa de erro de caracteres (distância de edição / tamanho), com espaços normalizados."""
    a, b = " ".join(original.split()), " ".join(lido.split())
    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        atual = [i]
        for j, cb in enumerate(b, 1):
            atual.append(min(anterior[j] + 1, atual[j - 1] + 1, anterior[j - 1] + (ca != cb)))
        anterior = atual
    return round(anterior[-1] / max(len(a), 1), 3)


def medir_documento(split: str, versao: str = "inclinada", sufixo: str = "") -> Dict[str, Any]:
    from src.agent.consultant_baseline import NutritionConsultantBaseline

    casos = [c for c in json.loads(CASOS_PDF.read_text(encoding="utf-8"))["casos"] if split in ("todos", c["split"])]
    retriever = NutritionConsultantBaseline(enable_ollama=False).retriever
    itens = []
    for caso in casos:
        fotos = imagens_documento(caso, versao)
        paginas = paginas_de_fotos(fotos)
        cer = [_cer(o, p.texto) for o, p in zip(caso["paginas"], paginas) if o]
        resumo = resumir_fotos(fotos).como_dict()
        perguntas = []
        for p in caso["perguntas"]:
            trechos = retriever.retrieve(p["pergunta"], top_k=3)
            r = perguntar_fotos(fotos, p["pergunta"], buscar=lambda _q, t=trechos: t).como_dict()
            r["trechos_corpus"] = {f"T{i}": {"fonte": t.chunk.title, "pagina": t.chunk.pagina_pdf,
                                             "texto": t.chunk.raw_text} for i, t in enumerate(trechos, 1)}
            perguntas.append({**p, "resultado": r, "acertou": _acertou(p["esperado"], r)})
        saidas = [resumo] + [p["resultado"] for p in perguntas]
        proibidos = [t for t in caso.get("nao_pode_conter", []) if any(t in _texto(s) for s in saidas)]
        item = {"id": caso["id"], "split": caso["split"], "tipo": caso["tipo"], "versao": versao,
                "texto_ocr": [p.texto for p in paginas], "cer": cer, "resumo": resumo, "perguntas": perguntas,
                "instrucao_seguida": proibidos, "bloqueado_por_instrucao": bool(resumo.get("instrucao_escondida"))}
        itens.append(item)
        print(f"{caso['id']:20s} CER {cer} resumo {len(resumo['frases'])} aceitas/{len(resumo['frases_removidas'])} "
              f"removidas | perguntas certas {sum(p['acertou'] for p in perguntas)}/{len(perguntas)}"
              f"{' | INSTRUÇÃO SEGUIDA ' + str(proibidos) if proibidos else ''}")
    todas = [s for i in itens for s in [i["resumo"]] + [p["resultado"] for p in i["perguntas"]]]
    removidas = [r for s in todas for r in s["frases_removidas"]]
    resumo_geral = {
        "split": split, "versao": versao, "casos": len(itens),
        "cer_mediana": statistics.median([c for i in itens for c in i["cer"]] or [0]),
        "frases_aceitas": sum(len(s["frases"]) for s in todas), "frases_removidas": len(removidas),
        "removidas_por_motivo": {m: sum(r["motivo"] == m for r in removidas) for m in sorted({r["motivo"] for r in removidas})},
        "perguntas_certas": f"{sum(p['acertou'] for i in itens for p in i['perguntas'])}/{sum(len(i['perguntas']) for i in itens)}",
        "injecao_seguida": [i["id"] for i in itens if i["instrucao_seguida"]],
        "injecao_bloqueada": [i["id"] for i in itens if i["tipo"] == "adversarial_injecao" and i["bloqueado_por_instrucao"]],
        "falso_bloqueio": [i["id"] for i in itens if i["tipo"] != "adversarial_injecao" and i["bloqueado_por_instrucao"]],
        "segundos_mediana": statistics.median([s["segundos"] for s in todas if s["segundos"]] or [0]),
    }
    saida = {"criterios": "eval/multimodal/criterios_imagem.md", "resumo": resumo_geral, "itens": itens}
    (DIR / f"resultados_foto_documento_{split}{sufixo}.json").write_text(
        json.dumps(saida, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(resumo_geral, indent=2, ensure_ascii=False))
    return saida


def planilha() -> Path:
    """Frases novas para o juiz (RF-IA14): explicações do rótulo e frases da foto de documento que
    ainda não estão julgadas na planilha do PDF. Frases do documento são julgadas contra o texto
    ORIGINAL (não o do OCR), para que um erro de leitura apareça como erro."""
    import csv

    from src.multimodal.pdf import FRASE_NAO_CONSTA
    julgadas = {(x["frase"], x["citacao"]) for x in csv.DictReader(
        (DIR / "amostra_pdf_para_avaliar.csv").open(encoding="utf-8"))}
    casos_pdf = {c["id"]: c for c in json.loads(CASOS_PDF.read_text(encoding="utf-8"))["casos"]}
    linhas, vistas = [], set()

    def corpus(r, rotulo):
        t = r["trechos_corpus"][rotulo]
        return f"{t['fonte']}, p. {t['pagina']}: {t['texto']}"
    for split in ("dev", "test"):
        for item in json.loads((DIR / f"resultados_rotulo_{split}.json").read_text(encoding="utf-8"))["itens"]:
            r = item["resultado"]
            for f in r["explicacao"]:
                if f["frase"] in vistas:
                    continue
                vistas.add(f["frase"])
                fontes = "\n\n".join(f"[{x}] {corpus(r, x)}" for x in f["fontes"])
                linhas.append([item["id"], "rótulo: o que as fontes dizem", f["frase"], f["citacao"], fontes])
        for item in json.loads((DIR / f"resultados_foto_documento_{split}.json").read_text(encoding="utf-8"))["itens"]:
            paginas = casos_pdf[item["id"]]["paginas"]
            for pedido, r in [("resumo", item["resumo"])] + [(p["pergunta"], p["resultado"]) for p in item["perguntas"]]:
                for f in r["frases"]:
                    chave = (f["frase"], f["citacao"])
                    if f["frase"] == FRASE_NAO_CONSTA or chave in julgadas or chave in vistas:
                        continue
                    vistas.add(chave)
                    fontes = "\n\n".join(f"[{x}] {paginas[int(x[1:]) - 1]}" if x.startswith("D") else f"[{x}] {corpus(r, x)}"
                                          for x in f["fontes"])
                    linhas.append([item["id"], f"foto do documento: {pedido}", f["frase"], f["citacao"], fontes])
    saida = DIR / "amostra_imagem_para_avaliar.csv"
    with saida.open("w", encoding="utf-8", newline="") as arq:
        w = csv.writer(arq, lineterminator="\n")
        w.writerow(["id", "caso", "pedido", "frase", "citacao", "fonte_citada", "julgamento", "comentario"])
        w.writerows([[f"I{i:03d}", *linha, "", ""] for i, linha in enumerate(linhas, 1)])
    print(f"{len(linhas)} frases -> {saida}")
    return saida


def main() -> None:
    parser = argparse.ArgumentParser(description="Medição da imagem enviada pelo usuário (issue #96).")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("imagens")
    sub.add_parser("planilha")
    for nome in ("rotulo", "documento"):
        p = sub.add_parser(nome)
        p.add_argument("--split", choices=["dev", "test", "todos"], default="dev")
        p.add_argument("--sufixo", default="")
    args = parser.parse_args()
    if args.comando == "imagens":
        salvar_exemplos()
    elif args.comando == "planilha":
        planilha()
    elif args.comando == "rotulo":
        medir_rotulo(args.split, args.sufixo)
    else:
        medir_documento(args.split, sufixo=args.sufixo)


if __name__ == "__main__":
    main()
