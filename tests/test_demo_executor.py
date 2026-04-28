"""Tests for the demo SQL executor routing."""
from __future__ import annotations

from backend.app.db.demo_executor import fetch_demo_rows


def test_demo_category_revenue_handles_order_details_from_clause():
    sql = """
SELECT
    categories.category_name,
    SUM(order_details.unit_price * order_details.quantity * (1 - order_details.discount)) AS total_revenue
FROM order_details
JOIN products ON order_details.product_id = products.product_id
JOIN categories ON products.category_id = categories.category_id
GROUP BY categories.category_name
ORDER BY total_revenue DESC
LIMIT 10;
"""
    rows = fetch_demo_rows(sql)
    assert rows
    assert set(rows[0]) == {"category_name", "total_revenue"}


def test_demo_employee_revenue_handles_order_details_from_clause():
    sql = """
SELECT
    employees.employee_id,
    employees.first_name,
    employees.last_name,
    SUM(order_details.unit_price * order_details.quantity * (1 - order_details.discount)) AS total_revenue
FROM order_details
JOIN orders ON order_details.order_id = orders.order_id
JOIN employees ON orders.employee_id = employees.employee_id
GROUP BY employees.employee_id, employees.first_name, employees.last_name
ORDER BY total_revenue DESC
LIMIT 10;
"""
    rows = fetch_demo_rows(sql)
    assert rows
    assert set(rows[0]) == {"employee_id", "first_name", "last_name", "total_revenue"}


def test_demo_product_order_count_handles_joined_query():
    sql = """
SELECT
    products.product_id,
    products.product_name,
    COUNT(DISTINCT order_details.order_id) AS order_count
FROM products
JOIN order_details ON products.product_id = order_details.product_id
GROUP BY products.product_id, products.product_name
ORDER BY order_count DESC
LIMIT 10;
"""
    rows = fetch_demo_rows(sql)
    assert rows
    assert set(rows[0]) == {"product_id", "product_name", "order_count"}
