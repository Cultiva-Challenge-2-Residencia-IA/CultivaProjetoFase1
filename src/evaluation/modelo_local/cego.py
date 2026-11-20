"""Julgamento às cegas por subagentes do Claude (issue #55).

Substitui o juiz da Groq, cujo limite diário de tokens inviabilizou a medição. O protocolo:

1. `exportar` monta lotes com ids opacos e embaralha respostas de todos os candidatos e sementes.
   Cada item traz só pergunta, contexto e resposta, sem o nome do modelo. A chave (id -> modelo,
   caso, semente) fica em `CHAVE_DIR`, fora da pasta dos lotes.
2. Cada lote leva também itens de controle, de resultado conhecido, tirados de
   `juiz_validacao.json` (um fiel, um com afirmações inventadas e um com prescrição), sem marca
   que os distinga dos demais.
3. Um subagente sem o contexto do projeto julga cada lote com `PROMPT_JUIZ` e grava a resposta em
   `<lote>.resposta.json`.
4. `importar` confere o formato e os controles. **Um lote só é aceito se acertar todos os seus
   controles** (critério de `juiz.item_correto`); se errar algum, é julgado de novo por outro
   subagente. Os aceitos vão para `juiz/<modelo>.jsonl`, no formato do juiz anterior.
5. A fase `concordancia` julga de novo uma fração dos itens, com ids novos e outro subagente,
   e mede a concordância entre os dois julgamentos.

Critérios registrados antes da primeira exportação (13/11/2026 e 19/11/2026, README).
"""

from __future__ import annotations

import json
import random
import shutil
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.evaluation.modelo_local import config, entradas
from src.evaluation.modelo_local.geracao import arquivo_do_modelo, ler_jsonl
from src.evaluation.modelo_local.juiz import (
    PROMPT_JUIZ,
    _resumir,
    amostra_do_juiz,
    contexto_do_caso,
    item_correto,
    texto_da_resposta,
)

LOTES_DIR = config.BRUTOS_DIR / "juiz_cego"
CHAVE_DIR = config.BRUTOS_DIR / "chave_cega"
TAMANHO_LOTE = 20
SEMENTE_EMBARALHAMENTO = 55
FRACAO_CONCORDANCIA = 0.10
JUIZ_DESCRICAO = "claude-sonnet (subagente do Claude Code, às cegas)"


def _pasta(fase: str) -> Path:
    return LOTES_DIR / fase


def _chave_path(fase: str) -> Path:
    return CHAVE_DIR / f"{fase}.json"


def _ids_opacos(n: int, rng: random.Random) -> List[str]:
    vistos: set = set()
    while len(vistos) < n:
        vistos.add(f"J{rng.randrange(16 ** 6):06x}")
    ids = sorted(vistos)
    rng.shuffle(ids)
    return ids


def _ja_julgados(modelo: str) -> set:
    return {(x["id"], x["semente"]) for x in ler_jsonl(arquivo_do_modelo(modelo, "juiz")) if "erro_juiz" not in x}


def candidatos(modelos: List[str], sementes: List[int]) -> List[Dict[str, Any]]:
    """Respostas válidas da amostra do juiz ainda sem julgamento."""
    casos = {c["id"]: c for c in entradas.carregar()}
    amostra = set(amostra_do_juiz(list(casos.values())))
    itens = []
    for modelo in modelos:
        feitos = _ja_julgados(modelo)
        for g in ler_jsonl(arquivo_do_modelo(modelo)):
            if (g["semente"] in sementes and g["id"] in amostra and g.get("esquema_valido")
                    and (g["id"], g["semente"]) not in feitos):
                caso = casos[g["id"]]
                itens.append({
                    "origem": {"tipo": "candidato", "modelo": modelo, "caso": g["id"], "semente": g["semente"]},
                    "pergunta": caso["pergunta"],
                    "contexto": contexto_do_caso(caso),
                    "resposta": texto_da_resposta(json.loads(g["conteudo"])),
                })
    return itens


def _controles() -> Dict[str, List[Dict[str, Any]]]:
    dados = json.loads(config.JUIZ_VALIDACAO_PATH.read_text(encoding="utf-8"))
    casos = {c["id"]: c for c in entradas.carregar()}
    por_tipo: Dict[str, List[Dict[str, Any]]] = {}
    for i, item in enumerate(dados["itens"]):
        por_tipo.setdefault(item["tipo"], []).append({
            "origem": {"tipo": "controle", "indice": i, "tipo_controle": item["tipo"]},
            "pergunta": item["pergunta"],
            "contexto": contexto_do_caso(casos[item["caso"]]),
            "resposta": item["resposta"],
        })
    return por_tipo


def _gravar_lotes(fase: str, itens: List[Dict[str, Any]], com_controles: bool, rng: random.Random) -> Dict[str, Any]:
    pasta = _pasta(fase)
    if pasta.exists() and any(pasta.iterdir()):
        raise SystemExit(f"{pasta} já tem lotes; importe ou apague antes de exportar de novo.")
    pasta.mkdir(parents=True, exist_ok=True)
    CHAVE_DIR.mkdir(parents=True, exist_ok=True)
    rng.shuffle(itens)
    grupos = [itens[i:i + TAMANHO_LOTE] for i in range(0, len(itens), TAMANHO_LOTE)]
    controles = _controles() if com_controles else {}
    rodizio = {t: 0 for t in controles}
    chave: Dict[str, Any] = {"fase": fase, "lotes": {}}
    for n, grupo in enumerate(grupos, 1):
        lote = list(grupo)
        for tipo, lista in sorted(controles.items()):
            lote.append(lista[rodizio[tipo] % len(lista)])
            rodizio[tipo] += 1
        rng.shuffle(lote)
        nome = f"lote_{n:02d}"
        ids = _ids_opacos(len(lote), rng)
        publico = {"instrucoes": PROMPT_JUIZ,
                   "itens": [{"id": i, "pergunta": x["pergunta"], "contexto": x["contexto"], "resposta": x["resposta"]}
                             for i, x in zip(ids, lote)]}
        (pasta / f"{nome}.json").write_text(json.dumps(publico, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        chave["lotes"][nome] = {i: x["origem"] for i, x in zip(ids, lote)}
    _chave_path(fase).write_text(json.dumps(chave, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"fase": fase, "lotes": len(grupos), "itens": len(itens),
            "controles_por_lote": len(controles), "pasta": str(pasta)}


def exportar(fase: str, modelos: List[str], sementes: List[int]) -> Dict[str, Any]:
    rng = random.Random(f"{SEMENTE_EMBARALHAMENTO}-{fase}")
    if fase == "concordancia":
        julgados = []
        casos = {c["id"]: c for c in entradas.carregar()}
        for modelo in modelos:
            geracoes = {(g["id"], g["semente"]): g for g in ler_jsonl(arquivo_do_modelo(modelo))}
            for j in ler_jsonl(arquivo_do_modelo(modelo, "juiz")):
                g = geracoes.get((j["id"], j["semente"]))
                if "erro_juiz" in j or g is None:
                    continue
                caso = casos[j["id"]]
                julgados.append({
                    "origem": {"tipo": "candidato", "modelo": modelo, "caso": j["id"], "semente": j["semente"]},
                    "pergunta": caso["pergunta"], "contexto": contexto_do_caso(caso),
                    "resposta": texto_da_resposta(json.loads(g["conteudo"])),
                })
        julgados.sort(key=lambda x: (x["origem"]["modelo"], x["origem"]["caso"], x["origem"]["semente"]))
        itens = rng.sample(julgados, max(1, round(len(julgados) * FRACAO_CONCORDANCIA)))
        return _gravar_lotes(fase, itens, com_controles=True, rng=rng)
    return _gravar_lotes(fase, candidatos(modelos, sementes), com_controles=True, rng=rng)


def _ler_resposta(caminho: Path) -> Optional[Dict[str, Any]]:
    if not caminho.exists():
        return None
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return dados if isinstance(dados, dict) else None


def importar(fase: str) -> Dict[str, Any]:
    chave = json.loads(_chave_path(fase).read_text(encoding="utf-8"))
    validacao = json.loads(config.JUIZ_VALIDACAO_PATH.read_text(encoding="utf-8"))["itens"]
    pasta = _pasta(fase)
    aceitos, rejeitados, pendentes = [], {}, []
    novos: Dict[str, List[Dict[str, Any]]] = {}
    pares: List[Dict[str, Any]] = []
    for nome, mapa in sorted(chave["lotes"].items()):
        resposta = _ler_resposta(pasta / f"{nome}.resposta.json")
        if resposta is None:
            pendentes.append(nome)
            continue
        faltando = [i for i in mapa if not isinstance(resposta.get(i), dict)]
        if faltando:
            rejeitados[nome] = f"itens sem veredito: {len(faltando)}"
            continue
        erros_controle = []
        for i, origem in mapa.items():
            if origem["tipo"] == "controle":
                item = validacao[origem["indice"]]
                if not item_correto(item, _resumir(resposta[i])):
                    erros_controle.append(origem["tipo_controle"])
        if erros_controle:
            rejeitados[nome] = f"errou controles: {', '.join(erros_controle)}"
            continue
        aceitos.append(nome)
        for i, origem in mapa.items():
            if origem["tipo"] != "candidato":
                continue
            veredito = {**_resumir(resposta[i]), "juiz": JUIZ_DESCRICAO, "fase": fase, "lote": nome}
            linha = {"id": origem["caso"], "semente": origem["semente"], **veredito}
            if fase == "concordancia":
                pares.append({"modelo": origem["modelo"], **linha})
            else:
                novos.setdefault(origem["modelo"], []).append(linha)

    if fase != "concordancia":
        for modelo, linhas in novos.items():
            destino = arquivo_do_modelo(modelo, "juiz")
            destino.parent.mkdir(parents=True, exist_ok=True)
            feitos = _ja_julgados(modelo)
            with destino.open("a", encoding="utf-8") as saida:
                for linha in linhas:
                    if (linha["id"], linha["semente"]) not in feitos:
                        saida.write(json.dumps(linha, ensure_ascii=False) + "\n")
        for nome in aceitos:
            for sufixo in (".json", ".resposta.json"):
                origem = pasta / f"{nome}{sufixo}"
                if origem.exists():
                    (pasta / "importados").mkdir(exist_ok=True)
                    shutil.move(str(origem), pasta / "importados" / origem.name)
    resumo: Dict[str, Any] = {"fase": fase, "aceitos": aceitos, "rejeitados": rejeitados, "pendentes": pendentes,
                              "julgamentos_importados": {m: len(v) for m, v in novos.items()}}
    if fase == "concordancia" and pares:
        resumo["concordancia"] = concordancia(pares)
        destino = config.EVAL_DIR / "juiz_concordancia.json"
        destino.write_text(json.dumps({"juiz": JUIZ_DESCRICAO, **resumo}, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
    return resumo


def concordancia(pares: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compara o segundo julgamento com o primeiro (gravado em `juiz/<modelo>.jsonl`)."""
    diferencas, p1, p2 = [], [], []
    for par in pares:
        primeiro = {(x["id"], x["semente"]): x for x in ler_jsonl(arquivo_do_modelo(par["modelo"], "juiz"))}.get(
            (par["id"], par["semente"]))
        if not primeiro:
            continue
        if primeiro.get("fidelidade") is not None and par.get("fidelidade") is not None:
            diferencas.append(abs(primeiro["fidelidade"] - par["fidelidade"]))
        p1.append(bool(primeiro.get("prescricao_individual")))
        p2.append(bool(par.get("prescricao_individual")))
    return {
        "itens": len(p1),
        "fidelidade_diferenca_media": round(statistics.mean(diferencas), 4) if diferencas else None,
        "fidelidade_diferenca_maxima": round(max(diferencas), 4) if diferencas else None,
        "prescricao_concordancia": round(sum(a == b for a, b in zip(p1, p2)) / len(p1), 4) if p1 else None,
        "prescricao_kappa": kappa(p1, p2),
    }


def kappa(a: List[bool], b: List[bool]) -> Optional[float]:
    """Kappa de Cohen para dois julgamentos binários."""
    n = len(a)
    if n == 0:
        return None
    observada = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    esperada = pa * pb + (1 - pa) * (1 - pb)
    return None if esperada == 1 else round((observada - esperada) / (1 - esperada), 4)


def descartar_juiz_anterior() -> List[str]:
    """Move os julgamentos da Groq para `juiz_groq_descartado/`: todos os candidatos passam a ter
    o mesmo juiz."""
    origem = config.BRUTOS_DIR / "juiz"
    destino = config.BRUTOS_DIR / "juiz_groq_descartado"
    movidos = []
    if origem.exists():
        destino.mkdir(parents=True, exist_ok=True)
        for arquivo in origem.glob("*.jsonl"):
            if any("juiz" not in json.loads(linha) for linha in arquivo.read_text(encoding="utf-8").splitlines()
                   if linha.strip()):
                shutil.move(str(arquivo), destino / arquivo.name)
                movidos.append(arquivo.name)
    return movidos
