import truststore
truststore.inject_into_ssl()

import os

from dotenv import load_dotenv
from docx import Document
from docx.oxml import OxmlElement
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.types import interrupt

from agent.tools import retrieve

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = os.environ.get("MODEL_NAME", "anthropic/claude-sonnet-5")
DEFAULT_OUTPUT = "tailored_cv.docx"
MAX_OUTPUT_TOKENS = 2048  # caps cost per call; a CV rewrite fits well within this


def get_llm(model: str | None = None, temperature: float = 0.2) -> ChatOpenAI:
    """Return a chat model served through OpenRouter.

    The model is read from DEFAULT_MODEL at call time, so evals can switch models.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is missing. Add it to the .env file in the project root."
        )
    return ChatOpenAI(
        model=model or DEFAULT_MODEL,
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
        temperature=temperature,
        max_tokens=MAX_OUTPUT_TOKENS,
    )


# Every model call is also logged here, so evals can read token counts directly.
USAGE_LOG: list[dict] = []


def _ask(system: str, user: str, node: str, temperature: float = 0.2) -> tuple[str, dict]:
    """Call the model and return (answer, usage record for this call)."""
    llm = get_llm(temperature=temperature)
    reply = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    usage = getattr(reply, "usage_metadata", None) or {}
    record = {
        "node": node,
        "model": llm.model_name,
        "input_tokens": int(usage.get("input_tokens", 0)),
        "output_tokens": int(usage.get("output_tokens", 0)),
    }
    USAGE_LOG.append(record)
    content = reply.content if isinstance(reply.content, str) else ""
    if not content.strip():
        # Usually a reasoning model used up max_tokens while thinking.
        raise RuntimeError(
            "The model returned an empty answer. Try a different MODEL_NAME "
            "or raise MAX_OUTPUT_TOKENS in agent/nodes.py."
        )
    return content, record


def guardrails(state: dict) -> dict:
    """Reject empty input, and input that is not a CV, before any tailoring work."""
    cv = (state.get("cv_text") or "").strip()
    job = (state.get("job_text") or "").strip()
    if not cv or not job:
        return {"error": "Missing CV or job description."}

    verdict, record = _ask(
        "You check whether a text is a CV (resume) document. Reply only YES or NO.",
        cv[:4000],
        node="guardrails",
        temperature=0.0,
    )
    if not verdict.strip().upper().startswith("YES"):
        return {
            "error": (
                "The first input is not a CV. This agent only tailors a CV to a job "
                "description, so the request was refused and nothing was saved."
            ),
            "usage": [record],
        }
    return {"cv_text": cv, "job_text": job, "attempts": 0, "usage": [record]}


def gap_analyzer(state: dict) -> dict:
    """Compare CV and job. Stop the run if the CV is from a clearly different field."""
    system = (
        "You compare a CV with a job description. On the first line reply FIT or NO_FIT. "
        "Reply NO_FIT only when the candidate's field is clearly different from the job's field. "
        "Then give a short analysis in English with three parts: matching skills, "
        "missing skills, and points to emphasize. Do not suggest experience that is not in the CV."
    )
    user = f"CV:\n{state['cv_text']}\n\nJob:\n{state['job_text']}"
    verdict, record = _ask(system, user, node="gap_analyzer", temperature=0.0)
    first, _, rest = verdict.strip().partition("\n")
    if first.strip().upper().startswith("NO_FIT"):
        return {
            "error": (
                "The CV does not match the job description, so nothing was saved. "
                "Check that you chose the right CV file and job description."
            ),
            "analysis": rest.strip(),
            "usage": [record],
        }
    return {"analysis": rest.strip() or verdict, "usage": [record]}


def tailor(state: dict) -> dict:
    system = (
        "Rewrite the CV for the job, in the same language as the original CV. You may reorder and reword. "
        "Use only facts that appear in the original CV. Never add degrees, years, "
        "employers, titles or skills that are not in it. "
        "Format the output as plain text: start each section heading line with '# ', "
        "start each bullet point with '- ', and write everything else as normal lines. "
        "Return only the rewritten CV, with no commentary."
    )
    user = f"Original CV:\n{state['cv_text']}\n\nAnalysis:\n{state['analysis']}"
    # RAG: add the writing guidelines that match this job and CV.
    snippets = retrieve(f"{state['job_text']}\n{state['analysis']}")
    if snippets:
        user += "\n\nWriting guidelines to follow:\n" + "\n\n".join(snippets)
    feedback = state.get("eval_feedback", "")
    if feedback:
        user += f"\n\nFix these problems from the previous attempt:\n{feedback}"
    text, record = _ask(system, user, node="tailor")
    return {
        "tailored": text,
        "attempts": state.get("attempts", 0) + 1,
        "usage": [record],
    }


def evaluator(state: dict) -> dict:
    system = (
        "You check a rewritten CV against the original. Reply with PASS on the first line "
        "if every fact in the rewrite appears in the original. Otherwise reply FAIL on the "
        "first line and list the problems below it."
    )
    user = f"Original:\n{state['cv_text']}\n\nRewrite:\n{state['tailored']}"
    verdict, record = _ask(system, user, node="evaluator", temperature=0.0)
    verdict = verdict.strip()
    first, _, rest = verdict.partition("\n")
    passed = first.strip().upper().startswith("PASS")
    return {
        "eval_passed": passed,
        "eval_feedback": "" if passed else (rest.strip() or verdict),
        "usage": [record],
    }


def gate(state: dict) -> dict:
    """Pause the graph and ask the user before saving (HITL)."""
    answer = interrupt(
        {
            "tailored": state["tailored"],
            "passed_check": state.get("eval_passed", False),
            "question": "Save the new version? [Y/N]",
        }
    )
    return {"approved": str(answer).strip().lower() in ("y", "yes")}


def _is_hebrew(text: str) -> bool:
    return any("֐" <= ch <= "׿" for ch in text)


def _set_rtl(paragraph) -> None:
    """Mark a paragraph as right-to-left."""
    pPr = paragraph._p.get_or_add_pPr()
    # Right-to-left paragraphs align to the right by default, so no explicit jc is set.
    pPr.append(OxmlElement("w:bidi"))


def writer(state: dict) -> dict:
    out = state.get("output_path") or DEFAULT_OUTPUT
    doc = Document()
    for raw in state["tailored"].splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("# "):
            paragraph = doc.add_heading(line[2:].strip(), level=2)
        elif line.startswith("- "):
            paragraph = doc.add_paragraph(line[2:].strip(), style="List Bullet")
        else:
            paragraph = doc.add_paragraph(line)
        if _is_hebrew(line):
            _set_rtl(paragraph)
    doc.save(out)
    return {"output_path": out}