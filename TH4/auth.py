from __future__ import annotations

import json
import urllib.error
import urllib.request
from functools import wraps
from typing import Any, Callable

from flask import current_app, g, jsonify, request

from config import AUTH_SERVICE_URL, AUTH_TIMEOUT_SECONDS


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
            current_app.logger.warning("Authentication service is unavailable at %s", AUTH_SERVICE_URL)
            return jsonify({"message": "Authentication service is unavailable"}), 503

        try:
            auth_payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            auth_payload = {}

        if status_code == 401:
            message = auth_payload.get("message", "Invalid or expired token") if isinstance(auth_payload, dict) else "Invalid or expired token"
            return jsonify({"message": message}), 401
        if status_code < 200 or status_code >= 300:
            current_app.logger.warning("Authentication service returned HTTP %s", status_code)
            return jsonify({"message": "Authentication service is unavailable"}), 503
        if not isinstance(auth_payload, dict) or not isinstance(auth_payload.get("user"), dict):
            current_app.logger.warning("Authentication service returned an unexpected response")
            return jsonify({"message": "Authentication service returned an invalid response"}), 503

        g.current_user = auth_payload["user"]
        return handler(*args, **kwargs)

    return wrapped
