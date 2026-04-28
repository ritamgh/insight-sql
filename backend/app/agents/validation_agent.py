"""Four-layer SQL validation: safety, schema, EXPLAIN, and semantic checks."""
from __future__ import annotations
import re
from typing import Any

try:
    import sqlglot
    from sqlglot import exp
except ModuleNotFoundError:
    sqlglot = None
    exp = None

from backend.app.db.connection import explain_query
from backend.app.db.health import is_database_connection_error
from backend.app.db.northwind_full_schema import TABLE_COLUMNS
from backend.app.schemas.state import AgentState

FORBIDDEN_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|COPY)\b",
    flags=re.IGNORECASE,
)


def validation_agent(state: AgentState) -> dict[str, Any]:
    sql = state.get("sql", "").strip()
    if not state.get("use_validation_layers", True):
        return _legacy_validation(sql)

    layers: list[str] = []
    parsed: Any = None
    for layer_name, check in (
        ("safety", _safety_check),
        ("schema", _schema_check),
        ("semantic", _semantic_check),
        ("explain", _explain_check),
    ):
        layers.append(layer_name)
        result = check(sql, parsed) if layer_name != "safety" else check(sql, None)
        if layer_name == "safety" and result.get("parsed") is not None:
            parsed = result["parsed"]
        if not result["is_valid"]:
            return {
                "is_valid": False,
                "error": result["error"],
                "retryable": result.get("retryable", True),
                "execution_backend": result.get("execution_backend", "postgres"),
                "validation_layers_triggered": layers,
                "failed_layer": layer_name,
                "detail": result.get("detail", result["error"]),
            }
        if result.get("execution_backend") == "demo":
            return {
                "is_valid": True,
                "error": "",
                "retryable": True,
                "execution_backend": "demo",
                "validation_layers_triggered": layers,
                "failed_layer": None,
                "detail": "PostgreSQL unavailable — using demo data.",
            }

    return {
        "is_valid": True,
        "error": "",
        "retryable": True,
        "execution_backend": "postgres",
        "validation_layers_triggered": layers,
        "failed_layer": None,
        "detail": "SQL passed safety, schema, EXPLAIN, and semantic checks.",
    }


def _safety_check(sql: str, _: Any) -> dict[str, Any]:
    if not sql:
        return _invalid("SQL is empty.", retryable=False)
    normalized = sql.rstrip().rstrip(";")
    if ";" in normalized:
        return _invalid("SQL must contain exactly one statement.", retryable=False)
    sql_without_literals = _strip_literals_and_comments(sql)
    if FORBIDDEN_SQL.search(sql_without_literals):
        return _invalid("SQL contains a forbidden write or DDL keyword.", retryable=False)
    if sqlglot is None:
        if not re.match(r"^\s*(SELECT|WITH)\b", normalized, flags=re.IGNORECASE):
            return _invalid("Only SELECT and WITH queries are allowed.", retryable=False)
        return {"is_valid": True, "parsed": None}
    try:
        statements = sqlglot.parse(sql, read="postgres")
    except Exception as exc:
        return _invalid(f"SQL parse failed: {exc}", retryable=True)
    if len(statements) != 1:
        return _invalid("SQL must contain exactly one statement.", retryable=False)
    parsed = statements[0]
    if not isinstance(parsed, (exp.Select, exp.With)) and parsed.find(exp.Select) is None:
        return _invalid("Only SELECT and WITH queries are allowed.", retryable=False)
    forbidden_nodes = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create)
    if any(parsed.find(node_type) for node_type in forbidden_nodes):
        return _invalid("SQL contains a forbidden write or DDL statement.", retryable=False)
    return {"is_valid": True, "parsed": parsed}


def _strip_literals_and_comments(sql: str) -> str:
    without_block_comments = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    without_line_comments = re.sub(r"--[^\n\r]*", " ", without_block_comments)
    without_single_quotes = re.sub(r"'(?:''|[^'])*'", "''", without_line_comments)
    return re.sub(r'"(?:""|[^"])*"', '""', without_single_quotes)


def _schema_check(sql: str, parsed: Any) -> dict[str, Any]:
    if sqlglot is None or parsed is None:
        return _schema_check_fallback(sql)
    tables = _table_aliases(parsed)
    select_aliases = _select_aliases(parsed)
    for table in tables.values():
        if table not in TABLE_COLUMNS:
            return _invalid(f"Unknown table: {table}", retryable=True)
    for column in parsed.find_all(exp.Column):
        name = column.name
        qualifier = column.table
        if name == "*":
            continue
        if qualifier:
            table = tables.get(qualifier, qualifier)
            if table in TABLE_COLUMNS and name not in TABLE_COLUMNS[table]:
                return _invalid(f"Unknown column: {qualifier}.{name}", retryable=True)
            if table not in TABLE_COLUMNS:
                return _invalid(f"Unknown table or alias: {qualifier}", retryable=True)
            continue
        if name in select_aliases:
            continue
        if tables and not any(name in TABLE_COLUMNS[table] for table in tables.values()):
            return _invalid(f"Unknown column: {name}", retryable=True)
    return {"is_valid": True}


def _explain_check(sql: str, _: Any) -> dict[str, Any]:
    try:
        explain_query(sql)
    except Exception as exc:
        if is_database_connection_error(exc):
            return {"is_valid": True, "execution_backend": "demo"}
        return _invalid(f"EXPLAIN failed: {exc}", retryable=True, execution_backend="postgres")
    return {"is_valid": True, "execution_backend": "postgres"}


def _semantic_check(sql: str, parsed: Any) -> dict[str, Any]:
    if sqlglot is None or parsed is None:
        return _semantic_check_fallback(sql)
    tables = list(_table_aliases(parsed).keys())
    if len(tables) >= 2 and not _has_join_condition(parsed):
        return _invalid("Multi-table queries must include explicit JOIN ... ON or a join predicate.", retryable=True)
    group = parsed.args.get("group")
    if group:
        grouped = {expr.sql(dialect="postgres").lower() for expr in group.expressions}
        for projection in parsed.expressions:
            expr_node = projection.this if isinstance(projection, exp.Alias) else projection
            if _contains_aggregate(expr_node):
                continue
            if expr_node.sql(dialect="postgres").lower() not in grouped:
                return _invalid(
                    f"Non-aggregated SELECT expression is missing from GROUP BY: {expr_node.sql(dialect='postgres')}",
                    retryable=True,
                )
    return {"is_valid": True}


def _legacy_validation(sql: str) -> dict[str, Any]:
    safety = _safety_check(sql, None)
    if not safety["is_valid"]:
        return {**safety, "validation_layers_triggered": ["safety"], "failed_layer": "safety"}
    explain = _explain_check(sql, None)
    if not explain["is_valid"]:
        return {**explain, "validation_layers_triggered": ["explain"], "failed_layer": "explain"}
    return {
        "is_valid": True,
        "error": "",
        "retryable": True,
        "execution_backend": explain.get("execution_backend", "postgres"),
        "validation_layers_triggered": ["safety", "explain"],
        "failed_layer": None,
        "detail": "SQL passed legacy safety and EXPLAIN checks.",
    }


def _table_aliases(parsed: Any) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for table in parsed.find_all(exp.Table):
        name = table.name
        if not name:
            continue
        aliases[name] = name
        alias = table.alias
        if alias:
            aliases[alias] = name
    return aliases


def _select_aliases(parsed: Any) -> set[str]:
    aliases: set[str] = set()
    for projection in getattr(parsed, "expressions", []) or []:
        if isinstance(projection, exp.Alias) and projection.alias:
            aliases.add(projection.alias)
    return aliases


def _has_join_condition(parsed: Any) -> bool:
    joins = list(parsed.find_all(exp.Join))
    if joins and all(join.args.get("on") is not None for join in joins):
        return True
    where = parsed.args.get("where")
    return bool(where and re.search(r"\b[a-z_][\w]*\.[a-z_][\w]*\s*=\s*[a-z_][\w]*\.[a-z_][\w]*", where.sql(dialect="postgres"), re.I))


def _contains_aggregate(node: Any) -> bool:
    aggregate_types = (exp.Sum, exp.Count, exp.Avg, exp.Min, exp.Max)
    return isinstance(node, aggregate_types) or any(node.find(agg) for agg in aggregate_types)


def _schema_check_fallback(sql: str) -> dict[str, Any]:
    table_names = re.findall(r"\bFROM\s+([a-z_][\w]*)|\bJOIN\s+([a-z_][\w]*)", sql, flags=re.I)
    tables = [next(name for name in pair if name).lower() for pair in table_names]
    for table in tables:
        if table not in TABLE_COLUMNS:
            return _invalid(f"Unknown table: {table}", retryable=True)
    for qualifier, column in re.findall(r"\b([a-z_][\w]*)\.([a-z_][\w]*)", sql, flags=re.I):
        table = qualifier.lower()
        col = column.lower()
        if table in TABLE_COLUMNS and col not in TABLE_COLUMNS[table]:
            return _invalid(f"Unknown column: {table}.{col}", retryable=True)
    return {"is_valid": True}


def _semantic_check_fallback(sql: str) -> dict[str, Any]:
    lower_sql = sql.lower()
    if re.search(r"\bfrom\s+[a-z_][\w]*(?:\s+[a-z_][\w]*)?\s*,\s*[a-z_][\w]*", lower_sql):
        return _invalid("Multi-table queries must use explicit JOIN ... ON.", retryable=True)
    return {"is_valid": True}


def _invalid(
    error: str,
    *,
    retryable: bool,
    execution_backend: str = "postgres",
) -> dict[str, Any]:
    return {
        "is_valid": False,
        "error": error,
        "retryable": retryable,
        "execution_backend": execution_backend,
        "detail": error,
    }
