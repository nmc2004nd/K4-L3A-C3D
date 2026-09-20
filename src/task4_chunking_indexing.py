"""Task 4: load, chunk, embed and index the standardized corpus.

The public functions in this module are also used by the retrieval tasks. Keep
heavy optional imports inside functions so importing it does not load a model.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .contracts import validate_document


PROJECT_DIR = Path(__file__).resolve().parent.parent
STANDARDIZED_DIR = PROJECT_DIR / "data" / "standardized"
CHROMA_DIR = PROJECT_DIR / "chroma_db"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
CHUNKING_METHOD = "recursive"

EMBEDDING_PROVIDER = "sentence_transformers"
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024

COLLECTION_NAME = "rag_documents"
_CHUNK_SEPARATORS = ("\n\n", "\n", ". ", "; ", ", ", " ")


def _embedding_settings() -> tuple[str, str]:
    """Read settings at call time, allowing CLI users to configure ``.env``."""
    load_dotenv(PROJECT_DIR / ".env")
    provider = os.getenv("EMBEDDING_PROVIDER", EMBEDDING_PROVIDER).strip().lower()
    model = os.getenv("EMBEDDING_MODEL", EMBEDDING_MODEL).strip()
    if not model:
        raise ValueError("EMBEDDING_MODEL must not be empty")
    return provider, model


@lru_cache(maxsize=2)
def _sentence_transformer(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover - depends on local setup
        raise RuntimeError(
            "sentence-transformers is required for EMBEDDING_PROVIDER="
            "sentence_transformers; install the project dependencies first"
        ) from exc
    return SentenceTransformer(model_name)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts using one configured provider and return plain float lists."""
    if not isinstance(texts, list) or any(not isinstance(text, str) for text in texts):
        raise TypeError("texts must be a list of strings")
    if not texts:
        return []

    provider, model_name = _embedding_settings()
    if provider in {"sentence_transformers", "sentence-transformers", "local"}:
        vectors = _sentence_transformer(model_name).encode(
            texts,
            batch_size=max(1, int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [[float(value) for value in vector] for vector in vectors]

    if provider == "openai":
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - depends on local setup
            raise RuntimeError("openai is required for the OpenAI embedding provider") from exc
        response = OpenAI().embeddings.create(model=model_name, input=texts)
        ordered = sorted(response.data, key=lambda item: item.index)
        return [[float(value) for value in item.embedding] for item in ordered]

    if provider == "gemini":
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:  # pragma: no cover - depends on local setup
            raise RuntimeError("google-genai is required for the Gemini embedding provider") from exc
        response = genai.Client().models.embed_content(
            model=model_name,
            contents=texts,
            config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
        )
        return [
            [float(value) for value in embedding.values]
            for embedding in (response.embeddings or [])
        ]

    raise ValueError(
        "Unsupported EMBEDDING_PROVIDER. Use sentence_transformers, openai, or gemini."
    )


def get_collection():
    """Open the persistent Chroma collection configured for cosine distance."""
    try:
        import chromadb
    except ImportError as exc:  # pragma: no cover - depends on local setup
        raise RuntimeError("chromadb is required to create the vector store") from exc

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _markdown_metadata(path: Path, content: str) -> dict[str, Any]:
    relative_path = path.relative_to(STANDARDIZED_DIR)
    title_match = re.search(r"^#\s+(.+?)\s*$", content, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem.replace("_", " ")
    url_match = re.search(
        r"^\*\*(?:Source URL|Source):\*\*\s*(https?://\S+)",
        content,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    doc_type = relative_path.parts[0].lower() if len(relative_path.parts) > 1 else "news"
    if doc_type not in {"legal", "news"}:
        raise ValueError(f"Unsupported document type for {relative_path}: {doc_type}")
    return {
        "source": relative_path.as_posix(),
        "title": title,
        "doc_type": doc_type,
        "url": url_match.group(1).rstrip(")].,;") if url_match else None,
    }


def load_documents() -> list[dict]:
    """Read every standardized Markdown file in deterministic path order."""
    if not STANDARDIZED_DIR.is_dir():
        raise FileNotFoundError(f"Standardized data directory not found: {STANDARDIZED_DIR}")

    documents: list[dict] = []
    for path in sorted(STANDARDIZED_DIR.rglob("*.md")):
        content = path.read_text(encoding="utf-8").strip()
        document = {
            "id": path.relative_to(STANDARDIZED_DIR).with_suffix("").as_posix(),
            "content": content,
            "metadata": _markdown_metadata(path, content),
        }
        validate_document(document)
        documents.append(document)
    return documents


def _boundary(text: str, start: int, maximum_end: int) -> int:
    """Choose the strongest natural boundary without exceeding maximum_end."""
    minimum_end = start + max(CHUNK_SIZE // 2, CHUNK_OVERLAP + 1)
    window = text[start:maximum_end]
    for separator in _CHUNK_SEPARATORS:
        position = window.rfind(separator)
        if position >= 0:
            candidate = start + position + len(separator)
            if candidate >= minimum_end:
                return candidate
    return maximum_end


def _split_text(text: str) -> list[str]:
    """A deterministic recursive-style splitter with character overlap."""
    text = text.strip()
    if not text:
        return []

    pieces: list[str] = []
    start = 0
    while start < len(text):
        maximum_end = min(start + CHUNK_SIZE, len(text))
        end = maximum_end if maximum_end == len(text) else _boundary(text, start, maximum_end)
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(text):
            break
        start = max(start + 1, end - CHUNK_OVERLAP)
        while start < end and text[start].isspace():
            start += 1
    return pieces


def chunk_documents(documents: list[dict]) -> list[dict]:
    """Split documents into non-empty, stable-ID chunks with source metadata."""
    chunks: list[dict] = []
    seen_ids: set[str] = set()
    for document in documents:
        validate_document(document)
        for index, content in enumerate(_split_text(document["content"])):
            chunk = {
                "id": f"{document['id']}::chunk-{index}",
                "content": content,
                "metadata": {**document["metadata"], "chunk_index": index},
            }
            validate_document(chunk, require_chunk=True)
            if chunk["id"] in seen_ids:
                raise ValueError(f"Duplicate chunk id: {chunk['id']}")
            seen_ids.add(chunk["id"])
            chunks.append(chunk)
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Return copies of chunks augmented with one embedding per chunk."""
    for chunk in chunks:
        validate_document(chunk, require_chunk=True)
    vectors = embed_texts([chunk["content"] for chunk in chunks])
    if len(vectors) != len(chunks):
        raise ValueError(
            f"Embedding provider returned {len(vectors)} vectors for {len(chunks)} chunks"
        )

    embedded: list[dict] = []
    dimension: int | None = None
    for chunk, vector in zip(chunks, vectors):
        if not isinstance(vector, (list, tuple)) or not vector:
            raise ValueError(f"Invalid embedding for chunk {chunk['id']}")
        try:
            clean_vector = [float(value) for value in vector]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Embedding for chunk {chunk['id']} is not numeric") from exc
        dimension = dimension or len(clean_vector)
        if len(clean_vector) != dimension:
            raise ValueError("All embeddings must have the same dimension")
        embedded.append({**chunk, "metadata": dict(chunk["metadata"]), "embedding": clean_vector})
    return embedded


def _chroma_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """Convert nullable contract values to scalar values accepted by Chroma."""
    return {key: "" if value is None else value for key, value in metadata.items()}


def index_to_vectorstore(chunks: list[dict]) -> None:
    """Idempotently upsert embedded chunks into Chroma in bounded batches."""
    if not chunks:
        return

    ids: set[str] = set()
    for chunk in chunks:
        validate_document(chunk, require_chunk=True)
        if chunk["id"] in ids:
            raise ValueError(f"Duplicate chunk id: {chunk['id']}")
        ids.add(chunk["id"])
        if not isinstance(chunk.get("embedding"), list) or not chunk["embedding"]:
            raise ValueError(f"Chunk {chunk['id']} has no embedding")

    collection = get_collection()
    batch_size = max(1, int(os.getenv("CHROMA_BATCH_SIZE", "128")))
    for offset in range(0, len(chunks), batch_size):
        batch = chunks[offset : offset + batch_size]
        collection.upsert(
            ids=[chunk["id"] for chunk in batch],
            documents=[chunk["content"] for chunk in batch],
            embeddings=[chunk["embedding"] for chunk in batch],
            metadatas=[_chroma_metadata(chunk["metadata"]) for chunk in batch],
        )


def run_pipeline() -> None:
    """Run the complete Task 4 indexing pipeline."""
    documents = load_documents()
    chunks = chunk_documents(documents)
    embedded_chunks = embed_chunks(chunks)
    index_to_vectorstore(embedded_chunks)
    print(f"Indexed {len(embedded_chunks)} chunks from {len(documents)} documents")


if __name__ == "__main__":
    run_pipeline()
