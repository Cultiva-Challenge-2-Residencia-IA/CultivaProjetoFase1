import json
from pathlib import Path
from typing import List

from src.models.schemas import DocumentChunk, GuidelineDocumentInput


class ContextualChunker:
    """Realiza Contextual Chunking preservando metadados clínicos e hierarquia de seções."""

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
                        )
                    )
                    chunk_counter += 1
        return chunks

    def load_and_chunk_json(self, json_path: Path) -> List[DocumentChunk]:
        if json_path.is_dir():
            return self.load_and_chunk_directory(json_path)
        raw_data = json.loads(json_path.read_text(encoding="utf-8"))
        documents = [GuidelineDocumentInput.model_validate(item) for item in raw_data]
        return self.chunk_documents(documents)

    def load_and_chunk_directory(self, dir_path: Path) -> List[DocumentChunk]:
        """Carrega todos os arquivos JSON de diretrizes e evidências científicas da pasta."""
        all_documents: List[GuidelineDocumentInput] = []
        seen_doc_ids = set()
        for json_file in sorted(dir_path.glob("*.json")):
            raw_data = json.loads(json_file.read_text(encoding="utf-8"))
            for item in raw_data:
                doc = GuidelineDocumentInput.model_validate(item)
                if doc.doc_id not in seen_doc_ids:
                    seen_doc_ids.add(doc.doc_id)
                    all_documents.append(doc)
        return self.chunk_documents(all_documents)
