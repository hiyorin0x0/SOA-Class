from __future__ import annotations

from flask import Blueprint, jsonify, request

from auth import auth_required
from database import get_db, get_order_row, recalculate_order_total
from product_client import (
    ProductNotFoundError,
    ProductUnauthorizedError,
    ProductUnavailableError,
    build_order_item,
)
from serializers import order_to_json
from validators import ValidationError, validate_order, validate_status

orders_bp = Blueprint("orders", __name__)


@orders_bp.get("/orders")
@auth_required
def list_orders():
    rows = get_db().execute("SELECT * FROM orders ORDER BY id").fetchall()
    return jsonify([order_to_json(row) for row in rows])


@orders_bp.get("/orders/<int:order_id>")
@auth_required
def get_order(order_id: int):
    row = get_order_row(order_id)
    if row is None:
        return jsonify({"message": "Order not found"}), 404
    return jsonify(order_to_json(row))


@orders_bp.post("/orders")
@auth_required
def create_order():
    try:
        order = validate_order(request.get_json(silent=True))
    except ValidationError as error:
        return jsonify({"message": str(error)}), 400

    authorization = request.headers.get("Authorization", "")
    connection = get_db()
    try:
        items = [build_order_item(item, authorization) for item in order["items"]]
    except ValidationError as error:
        return jsonify({"message": str(error)}), 400
    except ProductNotFoundError as error:
        return jsonify({"message": str(error)}), 404
    except ProductUnauthorizedError as error:
        return jsonify({"message": str(error)}), 401
    except ProductUnavailableError as error:
        return jsonify({"message": str(error)}), 503

    cursor = connection.execute(
        "INSERT INTO orders (customer_name, customer_email) VALUES (?, ?)",
        (order["customer_name"], order["customer_email"]),
    )
    order_id = cursor.lastrowid
    for item in items:
        connection.execute(
            """
            INSERT INTO order_items (order_id, product_id, product_name, quantity, unit_price, total_price)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                item["product_id"],
                item["product_name"],
                item["quantity"],
                item["unit_price"],
                item["total_price"],
            ),
        )
    recalculate_order_total(order_id)
    connection.commit()
    row = get_order_row(order_id)
    response = jsonify(order_to_json(row))
    response.status_code = 201
    response.headers["Location"] = f"/orders/{order_id}"
    return response


@orders_bp.put("/orders/<int:order_id>")
@auth_required
def update_order(order_id: int):
    if get_order_row(order_id) is None:
        return jsonify({"message": "Order not found"}), 404

    try:
        status = validate_status(request.get_json(silent=True))
    except ValidationError as error:
        return jsonify({"message": str(error)}), 400

    connection = get_db()
    connection.execute(
        "UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, order_id),
    )
    connection.commit()
    return jsonify(order_to_json(get_order_row(order_id)))


@orders_bp.delete("/orders/<int:order_id>")
@auth_required
def delete_order(order_id: int):
    connection = get_db()
    connection.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
    cursor = connection.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    connection.commit()
    if cursor.rowcount == 0:
        return jsonify({"message": "Order not found"}), 404
    return jsonify({"message": "Order deleted"})
