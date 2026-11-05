import unittest

from src.rag.generator import build_grounded_answer, filter_claims
from src.rag.retriever import RetrievalResult


class GeneratorTests(unittest.TestCase):
    def test_build_grounded_answer_uses_source_and_schema(self) -> None:
        result = RetrievalResult(
            chunk_id="s1-hidratacao",
            source_id="s1",
            score_dense=0.90,
            score_lexical=0.80,
            rrf_score=0.85,
        )
        answer = build_grounded_answer(
            "O que é importante sobre hidratação?",
            [result],
            {
                "s1": {
                    "title": "Água, hidratação e saúde",
                    "section": "Hidratação",
                    "snippet": "Água e hidratação ajudam na saúde e no desempenho físico.",
                }
            },
        )

        self.assertEqual(answer["confianca"], "alta")
        self.assertFalse(answer["recusou"])
        self.assertEqual(answer["sources"][0]["id"], "s1")
        self.assertTrue(answer["claims"])
        self.assertIn("hidratação", answer["answer"].lower())
        self.assertTrue(answer["avisos"])

    def test_build_grounded_answer_returns_nao_sei_when_evidence_is_too_low(self) -> None:
        result = RetrievalResult(
            chunk_id="s9-fraco",
            source_id="s9",
            score_dense=0.05,
            score_lexical=0.10,
            rrf_score=0.12,
        )

        answer = build_grounded_answer("Pergunta fora do corpus", [result], {})

        self.assertEqual(answer["answer"], "não sei")
        self.assertEqual(answer["motivo"], "não sei")
        self.assertFalse(answer["recusou"])
        self.assertEqual(answer["confianca"], "baixa")

    def test_filter_claims_removes_unsupported_statements(self) -> None:
        evidence = "Água e hidratação ajudam na saúde e no desempenho físico."
        claims = [
            {"texto": "Água e hidratação ajudam na saúde e no desempenho físico.", "source_ids": ["s1"], "tipo": "da_fonte"},
            {"texto": "Água cura todas as doenças.", "source_ids": ["s1"], "tipo": "da_fonte"},
        ]

        kept = filter_claims(claims, evidence)

        self.assertEqual(len(kept), 1)
        self.assertIn("saúde", kept[0]["texto"])


if __name__ == "__main__":
    unittest.main()
