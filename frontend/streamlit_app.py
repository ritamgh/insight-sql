"""Streamlit UI for InsightSQL."""
from __future__ import annotations
import html
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


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --ink: #15202b;
            --muted: #5d6b7a;
            --line: #dce3ea;
            --panel: #ffffff;
            --soft: #f6f8fb;
            --accent: #0f766e;
            --accent-2: #2563eb;
            --warn: #b45309;
            --bad: #b91c1c;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(15, 118, 110, 0.08), transparent 32rem),
                linear-gradient(180deg, #fbfcfe 0%, #f3f6fa 100%);
            color: var(--ink);
        }

        .block-container {
            padding-top: 3.25rem;
            padding-bottom: 4rem;
            max-width: 1280px;
        }

        [data-testid="stSidebar"] {
            background: #101820;
            color: #f8fafc;
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }

        [data-testid="stSidebar"] * {
            color: #f8fafc;
        }

        [data-testid="stSidebar"] .stCaption,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
            color: rgba(248, 250, 252, 0.78);
        }

        [data-testid="stSidebar"] .stButton > button {
            background: rgba(255, 255, 255, 0.08);
            color: #f8fafc;
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-radius: 8px;
            min-height: 2.35rem;
        }

        [data-testid="stSidebar"] .stButton > button:hover {
            background: rgba(255, 255, 255, 0.14);
            border-color: rgba(255, 255, 255, 0.3);
        }

        h1, h2, h3 {
            letter-spacing: 0;
            color: var(--ink);
        }

        h1 {
            font-size: 2.3rem;
            line-height: 1.05;
            margin-bottom: 0.25rem;
        }

        h2, h3 {
            margin-top: 0.35rem;
        }

        .hero {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 1.5rem;
            align-items: end;
            margin-top: 0.35rem;
            margin-bottom: 1.1rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--line);
        }

        .hero-kicker {
            color: var(--accent);
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }

        .hero-copy {
            color: var(--muted);
            font-size: 1.02rem;
            max-width: 50rem;
            margin-top: 0.35rem;
        }

        .status-strip {
            display: flex;
            justify-content: flex-end;
            gap: 0.55rem;
            flex-wrap: wrap;
        }

        .pill {
            border: 1px solid var(--line);
            border-radius: 999px;
            padding: 0.38rem 0.72rem;
            background: rgba(255, 255, 255, 0.78);
            color: var(--muted);
            font-size: 0.82rem;
            font-weight: 700;
            white-space: nowrap;
        }

        .pill.good {
            color: #0f766e;
            border-color: rgba(15, 118, 110, 0.24);
            background: rgba(15, 118, 110, 0.08);
        }

        .pill.warn {
            color: var(--warn);
            border-color: rgba(180, 83, 9, 0.24);
            background: rgba(180, 83, 9, 0.08);
        }

        .query-shell {
            border: 1px solid var(--line);
            background: rgba(255, 255, 255, 0.9);
            border-radius: 8px;
            padding: 1rem 1rem 0.85rem;
            box-shadow: 0 16px 40px rgba(21, 32, 43, 0.07);
            margin-bottom: 1rem;
        }

        .section-label {
            color: var(--muted);
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin: 0 0 0.5rem;
        }

        .clarification-callout {
            border: 1px solid rgba(37, 99, 235, 0.18);
            background: #eaf3ff;
            border-radius: 8px;
            padding: 0.78rem 0.9rem;
            margin: 0.35rem 0 0.85rem;
            color: #2563eb;
            font-size: 0.9rem;
            font-weight: 750;
        }

        .answer-panel {
            border: 1px solid var(--line);
            background: var(--panel);
            border-radius: 8px;
            padding: 1.05rem 1.15rem;
            margin: 0.35rem 0 1rem;
            box-shadow: 0 10px 24px rgba(21, 32, 43, 0.045);
        }

        .answer-panel p:last-child {
            margin-bottom: 0;
        }

        .metric-row {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.75rem;
            margin: 0.25rem 0 1rem;
        }

        .metric-card {
            border: 1px solid var(--line);
            background: rgba(255, 255, 255, 0.82);
            border-radius: 8px;
            padding: 0.85rem 0.95rem;
        }

        .metric-label {
            color: var(--muted);
            font-size: 0.76rem;
            font-weight: 800;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            margin-bottom: 0.22rem;
        }

        .metric-value {
            color: var(--ink);
            font-size: 1.2rem;
            font-weight: 800;
            line-height: 1.2;
            overflow-wrap: anywhere;
        }

        .stTextInput > div > div > input {
            border-radius: 8px;
            background: #ffffff;
            color: var(--ink);
            min-height: 3rem;
            border-color: var(--line);
            font-size: 1rem;
            box-shadow: 0 12px 28px rgba(21, 32, 43, 0.05);
        }

        .stTextInput > div > div > input::placeholder {
            color: #8b97a5;
        }

        .stTextInput label {
            color: var(--muted);
            font-weight: 800;
        }

        [data-testid="stForm"] {
            border: 0;
            padding: 0;
            margin: 0;
        }

        [data-testid="stForm"] > div {
            padding: 0;
        }

        .stButton > button,
        .stFormSubmitButton > button {
            border-radius: 8px;
            min-height: 2.7rem;
            font-weight: 800;
        }

        .stFormSubmitButton > button[kind="primary"],
        .stButton > button[kind="primary"] {
            background: #ff6b6b;
            border-color: #ff6b6b;
            color: #ffffff;
        }

        .stFormSubmitButton > button[kind="primary"]:hover,
        .stButton > button[kind="primary"]:hover {
            background: #ff7f7f;
            border-color: #ff7f7f;
            color: #ffffff;
        }

        [data-testid="stDataFrame"] {
            border: 1px solid var(--line);
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 10px 24px rgba(21, 32, 43, 0.04);
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 1.25rem;
            border-bottom: 1px solid var(--line);
        }

        .stTabs [data-baseweb="tab"] {
            color: #526273;
            font-weight: 800;
            padding-left: 0;
            padding-right: 0;
        }

        .stTabs [data-baseweb="tab"] p {
            color: #526273;
            font-size: 1rem;
            font-weight: 800;
        }

        .stTabs [aria-selected="true"] {
            color: #ef4444;
        }

        .stTabs [aria-selected="true"] p {
            color: #ef4444;
        }

        .streamlit-expanderHeader {
            font-weight: 800;
            color: var(--ink);
        }

        div[data-testid="stAlert"] {
            border-radius: 8px;
            border: 1px solid rgba(21, 32, 43, 0.08);
        }

        @media (max-width: 900px) {
            .hero {
                grid-template-columns: 1fr;
                align-items: start;
            }

            .status-strip {
                justify-content: flex-start;
            }

            .metric-row {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @media (max-width: 560px) {
            .metric-row {
                grid-template-columns: 1fr;
            }

            h1 {
                font-size: 1.9rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _panel(text: str) -> None:
    safe_text = html.escape(text).replace("\n", "<br>")
    st.markdown(f'<div class="answer-panel">{safe_text}</div>', unsafe_allow_html=True)


def _metric_row(items: list[tuple[str, str]]) -> None:
    cards = "".join(
        (
            '<div class="metric-card">'
            f'<div class="metric-label">{html.escape(label)}</div>'
            f'<div class="metric-value">{html.escape(value)}</div>'
            "</div>"
        )
        for label, value in items
    )
    st.markdown(f'<div class="metric-row">{cards}</div>', unsafe_allow_html=True)


def _status_pill(label: str, ok: bool | None = None) -> str:
    klass = "pill"
    if ok is True:
        klass += " good"
    elif ok is False:
        klass += " warn"
    return f'<span class="{klass}">{html.escape(label)}</span>'


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
        st.markdown('<div class="section-label">Clarification needed</div>', unsafe_allow_html=True)
        question = html.escape(state.get("clarification_question") or "Please clarify the question.")
        st.markdown(
            f'<div class="clarification-callout">{question}</div>',
            unsafe_allow_html=True,
        )
        with st.form("clarification-form"):
            answer_col, submit_col = st.columns([5, 1])
            with answer_col:
                answer = st.text_input(
                    "Clarification",
                    placeholder="For example: last 30 days",
                    label_visibility="collapsed",
                )
            with submit_col:
                submitted = st.form_submit_button(
                    "Submit",
                    type="primary",
                    use_container_width=True,
                )
        if submitted and answer.strip():
            _resume_with_clarification(answer)
            st.rerun()
        elif submitted:
            st.warning("Enter a clarification to continue.")
        return

    rows = state.get("result", [])
    trace_rows = state.get("agent_trace", [])
    data_source = state.get("data_source") or "n/a"
    validation = state.get("validation") or {}
    validation_status = "passed" if validation.get("is_valid") else "not run"
    if state.get("error"):
        validation_status = "attention"

    _metric_row(
        [
            ("Rows", str(len(rows))),
            ("Data Source", str(data_source).title()),
            ("Validation", validation_status.title()),
            ("Retries", str(state.get("retry_count", 0))),
        ]
    )

    st.markdown('<div class="section-label">Answer</div>', unsafe_allow_html=True)
    _panel(state.get("explanation", "No explanation was generated."))

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

    st.markdown('<div class="section-label">Results</div>', unsafe_allow_html=True)
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No rows to display.")

    sql_tab, trace_tab, context_tab, state_tab = st.tabs(
        ["Generated SQL", "Agent Trace", "RAG Context", "State"]
    )

    with sql_tab:
        st.code(state.get("sql", ""), language="sql")

    with trace_tab:
        if trace_rows:
            st.dataframe(pd.DataFrame(trace_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No trace rows were recorded.")

    with context_tab:
        schema_col, example_col = st.columns(2)
        with schema_col:
            st.markdown("**Retrieved schema context**")
            chunks = state.get("retrieved_schema_chunks", [])
            if chunks:
                for chunk in chunks:
                    st.caption(f"Score: {chunk.get('score', 'n/a')}")
                    st.write(chunk.get("text", ""))
            else:
                st.info("No RAG schema chunks were retrieved.")
        with example_col:
            st.markdown("**Retrieved examples**")
            examples = state.get("retrieved_examples", [])
            if examples:
                for example in examples:
                    st.caption(example.get("question", "Example"))
                    st.code(example.get("sql", example.get("text", "")), language="sql")
            else:
                st.info("No examples were retrieved.")

    with state_tab:
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


_inject_css()

db_health = check_database_health()

status_html = "".join(
    [
        _status_pill("PostgreSQL connected", True)
        if db_health["is_connected"]
        else _status_pill("Demo data fallback", False),
        _status_pill("Groq configured", True)
        if settings.groq_api_key
        else _status_pill("Groq key missing", False),
        _status_pill("LangSmith on", True)
        if settings.langsmith_tracing and settings.langsmith_api_key
        else _status_pill("LangSmith off", None),
    ]
)

st.markdown(
    (
        '<div class="hero">'
        "<div>"
        '<div class="hero-kicker">Northwind analytics agent</div>'
        "<h1>InsightSQL</h1>"
        '<div class="hero-copy">'
        "Ask business questions in plain English and inspect the generated SQL, "
        "validation path, retrieved context, and result set in one workspace."
        "</div>"
        "</div>"
        f'<div class="status-strip">{status_html}</div>'
        "</div>"
    ),
    unsafe_allow_html=True,
)

if not settings.groq_api_key:
    st.error(
        "GROQ_API_KEY is not set — SQL generation will fail. "
        "Add GROQ_API_KEY to your .env file and restart."
    )

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

st.markdown('<div class="section-label">Ask a question</div>', unsafe_allow_html=True)
with st.form("query-form"):
    query_col, action_col = st.columns([5, 1])
    with query_col:
        query = st.text_input(
            "Business question",
            key="query",
            placeholder="Top customers by revenue",
            label_visibility="collapsed",
        )
    with action_col:
        submitted = st.form_submit_button("Run query", type="primary", use_container_width=True)

if submitted and query.strip():
    _run_query(query.strip())
    st.rerun()
elif submitted:
    st.warning("Enter a query to run the agent pipeline.")

if st.session_state.get("last_state"):
    _render_state(st.session_state["last_state"])
