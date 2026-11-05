from __future__ import annotations

import sqlite3
from decimal import Decimal
from typing import Any

from flask import g

from config import DB_PATH


def initialize_database() -> None:
    """Create the order database and schema if they do not exist yet."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name VARCHAR(255) NOT NULL,
                customer_email VARCHAR(255) NOT NULL,
                total_amount DECIMAL(10, 2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
                status VARCHAR(50) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'completed', 'cancelled')),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL,
                product_name VARCHAR(255) NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                unit_price DECIMAL(10, 2) NOT NULL CHECK (unit_price >= 0),
                total_price DECIMAL(10, 2) NOT NULL CHECK (total_price >= 0)
            )
            """
        )
        connection.commit()
    finally:
        connection.close()


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        connection = sqlite3.connect(DB_PATH, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection
    return g.db


def close_db(error: BaseException | None = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        if error is not None:
            connection.rollback()
        connection.close()


def get_order_row(order_id: int) -> sqlite3.Row | None:
    return get_db().execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()


def get_item_row(item_id: int) -> sqlite3.Row | None:
    return get_db().execute("SELECT * FROM order_items WHERE id = ?", (item_id,)).fetchone()


def get_order_item_rows(order_id: int) -> list[sqlite3.Row]:
    return get_db().execute(
        "SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,)
    ).fetchall()


def recalculate_order_total(order_id: int) -> None:
    """Recompute total_amount as the sum of its items' total_price."""
    rows = get_order_item_rows(order_id)
    total = sum((Decimal(str(row["total_price"])) for row in rows), Decimal("0"))
    get_db().execute(
        "UPDATE orders SET total_amount = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (format(total.quantize(Decimal("0.01")), ".2f"), order_id),
    )
