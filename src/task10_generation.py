"""Task 10: grounded answer generation with verifiable citations."""

from __future__ import annotations

import os
import re
import warnings
from pathlib import Path

from dotenv import load_dotenv

from .contracts import (
    validate_document,
    validate_generation_result,
    validate_search_results,
)
from .task9_retrieval_pipeline import retrieve


PROJECT_DIR = Path(__file__).resolve().parent.parent

TOP_K = 5
TOP_P = 0.9
TEMPERATURE = 0.3
MAX_OUTPUT_TOKENS = 1200

LLM_PROVIDER = "openai"
LLM_MODEL = ""

SAFE_REFUSAL = "Tôi không thể xác minh thông tin này từ nguồn hiện có."

SYSTEM_PROMPT = """Bạn là trợ lý RAG trả lời bằng ngôn ngữ của câu hỏi.
Sử dụng bằng chứng từ CONTEXT để trả lời. Không bịa thông tin ngoài CONTEXT.
Mỗi khẳng định thực tế PHẢI kèm citation dạng [S1], [S2], v.v. tương ứng với
nhãn nguồn trong CONTEXT.
Chỉ trả lời "Tôi không thể xác minh thông tin này từ nguồn hiện có." khi
CONTEXT hoàn toàn không liên quan đến câu hỏi."""

_CITATION_PATTERN = re.compile(r"\[S(\d+)\]")


def _safe_refusal() -> dict:
    result = {
        "answer": SAFE_REFUSAL,
        "sources": [],
        "retrieval_source": "none",
    }
    validate_generation_result(result)
    return result


def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """Place high-ranked chunks near both edges without mutating the input."""
    if not isinstance(chunks, list):
        raise TypeError("chunks must be a list")
    for chunk in chunks:
        validate_document(chunk, require_chunk=True)
    if len(chunks) <= 2:
        return list(chunks)

    # Input is score-descending. This keeps the best chunk first and moves the
    # second-best to the end, reducing the model's lost-in-the-middle effect.
    front = chunks[::2]
    back = chunks[1::2]
    return front + back[::-1]


def format_context(chunks: list[dict]) -> str:
    """Format evidence with citation labels, IDs, titles and source names."""
    if not isinstance(chunks, list):
        raise TypeError("chunks must be a list")

    parts: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        validate_document(chunk, require_chunk=True)
        metadata = chunk["metadata"]
        label = chunk.get("_citation_label", f"S{index}")
        if not isinstance(label, str) or re.fullmatch(r"S[1-9]\d*", label) is None:
            raise ValueError(f"Invalid citation label for chunk {chunk['id']!r}")
        url = metadata.get("url") or "N/A"
        parts.append(
            f"[{label} | ID: {chunk['id']} | Title: {metadata['title']} | "
            f"Source: {metadata['source']} | URL: {url}]\n{chunk['content']}"
        )
    return "\n\n---\n\n".join(parts)


def _llm_settings() -> tuple[str, str]:
    load_dotenv(PROJECT_DIR / ".env")
    provider = os.getenv("LLM_PROVIDER", LLM_PROVIDER).strip().lower()
    model = os.getenv("LLM_MODEL", LLM_MODEL).strip()
    if provider not in {"openai", "gemini", "anthropic"}:
        raise ValueError("LLM_PROVIDER must be openai, gemini, or anthropic")
    if not model:
        raise ValueError("LLM_MODEL must be configured")
    return provider, model


def _require_api_key(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not configured")
    return value


def _call_openai(model: str, system_prompt: str, user_message: str) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - depends on local setup
        raise RuntimeError("openai is required for LLM_PROVIDER=openai") from exc

    response = OpenAI(api_key=_require_api_key("OPENAI_API_KEY")).responses.create(
        model=model,
        instructions=system_prompt,
        input=user_message,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        temperature=TEMPERATURE,
        store=False,
    )
    return str(response.output_text or "").strip()


def _call_gemini(model: str, system_prompt: str, user_message: str) -> str:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:  # pragma: no cover - depends on local setup
        raise RuntimeError("google-genai is required for LLM_PROVIDER=gemini") from exc

    response = genai.Client(api_key=_require_api_key("GEMINI_API_KEY")).models.generate_content(
        model=model,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=TEMPERATURE,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        ),
    )
    return str(response.text or "").strip()


def _call_anthropic(model: str, system_prompt: str, user_message: str) -> str:
    try:
        from anthropic import Anthropic
    except ImportError as exc:  # pragma: no cover - depends on local setup
        raise RuntimeError("anthropic is required for LLM_PROVIDER=anthropic") from exc

    response = Anthropic(api_key=_require_api_key("ANTHROPIC_API_KEY")).messages.create(
        model=model,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
        max_tokens=MAX_OUTPUT_TOKENS,
        temperature=TEMPERATURE,
    )
    return "".join(
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text" and getattr(block, "text", None)
    ).strip()


def call_llm(system_prompt: str, user_message: str) -> str:
    """Call the configured OpenAI, Gemini, or Anthropic provider."""
    if not isinstance(system_prompt, str) or not system_prompt.strip():
        raise ValueError("system_prompt must be a non-empty string")
    if not isinstance(user_message, str) or not user_message.strip():
        raise ValueError("user_message must be a non-empty string")

    provider, model = _llm_settings()
    dispatch = {
        "openai": _call_openai,
        "gemini": _call_gemini,
        "anthropic": _call_anthropic,
    }
    answer = dispatch[provider](model, system_prompt, user_message)
    if not answer:
        raise RuntimeError(f"{provider} returned an empty response")
    return answer


def _citations_are_valid(answer: str, source_count: int) -> bool:
    labels = [int(value) for value in _CITATION_PATTERN.findall(answer)]
    return bool(labels) and all(1 <= label <= source_count for label in labels)


def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """Retrieve evidence and return a grounded, citation-checked answer."""
    if not isinstance(query, str):
        raise TypeError("query must be a string")
    if not isinstance(top_k, int) or isinstance(top_k, bool):
        raise TypeError("top_k must be an integer")
    query = query.strip()
    if not query or top_k <= 0:
        return _safe_refusal()

    try:
        sources = retrieve(query, top_k=top_k)
        validate_search_results(sources, top_k=top_k)
    except Exception as exc:
        warnings.warn(f"Retrieval unavailable: {exc}", RuntimeWarning)
        return _safe_refusal()
    if not sources:
        return _safe_refusal()

    # Labels follow the score-sorted ``sources`` output, even though context is
    # reordered. Thus [S1] always maps to sources[0], [S2] to sources[1], etc.
    labeled = [
        {
            **source,
            "metadata": dict(source["metadata"]),
            "_citation_label": f"S{index}",
        }
        for index, source in enumerate(sources, start=1)
    ]
    context = format_context(reorder_for_llm(labeled))
    user_message = (
        "CONTEXT:\n"
        f"{context}\n\n"
        "QUESTION:\n"
        f"{query}\n\n"
        "Trả lời trực tiếp và gắn citation [S#] sau từng khẳng định thực tế."
    )

    try:
        answer = call_llm(SYSTEM_PROMPT, user_message).strip()
    except Exception as exc:
        warnings.warn(f"Generation provider unavailable: {exc}", RuntimeWarning)
        return _safe_refusal()
    if not _citations_are_valid(answer, len(sources)):
        warnings.warn("Generated answer has missing or invalid citations", RuntimeWarning)
        return _safe_refusal()

    methods = {source["retrieval_method"] for source in sources}
    retrieval_source = "pageindex" if methods == {"pageindex"} else "hybrid"
    result = {
        "answer": answer,
        "sources": sources,
        "retrieval_source": retrieval_source,
    }
    validate_generation_result(result)
    return result


if __name__ == "__main__":
    print(generate_with_citation("Điều kiện kinh doanh dịch vụ lữ hành là gì?"))
