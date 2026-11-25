"""Cost eval: tokens and cost for each step of one run, on each sample.

Prices are USD per million tokens, (input, output). Update them from openrouter.ai/models.
Free models are reported at cost 0, and also with a theoretical cost, which is what the
same tokens would cost at the reference paid model.

Run from the project root:
    python -m evals.cost_eval
"""

import csv
import tempfile
import uuid
from pathlib import Path

from agent import nodes, pricing
from agent.graph import graph
from evals.samples import SAMPLES

PRICES = pricing.PRICES
REFERENCE_MODEL = pricing.REFERENCE_MODEL
RESULTS = Path(__file__).parent / "results" / "cost_eval.csv"


def price_of(model: str) -> tuple[float, float]:
    if model not in PRICES:
        print(f"[WARN] No price set for {model}; cost counted as 0.")
    return PRICES.get(model, (0.0, 0.0))


def cost_of(record: dict, prices: tuple[float, float]) -> float:
    in_price, out_price = prices
    return (record["input_tokens"] * in_price + record["output_tokens"] * out_price) / 1_000_000


def run_sample(sample: dict) -> list[dict]:
    """Run the graph up to the approval step and return one row per model call."""
    thread = {"configurable": {"thread_id": str(uuid.uuid4())}}
    output = str(Path(tempfile.mkdtemp()) / "cost_eval.docx")
    nodes.USAGE_LOG.clear()
    graph.invoke(
        {"cv_text": sample["cv"], "job_text": sample["job"], "output_path": output},
        thread,
    )
    records = list(nodes.USAGE_LOG)

    reference = PRICES.get(REFERENCE_MODEL, (0.0, 0.0))
    rows = []
    for record in records:
        prices = price_of(record["model"])
        actual = cost_of(record, prices)
        theoretical = actual if actual > 0 else cost_of(record, reference)
        rows.append(
            {
                "sample": sample["name"],
                "node": record["node"],
                "model": record["model"],
                "input_tokens": record["input_tokens"],
                "output_tokens": record["output_tokens"],
                "cost_usd": round(actual, 6),
                "theoretical_cost_usd": round(theoretical, 6),
            }
        )
    return rows


def main() -> int:
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for sample in SAMPLES:
        sample_rows = run_sample(sample)
        rows.extend(sample_rows)
        total = sum(r["cost_usd"] for r in sample_rows)
        theoretical = sum(r["theoretical_cost_usd"] for r in sample_rows)
        print(f"[INFO] {sample['name']}: cost ${total:.6f} (theoretical ${theoretical:.6f})")
        for r in sample_rows:
            print(f"        {r['node']:<14} in={r['input_tokens']:<6} out={r['output_tokens']:<6} ${r['cost_usd']:.6f}")

    fields = ["sample", "node", "model", "input_tokens", "output_tokens", "cost_usd", "theoretical_cost_usd"]
    with RESULTS.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    total_cost = sum(r["cost_usd"] for r in rows)
    total_theory = sum(r["theoretical_cost_usd"] for r in rows)
    print(f"[INFO] Total cost: ${total_cost:.6f} (theoretical ${total_theory:.6f})")
    print(f"[INFO] Results saved to {RESULTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())