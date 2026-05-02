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
            --ink: #302827;
            --muted: #756965;
            --line: #eadfcf;
            --panel: #fffdf7;
            --soft: #fbf4e9;
            --cream: #fff8ec;
            --cream-strong: #f4ead8;
            --nav: #474040;
            --nav-2: #5a514f;
            --accent: #b85c38;
            --accent-2: #7d4f3f;
            --warn: #9a5a13;
            --bad: #b91c1c;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(184, 92, 56, 0.06), transparent 30rem),
                radial-gradient(circle at bottom right, rgba(71, 64, 64, 0.05), transparent 28rem),
                linear-gradient(180deg, #fffbf3 0%, var(--cream) 100%);
            color: var(--ink);
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 4rem;
            max-width: 1280px;
        }

        [data-testid="stHeader"],
        header[data-testid="stHeader"],
        .stAppHeader {
            background: #474040 !important;
            color: #fff7ea !important;
            border-bottom: 1px solid rgba(255, 247, 234, 0.12);
        }

        [data-testid="stToolbar"],
        .stAppToolbar,
        [data-testid="stToolbarActions"] {
            background: #474040 !important;
            color: #fff7ea !important;
        }

        [data-testid="stHeader"] button,
        [data-testid="stHeader"] svg,
        [data-testid="stHeader"] span,
        .stAppHeader button,
        .stAppHeader svg,
        .stAppHeader span {
            color: #fff7ea !important;
        }

        [data-testid="stBaseButton-header"],
        [data-testid="stMainMenuButton"] {
            background: rgba(255, 247, 234, 0.08) !important;
            border-color: rgba(255, 247, 234, 0.14) !important;
        }

        [data-testid="stBaseButton-header"]:hover,
        [data-testid="stMainMenuButton"]:hover {
            background: rgba(255, 247, 234, 0.16) !important;
        }

        [data-testid="stSidebar"] {
            background: #474040;
            color: #fff7ea;
            border-right: 1px solid rgba(255, 247, 234, 0.12);
            box-shadow: 10px 0 28px rgba(48, 40, 39, 0.18);
        }

        [data-testid="stSidebar"] * {
            color: #fff7ea;
        }

        [data-testid="stSidebar"] .stCaption,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
            color: rgba(255, 247, 234, 0.78);
        }

        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            color: #f9dec3 !important;
            font-size: 0.78rem;
            font-weight: 900;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            margin-top: 1.25rem;
            padding-bottom: 0.45rem;
            border-bottom: 1px solid rgba(255, 247, 234, 0.14);
        }

        [data-testid="stSidebar"] .block-container,
        [data-testid="stSidebar"] > div:first-child {
            padding-top: 0.7rem;
        }

        .sidebar-section-title {
            color: #f9dec3;
            font-size: 0.72rem;
            font-weight: 900;
            letter-spacing: 0.11em;
            text-transform: uppercase;
            margin: 1.1rem 0 0.55rem;
        }

        .sidebar-card {
            background: rgba(255, 247, 234, 0.08);
            border: 1px solid rgba(255, 247, 234, 0.14);
            border-radius: 8px;
            padding: 0.8rem 0.85rem;
            margin-bottom: 0.75rem;
        }

        .sidebar-status-row {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            color: #fff7ea;
            font-size: 0.9rem;
            font-weight: 800;
            margin-bottom: 0.45rem;
        }

        .sidebar-status-dot {
            width: 0.55rem;
            height: 0.55rem;
            border-radius: 999px;
            background: #34d399;
            box-shadow: 0 0 0 3px rgba(52, 211, 153, 0.14);
            flex: 0 0 auto;
        }

        .sidebar-status-dot.warn {
            background: #f59e0b;
            box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.16);
        }

        .sidebar-muted {
            color: rgba(255, 247, 234, 0.66);
            font-size: 0.74rem;
            line-height: 1.4;
            overflow-wrap: anywhere;
        }

        .sidebar-stack-row {
            display: grid;
            grid-template-columns: 1.25rem minmax(0, 1fr);
            gap: 0.55rem;
            align-items: start;
            padding: 0.45rem 0;
            border-bottom: 1px solid rgba(255, 247, 234, 0.09);
        }

        .sidebar-stack-row:last-child {
            border-bottom: 0;
        }

        .sidebar-stack-icon {
            color: #f9dec3;
            font-size: 0.95rem;
            line-height: 1.25;
            text-align: center;
        }

        .sidebar-stack-label {
            color: rgba(255, 247, 234, 0.58);
            font-size: 0.68rem;
            font-weight: 850;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            margin-bottom: 0.05rem;
        }

        .sidebar-stack-value {
            color: #fff7ea;
            font-size: 0.82rem;
            font-weight: 750;
            line-height: 1.3;
            overflow-wrap: anywhere;
        }

        .sidebar-empty {
            color: rgba(255, 247, 234, 0.58);
            border: 1px dashed rgba(255, 247, 234, 0.18);
            border-radius: 8px;
            padding: 0.65rem 0.75rem;
            font-size: 0.78rem;
        }

        [data-testid="stSidebar"] .stButton > button {
            background: rgba(255, 247, 234, 0.08);
            color: #fff7ea;
            border: 1px solid rgba(255, 247, 234, 0.16);
            border-radius: 8px;
            min-height: 2.35rem;
            font-weight: 750;
            transition: background 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
        }

        [data-testid="stSidebar"] .stButton > button:hover {
            background: rgba(249, 222, 195, 0.18);
            border-color: rgba(249, 222, 195, 0.42);
            transform: translateX(2px);
        }

        [data-testid="stSidebar"] div[data-testid="stAlert"] {
            background: rgba(255, 247, 234, 0.10);
            border-color: rgba(255, 247, 234, 0.18);
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
            align-items: center;
            margin: 0 0 1.25rem;
            padding: 0.9rem 0 1rem;
            border-bottom: 1px solid var(--line);
            background: transparent;
            box-shadow: none;
        }

        .hero-kicker {
            color: var(--accent);
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }

        .hero h1 {
            color: var(--ink);
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
            background: rgba(255, 253, 247, 0.82);
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
            border-color: rgba(154, 90, 19, 0.24);
            background: rgba(154, 90, 19, 0.08);
        }

        .query-shell {
            border: 1px solid var(--line);
            background: rgba(255, 253, 247, 0.92);
            border-radius: 8px;
            padding: 1rem 1rem 0.85rem;
            box-shadow: 0 16px 40px rgba(71, 64, 64, 0.10);
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
            box-shadow: 0 10px 24px rgba(71, 64, 64, 0.08);
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
            background: rgba(255, 253, 247, 0.88);
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
            background: #fffdf7;
            color: var(--ink);
            min-height: 3rem;
            border-color: var(--line);
            font-size: 1rem;
            box-shadow: 0 12px 28px rgba(71, 64, 64, 0.08);
        }

        .stTextInput > div > div > input:focus {
            border-color: var(--accent) !important;
            box-shadow: 0 0 0 3px rgba(184, 92, 56, 0.16);
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
            background: var(--accent);
            border-color: var(--accent);
            color: #ffffff;
        }

        .stFormSubmitButton > button[kind="primary"]:hover,
        .stButton > button[kind="primary"]:hover {
            background: #a84e2d;
            border-color: #a84e2d;
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
            color: var(--accent);
        }

        .stTabs [aria-selected="true"] p {
            color: var(--accent);
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
        "<h1>InsightSQL</h1>"
        '<div class="hero-kicker">Northwind analytics agent</div>'
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
    status_label = "PostgreSQL connected" if db_health["is_connected"] else "Demo data fallback"
    status_dot = "sidebar-status-dot" if db_health["is_connected"] else "sidebar-status-dot warn"
    status_hint = f'<div class="sidebar-muted">{html.escape(db_health["hint"])}</div>' if db_health.get("hint") else ""
    st.markdown(
        (
            '<div class="sidebar-section-title">System Status</div>'
            '<div class="sidebar-card">'
            '<div class="sidebar-status-row">'
            f'<span class="{status_dot}"></span>'
            f"<span>{html.escape(status_label)}</span>"
            "</div>"
            f'<div class="sidebar-muted">{html.escape(db_health["message"])}</div>'
            f'<div class="sidebar-muted">{html.escape(db_health["database_url"])}</div>'
            f"{status_hint}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    langsmith_status = (
        "Enabled"
        if settings.langsmith_tracing and settings.langsmith_api_key
        else "Configured off"
    )
    st.markdown(
        (
            '<div class="sidebar-section-title">Agent Stack</div>'
            '<div class="sidebar-card">'
            '<div class="sidebar-stack-row">'
            '<div class="sidebar-stack-icon">L</div>'
            '<div><div class="sidebar-stack-label">Workflow</div>'
            '<div class="sidebar-stack-value">LangGraph</div></div>'
            "</div>"
            '<div class="sidebar-stack-row">'
            '<div class="sidebar-stack-icon">G</div>'
            '<div><div class="sidebar-stack-label">LLM</div>'
            f'<div class="sidebar-stack-value">groq / {html.escape(settings.groq_model)}</div></div>'
            "</div>"
            '<div class="sidebar-stack-row">'
            '<div class="sidebar-stack-icon">S</div>'
            '<div><div class="sidebar-stack-label">LangSmith</div>'
            f'<div class="sidebar-stack-value">{html.escape(langsmith_status)}</div></div>'
            "</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    st.markdown('<div class="sidebar-section-title">Demo Queries</div>', unsafe_allow_html=True)
    for example_query in EXAMPLE_QUERIES:
        if st.button(example_query, use_container_width=True):
            st.session_state["query"] = example_query
            _run_query(example_query)
            st.rerun()

    st.markdown('<div class="sidebar-section-title">Query History</div>', unsafe_allow_html=True)
    history_items = list(_history())
    if history_items:
        for idx, history_query in enumerate(history_items):
            if st.button(history_query, key=f"history-{idx}", use_container_width=True):
                st.session_state["query"] = history_query
                _run_query(history_query)
                st.rerun()
    else:
        st.markdown('<div class="sidebar-empty">No recent queries yet.</div>', unsafe_allow_html=True)

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
