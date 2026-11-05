from __future__ import annotations

from decimal import Decimal

from flask import Blueprint, jsonify, request

from auth import auth_required
from database import get_db, get_item_row, get_order_item_rows, get_order_row, recalculate_order_total
from product_client import (
    ProductNotFoundError,
    ProductUnauthorizedError,
    ProductUnavailableError,
    ensure_stock,
    fetch_product,
    product_price,
)
from serializers import item_to_json
from validators import ValidationError, validate_order_item

order_items_bp = Blueprint("order_items", __name__)


@order_items_bp.get("/order_items")
@auth_required
def list_order_items():
    order_id = request.args.get("order_id", type=int)
    if order_id is not None:
        if get_order_row(order_id) is None:
            return jsonify({"message": "Order not found"}), 404
        return jsonify([item_to_json(row) for row in get_order_item_rows(order_id)])
    rows = get_db().execute("SELECT * FROM order_items ORDER BY id").fetchall()
    return jsonify([item_to_json(row) for row in rows])


@order_items_bp.get("/order_items/<int:item_id>")
@auth_required
def get_order_item(item_id: int):
    row = get_item_row(item_id)
    if row is None:
        return jsonify({"message": "Order item not found"}), 404
    return jsonify(item_to_json(row))


@order_items_bp.post("/order_items")
@auth_required
def create_order_item():
    try:
        item = validate_order_item(request.get_json(silent=True))
    except ValidationError as error:
        return jsonify({"message": str(error)}), 400

    if get_order_row(item["order_id"]) is None:
        return jsonify({"message": "Order not found"}), 404

    authorization = request.headers.get("Authorization", "")
    try:
        product = fetch_product(item["product_id"], authorization)
        ensure_stock(product, item["quantity"])
    except ProductNotFoundError as error:
        return jsonify({"message": str(error)}), 404
    except ProductUnauthorizedError as error:
        return jsonify({"message": str(error)}), 401
    except ProductUnavailableError as error:
        return jsonify({"message": str(error)}), 503
    except ValidationError as error:
        return jsonify({"message": str(error)}), 400

    unit_price = product_price(product)
    total_price = (unit_price * Decimal(item["quantity"])).quantize(Decimal("0.01"))

    connection = get_db()
    cursor = connection.execute(
        """
        INSERT INTO order_items (order_id, product_id, product_name, quantity, unit_price, total_price)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            item["order_id"],
            item["product_id"],
            str(product.get("name", "")).strip() or f"Product {item['product_id']}",
            item["quantity"],
            format(unit_price, ".2f"),
            format(total_price, ".2f"),
        ),
    )
    recalculate_order_total(item["order_id"])
    connection.commit()
    row = get_item_row(cursor.lastrowid)
    response = jsonify(item_to_json(row))
    response.status_code = 201
    response.headers["Location"] = f"/order_items/{cursor.lastrowid}"
    return response


@order_items_bp.put("/order_items/<int:item_id>")
@auth_required
def update_order_item(item_id: int):
    row = get_item_row(item_id)
    if row is None:
        return jsonify({"message": "Order item not found"}), 404

    try:
        item = validate_order_item(request.get_json(silent=True), partial=True)
    except ValidationError as error:
        return jsonify({"message": str(error)}), 400

    authorization = request.headers.get("Authorization", "")
    product_id = item.get("product_id", row["product_id"])
    quantity = item.get("quantity", row["quantity"])

    connection = get_db()
    try:
        if "product_id" in item or "quantity" in item:
            product = fetch_product(product_id, authorization)
            ensure_stock(product, quantity)
    except ProductNotFoundError as error:
        return jsonify({"message": str(error)}), 404
    except ProductUnauthorizedError as error:
        return jsonify({"message": str(error)}), 401
    except ProductUnavailableError as error:
        return jsonify({"message": str(error)}), 503
    except ValidationError as error:
        return jsonify({"message": str(error)}), 400

    if "product_id" in item:
        unit_price = product_price(product)
        connection.execute(
            """
            UPDATE order_items
            SET product_id = ?, product_name = ?, unit_price = ?
            WHERE id = ?
            """,
            (
                product_id,
                str(product.get("name", "")).strip() or f"Product {product_id}",
                format(unit_price, ".2f"),
                item_id,
            ),
        )
    if "quantity" in item:
        connection.execute("UPDATE order_items SET quantity = ? WHERE id = ?", (quantity, item_id))

    current = get_item_row(item_id)
    total_price = (Decimal(str(current["unit_price"])) * Decimal(current["quantity"])).quantize(Decimal("0.01"))
    connection.execute("UPDATE order_items SET total_price = ? WHERE id = ?", (format(total_price, ".2f"), item_id))
    recalculate_order_total(current["order_id"])
    connection.commit()
    return jsonify(item_to_json(get_item_row(item_id)))


@order_items_bp.delete("/order_items/<int:item_id>")
@auth_required
def delete_order_item(item_id: int):
    row = get_item_row(item_id)
    if row is None:
        return jsonify({"message": "Order item not found"}), 404

    connection = get_db()
    connection.execute("DELETE FROM order_items WHERE id = ?", (item_id,))
    recalculate_order_total(row["order_id"])
    connection.commit()
    return jsonify({"message": "Order item deleted"})
