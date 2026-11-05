# Order Management Service (TH4)

Dịch vụ Flask quản lý đơn hàng, chạy độc lập trên cổng `5002` và dùng cơ sở dữ liệu SQLite riêng tại `instance/orders.db` (tuân theo nguyên tắc SOA: mỗi service một cổng, một CSDL riêng). Service xác thực Bearer token bằng cách gọi `GET /auth` của dịch vụ bài thực hành số 2, và **kiểm tra tồn kho** bằng cách gọi `GET /products/<id>` của dịch vụ quản lý sản phẩm bài thực hành số 3 trước khi tạo đơn hàng hoặc thêm/cập nhật mặt hàng.

## Chạy dịch vụ

Cần chạy đủ 3 service:

1. Terminal thứ nhất tại thư mục gốc `SOA-Class` — service xác thực bài 2:

```powershell
.\.venv\Scripts\Activate.ps1
python app.py
```

2. Terminal thứ hai tại `SOA-Class\product-service` — service sản phẩm bài 3:

```powershell
..\.venv\Scripts\Activate.ps1
python app.py
```

3. Terminal thứ ba tại `SOA-Class\TH4` — service đơn hàng bài 4:

```powershell
..\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Mặc định: bài 2 tại `http://127.0.0.1:5000`, bài 3 tại `http://127.0.0.1:5001`, bài 4 tại `http://127.0.0.1:5002`. Có thể cấu hình bằng biến môi trường:

```powershell
$env:AUTH_SERVICE_URL = 'http://127.0.0.1:5000/auth'
$env:PRODUCT_SERVICE_URL = 'http://127.0.0.1:5001/products'
$env:ORDER_PORT = '5002'
$env:ORDER_DB_PATH = 'D:\data\orders.db'
python app.py
```

SQLite tự tạo bảng `orders` và `order_items` khi service khởi động. `GET /health` là endpoint kiểm tra tình trạng service và không yêu cầu token.

## Cấu trúc thư mục

```
TH4/
├── app.py               # Entry point: tạo Flask app, đăng ký blueprint và error handler
├── config.py            # Cấu hình: đường dẫn DB, URL service bài 2/bài 3, timeout
├── database.py          # Kết nối SQLite, tạo schema, các hàm truy vấn và tính lại tổng tiền
├── auth.py              # Decorator auth_required — xác thực token qua service bài 2
├── product_client.py    # Gọi product-service bài 3: tra sản phẩm, kiểm tra tồn kho
├── validators.py        # Kiểm tra dữ liệu đầu vào của các API
├── serializers.py       # Chuyển dòng DB thành JSON trả về
├── orders.py            # Blueprint các route /orders
├── order_items.py       # Blueprint các route /order_items
├── requirements.txt
└── README.md
```

Chạy dịch vụ vẫn là `python app.py` trong thư mục `TH4` như hướng dẫn ở trên.

## Lấy token

Đăng nhập vào bài 2 (tài khoản mẫu là `admin`, mật khẩu `123456` được lưu dạng Base64 là `MTIzNDU2`):

```http
POST http://127.0.0.1:5000/login
Content-Type: application/json

{"userName":"admin","password":"MTIzNDU2"}
```

Dùng giá trị `token` nhận được trong header `Authorization: Bearer <token>` cho mọi request bên dưới.

## REST API

Mọi API `/orders` và `/order_items` yêu cầu token hợp lệ.

| Method | Endpoint | Ý nghĩa |
|---|---|---|
| `GET` | `/orders` | Lấy danh sách tất cả đơn hàng |
| `GET` | `/orders/<id>` | Xem chi tiết một đơn hàng (kèm các mặt hàng) |
| `POST` | `/orders` | Tạo đơn hàng mới (kiểm tra tồn kho qua bài 3) |
| `PUT` | `/orders/<id>` | Cập nhật trạng thái đơn hàng |
| `DELETE` | `/orders/<id>` | Xóa đơn hàng (kèm toàn bộ mặt hàng) |
| `GET` | `/order_items` | Lấy danh sách mặt hàng (có thể lọc `?order_id=<id>`) |
| `GET` | `/order_items/<id>` | Xem chi tiết một mặt hàng |
| `POST` | `/order_items` | Thêm mặt hàng vào đơn hàng (kiểm tra tồn kho) |
| `PUT` | `/order_items/<id>` | Cập nhật mặt hàng (số lượng và/hoặc sản phẩm) |
| `DELETE` | `/order_items/<id>` | Xóa một mặt hàng trong đơn hàng |

Ví dụ tạo đơn hàng kèm mặt hàng:

```http
POST http://127.0.0.1:5002/orders
Authorization: Bearer <token>
Content-Type: application/json

{
  "customer_name": "Nguyen Van A",
  "customer_email": "a@example.com",
  "items": [
    {"product_id": 1, "quantity": 2},
    {"product_id": 3, "quantity": 1}
  ]
}
```

`items` là tùy chọn; có thể tạo đơn rỗng rồi thêm mặt hàng qua `POST /order_items`:

```http
POST http://127.0.0.1:5002/order_items
Authorization: Bearer <token>
Content-Type: application/json

{"order_id": 1, "product_id": 2, "quantity": 5}
```

Cập nhật trạng thái đơn hàng (`pending`, `completed`, `cancelled`):

```http
PUT http://127.0.0.1:5002/orders/1
Authorization: Bearer <token>
Content-Type: application/json

{"status": "completed"}
```

## Nghiệp vụ

- Khi tạo đơn hàng, thêm hoặc cập nhật mặt hàng, service gọi sang product-service (bài 3) để lấy thông tin sản phẩm và **kiểm tra số lượng tồn kho**; nếu tồn kho không đủ trả về `400`, sản phẩm không tồn tại trả về `404`.
- `unit_price` và `product_name` của mặt hàng được chốt theo giá trị từ product-service tại thời điểm đặt hàng.
- `total_price` của mỗi mặt hàng = `quantity * unit_price`; `total_amount` của đơn hàng luôn được tự động tính lại bằng tổng `total_price` của các mặt hàng.
- Trạng thái đơn hàng chỉ nhận `pending`, `completed`, `cancelled` (mặc định khi tạo là `pending`).
- Xóa đơn hàng sẽ xóa cả các mặt hàng thuộc đơn đó (cascade).

Lỗi: đầu vào không hợp lệ hoặc thiếu tồn kho là `400`, tài nguyên không tồn tại là `404`, token thiếu/sai/hết hạn là `401`, service bài 2 hoặc bài 3 không phản hồi là `503`.
