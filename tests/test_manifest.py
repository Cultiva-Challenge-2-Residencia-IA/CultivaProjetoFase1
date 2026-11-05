import tempfile
import unittest
from pathlib import Path

from src.rag.manifest import ManifestError, load_manifest


class ManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name) / "corpus"
        (self.root / "nutricao").mkdir(parents=True)
        self.manifest_path = self.root / "manifest.yaml"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_manifest(self, content: str) -> None:
        self.manifest_path.write_text(content, encoding="utf-8")

    def test_empty_manifest_does_not_authorize_discovered_documents(self) -> None:
        (self.root / "nutricao" / "unlisted.md").write_text("texto", encoding="utf-8")
        self.write_manifest("version: 1\nsources: []\n")

        self.assertEqual(load_manifest(self.manifest_path), ())

    def test_null_metadata_is_preserved_for_an_explicit_source(self) -> None:
        (self.root / "nutricao" / "source.md").write_text("texto", encoding="utf-8")
        self.write_manifest(
            "version: 1\nsources:\n"
            "  - id: source-1\n"
            "    path: nutricao/source.md\n"
            "    title: null\n"
            "    publisher: null\n"
            "    type: null\n"
            "    url: null\n"
            "    license: null\n"
            "    data_publicacao: null\n"
        )

        sources = load_manifest(self.manifest_path)

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].id, "source-1")
        self.assertIsNone(sources[0].license)

    def test_duplicate_source_ids_are_rejected(self) -> None:
        source = (
            "    path: nutricao/source.md\n"
            "    title: null\n"
            "    publisher: null\n"
            "    type: null\n"
            "    url: null\n"
            "    license: null\n"
            "    data_publicacao: null\n"
        )
        (self.root / "nutricao" / "source.md").write_text("texto", encoding="utf-8")
        self.write_manifest(
            "version: 1\nsources:\n  - id: duplicate\n"
            + source
            + "  - id: duplicate\n"
            + source
        )

        with self.assertRaises(ManifestError):
            load_manifest(self.manifest_path)

    def test_path_outside_corpus_is_rejected(self) -> None:
        (self.root.parent / "outside.md").write_text("texto", encoding="utf-8")
        self.write_manifest(
            "version: 1\nsources:\n"
            "  - id: outside\n"
            "    path: ../outside.md\n"
            "    title: null\n"
            "    publisher: null\n"
            "    type: null\n"
            "    url: null\n"
            "    license: null\n"
            "    data_publicacao: null\n"
        )

        with self.assertRaises(ManifestError):
            load_manifest(self.manifest_path)

    def test_missing_source_file_is_rejected(self) -> None:
        self.write_manifest(
            "version: 1\nsources:\n"
            "  - id: missing\n"
            "    path: nutricao/missing.md\n"
            "    title: null\n"
            "    publisher: null\n"
            "    type: null\n"
            "    url: null\n"
            "    license: null\n"
            "    data_publicacao: null\n"
        )

        with self.assertRaises(ManifestError):
            load_manifest(self.manifest_path)

    def test_source_path_is_required(self) -> None:
        self.write_manifest(
            "version: 1\nsources:\n"
            "  - id: missing-path\n"
            "    title: null\n"
            "    publisher: null\n"
            "    type: null\n"
            "    url: null\n"
            "    license: null\n"
            "    data_publicacao: null\n"
        )

        with self.assertRaises(ManifestError):
            load_manifest(self.manifest_path)

    def test_unknown_metadata_cannot_be_an_empty_string(self) -> None:
        (self.root / "nutricao" / "source.md").write_text("texto", encoding="utf-8")
        self.write_manifest(
            "version: 1\nsources:\n"
            "  - id: source-1\n"
            "    path: nutricao/source.md\n"
            "    title: ''\n"
            "    publisher: null\n"
            "    type: null\n"
            "    url: null\n"
            "    license: null\n"
            "    data_publicacao: null\n"
        )

        with self.assertRaises(ManifestError):
            load_manifest(self.manifest_path)

    def test_repository_manifest_authorizes_no_unlisted_documents(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]

        self.assertEqual(load_manifest(repository_root / "corpus" / "manifest.yaml"), ())


if __name__ == "__main__":
    unittest.main()