# Product Management Service (TH3)

Dịch vụ Flask quản lý sản phẩm, chạy độc lập trên cổng `5001` và dùng cơ sở dữ liệu SQLite riêng tại `instance/products.db`. Service xác thực Bearer token bằng cách gọi `GET /auth` của dịch vụ bài thực hành số 2 trước khi xử lý các API sản phẩm.

## Chạy dịch vụ

Mở terminal thứ nhất tại thư mục gốc `SOA-Class` và khởi động service xác thực bài 2:

```powershell
.\.venv\Scripts\Activate.ps1
python app.py
```

Mở terminal thứ hai tại `SOA-Class\product-service`:

```powershell
..\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Mặc định, bài 2 chạy tại `http://127.0.0.1:5000`, bài 3 tại `http://127.0.0.1:5001`, và bài 3 gọi `http://127.0.0.1:5000/auth` để kiểm tra token. Có thể cấu hình bằng biến môi trường:

```powershell
$env:AUTH_SERVICE_URL = 'http://127.0.0.1:5000/auth'
$env:PRODUCT_PORT = '5001'
$env:PRODUCT_DB_PATH = 'D:\data\products.db'
python app.py
```

SQLite tự tạo bảng `products` khi service khởi động. `GET /health` là endpoint kiểm tra tình trạng service và không yêu cầu token.

## Lấy token

Đăng nhập vào bài 2 (tài khoản mẫu trong `app.py` là `admin`; mật khẩu `123456` được lưu dạng Base64 là `MTIzNDU2`):

```http
POST http://127.0.0.1:5000/login
Content-Type: application/json

{"userName":"admin","password":"MTIzNDU2"}
```

Dùng giá trị `token` nhận được trong header `Authorization: Bearer <token>` cho các request bên dưới.

## REST API

Mọi API `/products` yêu cầu token hợp lệ. `PUT` nhận đầy đủ `name`, `price`, `quantity`; `description` là tùy chọn và mặc định thành chuỗi rỗng.

| Method | Endpoint | Ý nghĩa |
|---|---|---|
| `GET` | `/products` | Lấy danh sách sản phẩm |
| `GET` | `/products/<id>` | Xem chi tiết sản phẩm |
| `POST` | `/products` | Tạo sản phẩm |
| `PUT` | `/products/<id>` | Cập nhật sản phẩm |
| `DELETE` | `/products/<id>` | Xóa sản phẩm |

Ví dụ tạo sản phẩm:

```http
POST http://127.0.0.1:5001/products
Authorization: Bearer <token>
Content-Type: application/json

{"name":"Bàn phím cơ","description":"Switch red","price":1250000,"quantity":12}
```

Các trường đầu vào: `name` (bắt buộc, tối đa 255 ký tự), `description` (tùy chọn), `price` (bắt buộc, không âm, tối đa 2 chữ số thập phân) và `quantity` (bắt buộc, số nguyên không âm). Dịch vụ trả JSON; lỗi đầu vào là `400`, sản phẩm không tồn tại là `404`, token thiếu/sai/hết hạn là `401`, còn khi service bài 2 không phản hồi là `503`.