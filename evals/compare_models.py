"""Model comparison eval: same samples on several models, scored by a fixed judge.

For each model: how long the run takes, whether it fails, and the judge score (1-5)
from evals/rubric.md. The judge model is fixed for every comparison, so the scores
stay comparable.

Edit MODELS below, then run from the project root:
    python -m evals.compare_models
"""

import csv
import re
import time
import uuid
import tempfile
from pathlib import Path

from agent import nodes
from agent.graph import graph
from evals.samples import SAMPLES

MODELS = [
    "anthropic/claude-sonnet-5",
    "google/gemma-4-31b-it",
]
JUDGE_MODEL = "anthropic/claude-sonnet-5"
RUBRIC = (Path(__file__).parent / "rubric.md").read_text(encoding="utf-8")
RESULTS = Path(__file__).parent / "results" / "compare_models.csv"
SCORE_LINE = re.compile(r"SCORE:\s*([1-5])")


def judge(sample: dict, tailored: str) -> int | None:
    llm = nodes.get_llm(model=JUDGE_MODEL, temperature=0.0)
    prompt = (
        f"{RUBRIC}\n\nOriginal CV:\n{sample['cv']}\n\n"
        f"Job:\n{sample['job']}\n\nRewrite:\n{tailored}"
    )
    reply = llm.invoke(prompt).content
    match = SCORE_LINE.search(reply if isinstance(reply, str) else "")
    return int(match.group(1)) if match else None


def run_one(model: str, sample: dict) -> dict:
    nodes.DEFAULT_MODEL = model
    thread = {"configurable": {"thread_id": str(uuid.uuid4())}}
    output = str(Path(tempfile.mkdtemp()) / "compare.docx")
    started = time.perf_counter()
    error = ""
    tailored = ""
    try:
        graph.invoke(
            {"cv_text": sample["cv"], "job_text": sample["job"], "output_path": output},
            thread,
        )
        values = graph.get_state(thread).values
        error = values.get("error", "")
        tailored = values.get("tailored", "")
    except Exception as exc:  # noqa: BLE001 - record the failure and keep going
        error = str(exc)
    seconds = round(time.perf_counter() - started, 2)

    score = judge(sample, tailored) if tailored else None
    return {
        "model": model,
        "sample": sample["name"],
        "seconds": seconds,
        "score": score if score is not None else "",
        "error": error,
    }


def main() -> int:
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for model in MODELS:
        for sample in SAMPLES:
            row = run_one(model, sample)
            rows.append(row)
            print(f"[INFO] {model} | {sample['name']} | {row['seconds']}s | score={row['score']} | {row['error'][:80]}")

    fields = ["model", "sample", "seconds", "score", "error"]
    with RESULTS.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[INFO] Results saved to {RESULTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())