
import sys

from agent.nodes import get_llm


def main() -> int:
    try:
        llm = get_llm()
        reply = llm.invoke("Reply with one short sentence in Hebrew.")
    except Exception as exc:  # noqa: BLE001 - show any failure plainly
        print(f"[ERROR] Connection failed: {exc}")
        return 

    print("[INFO] Connection OK")
    print(reply.content)


if __name__ == "__main__":
    sys.exit(main())
