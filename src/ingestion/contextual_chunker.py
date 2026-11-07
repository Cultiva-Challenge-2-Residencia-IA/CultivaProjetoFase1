import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from src.config import CORPUS_MANIFEST_PATH, CORPUS_RAG_DIR, GUIDELINES_DIR
from src.models.schemas import (
    CuratedSourceRecord,
    DocumentChunk,
    GuidelineDocumentInput,
)

PMID_REGEX = re.compile(r"PMID:(\d+)")
DOI_REGEX = re.compile(r"DOI:\s*([^\s\)]+)")
STUDY_TITLE_REGEX = re.compile(r"^Estudo:\s*(.+?)\s*\(PMID:\d+")
PAGE_REGEX = re.compile(r"P[áa]gs?\.\s*(\d+)")

CORPUS_SOURCE_DOMAIN_MAP: Dict[str, tuple[str, str]] = {
    "guia-alimentar-populacao-brasileira-2014": (
        "Diretrizes Alimentares Oficiais, Classificação NOVA e Comensalidade",
        "GUIDELINE_CONSENSUS",
    ),
    "protocolos-guia-alimentar-fasciculo1-2021": (
        "Protocolos de Uso Clínico do Guia Alimentar para Adultos na Atenção Primária",
        "GUIDELINE_CONSENSUS",
    ),
    "martins-ultraprocessados-rsp-2013": (
        "Epidemiologia Nutricional, Classificação NOVA e Consumo de Ultraprocessados no Brasil",
        "GRADE_B",
    ),
    "souza-backes-universitarios-csc-2020": (
        "Comportamento Alimentar de Universitários e Adesão aos Dez Passos do Guia Alimentar",
        "GRADE_B",
    ),
    "guia-dietas-vegetarianas-svb-2012": (
        "Planejamento Nutricional e Biodisponibilidade em Dietas Vegetarianas e Veganas",
        "GUIDELINE_CONSENSUS",
    ),
    "moreira-rodrigues-conhecimento-nutricional-suplementacao-2014": (
        "Suplementação Alimentar em Praticantes de Exercício Físico e Orientação Profissional",
        "GRADE_C",
    ),
}


class ContextualChunker:
    """
    Realiza Contextual Chunking (Page-Aware & Section-Aware + Injeção de Cabeçalho Contextual)
    preservando metadados clínicos, hierarquia de seções, página física do PDF, PMID/DOI e licença.
    """

    def __init__(self, max_chars_per_chunk: int = 1200) -> None:
        self.max_chars_per_chunk = max_chars_per_chunk

    @staticmethod
    def build_context_header(
        title: str,
        source_organization: str,
        publication_year: int,
        clinical_domain: str,
        evidence_level: str,
        section_path: str,
    ) -> str:
        return (
            f"[Documento: {title} | Fonte: {source_organization} ({publication_year}) | "
            f"Domínio: {clinical_domain} | Nível de Evidência: {evidence_level} | "
            f"Seção: {section_path}]"
        )

    def _split_long_text(self, text: str) -> List[str]:
        cleaned = text.strip()
        if len(cleaned) <= self.max_chars_per_chunk:
            return [cleaned]

        sentences = [s.strip() for s in cleaned.split(". ") if s.strip()]
        sub_chunks: List[str] = []
        current: List[str] = []
        current_len = 0

        for sentence in sentences:
            formatted = sentence if sentence.endswith(".") else f"{sentence}."
            if current and current_len + len(formatted) + 1 > self.max_chars_per_chunk:
                sub_chunks.append(" ".join(current))
                current = [formatted]
                current_len = len(formatted)
            else:
                current.append(formatted)
                current_len += len(formatted) + 1

        if current:
            sub_chunks.append(" ".join(current))

        return sub_chunks

    @staticmethod
    def _extract_traceability_metadata(
        doc: GuidelineDocumentInput, section_path: str, raw_text: str
    ) -> Dict[str, Any]:
        """Extrai metadados granulares de rastreabilidade (PMID, DOI, URL oficial, página e licença)."""
        page_match = PAGE_REGEX.search(section_path)
        page_num = int(page_match.group(1)) if page_match else None

        if doc.doc_id.startswith("GUIA_MS_"):
            return {
                "source_id": "guia-alimentar-populacao-brasileira-2014",
                "source_url": "https://bvsms.saude.gov.br/bvs/publicacoes/guia_alimentar_populacao_brasileira_2ed.pdf",
                "license": "CC-BY-NC-SA-4.0",
                "review_status": "pendente",
                "page_number": page_num,
            }

        pmid_match = PMID_REGEX.search(section_path)
        if pmid_match:
            pmid = pmid_match.group(1)
            doi_match = DOI_REGEX.search(section_path)
            doi = doi_match.group(1).rstrip(".,;)") if doi_match else None
            url = (
                f"https://doi.org/{doi}"
                if doi
                else f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            )
            return {
                "source_id": f"PMID:{pmid}",
                "source_url": url,
                "license": "pendente (PubMed/NCBI Entrez Abstract)",
                "review_status": "pendente",
                "page_number": None,
            }

        return {
            "source_id": doc.doc_id,
            "source_url": f"urn:cultiva:guideline-synthesis:{doc.doc_id}",
            "license": "Síntese normativa interna baseada em diretrizes públicas",
            "review_status": "pendente",
            "page_number": page_num,
        }

    def chunk_documents(self, documents: List[GuidelineDocumentInput]) -> List[DocumentChunk]:
        chunks: List[DocumentChunk] = []
        for doc in documents:
            chunk_counter = 1
            for section in doc.sections:
                header = self.build_context_header(
                    title=doc.title,
                    source_organization=doc.source_organization,
                    publication_year=doc.publication_year,
                    clinical_domain=doc.clinical_domain,
                    evidence_level=doc.evidence_level,
                    section_path=section.section_path,
                )
                trace_meta = self._extract_traceability_metadata(
                    doc, section.section_path, section.text
                )
                for part in self._split_long_text(section.text):
                    chunk_id = f"{doc.doc_id}_C{chunk_counter:02d}"
                    contextualized = f"{header}\n{part}"
                    chunks.append(
                        DocumentChunk(
                            chunk_id=chunk_id,
                            doc_id=doc.doc_id,
                            title=doc.title,
                            source_organization=doc.source_organization,
                            publication_year=doc.publication_year,
                            clinical_domain=doc.clinical_domain,
                            evidence_level=doc.evidence_level,
                            section_path=section.section_path,
                            raw_text=part,
                            contextualized_text=contextualized,
                            source_id=trace_meta["source_id"],
                            source_url=trace_meta["source_url"],
                            license=trace_meta["license"],
                            review_status=trace_meta["review_status"],
                            page_number=trace_meta["page_number"],
                        )
                    )
                    chunk_counter += 1
        return chunks

    def load_corpus_rag_jsonl(
        self,
        corpus_rag_dir: Path = CORPUS_RAG_DIR,
        manifest_path: Path = CORPUS_MANIFEST_PATH,
        exclude_guia_duplicate: bool = True,
    ) -> List[DocumentChunk]:
        """
        Carrega os trechos curados em corpus/nutricao/rag/*.jsonl gerados pelo pipeline
        auditável (prepare_rag.py) a partir dos PDFs de corpus/manifest.yaml.
        """
        if not corpus_rag_dir.exists() or not manifest_path.exists():
            return []

        manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        manifest_map: Dict[str, Dict[str, Any]] = {
            s["id"]: s for s in manifest_data.get("sources", []) if "id" in s
        }

        corpus_chunks: List[DocumentChunk] = []

        for jsonl_file in sorted(corpus_rag_dir.glob("*.jsonl")):
            lines = [
                json.loads(line)
                for line in jsonl_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            if not lines:
                continue

            fonte_id = lines[0].get("fonte_id", "")
            # O Guia Alimentar 2014 já está estruturado por capítulos em guia_alimentar_ms_2ed.json
            if exclude_guia_duplicate and fonte_id == "guia-alimentar-populacao-brasileira-2014":
                continue

            meta = manifest_map.get(fonte_id, {})
            institutions = ", ".join(meta.get("institutions", ["Fonte Oficial"]))
            year = int(meta.get("year", 2021))
            source_url = str(meta.get("source", ""))
            domain, ev_level = CORPUS_SOURCE_DOMAIN_MAP.get(
                fonte_id,
                ("Nutrição Baseada em Evidências", "GUIDELINE_CONSENSUS"),
            )
            doc_id = f"CORPUS_{fonte_id.upper().replace('-', '_')}"

            # Agrupa trechos curtos da mesma página/seção até max_chars_per_chunk
            grouped_records: List[Dict[str, Any]] = []
            for rec in lines:
                sec = str(rec.get("secao", "")).strip()
                txt = str(rec.get("texto", "")).strip()
                pag = int(rec.get("pagina_pdf", 1))
                # Ignora páginas iniciais de expediente/ficha catalográfica sem seção
                if pag <= 3 and not sec and len(lines) > 15:
                    continue
                if len(txt) < 40:
                    continue

                if (
                    grouped_records
                    and grouped_records[-1]["pagina_pdf"] == pag
                    and grouped_records[-1]["secao"] == sec
                    and len(grouped_records[-1]["texto"]) + len(txt) + 2 <= self.max_chars_per_chunk
                ):
                    grouped_records[-1]["texto"] += "\n" + txt
                else:
                    grouped_records.append(
                        {
                            "id": rec["id"],
                            "titulo_fonte": rec["titulo_fonte"],
                            "pagina_pdf": pag,
                            "secao": sec or "Texto Principal",
                            "texto": txt,
                            "licenca": rec.get("licenca", meta.get("license", "pendente")),
                            "review_status": rec.get("review_status", "pendente"),
                        }
                    )

            for idx, grp in enumerate(grouped_records, start=1):
                section_label = f"{grp['secao']} > Pág. PDF {grp['pagina_pdf']}"
                header = self.build_context_header(
                    title=grp["titulo_fonte"],
                    source_organization=institutions,
                    publication_year=year,
                    clinical_domain=domain,
                    evidence_level=ev_level,
                    section_path=section_label,
                )
                chunk_id = f"{doc_id}_C{idx:02d}"
                corpus_chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        doc_id=doc_id,
                        title=grp["titulo_fonte"],
                        source_organization=institutions,
                        publication_year=year,
                        clinical_domain=domain,
                        evidence_level=ev_level,  # type: ignore[arg-type]
                        section_path=section_label,
                        raw_text=grp["texto"],
                        contextualized_text=f"{header}\n{grp['texto']}",
                        source_id=fonte_id,
                        source_url=source_url,
                        license=str(grp["licenca"]),
                        review_status=str(grp["review_status"]),
                        page_number=int(grp["pagina_pdf"]),
                    )
                )

        return corpus_chunks

    def load_and_chunk_json(self, json_path: Path) -> List[DocumentChunk]:
        if json_path.is_dir():
            return self.load_and_chunk_directory(json_path)
        raw_data = json.loads(json_path.read_text(encoding="utf-8"))
        documents = [GuidelineDocumentInput.model_validate(item) for item in raw_data]
        return self.chunk_documents(documents)

    def load_and_chunk_directory(
        self,
        dir_path: Path = GUIDELINES_DIR,
        include_corpus_rag: bool = True,
    ) -> List[DocumentChunk]:
        """
        Carrega todos os documentos científicos de data/raw/guidelines/ e une com
        os documentos curados de corpus/nutricao/rag/*.jsonl (catálogo manifest.yaml).
        """
        all_documents: List[GuidelineDocumentInput] = []
        seen_doc_ids = set()
        for json_file in sorted(dir_path.glob("*.json")):
            raw_data = json.loads(json_file.read_text(encoding="utf-8"))
            for item in raw_data:
                doc = GuidelineDocumentInput.model_validate(item)
                if doc.doc_id not in seen_doc_ids:
                    seen_doc_ids.add(doc.doc_id)
                    all_documents.append(doc)

        chunks = self.chunk_documents(all_documents)
        if include_corpus_rag:
            chunks.extend(self.load_corpus_rag_jsonl())
        return chunks

    @staticmethod
    def get_curated_sources_inventory(
        chunks: List[DocumentChunk],
    ) -> List[CuratedSourceRecord]:
        """
        Consolida o inventário auditável de documentos-fonte únicos na base de conhecimento,
        individualizando os 6 documentos oficiais em PDF de corpus/manifest.yaml, os 34 artigos
        reais indexados do PubMed (PMID/DOI) e as sínteses de diretrizes clínicas.
        """
        inventory_map: Dict[str, CuratedSourceRecord] = {}

        for c in chunks:
            src_id = c.source_id or c.doc_id
            if src_id not in inventory_map:
                if src_id.startswith("PMID:"):
                    study_match = STUDY_TITLE_REGEX.search(c.raw_text)
                    study_title = study_match.group(1) if study_match else c.title
                    year_match = re.search(r",\s*(20\d{2}|19\d{2})", c.section_path)
                    pub_year = int(year_match.group(1)) if year_match else c.publication_year
                    src_type = "PUBMED_PEER_REVIEWED"
                elif c.source_url and not c.source_url.startswith("urn:"):
                    study_title = (
                        "Guia Alimentar para a População Brasileira (2ª Edição)"
                        if src_id == "guia-alimentar-populacao-brasileira-2014"
                        else c.title
                    )
                    pub_year = c.publication_year
                    src_type = "PDF_OFICIAL_CORPUS"
                else:
                    study_title = c.title
                    pub_year = c.publication_year
                    src_type = "CLINICAL_SYNTHESIS"

                inventory_map[src_id] = CuratedSourceRecord(
                    source_id=src_id,
                    doc_id=c.doc_id,
                    title=study_title,
                    source_organization=c.source_organization,
                    publication_year=pub_year,
                    clinical_domain=c.clinical_domain,
                    evidence_level=c.evidence_level,
                    source_url=c.source_url or "",
                    license=c.license or "pendente",
                    review_status=c.review_status or "pendente",
                    source_type=src_type,  # type: ignore[arg-type]
                    chunks_count=1,
                )
            else:
                inventory_map[src_id].chunks_count += 1

        return list(inventory_map.values())
