from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("PRODUCT_DB_PATH", str(BASE_DIR / "instance" / "products.db"))).expanduser()
AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://127.0.0.1:5000/auth")
AUTH_TIMEOUT_SECONDS = float(os.environ.get("AUTH_TIMEOUT_SECONDS", "3"))
app = Flask(__name__)


class ValidationError(ValueError):
    pass


def initialize_database() -> None:
    """Create the product database and schema if they do not exist yet."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                price DECIMAL(10, 2) NOT NULL CHECK (price >= 0),
                quantity INTEGER NOT NULL CHECK (quantity >= 0),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
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
        g.db = connection
    return g.db


@app.teardown_appcontext
def close_db(error: BaseException | None = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        if error is not None:
            connection.rollback()
        connection.close()


def auth_required(handler: Callable[..., Any]) -> Callable[..., Any]:
    """Delegate bearer-token validation to the authentication service from TH2."""
    @wraps(handler)
    def wrapped(*args: Any, **kwargs: Any):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer ") or not authorization[7:].strip():
            return jsonify({"message": "Bearer token is required"}), 401

        auth_request = urllib.request.Request(
            AUTH_SERVICE_URL,
            headers={"Authorization": authorization, "Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(auth_request, timeout=AUTH_TIMEOUT_SECONDS) as response:
                status_code = response.status
                body = response.read()
        except urllib.error.HTTPError as error:
            status_code = error.code
            body = error.read()
        except (urllib.error.URLError, TimeoutError, OSError):
            app.logger.warning("Authentication service is unavailable at %s", AUTH_SERVICE_URL)
            return jsonify({"message": "Authentication service is unavailable"}), 503

        try:
            auth_payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            auth_payload = {}

        if status_code == 401:
            message = auth_payload.get("message", "Invalid or expired token") if isinstance(auth_payload, dict) else "Invalid or expired token"
            return jsonify({"message": message}), 401
        if status_code < 200 or status_code >= 300:
            app.logger.warning("Authentication service returned HTTP %s", status_code)
            return jsonify({"message": "Authentication service is unavailable"}), 503
        if not isinstance(auth_payload, dict) or not isinstance(auth_payload.get("user"), dict):
            app.logger.warning("Authentication service returned an unexpected response")
            return jsonify({"message": "Authentication service returned an invalid response"}), 503

        g.current_user = auth_payload["user"]
        return handler(*args, **kwargs)

    return wrapped


def validate_product(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object")

    allowed_fields = {"name", "description", "price", "quantity"}
    unknown_fields = set(payload) - allowed_fields
    if unknown_fields:
        raise ValidationError(f"Unknown field(s): {', '.join(sorted(unknown_fields))}")

    required_fields = {"name", "price", "quantity"}
    missing_fields = required_fields - set(payload)
    if missing_fields:
        raise ValidationError(f"Missing required field(s): {', '.join(sorted(missing_fields))}")

    name = payload["name"]
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("name must be a non-empty string")
    name = name.strip()
    if len(name) > 255:
        raise ValidationError("name must be at most 255 characters")

    description = payload.get("description", "")
    if not isinstance(description, str):
        raise ValidationError("description must be a string")

    raw_price = payload["price"]
    if isinstance(raw_price, bool) or not isinstance(raw_price, (int, float, str)):
        raise ValidationError("price must be a number with at most 2 decimal places")
    try:
        price = Decimal(str(raw_price))
        if not price.is_finite():
            raise ValidationError("price must be a finite number")
        rounded_price = price.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ValidationError("price must be a valid number with at most 2 decimal places") from None
    if price < 0 or price >= Decimal("100000000") or rounded_price != price:
        raise ValidationError("price must be between 0 and 99,999,999.99 with at most 2 decimal places")

    quantity = payload["quantity"]
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
        raise ValidationError("quantity must be a non-negative integer")

    return {
        "name": name,
        "description": description,
        "price": format(rounded_price, ".2f"),
        "quantity": quantity,
    }


def product_to_json(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "price": float(Decimal(str(row["price"])).quantize(Decimal("0.01"))),
        "quantity": row["quantity"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_product_row(product_id: int) -> sqlite3.Row | None:
    return get_db().execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "product-service"})


@app.get("/products")
@auth_required
def list_products():
    rows = get_db().execute("SELECT * FROM products ORDER BY id").fetchall()
    return jsonify([product_to_json(row) for row in rows])


@app.get("/products/<int:product_id>")
@auth_required
def get_product(product_id: int):
    row = get_product_row(product_id)
    if row is None:
        return jsonify({"message": "Product not found"}), 404
    return jsonify(product_to_json(row))


@app.post("/products")
@auth_required
def create_product():
    try:
        product = validate_product(request.get_json(silent=True))
    except ValidationError as error:
        return jsonify({"message": str(error)}), 400

    connection = get_db()
    cursor = connection.execute(
        "INSERT INTO products (name, description, price, quantity) VALUES (?, ?, ?, ?)",
        (product["name"], product["description"], product["price"], product["quantity"]),
    )
    connection.commit()
    row = get_product_row(cursor.lastrowid)
    response = jsonify(product_to_json(row))
    response.status_code = 201
    response.headers["Location"] = f"/products/{cursor.lastrowid}"
    return response


@app.put("/products/<int:product_id>")
@auth_required
def update_product(product_id: int):
    if get_product_row(product_id) is None:
        return jsonify({"message": "Product not found"}), 404

    try:
        product = validate_product(request.get_json(silent=True))
    except ValidationError as error:
        return jsonify({"message": str(error)}), 400

    connection = get_db()
    connection.execute(
        """
        UPDATE products
        SET name = ?, description = ?, price = ?, quantity = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (product["name"], product["description"], product["price"], product["quantity"], product_id),
    )
    connection.commit()
    return jsonify(product_to_json(get_product_row(product_id)))


@app.delete("/products/<int:product_id>")
@auth_required
def delete_product(product_id: int):
    connection = get_db()
    cursor = connection.execute("DELETE FROM products WHERE id = ?", (product_id,))
    connection.commit()
    if cursor.rowcount == 0:
        return jsonify({"message": "Product not found"}), 404
    return jsonify({"message": "Product deleted"})


@app.errorhandler(HTTPException)
def handle_http_error(error: HTTPException):
    return jsonify({"message": error.description}), error.code


@app.errorhandler(Exception)
def handle_unexpected_error(error: Exception):
    app.logger.exception("Unhandled product-service error")
    return jsonify({"message": "Internal server error"}), 500


initialize_database()


if __name__ == "__main__":
    host = os.environ.get("PRODUCT_HOST", "127.0.0.1")
    port = int(os.environ.get("PRODUCT_PORT", "5001"))
    app.run(host=host, port=port, debug=False)