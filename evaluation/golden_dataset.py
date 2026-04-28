"""Golden NL2SQL dataset for comparing pipeline configurations."""
from __future__ import annotations

_BASE: list[dict[str, object]] = [
    {"category": "simple", "question": "List all customers in Germany", "gold_sql": "SELECT customers.customer_id, customers.company_name, customers.city FROM customers WHERE customers.country = 'Germany' ORDER BY customers.company_name;"},
    {"category": "simple", "question": "List products with fewer than 20 units in stock", "gold_sql": "SELECT products.product_id, products.product_name, products.units_in_stock FROM products WHERE products.units_in_stock < 20 ORDER BY products.units_in_stock ASC;"},
    {"category": "simple", "question": "Show all shippers", "gold_sql": "SELECT shippers.shipper_id, shippers.company_name FROM shippers ORDER BY shippers.company_name;"},
    {"category": "simple", "question": "List suppliers in USA", "gold_sql": "SELECT suppliers.supplier_id, suppliers.company_name, suppliers.city FROM suppliers WHERE suppliers.country = 'USA' ORDER BY suppliers.company_name;"},
    {"category": "simple", "question": "Show discontinued products", "gold_sql": "SELECT products.product_id, products.product_name FROM products WHERE products.discontinued = 1 ORDER BY products.product_name;"},
    {"category": "simple", "question": "List employees in USA", "gold_sql": "SELECT employees.employee_id, employees.first_name, employees.last_name FROM employees WHERE employees.country = 'USA' ORDER BY employees.last_name;"},
    {"category": "simple", "question": "Show customers by country", "gold_sql": "SELECT customers.country, COUNT(customers.customer_id) AS customer_count FROM customers GROUP BY customers.country ORDER BY customer_count DESC;"},
    {"category": "simple", "question": "List categories", "gold_sql": "SELECT categories.category_id, categories.category_name FROM categories ORDER BY categories.category_name;"},
    {"category": "simple", "question": "Show orders with high freight", "gold_sql": "SELECT orders.order_id, orders.customer_id, orders.freight FROM orders WHERE orders.freight > 100 ORDER BY orders.freight DESC;"},
    {"category": "simple", "question": "List product prices", "gold_sql": "SELECT products.product_name, products.unit_price FROM products ORDER BY products.unit_price DESC;"},
    {"category": "two-table", "question": "Show orders with customer names", "gold_sql": "SELECT orders.order_id, customers.company_name, orders.order_date FROM orders JOIN customers ON orders.customer_id = customers.customer_id ORDER BY orders.order_date DESC;"},
    {"category": "two-table", "question": "Show products with category names", "gold_sql": "SELECT products.product_name, categories.category_name FROM products JOIN categories ON products.category_id = categories.category_id ORDER BY products.product_name;"},
    {"category": "two-table", "question": "Show products with supplier names", "gold_sql": "SELECT products.product_name, suppliers.company_name AS supplier_name FROM products JOIN suppliers ON products.supplier_id = suppliers.supplier_id ORDER BY products.product_name;"},
    {"category": "two-table", "question": "Show orders with shipper names", "gold_sql": "SELECT orders.order_id, shippers.company_name AS shipper_name, orders.freight FROM orders JOIN shippers ON orders.ship_via = shippers.shipper_id ORDER BY orders.order_id;"},
    {"category": "two-table", "question": "Count orders by customer", "gold_sql": "SELECT customers.company_name, COUNT(orders.order_id) AS order_count FROM customers JOIN orders ON customers.customer_id = orders.customer_id GROUP BY customers.company_name ORDER BY order_count DESC;"},
    {"category": "two-table", "question": "Count products by category", "gold_sql": "SELECT categories.category_name, COUNT(products.product_id) AS product_count FROM categories JOIN products ON categories.category_id = products.category_id GROUP BY categories.category_name ORDER BY product_count DESC;"},
    {"category": "two-table", "question": "Average freight by shipper", "gold_sql": "SELECT shippers.company_name, AVG(orders.freight) AS average_freight FROM shippers JOIN orders ON shippers.shipper_id = orders.ship_via GROUP BY shippers.company_name ORDER BY average_freight DESC;"},
    {"category": "two-table", "question": "Suppliers and number of products", "gold_sql": "SELECT suppliers.company_name, COUNT(products.product_id) AS product_count FROM suppliers JOIN products ON suppliers.supplier_id = products.supplier_id GROUP BY suppliers.company_name ORDER BY product_count DESC;"},
    {"category": "two-table", "question": "Employees and their order counts", "gold_sql": "SELECT employees.employee_id, employees.first_name, employees.last_name, COUNT(orders.order_id) AS order_count FROM employees JOIN orders ON employees.employee_id = orders.employee_id GROUP BY employees.employee_id, employees.first_name, employees.last_name ORDER BY order_count DESC;"},
    {"category": "two-table", "question": "Customers and their latest order date", "gold_sql": "SELECT customers.company_name, MAX(orders.order_date) AS latest_order_date FROM customers JOIN orders ON customers.customer_id = orders.customer_id GROUP BY customers.company_name ORDER BY latest_order_date DESC;"},
]

_MULTI = [
    ("Top customers by revenue", "SELECT customers.customer_id, customers.company_name, SUM(order_details.unit_price * order_details.quantity * (1 - order_details.discount)) AS total_revenue FROM customers JOIN orders ON customers.customer_id = orders.customer_id JOIN order_details ON orders.order_id = order_details.order_id GROUP BY customers.customer_id, customers.company_name ORDER BY total_revenue DESC LIMIT 10;"),
    ("Best products by revenue", "SELECT products.product_id, products.product_name, SUM(order_details.unit_price * order_details.quantity * (1 - order_details.discount)) AS total_revenue FROM products JOIN order_details ON products.product_id = order_details.product_id GROUP BY products.product_id, products.product_name ORDER BY total_revenue DESC LIMIT 10;"),
    ("Sales by category", "SELECT categories.category_name, SUM(order_details.unit_price * order_details.quantity * (1 - order_details.discount)) AS total_revenue FROM categories JOIN products ON categories.category_id = products.category_id JOIN order_details ON products.product_id = order_details.product_id GROUP BY categories.category_name ORDER BY total_revenue DESC;"),
    ("Employees by revenue", "SELECT employees.employee_id, employees.first_name, employees.last_name, SUM(order_details.unit_price * order_details.quantity * (1 - order_details.discount)) AS total_revenue FROM employees JOIN orders ON employees.employee_id = orders.employee_id JOIN order_details ON orders.order_id = order_details.order_id GROUP BY employees.employee_id, employees.first_name, employees.last_name ORDER BY total_revenue DESC;"),
    ("Revenue by supplier", "SELECT suppliers.company_name, SUM(order_details.unit_price * order_details.quantity * (1 - order_details.discount)) AS total_revenue FROM suppliers JOIN products ON suppliers.supplier_id = products.supplier_id JOIN order_details ON products.product_id = order_details.product_id GROUP BY suppliers.company_name ORDER BY total_revenue DESC;"),
    ("Order details with customer and product", "SELECT orders.order_id, customers.company_name, products.product_name, order_details.quantity FROM orders JOIN customers ON orders.customer_id = customers.customer_id JOIN order_details ON orders.order_id = order_details.order_id JOIN products ON order_details.product_id = products.product_id ORDER BY orders.order_id LIMIT 100;"),
    ("Freight by customer country", "SELECT customers.country, SUM(orders.freight) AS total_freight FROM customers JOIN orders ON customers.customer_id = orders.customer_id GROUP BY customers.country ORDER BY total_freight DESC;"),
    ("Revenue by product category and supplier country", "SELECT categories.category_name, suppliers.country, SUM(order_details.unit_price * order_details.quantity * (1 - order_details.discount)) AS total_revenue FROM categories JOIN products ON categories.category_id = products.category_id JOIN suppliers ON products.supplier_id = suppliers.supplier_id JOIN order_details ON products.product_id = order_details.product_id GROUP BY categories.category_name, suppliers.country ORDER BY total_revenue DESC;"),
    ("Customers buying beverages", "SELECT DISTINCT customers.customer_id, customers.company_name FROM customers JOIN orders ON customers.customer_id = orders.customer_id JOIN order_details ON orders.order_id = order_details.order_id JOIN products ON order_details.product_id = products.product_id JOIN categories ON products.category_id = categories.category_id WHERE categories.category_name = 'Beverages' ORDER BY customers.company_name;"),
    ("Products sold by each employee", "SELECT employees.employee_id, employees.last_name, products.product_name, SUM(order_details.quantity) AS total_quantity FROM employees JOIN orders ON employees.employee_id = orders.employee_id JOIN order_details ON orders.order_id = order_details.order_id JOIN products ON order_details.product_id = products.product_id GROUP BY employees.employee_id, employees.last_name, products.product_name ORDER BY total_quantity DESC;"),
]

_AGG = [
    ("Total revenue", "SELECT SUM(order_details.unit_price * order_details.quantity * (1 - order_details.discount)) AS total_revenue FROM order_details;"),
    ("Total orders", "SELECT COUNT(*) AS order_count FROM orders;"),
    ("Average product price", "SELECT AVG(products.unit_price) AS average_unit_price FROM products;"),
    ("Total inventory", "SELECT SUM(products.units_in_stock) AS total_units_in_stock FROM products;"),
    ("Maximum freight", "SELECT MAX(orders.freight) AS max_freight FROM orders;"),
    ("Minimum product price", "SELECT MIN(products.unit_price) AS min_unit_price FROM products;"),
    ("Average discount", "SELECT AVG(order_details.discount) AS average_discount FROM order_details;"),
    ("Total quantity sold", "SELECT SUM(order_details.quantity) AS total_quantity FROM order_details;"),
    ("Number of countries with customers", "SELECT COUNT(DISTINCT customers.country) AS country_count FROM customers;"),
    ("Number of active products", "SELECT COUNT(*) AS active_product_count FROM products WHERE products.discontinued = 0;"),
]

_HAVING = [
    ("Customers with more than ten orders", "SELECT customers.customer_id, customers.company_name, COUNT(orders.order_id) AS order_count FROM customers JOIN orders ON customers.customer_id = orders.customer_id GROUP BY customers.customer_id, customers.company_name HAVING COUNT(orders.order_id) > 10 ORDER BY order_count DESC;"),
    ("Categories with more than ten products", "SELECT categories.category_name, COUNT(products.product_id) AS product_count FROM categories JOIN products ON categories.category_id = products.category_id GROUP BY categories.category_name HAVING COUNT(products.product_id) > 10 ORDER BY product_count DESC;"),
    ("Products with quantity sold over 100", "SELECT products.product_name, SUM(order_details.quantity) AS total_quantity FROM products JOIN order_details ON products.product_id = order_details.product_id GROUP BY products.product_name HAVING SUM(order_details.quantity) > 100 ORDER BY total_quantity DESC;"),
    ("Countries with more than five customers", "SELECT customers.country, COUNT(customers.customer_id) AS customer_count FROM customers GROUP BY customers.country HAVING COUNT(customers.customer_id) > 5 ORDER BY customer_count DESC;"),
    ("Shippers with average freight over 50", "SELECT shippers.company_name, AVG(orders.freight) AS average_freight FROM shippers JOIN orders ON shippers.shipper_id = orders.ship_via GROUP BY shippers.company_name HAVING AVG(orders.freight) > 50 ORDER BY average_freight DESC;"),
]

_TIME = [
    ("Orders by year", "SELECT EXTRACT(YEAR FROM orders.order_date) AS order_year, COUNT(*) AS order_count FROM orders GROUP BY EXTRACT(YEAR FROM orders.order_date) ORDER BY order_year;"),
    ("Monthly revenue", "SELECT DATE_TRUNC('month', orders.order_date) AS month, SUM(order_details.unit_price * order_details.quantity * (1 - order_details.discount)) AS total_revenue FROM orders JOIN order_details ON orders.order_id = order_details.order_id GROUP BY DATE_TRUNC('month', orders.order_date) ORDER BY month;"),
    ("Orders shipped late", "SELECT orders.order_id, orders.order_date, orders.required_date, orders.shipped_date FROM orders WHERE orders.shipped_date > orders.required_date ORDER BY orders.shipped_date DESC;"),
    ("Recent orders in last 30 days", "SELECT orders.order_id, orders.customer_id, orders.order_date FROM orders WHERE orders.order_date >= CURRENT_DATE - INTERVAL '30 days' ORDER BY orders.order_date DESC;"),
    ("Revenue by quarter", "SELECT EXTRACT(YEAR FROM orders.order_date) AS order_year, EXTRACT(QUARTER FROM orders.order_date) AS order_quarter, SUM(order_details.unit_price * order_details.quantity * (1 - order_details.discount)) AS total_revenue FROM orders JOIN order_details ON orders.order_id = order_details.order_id GROUP BY EXTRACT(YEAR FROM orders.order_date), EXTRACT(QUARTER FROM orders.order_date) ORDER BY order_year, order_quarter;"),
]

GOLDEN_QUESTIONS: list[dict[str, object]] = []
for idx, row in enumerate(_BASE, start=1):
    GOLDEN_QUESTIONS.append({"id": f"q{idx:03d}", "time_sensitive": False, **row})
for collection, category in ((_MULTI, "multi-table"), (_AGG, "aggregation"), (_HAVING, "group-by-having"), (_TIME, "time-based")):
    for question, gold_sql in collection:
        idx = len(GOLDEN_QUESTIONS) + 1
        GOLDEN_QUESTIONS.append({
            "id": f"q{idx:03d}",
            "category": category,
            "question": question,
            "gold_sql": gold_sql,
            "time_sensitive": category == "time-based",
        })
