"""Run a reproducible dense-vs-hybrid RAG benchmark and write the report.

Usage:
    python scripts/evaluate_rag.py
    python scripts/evaluate_rag.py --limit 2   # smoke test

The script checkpoints generation output after every question. Re-running it
resumes completed cases unless ``--force`` is supplied. API keys are loaded
from ``.env`` and are never written to result artifacts.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import statistics
import subprocess
import sys
import time
from datetime import date
from importlib.metadata import version
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from dotenv import load_dotenv

from src.task10_generation import SYSTEM_PROMPT, call_llm, format_context, reorder_for_llm
from src.task5_semantic_search import semantic_search
from src.task9_retrieval_pipeline import retrieve


EVALUATION_DIR = PROJECT_DIR / "group_project" / "evaluation"
GOLDEN_PATH = EVALUATION_DIR / "golden_dataset.json"
RESULTS_PATH = EVALUATION_DIR / "benchmark_results.json"
REPORT_PATH = EVALUATION_DIR / "RESULT.md"

DEFAULT_GENERATOR_MODEL = "gpt-4o-mini"
DEFAULT_EVALUATOR_MODEL = "gpt-4o-mini"
DEFAULT_EVALUATOR_EMBEDDING_MODEL = "text-embedding-3-small"
TOP_K = 5

CONFIGS = {
    "dense_only": False,
    "hybrid_rrf": True,
}

OUT_OF_DOMAIN_QUERIES = [
    "Giá cổ phiếu Apple hôm nay là bao nhiêu?",
    "Viết chương trình sắp xếp quicksort bằng Rust.",
    "Dự báo thời tiết Tokyo ngày mai như thế nào?",
    "Ai vô địch World Cup bóng đá năm 2034?",
    "Cách điều trị bệnh tiểu đường bằng thuốc nào?",
]


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _settings() -> dict[str, str]:
    load_dotenv(PROJECT_DIR / ".env")
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    generator_model = os.getenv("LLM_MODEL", "").strip() or DEFAULT_GENERATOR_MODEL
    evaluator_model = (
        os.getenv("EVALUATOR_MODEL", "").strip() or DEFAULT_EVALUATOR_MODEL
    )
    evaluator_embedding_model = (
        os.getenv("EVALUATOR_EMBEDDING_MODEL", "").strip()
        or DEFAULT_EVALUATOR_EMBEDDING_MODEL
    )
    if provider != "openai":
        raise ValueError(
            "This benchmark currently uses the OpenAI Ragas evaluator. "
            "Set LLM_PROVIDER=openai and OPENAI_API_KEY in .env."
        )
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise RuntimeError("OPENAI_API_KEY is missing from .env")
    # task10 reads its configuration at call time.
    os.environ["LLM_PROVIDER"] = provider
    os.environ["LLM_MODEL"] = generator_model
    return {
        "provider": provider,
        "generator_model": generator_model,
        "evaluator_model": evaluator_model,
        "evaluator_embedding_model": evaluator_embedding_model,
    }


def _new_state(settings: dict[str, str], case_count: int) -> dict[str, Any]:
    return {
        "run_info": {
            "date": date.today().isoformat(),
            "generator_model": settings["generator_model"],
            "evaluator_model": settings["evaluator_model"],
            "evaluator_embedding_model": settings["evaluator_embedding_model"],
            "embedding_model": os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"),
            "top_k": TOP_K,
            "golden_dataset_size": case_count,
            "ragas_version": version("ragas"),
            "commit": _commit(),
        },
        "threshold_calibration": {},
        "cases": [],
        "summary": {},
    }


def _commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_DIR,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _citation_context(chunks: list[dict]) -> str:
    labeled = [
        {**chunk, "metadata": dict(chunk["metadata"]), "_citation_label": f"S{i}"}
        for i, chunk in enumerate(chunks, 1)
    ]
    return format_context(reorder_for_llm(labeled))


def _answer(question: str, use_reranking: bool) -> tuple[str, list[dict], float]:
    started = time.perf_counter()
    # -2 is below the minimum cosine similarity, so PageIndex is disabled and
    # the A/B comparison changes retrieval strategy only.
    chunks = retrieve(
        question,
        top_k=TOP_K,
        score_threshold=-2.0,
        use_reranking=use_reranking,
    )
    context = _citation_context(chunks)
    if not chunks:
        answer = "Tôi không thể xác minh thông tin này từ nguồn hiện có."
    else:
        answer = call_llm(
            SYSTEM_PROMPT,
            f"CONTEXT:\n{context}\n\nQUESTION:\n{question}\n\n"
            "Trả lời trực tiếp và gắn citation [S#] sau từng khẳng định thực tế.",
        ).strip()
    latency = time.perf_counter() - started
    return answer, chunks, latency


def generate_cases(
    golden: list[dict[str, Any]],
    state: dict[str, Any],
    *,
    force: bool,
) -> None:
    existing = {
        (case["id"], case["config"]): case
        for case in state.get("cases", [])
        if isinstance(case, dict) and "id" in case and "config" in case
    }
    total = len(golden) * len(CONFIGS)
    completed = 0
    for item in golden:
        for config, use_reranking in CONFIGS.items():
            key = (item["id"], config)
            if key in existing and not force:
                completed += 1
                print(f"[{completed}/{total}] cached {item['id']} {config}", flush=True)
                continue
            answer, sources, latency = _answer(item["question"], use_reranking)
            case = {
                "id": item["id"],
                "category": item.get("category", "unknown"),
                "difficulty": item.get("difficulty", "unknown"),
                "question": item["question"],
                "reference": item["expected_answer"],
                "expected_context": item["expected_context"],
                "config": config,
                "answer": answer,
                "retrieved_contexts": [source["content"] for source in sources],
                "source_ids": [source["id"] for source in sources],
                "source_methods": [source["retrieval_method"] for source in sources],
                "latency_seconds": round(latency, 4),
                "scores": {},
            }
            existing[key] = case
            state["cases"] = sorted(existing.values(), key=lambda row: (row["id"], row["config"]))
            _atomic_json(RESULTS_PATH, state)
            completed += 1
            print(f"[{completed}/{total}] generated {item['id']} {config} ({latency:.2f}s)", flush=True)


def calibrate_threshold(golden: list[dict[str, Any]], state: dict[str, Any]) -> None:
    samples: list[tuple[str, bool, float]] = []
    for item in golden:
        results = semantic_search(item["question"], top_k=1)
        samples.append((item["question"], True, results[0]["score"] if results else -1.0))
    for query in OUT_OF_DOMAIN_QUERIES:
        results = semantic_search(query, top_k=1)
        samples.append((query, False, results[0]["score"] if results else -1.0))

    unique_scores = sorted({score for _, _, score in samples})
    candidates = [-1.0]
    candidates.extend(
        (left + right) / 2 for left, right in zip(unique_scores, unique_scores[1:])
    )
    candidates.append(1.0)

    best: tuple[float, float, float, float] | None = None
    for threshold in candidates:
        tp = sum(label and score >= threshold for _, label, score in samples)
        fn = sum(label and score < threshold for _, label, score in samples)
        tn = sum(not label and score < threshold for _, label, score in samples)
        fp = sum(not label and score >= threshold for _, label, score in samples)
        tpr = tp / (tp + fn) if tp + fn else 0.0
        tnr = tn / (tn + fp) if tn + fp else 0.0
        balanced_accuracy = (tpr + tnr) / 2
        candidate = (balanced_accuracy, tpr, tnr, threshold)
        if best is None or candidate > best:
            best = candidate
    assert best is not None
    state["threshold_calibration"] = {
        "threshold": round(best[3], 6),
        "balanced_accuracy": round(best[0], 6),
        "in_domain_recall": round(best[1], 6),
        "out_of_domain_specificity": round(best[2], 6),
        "in_domain_count": len(golden),
        "out_of_domain_count": len(OUT_OF_DOMAIN_QUERIES),
        "in_domain_scores": [round(score, 6) for _, label, score in samples if label],
        "out_of_domain_scores": [round(score, 6) for _, label, score in samples if not label],
    }
    _atomic_json(RESULTS_PATH, state)


def evaluate_cases(
    state: dict[str, Any],
    settings: dict[str, str],
    *,
    evaluation_limit: int | None = None,
) -> None:
    from langchain_openai import OpenAIEmbeddings
    from openai import OpenAI
    from ragas.dataset_schema import SingleTurnSample
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import llm_factory
    from ragas.metrics import (
        AnswerRelevancy,
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
    )

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    evaluator_llm = llm_factory(
        settings["evaluator_model"], provider="openai", client=client
    )
    evaluator_embeddings = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(
            model=settings["evaluator_embedding_model"],
            api_key=os.environ["OPENAI_API_KEY"],
        )
    )
    metrics = {
        "faithfulness": Faithfulness(llm=evaluator_llm),
        "answer_relevance": AnswerRelevancy(
            llm=evaluator_llm,
            embeddings=evaluator_embeddings,
            strictness=1,
        ),
        "context_recall": LLMContextRecall(llm=evaluator_llm),
        "context_precision": LLMContextPrecisionWithReference(llm=evaluator_llm),
    }

    async def score_case(case: dict[str, Any]) -> dict[str, float | None]:
        sample = SingleTurnSample(
            user_input=case["question"],
            response=case["answer"],
            retrieved_contexts=case["retrieved_contexts"],
            reference=case["reference"],
        )
        names = list(metrics)
        values = await asyncio.gather(
            *(metrics[name].single_turn_ascore(sample, timeout=180) for name in names),
            return_exceptions=True,
        )
        scores: dict[str, float | None] = {}
        for name, value in zip(names, values):
            if isinstance(value, BaseException):
                print(f"  {name} failed: {value}", flush=True)
                scores[name] = None
                continue
            try:
                number = float(value)
                scores[name] = round(number, 6) if math.isfinite(number) else None
            except (TypeError, ValueError):
                scores[name] = None
        return scores

    cases = state["cases"]
    if evaluation_limit is not None:
        cases = cases[: max(0, evaluation_limit)]
    for index, case in enumerate(cases, 1):
        current = case.get("scores", {})
        if all(current.get(name) is not None for name in metrics):
            print(f"[{index}/{len(cases)}] cached scores {case['id']} {case['config']}", flush=True)
            continue
        print(f"[{index}/{len(cases)}] scoring {case['id']} {case['config']}", flush=True)
        case["scores"] = asyncio.run(score_case(case))
        _summarize(state)
        _atomic_json(RESULTS_PATH, state)
    _summarize(state)
    _atomic_json(RESULTS_PATH, state)


def _mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 6) if values else None


def _summarize(state: dict[str, Any]) -> None:
    summary: dict[str, Any] = {}
    for config in CONFIGS:
        cases = [case for case in state["cases"] if case["config"] == config]
        metric_means = {}
        for metric in ("faithfulness", "answer_relevance", "context_recall", "context_precision"):
            values = [case["scores"].get(metric) for case in cases]
            metric_means[metric] = _mean([value for value in values if value is not None])
        valid = [value for value in metric_means.values() if value is not None]
        metric_means["average"] = _mean(valid)
        metric_means["latency_seconds"] = _mean(
            [float(case["latency_seconds"]) for case in cases]
        )
        summary[config] = metric_means
    state["summary"] = summary


def _fmt(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.4f}"


def write_report(state: dict[str, Any]) -> None:
    info = state["run_info"]
    calibration = state["threshold_calibration"]
    summary = state["summary"]
    dense = summary["dense_only"]
    hybrid = summary["hybrid_rrf"]
    metric_keys = (
        ("Faithfulness", "faithfulness"),
        ("Answer relevance", "answer_relevance"),
        ("Context recall", "context_recall"),
        ("Context precision", "context_precision"),
        ("**Average**", "average"),
    )
    rows = []
    for label, key in metric_keys:
        left, right = dense[key], hybrid[key]
        delta = None if left is None or right is None else right - left
        rows.append(f"| {label} | {_fmt(left)} | {_fmt(right)} | {_fmt(delta)} |")

    winner = "hybrid + RRF" if (hybrid["average"] or 0) >= (dense["average"] or 0) else "dense-only"
    ranked = []
    for case in state["cases"]:
        values = [value for value in case["scores"].values() if value is not None]
        ranked.append((statistics.fmean(values) if values else math.inf, case))
    worst = sorted(ranked, key=lambda pair: pair[0])[:3]
    worst_rows = []
    for index, (_, case) in enumerate(worst, 1):
        score = case["scores"]
        worst_rows.append(
            f"| {index} | {case['question'].replace('|', '/')} | {case['config']} | "
            f"{_fmt(score.get('faithfulness'))} | {_fmt(score.get('answer_relevance'))} | "
            f"{_fmt(score.get('context_recall'))} | {_fmt(score.get('context_precision'))} | "
            "retrieval/generation | Điểm trung bình thấp; kiểm tra context và câu trả lời trong benchmark_results.json |"
        )

    report = f"""# RAG evaluation results

## Run information

| Field | Value |
|---|---|
| Evaluation date | {info['date']} |
| Framework and version | Ragas {info['ragas_version']} |
| Evaluator model | `{info['evaluator_model']}` |
| Generator model | `{info['generator_model']}` |
| Embedding model | `{info['embedding_model']}` |
| Evaluator embedding | `{info['evaluator_embedding_model']}` |
| Corpus version/commit | `{info['commit']}`; 3 legal + 10 news documents |
| Golden dataset size | {info['golden_dataset_size']} |
| `top_k` | {info['top_k']} |
| Fallback threshold and calibration | `{calibration['threshold']:.4f}`; balanced accuracy {_fmt(calibration['balanced_accuracy'])} trên {calibration['in_domain_count']} in-domain + {calibration['out_of_domain_count']} out-of-domain queries |

## Configurations

- **Config A — dense-only:** semantic search, không BM25/RRF/PageIndex.
- **Config B — hybrid + RRF:** dense + BM25, fuse RRF đúng một lần với `k=60`, không PageIndex trong A/B.

Hai config dùng cùng corpus, golden dataset, generator, evaluator, prompt và `top_k`; chỉ thay retrieval strategy.

## Overall scores

| Metric | Config A | Config B | Delta B−A |
|---|---:|---:|---:|
{chr(10).join(rows)}

Latency trung bình: dense-only `{dense['latency_seconds']:.2f}s/query`, hybrid + RRF `{hybrid['latency_seconds']:.2f}s/query`.

## A/B comparison

- Cấu hình tốt hơn theo trung bình bốn metric: **{winner}**.
- Evidence: average dense-only `{_fmt(dense['average'])}`, hybrid + RRF `{_fmt(hybrid['average'])}`, delta `{_fmt((hybrid['average'] or 0) - (dense['average'] or 0))}`.
- Trade-off: hybrid chạy thêm BM25 và RRF; chênh lệch latency đo được là `{hybrid['latency_seconds'] - dense['latency_seconds']:.2f}s/query`.
- Dữ liệu chi tiết từng câu, context, answer, latency và metric nằm trong `benchmark_results.json`.

## Threshold calibration

- Threshold đề xuất: `{calibration['threshold']:.4f}`.
- In-domain recall: `{_fmt(calibration['in_domain_recall'])}`.
- Out-of-domain specificity: `{_fmt(calibration['out_of_domain_specificity'])}`.
- Threshold chỉ dùng cho fallback runtime; A/B đã tắt fallback để cô lập retrieval strategy.

## Worst performers

| # | Question | Config | Faithfulness | Relevance | Recall | Precision | Failure stage | Root cause |
|---:|---|---|---:|---:|---:|---:|---|---|
{chr(10).join(worst_rows)}

## Recommendations

| Priority | Action | Evidence from failure analysis | Expected impact | How to verify |
|---:|---|---|---|---|
| 1 | Kiểm tra thủ công ba case thấp nhất và bổ sung/điều chỉnh chunk liên quan | Các case trong bảng Worst performers có điểm trung bình thấp nhất | Tăng context recall và precision | Chạy lại đúng ba case và so sánh metric |
| 2 | Dùng threshold `{calibration['threshold']:.4f}` thay cho mặc định 0.3 sau khi xác nhận trên tập holdout | Calibration đạt balanced accuracy {_fmt(calibration['balanced_accuracy'])} | Giảm fallback sai | Đánh giá thêm query in/out-domain chưa dùng khi calibration |
| 3 | Tối ưu prompt/citation cho các case faithfulness thấp | Benchmark lưu answer và source của từng case | Giảm unsupported claims | Chạy lại Ragas faithfulness trên cùng context |

## Bonus experiments

| Experiment | Baseline | Metric delta | Latency/cost delta | Conclusion |
|---|---|---:|---:|---|
| Chưa thực hiện | Config B | N/A | N/A | Ưu tiên ổn định baseline trước khi thử HyDE/reranker nâng cao |
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-generation", action="store_true")
    parser.add_argument("--skip-evaluation", action="store_true")
    parser.add_argument("--evaluation-limit", type=int, default=None)
    args = parser.parse_args()

    settings = _settings()
    golden = _load_json(GOLDEN_PATH)
    if args.limit is not None:
        golden = golden[: max(0, args.limit)]
    state = _load_json(RESULTS_PATH) if RESULTS_PATH.exists() and not args.force else _new_state(settings, len(golden))
    state["run_info"] = _new_state(settings, len(golden))["run_info"]

    if not args.skip_generation:
        generate_cases(golden, state, force=args.force)
    calibrate_threshold(golden, state)
    if not args.skip_evaluation:
        evaluate_cases(state, settings, evaluation_limit=args.evaluation_limit)
        write_report(state)
    _atomic_json(RESULTS_PATH, state)
    print(f"Saved: {RESULTS_PATH.relative_to(PROJECT_DIR)}")
    if not args.skip_evaluation:
        print(f"Saved: {REPORT_PATH.relative_to(PROJECT_DIR)}")


if __name__ == "__main__":
    main()
