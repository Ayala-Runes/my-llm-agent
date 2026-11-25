"""Scope eval: the agent must refuse requests that are not CVs.

Each off-topic question is sent as the CV input. A correct refusal stops the run
with an error before any tailoring happens. The refusal rate is written to a CSV.

Run from the project root:
    python -m evals.scope_eval
"""

import csv
import tempfile
import uuid
from pathlib import Path

from agent.graph import graph

OFF_TOPIC = [
    "What is the weather in Tel Aviv tomorrow?",
    "Write me a recipe for chocolate cake.",
    "Who won the football match yesterday?",
    "Explain photosynthesis in simple words.",
    "Write a short poem about the sea.",
    "What time is it in New York right now?",
]

JOB = "Python developer with SQL experience, full-time, Tel Aviv."
RESULTS = Path(__file__).parent / "results" / "scope_eval.csv"


def is_refused(question: str) -> tuple[bool, str]:
    thread = {"configurable": {"thread_id": str(uuid.uuid4())}}
    output = str(Path(tempfile.mkdtemp()) / "should_not_exist.docx")
    result = graph.invoke(
        {"cv_text": question, "job_text": JOB, "output_path": output},
        thread,
    )
    error = result.get("error") or ""
    return bool(error), error


def main() -> int:
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for question in OFF_TOPIC:
        refused, message = is_refused(question)
        rows.append({"question": question, "refused": refused, "message": message})
        print(f"[INFO] refused={refused} | {question}")

    with RESULTS.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["question", "refused", "message"])
        writer.writeheader()
        writer.writerows(rows)

    correct = sum(row["refused"] for row in rows)
    rate = 100 * correct / len(rows)
    print(f"[INFO] Refusal rate: {correct}/{len(rows)} ({rate:.0f}%)")
    print(f"[INFO] Results saved to {RESULTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
