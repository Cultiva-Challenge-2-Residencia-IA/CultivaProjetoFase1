from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml


class ManifestError(ValueError):
    """Raised when the source manifest is invalid or unsafe."""


@dataclass(frozen=True)
class Source:
    id: str
    path: Path
    title: str | None
    publisher: str | None
    type: str | None
    url: str | None
    license: str | None
    data_publicacao: str | None


_SOURCE_FIELDS = {
    "id",
    "path",
    "title",
    "publisher",
    "type",
    "url",
    "license",
    "data_publicacao",
}
_METADATA_FIELDS = _SOURCE_FIELDS - {"id", "path"}


def load_manifest(manifest_path: Path) -> tuple[Source, ...]:
    """Load only explicitly allowlisted Markdown files under the corpus root."""
    try:
        manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ManifestError(f"Unable to read manifest: {manifest_path}") from error

    if not isinstance(manifest_data, Mapping):
        raise ManifestError("Manifest must be a mapping")
    if set(manifest_data) != {"version", "sources"}:
        raise ManifestError("Manifest must contain exactly version and sources")
    if type(manifest_data.get("version")) is not int or manifest_data["version"] != 1:
        raise ManifestError("Manifest version must be 1")

    entries = manifest_data.get("sources")
    if not isinstance(entries, list):
        raise ManifestError("Manifest sources must be a list")

    corpus_root = manifest_path.resolve().parent
    sources: list[Source] = []
    seen_ids: set[str] = set()
    seen_paths: set[Path] = set()

    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise ManifestError(f"Source at index {index} must be a mapping")
        if set(entry) != _SOURCE_FIELDS:
            raise ManifestError(
                f"Source at index {index} must contain exactly: "
                f"{', '.join(sorted(_SOURCE_FIELDS))}"
            )

        source_id = entry["id"]
        raw_path = entry["path"]
        if not isinstance(source_id, str) or not source_id.strip() or source_id != source_id.strip():
            raise ManifestError(f"Source at index {index} has an invalid id")
        if source_id in seen_ids:
            raise ManifestError(f"Duplicate source id: {source_id}")
        if (
            not isinstance(raw_path, str)
            or not raw_path.strip()
            or raw_path != raw_path.strip()
            or "\\" in raw_path
        ):
            raise ManifestError(f"Source {source_id} has an invalid path")

        relative_path = PurePosixPath(raw_path)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ManifestError(f"Source {source_id} path must stay inside corpus/")
        if relative_path.suffix.lower() != ".md":
            raise ManifestError(f"Source {source_id} path must reference a Markdown file")

        resolved_path = (corpus_root / Path(*relative_path.parts)).resolve()
        try:
            resolved_path.relative_to(corpus_root)
        except ValueError as error:
            raise ManifestError(f"Source {source_id} path must stay inside corpus/") from error
        if not resolved_path.is_file():
            raise ManifestError(f"Source {source_id} file does not exist: {raw_path}")
        if resolved_path in seen_paths:
            raise ManifestError(f"Duplicate source path: {raw_path}")

        metadata: dict[str, str | None] = {}
        for field in _METADATA_FIELDS:
            value = entry[field]
            if value is not None and not isinstance(value, str):
                raise ManifestError(f"Source {source_id} field {field} must be text or null")
            if isinstance(value, str) and not value.strip():
                raise ManifestError(f"Source {source_id} field {field} must use null when unknown")
            metadata[field] = value

        sources.append(
            Source(
                id=source_id,
                path=Path(*relative_path.parts),
                title=metadata["title"],
                publisher=metadata["publisher"],
                type=metadata["type"],
                url=metadata["url"],
                license=metadata["license"],
                data_publicacao=metadata["data_publicacao"],
            )
        )
        seen_ids.add(source_id)
        seen_paths.add(resolved_path)

    return tuple(sources)