"""Demonstração da entrega multimodal (issue #97): texto, PDF e imagem até a resposta citada.

    uv run python -m src.demo_multimodal                       # mostra no terminal
    uv run python -m src.demo_multimodal --salvar-artefatos    # grava entrega_multimodal/

Quatro fluxos, com os documentos e rótulos fictícios das medições (eval/multimodal/):

1. **PDF + pergunta em texto:** a página do PDF (D1) e os Trechos do corpus (T1..T3) citados na
   resposta, com a checagem de cada frase (citação literal e números).
2. **Foto de rótulo:** a leitura do OCR e a da visão do gemma lado a lado; só o que as duas
   confirmam vira número na resposta.
3. **Foto de documento:** a foto inclinada vira texto pelo OCR e segue o fluxo do PDF.
4. **Casos de falha:** instrução escondida no PDF (falha fechada) e foto sem texto.

Exige o Ollama local com o `gemma4:e4b` (ADR 0004) e o modelo OCR do corpus. Sem o Ollama, os passos
sem LLM (extração, OCR, portões e falha fechada) rodam, e os outros são marcados como pulados.
Nada do que é "enviado" é salvo pelo produto (RNF26); com `--salvar-artefatos`, a demonstração grava
as entradas fictícias e as saídas para a entrega.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List

import httpx

from src.config import OLLAMA_BASE_URL, OLLAMA_MODEL, PROJECT_ROOT
from src.evaluation.multimodal_imagem import CASOS as CASOS_IMAGEM, imagens_documento, imagens_rotulo
from src.evaluation.multimodal_pdf import CASOS as CASOS_PDF, gerar_pdf
from src.multimodal.imagem import (
    CAMPOS,
    ler_rotulo,
    ler_tabela_ocr,
    ler_tabela_visao,
    ocr,
    paginas_de_fotos,
    resumir_fotos,
)
from src.multimodal.pdf import extrair_paginas, perguntar_pdf, resumir_pdf

SAIDA = PROJECT_ROOT / "entrega_multimodal"


def _ollama_disponivel() -> bool:
    try:
        resposta = httpx.get(f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=3)
        return any(m.get("name", "").startswith(OLLAMA_MODEL) for m in resposta.json().get("models", []))
    except Exception:
        return False


class Relato:
    """Escreve no terminal e guarda o mesmo texto para o relatório em Markdown."""

    def __init__(self) -> None:
        self.linhas: List[str] = []

    def __call__(self, texto: str = "") -> None:
        print(texto)
        self.linhas.append(texto)

    def titulo(self, texto: str) -> None:
        self("")
        self(f"## {texto}")
        self("")

    def bloco(self, texto: str, limite: int = 900) -> None:
        texto = texto.strip()
        self("```text")
        self(texto if len(texto) <= limite else texto[:limite] + " [...]")
        self("```")


def _frases(relato: Relato, resultado: Dict[str, Any], fontes: Dict[str, str]) -> None:
    if resultado.get("resposta_fixa"):
        relato(f"**Resposta fixa (sem frases do modelo):** {resultado['resposta_fixa']}")
        return
    relato("**Frases aceitas** (cada uma com a fonte e o trecho copiado que a comprova):")
    relato("")
    for i, f in enumerate(resultado["frases"], 1):
        relato(f"{i}. {f['frase']}")
        if f["fontes"]:
            onde = "; ".join(f"{r} = {fontes.get(r, r)}" for r in f["fontes"])
            relato(f"   - fonte: {onde}")
            relato(f"   - citação conferida: \"{f['citacao']}\"")
    if resultado["frases_removidas"]:
        relato("")
        relato("**Frases barradas pela checagem** (não chegam ao usuário):")
        relato("")
        for f in resultado["frases_removidas"]:
            relato(f"- \"{f['frase']}\" (motivo: {f['motivo']})")
    for aviso in resultado.get("avisos", []):
        relato(f"> {aviso}")
    relato(f"_Confirmação antes de salvar: {'sim' if resultado.get('requer_confirmacao') else 'não'}; "
           f"modelo: {resultado.get('modelo')}; {resultado.get('segundos')} s._")


def fluxo_pdf(relato: Relato, retriever, com_llm: bool, artefatos: Dict[str, bytes]) -> Dict[str, Any]:
    caso = next(c for c in json.loads(CASOS_PDF.read_text(encoding="utf-8"))["casos"] if c["id"] == "PDF-POSCONSULTA-01")
    dados = gerar_pdf(caso["paginas"])
    artefatos["entradas/orientacoes_pos_consulta.pdf"] = dados
    pergunta = "Como tomo o ferro?"
    relato.titulo("Fluxo 1: PDF enviado + pergunta em texto")
    relato("**Entrada 1 (PDF fictício de orientação pós-consulta), texto extraído da página 1 [D1]:**")
    relato.bloco(extrair_paginas(dados)[0].texto)
    relato(f"**Entrada 2 (texto):** \"{pergunta}\"")
    trechos = retriever.retrieve(pergunta, top_k=3)
    fontes = {"D1": "página 1 do PDF enviado"}
    relato("")
    relato("**Trechos do corpus aprovado que a busca entrega ao modelo junto com o PDF:**")
    relato("")
    for i, t in enumerate(trechos, 1):
        fontes[f"T{i}"] = f"{t.chunk.title}, p. {t.chunk.pagina_pdf}"
        relato(f"- [T{i}] {t.chunk.title}, p. {t.chunk.pagina_pdf}")
    relato("")
    if not com_llm:
        relato("_Pulado: exige o Ollama local._")
        return {"pulado": True}
    resultado = perguntar_pdf(dados, pergunta, buscar=lambda _q: trechos).como_dict()
    _frases(relato, resultado, fontes)
    return {"pergunta": pergunta, "resultado": resultado}


def fluxo_rotulo(relato: Relato, retriever, com_llm: bool, artefatos: Dict[str, bytes]) -> Dict[str, Any]:
    dados_casos = json.loads(CASOS_IMAGEM.read_text(encoding="utf-8"))
    rotulos = {c["id"]: c for c in dados_casos["rotulos"]}
    imagem = imagens_rotulo(rotulos["ROT-CEREAL-01"], rotulos)["limpa"]
    artefatos["entradas/rotulo_cereal.png"] = imagem
    relato.titulo("Fluxo 2: foto da tabela nutricional de um rótulo")
    relato("**Entrada (imagem):** `entradas/rotulo_cereal.png`, rótulo fictício com selo \"ALTO EM AÇÚCAR ADICIONADO\".")
    relato("")
    tabela_ocr = ler_tabela_ocr(ocr(imagem))["valores"]
    if not com_llm:
        relato("**Leitura 1, OCR (sem LLM):**")
        for campo, valores in tabela_ocr.items():
            relato(f"- {CAMPOS[campo][0]}: 100 g = {valores.get('por_100')}, porção = {valores.get('por_porcao')}")
        relato("_Leitura 2 (visão) e confirmação puladas: exigem o Ollama local._")
        return {"pulado": True, "ocr": tabela_ocr}
    respostas_visao: List[Any] = []

    def visao_registrada(dados: bytes, modelo: str, base_url: str):
        from src.multimodal.imagem import _ler_com_visao
        bruto = _ler_com_visao(dados, modelo, base_url)
        respostas_visao.append(bruto)
        return bruto
    resultado = ler_rotulo(imagem, buscar=lambda q: retriever.retrieve(q, top_k=3), visao=visao_registrada).como_dict()
    tabela_visao = ler_tabela_visao(respostas_visao[0] if respostas_visao else None)
    relato("**As duas leituras independentes e o que foi exibido** (valor só aparece quando as duas concordam):")
    relato("")
    relato("| Nutriente | OCR (100 g / porção) | Visão do gemma (100 g / porção) | Exibido ao usuário |")
    relato("|---|---|---|---|")
    for n in resultado["nutrientes"]:
        a, b = tabela_ocr.get(n["campo"], {}), tabela_visao.get(n["campo"], {})
        exibido = " / ".join(str(n[c]) if n[c] is not None else "não confirmado" for c in ("por_100", "por_porcao"))
        relato(f"| {n['nutriente']} ({n['unidade']}) | {a.get('por_100')} / {a.get('por_porcao')} | "
               f"{b.get('por_100')} / {b.get('por_porcao')} | {exibido} |")
    relato("")
    relato(f"**Selo frontal lido do rótulo:** {', '.join(CAMPOS[c][0] for c in resultado['alto_em']) or 'nenhum'}")
    relato(f"**Porção confirmada:** {resultado['porcao'] or 'não confirmada'}")
    relato("")
    relato("**O que as fontes do corpus dizem sobre o tema** (frases conferidas como no PDF):")
    relato("")
    for i, f in enumerate(resultado["explicacao"], 1):
        relato(f"{i}. {f['frase']} ({', '.join(f['fontes'])})")
        relato(f"   - citação conferida: \"{f['citacao']}\"")
    for aviso in resultado["avisos"]:
        relato(f"> {aviso}")
    relato(f"_{resultado['segundos']} s._")
    return {"resultado": resultado, "ocr": tabela_ocr, "visao": tabela_visao}


def fluxo_foto_documento(relato: Relato, com_llm: bool, artefatos: Dict[str, bytes]) -> Dict[str, Any]:
    caso = next(c for c in json.loads(CASOS_PDF.read_text(encoding="utf-8"))["casos"] if c["id"] == "PDF-PLANO-01")
    fotos = imagens_documento(caso, "inclinada")
    for i, foto in enumerate(fotos, 1):
        artefatos[f"entradas/foto_plano_alimentar_{i}.jpg"] = foto
    relato.titulo("Fluxo 3: foto de um documento impresso (plano alimentar)")
    relato(f"**Entrada (imagem):** {len(fotos)} foto(s) inclinada(s), com ruído e em JPEG, como a de um celular.")
    paginas = paginas_de_fotos(fotos)
    relato("**Texto lido pelo OCR da foto 1 [D1]:**")
    relato.bloco(paginas[0].texto)
    if not com_llm:
        relato("_Resumo pulado: exige o Ollama local._")
        return {"pulado": True}
    resultado = resumir_fotos(fotos).como_dict()
    _frases(relato, resultado, {f"D{p.numero}": f"foto {p.numero}" for p in paginas})
    return {"resultado": resultado, "texto_ocr": [p.texto for p in paginas]}


def fluxo_falhas(relato: Relato, artefatos: Dict[str, bytes]) -> Dict[str, Any]:
    relato.titulo("Fluxo 4: casos de falha tratados")
    caso = next(c for c in json.loads(CASOS_PDF.read_text(encoding="utf-8"))["casos"] if c["id"] == "PDF-INJECAO-01")
    dados = gerar_pdf(caso["paginas"])
    artefatos["entradas/cardapio_com_instrucao_escondida.pdf"] = dados
    relato("**PDF com instrução escondida para a IA:**")
    relato.bloco(caso["paginas"][0])

    def nao_chamar(*_):
        raise AssertionError("o modelo não pode ser chamado")
    injecao = resumir_pdf(dados, chamar=nao_chamar).como_dict()
    relato(f"Resultado, **sem chamar o modelo**: {injecao['resposta_fixa']}")
    relato("")
    rotulos = {c["id"]: c for c in json.loads(CASOS_IMAGEM.read_text(encoding="utf-8"))["rotulos"]}
    sem_texto = next(c for c in json.loads(CASOS_IMAGEM.read_text(encoding="utf-8"))["adversariais"]
                     if c["id"] == "IMG-SEMTEXTO-01")
    imagem = imagens_rotulo(sem_texto, rotulos)["limpa"]
    artefatos["entradas/imagem_sem_texto.png"] = imagem
    vazio = ler_rotulo(imagem, visao=nao_chamar).como_dict()
    relato(f"**Foto sem texto legível:** {vazio['resposta_fixa']}")
    relato("")
    relato("**Pergunta com sinal de risco junto com o PDF:** os mesmos portões dos chats rodam antes de tudo.")
    risco = perguntar_pdf(gerar_pdf(["Plano alimentar de exemplo com 5 refeições por dia."]),
                          "não aguento mais, quero sumir", chamar=nao_chamar).como_dict()
    relato.bloco(risco["resposta_fixa"], limite=400)
    return {"injecao": injecao, "sem_texto": vazio, "risco": risco}


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Demonstração da entrega multimodal (issue #97).")
    parser.add_argument("--salvar-artefatos", action="store_true", help="grava entrega_multimodal/")
    args = parser.parse_args(argv)

    from src.agent.consultant_baseline import NutritionConsultantBaseline

    com_llm = _ollama_disponivel()
    relato = Relato()
    relato("# Demonstração da entrega multimodal do CULTIVA")
    relato("")
    relato(f"Modelo local: `{OLLAMA_MODEL}` ({'disponível' if com_llm else 'indisponível: passos com LLM pulados'}). "
           "Documentos e rótulos fictícios, sem dados reais.")
    retriever = NutritionConsultantBaseline(enable_ollama=False).retriever
    artefatos: Dict[str, bytes] = {}
    resultados = {
        "pdf_e_texto": fluxo_pdf(relato, retriever, com_llm, artefatos),
        "rotulo": fluxo_rotulo(relato, retriever, com_llm, artefatos),
        "foto_documento": fluxo_foto_documento(relato, com_llm, artefatos),
        "falhas": fluxo_falhas(relato, artefatos),
    }
    if args.salvar_artefatos:
        for caminho, conteudo in artefatos.items():
            destino = SAIDA / caminho
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(conteudo)
        (SAIDA / "demonstracao.md").write_text("\n".join(relato.linhas) + "\n", encoding="utf-8")
        (SAIDA / "resultados.json").write_text(json.dumps(resultados, indent=2, ensure_ascii=False, default=str) + "\n",
                                               encoding="utf-8")
        print(f"\nArtefatos gravados em {SAIDA.relative_to(PROJECT_ROOT)}/", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
