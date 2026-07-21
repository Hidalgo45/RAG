from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from llama_index.core import SimpleDirectoryReader

from .config import AppConfig
from .privacy import redact_sensitive_text


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def discover_files(data_dir: Path) -> list[Path]:
    return sorted(
        path for path in data_dir.rglob("*")
        if path.is_file() and not path.name.startswith(".")
    )


def build_manifest(data_dir: Path) -> dict[str, dict[str, Any]]:
    manifest = {}
    for path in discover_files(data_dir):
        relative = path.relative_to(data_dir).as_posix()
        manifest[relative] = {
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
            "modified_ns": path.stat().st_mtime_ns,
        }
    return manifest


def load_manifest(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(path: Path, manifest: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def archive_changed_files(config: AppConfig, old: dict, new: dict) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for relative, previous in old.items():
        current = new.get(relative)
        if current and current.get("sha256") != previous.get("sha256"):
            source = config.data_dir / relative
            if source.exists():
                destination = config.versions_dir / timestamp / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)


def clean_text(text: str) -> str:
    text = redact_sensitive_text(text)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(?m)^\s*\d+\s*$", "", text)
    return text.strip()


def file_metadata(file_path: str) -> dict:
    path = Path(file_path)
    name = path.name.lower()
    document_type = "certificacion" if "cert" in name or "diplom" in name else "curriculum"
    priority = 100 if any(word in name for word in ("cv", "curriculum", "hoja")) else 70
    return {
        "file_name": path.name,
        "document_type": document_type,
        "source_priority": priority,
        "ingested_at": datetime.now().isoformat(timespec="seconds"),
    }


def load_documents(config: AppConfig):
    files = discover_files(config.data_dir)
    if not files:
        raise FileNotFoundError(
            f"No hay documentos en {config.data_dir}. Agregue CV y certificaciones autorizadas."
        )

    reader = SimpleDirectoryReader(
        input_dir=str(config.data_dir),
        recursive=True,
        filename_as_id=True,
        file_metadata=file_metadata,
    )
    documents = reader.load_data()

    cleaned = []
    for document in documents:
        document.text = clean_text(document.text or "")
        if document.text:
            cleaned.append(document)

    if not cleaned:
        raise ValueError("Los documentos no produjeron texto utilizable.")
    return cleaned
