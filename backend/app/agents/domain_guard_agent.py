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
