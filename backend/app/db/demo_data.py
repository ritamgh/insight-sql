"""In-memory Northwind-like dataset using pandas DataFrames."""
from __future__ import annotations
import pandas as pd


def load_demo_tables() -> dict[str, pd.DataFrame]:
    customers = pd.DataFrame([
        {"customer_id": "ALFKI", "company_name": "Alfreds Futterkiste",           "contact_name": "Maria Anders",     "city": "Berlin",    "country": "Germany"},
        {"customer_id": "ANATR", "company_name": "Ana Trujillo Emparedados",       "contact_name": "Ana Trujillo",      "city": "Mexico D.F.", "country": "Mexico"},
        {"customer_id": "AROUT", "company_name": "Around the Horn",                "contact_name": "Thomas Hardy",      "city": "London",    "country": "UK"},
        {"customer_id": "BERGS", "company_name": "Berglunds snabbkop",             "contact_name": "Christina Berglund","city": "Lulea",     "country": "Sweden"},
        {"customer_id": "BONAP", "company_name": "Bon app",                        "contact_name": "Laurence Lebihan",  "city": "Marseille", "country": "France"},
        {"customer_id": "ERNSH", "company_name": "Ernst Handel",                   "contact_name": "Roland Mendel",     "city": "Graz",      "country": "Austria"},
    ])

    employees = pd.DataFrame([
        {"employee_id": 1, "first_name": "Nancy",    "last_name": "Davolio",  "title": "Sales Representative", "country": "USA"},
        {"employee_id": 2, "first_name": "Andrew",   "last_name": "Fuller",   "title": "Vice President Sales", "country": "USA"},
        {"employee_id": 3, "first_name": "Janet",    "last_name": "Leverling","title": "Sales Representative", "country": "USA"},
        {"employee_id": 4, "first_name": "Margaret", "last_name": "Peacock",  "title": "Sales Representative", "country": "USA"},
    ])

    shippers = pd.DataFrame([
        {"shipper_id": 1, "company_name": "Speedy Express"},
        {"shipper_id": 2, "company_name": "United Package"},
        {"shipper_id": 3, "company_name": "Federal Shipping"},
    ])

    categories = pd.DataFrame([
        {"category_id": 1, "category_name": "Beverages",   "description": "Soft drinks, coffees, teas, beers"},
        {"category_id": 2, "category_name": "Condiments",  "description": "Sweet and savory sauces, relishes"},
        {"category_id": 3, "category_name": "Confections", "description": "Desserts, candies, and sweet breads"},
    ])

    suppliers = pd.DataFrame([
        {"supplier_id": 1, "company_name": "Exotic Liquids",                  "city": "London",      "country": "UK"},
        {"supplier_id": 2, "company_name": "New Orleans Cajun Delights",       "city": "New Orleans", "country": "USA"},
        {"supplier_id": 3, "company_name": "Grandma Kellys Homestead",         "city": "Ann Arbor",   "country": "USA"},
    ])

    products = pd.DataFrame([
        {"product_id": 1, "product_name": "Chai",                          "supplier_id": 1, "category_id": 1, "unit_price": 18.0,  "units_in_stock": 39,  "discontinued": False},
        {"product_id": 2, "product_name": "Chang",                         "supplier_id": 1, "category_id": 1, "unit_price": 19.0,  "units_in_stock": 17,  "discontinued": False},
        {"product_id": 3, "product_name": "Aniseed Syrup",                 "supplier_id": 1, "category_id": 2, "unit_price": 10.0,  "units_in_stock": 13,  "discontinued": False},
        {"product_id": 4, "product_name": "Chef Anton Cajun Seasoning",    "supplier_id": 2, "category_id": 2, "unit_price": 22.0,  "units_in_stock": 53,  "discontinued": False},
        {"product_id": 5, "product_name": "Grandmas Boysenberry Spread",   "supplier_id": 3, "category_id": 2, "unit_price": 25.0,  "units_in_stock": 120, "discontinued": False},
        {"product_id": 6, "product_name": "Chocolate Biscuits Mix",        "supplier_id": 3, "category_id": 3, "unit_price": 9.2,   "units_in_stock": 30,  "discontinued": False},
    ])

    orders = pd.DataFrame([
        {"order_id": 10248, "customer_id": "ALFKI", "employee_id": 1, "order_date": pd.Timestamp("1998-04-01"), "shipped_date": pd.Timestamp("1998-04-05"), "ship_via": 3, "freight": 32.38},
        {"order_id": 10249, "customer_id": "ANATR", "employee_id": 2, "order_date": pd.Timestamp("1998-04-03"), "shipped_date": pd.Timestamp("1998-04-10"), "ship_via": 1, "freight": 11.61},
        {"order_id": 10250, "customer_id": "AROUT", "employee_id": 3, "order_date": pd.Timestamp("1998-04-08"), "shipped_date": pd.Timestamp("1998-04-12"), "ship_via": 2, "freight": 65.83},
        {"order_id": 10251, "customer_id": "BERGS", "employee_id": 3, "order_date": pd.Timestamp("1998-04-15"), "shipped_date": pd.Timestamp("1998-04-20"), "ship_via": 1, "freight": 41.34},
        {"order_id": 10252, "customer_id": "BONAP", "employee_id": 4, "order_date": pd.Timestamp("1998-04-20"), "shipped_date": pd.Timestamp("1998-04-25"), "ship_via": 2, "freight": 51.30},
        {"order_id": 10253, "customer_id": "ERNSH", "employee_id": 1, "order_date": pd.Timestamp("1998-05-01"), "shipped_date": pd.Timestamp("1998-05-08"), "ship_via": 3, "freight": 58.17},
        {"order_id": 10254, "customer_id": "ERNSH", "employee_id": 4, "order_date": pd.Timestamp("1998-05-04"), "shipped_date": pd.Timestamp("1998-05-12"), "ship_via": 2, "freight": 22.98},
        {"order_id": 10255, "customer_id": "ALFKI", "employee_id": 2, "order_date": pd.Timestamp("1998-05-06"), "shipped_date": pd.Timestamp("1998-05-10"), "ship_via": 1, "freight": 148.33},
    ])

    order_details = pd.DataFrame([
        {"order_id": 10248, "product_id": 1, "unit_price": 14.0,  "quantity": 12, "discount": 0.0},
        {"order_id": 10248, "product_id": 2, "unit_price": 9.8,   "quantity": 10, "discount": 0.0},
        {"order_id": 10249, "product_id": 3, "unit_price": 9.8,   "quantity": 5,  "discount": 0.0},
        {"order_id": 10250, "product_id": 4, "unit_price": 21.35, "quantity": 10, "discount": 0.0},
        {"order_id": 10250, "product_id": 5, "unit_price": 7.7,   "quantity": 35, "discount": 0.25},
        {"order_id": 10251, "product_id": 6, "unit_price": 16.8,  "quantity": 6,  "discount": 0.05},
        {"order_id": 10252, "product_id": 1, "unit_price": 14.0,  "quantity": 40, "discount": 0.05},
        {"order_id": 10253, "product_id": 2, "unit_price": 9.8,   "quantity": 25, "discount": 0.0},
        {"order_id": 10254, "product_id": 3, "unit_price": 9.8,   "quantity": 20, "discount": 0.0},
        {"order_id": 10255, "product_id": 5, "unit_price": 7.7,   "quantity": 15, "discount": 0.1},
    ])

    return {
        "customers": customers,
        "employees": employees,
        "shippers": shippers,
        "categories": categories,
        "suppliers": suppliers,
        "products": products,
        "orders": orders,
        "order_details": order_details,
    }
