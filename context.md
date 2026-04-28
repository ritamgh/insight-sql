# InsightSQL — Complete Implementation Specification for Claude Code

You are building **InsightSQL** — a complete, working, production-quality agentic NL2SQL
system. Read this entire document before writing a single line of code. Every decision,
file, function signature, routing rule, environment variable, and test case is specified
here. Implement exactly what is described.

---

## 1. WHAT YOU ARE BUILDING

A Streamlit web app where a business user types a plain-English question like
"Top customers by revenue" and gets back:

1. A table of real data from a PostgreSQL (Northwind) database
2. A plain-English explanation of the results
3. The generated SQL query (in an expander)
4. A trace table showing every agent that ran and how long each took

The system works in three modes — with a real Postgres DB, with built-in demo pandas
data (no DB needed), or in a fully offline mode with no LLM. It must work out of the
box with zero configuration.

---

## 2. TECHNOLOGY STACK

```
Python 3.11+
LangGraph      — pipeline orchestration (StateGraph)
LangSmith      — optional observability (@traceable decorators)
LangChain      — LLM integration (langchain-core, langchain-ollama)
OpenAI         — optional LLM provider
Ollama         — optional local LLM (model: qwen3.5:9b)
PostgreSQL     — real database (Northwind schema)
psycopg2       — DB driver
pandas         — demo data computation
Streamlit      — UI
pytest         — tests
Docker Compose — optional Postgres container
```

**requirements.txt** (exact versions):

```
langchain>=1.2.0
langchain-ollama>=1.1.0
langgraph>=1.1.0
langsmith>=0.7.0
openai>=1.40.0
pandas>=2.2.0
psycopg2-binary>=2.9.9
pytest>=8.2.0
streamlit>=1.36.0
```

---

## 3. COMPLETE FOLDER STRUCTURE

Create every file listed here. Do not add extra files or folders.

```
insightsql/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
│
├── backend/
│   ├── __init__.py
│   └── app/
│       ├── __init__.py
│       ├── controller.py                  ← LangGraph graph + all node wrappers
│       │
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── disambiguation_agent.py
│       │   ├── domain_guard_agent.py
│       │   ├── retrieval_agent.py
│       │   ├── sql_generation_agent.py
│       │   ├── validation_agent.py
│       │   ├── execution_agent.py
│       │   └── explanation_agent.py
│       │
│       ├── core/
│       │   ├── __init__.py
│       │   └── config.py
│       │
│       ├── db/
│       │   ├── __init__.py
│       │   ├── connection.py
│       │   ├── demo_data.py
│       │   ├── demo_executor.py
│       │   ├── health.py
│       │   └── northwind_schema.py
│       │
│       ├── prompts/
│       │   ├── __init__.py
│       │   └── sql_generation.py
│       │
│       ├── schemas/
│       │   ├── __init__.py
│       │   └── state.py
│       │
│       └── services/
│           ├── __init__.py
│           └── llm.py
│
├── frontend/
│   └── streamlit_app.py
│
├── data/
│   └── postgres/
│       └── init/
│           └── 01_northwind_demo.sql      ← Northwind SQL dump
│
└── tests/
    ├── test_agents.py
    └── test_controller.py
```

---

## 4. ENVIRONMENT CONFIGURATION

### `.env.example`

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/northwind
DATABASE_CONNECT_TIMEOUT_SECONDS=2
STATEMENT_TIMEOUT_MS=10000

# offline = no LLM (uses keyword-template SQL)
# openai  = OpenAI API
# ollama  = local Ollama
LLM_PROVIDER=offline

OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3.5:9b

LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=InsightSQL-AgentOps

# auto     = try Postgres, fall back to demo if unavailable
# demo     = always use built-in demo data
# postgres = real DB only, fail hard if unavailable
EXECUTION_BACKEND=auto
```

### `docker-compose.yml`

```yaml
services:
  postgres:
    image: postgres:16
    container_name: insightsql-postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: northwind
    ports:
      - "5432:5432"
    volumes:
      - ./data/postgres/init:/docker-entrypoint-initdb.d:ro
      - insightsql-postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d northwind"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  insightsql-postgres-data:
```

### `pytest.ini`

```ini
[pytest]
testpaths = tests
```

---

## 5. CORE: `backend/app/schemas/state.py`

This is the shared state dict passed between every agent. Use TypedDict with
`total=False` so all keys are optional (agents may not have written them yet).

```python
"""Shared pipeline state passed between agents."""
from __future__ import annotations
from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    query: str                          # raw user input — never modified
    refined_query: str                  # query + any disambiguation assumptions appended
    is_ambiguous: bool                  # True if disambiguation appended assumptions
    clarification: str                  # the assumption text shown to user
    out_of_scope: bool                  # True if domain guard rejected the query
    schema: str                         # formatted table schema text for SQL prompt
    sql: str                            # generated SQL (modified by execution to add LIMIT)
    validation: dict[str, Any]          # {is_valid, error, retryable, execution_backend, detail}
    retry_count: int                    # number of validation retries so far
    max_attempts: int                   # retry cap (default 2)
    result: list[dict[str, Any]]        # rows returned from DB or demo executor
    explanation: str                    # plain-English summary shown at top of UI
    error: str                          # error message if something failed
    data_source: str                    # "postgres" or "demo"
    agent_trace: list[dict[str, Any]]   # [{agent, status, detail, duration_ms}, ...]
    db_health: dict[str, Any]           # from health check
```

---

## 6. CORE: `backend/app/core/config.py`

Load `.env` manually (no python-dotenv dependency). Expose a frozen dataclass.
Use `get_settings()` as the accessor everywhere — never read `os.environ` directly
in agent files.

```python
"""Runtime configuration for InsightSQL."""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_env_file() -> None:
    env_file = Path(__file__).resolve().parents[3] / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _env_int(name: str, default: str) -> int:
    return int(os.getenv(name, default))


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: _env(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/northwind",
        )
    )
    llm_provider: str = field(
        default_factory=lambda: _env("LLM_PROVIDER", "offline").lower()
    )
    openai_api_key: str | None = field(
        default_factory=lambda: _env("OPENAI_API_KEY") or None
    )
    openai_model: str = field(
        default_factory=lambda: _env("OPENAI_MODEL", "gpt-4o-mini")
    )
    ollama_base_url: str = field(
        default_factory=lambda: _env("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    ollama_model: str = field(
        default_factory=lambda: _env("OLLAMA_MODEL", "llama3.1")
    )
    langsmith_tracing: bool = field(
        default_factory=lambda: _env("LANGSMITH_TRACING", "false").lower() == "true"
    )
    langsmith_api_key: str | None = field(
        default_factory=lambda: _env("LANGSMITH_API_KEY") or None
    )
    langsmith_project: str = field(
        default_factory=lambda: _env("LANGSMITH_PROJECT", "InsightSQL-AgentOps")
    )
    statement_timeout_ms: int = field(
        default_factory=lambda: _env_int("STATEMENT_TIMEOUT_MS", "10000")
    )
    database_connect_timeout_seconds: int = field(
        default_factory=lambda: _env_int("DATABASE_CONNECT_TIMEOUT_SECONDS", "2")
    )
    execution_backend: str = field(
        default_factory=lambda: _env("EXECUTION_BACKEND", "auto").lower()
    )


def get_settings() -> Settings:
    return Settings()
```

---

## 7. DATABASE LAYER

### `backend/app/db/connection.py`

```python
"""PostgreSQL connection and query helpers."""
from __future__ import annotations
from contextlib import contextmanager
from typing import Any, Iterator

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ModuleNotFoundError:
    psycopg2 = None
    RealDictCursor = None

from backend.app.core.config import get_settings


@contextmanager
def get_connection() -> Iterator[Any]:
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is not installed.")
    settings = get_settings()
    connection = psycopg2.connect(
        settings.database_url,
        connect_timeout=settings.database_connect_timeout_seconds,
    )
    try:
        yield connection
    finally:
        connection.close()


def explain_query(sql: str) -> list[dict[str, Any]]:
    """Run EXPLAIN (never executes) — used by validation for syntax check."""
    settings = get_settings()
    with get_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SET statement_timeout = %s", (settings.statement_timeout_ms,))
            cursor.execute(f"EXPLAIN {sql.rstrip(';')}")
            return [dict(row) for row in cursor.fetchall()]


def fetch_rows(sql: str) -> list[dict[str, Any]]:
    """Execute SQL and return rows as list of dicts."""
    settings = get_settings()
    with get_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SET statement_timeout = %s", (settings.statement_timeout_ms,))
            cursor.execute(sql)
            return [dict(row) for row in cursor.fetchall()]
```

### `backend/app/db/health.py`

```python
"""Database health check and user-facing error messages."""
from __future__ import annotations
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from backend.app.core.config import get_settings
from backend.app.db.connection import get_connection


def check_database_health() -> dict[str, Any]:
    settings = get_settings()
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                cursor.fetchone()
    except Exception as exc:
        return {
            "is_connected": False,
            "database_url": mask_database_url(settings.database_url),
            "message": friendly_database_error(exc),
            "hint": (
                "PostgreSQL is optional in auto mode. The app falls back to "
                "built-in demo data, or run: docker compose up -d"
            ),
        }
    return {
        "is_connected": True,
        "database_url": mask_database_url(settings.database_url),
        "message": "Connected to PostgreSQL.",
        "hint": "",
    }


def mask_database_url(database_url: str) -> str:
    parts = urlsplit(database_url)
    if not parts.password:
        return database_url
    username = parts.username or ""
    hostname = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{username}:***@{hostname}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def friendly_database_error(exc: Exception) -> str:
    message = str(exc).strip()
    lower = message.lower()
    if "connection refused" in lower:
        return "PostgreSQL refused the connection on localhost:5432. The server is not running."
    if "timeout expired" in lower or "timed out" in lower:
        return "The database connection timed out."
    if "password authentication failed" in lower:
        return "PostgreSQL rejected the username or password in DATABASE_URL."
    if "database" in lower and "does not exist" in lower:
        return "The configured PostgreSQL database does not exist."
    return message


def is_database_connection_error(exc: Exception) -> bool:
    lower = str(exc).lower()
    return any(
        fragment in lower
        for fragment in (
            "connection refused",
            "could not connect",
            "timeout expired",
            "timed out",
            "password authentication failed",
            "does not exist",
        )
    )
```

### `backend/app/db/northwind_schema.py`

This file defines the hardcoded schema strings for all 8 Northwind tables and the
keyword-to-table mapping used by the retrieval agent.

```python
"""Hardcoded Northwind schema snippets used by the simulated RAG retrieval agent."""
from __future__ import annotations
from collections.abc import Iterable

SCHEMA_SNIPPETS: dict[str, str] = {
    "customers": """
Table: customers
Columns:
- customers.customer_id: text primary key
- customers.company_name: text customer company name
- customers.contact_name: text contact person
- customers.city: text
- customers.country: text
Relationships:
- customers.customer_id = orders.customer_id
""",
    "orders": """
Table: orders
Columns:
- orders.order_id: integer primary key
- orders.customer_id: text foreign key to customers.customer_id
- orders.employee_id: integer foreign key to employees.employee_id
- orders.order_date: date
- orders.shipped_date: date
- orders.ship_via: integer foreign key to shippers.shipper_id
- orders.freight: numeric
Relationships:
- orders.order_id = order_details.order_id
- orders.customer_id = customers.customer_id
- orders.employee_id = employees.employee_id
- orders.ship_via = shippers.shipper_id
""",
    "order_details": """
Table: order_details
Columns:
- order_details.order_id: integer foreign key to orders.order_id
- order_details.product_id: integer foreign key to products.product_id
- order_details.unit_price: numeric
- order_details.quantity: integer
- order_details.discount: real fraction from 0 to 1
Business metrics:
- revenue = order_details.unit_price * order_details.quantity * (1 - order_details.discount)
Relationships:
- order_details.order_id = orders.order_id
- order_details.product_id = products.product_id
""",
    "products": """
Table: products
Columns:
- products.product_id: integer primary key
- products.product_name: text
- products.supplier_id: integer foreign key to suppliers.supplier_id
- products.category_id: integer foreign key to categories.category_id
- products.unit_price: numeric
- products.units_in_stock: integer
- products.discontinued: boolean
Relationships:
- products.category_id = categories.category_id
- products.supplier_id = suppliers.supplier_id
""",
    "categories": """
Table: categories
Columns:
- categories.category_id: integer primary key
- categories.category_name: text
- categories.description: text
Relationships:
- categories.category_id = products.category_id
""",
    "employees": """
Table: employees
Columns:
- employees.employee_id: integer primary key
- employees.first_name: text
- employees.last_name: text
- employees.title: text
- employees.country: text
Relationships:
- employees.employee_id = orders.employee_id
""",
    "suppliers": """
Table: suppliers
Columns:
- suppliers.supplier_id: integer primary key
- suppliers.company_name: text supplier company name
- suppliers.city: text
- suppliers.country: text
Relationships:
- suppliers.supplier_id = products.supplier_id
""",
    "shippers": """
Table: shippers
Columns:
- shippers.shipper_id: integer primary key
- shippers.company_name: text shipper company name
Relationships:
- shippers.shipper_id = orders.ship_via
""",
}

KEYWORDS_TO_TABLES: dict[str, tuple[str, ...]] = {
    "customer":    ("customers", "orders", "order_details"),
    "client":      ("customers", "orders", "order_details"),
    "country":     ("customers", "orders"),
    "order":       ("orders", "order_details", "customers"),
    "sale":        ("orders", "order_details", "products"),
    "revenue":     ("orders", "order_details", "products", "customers"),
    "freight":     ("orders", "customers", "shippers"),
    "ship":        ("orders", "shippers", "customers"),
    "recent":      ("orders", "customers", "order_details"),
    "product":     ("products", "order_details", "orders"),
    "item":        ("products", "order_details", "orders"),
    "stock":       ("products", "categories", "suppliers"),
    "inventory":   ("products", "categories", "suppliers"),
    "category":    ("categories", "products", "order_details"),
    "employee":    ("employees", "orders", "order_details"),
    "salesperson": ("employees", "orders", "order_details"),
    "supplier":    ("suppliers", "products", "categories"),
}

DEFAULT_TABLES: tuple[str, ...] = ("customers", "orders", "order_details", "products")


def select_schema_context(query: str) -> str:
    """Return formatted schema strings for tables relevant to query."""
    selected = _select_tables(query.lower().split())
    return "\n\n".join(SCHEMA_SNIPPETS[t].strip() for t in selected)


def _select_tables(tokens: Iterable[str]) -> list[str]:
    selected: list[str] = []
    token_text = " ".join(tokens)
    for keyword, table_names in KEYWORDS_TO_TABLES.items():
        if keyword in token_text:
            for table_name in table_names:
                if table_name not in selected:
                    selected.append(table_name)
    if not selected:
        selected.extend(DEFAULT_TABLES)
    return selected
```

### `backend/app/db/demo_data.py`

Compact in-memory Northwind-like dataset using pandas DataFrames.
Implement load_demo_tables() returning a dict with keys:
"customers", "employees", "shippers", "categories", "suppliers",
"products", "orders", "order_details".

Customers (6 rows): ALFKI/Alfreds Futterkiste/Germany,
ANATR/Ana Trujillo Emparedados/Mexico, AROUT/Around the Horn/UK,
BERGS/Berglunds snabbkop/Sweden, BONAP/Bon app/France,
ERNSH/Ernst Handel/Austria.

Employees (4 rows): 1/Nancy/Davolio, 2/Andrew/Fuller,
3/Janet/Leverling, 4/Margaret/Peacock.

Shippers (3 rows): 1/Speedy Express, 2/United Package, 3/Federal Shipping.

Categories (3 rows): 1/Beverages, 2/Condiments, 3/Confections.

Suppliers (3 rows): 1/Exotic Liquids, 2/New Orleans Cajun Delights,
3/Grandma Kellys Homestead.

Products (6 rows):
1, Chai, supplier_id=1, category_id=1, unit_price=18.0, units_in_stock=39
2, Chang, supplier_id=1, category_id=1, unit_price=19.0, units_in_stock=17
3, Aniseed Syrup, supplier_id=1, category_id=2, unit_price=10.0, units_in_stock=13
4, Chef Anton Cajun Seasoning, supplier_id=2, category_id=2, unit_price=22.0, units_in_stock=53
5, Grandmas Boysenberry Spread, supplier_id=3, category_id=2, unit_price=25.0, units_in_stock=120
6, Chocolate Biscuits Mix, supplier_id=3, category_id=3, unit_price=9.2, units_in_stock=30

Orders (8 rows) with order_date and shipped_date as datetime64:
10248, ALFKI, emp=1, 1998-04-01, 1998-04-05, ship_via=3, freight=32.38
10249, ANATR, emp=2, 1998-04-03, 1998-04-10, ship_via=1, freight=11.61
10250, AROUT, emp=3, 1998-04-08, 1998-04-12, ship_via=2, freight=65.83
10251, BERGS, emp=3, 1998-04-15, 1998-04-20, ship_via=1, freight=41.34
10252, BONAP, emp=4, 1998-04-20, 1998-04-25, ship_via=2, freight=51.30
10253, ERNSH, emp=1, 1998-05-01, 1998-05-08, ship_via=3, freight=58.17
10254, ERNSH, emp=4, 1998-05-04, 1998-05-12, ship_via=2, freight=22.98
10255, ALFKI, emp=2, 1998-05-06, 1998-05-10, ship_via=1, freight=148.33

Order_details (10 rows):
order_id=10248, product_id=1, unit_price=14.0, quantity=12, discount=0.0
order_id=10248, product_id=2, unit_price=9.8, quantity=10, discount=0.0
order_id=10249, product_id=3, unit_price=9.8, quantity=5, discount=0.0
order_id=10250, product_id=4, unit_price=21.35, quantity=10, discount=0.0
order_id=10250, product_id=5, unit_price=7.7, quantity=35, discount=0.25
order_id=10251, product_id=6, unit_price=16.8, quantity=6, discount=0.05
order_id=10252, product_id=1, unit_price=14.0, quantity=40, discount=0.05
order_id=10253, product_id=2, unit_price=9.8, quantity=25, discount=0.0
order_id=10254, product_id=3, unit_price=9.8, quantity=20, discount=0.0
order_id=10255, product_id=5, unit_price=7.7, quantity=15, discount=0.1

### `backend/app/db/demo_executor.py`

Pattern-match SQL string → pandas computation. Never actually runs SQL.

```python
def fetch_demo_rows(sql: str) -> list[dict[str, Any]]:
    sql_lower = sql.lower()
    tables = load_demo_tables()

    if "from categories" in sql_lower and "total_revenue" in sql_lower:
        return _category_revenue(tables)
    if "from employees" in sql_lower and "total_revenue" in sql_lower:
        return _employee_revenue(tables)
    if "from products" in sql_lower and "units_in_stock" in sql_lower:
        return _product_inventory(tables)
    if "from products" in sql_lower and "total_revenue" in sql_lower:
        return _product_revenue(tables)
    if "from shippers" in sql_lower:
        return _shipper_freight(tables)
    if "from customers" in sql_lower and "count(customers.customer_id)" in sql_lower:
        return _customers_by_country(tables)
    if "where orders.order_date >=" in sql_lower:
        return _recent_orders(tables)
    if "from customers" in sql_lower and "total_revenue" in sql_lower:
        return _customer_revenue(tables)
    return _recent_orders(tables)
```

Implement each helper using pandas merges and groupby:

- \_customer_revenue: join orders+order_details+customers, sum revenue, top 10
- \_product_revenue: join order_details+products, sum revenue, top 10
- \_category_revenue: join order_details+products+categories, sum revenue, top 10
- \_employee_revenue: join orders+order_details+employees, sum revenue, top 10
- \_product_inventory: join products+categories+suppliers, sort by units_in_stock asc, top 20
- \_shipper_freight: join orders+shippers, groupby shipper, count orders + avg freight, top 10
- \_customers_by_country: groupby country, count customers, sort desc, top 20
- \_recent_orders: filter to last 30 days from max(order_date), join customers, sort desc

Revenue formula everywhere: unit_price _ quantity _ (1 - discount)
Round all revenue/freight to 2 decimal places.
Format order_date and shipped_date as "%Y-%m-%d" strings.

---

## 8. PROMPTS: `backend/app/prompts/sql_generation.py`

```python
"""Prompts used by the SQL generation agent."""
from __future__ import annotations

SQL_GENERATION_SYSTEM_PROMPT = """You are a careful PostgreSQL SQL generator for a Northwind analytics database.
Follow these rules:
- Use only the provided schema context.
- Use explicit JOIN syntax.
- Qualify columns with table names.
- Return exactly one SELECT statement.
- Do not use DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, CREATE, GRANT, REVOKE, or COPY.
- Prefer clear aggregate aliases such as total_revenue or order_count.
- Add a LIMIT when the user asks for top rows or a sample.
"""


def build_sql_generation_prompt(
    refined_query: str,
    schema_context: str,
    last_error: str | None = None,
) -> str:
    retry_guidance = ""
    if last_error:
        retry_guidance = (
            f"\nThe previous SQL failed validation with this error:\n{last_error}\nFix it."
        )
    return f"""Schema context:
{schema_context}

Business question:
{refined_query}
{retry_guidance}

Return only SQL, with no markdown fence and no explanation."""
```

---

## 9. SERVICES: `backend/app/services/llm.py`

Three-tier LLM with full offline fallback.

````python
"""Optional LLM integration with deterministic fallback SQL generation."""
from __future__ import annotations
import re

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from backend.app.core.config import get_settings
from backend.app.prompts.sql_generation import (
    SQL_GENERATION_SYSTEM_PROMPT,
    build_sql_generation_prompt,
)


def generate_sql_with_llm_or_fallback(
    refined_query: str,
    schema_context: str,
    last_error: str | None = None,
) -> str:
    prompt = build_sql_generation_prompt(refined_query, schema_context, last_error)
    llm_sql = _call_configured_llm(prompt)
    if llm_sql:
        return _extract_sql(llm_sql)
    return _fallback_sql(refined_query, last_error)


def _call_configured_llm(prompt: str) -> str | None:
    settings = get_settings()
    if settings.llm_provider == "openai":
        return _call_openai(prompt)
    if settings.llm_provider == "ollama":
        return _call_ollama(prompt)
    return None


def _call_openai(prompt: str) -> str | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.openai_model,
            temperature=0,
            messages=[
                {"role": "system", "content": SQL_GENERATION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content
    except Exception:
        return None


def _call_ollama(prompt: str) -> str | None:
    settings = get_settings()
    try:
        model = ChatOllama(
            model=settings.ollama_model,
            temperature=0,
            base_url=settings.ollama_base_url,
        )
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", SQL_GENERATION_SYSTEM_PROMPT),
            ("human", "{task_prompt}"),
        ])
        chain = prompt_template | model
        response = chain.invoke({"task_prompt": prompt})
        content = response.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("text")
            )
        return None
    except Exception:
        return None


def _extract_sql(text: str) -> str:
    match = re.search(r"```(?:sql)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def _fallback_sql(refined_query: str, last_error: str | None = None) -> str:
    """Keyword-matched hardcoded SQL templates. No LLM required."""
    query = refined_query.lower()

    if "category" in query and ("sale" in query or "revenue" in query or "best" in query):
        return """SELECT
    categories.category_name,
    SUM(order_details.unit_price * order_details.quantity * (1 - order_details.discount)) AS total_revenue
FROM categories
JOIN products ON categories.category_id = products.category_id
JOIN order_details ON products.product_id = order_details.product_id
JOIN orders ON order_details.order_id = orders.order_id
GROUP BY categories.category_name
ORDER BY total_revenue DESC
LIMIT 10;""".strip()

    if "employee" in query or "salesperson" in query or "sales rep" in query:
        return """SELECT
    employees.employee_id,
    employees.first_name,
    employees.last_name,
    SUM(order_details.unit_price * order_details.quantity * (1 - order_details.discount)) AS total_revenue
FROM employees
JOIN orders ON employees.employee_id = orders.employee_id
JOIN order_details ON orders.order_id = order_details.order_id
GROUP BY employees.employee_id, employees.first_name, employees.last_name
ORDER BY total_revenue DESC
LIMIT 10;""".strip()

    if "product" in query or "item" in query:
        if "stock" in query or "inventory" in query:
            return """SELECT
    products.product_id,
    products.product_name,
    categories.category_name,
    suppliers.company_name AS supplier_name,
    products.units_in_stock
FROM products
JOIN categories ON products.category_id = categories.category_id
JOIN suppliers ON products.supplier_id = suppliers.supplier_id
ORDER BY products.units_in_stock ASC
LIMIT 20;""".strip()
        return """SELECT
    products.product_id,
    products.product_name,
    SUM(order_details.unit_price * order_details.quantity * (1 - order_details.discount)) AS total_revenue
FROM products
JOIN order_details ON products.product_id = order_details.product_id
JOIN orders ON order_details.order_id = orders.order_id
GROUP BY products.product_id, products.product_name
ORDER BY total_revenue DESC
LIMIT 10;""".strip()

    if "country" in query and ("customer" in query or "client" in query):
        return """SELECT
    customers.country,
    COUNT(customers.customer_id) AS customer_count
FROM customers
GROUP BY customers.country
ORDER BY customer_count DESC, customers.country ASC
LIMIT 20;""".strip()

    if "recent" in query or "last 30 days" in query:
        return """SELECT
    orders.order_id,
    customers.company_name,
    orders.order_date,
    orders.shipped_date,
    orders.freight
FROM orders
JOIN customers ON orders.customer_id = customers.customer_id
WHERE orders.order_date >= (SELECT MAX(orders.order_date) FROM orders) - INTERVAL '30 days'
ORDER BY orders.order_date DESC
LIMIT 100;""".strip()

    if "ship" in query or "freight" in query:
        return """SELECT
    shippers.company_name AS shipper_name,
    COUNT(orders.order_id) AS order_count,
    AVG(orders.freight) AS average_freight
FROM shippers
JOIN orders ON shippers.shipper_id = orders.ship_via
GROUP BY shippers.company_name
ORDER BY order_count DESC
LIMIT 10;""".strip()

    if "customer" in query or "client" in query or "top" in query or "best" in query:
        return """SELECT
    customers.customer_id,
    customers.company_name,
    SUM(order_details.unit_price * order_details.quantity * (1 - order_details.discount)) AS total_revenue
FROM customers
JOIN orders ON customers.customer_id = orders.customer_id
JOIN order_details ON orders.order_id = order_details.order_id
GROUP BY customers.customer_id, customers.company_name
ORDER BY total_revenue DESC
LIMIT 10;""".strip()

    return """SELECT
    orders.order_id,
    customers.company_name,
    orders.order_date,
    orders.freight
FROM orders
JOIN customers ON orders.customer_id = customers.customer_id
ORDER BY orders.order_date DESC
LIMIT 100;""".strip()
````

---

## 10. THE SEVEN AGENTS

### `backend/app/agents/disambiguation_agent.py`

```python
"""Disambiguation agent — resolves vague language with hardcoded defaults."""
from __future__ import annotations
import re
from backend.app.schemas.state import AgentState

AMBIGUOUS_DEFAULTS: dict[str, str] = {
    "top":    "Assume top means highest total revenue and limit 10.",
    "recent": "Assume recent means the last 30 days in the dataset by orders.order_date.",
    "best":   "Assume best means highest total revenue.",
}


def disambiguation_agent(state: AgentState) -> AgentState:
    query = state.get("query", "").strip()
    lower_query = query.lower()
    assumptions = [
        assumption
        for term, assumption in AMBIGUOUS_DEFAULTS.items()
        if re.search(rf"\b{re.escape(term)}\b", lower_query)
    ]
    refined_query = query
    if assumptions:
        refined_query = f"{query} ({' '.join(assumptions)})"
    state["is_ambiguous"] = bool(assumptions)
    state["refined_query"] = refined_query
    state["clarification"] = " ".join(assumptions)
    return state
```

### `backend/app/agents/domain_guard_agent.py`

```python
"""Domain guard — rejects questions unrelated to Northwind."""
from __future__ import annotations
import re
from backend.app.schemas.state import AgentState

SCHEMA_ENTITY_TERMS = {
    "customer", "customers", "order", "orders", "product", "products",
    "item", "items", "supplier", "suppliers", "category", "categories",
    "employee", "employees", "salesperson", "salespeople", "shipper",
    "shippers", "shipping", "freight", "inventory", "stock", "revenue",
    "sale", "sales", "discount", "country", "city", "region", "state",
    "territory",
}

UNSUPPORTED_DOMAIN_TERMS = {
    "car", "cars", "vehicle", "vehicles", "automobile", "automobiles",
    "truck", "trucks", "bike", "bikes", "motorcycle", "motorcycles",
    "furniture", "sofa", "sofas", "chair", "chairs", "couch", "couches",
    "bed", "beds", "hospital", "hospitals", "patient", "patients",
    "doctor", "doctors", "weather", "temperature", "stockmarket",
    "crypto", "bitcoin",
}


def domain_guard_agent(state: AgentState) -> AgentState:
    query = (state.get("refined_query") or state.get("query") or "").lower()
    tokens = set(re.findall(r"[a-zA-Z_]+", query))
    matched_supported = sorted(tokens & SCHEMA_ENTITY_TERMS)
    matched_unsupported = sorted(tokens & UNSUPPORTED_DOMAIN_TERMS)
    out_of_scope = bool(matched_unsupported and not matched_supported)
    state["out_of_scope"] = out_of_scope
    if out_of_scope:
        unsupported_text = ", ".join(matched_unsupported)
        state["error"] = (
            "This question appears to be outside the Northwind domain. "
            f"I found unsupported topic terms: {unsupported_text}. "
            "Northwind is a sales and operations dataset about customers, orders, "
            "products, suppliers, employees, and shipping."
        )
    return state
```

### `backend/app/agents/retrieval_agent.py`

```python
"""Retrieval agent — attaches relevant schema context to state."""
from __future__ import annotations
from backend.app.db.northwind_schema import select_schema_context
from backend.app.schemas.state import AgentState


def retrieval_agent(state: AgentState) -> AgentState:
    query = state.get("refined_query") or state.get("query", "")
    state["schema"] = select_schema_context(query)
    return state
```

### `backend/app/agents/sql_generation_agent.py`

```python
"""SQL generation agent."""
from __future__ import annotations
from backend.app.schemas.state import AgentState
from backend.app.services.llm import generate_sql_with_llm_or_fallback


def sql_generation_agent(state: AgentState) -> AgentState:
    last_error = state.get("error") if state.get("retry_count", 0) > 0 else None
    state["sql"] = generate_sql_with_llm_or_fallback(
        refined_query=state.get("refined_query") or state.get("query", ""),
        schema_context=state.get("schema", ""),
        last_error=last_error,
    )
    return state
```

### `backend/app/agents/validation_agent.py`

```python
"""Validation agent — safety check + PostgreSQL EXPLAIN."""
from __future__ import annotations
import re
from backend.app.core.config import get_settings
from backend.app.db.connection import explain_query
from backend.app.db.health import friendly_database_error, is_database_connection_error
from backend.app.schemas.state import AgentState

FORBIDDEN_SQL = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE)\b",
    flags=re.IGNORECASE,
)


def validation_agent(state: AgentState) -> dict:
    sql = state.get("sql", "").strip()
    settings = get_settings()

    safety_error = _safety_error(sql)
    if safety_error:
        return {"is_valid": False, "error": safety_error, "retryable": False}

    if settings.execution_backend == "demo":
        return {
            "is_valid": True,
            "error": "",
            "retryable": True,
            "execution_backend": "demo",
            "detail": "Safety checks passed. Using built-in demo data.",
        }

    try:
        explain_query(sql)
    except Exception as exc:
        if is_database_connection_error(exc):
            if settings.execution_backend == "auto":
                return {
                    "is_valid": True,
                    "error": "",
                    "retryable": True,
                    "execution_backend": "demo",
                    "detail": "PostgreSQL unavailable — using demo data.",
                }
            return {
                "is_valid": False,
                "error": friendly_database_error(exc),
                "retryable": False,
                "execution_backend": "postgres",
            }
        return {
            "is_valid": False,
            "error": f"EXPLAIN failed: {exc}",
            "execution_backend": "postgres",
        }

    return {
        "is_valid": True,
        "error": "",
        "retryable": True,
        "execution_backend": "postgres",
        "detail": "SQL passed safety checks and PostgreSQL EXPLAIN.",
    }


def _safety_error(sql: str) -> str | None:
    if not sql:
        return "SQL is empty."
    if FORBIDDEN_SQL.search(sql):
        return "SQL contains a forbidden write or DDL keyword."
    normalized = sql.rstrip().rstrip(";")
    if ";" in normalized:
        return "SQL must contain exactly one statement."
    if not re.match(r"^\s*(SELECT|WITH)\b", normalized, flags=re.IGNORECASE):
        return "Only SELECT queries are allowed."
    return None
```

### `backend/app/agents/execution_agent.py`

```python
"""Execution agent — runs validated SQL against Postgres or demo backend."""
from __future__ import annotations
from backend.app.db.connection import fetch_rows
from backend.app.db.demo_executor import fetch_demo_rows
from backend.app.schemas.state import AgentState


def execution_agent(state: AgentState) -> AgentState:
    sql = _with_limit_safeguard(state.get("sql", ""))
    state["sql"] = sql
    execution_backend = (
        state.get("validation", {}).get("execution_backend")
        if isinstance(state.get("validation"), dict)
        else None
    )
    try:
        if execution_backend == "demo":
            state["result"] = fetch_demo_rows(sql)
            state["data_source"] = "demo"
        else:
            state["result"] = fetch_rows(sql)
            state["data_source"] = "postgres"
        state["error"] = ""
    except Exception as exc:
        state["result"] = []
        state["error"] = f"Execution failed: {exc}"
    return state


def _with_limit_safeguard(sql: str) -> str:
    """Append LIMIT 100 if the SQL doesn't already bound the result set."""
    if "limit" not in sql.lower():
        return sql.rstrip().rstrip(";") + " LIMIT 100;"
    return sql
```

### `backend/app/agents/explanation_agent.py`

```python
"""Explanation agent — produces plain-English summary from result rows. No LLM."""
from __future__ import annotations
from typing import Any
from backend.app.schemas.state import AgentState


def explanation_agent(state: AgentState) -> AgentState:
    if state.get("out_of_scope"):
        state["explanation"] = (
            "This question is outside the Northwind dataset domain. "
            "Northwind can answer questions about customers, orders, products, "
            "suppliers, employees, shipping, revenue, and inventory."
        )
        return state

    if state.get("error"):
        state["explanation"] = (
            "I could not complete the analysis because the SQL pipeline reported an error. "
            f"Details: {state['error']}"
        )
        return state

    rows = state.get("result", [])
    if not rows:
        state["explanation"] = (
            "The query ran successfully but returned no rows. "
            "The selected filters may be too narrow for the current Northwind data."
        )
        return state

    state["explanation"] = _summarize_rows(state.get("query", ""), rows)
    return state


def _summarize_rows(query: str, rows: list[dict[str, Any]]) -> str:
    first_row = rows[0]
    row_count = len(rows)
    metric_key = _find_metric_key(first_row)
    if metric_key:
        label = _row_label(first_row, exclude=metric_key)
        metric_value = first_row[metric_key]
        return (
            f"The analysis returned {row_count} row(s) for the business question. "
            f"The leading result is {label} with "
            f"{metric_key.replace('_', ' ')} of {metric_value}."
        )
    label = _row_label(first_row)
    return (
        f"The analysis returned {row_count} row(s) for the business question. "
        f"The first result is {label}, which can be reviewed in the result table."
    )


def _find_metric_key(row: dict[str, Any]) -> str | None:
    preferred = ("revenue", "count", "average", "total", "quantity", "freight")
    for key in row:
        if any(frag in key.lower() for frag in preferred):
            return key
    return None


def _row_label(row: dict[str, Any], exclude: str | None = None) -> str:
    for key, value in row.items():
        if key == exclude:
            continue
        if isinstance(value, str) and value:
            return value
    for key, value in row.items():
        if key != exclude:
            return f"{key} {value}"
    return "the top row"
```

---

## 11. CONTROLLER: `backend/app/controller.py`

This is the most important file. It builds the LangGraph StateGraph, wraps each
agent in a @traceable node function with timing, defines the two routing functions,
and exposes `run_agent_pipeline()` as the single public entrypoint.

```python
"""Central AgentOps-style controller powered by LangGraph."""
from __future__ import annotations
from functools import lru_cache
from time import perf_counter
from typing import Any

from langgraph.graph import END, START, StateGraph
from langsmith import traceable

from backend.app.agents.disambiguation_agent import disambiguation_agent
from backend.app.agents.domain_guard_agent import domain_guard_agent
from backend.app.agents.execution_agent import execution_agent
from backend.app.agents.explanation_agent import explanation_agent
from backend.app.agents.retrieval_agent import retrieval_agent
from backend.app.agents.sql_generation_agent import sql_generation_agent
from backend.app.agents.validation_agent import validation_agent
from backend.app.schemas.state import AgentState


def initial_state(query: str) -> AgentState:
    return {
        "query": query,
        "refined_query": "",
        "schema": "",
        "sql": "",
        "result": [],
        "error": "",
        "retry_count": 0,
        "max_attempts": 2,
        "agent_trace": [],
    }


def run_agent_pipeline(query: str, max_attempts: int = 2) -> AgentState:
    state = initial_state(query)
    state["max_attempts"] = max_attempts
    graph = _build_workflow()
    return graph.invoke(state)


@lru_cache(maxsize=1)
def _build_workflow():
    workflow = StateGraph(AgentState)

    # Register all 7 nodes
    workflow.add_node("disambiguation", _disambiguation_node)
    workflow.add_node("domain_guard",   _domain_guard_node)
    workflow.add_node("retrieval",      _retrieval_node)
    workflow.add_node("sql_generation", _sql_generation_node)
    workflow.add_node("validation",     _validation_node)
    workflow.add_node("execution",      _execution_node)
    workflow.add_node("explanation",    _explanation_node)

    # Fixed edges
    workflow.add_edge(START, "disambiguation")
    workflow.add_edge("disambiguation", "domain_guard")
    workflow.add_edge("retrieval", "sql_generation")
    workflow.add_edge("sql_generation", "validation")
    workflow.add_edge("execution", "explanation")
    workflow.add_edge("explanation", END)

    # Conditional edges — the only branching points
    workflow.add_conditional_edges(
        "domain_guard",
        _route_after_domain_guard,
        {"retrieval": "retrieval", "explanation": "explanation"},
    )
    workflow.add_conditional_edges(
        "validation",
        _route_after_validation,
        {
            "sql_generation": "sql_generation",
            "execution":      "execution",
            "explanation":    "explanation",
        },
    )

    return workflow.compile()


# ── Routing functions ─────────────────────────────────────────────────────────

def _route_after_domain_guard(state: AgentState) -> str:
    if state.get("out_of_scope"):
        return "explanation"
    return "retrieval"


def _route_after_validation(state: AgentState) -> str:
    validation = state.get("validation", {})
    if validation.get("is_valid"):
        return "execution"
    can_retry = (
        validation.get("retryable", True)
        and state.get("retry_count", 0) < state.get("max_attempts", 2)
    )
    if can_retry:
        return "sql_generation"
    return "explanation"


# ── Node wrappers ─────────────────────────────────────────────────────────────
# Each wrapper: calls the agent, times it, appends to agent_trace,
# and returns ONLY the keys that agent is allowed to modify.

@traceable(name="Disambiguation Agent", run_type="chain")
def _disambiguation_node(state: AgentState) -> dict[str, Any]:
    started_at = perf_counter()
    updated = disambiguation_agent(dict(state))
    detail = (
        "Added default assumptions."
        if updated.get("is_ambiguous")
        else "Query was clear enough to continue."
    )
    return _state_update(
        current_state=state,
        updated_state=updated,
        keys=["is_ambiguous", "refined_query", "clarification"],
        agent="Disambiguation Agent",
        status="success",
        detail=detail,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
    )


@traceable(name="Domain Guard Agent", run_type="chain")
def _domain_guard_node(state: AgentState) -> dict[str, Any]:
    started_at = perf_counter()
    updated = domain_guard_agent(dict(state))
    detail = (
        str(updated.get("error"))
        if updated.get("out_of_scope")
        else "Question is within the Northwind domain."
    )
    return _state_update(
        current_state=state,
        updated_state=updated,
        keys=["out_of_scope", "error"],
        agent="Domain Guard Agent",
        status="success",
        detail=detail,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
    )


@traceable(name="Retrieval Agent", run_type="chain")
def _retrieval_node(state: AgentState) -> dict[str, Any]:
    started_at = perf_counter()
    updated = retrieval_agent(dict(state))
    detail = f"Selected {updated.get('schema', '').count('Table:')} schema table(s)."
    return _state_update(
        current_state=state,
        updated_state=updated,
        keys=["schema"],
        agent="Retrieval Agent",
        status="success",
        detail=detail,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
    )


@traceable(name="SQL Generation Agent", run_type="llm")
def _sql_generation_node(state: AgentState) -> dict[str, Any]:
    started_at = perf_counter()
    updated = sql_generation_agent(dict(state))
    return _state_update(
        current_state=state,
        updated_state=updated,
        keys=["sql"],
        agent="SQL Generation Agent",
        status="success",
        detail="Generated a SELECT statement for validation.",
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
    )


@traceable(name="Validation Agent", run_type="chain")
def _validation_node(state: AgentState) -> dict[str, Any]:
    started_at = perf_counter()
    validation = validation_agent(dict(state))
    duration_ms = round((perf_counter() - started_at) * 1000, 2)

    updates: dict[str, Any] = {
        "validation": validation,
        "error": "" if validation["is_valid"] else str(validation["error"]),
    }

    should_retry = (
        not validation["is_valid"]
        and validation.get("retryable", True)
        and state.get("retry_count", 0) < state.get("max_attempts", 2)
    )
    if should_retry:
        updates["retry_count"] = state.get("retry_count", 0) + 1

    updates["agent_trace"] = list(state.get("agent_trace", [])) + [
        _trace_item(
            agent="Validation Agent",
            status="success" if validation["is_valid"] else "failed",
            detail=str(validation.get("detail") or updates["error"] or "Validation succeeded."),
            duration_ms=duration_ms,
        )
    ]
    return updates


@traceable(name="Execution Agent", run_type="tool")
def _execution_node(state: AgentState) -> dict[str, Any]:
    started_at = perf_counter()
    updated = execution_agent(dict(state))
    detail = (
        f"Returned {len(updated.get('result', []))} row(s)."
        if not updated.get("error")
        else str(updated["error"])
    )
    return _state_update(
        current_state=state,
        updated_state=updated,
        keys=["sql", "result", "error", "data_source"],
        agent="Execution Agent",
        status="success" if not updated.get("error") else "failed",
        detail=detail,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
    )


@traceable(name="Explanation Agent", run_type="chain")
def _explanation_node(state: AgentState) -> dict[str, Any]:
    started_at = perf_counter()
    updated = explanation_agent(dict(state))
    detail = (
        "Explained that the question is out of scope for Northwind."
        if updated.get("out_of_scope")
        else "Explained why the pipeline could not finish."
        if updated.get("error")
        else "Created a business summary."
    )
    return _state_update(
        current_state=state,
        updated_state=updated,
        keys=["explanation"],
        agent="Explanation Agent",
        status="success",
        detail=detail,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _state_update(
    current_state: AgentState,
    updated_state: AgentState,
    keys: list[str],
    agent: str,
    status: str,
    detail: str,
    duration_ms: float,
) -> dict[str, Any]:
    updates = {key: updated_state.get(key) for key in keys}
    updates["agent_trace"] = list(current_state.get("agent_trace", [])) + [
        _trace_item(agent, status, detail, duration_ms)
    ]
    return updates


def _trace_item(
    agent: str, status: str, detail: str, duration_ms: float
) -> dict[str, Any]:
    return {"agent": agent, "status": status, "detail": detail, "duration_ms": duration_ms}
```

---

## 12. FRONTEND: `frontend/streamlit_app.py`

```python
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
    "Highest sold car model",          # triggers domain guard rejection
]

st.title("InsightSQL")
st.caption("Agentic NL2SQL prototype for Northwind analytics")

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
    st.write(
        f"LLM: {settings.llm_provider} / "
        f"{settings.ollama_model if settings.llm_provider == 'ollama' else settings.openai_model}"
    )
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
            "refined_query":    state.get("refined_query"),
            "retry_count":      state.get("retry_count"),
            "validation":       state.get("validation"),
            "data_source":      state.get("data_source"),
            "out_of_scope":     state.get("out_of_scope"),
            "workflow_engine":  "langgraph",
            "llm_provider":     settings.llm_provider,
            "llm_model":        settings.ollama_model if settings.llm_provider == "ollama"
                                else settings.openai_model,
            "langsmith_tracing": settings.langsmith_tracing,
            "db_health":        db_health,
        })

elif submitted:
    st.warning("Enter a query to run the agent pipeline.")
```

---

## 13. TESTS

### `tests/test_agents.py`

Write the following 9 tests. All must pass without a live Postgres or LLM:

```
test_disambiguation_marks_ambiguous_and_adds_default_assumption
  - Input: {"query": "Show recent orders"}
  - Assert: state["is_ambiguous"] is True
  - Assert: "last 30 days" in state["refined_query"]

test_retrieval_selects_relevant_schema_snippets
  - Input: {"refined_query": "Top customers by revenue"}
  - Assert: "Table: customers" in state["schema"]
  - Assert: "Table: orders" in state["schema"]
  - Assert: "Table: order_details" in state["schema"]

test_domain_guard_rejects_out_of_scope_query
  - Input: {"query": "Highest sold car model"}
  - Assert: state["out_of_scope"] is True
  - Assert: "outside the Northwind domain" in state["error"]

test_domain_guard_allows_supported_query
  - Input: {"query": "Top customers by revenue"}
  - Assert: state["out_of_scope"] is False

test_validation_blocks_dangerous_sql
  - Input: {"sql": "DELETE FROM customers;"}
  - Assert: result["is_valid"] is False
  - Assert: "forbidden" in str(result["error"])

test_validation_uses_explain_for_safe_sql (monkeypatch explain_query)
  - Monkeypatch explain_query to return [{"QUERY PLAN": "Seq Scan"}]
  - Input: {"sql": "SELECT customers.customer_id FROM customers;"}
  - Assert: result["is_valid"] is True
  - Assert: explain was called with the exact SQL

test_validation_marks_database_connection_errors_not_retryable (monkeypatch)
  - Monkeypatch explain_query to raise RuntimeError("connection refused")
  - Monkeypatch get_settings to return execution_backend="postgres"
  - Assert: result["is_valid"] is False
  - Assert: result["retryable"] is False
  - Assert: "PostgreSQL refused" in str(result["error"])

test_validation_falls_back_to_demo_when_auto_mode_cannot_reach_database (monkeypatch)
  - Monkeypatch explain_query to raise RuntimeError("connection refused")
  - Monkeypatch get_settings to return execution_backend="auto"
  - Assert: result["is_valid"] is True
  - Assert: result["execution_backend"] == "demo"

test_execution_adds_limit_safeguard_when_missing
  - Call _with_limit_safeguard("SELECT customers.customer_id FROM customers;")
  - Assert: result ends with "LIMIT 100;"

test_execution_uses_demo_backend_when_requested
  - Input: sql = customer revenue query, validation={"execution_backend": "demo"}
  - Assert: state["data_source"] == "demo"
  - Assert: len(state["result"]) > 0
```

### `tests/test_controller.py`

Write the following 4 tests using monkeypatch to fake agents:

```
test_controller_retries_after_validation_error
  - First sql_generation returns bad SQL, second returns good SQL
  - First validation returns is_valid=False, second returns is_valid=True
  - Assert: state["retry_count"] == 1
  - Assert: state["result"] == [{"customer_id": "ALFKI"}]
  - Assert: agent_trace order is exactly:
    [Disambiguation Agent, Domain Guard Agent, Retrieval Agent,
     SQL Generation Agent, Validation Agent,
     SQL Generation Agent, Validation Agent,    ← retry
     Execution Agent, Explanation Agent]

test_controller_does_not_retry_database_connection_errors
  - validation returns is_valid=False, retryable=False
  - Assert: state["retry_count"] == 0
  - Assert: state["result"] == []
  - Assert: "PostgreSQL refused" in state["error"]
  - Assert: execution_agent is NEVER called (use AssertionError if it is)

test_controller_stops_on_out_of_scope_query
  - Use real run_agent_pipeline("Highest sold car model")
  - Assert: state["out_of_scope"] is True
  - Assert: state.get("sql", "") == ""
  - Assert: agent_trace contains only:
    [Disambiguation Agent, Domain Guard Agent, Explanation Agent]

test_controller_executes_with_demo_backend_when_validation_allows_it
  - validation returns is_valid=True, execution_backend="demo"
  - execution returns result=[{"customer_id": "ALFKI"}], data_source="demo"
  - Assert: state["result"] == [{"customer_id": "ALFKI"}]
  - Assert: state["data_source"] == "demo"
```

---

## 14. NORTHWIND SQL DUMP

Place a compact Northwind-compatible PostgreSQL schema + data dump at:
`data/postgres/init/01_northwind_demo.sql`

It must create and populate these 8 tables:
customers, employees, shippers, categories, suppliers, products, orders, order_details

Use the same data as the demo_data.py in-memory tables (same rows, same values).
Include CREATE TABLE statements with proper types, PRIMARY KEY and FOREIGN KEY
constraints, and INSERT statements. Use IF NOT EXISTS on creates.

---

## 15. HOW TO RUN (put this in README.md)

```
# Minimum — zero setup, works immediately
pip install -r requirements.txt
python -m streamlit run frontend/streamlit_app.py

# With PostgreSQL via Docker
docker compose up -d
python -m streamlit run frontend/streamlit_app.py

# With OpenAI LLM
cp .env.example .env
# Edit .env: LLM_PROVIDER=openai, OPENAI_API_KEY=sk-...
python -m streamlit run frontend/streamlit_app.py

# With Ollama
ollama pull qwen3.5:9b
# Edit .env: LLM_PROVIDER=ollama, OLLAMA_MODEL=qwen3.5:9b
python -m streamlit run frontend/streamlit_app.py

# With LangSmith tracing
# Edit .env: LANGSMITH_TRACING=true, LANGSMITH_API_KEY=ls__...
python -m streamlit run frontend/streamlit_app.py

# Run tests (no Postgres or LLM required)
pytest
```

---

## 16. IMPLEMENTATION ORDER

Implement in this exact order to avoid import errors:

1. All `__init__.py` files (empty)
2. `backend/app/schemas/state.py`
3. `backend/app/core/config.py`
4. `backend/app/db/connection.py`
5. `backend/app/db/health.py`
6. `backend/app/db/northwind_schema.py`
7. `backend/app/db/demo_data.py`
8. `backend/app/db/demo_executor.py`
9. `backend/app/prompts/sql_generation.py`
10. `backend/app/services/llm.py`
11. All 7 agent files (any order)
12. `backend/app/controller.py`
13. `frontend/streamlit_app.py`
14. `tests/test_agents.py`
15. `tests/test_controller.py`
16. `data/postgres/init/01_northwind_demo.sql`
17. `.env.example`, `docker-compose.yml`, `pytest.ini`, `requirements.txt`

After implementing all files, run `pytest` and confirm all tests pass.
Then run `python -m streamlit run frontend/streamlit_app.py` and confirm the UI loads.

---

## 17. CRITICAL RULES — DO NOT VIOLATE

1. **No agent imports another agent.** Agents are pure functions. Only controller.py
   imports agents.

2. **Agents never call get_settings() except validation_agent.** Config reads happen
   in services/llm.py and db/ files.

3. **controller.py node functions return only the keys listed in \_state_update keys=[].**
   Never let a node overwrite keys it doesn't own. The validation node is the exception
   — it has a custom update block because it also manages retry_count.

4. **\_build_workflow() is cached with @lru_cache(maxsize=1).** The graph is compiled
   once and reused. Never call workflow.compile() outside this function.

5. **The LIMIT safeguard operates on the final SQL string.** Never parse SQL structure.
   `if "limit" not in sql.lower(): sql = sql.rstrip().rstrip(";") + " LIMIT 100;"`

6. **Safety validation returns retryable=False for forbidden SQL.** Retrying a
   DROP TABLE query will produce another DROP TABLE query.

7. **EXPLAIN runs without a semicolon.** Strip the trailing semicolon before passing
   to EXPLAIN: `cursor.execute(f"EXPLAIN {sql.rstrip(';')}")`

8. **All **init**.py files must exist** even if empty. Python treats directories as
   packages only when **init**.py is present.

9. **The domain guard uses set intersection, not substring matching.** Use
   `re.findall(r"[a-zA-Z_]+", query)` to tokenise, then `tokens & WORD_SET`.

10. **LangSmith is activated by environment variables only.** No code changes needed
    to enable/disable tracing. The @traceable decorators activate automatically when
    LANGCHAIN_TRACING_V2 is set (LangSmith reads this from env).
