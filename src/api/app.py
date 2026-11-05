from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from uuid import uuid4

from src.guardrails.injection import PromptInjectionGuard
from src.guardrails.prescricao import ScopeGate
from src.guardrails.risco import RiskGate
from src.rag.chunking import Chunk
from src.rag.generator import build_grounded_answer
from src.rag.retriever import InMemoryVectorStore, hybrid_search


class NutritionAPI:
    def __init__(self) -> None:
        self.risk_gate = RiskGate()
        self.scope_gate = ScopeGate()
        self.injection_gate = PromptInjectionGuard()
        self.chunks = [
            Chunk(
                source_id="s1",
                section="Hidratação",
                text="Água e hidratação ajudam na saúde e no desempenho físico.",
                chunk_id="s1-hidratacao",
            ),
            Chunk(
                source_id="s2",
                section="Depressão",
                text="Sintomas depressivos podem piorar o comportamento alimentar e a compulsão.",
                chunk_id="s2-depressao",
            ),
            Chunk(
                source_id="s3",
                section="Sono",
                text="O sono adequado favorece melhor regulação emocional e controle alimentar.",
                chunk_id="s3-sono",
            ),
        ]
        self.source_map = {
            "s1": {
                "title": "Água, hidratação e saúde",
                "section": "Hidratação",
                "snippet": "Água e hidratação ajudam na saúde e no desempenho físico.",
            },
            "s2": {
                "title": "Relação entre humor e alimentação",
                "section": "Depressão",
                "snippet": "Sintomas depressivos podem piorar o comportamento alimentar e a compulsão.",
            },
            "s3": {
                "title": "Sono e regulação emocional",
                "section": "Sono",
                "snippet": "O sono adequado favorece melhor regulação emocional e controle alimentar.",
            },
        }
        self.store = InMemoryVectorStore(self.chunks)

    def _trace_id(self) -> str:
        return f"trace-{uuid4().hex[:12]}"

    def _refuse(self, answer: str, motivo: str, *, risk: bool = False) -> dict[str, Any]:
        return {
            "answer": answer,
            "claims": [],
            "sources": [],
            "confianca": "baixa",
            "recusou": True,
            "motivo": motivo,
            "avisos": ["AVISO: Este conteúdo não pode substituir orientação profissional qualificada."],
            "trace_id": self._trace_id(),
        }

    def health(self) -> dict[str, Any]:
        return {"status": "ok"}

    def ask(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        data = payload or {}
        question = str(data.get("question", "")).strip()

        if not question:
            return {
                "answer": "não sei",
                "claims": [],
                "sources": [],
                "confianca": "baixa",
                "recusou": False,
                "motivo": "não sei",
                "avisos": ["AVISO: Este conteúdo não pode substituir orientação profissional qualificada."],
                "trace_id": self._trace_id(),
            }

        if self.injection_gate.should_block(question):
            return self._refuse(
                "Não posso seguir instruções que tentem ignorar regras do sistema ou expor o prompt.",
                "prompt injection",
            )

        if self.risk_gate.should_block(question):
            return self._refuse(
                "Não posso responder a sinais de risco sem apoio profissional. Procure ajuda imediata ou ligue para o CVV 188.",
                "risco",
                risk=True,
            )

        if self.scope_gate.should_block(question):
            return self._refuse(
                "Não posso atender uma prescrição de dieta, suplemento ou plano alimentar. Posso orientar sobre princípios gerais de nutrição e hidratação.",
                "escopo fora do permitido",
            )

        results = hybrid_search(self.store, question, top_k=3)
        answer = build_grounded_answer(question, results, self.source_map)
        if answer.get("answer") == "não sei":
            answer["recusou"] = False
        return answer

    def feedback(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        data = payload or {}
        question = str(data.get("question", "")).strip()
        answer = str(data.get("answer", "")).strip()
        correct = bool(data.get("correct", False))
        if not question and not answer:
            return {"status": "rejected", "saved": False, "reason": "empty payload"}
        return {"status": "accepted", "saved": True, "correct": correct}


class NutritionRequestHandler(BaseHTTPRequestHandler):
    server_version = "NutritionAPI/1.0"

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send_json(200, self.server.api.health())
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed_path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {}

        if parsed_path == "/v1/nutricao/perguntar":
            self._send_json(200, self.server.api.ask(payload))
            return
        if parsed_path == "/v1/feedback":
            self._send_json(200, self.server.api.feedback(payload))
            return
        self._send_json(404, {"error": "not found"})

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


def run_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), NutritionRequestHandler)
    server.api = NutritionAPI()
    print(f"Nutrition API running on http://{host}:{port}")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="CULTIVA nutrition API")
    parser.add_argument("command", choices=["health", "ask", "server"], help="Command to run")
    parser.add_argument("--question", default="", help="Question to ask when using the ask command")
    parser.add_argument("--host", default="0.0.0.0", help="Host for the HTTP server")
    parser.add_argument("--port", type=int, default=8000, help="Port for the HTTP server")
    args = parser.parse_args()

    api = NutritionAPI()
    if args.command == "health":
        print(json.dumps(api.health(), ensure_ascii=False, indent=2))
        return
    if args.command == "ask":
        payload = {"question": args.question}
        print(json.dumps(api.ask(payload), ensure_ascii=False, indent=2))
        return
    run_server(args.host, args.port)


if __name__ == "__main__":
    main()
