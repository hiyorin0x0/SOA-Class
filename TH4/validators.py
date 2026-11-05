from __future__ import annotations

from typing import Any

from config import EMAIL_PATTERN, VALID_STATUSES


class ValidationError(ValueError):
    pass


def validate_customer_fields(payload: Any) -> tuple[str, str]:
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object")

    customer_name = payload.get("customer_name")
    if not isinstance(customer_name, str) or not customer_name.strip():
        raise ValidationError("customer_name must be a non-empty string")
    customer_name = customer_name.strip()
    if len(customer_name) > 255:
        raise ValidationError("customer_name must be at most 255 characters")

    customer_email = payload.get("customer_email")
    if not isinstance(customer_email, str) or not customer_email.strip():
        raise ValidationError("customer_email must be a non-empty string")
    customer_email = customer_email.strip()
    if len(customer_email) > 255:
        raise ValidationError("customer_email must be at most 255 characters")
    if EMAIL_PATTERN.fullmatch(customer_email) is None:
        raise ValidationError("customer_email must be a valid email address")

    return customer_name, customer_email


def validate_item_payload(item: Any) -> dict[str, int]:
    if not isinstance(item, dict):
        raise ValidationError("Each item must be a JSON object")

    allowed_fields = {"product_id", "quantity"}
    unknown_fields = set(item) - allowed_fields
    if unknown_fields:
        raise ValidationError(f"Unknown field(s) in item: {', '.join(sorted(unknown_fields))}")

    missing_fields = allowed_fields - set(item)
    if missing_fields:
        raise ValidationError(f"Missing required field(s) in item: {', '.join(sorted(missing_fields))}")

    product_id = item["product_id"]
    if isinstance(product_id, bool) or not isinstance(product_id, int) or product_id <= 0:
        raise ValidationError("product_id must be a positive integer")

    quantity = item["quantity"]
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise ValidationError("quantity must be a positive integer")

    return {"product_id": product_id, "quantity": quantity}


def validate_order(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object")

    allowed_fields = {"customer_name", "customer_email", "items"}
    unknown_fields = set(payload) - allowed_fields
    if unknown_fields:
        raise ValidationError(f"Unknown field(s): {', '.join(sorted(unknown_fields))}")

    customer_name, customer_email = validate_customer_fields(payload)

    items = payload.get("items", [])
    if not isinstance(items, list):
        raise ValidationError("items must be an array of {product_id, quantity} objects")
    validated_items = [validate_item_payload(item) for item in items]

    return {"customer_name": customer_name, "customer_email": customer_email, "items": validated_items}


def validate_status(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object")

    allowed_fields = {"status"}
    unknown_fields = set(payload) - allowed_fields
    if unknown_fields:
        raise ValidationError(f"Unknown field(s): {', '.join(sorted(unknown_fields))}")
    missing_fields = allowed_fields - set(payload)
    if missing_fields:
        raise ValidationError(f"Missing required field(s): {', '.join(sorted(missing_fields))}")

    status = payload["status"]
    if not isinstance(status, str) or status not in VALID_STATUSES:
        raise ValidationError(f"status must be one of: {', '.join(VALID_STATUSES)}")
    return status


def validate_order_item(payload: Any, partial: bool = False) -> dict[str, int]:
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object")

    allowed_fields = {"order_id", "product_id", "quantity"} if not partial else {"product_id", "quantity"}
    unknown_fields = set(payload) - allowed_fields
    if unknown_fields:
        raise ValidationError(f"Unknown field(s): {', '.join(sorted(unknown_fields))}")

    required_fields = allowed_fields if not partial else set()
    missing_fields = required_fields - set(payload)
    if missing_fields:
        raise ValidationError(f"Missing required field(s): {', '.join(sorted(missing_fields))}")

    validated: dict[str, int] = {}
    if "order_id" in payload:
        order_id = payload["order_id"]
        if isinstance(order_id, bool) or not isinstance(order_id, int) or order_id <= 0:
            raise ValidationError("order_id must be a positive integer")
        validated["order_id"] = order_id

    if "product_id" in payload:
        product_id = payload["product_id"]
        if isinstance(product_id, bool) or not isinstance(product_id, int) or product_id <= 0:
            raise ValidationError("product_id must be a positive integer")
        validated["product_id"] = product_id

    if "quantity" in payload:
        quantity = payload["quantity"]
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValidationError("quantity must be a positive integer")
        validated["quantity"] = quantity

    if partial and not validated:
        raise ValidationError("Provide at least one of: product_id, quantity")

    return validated
