<!-- Generated: 2026-04-28 | Files scanned: 3 | Token estimate: ~500 -->

# Data Layer

## PostgreSQL (Northwind)

Docker Compose: `postgres:16` on port `5433:5432`, database `northwind`.

Init script: `data/postgres/init/01_northwind_demo.sql`

### Tables

```
categories     (category_id PK, category_name, description, picture)
customers      (customer_id PK, company_name, contact_name, city, country)
employees      (employee_id PK, first_name, last_name, title, country)
orders         (order_id PK, customer_id FK→customers, employee_id FK→employees,
                order_date, shipped_date, ship_via FK→shippers, freight)
order_details  (order_id FK→orders, product_id FK→products, unit_price, quantity, discount)
products       (product_id PK, product_name, supplier_id FK→suppliers,
                category_id FK→categories, unit_price, units_in_stock, discontinued)
shippers       (shipper_id PK, company_name)
suppliers      (supplier_id PK, company_name, city, country)
```

### Key Relationships

```
customers ──1:N──→ orders ──1:N──→ order_details ←──N:1── products
employees  ──1:N──→ orders                    products ←──N:1── categories
shippers   ──1:N──→ orders                    products ←──N:1── suppliers
```

### Business Metrics

`revenue = order_details.unit_price * quantity * (1 - discount)`

## Demo Data Backend

`backend/app/db/demo_data.py` (83 lines) — Hardcoded Northwind DataFrames.

`backend/app/db/demo_executor.py` (165 lines) — Pattern-matches SQL to pandas operations.

### Supported Demo Query Patterns

| Pattern | SQL Match | Pandas Function |
|---------|-----------|-----------------|
| Customer revenue | `FROM customers` + `total_revenue` | `_customer_revenue()` |
| Product revenue | `FROM products` + `total_revenue` | `_product_revenue()` |
| Category revenue | `FROM categories` + `total_revenue` | `_category_revenue()` |
| Employee revenue | `FROM employees` + `total_revenue` | `_employee_revenue()` |
| Product inventory | `FROM products` + `units_in_stock` | `_product_inventory()` |
| Shipper freight | `FROM shippers` | `_shipper_freight()` |
| Customers by country | `COUNT(customers.customer_id)` | `_customers_by_country()` |
| Recent orders | `WHERE orders.order_date >=` | `_recent_orders()` |
| Fallback | (anything else) | `_recent_orders()` |

## Schema Retrieval

`backend/app/db/northwind_schema.py` — Keyword→table mapping for RAG-style retrieval.
Maps 18 keywords (customer, order, revenue, freight, etc.) to relevant table groups.
