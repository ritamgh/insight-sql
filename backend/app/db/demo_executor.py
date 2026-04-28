"""Pattern-match SQL string to pandas computation. Never actually runs SQL."""
from __future__ import annotations
import re
from typing import Any

import pandas as pd

from backend.app.db.demo_data import load_demo_tables


def fetch_demo_rows(sql: str) -> list[dict[str, Any]]:
    sql_lower = sql.lower()
    tables = load_demo_tables()

    if _mentions(sql_lower, "categories") and "total_revenue" in sql_lower:
        return _category_revenue(tables)
    if _mentions(sql_lower, "employees") and "total_revenue" in sql_lower:
        return _employee_revenue(tables)
    if _mentions(sql_lower, "products") and "order_count" in sql_lower:
        return _product_order_count(tables)
    if _mentions(sql_lower, "products") and "units_in_stock" in sql_lower:
        return _product_inventory(tables)
    if _mentions(sql_lower, "products") and "total_revenue" in sql_lower:
        return _product_revenue(tables)
    if _mentions(sql_lower, "shippers"):
        return _shipper_freight(tables)
    if _mentions(sql_lower, "customers") and "count(customers.customer_id)" in sql_lower:
        return _customers_by_country(tables)
    if "where orders.order_date >=" in sql_lower:
        return _recent_orders(tables, sql_lower)
    if _mentions(sql_lower, "customers") and "total_revenue" in sql_lower:
        return _customer_revenue(tables)
    return _recent_orders(tables, sql_lower)


def _mentions(sql_lower: str, table: str) -> bool:
    return bool(re.search(rf"\b{re.escape(table)}\b", sql_lower))


def _customer_revenue(tables: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    od = tables["order_details"].copy()
    od["revenue"] = od["unit_price"] * od["quantity"] * (1 - od["discount"])
    merged = (
        od.merge(tables["orders"][["order_id", "customer_id"]], on="order_id")
          .merge(tables["customers"][["customer_id", "company_name"]], on="customer_id")
    )
    result = (
        merged.groupby(["customer_id", "company_name"], as_index=False)["revenue"]
              .sum()
              .rename(columns={"revenue": "total_revenue"})
              .sort_values("total_revenue", ascending=False)
              .head(10)
    )
    result["total_revenue"] = result["total_revenue"].round(2)
    return result.to_dict(orient="records")


def _product_revenue(tables: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    od = tables["order_details"].copy()
    od["revenue"] = od["unit_price"] * od["quantity"] * (1 - od["discount"])
    merged = od.merge(
        tables["products"][["product_id", "product_name"]], on="product_id"
    )
    result = (
        merged.groupby(["product_id", "product_name"], as_index=False)["revenue"]
              .sum()
              .rename(columns={"revenue": "total_revenue"})
              .sort_values("total_revenue", ascending=False)
              .head(10)
    )
    result["total_revenue"] = result["total_revenue"].round(2)
    return result.to_dict(orient="records")


def _product_order_count(tables: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    merged = tables["order_details"].merge(
        tables["products"][["product_id", "product_name"]], on="product_id"
    )
    result = (
        merged.groupby(["product_id", "product_name"], as_index=False)["order_id"]
              .nunique()
              .rename(columns={"order_id": "order_count"})
              .sort_values("order_count", ascending=False)
              .head(10)
    )
    return result.to_dict(orient="records")


def _category_revenue(tables: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    od = tables["order_details"].copy()
    od["revenue"] = od["unit_price"] * od["quantity"] * (1 - od["discount"])
    merged = (
        od.merge(tables["products"][["product_id", "category_id"]], on="product_id")
          .merge(tables["categories"][["category_id", "category_name"]], on="category_id")
    )
    result = (
        merged.groupby("category_name", as_index=False)["revenue"]
              .sum()
              .rename(columns={"revenue": "total_revenue"})
              .sort_values("total_revenue", ascending=False)
              .head(10)
    )
    result["total_revenue"] = result["total_revenue"].round(2)
    return result.to_dict(orient="records")


def _employee_revenue(tables: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    od = tables["order_details"].copy()
    od["revenue"] = od["unit_price"] * od["quantity"] * (1 - od["discount"])
    merged = (
        od.merge(tables["orders"][["order_id", "employee_id"]], on="order_id")
          .merge(
              tables["employees"][["employee_id", "first_name", "last_name"]],
              on="employee_id",
          )
    )
    result = (
        merged.groupby(["employee_id", "first_name", "last_name"], as_index=False)["revenue"]
              .sum()
              .rename(columns={"revenue": "total_revenue"})
              .sort_values("total_revenue", ascending=False)
              .head(10)
    )
    result["total_revenue"] = result["total_revenue"].round(2)
    return result.to_dict(orient="records")


def _product_inventory(tables: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    merged = (
        tables["products"]
        .merge(tables["categories"][["category_id", "category_name"]], on="category_id")
        .merge(
            tables["suppliers"][["supplier_id", "company_name"]].rename(
                columns={"company_name": "supplier_name"}
            ),
            on="supplier_id",
        )
    )
    result = (
        merged[["product_id", "product_name", "category_name", "supplier_name", "units_in_stock"]]
        .sort_values("units_in_stock")
        .head(20)
    )
    return result.to_dict(orient="records")


def _shipper_freight(tables: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    merged = tables["orders"].merge(
        tables["shippers"].rename(columns={"company_name": "shipper_name"}),
        left_on="ship_via",
        right_on="shipper_id",
    )
    result = (
        merged.groupby("shipper_name", as_index=False)
              .agg(order_count=("order_id", "count"), average_freight=("freight", "mean"))
              .sort_values("order_count", ascending=False)
              .head(10)
    )
    result["average_freight"] = result["average_freight"].round(2)
    return result.to_dict(orient="records")


def _customers_by_country(tables: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    result = (
        tables["customers"]
        .groupby("country", as_index=False)
        .agg(customer_count=("customer_id", "count"))
        .sort_values("customer_count", ascending=False)
        .head(20)
    )
    return result.to_dict(orient="records")


def _recent_orders(tables: dict[str, pd.DataFrame], sql_lower: str = "") -> list[dict[str, Any]]:
    orders = tables["orders"].copy()
    cutoff = _dataset_relative_cutoff(orders["order_date"].max(), sql_lower)
    recent = orders[orders["order_date"] >= cutoff].copy()
    merged = recent.merge(
        tables["customers"][["customer_id", "company_name"]], on="customer_id"
    ).sort_values("order_date", ascending=False)
    merged["order_date"] = merged["order_date"].dt.strftime("%Y-%m-%d")
    merged["shipped_date"] = merged["shipped_date"].dt.strftime("%Y-%m-%d")
    merged["freight"] = merged["freight"].round(2)
    cols = ["order_id", "company_name", "order_date", "shipped_date", "freight"]
    return merged[cols].to_dict(orient="records")


def _dataset_relative_cutoff(max_order_date: pd.Timestamp, sql_lower: str) -> pd.Timestamp:
    match = re.search(r"interval\s+'(\d+)\s+(day|days|week|weeks|month|months|year|years)'", sql_lower)
    if not match:
        return max_order_date - pd.Timedelta(days=30)
    amount = int(match.group(1))
    unit = match.group(2)
    if unit.startswith("day"):
        return max_order_date - pd.Timedelta(days=amount)
    if unit.startswith("week"):
        return max_order_date - pd.Timedelta(weeks=amount)
    if unit.startswith("month"):
        return max_order_date - pd.DateOffset(months=amount)
    if unit.startswith("year"):
        return max_order_date - pd.DateOffset(years=amount)
    return max_order_date - pd.Timedelta(days=30)
