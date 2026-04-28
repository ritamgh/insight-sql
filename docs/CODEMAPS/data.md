<!-- Generated: 2026-04-29 | Files scanned: 3 | Token estimate: ~500 -->

# Data Layer

## PostgreSQL (Northwind)

Docker Compose: `postgres:16` on port `5433:5432`, database `northwind`.

Init script: `data/postgres/init/01_northwind_demo.sql`

### Tables (15 in schema metadata)

```
categories, customers, employees, orders, order_details, products,
shippers, suppliers, region, territories, employee_territories,
customer_customer_demo, customer_demographics, us_states
```

### Key Relationships (13 FKs)

```
orders.customer_id → customers.customer_id
orders.employee_id → employees.employee_id
orders.ship_via → shippers.shipper_id
order_details.order_id → orders.order_id
order_details.product_id → products.product_id
products.category_id → categories.category_id
products.supplier_id → suppliers.supplier_id
employees.reports_to → employees.employee_id  (self-join)
territories.region_id → region.region_id
employee_territories.territory_id → territories.territory_id
employee_territories.employee_id → employees.employee_id
customer_customer_demo.customer_id → customers.customer_id
customer_customer_demo.customer_type_id → customer_demographics.customer_type_id
```

### Business Metrics

`revenue = order_details.unit_price * quantity * (1 - discount)`

## ChromaDB RAG Index

`.rag_index/` — Persistent ChromaDB with 2 collections:

| Collection | Contents | K |
|------------|----------|---|
| `schema_chunks` | Column-level chunks (one per column, with FK info) | 3 |
| `examples` | 18 Q→SQL example pairs | 2 |

Built via `scripts/build_rag_index.py`.

## Demo Data Backend

`backend/app/db/demo_data.py` — Hardcoded Northwind DataFrames.
`backend/app/db/demo_executor.py` — Pattern-matches SQL to pandas operations (8 patterns).

## Schema Metadata

`backend/app/db/northwind_full_schema.py` — Full schema for RAG and validation:
- `TABLE_COLUMNS` — 15 tables with column names and type descriptions
- `PRIMARY_KEYS` — composite and single-column PKs
- `FOREIGN_KEYS` — 13 tuples `(child_table, child_col, parent_table, parent_col)`

`backend/app/db/northwind_schema.py` — Legacy keyword→table mapping (18 keywords).

## Evaluation Golden Dataset

`evaluation/golden_dataset.py` — 50 questions across 6 categories:
- 10 simple SELECT, 10 two-table JOIN, 10 multi-table JOIN (3+), 10 aggregation, 5 GROUP BY + HAVING, 5 time-based
- Each with hand-verified `gold_sql` and `time_sensitive` flag
