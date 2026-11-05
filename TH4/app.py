from __future__ import annotations

import os

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

import database
from order_items import order_items_bp
from orders import orders_bp

app = Flask(__name__)
database.initialize_database()
app.teardown_appcontext(database.close_db)
app.register_blueprint(orders_bp)
app.register_blueprint(order_items_bp)


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "order-service"})


@app.errorhandler(HTTPException)
def handle_http_error(error: HTTPException):
    return jsonify({"message": error.description}), error.code


@app.errorhandler(Exception)
def handle_unexpected_error(error: Exception):
    app.logger.exception("Unhandled order-service error")
    return jsonify({"message": "Internal server error"}), 500


if __name__ == "__main__":
    host = os.environ.get("ORDER_HOST", "127.0.0.1")
    port = int(os.environ.get("ORDER_PORT", "5002"))
    app.run(host=host, port=port, debug=False)
