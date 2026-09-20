"""Bước 12 — Evaluation script.

Chạy 18 câu golden dataset qua 2 config:
  - Config A: dense-only  (use_reranking=False)
  - Config B: hybrid+RRF  (use_reranking=True)

Đo 4 metric bằng LLM-as-judge (OpenAI):
  1. Faithfulness     — câu trả lời có trung thực với context không?
  2. Answer relevance — câu trả lời có liên quan đến câu hỏi không?
  3. Context recall   — context retrieved có chứa thông tin cần thiết không?
  4. Context precision — các chunk xếp hạng cao có liên quan không?

Cách chạy:
    python run_evaluation.py
"""

from __future__ import annotations

import json
import os
import time
import warnings
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")

# ── Config ──────────────────────────────────────────────────────────────────
GOLDEN_PATH = PROJECT_DIR / "group_project" / "evaluation" / "golden_dataset.json"
OUTPUT_PATH = PROJECT_DIR / "group_project" / "evaluation" / "eval_results.json"
TOP_K = 5
EVAL_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")


def load_golden() -> list[dict]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


# ── LLM Judge ──────────────────────────────────────────────────────────────
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def llm_judge(system: str, user: str) -> float:
    """Ask GPT to score 0.0–1.0."""
    for attempt in range(3):
        try:
            resp = client.responses.create(
                model=EVAL_MODEL,
                instructions=system,
                input=user,
                temperature=0,
                max_output_tokens=50,
            )
            text = resp.output_text.strip()
            # Extract first float from response
            for token in text.replace(",", ".").split():
                try:
                    val = float(token)
                    return max(0.0, min(1.0, val))
                except ValueError:
                    continue
            return 0.0
        except Exception as exc:
            if attempt < 2:
                print(f"  ⚠ Retry ({attempt+1}/3): {exc}")
                time.sleep(2 ** attempt)
            else:
                print(f"  ✗ Judge failed: {exc}")
                return 0.0


def score_faithfulness(question: str, answer: str, context: str) -> float:
    system = (
        "You are an evaluation judge. Score how faithful the answer is to the "
        "provided context. Score 1.0 if every claim in the answer is supported "
        "by the context. Score 0.0 if the answer contains fabricated info. "
        "Reply with ONLY a single float between 0.0 and 1.0."
    )
    user = f"Context:\n{context}\n\nQuestion: {question}\nAnswer: {answer}\n\nScore:"
    return llm_judge(system, user)


def score_answer_relevance(question: str, answer: str) -> float:
    system = (
        "You are an evaluation judge. Score how relevant and complete the "
        "answer is to the question. Score 1.0 if the answer fully addresses "
        "the question. Score 0.0 if completely irrelevant. "
        "Reply with ONLY a single float between 0.0 and 1.0."
    )
    user = f"Question: {question}\nAnswer: {answer}\n\nScore:"
    return llm_judge(system, user)


def score_context_recall(expected_context: str, retrieved_context: str) -> float:
    system = (
        "You are an evaluation judge. Score how much of the expected context "
        "information is present in the retrieved context. Score 1.0 if all "
        "key information from expected context appears in retrieved context. "
        "Score 0.0 if none is found. "
        "Reply with ONLY a single float between 0.0 and 1.0."
    )
    user = (
        f"Expected context:\n{expected_context}\n\n"
        f"Retrieved context:\n{retrieved_context}\n\nScore:"
    )
    return llm_judge(system, user)


def score_context_precision(question: str, contexts: list[str]) -> float:
    system = (
        "You are an evaluation judge. You are given a question and a ranked "
        "list of text chunks. Score how well the ranking places relevant "
        "chunks at the top. Score 1.0 if the most relevant chunks are ranked "
        "first. Score 0.0 if relevant chunks are at the bottom or absent. "
        "Reply with ONLY a single float between 0.0 and 1.0."
    )
    ranked = "\n\n".join(
        f"[Rank {i+1}]: {ctx[:300]}" for i, ctx in enumerate(contexts)
    )
    user = f"Question: {question}\n\nRanked chunks:\n{ranked}\n\nScore:"
    return llm_judge(system, user)


# ── Retrieval ──────────────────────────────────────────────────────────────
def run_retrieval(query: str, use_reranking: bool) -> list[dict]:
    """Run retrieval pipeline with error handling."""
    from src.task9_retrieval_pipeline import retrieve
    try:
        return retrieve(query, top_k=TOP_K, use_reranking=use_reranking)
    except Exception as exc:
        warnings.warn(f"Retrieval failed for '{query[:40]}...': {exc}")
        return []


def run_generation(query: str, sources: list[dict]) -> str:
    """Generate answer from pre-retrieved sources."""
    from src.task10_generation import (
        SYSTEM_PROMPT,
        call_llm,
        format_context,
        reorder_for_llm,
        _citations_are_valid,
        SAFE_REFUSAL,
    )
    import re

    if not sources:
        return SAFE_REFUSAL

    labeled = [
        {**s, "metadata": dict(s["metadata"]), "_citation_label": f"S{i}"}
        for i, s in enumerate(sources, 1)
    ]
    context = format_context(reorder_for_llm(labeled))
    user_message = (
        f"CONTEXT:\n{context}\n\n"
        f"QUESTION:\n{query}\n\n"
        "Trả lời trực tiếp và gắn citation [S#] sau từng khẳng định thực tế."
    )
    try:
        answer = call_llm(SYSTEM_PROMPT, user_message).strip()
    except Exception as exc:
        warnings.warn(f"Generation failed: {exc}")
        return SAFE_REFUSAL
    return answer


# ── Main evaluation ───────────────────────────────────────────────────────
def evaluate():
    golden = load_golden()
    print(f"\n{'='*60}")
    print(f"  RAG Evaluation — {len(golden)} questions, top_k={TOP_K}")
    print(f"  Config A: dense-only | Config B: hybrid+RRF")
    print(f"{'='*60}\n")

    results = {"config_a": [], "config_b": []}

    for idx, item in enumerate(golden, 1):
        qid = item["id"]
        question = item["question"]
        expected_answer = item["expected_answer"]
        expected_context = item["expected_context"]

        print(f"[{idx}/{len(golden)}] {qid}: {question[:60]}...")

        for config_name, use_reranking in [("config_a", False), ("config_b", True)]:
            label = "A (dense)" if config_name == "config_a" else "B (hybrid)"
            print(f"  ► Config {label}...", end=" ", flush=True)

            sources = run_retrieval(question, use_reranking=use_reranking)
            answer = run_generation(question, sources)

            context_texts = [s["content"] for s in sources]
            full_context = "\n\n".join(context_texts)

            faithfulness = score_faithfulness(question, answer, full_context)
            relevance = score_answer_relevance(question, answer)
            recall = score_context_recall(expected_context, full_context)
            precision = score_context_precision(question, context_texts)

            entry = {
                "id": qid,
                "question": question,
                "answer": answer,
                "n_sources": len(sources),
                "faithfulness": faithfulness,
                "answer_relevance": relevance,
                "context_recall": recall,
                "context_precision": precision,
                "avg": round(
                    (faithfulness + relevance + recall + precision) / 4, 4
                ),
            }
            results[config_name].append(entry)
            print(
                f"F={faithfulness:.2f} R={relevance:.2f} "
                f"CR={recall:.2f} CP={precision:.2f} avg={entry['avg']:.2f}"
            )

        print()

    # ── Summary ────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  OVERALL RESULTS")
    print(f"{'='*60}")

    summary = {}
    for config_name, label in [("config_a", "Config A (dense)"), ("config_b", "Config B (hybrid)")]:
        items = results[config_name]
        n = len(items) or 1
        metrics = {
            "faithfulness": round(sum(e["faithfulness"] for e in items) / n, 4),
            "answer_relevance": round(sum(e["answer_relevance"] for e in items) / n, 4),
            "context_recall": round(sum(e["context_recall"] for e in items) / n, 4),
            "context_precision": round(sum(e["context_precision"] for e in items) / n, 4),
        }
        metrics["average"] = round(sum(metrics.values()) / 4, 4)
        summary[config_name] = metrics

        print(f"\n  {label}:")
        for k, v in metrics.items():
            print(f"    {k:20s}: {v:.4f}")

    # Delta
    print(f"\n  Delta (B − A):")
    for metric in ["faithfulness", "answer_relevance", "context_recall", "context_precision", "average"]:
        delta = summary["config_b"][metric] - summary["config_a"][metric]
        sign = "+" if delta >= 0 else ""
        print(f"    {metric:20s}: {sign}{delta:.4f}")

    # ── Worst performers ───────────────────────────────────────────────────
    all_entries = []
    for config_name in ["config_a", "config_b"]:
        for entry in results[config_name]:
            all_entries.append({**entry, "config": config_name})
    worst = sorted(all_entries, key=lambda e: e["avg"])[:3]
    print(f"\n  Worst 3 performers:")
    for w in worst:
        print(f"    {w['config']} | {w['id']} | avg={w['avg']:.2f} | {w['question'][:50]}...")

    # ── Save ───────────────────────────────────────────────────────────────
    output = {"summary": summary, "details": results, "worst_performers": worst}
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ Results saved to {OUTPUT_PATH}")

    return output


if __name__ == "__main__":
    evaluate()
