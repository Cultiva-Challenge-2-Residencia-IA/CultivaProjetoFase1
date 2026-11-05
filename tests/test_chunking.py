import unittest

from src.rag.chunking import Chunk, chunk_markdown, normalize_markdown


class ChunkingTests(unittest.TestCase):
    def test_normalize_markdown_removes_artificial_page_noise(self) -> None:
        raw = """
        # Água, Hidratação e Saúde

        [Imagem: página ilustrada sem texto extraível.]
        Página 1
        Texto de exemplo  com  excesso   de espaço.
        """

        normalized = normalize_markdown(raw)

        self.assertIn("Água, Hidratação e Saúde", normalized)
        self.assertNotIn("[Imagem:", normalized)
        self.assertNotIn("Página 1", normalized)
        self.assertNotIn("  com  excesso   de espaço", normalized)

    def test_chunk_markdown_keeps_stable_ids_and_nonempty_chunks(self) -> None:
        text = """
        # Título

        ## Introdução
        Primeiro parágrafo com uma ideia central para nutrição.

        ## Método
        Segundo parágrafo com detalhes adicionais e contexto.

        ## Discussão
        Terceiro parágrafo com a conclusão do texto.
        """

        chunks = chunk_markdown("source-1", text)

        self.assertTrue(chunks)
        self.assertTrue(all(isinstance(chunk, Chunk) for chunk in chunks))
        self.assertTrue(all(chunk.chunk_id for chunk in chunks))
        self.assertTrue(all(chunk.text.strip() for chunk in chunks))
        self.assertEqual(
            [chunk.chunk_id for chunk in chunks],
            [chunk.chunk_id for chunk in chunk_markdown("source-1", text)],
        )

    def test_chunk_markdown_respects_sections(self) -> None:
        text = """
        # A
        ## Seção 1
        Texto seção 1.

        ## Seção 2
        Texto seção 2.
        """

        chunks = chunk_markdown("source-2", text, max_chars=200)

        self.assertEqual(len(chunks), 2)
        self.assertIn("Seção 1", chunks[0].text)
        self.assertIn("Seção 2", chunks[1].text)


if __name__ == "__main__":
    unittest.main()
