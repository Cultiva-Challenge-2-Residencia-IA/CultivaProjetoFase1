import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple

import httpx

from src.config import DATA_DIR
from src.models.schemas import DocumentSectionInput, GuidelineDocumentInput

PUBMED_OUTPUT_PATH = DATA_DIR / "raw" / "guidelines" / "pubmed_clinical_evidence.json"
EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Consultas temáticas estruturadas na API oficial do PubMed focadas em Meta-Análises, Revisões Sistemáticas e Diretrizes
PUBMED_TOPICS: List[Tuple[str, str, str, str]] = [
    (
        "PUBMED_FIBER_MICROBIOTA",
        "Meta-Analyses & Systematic Reviews: Dietary Fiber, Beta-Glucan, Gut Microbiota and Short-Chain Fatty Acids",
        "Saúde Gastrointestinal, Fibras Solúveis (Beta-Glucana/Psyllium), Microbiota e AGCC",
        '(("dietary fiber"[Title/Abstract] OR "beta-glucan"[Title/Abstract] OR "psyllium"[Title/Abstract]) AND ("short-chain fatty acids"[Title/Abstract] OR "LDL"[Title/Abstract] OR "glycemic"[Title/Abstract]) AND (meta-analysis[Publication Type] OR systematic review[Publication Type]))',
    ),
    (
        "PUBMED_GLYCEMIC_DIABETES",
        "Meta-Analyses & Guidelines: Nutritional Management of Glycemia, HbA1c and Insulin Resistance",
        "Controle Glicêmico, Hemoglobina Glicada (HbA1c), Carga Glicêmica e Amido Resistente",
        '(("resistant starch"[Title/Abstract] OR "glycemic index"[Title/Abstract] OR "soluble fiber"[Title/Abstract]) AND ("HbA1c"[Title/Abstract] OR "insulin resistance"[Title/Abstract] OR "type 2 diabetes"[Title/Abstract]) AND (meta-analysis[Publication Type] OR practice guideline[Publication Type]))',
    ),
    (
        "PUBMED_LIPIDS_CARDIO",
        "Meta-Analyses & Guidelines: Dietary Fats, Phytosterols, Omega-3 (EPA/DHA) and Dyslipidemia",
        "Saúde Cardiovascular, Colesterol LDL, Fitoesteróis e Ômega-3 Marinho (EPA/DHA)",
        '(("phytosterols"[Title/Abstract] OR "plant sterols"[Title/Abstract] OR "eicosapentaenoic"[Title/Abstract] OR "saturated fat"[Title/Abstract]) AND ("LDL cholesterol"[Title/Abstract] OR "triglycerides"[Title/Abstract]) AND (meta-analysis[Publication Type] OR systematic review[Publication Type]))',
    ),
    (
        "PUBMED_DASH_HYPERTENSION",
        "Meta-Analyses & Guidelines: DASH Diet, Sodium, Potassium, Magnesium and Dietary Nitrates in Blood Pressure",
        "Pressão Arterial, Padrão Alimentar DASH, Sódio/Potássio e Nitratos Alimentares",
        '(("DASH diet"[Title/Abstract] OR "dietary nitrate"[Title/Abstract] OR "potassium intake"[Title/Abstract]) AND ("blood pressure"[Title/Abstract] OR "hypertension"[Title/Abstract]) AND (meta-analysis[Publication Type] OR systematic review[Publication Type]))',
    ),
    (
        "PUBMED_PROTEIN_SUPPLEMENTS",
        "Position Stands & Meta-Analyses: Dietary Protein, Leucine, Creatine Monohydrate and Caffeine",
        "Proteínas, Hipertrofia/Sarcopenia, Creatina Monohidratada (Segurança Renal) e Cafeína",
        '(("creatine supplementation"[Title/Abstract] OR "protein intake"[Title/Abstract] OR "leucine"[Title/Abstract]) AND ("muscle mass"[Title/Abstract] OR "strength"[Title/Abstract] OR "renal function"[Title/Abstract] OR "sarcopenia"[Title/Abstract]) AND (meta-analysis[Publication Type] OR systematic review[Publication Type]))',
    ),
    (
        "PUBMED_BIOACTIVES_MICRONUTRIENTS",
        "Meta-Analyses & Reviews: Curcumin Bioavailability (Piperine), Green Tea Catechins (EGCG), Sulforaphane and Iron Absorption",
        "Compostos Bioativos (Curcumina/Piperina, EGCG, Sulforafano) e Biodisponibilidade de Micronutrientes (Ferro/Vitamina C/B12)",
        '(("curcumin"[Title/Abstract] AND "piperine"[Title/Abstract]) OR ("non-heme iron"[Title/Abstract] AND "ascorbic acid"[Title/Abstract]) OR ("sulforaphane"[Title/Abstract] AND "broccoli"[Title/Abstract]) OR ("green tea"[Title/Abstract] AND "catechin"[Title/Abstract] AND meta-analysis[Publication Type]))',
    ),
]


def _search_pmids(client: httpx.Client, term: str, retmax: int = 6) -> List[str]:
    resp = client.get(
        f"{EUTILS_BASE}/esearch.fcgi",
        params={
            "db": "pubmed",
            "term": term,
            "retmode": "json",
            "retmax": str(retmax),
            "sort": "relevance",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("esearchresult", {}).get("idlist", [])


def _fetch_articles_xml(client: httpx.Client, pmids: List[str]) -> List[Dict[str, str]]:
    if not pmids:
        return []
    resp = client.get(
        f"{EUTILS_BASE}/efetch.fcgi",
        params={
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        },
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.text)

    articles: List[Dict[str, str]] = []
    for pubmed_article in root.findall(".//PubmedArticle"):
        pmid_el = pubmed_article.find(".//MedlineCitation/PMID")
        pmid = pmid_el.text.strip() if pmid_el is not None and pmid_el.text else "N/A"

        title_el = pubmed_article.find(".//Article/ArticleTitle")
        title = "".join(title_el.itertext()).strip() if title_el is not None else "Untitled"

        journal_el = pubmed_article.find(".//Article/Journal/Title")
        journal = journal_el.text.strip() if journal_el is not None and journal_el.text else "PubMed Journal"

        year_el = pubmed_article.find(".//Article/Journal/JournalIssue/PubDate/Year")
        year = year_el.text.strip() if year_el is not None and year_el.text else "2024"

        doi = ""
        for id_el in pubmed_article.findall(".//PubmedData/ArticleIdList/ArticleId"):
            if id_el.attrib.get("IdType") == "doi" and id_el.text:
                doi = id_el.text.strip()
                break

        abstract_parts: List[str] = []
        for abs_el in pubmed_article.findall(".//Article/Abstract/AbstractText"):
            label = abs_el.attrib.get("Label", "")
            txt = "".join(abs_el.itertext()).strip()
            if txt:
                abstract_parts.append(f"{label}: {txt}" if label else txt)

        if not abstract_parts:
            continue

        articles.append(
            {
                "pmid": pmid,
                "doi": doi,
                "title": title,
                "journal": journal,
                "year": year,
                "abstract": " ".join(abstract_parts),
            }
        )
    return articles


def fetch_and_save_pubmed_corpus(
    output_path: Path = PUBMED_OUTPUT_PATH,
    retmax_per_topic: int = 6,
) -> List[GuidelineDocumentInput]:
    documents: List[GuidelineDocumentInput] = []

    with httpx.Client(timeout=25.0, headers={"User-Agent": "NutriEvidenceConsultant/0.1"}) as client:
        for doc_id, title, clinical_domain, query_term in PUBMED_TOPICS:
            pmids = _search_pmids(client, query_term, retmax=retmax_per_topic)
            time.sleep(0.35)  # Respeita o rate limit público da API NCBI Entrez (3 req/s sem API key)
            articles = _fetch_articles_xml(client, pmids)
            time.sleep(0.35)

            sections: List[DocumentSectionInput] = []
            for art in articles:
                doi_str = f" | DOI: {art['doi']}" if art["doi"] else ""
                section_path = f"PMID:{art['pmid']} ({art['journal']}, {art['year']}{doi_str})"
                text_body = f"Estudo: {art['title']} ({section_path}). {art['abstract']}"
                sections.append(
                    DocumentSectionInput(
                        section_path=section_path,
                        text=text_body,
                    )
                )

            if sections:
                documents.append(
                    GuidelineDocumentInput(
                        doc_id=doc_id,
                        title=title,
                        source_organization="PubMed / NCBI Entrez (Meta-Analyses & Systematic Reviews)",
                        publication_year=2024,
                        clinical_domain=clinical_domain,
                        evidence_level="GRADE_A",
                        sections=sections,
                    )
                )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([d.model_dump() for d in documents], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return documents


if __name__ == "__main__":
    docs = fetch_and_save_pubmed_corpus()
    total_articles = sum(len(d.sections) for d in docs)
    total_chars = sum(len(s.text) for d in docs for s in d.sections)
    print(f"Baixados {total_articles} artigos/meta-análises reais do PubMed em {len(docs)} domínios ({total_chars:,} caracteres).")
    print(f"Salvo em: {PUBMED_OUTPUT_PATH}")
