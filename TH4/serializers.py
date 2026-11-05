from __future__ import annotations

import sqlite3
from decimal import Decimal
from typing import Any

from database import get_order_item_rows


def item_to_json(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "order_id": row["order_id"],
        "product_id": row["product_id"],
        "product_name": row["product_name"],
        "quantity": row["quantity"],
        "unit_price": float(Decimal(str(row["unit_price"])).quantize(Decimal("0.01"))),
        "total_price": float(Decimal(str(row["total_price"])).quantize(Decimal("0.01"))),
    }


def order_to_json(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "customer_name": row["customer_name"],
        "customer_email": row["customer_email"],
        "total_amount": float(Decimal(str(row["total_amount"])).quantize(Decimal("0.01"))),
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "items": [item_to_json(item_row) for item_row in get_order_item_rows(row["id"])],
    }
