from __future__ import annotations

import os
import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("ORDER_DB_PATH", str(BASE_DIR / "instance" / "orders.db"))).expanduser()
AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://127.0.0.1:5000/auth")
PRODUCT_SERVICE_URL = os.environ.get("PRODUCT_SERVICE_URL", "http://127.0.0.1:5001/products").rstrip("/")
AUTH_TIMEOUT_SECONDS = float(os.environ.get("AUTH_TIMEOUT_SECONDS", "3"))
PRODUCT_TIMEOUT_SECONDS = float(os.environ.get("PRODUCT_TIMEOUT_SECONDS", "3"))
VALID_STATUSES = ("pending", "completed", "cancelled")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
