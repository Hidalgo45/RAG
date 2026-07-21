from llama_index.core import Settings, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

from .config import AppConfig
from .documents import (
    archive_changed_files,
    build_manifest,
    load_documents,
    load_manifest,
    save_manifest,
)


def configure_embedding(config: AppConfig) -> None:
    Settings.embed_model = OllamaEmbedding(
        model_name=config.embed_model,
        base_url=config.ollama_base_url,
    )


def ingest_documents(config: AppConfig, rebuild: bool = False) -> bool:
    config.ensure_directories()
    old_manifest = load_manifest(config.manifest_path)
    new_manifest = build_manifest(config.data_dir)

    if not rebuild and old_manifest and old_manifest == new_manifest:
        return False

    archive_changed_files(config, old_manifest, new_manifest)
    documents = load_documents(config)
    configure_embedding(config)

    client = QdrantClient(path=str(config.qdrant_path))
    if client.collection_exists(config.collection_name):
        client.delete_collection(config.collection_name)

    vector_store = QdrantVectorStore(
        client=client,
        collection_name=config.collection_name,
    )
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    splitter = SentenceSplitter(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
    )

    VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        transformations=[splitter],
        show_progress=True,
    )
    save_manifest(config.manifest_path, new_manifest)
    client.close()
    return True
