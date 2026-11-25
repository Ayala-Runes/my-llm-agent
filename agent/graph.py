from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agent import nodes

MAX_ATTEMPTS = 3


class AgentState(TypedDict, total=False):
    cv_text: str
    job_text: str
    analysis: str
    tailored: str
    eval_passed: bool
    eval_feedback: str
    attempts: int
    approved: bool
    output_path: str
    error: str


def after_guardrails(state: AgentState) -> str:
    return END if state.get("error") else "gap_analyzer"


def after_gap_analyzer(state: AgentState) -> str:
    return END if state.get("error") else "tailor"


def after_evaluator(state: AgentState) -> str:
    if state.get("eval_passed") or state.get("attempts", 0) >= MAX_ATTEMPTS:
        return "gate"
    return "tailor"


def after_gate(state: AgentState) -> str:
    return "writer" if state.get("approved") else END


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("guardrails", nodes.guardrails)
    graph.add_node("gap_analyzer", nodes.gap_analyzer)
    graph.add_node("tailor", nodes.tailor)
    graph.add_node("evaluator", nodes.evaluator)
    graph.add_node("gate", nodes.gate)
    graph.add_node("writer", nodes.writer)

    graph.set_entry_point("guardrails")
    graph.add_conditional_edges("guardrails", after_guardrails)
    graph.add_conditional_edges("gap_analyzer", after_gap_analyzer)
    graph.add_edge("tailor", "evaluator")
    graph.add_conditional_edges("evaluator", after_evaluator)
    graph.add_conditional_edges("gate", after_gate)
    graph.add_edge("writer", END)

    # A checkpointer is required so the graph can pause at the gate and resume.
    return graph.compile(checkpointer=MemorySaver())


graph = build_graph()