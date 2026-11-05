"""Extrator de Trechos a partir do Corpus e manifesto documental de Nutrição.

Converte documentos Markdown revisados (com marcadores <!-- PDF_PAGE: X -->)
e arquivos de diretrizes em instâncias do esquema único Trecho.
Garante a rastreabilidade direta ao PDF original e a conformidade com corpus/manifest.yaml.
"""

from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import yaml

from src.config import PROJECT_ROOT
from src.models.schemas import Trecho


class TrechoCorpusExtractor:
    """Extrai Trechos padronizados a partir das fontes do Corpus de Nutrição."""

    def __init__(self, project_root: Path = PROJECT_ROOT) -> None:
        self.project_root = project_root
        self.manifest_path = project_root / "corpus" / "manifest.yaml"
        self._manifest_sources: Dict[str, Dict[str, Any]] = {}
        self._load_manifest()

    def _load_manifest(self) -> None:
        if not self.manifest_path.exists():
            return
        content = self.manifest_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content) or {}
        for src in data.get("sources", []):
            if "id" in src:
                self._manifest_sources[src["id"]] = src

    def get_source_metadata(self, source_id: str) -> Dict[str, Any]:
        return self._manifest_sources.get(source_id, {})

    def extract_from_markdown(
        self,
        markdown_path: Path,
        max_chars_per_trecho: int = 1200,
        default_approval_status: Optional[str] = None,
    ) -> List[Trecho]:
        """
        Extrai trechos a partir de um arquivo Markdown do corpus/nutricao/markdown/.
        Lê marcadores <!-- PDF_PAGE: X --> e seções (#, ##, ###).
        """
        raw_text = markdown_path.read_text(encoding="utf-8")

        # 1. Parse do Frontmatter (se houver)
        frontmatter_match = re.match(r"^---\n(.*?)\n---\n(.*)$", raw_text, re.DOTALL)
        fm_data: Dict[str, Any] = {}
        content_body = raw_text
        if frontmatter_match:
            try:
                fm_data = yaml.safe_load(frontmatter_match.group(1)) or {}
            except Exception:
                fm_data = {}
            content_body = frontmatter_match.group(2)

        source_id = fm_data.get("source_id", markdown_path.stem)
        manifest_meta = self.get_source_metadata(source_id)

        license_val = (
            fm_data.get("license")
            or manifest_meta.get("license")
            or "CC-BY-NC-SA-4.0"
        )
        approval_status = (
            default_approval_status
            or fm_data.get("approval_status")
            or manifest_meta.get("approval_status")
            or "pendente"
        )
        title = fm_data.get("title") or manifest_meta.get("title") or source_id
        year = fm_data.get("year") or manifest_meta.get("year") or 2014
        institutions = manifest_meta.get("institutions", ["Ministério da Saúde"])
        institution_str = institutions[0] if institutions else "Ministério da Saúde"

        # 2. Iterar linha a linha identificando página e seções
        trechos: List[Trecho] = []
        current_page = 1
        current_section = title
        section_hierarchy: List[str] = [title]

        current_block: List[str] = []
        current_len = 0
        trecho_counter = 1

        def flush_block() -> None:
            nonlocal current_block, current_len, trecho_counter
            if not current_block:
                return
            texto_trecho = " ".join(current_block).strip()
            if len(texto_trecho) >= 30:  # Ignora fragmentos insignificantes
                tid = f"{source_id}_p{current_page:03d}_t{trecho_counter:02d}"
                context_header = (
                    f"[{title} | {institution_str} ({year}) | Seção: {current_section} | "
                    f"p.{current_page} | Licença: {license_val}]"
                )
                trechos.append(
                    Trecho(
                        id=tid,
                        fonte_id=source_id,
                        pagina_pdf=current_page,
                        secao=current_section,
                        texto=texto_trecho,
                        licenca=license_val,
                        approval_status=approval_status,
                        titulo_fonte=title,
                        ano_publicacao=int(year) if str(year).isdigit() else None,
                        instituicao=institution_str,
                        contexto_adicional=f"{context_header}\n{texto_trecho}",
                    )
                )
                trecho_counter += 1
            current_block = []
            current_len = 0

        for line in content_body.splitlines():
            line_str = line.strip()

            # Marcador de página do PDF
            page_match = re.match(r"^<!-- PDF_PAGE:\s*(\d+)\s*-->", line_str)
            if page_match:
                flush_block()
                current_page = int(page_match.group(1))
                continue

            # Cabeçalhos Markdown
            header_match = re.match(r"^(#{1,6})\s+(.*)$", line_str)
            if header_match:
                flush_block()
                level = len(header_match.group(1))
                h_text = header_match.group(2).strip()

                # Ignora cabeçalhos puramente de navegação de página do script de conversão
                if re.match(r"^Página PDF \d+", h_text, re.IGNORECASE):
                    continue

                if level == 1:
                    section_hierarchy = [h_text]
                elif level <= len(section_hierarchy):
                    section_hierarchy = section_hierarchy[: level - 1] + [h_text]
                else:
                    section_hierarchy.append(h_text)
                current_section = " > ".join(section_hierarchy)
                continue

            # Ignora notas de conversão e links isolados
            if line_str.startswith("> **Nota de conversão") or line_str.startswith("[Conferir no original"):
                continue

            # Parágrafos de texto
            if line_str:
                if current_len + len(line_str) + 1 > max_chars_per_trecho:
                    flush_block()
                current_block.append(line_str)
                current_len += len(line_str) + 1
            else:
                if current_len >= 300:
                    flush_block()

        flush_block()
        return trechos
