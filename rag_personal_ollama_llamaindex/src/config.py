from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name, str(default)).strip().lower()
    return value in {"1", "true", "yes", "si", "sí", "on"}


@dataclass(frozen=True)
class AppConfig:
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    llm_model: str = os.getenv("OLLAMA_LLM_MODEL", "qwen2.5:3b")
    embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    qdrant_path: Path = Path(os.getenv("QDRANT_PATH", "storage/qdrant"))
    collection_name: str = os.getenv("QDRANT_COLLECTION", "kevin_personal_rag")
    data_dir: Path = Path(os.getenv("DATA_DIR", "data/raw"))
    versions_dir: Path = Path(os.getenv("VERSIONS_DIR", "data/versions"))
    manifest_path: Path = Path(os.getenv("MANIFEST_PATH", "storage/manifests/documents.json"))
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "600"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "80"))
    similarity_top_k: int = int(os.getenv("SIMILARITY_TOP_K", "4"))
    request_timeout: float = float(os.getenv("REQUEST_TIMEOUT", "180"))
    min_free_disk_gb: float = float(os.getenv("MIN_FREE_DISK_GB", "3"))
    debug_sources: bool = _bool_env("DEBUG_SOURCES", False)

    def ensure_directories(self) -> None:
        for path in (
            self.qdrant_path,
            self.data_dir,
            self.versions_dir,
            self.manifest_path.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)
