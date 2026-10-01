from flask import Flask, request, jsonify
from functools import wraps
import jwt
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

# Khóa dùng để ký JWT
app.config["SECRET_KEY"] = "secret123"


# -------------------------
# Dữ liệu User giả lập
# -------------------------
users = [
    {
        "idUser": 1,
        "userName": "admin",

        # 123456 được encode Base64
        "password": "MTIzNDU2"
    }
]


# -------------------------
# Middleware kiểm tra JWT
# -------------------------
def token_required(f):

    @wraps(f)
    def decorated(*args, **kwargs):

        auth_header = request.headers.get("Authorization")

        # Không có Authorization header
        if not auth_header:
            return jsonify({
                "message": "Thieu token"
            }), 401

        # Header phải có dạng:
        # Bearer <token>
        if not auth_header.startswith("Bearer "):
            return jsonify({
                "message": "Token khong hop le"
            }), 401

        token = auth_header.split(" ")[1]

        try:
            data = jwt.decode(
                token,
                app.config["SECRET_KEY"],
                algorithms=["HS256"]
            )

            current_user = {
                "idUser": data["idUser"],
                "userName": data["userName"]
            }

        except jwt.ExpiredSignatureError:
            return jsonify({
                "message": "Token da het han"
            }), 401

        except jwt.InvalidTokenError:
            return jsonify({
                "message": "Token khong hop le"
            }), 401

        return f(current_user, *args, **kwargs)

    return decorated


# -------------------------
# Router: Login
# -------------------------
@app.route("/login", methods=["POST"])
def login():

    data = request.get_json()

    if not data:
        return jsonify({
            "message": "Khong co du lieu"
        }), 400

    user_name = data.get("userName")
    password = data.get("password")

    # Tim user phù hợp
    user = next(
        (
            u for u in users
            if u["userName"] == user_name
            and u["password"] == password
        ),
        None
    )

    if user is None:
        return jsonify({
            "message": "Sai tai khoan hoac mat khau"
        }), 401

    # Tạo dữ liệu nằm trong JWT
    payload = {
        "idUser": user["idUser"],
        "userName": user["userName"],

        # Token hết hạn sau 1 giờ
        "exp": datetime.now(timezone.utc) + timedelta(hours=1)
    }

    # Sinh JWT
    token = jwt.encode(
        payload,
        app.config["SECRET_KEY"],
        algorithm="HS256"
    )

    return jsonify({
        "token": token
    })


# -------------------------
# Router: kiểm tra Token
# -------------------------
@app.route("/auth", methods=["GET"])
@token_required
def auth(current_user):

    return jsonify({
        "message": "Token hop le",
        "user": current_user
    })


# -------------------------
# API Hello World bài 1
# được Middleware bảo vệ
# -------------------------
@app.route("/api/hello", methods=["GET"])
@token_required
def hello(current_user):

    return jsonify({
        "message": "Hello World"
    })


if __name__ == "__main__":
    app.run(debug=True)