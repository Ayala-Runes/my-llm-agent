"""Interactive command-line interface for the CV tailor agent.

Run from the project root:
    python -m agent.cli
"""

import uuid
from pathlib import Path

from langgraph.types import Command

from agent import nodes
from agent.graph import graph
from agent.nodes import DEFAULT_OUTPUT
from agent.pricing import cost_of

HELP_TEXT = """
Commands:
  <path>       Paste the path to your CV file to start a new job
  help or ?    Show this help
  exit         Quit

During a job, the new version is shown and you are asked to confirm with Y or N.
The CV can be a .txt or .docx file.
"""


def read_document(path: Path) -> str:
    """Read a .txt or .docx file and return its text."""
    if path.suffix.lower() == ".docx":
        from docx import Document

        return "\n".join(p.text for p in Document(str(path)).paragraphs)
    return path.read_text(encoding="utf-8")


def read_cv(path_text: str) -> str:
    path = Path(path_text.strip().strip('"'))
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    return read_document(path)


def read_job(text: str) -> str:
    """The job can be a file path (.txt or .docx) or the text itself."""
    candidate = Path(text.strip().strip('"'))
    if candidate.is_file():
        return read_document(candidate)
    return text.strip()


def stream_graph(payload, thread: dict) -> None:
    """Run the graph and print each node as it completes."""
    for update in graph.stream(payload, thread, stream_mode="updates"):
        for node in update:
            if node != "__interrupt__":
                print(f"[INFO] Completed Node: {node}")


def print_usage() -> None:
    """Show tokens and cost per step, and the total, at the end of a run."""
    records = list(nodes.USAGE_LOG)
    if not records:
        return
    print("\n[INFO] Usage for this run:")
    total_cost = 0.0
    for record in records:
        cost = cost_of(record["model"], record["input_tokens"], record["output_tokens"])
        total_cost += cost
        print(
            f"  {record['node']:<14} in={record['input_tokens']:<6} "
            f"out={record['output_tokens']:<6} ${cost:.6f}"
        )
    total_in = sum(r["input_tokens"] for r in records)
    total_out = sum(r["output_tokens"] for r in records)
    print(f"  Total          in={total_in:<6} out={total_out:<6} ${total_cost:.6f}")


def run_job(cv_text: str, job_text: str, output_path: str) -> None:
    nodes.USAGE_LOG.clear()
    thread = {"configurable": {"thread_id": str(uuid.uuid4())}}
    payload = {"cv_text": cv_text, "job_text": job_text, "output_path": output_path}
    stream_graph(payload, thread)

    # The graph pauses at the gate node and waits for a Y/N answer.
    while True:
        snapshot = graph.get_state(thread)
        if not snapshot.next:
            break
        request = snapshot.tasks[0].interrupts[0].value
        print("\n--- Proposed version ---")
        print(request["tailored"])
        print(f"\n[INFO] Check passed: {request['passed_check']}")
        answer = input(f"\n{request['question']} ").strip()
        stream_graph(Command(resume=answer), thread)

    final = graph.get_state(thread).values
    if final.get("error"):
        # A refusal is intentional (not a crash): say so, and that nothing was saved.
        print(f"[REFUSED] {final['error']}")
    elif final.get("approved"):
        print(f"[INFO] Saved: {final.get('output_path')}")
    else:
        print("[INFO] Not saved.")
    print(f"[INFO] Attempts: {final.get('attempts', 0)}")
    print_usage()


def main() -> None:
    print("CV Tailor Agent")
    print("Paste the path to your CV file to start.")
    print("Type help for more options, or exit to quit.")
    while True:
        try:
            entry = input("\nCV file path (or help / exit): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        command = entry.lower()
        if command in ("exit", "quit"):
            break
        if command in ("help", "?"):
            print(HELP_TEXT)
            continue
        if command == "":
            continue

        try:
            cv_text = read_cv(entry)
            job_text = read_job(input("Job description (file path or text): "))
            output = input(f"Output file path [{DEFAULT_OUTPUT}]: ").strip()
            run_job(cv_text, job_text, output or DEFAULT_OUTPUT)
        except Exception as exc:  # noqa: BLE001 - show any failure plainly
            print(f"[ERROR] {exc}")


if __name__ == "__main__":
    main()