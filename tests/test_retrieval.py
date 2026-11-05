import unittest

from src.rag.chunking import Chunk
from src.rag.retriever import EvidenceGate, InMemoryVectorStore, RetrievalResult, hybrid_search


class RetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
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

    def test_hybrid_search_prioritizes_relevant_chunks(self) -> None:
        store = InMemoryVectorStore(self.chunks)
        results = hybrid_search(store, "hidratação e saúde")

        self.assertTrue(results)
        self.assertEqual(results[0].chunk_id, "s1-hidratacao")
        self.assertGreaterEqual(results[0].rrf_score, 0.5)

    def test_evidence_gate_rejects_low_confidence_results(self) -> None:
        gate = EvidenceGate(min_score=0.5)
        result = RetrievalResult(
            chunk_id="x",
            source_id="s4",
            score_dense=0.10,
            score_lexical=0.15,
            rrf_score=0.20,
        )

        self.assertFalse(gate.can_answer([result]))
        self.assertEqual(gate.reason([result]), "não sei")

    def test_evidence_gate_accepts_relevant_result(self) -> None:
        gate = EvidenceGate(min_score=0.5)
        result = RetrievalResult(
            chunk_id="s1-hidratacao",
            source_id="s1",
            score_dense=0.80,
            score_lexical=0.70,
            rrf_score=0.76,
        )

        self.assertTrue(gate.can_answer([result]))
        self.assertEqual(gate.reason([result]), "evidência suficiente")


if __name__ == "__main__":
    unittest.main()
