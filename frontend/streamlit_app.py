"""Streamlit UI for InsightSQL."""
from __future__ import annotations
import sys
from pathlib import Path

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

with st.form("query-form"):
    query = st.text_input(
        "Business question",
        key="query",
        placeholder="Top customers by revenue",
    )
    submitted = st.form_submit_button("Run query", type="primary")

if submitted and query.strip():
    with st.spinner("Agents are working through the query..."):
        state = run_agent_pipeline(query.strip())

    st.subheader("Explanation")
    st.write(state.get("explanation", "No explanation was generated."))

    if state.get("error"):
        st.error(state["error"])
    elif state.get("data_source") == "demo":
        st.info("Running on built-in demo data because PostgreSQL is unavailable.")
    elif state.get("data_source") == "postgres":
        st.success("Running on PostgreSQL.")

    if state.get("out_of_scope"):
        st.warning(
            "Out-of-domain question detected. Try asking about customers, orders, "
            "products, suppliers, employees, shipping, revenue, or inventory."
        )

    if state.get("is_ambiguous") and state.get("clarification"):
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

    with st.expander("Generated SQL"):
        st.code(state.get("sql", ""), language="sql")

    with st.expander("Agent State"):
        st.json({
            "refined_query":     state.get("refined_query"),
            "retry_count":       state.get("retry_count"),
            "validation":        state.get("validation"),
            "data_source":       state.get("data_source"),
            "out_of_scope":      state.get("out_of_scope"),
            "workflow_engine":   "langgraph",
            "llm_provider":      "groq",
            "llm_model":         settings.groq_model,
            "langsmith_tracing": settings.langsmith_tracing,
            "db_health":         db_health,
        })

elif submitted:
    st.warning("Enter a query to run the agent pipeline.")
