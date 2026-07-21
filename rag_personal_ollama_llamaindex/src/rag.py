from langdetect import DetectorFactory, LangDetectException, detect
from llama_index.core import Settings, VectorStoreIndex
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

from .config import AppConfig
from .privacy import REFUSAL_EN, REFUSAL_ES, is_sensitive_query, redact_sensitive_text
from .prompts import build_prompt

DetectorFactory.seed = 0


def detect_language(text: str) -> str:
    if len(text.strip()) < 12:
        english_markers = {"what", "who", "how", "experience", "certification", "skills"}
        return "en" if set(text.lower().split()) & english_markers else "es"
    try:
        return "en" if detect(text) == "en" else "es"
    except LangDetectException:
        return "es"


class PersonalRAG:
    def __init__(self, config: AppConfig):
        self.config = config
        Settings.llm = Ollama(
            model=config.llm_model,
            base_url=config.ollama_base_url,
            request_timeout=config.request_timeout,
            temperature=0.1,
        )
        Settings.embed_model = OllamaEmbedding(
            model_name=config.embed_model,
            base_url=config.ollama_base_url,
        )
        self.client = QdrantClient(path=str(config.qdrant_path))
        if not self.client.collection_exists(config.collection_name):
            self.client.close()
            raise RuntimeError("La colección no existe. Ejecute primero: python -m src.cli ingest")
        vector_store = QdrantVectorStore(
            client=self.client,
            collection_name=config.collection_name,
        )
        self.index = VectorStoreIndex.from_vector_store(vector_store)

    def close(self) -> None:
        self.client.close()

    def ask(self, query: str, role: dict) -> dict:
        language = detect_language(query)
        if is_sensitive_query(query):
            return {
                "answer": REFUSAL_EN if language == "en" else REFUSAL_ES,
                "language": language,
                "sources": [],
            }

        query_engine = self.index.as_query_engine(
            similarity_top_k=self.config.similarity_top_k,
            text_qa_template=build_prompt(role, language),
            response_mode="compact",
        )
        response = query_engine.query(query)
        answer = redact_sensitive_text(str(response))

        sources = []
        for node in getattr(response, "source_nodes", []):
            sources.append(
                {
                    "score": node.score,
                    "file_name": node.metadata.get("file_name", "desconocido"),
                    "document_type": node.metadata.get("document_type", "desconocido"),
                    "text": node.text[:300],
                }
            )

        return {"answer": answer, "language": language, "sources": sources}
