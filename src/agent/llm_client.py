import json
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

from src.config import (
    ALLOW_EXTERNAL_LLM,
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GROQ_FALLBACK_MODEL,
    GROQ_MODEL,
    GROQ_TIMEOUT,
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_FALLBACK_MODEL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT,
)
from src.models.schemas import RetrievedChunk

SYSTEM_PROMPT_CONSULTANT = """Você é um Consultor Científico de Nutrição Baseado em Evidências.
Sua função é responder dúvidas gerais de nutrição baseando-se EXCLUSIVAMENTE nos trechos de diretrizes clínicas e estudos científicos fornecidos no contexto.

REGRAS OBRIGATÓRIAS DE CONFORMIDADE LEGAL (Lei Federal nº 8.234/1991 - CFN):
1. NUNCA prescreva dietas, cardápios, quantidades em gramas personalizadas ou horários de refeições para o indivíduo.
2. NUNCA faça diagnóstico clínico ou prescreva posologia individualizada de suplementos.
3. Apresente apenas o que os estudos clínicos e diretrizes mostram em nível populacional, explicando o mecanismo fisiológico, o grau de evidência (GRADE) e os alimentos ou compostos estudados.

Responda ESTRITAMENTE em formato JSON válido com as seguintes chaves:
{
  "evidence_summary": "Síntese clara e direta do que a evidência científica mostra",
  "physiological_mechanism": "Explicação detalhada do mecanismo bioquímico/fisiológico descrito nas fontes",
  "protocol_findings": "O que dizem os protocolos clínicos, faixas populacionais estudadas e ressalvas/contraindicações",
  "food_sources_or_compounds": ["lista de alimentos ou compostos bioativos citados nos trechos"],
  "evidence_grade": "Grau de evidência predominante nas fontes (ex: GRADE_A, GRADE_B, GUIDELINE_CONSENSUS)"
}"""

_PERSONAL_DATA_PATTERNS = (
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)"),
    re.compile(r"(?<!\d)(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?9?\d{4}[-.\s]?\d{4}(?!\d)"),
    re.compile(
        r"(?i)(\b(?:meu nome(?: completo)?(?: é|:)|me chamo|chamo-me)\s+)"
        r"[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-öø-ÿ'-]*(?:\s+[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-öø-ÿ'-]*){0,3}"
    ),
)


def mask_personal_data(text: str) -> str:
    """Mask common direct identifiers before sending a prompt to an external provider."""
    masked = text
    for pattern in _PERSONAL_DATA_PATTERNS:
        masked = pattern.sub("[DADO PESSOAL REMOVIDO]", masked)
    return masked


class LocalLLMClient:
    """Cliente Ollama local, com Groq externa opcional e fallback extrativo."""

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        primary_model: str = OLLAMA_MODEL,
        fallback_model: str = OLLAMA_FALLBACK_MODEL,
        timeout: float = OLLAMA_TIMEOUT,
        enable_ollama: bool = True,
        provider: str = LLM_PROVIDER,
        groq_api_key: str = GROQ_API_KEY,
        groq_base_url: str = GROQ_BASE_URL,
        groq_model: str = GROQ_MODEL,
        groq_fallback_model: str = GROQ_FALLBACK_MODEL,
        groq_timeout: float = GROQ_TIMEOUT,
        enable_groq: Optional[bool] = None,
        allow_external_llm: bool = ALLOW_EXTERNAL_LLM,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.timeout = timeout
        self.enable_ollama = enable_ollama

        self.provider = provider.lower()
        self.groq_api_key = groq_api_key.strip()
        self.groq_base_url = groq_base_url.rstrip("/")
        self.groq_model = groq_model
        self.groq_fallback_model = groq_fallback_model
        self.groq_timeout = groq_timeout
        self.enable_groq = enable_ollama if enable_groq is None else enable_groq
        self.allow_external_llm = allow_external_llm

    def is_groq_available(self) -> bool:
        return bool(self.allow_external_llm and self.enable_groq and self.groq_api_key)

    def is_ollama_available(self) -> bool:
        if not self.enable_ollama:
            return False
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    def _build_user_prompt(
        self,
        query: str,
        retrieved_chunks: List[RetrievedChunk],
        taco_context_str: str = "",
        graph_context_str: str = "",
    ) -> str:
        context_blocks: List[str] = []
        for idx, item in enumerate(retrieved_chunks, start=1):
            c = item.chunk
            context_blocks.append(
                f"--- FONTE {idx} ({c.doc_id} | {c.source_organization}, {c.publication_year} | "
                f"Evidência: {c.evidence_level} | Seção: {c.section_path}) ---\n{c.raw_text}"
            )
        joined_context = "\n\n".join(context_blocks)
        taco_section = f"\n\n{taco_context_str}\n" if taco_context_str else ""
        graph_section = f"\n\n{graph_context_str}\n" if graph_context_str else ""
        return (
            f"PERGUNTA DE CONSULTA NUTRICIONAL:\n{query}\n\n"
            f"EVIDÊNCIAS RECUPERADAS PELO RAG HÍBRIDO:\n{joined_context}{taco_section}{graph_section}\n\n"
            "Elabore a resposta em JSON seguindo rigorosamente o esquema solicitado e usando os termos técnicos, cadeias do Grafo Causal e valores da Tabela TACO presentes nas fontes."
        )

    def _call_groq_model(self, model_name: str, user_prompt: str) -> Optional[Dict[str, Any]]:
        if not self.groq_api_key:
            return None
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_CONSULTANT},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }
        try:
            with httpx.Client(timeout=self.groq_timeout) as client:
                response = client.post(
                    f"{self.groq_base_url}/chat/completions",
                    headers=headers,
                    json={
                        **payload,
                        "messages": [
                            {"role": message["role"], "content": mask_personal_data(message["content"])}
                            for message in payload["messages"]
                        ],
                    },
                )
                response.raise_for_status()
                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    return None
                content = choices[0].get("message", {}).get("content", "")
                parsed = json.loads(content)
                if isinstance(parsed, dict) and "evidence_summary" in parsed:
                    return parsed
        except Exception:
            return None
        return None

    def _call_ollama_model(self, model_name: str, user_prompt: str) -> Optional[Dict[str, Any]]:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_CONSULTANT},
                {"role": "user", "content": user_prompt},
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1,
            },
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                content = data.get("message", {}).get("content", "")
                parsed = json.loads(content)
                if isinstance(parsed, dict) and "evidence_summary" in parsed:
                    return parsed
        except Exception:
            return None
        return None

    @staticmethod
    def _extract_food_and_compounds(texts: List[str]) -> List[str]:
        candidates = [
            "Aveia (beta-glucana)",
            "Psyllium",
            "Feijão e leguminosas",
            "Arroz com feijão (lisina + metionina)",
            "Azeite de oliva extravirgem (MUFA)",
            "Fitoesteróis vegetais",
            "Peixes marinhos (EPA e DHA - Ômega-3)",
            "Beterraba e folhosos verdes (nitratos inorgânicos)",
            "Cúrcuma (curcumina) + Pimenta-do-reino (piperina)",
            "Chá verde (catequina EGCG)",
            "Brócolis e crucíferas (sulforafano / glicorafanina)",
            "Frutas cítricas (Vitamina C / ácido ascórbico)",
            "Creatina monohidratada",
            "Cafeína",
            "Whey Protein / Fontes proteicas ricas em leucina",
        ]
        combined = " ".join(texts).lower()
        found: List[str] = []
        trigger_map = {
            "Aveia (beta-glucana)": ["beta-glucana", "aveia"],
            "Psyllium": ["psyllium"],
            "Feijão e leguminosas": ["feijao", "feijão", "leguminosas", "lentilha"],
            "Arroz com feijão (lisina + metionina)": ["lisina", "metionina"],
            "Azeite de oliva extravirgem (MUFA)": ["azeite", "monoinsaturados"],
            "Fitoesteróis vegetais": ["fitoesterois", "fitoesteróis"],
            "Peixes marinhos (EPA e DHA - Ômega-3)": ["epa", "dha", "sardinha", "salmao", "salmão"],
            "Beterraba e folhosos verdes (nitratos inorgânicos)": ["beterraba", "nitrato"],
            "Cúrcuma (curcumina) + Pimenta-do-reino (piperina)": ["curcumina", "piperina"],
            "Chá verde (catequina EGCG)": ["egcg", "cha verde", "chá verde"],
            "Brócolis e crucíferas (sulforafano / glicorafanina)": ["sulforafano", "glicorafanina", "mirosinase"],
            "Frutas cítricas (Vitamina C / ácido ascórbico)": ["acido ascorbico", "ácido ascórbico", "vitamina c"],
            "Creatina monohidratada": ["fosfocreatina", "creatina"],
            "Cafeína": ["adenosina", "cyp1a2", "cafeina", "cafeína"],
            "Whey Protein / Fontes proteicas ricas em leucina": ["leucina", "mtorc1", "whey"],
        }
        for label in candidates:
            triggers = trigger_map.get(label, [])
            if any(t in combined for t in triggers):
                found.append(label)
        return found[:6]

    def synthesize_extractive_fallback(
        self,
        query: str,
        retrieved_chunks: List[RetrievedChunk],
        taco_context_str: str = "",
        graph_context_str: str = "",
    ) -> Dict[str, Any]:
        """Síntese estruturada determinística baseada nos chunks recuperados, Grafo de 4 Camadas e Tabela TACO."""
        if not retrieved_chunks:
            return {
                "evidence_summary": "Não foram encontradas evidências específicas na base para a consulta informada.",
                "physiological_mechanism": graph_context_str or "Mecanismo não disponível nos trechos recuperados.",
                "protocol_findings": taco_context_str or "Consulte diretrizes clínicas adicionais.",
                "food_sources_or_compounds": [],
                "evidence_grade": "N/A",
            }

        top_chunk = retrieved_chunks[0].chunk
        raw_texts = [item.chunk.raw_text for item in retrieved_chunks]

        summary_sentences: List[str] = []
        mechanism_sentences: List[str] = []
        protocol_sentences: List[str] = []

        mechanism_Regex = re.compile(
            r"(mecanismo|viscosidade|receptor|enzima|absor|fermenta|butirato|atp|fosfocreatina|"
            r"mtorc1|leucina|adenosina|glicuronida|mirosinase|oxido nitrico|leptina|grelina|"
            r"retrograda|quelato|fe2\+|ppar|micela|lisina|metionina)",
            re.IGNORECASE,
        )
        protocol_Regex = re.compile(
            r"(protocolo|diretriz|ensaio|meta-analise|meta-análise|grade|g/dia|mg/dia|g/kg|"
            r"contraindica|cautela|renal|creatinina|cistatina|horas|resfriamento)",
            re.IGNORECASE,
        )

        for text in raw_texts[:3]:
            for sent in [s.strip() for s in text.split(". ") if s.strip()]:
                clean_sent = sent if sent.endswith(".") else f"{sent}."
                if mechanism_Regex.search(clean_sent) and len(mechanism_sentences) < 5:
                    mechanism_sentences.append(clean_sent)
                if protocol_Regex.search(clean_sent) and len(protocol_sentences) < 5:
                    protocol_sentences.append(clean_sent)
                if len(summary_sentences) < 4:
                    summary_sentences.append(clean_sent)

        if not mechanism_sentences:
            mechanism_sentences = [top_chunk.raw_text]
        if not protocol_sentences:
            protocol_sentences = [item.chunk.raw_text for item in retrieved_chunks[:2]]

        mechanism_text = " ".join(mechanism_sentences)
        if graph_context_str:
            mechanism_text = f"{mechanism_text}\n\n{graph_context_str}"

        protocol_text = " ".join(protocol_sentences)
        if taco_context_str:
            protocol_text = f"{protocol_text}\n\n{taco_context_str}"

        grades = [item.chunk.evidence_level for item in retrieved_chunks]
        best_grade = "GRADE_A" if "GRADE_A" in grades else top_chunk.evidence_level

        return {
            "evidence_summary": " ".join(summary_sentences),
            "physiological_mechanism": mechanism_text,
            "protocol_findings": protocol_text,
            "food_sources_or_compounds": self._extract_food_and_compounds(raw_texts),
            "evidence_grade": best_grade,
        }

    @staticmethod
    def _merge_llm_with_extractive(
        llm_result: Dict[str, Any],
        extractive: Dict[str, Any],
        taco_context_str: str = "",
    ) -> Dict[str, Any]:
        llm_protocol = str(
            llm_result.get("protocol_findings") or extractive["protocol_findings"]
        )
        if taco_context_str and "TABELA TACO" not in llm_protocol:
            llm_protocol = f"{llm_protocol}\n\n{taco_context_str}"
        return {
            "evidence_summary": str(
                llm_result.get("evidence_summary") or extractive["evidence_summary"]
            ),
            "physiological_mechanism": (
                f"{llm_result.get('physiological_mechanism', '')} "
                f"({extractive['physiological_mechanism']})"
            ).strip(),
            "protocol_findings": llm_protocol,
            "food_sources_or_compounds": (
                llm_result.get("food_sources_or_compounds")
                if isinstance(llm_result.get("food_sources_or_compounds"), list)
                and llm_result.get("food_sources_or_compounds")
                else extractive["food_sources_or_compounds"]
            ),
            "evidence_grade": str(
                llm_result.get("evidence_grade") or extractive["evidence_grade"]
            ),
        }

    def generate_structured_synthesis(
        self,
        query: str,
        retrieved_chunks: List[RetrievedChunk],
        taco_context_str: str = "",
        graph_context_str: str = "",
    ) -> Tuple[Dict[str, Any], str]:
        """
        Gera a síntese localmente por padrão; Groq exige opt-in explícito e
        a síntese extrativa determinística permanece como fallback final.
        """
        extractive = self.synthesize_extractive_fallback(
            query,
            retrieved_chunks,
            taco_context_str=taco_context_str,
            graph_context_str=graph_context_str,
        )

        groq_ready = self.provider in ("groq", "auto") and self.is_groq_available()
        ollama_ready = self.provider in ("ollama", "auto", "groq") and self.is_ollama_available()

        if not groq_ready and not ollama_ready:
            return extractive, "local_extractive_synthesis"

        user_prompt = self._build_user_prompt(
            query,
            retrieved_chunks,
            taco_context_str=taco_context_str,
            graph_context_str=graph_context_str,
        )

        # 1. Tenta Groq somente quando o envio externo foi explicitamente habilitado.
        if groq_ready:
            for model_name in [self.groq_model, self.groq_fallback_model]:
                if not model_name:
                    continue
                llm_result = self._call_groq_model(model_name, user_prompt)
                if llm_result:
                    merged = self._merge_llm_with_extractive(
                        llm_result, extractive, taco_context_str
                    )
                    return merged, f"groq:{model_name}"

        # 2. Fallback para Ollama local caso configurado/disponível
        if ollama_ready:
            for model_name in [self.primary_model, self.fallback_model]:
                if not model_name:
                    continue
                llm_result = self._call_ollama_model(model_name, user_prompt)
                if llm_result:
                    merged = self._merge_llm_with_extractive(
                        llm_result, extractive, taco_context_str
                    )
                    return merged, f"ollama:{model_name}"

        return extractive, "local_extractive_synthesis"
