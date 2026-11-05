from __future__ import annotations

import json
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Any

from flask import current_app

from config import PRODUCT_SERVICE_URL, PRODUCT_TIMEOUT_SECONDS
from validators import ValidationError


class ProductLookupError(Exception):
    """Raised when the product service cannot fulfill a product lookup."""


class ProductNotFoundError(ProductLookupError):
    pass


class ProductUnauthorizedError(ProductLookupError):
    pass


class ProductUnavailableError(ProductLookupError):
    pass


def fetch_product(product_id: int, authorization: str) -> dict[str, Any]:
    """Look up one product via the product management service from TH3."""
    product_request = urllib.request.Request(
        f"{PRODUCT_SERVICE_URL}/{product_id}",
        headers={"Authorization": authorization, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(product_request, timeout=PRODUCT_TIMEOUT_SECONDS) as response:
            status_code = response.status
            body = response.read()
    except urllib.error.HTTPError as error:
        status_code = error.code
        body = error.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        current_app.logger.warning("Product service is unavailable at %s", PRODUCT_SERVICE_URL)
        raise ProductUnavailableError("Product service is unavailable") from None

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {}

    if status_code == 404:
        raise ProductNotFoundError(f"Product {product_id} does not exist in the product service")
    if status_code in (401, 403):
        raise ProductUnauthorizedError("Product service rejected the access token")
    if status_code < 200 or status_code >= 300:
        current_app.logger.warning("Product service returned HTTP %s", status_code)
        raise ProductUnavailableError("Product service is unavailable")
    if not isinstance(payload, dict) or "id" not in payload:
        current_app.logger.warning("Product service returned an unexpected response")
        raise ProductUnavailableError("Product service returned an invalid response")
    return payload


def ensure_stock(product: dict[str, Any], quantity: int) -> None:
    """Verify the product service still has enough of this product in stock."""
    available = product.get("quantity")
    if isinstance(available, bool) or not isinstance(available, int):
        current_app.logger.warning("Product service returned an invalid quantity for product %s", product.get("id"))
        raise ProductUnavailableError("Product service returned an invalid quantity")
    if available < quantity:
        raise ValidationError(
            f"Insufficient stock for product '{product.get('name', product.get('id'))}': "
            f"requested {quantity}, available {available}"
        )


def product_price(product: dict[str, Any]) -> Decimal:
    raw_price = product.get("price")
    if isinstance(raw_price, bool) or not isinstance(raw_price, (int, float, str)):
        current_app.logger.warning("Product service returned an invalid price for product %s", product.get("id"))
        raise ProductUnavailableError("Product service returned an invalid price")
    try:
        price = Decimal(str(raw_price))
        rounded_price = price.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        current_app.logger.warning("Product service returned an invalid price for product %s", product.get("id"))
        raise ProductUnavailableError("Product service returned an invalid price") from None
    if not price.is_finite() or price < 0 or rounded_price != price:
        current_app.logger.warning("Product service returned an invalid price for product %s", product.get("id"))
        raise ProductUnavailableError("Product service returned an invalid price")
    return rounded_price


def build_order_item(item: dict[str, int], authorization: str) -> dict[str, Any]:
    """Check stock on the product service and build one order_item row payload."""
    product = fetch_product(item["product_id"], authorization)
    ensure_stock(product, item["quantity"])
    unit_price = product_price(product)
    quantity = Decimal(item["quantity"])
    return {
        "product_id": item["product_id"],
        "product_name": str(product.get("name", "")).strip() or f"Product {item['product_id']}",
        "quantity": item["quantity"],
        "unit_price": format(unit_price, ".2f"),
        "total_price": format((unit_price * quantity).quantize(Decimal("0.01")), ".2f"),
    }
