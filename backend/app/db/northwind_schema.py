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
