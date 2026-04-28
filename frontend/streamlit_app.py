"""Streamlit UI for InsightSQL."""
from __future__ import annotations
import sys
import warnings
from collections import deque
from pathlib import Path

warnings.filterwarnings("ignore", message="Accessing `__path__`")

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.controller import run_agent_pipeline
from backend.app.core.config import get_settings
from backend.app.db.health import check_database_health

st.set_page_config(page_title="InsightSQL", layout="wide")
settings = get_settings()

EXAMPLE_QUERIES = [
    "Top customers by revenue",
    "Recent orders",
    "Best products",
    "Sales by category",
    "Employees by revenue",
    "Average freight by shipper",
    "Highest sold car model",
]


def _history() -> deque[str]:
    if "history" not in st.session_state:
        st.session_state["history"] = deque(maxlen=10)
    elif not isinstance(st.session_state["history"], deque):
        st.session_state["history"] = deque(st.session_state["history"], maxlen=10)
    return st.session_state["history"]


def _remember(query: str) -> None:
    history = _history()
    if query in history:
        history.remove(query)
    history.appendleft(query)
    st.session_state["history"] = history


def _run_query(query: str) -> None:
    with st.spinner("Agents are working through the query..."):
        state = run_agent_pipeline(query.strip())
    if state.get("pending_clarification"):
        st.session_state["pending_state"] = state
    else:
        _remember(query.strip())
        st.session_state.pop("pending_state", None)
    st.session_state["last_state"] = state


def _resume_with_clarification(answer: str) -> None:
    pending = st.session_state.get("pending_state")
    if not pending:
        return
    with st.spinner("Resuming the agent pipeline..."):
        state = run_agent_pipeline(prior_state=pending, user_clarification=answer.strip())
    if state.get("pending_clarification") and state.get("clarification_attempts", 0) < 2:
        st.session_state["pending_state"] = state
    else:
        _remember(state.get("query", ""))
        st.session_state.pop("pending_state", None)
    st.session_state["last_state"] = state


def _markdown_plain(text: str) -> str:
    return text.replace("$", r"\$")


def _render_state(state: dict) -> None:
    if state.get("pending_clarification"):
        st.subheader("Clarification")
        st.info(state.get("clarification_question") or "Please clarify the question.")
        with st.form("clarification-form"):
            answer = st.text_input("Clarification", placeholder="For example: by category")
            submitted = st.form_submit_button("Submit", type="primary")
        if submitted and answer.strip():
            _resume_with_clarification(answer)
            st.rerun()
        elif submitted:
            st.warning("Enter a clarification to continue.")
        return

    st.subheader("Explanation")
    st.markdown(_markdown_plain(state.get("explanation", "No explanation was generated.")))

    if state.get("cardinality_warning"):
        st.warning(state["cardinality_warning"])
    if state.get("error") and not state.get("out_of_scope"):
        st.error(state["error"])
    elif state.get("data_source") == "demo":
        st.info("Running on built-in demo data because PostgreSQL is unavailable.")
    elif state.get("data_source") == "postgres":
        st.success("Running on PostgreSQL.")

    if state.get("disambiguation_triggered") and state.get("clarification"):
        st.info(f"Default assumption applied: {state['clarification']}")
    elif state.get("applied_clarification"):
        st.info(f"Clarification applied: {state['refined_query']}")
    elif (
        state.get("clarification")
        and not state.get("pending_clarification")
        and not state.get("user_clarification")
    ):
        st.info(state["clarification"])

    trace_rows = state.get("agent_trace", [])
    if trace_rows:
        st.subheader("Agent Trace")
        st.dataframe(pd.DataFrame(trace_rows), use_container_width=True, hide_index=True)

    st.subheader("Results")
    rows = state.get("result", [])
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.write("No rows to display.")

    with st.expander("Retrieved schema context (top-3)"):
        chunks = state.get("retrieved_schema_chunks", [])
        if chunks:
            for chunk in chunks:
                st.write(f"{chunk.get('text', '')}  Score: {chunk.get('score', 'n/a')}")
        else:
            st.write("No RAG schema chunks were retrieved.")

    with st.expander("Retrieved examples (top-2)"):
        examples = state.get("retrieved_examples", [])
        if examples:
            for example in examples:
                st.write(f"Q: {example.get('question', '')}")
                st.code(example.get("sql", example.get("text", "")), language="sql")
        else:
            st.write("No examples were retrieved.")

    with st.expander("Generated SQL"):
        st.code(state.get("sql", ""), language="sql")

    with st.expander("Agent State"):
        st.json({
            "refined_query":     state.get("refined_query"),
            "retry_count":       state.get("retry_count"),
            "validation":        state.get("validation"),
            "validation_layers": state.get("validation_layers_triggered"),
            "failed_layer":      state.get("failed_layer"),
            "data_source":       state.get("data_source"),
            "out_of_scope":      state.get("out_of_scope"),
            "workflow_engine":   "langgraph",
            "llm_provider":      "groq",
            "llm_model":         settings.groq_model,
            "langsmith_tracing": settings.langsmith_tracing,
            "db_health":         db_health,
        })


st.title("InsightSQL")
st.caption("Agentic NL2SQL prototype for Northwind analytics")

if not settings.groq_api_key:
    st.error(
        "GROQ_API_KEY is not set — SQL generation will fail. "
        "Add GROQ_API_KEY to your .env file and restart."
    )

db_health = check_database_health()

with st.sidebar:
    st.header("System Status")
    if db_health["is_connected"]:
        st.success(db_health["message"])
    else:
        st.warning(db_health["message"])
        st.caption(db_health["hint"])
    st.caption(db_health["database_url"])

    st.header("Agent Stack")
    st.write("Workflow: LangGraph")
    st.write(f"LLM: groq / {settings.groq_model}")
    st.write(
        "LangSmith: enabled"
        if settings.langsmith_tracing and settings.langsmith_api_key
        else "LangSmith: configured off"
    )

    st.header("Demo Queries")
    for example_query in EXAMPLE_QUERIES:
        if st.button(example_query, use_container_width=True):
            st.session_state["query"] = example_query
            _run_query(example_query)
            st.rerun()

    st.header("Query History")
    for idx, history_query in enumerate(list(_history())):
        if st.button(history_query, key=f"history-{idx}", use_container_width=True):
            st.session_state["query"] = history_query
            _run_query(history_query)
            st.rerun()

with st.form("query-form"):
    query = st.text_input(
        "Business question",
        key="query",
        placeholder="Top customers by revenue",
    )
    submitted = st.form_submit_button("Run query", type="primary")

if submitted and query.strip():
    _run_query(query.strip())
    st.rerun()
elif submitted:
    st.warning("Enter a query to run the agent pipeline.")

if st.session_state.get("last_state"):
    _render_state(st.session_state["last_state"])
