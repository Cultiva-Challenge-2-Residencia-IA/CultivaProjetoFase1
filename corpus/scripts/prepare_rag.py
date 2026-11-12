#!/usr/bin/env python3
"""Markdown convertido -> Trechos limpos em JSONL, prontos para indexação no RAG.

Não altera os .md convertidos, o manifesto nem os status de revisão. Cada Trecho
pertence a uma única página física do PDF, para que a citação aponte a página exata.
Os status de revisão e aprovação são copiados do manifesto: quem indexa decide se
aceita fontes pendentes. Cada execução atualiza `rag/geracao.json` com os hashes de
tudo de que o JSONL depende (Markdown ou JSON de origem, este script, a seção da fonte
no `rag.yaml` e o próprio JSONL), conferidos por `verify_trechos.py`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "corpus/nutricao/rag"
GENERATION_PATH = OUTPUT_DIR / "geracao.json"
SCRIPT_PATH = Path(__file__).resolve()
CONFIG_PATH = ROOT / "corpus/scripts/config/rag.yaml"
SCHEMA_PATH = ROOT / "corpus/schemas/trecho.schema.json"
TARGET_CHARS = 1000
MAX_CHARS = 1400
MIN_CHARS = 80
RUNNING_HEADER_MAX_CHARS = 200
RUNNING_HEADER_MIN_PAGES = 4

# Seções sem conteúdo científico a recuperar. Descartadas até o próximo título.
# Aceita numeração antes do título ("9. BIBLIOGRAFIA", "9.BIBLIOGRAFIA").
SKIPPED_SECTIONS = re.compile(
    r"^(\d+(\.\d+)*\.?\s*)?"
    r"(refer[eê]ncias( bibliogr[aá]ficas)?|references?|bibliografia|colaboradores|abstract|resumen|[ií]ndice|sum[aá]rio"
    r"|fomento|agradecimentos|acknowledge?ments?|conflitos? de interesses?|conflicts? of interest)$",
    re.I,
)
# Linhas de cabeçalho/rodapé de periódico e numeração solta.
NOISE_LINE = re.compile(
    r"^(\d{1,4}|CAP[ÍI]TULO \d+|.*\.indd( \d+)?.*|DOI:?\s*\S+|Artigos? Originais?|artigo article"
    r"|Rev Saúde Pública \d{4};.*|Ciênc\.? Saúde Colet.*)$",
    re.I,
)
PAGE_MARK = re.compile(r"<!-- PDF_PAGE: (\d+) -->")


def tipos_de_fonte() -> list[str]:
    """Tipos de fonte aceitos, lidos do JSON Schema do Trecho (fonte única do contrato)."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return schema["properties"]["tipo_fonte"]["enum"]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rag_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}


def source_config_sha256(config: dict, source_id: str) -> str:
    """Hash só da seção da fonte no rag.yaml: mudar outra fonte não invalida esta."""
    return sha256_text(json.dumps(config.get(source_id, {}), ensure_ascii=False, sort_keys=True))


def generation_entry(output: Path, origin: dict, config: dict, source_id: str, trechos: int) -> dict:
    return {
        "jsonl_path": str(output.relative_to(ROOT)),
        "jsonl_sha256": sha256_file(output),
        **origin,
        "prepare_rag_sha256": sha256_file(SCRIPT_PATH),
        "rag_config_sha256": source_config_sha256(config, source_id),
        "trechos": trechos,
    }


def load_generation() -> dict:
    if not GENERATION_PATH.exists():
        return {"versao": 1, "fontes": {}}
    return json.loads(GENERATION_PATH.read_text(encoding="utf-8"))


def write_generation(generation: dict) -> None:
    generation["fontes"] = dict(sorted(generation["fontes"].items()))
    GENERATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    GENERATION_PATH.write_text(json.dumps(generation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def repo_path(value: str) -> Path:
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"Caminho fora do repositório: {value}")
    return path


def split_pages(markdown: str) -> list[tuple[int, str]]:
    """Separa por marcador de página, descartando o cabeçalho de conversão."""
    parts = PAGE_MARK.split(markdown)
    return [(int(parts[i]), parts[i + 1]) for i in range(1, len(parts), 2)]


def collapse_spaced_letters(title: str) -> str:
    """Junta títulos com letras separadas por espaço ("r e f e r e n c e s")."""
    tokens = title.split()
    return "".join(tokens) if len(tokens) > 2 and all(len(t) == 1 for t in tokens) else title


# Títulos inválidos que decorrem de artefatos de extração do PDF: referências
# numéricas, fragmentos de frases, classificações de evidência ou legendas.
INVALID_HEADING = re.compile(
    r"\[\d+\]"                                            # referências numéricas [121], [110]
    r"|^\([A-Za-zÀ-Úà-ú]+.*?\d{4}\)$"                     # citações parentéticas soltas (arnow, Kenardy & agras, 1995)
    r"|\b(N[íi]vel de evid[êe]ncia|Classe de recomenda[çc][ãa]o)\b"   # fragmentos de classificação de evidência
    r"|^\d{4}\s+minist[eé]rio\s+da\s+sa[uú]de"            # 2006 ministério da saúde.
    r"|^[A-Za-zÀ-Úà-ú]+,\s+[A-Z]\.\s+.*?\b\d{4}\b"        # citações bibliográficas soltas
    r"|^Aprova o C[óo]digo de [ÉE]tica"                   # ementa de resolução
    r"|^(Assim, a carne vermelha|acompanhamento individualizado|idoneidade dos servi[çc]os)\b"
    r"|^Tabela\s+\d+[:.]"                                 # legendas de tabela convertidas em título
    r"|©|todos os direitos reservados",
    re.I,
)


def normalize_title(title: str) -> str:
    """Normaliza título de seção: letras espaçadas, cedilha solta e pontuação final."""
    title = collapse_spaced_letters(title)
    # Cola cedilha separada por espaço ("RECOMENDA Ç ÃO" -> "RECOMENDAÇÃO", "DEFINI Ç ÕES" -> "DEFINIÇÕES")
    title = re.sub(r"(?<=[A-Za-zÀ-Úà-ú])\s+([çÇ])\s+(?=[A-Za-zÀ-Úà-ú])", r"\1", title)
    return title.rstrip(" .")


def is_invalid_heading(title: str) -> bool:
    """Identifica títulos inválidos gerados por artefatos de extração do PDF."""
    if not title or len(title) > 250:
        return True
    return bool(INVALID_HEADING.search(title))


# Palavra com "_" que não é ênfase: URL, caminho ou nome de arquivo
# ("guia_alimentar_populacao_brasileira_2ed.pdf", "Dietary_Guidelines_for_Americans").
PROTECTED_TOKEN = re.compile(
    r"://|www\.|[/?=&]|\.(pdf|html?|jsp|aspx?|php|docx?|xlsx?)\b|\w_\w+_\w", re.I
)
# Par de marcadores de ênfase (itálico/negrito) com o mesmo delimitador dos dois lados.
EMPHASIS_PAIR = re.compile(r"(\*{1,3}|_{1,3})([^*_\n]+?)\1")
NO_SPACE_BEFORE = set(" \t([{\"'“‘/-<>=≤≥±+%")
NO_SPACE_AFTER = set(" \t.,;:!?)]}\"'”’/-<>=≤≥±+%")


def strip_emphasis(line: str) -> str:
    """Remove marcadores de ênfase sem colar a ênfase às palavras vizinhas.

    O conversor às vezes gera itálico sem espaço ("Alimentos_in natura_ou"); apagar só os
    "_" produziria "Alimentosin naturaou". URLs e nomes de arquivo mantêm seus "_".
    """
    protected: list[str] = []

    def protect(match: re.Match) -> str:
        token = match.group(0)
        core = token.strip("*_`")
        if not re.search(r"\w_\w", core) or not PROTECTED_TOKEN.search(core):
            return token
        protected.append(core)
        return f"\x00{len(protected) - 1}\x00"

    # Asteriscos escapados ("\*\*", marca de nota) e pares vazios ("****") não são ênfase.
    line = re.sub(r"\\[*`]", "", line)
    line = re.sub(r"(\*{2,3}|_{2,3})\1", "", line)
    line = re.sub(r"\S+", protect, line)

    def unwrap(match: re.Match) -> str:
        text, start, end = match.string, match.start(), match.end()
        inner = match.group(2)
        before = " " if start > 0 and text[start - 1] not in NO_SPACE_BEFORE else ""
        after = " " if end < len(text) and text[end] not in NO_SPACE_AFTER else ""
        # Negrito partindo uma sigla ("**IDAT**E"): maiúsculas dos dois lados, sem espaço.
        if before and (inner[0] in NO_SPACE_AFTER or text[start - 1].isupper() and inner[0].isupper()):
            before = ""
        if after and text[end].isupper() and inner[-1].isupper():
            after = ""
        return f"{before}{match.group(2)}{after}"

    line = EMPHASIS_PAIR.sub(unwrap, line)
    # Marcadores sem par: "*" e "`" saem; "_" só sai na borda de palavra.
    line = re.sub(r"[*`]{1,3}|(?<!\w)_+|_+(?!\w)", "", line)
    return re.sub(r"\x00(\d+)\x00", lambda m: protected[int(m.group(1))], line)


def clean_inline(line: str) -> str:
    line = re.sub(r"<!--.*?-->", "", line)
    line = re.sub(r"<sup>.*?</sup>", "", line)
    line = re.sub(r"<br\s*/?>", " ", line)
    line = re.sub(r"</?[a-z][^>]*>", "", line)
    line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)
    line = strip_emphasis(line)
    # Ligaturas quebradas pela extração do PDF ("signifi cativo" -> "significativo").
    line = re.sub(r"(?<=[A-Za-zà-ú])(ffi|ffl|fi|fl) (?=[a-zà-ú]+\b)", r"\1", line)
    line = re.sub(r"(?<![A-Za-zà-ú])(fi|fl) (?=[a-zà-ú]{3,})", r"\1", line)
    line = re.sub(r"\s+", " ", line).strip()
    return unicodedata.normalize("NFC", line)


def clean_page(raw: str, skipping: bool, section: str,
               keep_sections: frozenset[str] = frozenset(),
               resume: tuple[re.Pattern, ...] = ()) -> tuple[list[tuple[str, str, bool]], bool, str]:
    """Devolve (seção, parágrafo, é_linha_de_tabela), se segue em seção descartada e a seção corrente."""
    paragraphs: list[tuple[str, str, bool]] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            paragraphs.append((section, " ".join(current), False))
            current.clear()

    last_valid_section = ""

    for line in raw.splitlines():
        stripped = line.strip()
        if (not stripped or stripped == "---" or stripped.startswith("<a id=")
                or stripped.startswith("<!--") or stripped.startswith("> **Nota de conversão")
                or stripped.startswith("[Conferir no original]")
                or re.match(r"^##\s+Página PDF \d+\s*$", stripped)):
            flush()
            continue
        heading = re.match(r"^#{1,6}\s+(.*)$", stripped)
        if heading:
            flush()
            raw_title = clean_inline(heading.group(1))
            if is_invalid_heading(raw_title):
                section = last_valid_section
                continue
            title = normalize_title(raw_title)
            name = title.strip(" .:")
            skipping = bool(SKIPPED_SECTIONS.match(name)) and name.lower() not in keep_sections
            if title and not skipping:
                section = title
                last_valid_section = title
            continue
        if skipping:
            if resume and any(rx.match(clean_inline(stripped)) for rx in resume):
                skipping, section = False, normalize_title(clean_inline(stripped))
                last_valid_section = section
            continue
        if re.match(r"^\|[\s:|-]+\|?$", stripped):  # separador de tabela
            continue
        if stripped.startswith("|"):  # linha de tabela: uma por linha, sem barras
            flush()
            cells = [clean_inline(c) for c in stripped.strip("|").split("|")]
            row = " | ".join(c for c in cells if c)
            if row:
                paragraphs.append((section, row, True))
            continue
        text = clean_inline(stripped)
        if not text or NOISE_LINE.match(text):
            continue
        current.append(text)
    flush()
    return paragraphs, skipping, section


def split_long(paragraph: str) -> list[str]:
    """Divide parágrafos maiores que MAX_CHARS em fronteiras de frase."""
    if len(paragraph) <= MAX_CHARS:
        return [paragraph]
    sentences = re.split(r"(?<=[.!?;])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9])", paragraph)
    pieces: list[str] = []
    buffer = ""
    for sentence in sentences:
        if buffer and len(buffer) + 1 + len(sentence) > TARGET_CHARS:
            pieces.append(buffer)
            buffer = sentence
        else:
            buffer = f"{buffer} {sentence}".strip()
    if buffer:
        pieces.append(buffer)
    return pieces


def chunk_page(paragraphs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Junta parágrafos curtos até ~TARGET_CHARS, sem atravessar página nem seção."""
    chunks: list[tuple[str, str]] = []
    buffer, buffer_section = "", ""
    for section, paragraph in paragraphs:
        for piece in split_long(paragraph):
            if buffer and (section != buffer_section or len(buffer) + 2 + len(piece) > TARGET_CHARS):
                chunks.append((buffer_section, buffer))
                buffer = piece
            else:
                buffer = f"{buffer}\n\n{piece}".strip()
            buffer_section = section
    if buffer:
        chunks.append((buffer_section, buffer))
    return chunks


def prepare(source: dict) -> tuple[dict, dict]:
    markdown_path = repo_path(source["markdown_path"])
    markdown = markdown_path.read_text(encoding="utf-8")
    report = json.loads(repo_path(source["report_path"]).read_text(encoding="utf-8"))
    if sha256_text(markdown) != report["markdown_sha256"]:
        raise ValueError(f"Markdown mudou após a conversão: {markdown_path.name}")

    if source.get("source_type") not in tipos_de_fonte():
        raise ValueError(
            f"source_type ausente ou inválido em {source['id']}: {source.get('source_type')!r} "
            f"(aceitos: {', '.join(tipos_de_fonte())})"
        )
    fonte_url = source["source"] if str(source["source"]).startswith(("http://", "https://")) else None
    config = load_rag_config()
    source_config = config.get(source["id"], {})
    drop = [re.compile(p) for p in source_config.get("drop_paragraphs", [])]
    keep = frozenset(s.lower() for s in source_config.get("keep_sections", []))
    resume = tuple(re.compile(p) for p in source_config.get("resume_after_skip", []))
    skip_pages = frozenset(source_config.get("skip_pages", []))
    records: list[dict] = []
    skipping, section = False, ""
    discarded_short = 0
    cleaned = []
    for page, raw in split_pages(markdown):
        if page in skip_pages:
            cleaned.append((page, []))
            continue
        paragraphs, skipping, section = clean_page(raw, skipping, section, keep, resume)
        cleaned.append((page, [(s, p, t) for s, p, t in paragraphs if not any(rx.search(p) for rx in drop)]))
    # Cabeçalhos e rodapés correntes: parágrafo curto que se repete em várias páginas.
    # Linhas de tabela ficam de fora: cabeçalhos de coluna repetidos são conteúdo.
    pages_by_text: dict[str, set[int]] = {}
    for page, paragraphs in cleaned:
        for _, paragraph, is_table in paragraphs:
            if not is_table and len(paragraph) < RUNNING_HEADER_MAX_CHARS:
                pages_by_text.setdefault(paragraph, set()).add(page)
    running = {text for text, pages in pages_by_text.items() if len(pages) >= RUNNING_HEADER_MIN_PAGES}
    for page, paragraphs in cleaned:
        paragraphs = [(s, p) for s, p, t in paragraphs if t or p not in running]
        for number, (chunk_section, text) in enumerate(chunk_page(paragraphs), 1):
            if len(text) < MIN_CHARS:
                discarded_short += 1
                continue
            records.append({
                "id": f"{source['id']}-p{page:03d}-{number:02d}",
                "fonte_id": source["id"],
                "titulo_fonte": source["title"],
                "instituicoes": list(source["institutions"]),
                "ano": int(source["year"]),
                "tipo_fonte": source["source_type"],
                "fonte_url": fonte_url,
                "doi": source.get("doi"),
                "pagina_pdf": page,
                "secao": chunk_section,
                "texto": text,
                "licenca": source["license"],
                "approval_status": source["approval_status"],
            })

    output = OUTPUT_DIR / f"{markdown_path.stem}.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8"
    )
    sizes = sorted(len(r["texto"]) for r in records)
    entry = generation_entry(output, {"markdown_sha256": report["markdown_sha256"]}, config,
                             source["id"], len(records))
    return entry, {
        "arquivo": str(output.relative_to(ROOT)),
        "trechos": len(records),
        "descartados_curtos": discarded_short,
        "paginas_com_trecho": len({r["pagina_pdf"] for r in records}),
        "tamanho_min_mediana_max": [sizes[0], sizes[len(sizes) // 2], sizes[-1]] if sizes else [],
    }


# Prefixo que o ingest_pubmed_evidence.py põe em cada resumo: "Estudo: <título> (PMID:<n> (...)). "
RESUMO_PREFIXO = re.compile(r"^Estudo:\s*.+?\(PMID:(\d+).*?\)\)\.\s*", re.S)


def prepare_resumos(sources: list[dict]) -> tuple[dict[str, dict], dict]:
    """Trechos dos resumos do PubMed (kind: resumo_pubmed), todos num único JSONL, sem página."""
    por_pmid = {str(s["pmid"]): s for s in sources}
    destinos = {s["rag_path"] for s in sources}
    if len(destinos) != 1:
        raise ValueError("Os resumos do PubMed devem compartilhar o mesmo rag_path.")
    textos: dict[str, str] = {}
    for raw_path in sorted({s["raw_path"] for s in sources}):
        raw = repo_path(raw_path)
        esperados = {s["raw_sha256"] for s in sources if s["raw_path"] == raw_path}
        if hashlib.sha256(raw.read_bytes()).hexdigest() not in esperados:
            raise ValueError(f"JSON de origem divergente do manifesto: {raw_path}")
        for documento in json.loads(raw.read_text(encoding="utf-8")):
            for secao in documento["sections"]:
                achado = RESUMO_PREFIXO.match(secao["text"])
                if achado and achado.group(1) in por_pmid and achado.group(1) not in textos:
                    textos[achado.group(1)] = secao["text"][achado.end():].strip()
    faltando = sorted(set(por_pmid) - set(textos))
    if faltando:
        raise ValueError(f"Resumos não encontrados no JSON de origem: PMID {', '.join(faltando)}")

    records: list[dict] = []
    for pmid, source in por_pmid.items():
        if source.get("source_type") not in tipos_de_fonte():
            raise ValueError(f"source_type ausente ou inválido em {source['id']}: {source.get('source_type')!r}")
        paragrafos = [("Resumo", clean_inline(textos[pmid]))]
        for number, (_, text) in enumerate(chunk_page(paragrafos), 1):
            records.append({
                "id": f"{source['id']}-resumo-{number:02d}",
                "fonte_id": source["id"],
                "titulo_fonte": source["title"],
                "instituicoes": list(source["institutions"]),
                "ano": int(source["year"]),
                "tipo_fonte": source["source_type"],
                "fonte_url": source["source"],
                "doi": source.get("doi"),
                "pagina_pdf": None,
                "secao": "Resumo",
                "texto": text,
                "licenca": source["license"],
                "approval_status": source["approval_status"],
            })
    output = repo_path(destinos.pop())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    config = load_rag_config()
    entries = {
        s["id"]: generation_entry(output, {"raw_sha256": s["raw_sha256"]}, config, s["id"],
                                  sum(r["fonte_id"] == s["id"] for r in records))
        for s in sources
    }
    return entries, {"arquivo": str(output.relative_to(ROOT)), "fontes": len(por_pmid), "trechos": len(records)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="corpus/manifest.yaml")
    parser.add_argument("--source", help="Processa somente o identificador informado")
    args = parser.parse_args()
    try:
        manifest = yaml.safe_load(repo_path(args.manifest).read_text(encoding="utf-8"))
        sources = [s for s in manifest["sources"] if not args.source or s["id"] == args.source]
        if not sources:
            raise ValueError("Nenhuma fonte selecionada.")
        generation = load_generation()
        if not args.source:
            generation["fontes"] = {}
        for source in sources:
            if source.get("kind", "pdf") == "pdf":
                entry, summary = prepare(source)
                generation["fontes"][source["id"]] = entry
                print(f"{source['id']}: {json.dumps(summary, ensure_ascii=False)}")
        if any(s.get("kind", "pdf") == "resumo_pubmed" for s in sources):
            # Os resumos compartilham um único JSONL: regenera todos juntos.
            resumos = [s for s in manifest["sources"] if s.get("kind", "pdf") == "resumo_pubmed"]
            entries, summary = prepare_resumos(resumos)
            generation["fontes"].update(entries)
            print(f"resumos do PubMed: {json.dumps(summary, ensure_ascii=False)}")
        write_generation(generation)
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
