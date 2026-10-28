import asyncio
import logging

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger("clinic-embeddings")

EMBEDDING_BATCH_SIZE = 32


class RagUnavailableError(RuntimeError):
    """Raised when the knowledge base cannot be indexed or searched."""


def rag_available() -> bool:
    return bool(settings.rag_enabled and settings.openai_api_key)


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not rag_available():
        raise RagUnavailableError(
            "RAG is not configured. Set OPENAI_API_KEY and RAG_ENABLED=true."
        )

    cleaned = [text.strip() for text in texts if text and text.strip()]
    if not cleaned:
        return []

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.rag_timeout_seconds,
    )
    vectors: list[list[float]] = []

    try:
        for start in range(0, len(cleaned), EMBEDDING_BATCH_SIZE):
            batch = cleaned[start : start + EMBEDDING_BATCH_SIZE]
            response = await asyncio.wait_for(
                client.embeddings.create(
                    model=settings.openai_embedding_model,
                    input=batch,
                ),
                timeout=settings.rag_timeout_seconds,
            )
            ordered = sorted(response.data, key=lambda item: item.index)
            vectors.extend(
                [float(value) for value in item.embedding]
                for item in ordered
            )
    except RagUnavailableError:
        raise
    except Exception as exc:
        logger.exception("Embedding request failed")
        raise RagUnavailableError(
            "The knowledge embedding provider is unavailable."
        ) from exc
    finally:
        await client.close()

    return vectors


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    dot = sum(a * b for a, b in zip(left, right))
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
