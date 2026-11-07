import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

import pymupdf

from src.config import DATA_DIR
from src.models.schemas import DocumentSectionInput, GuidelineDocumentInput

PDF_DEFAULT_PATH = DATA_DIR / "raw" / "pdfs" / "guia_alimentar_populacao_brasileira_2ed.pdf"
EXTRACTED_JSON_PATH = DATA_DIR / "raw" / "guidelines" / "guia_alimentar_ms_2ed.json"

# Mapeamento oficial dos capítulos do Guia Alimentar para a População Brasileira (2ª Edição)
# (pdf_start_page_1based, pdf_end_page_1based, doc_id, title, clinical_domain)
GUIA_ALIMENTAR_CHAPTERS: List[Tuple[int, int, str, str, str]] = [
    (
        6,
        15,
        "GUIA_MS_INTRO",
        "Guia Alimentar para a População Brasileira — Apresentação, Preâmbulo e Introdução",
        "Políticas Públicas, Direito à Alimentação e Escopo de Atuação do Nutricionista",
    ),
    (
        16,
        25,
        "GUIA_MS_CAP1_PRINCIPIOS",
        "Guia Alimentar para a População Brasileira — Capítulo 1: Princípios Norteadores",
        "Princípios da Alimentação Adequada e Saudável, Sustentabilidade e Autonomia",
    ),
    (
        26,
        53,
        "GUIA_MS_CAP2_ESCOLHA_ALIMENTOS",
        "Guia Alimentar para a População Brasileira — Capítulo 2: A Escolha dos Alimentos (Classificação NOVA)",
        "Classificação NOVA: Alimentos In Natura, Minimamente Processados, Processados, Ultraprocessados e Ingredientes Culinários",
    ),
    (
        54,
        91,
        "GUIA_MS_CAP3_REFEICOES",
        "Guia Alimentar para a População Brasileira — Capítulo 3: Dos Alimentos à Refeição",
        "Composição de Refeições Brasileiras, Café da Manhã, Almoço, Jantar, Grupos de Alimentos (Feijões, Cereais, Raízes, Hortaliças, Frutas, Carnes, Leite, Castanhas)",
    ),
    (
        92,
        103,
        "GUIA_MS_CAP4_COMENSALIDADE",
        "Guia Alimentar para a População Brasileira — Capítulo 4: O Ato de Comer e a Comensalidade",
        "Comportamento Alimentar, Saciedade, Ambiente Alimentar, Regularidade, Atenção Plena e Comensalidade",
    ),
    (
        104,
        125,
        "GUIA_MS_CAP5_OBSTACULOS",
        "Guia Alimentar para a População Brasileira — Capítulo 5: A Compreensão e a Superação de Obstáculos",
        "Informação Confiável, Oferta, Custo, Habilidades Culinárias, Tempo e Publicidade de Ultraprocessados",
    ),
    (
        126,
        131,
        "GUIA_MS_DEZ_PASSOS",
        "Guia Alimentar para a População Brasileira — Dez Passos para uma Alimentação Adequada e Saudável",
        "Síntese Prática das Recomendações Oficiais e Regra de Ouro",
    ),
    (
        132,
        158,
        "GUIA_MS_ANEXOS_EVIDENCIAS",
        "Guia Alimentar para a População Brasileira — Para Saber Mais e Anexo A (Bases Científicas)",
        "Fundamentação Científica, Referências Bibliográficas e Processo de Elaboração",
    ),
]


def clean_pdf_page_text(raw_page_text: str) -> str:
    """Limpa cabeçalhos/rodapés repetitivos e hifenizações de quebra de linha do PDF."""
    lines = raw_page_text.splitlines()
    cleaned_lines: List[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
        # Ignora linhas que são apenas número de página ou cabeçalho institucional repetido
        if re.fullmatch(r"\d{1,3}", stripped):
            continue
        if stripped.upper() in {
            "MINISTÉRIO DA SAÚDE",
            "GUIA ALIMENTAR PARA A POPULAÇÃO BRASILEIRA",
        }:
            continue
        cleaned_lines.append(stripped)

    # Reconstrói parágrafos juntando quebras de linha dentro da mesma frase
    paragraphs: List[str] = []
    current_para: List[str] = []

    for line in cleaned_lines:
        if not line:
            if current_para:
                paragraphs.append(" ".join(current_para))
                current_para = []
        else:
            if current_para and current_para[-1].endswith("-"):
                current_para[-1] = current_para[-1][:-1] + line
            else:
                current_para.append(line)

    if current_para:
        paragraphs.append(" ".join(current_para))

    text = "\n\n".join(p.strip() for p in paragraphs if len(p.strip()) > 20)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def extract_guia_alimentar_pdf(
    pdf_path: Path = PDF_DEFAULT_PATH,
    output_json_path: Path = EXTRACTED_JSON_PATH,
) -> List[GuidelineDocumentInput]:
    """
    Extrai todas as páginas de conteúdo do PDF oficial do Guia Alimentar para a População Brasileira,
    estruturando por capítulo e páginas para indexação no motor de RAG Híbrido.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF não encontrado em: {pdf_path}")

    doc = pymupdf.open(str(pdf_path))
    total_pages = len(doc)

    documents: List[GuidelineDocumentInput] = []

    for start_page, end_page, doc_id, title, clinical_domain in GUIA_ALIMENTAR_CHAPTERS:
        sections: List[DocumentSectionInput] = []
        actual_end = min(end_page, total_pages)

        # Agrupa a cada 2 páginas contíguas com texto substancial para preservar continuidade entre páginas
        buffer_pages: List[int] = []
        buffer_texts: List[str] = []

        for page_num in range(start_page, actual_end + 1):
            page = doc[page_num - 1]
            cleaned = clean_pdf_page_text(page.get_text("text"))
            if len(cleaned) < 80:
                continue

            book_page = page_num - 1
            buffer_pages.append(book_page)
            buffer_texts.append(cleaned)

            if len(" ".join(buffer_texts)) >= 950:
                page_label = (
                    f"Pág. {buffer_pages[0]}"
                    if len(buffer_pages) == 1
                    else f"Págs. {buffer_pages[0]}-{buffer_pages[-1]}"
                )
                sections.append(
                    DocumentSectionInput(
                        section_path=f"{title.split('—')[-1].strip()} > {page_label}",
                        text="\n\n".join(buffer_texts),
                    )
                )
                buffer_pages = []
                buffer_texts = []

        if buffer_texts:
            page_label = (
                f"Pág. {buffer_pages[0]}"
                if len(buffer_pages) == 1
                else f"Págs. {buffer_pages[0]}-{buffer_pages[-1]}"
            )
            sections.append(
                DocumentSectionInput(
                    section_path=f"{title.split('—')[-1].strip()} > {page_label}",
                    text="\n\n".join(buffer_texts),
                )
            )

        documents.append(
            GuidelineDocumentInput(
                doc_id=doc_id,
                title=title,
                source_organization="Ministério da Saúde (Brasil) — 2ª Edição Oficial",
                publication_year=2014,
                clinical_domain=clinical_domain,
                evidence_level="GUIDELINE_CONSENSUS",
                sections=sections,
            )
        )

    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = [d.model_dump() for d in documents]
    output_json_path.write_text(
        json.dumps(serialized, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return documents


ingest_guia_alimentar_pdf = extract_guia_alimentar_pdf


if __name__ == "__main__":
    docs = extract_guia_alimentar_pdf()
    total_sections = sum(len(d.sections) for d in docs)
    total_chars = sum(len(s.text) for d in docs for s in d.sections)
    print(f"Extraídos {len(docs)} capítulos ({total_sections} seções, {total_chars:,} caracteres) do PDF oficial.")
    print(f"Salvo em: {EXTRACTED_JSON_PATH}")
