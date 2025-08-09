# TaskNest Backend

## 1. Giới thiệu
TaskNest Backend được xây dựng trên **Django REST Framework** kết hợp **Django Channels** và **Redis** để cung cấp API và tính năng realtime cho ứng dụng quản lý công việc dạng Trello.

Hệ thống hỗ trợ:
- Xác thực JWT (SimpleJWT) + Google OAuth
- Quản lý Workspace, Board, List, Card, Label, Thành viên
- Chia sẻ Board qua link mời
- Lọc dữ liệu (filter) nâng cao
- Cập nhật realtime qua WebSocket

---

## 2. Tech Stack
- **Ngôn ngữ**: Python 3.x
- **Framework**: Django 5.x
- **API**: Django REST Framework (DRF)
- **Auth**: SimpleJWT, Google OAuth
- **Realtime**: Django Channels + Redis
- **CSDL**: PostgreSQL / SQLite (dev)
- **Storage**: Local media (avatar, file)
- **Khác**: CORS Headers, Pillow

---

## 3. Endpoint chính

### Auth (`/api/auth/`)
- `POST /register/` — Đăng ký
- `POST /login/` — Đăng nhập
- `POST /logout/` — Đăng xuất
- `GET /me/` — Lấy thông tin user hiện tại
- `POST /google-login/` — Đăng nhập bằng Google
- `GET /users/search/?q=` — Tìm kiếm user

### Boards (`/api/`)
- `GET/POST /workspaces/` — Danh sách / Tạo workspace
- `GET/POST /boards/` — Danh sách / Tạo board
- `GET/POST /boards/<id>/lists/` — Danh sách / Tạo list
- `GET/POST /lists/<id>/cards/` — Danh sách / Tạo card
- `GET/POST /boards/<id>/labels/` — Danh sách / Tạo label
- `GET/POST /boards/<id>/members/` — Danh sách / Thêm thành viên
- `POST /boards/<id>/invite-link/` — Tạo link mời
- `POST /boards/join/` — Tham gia board qua link

---

## 4. Realtime (WebSocket)
- Endpoint: `ws/boards/<board_id>/`
- Sử dụng **BoardConsumer** để gửi cập nhật realtime khi:
  - Tạo / cập nhật / xóa list
  - Tạo / cập nhật / xóa card
- Channels sử dụng **Redis** làm backend.

---

## 5. Cài đặt & Chạy
```bash
# Clone repo
git clone <repo-url>
cd backend

# Tạo môi trường ảo
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Cài đặt dependencies
pip install -r requirements.txt

# Tạo file .env và cấu hình
cp .env.example .env

# Chạy migrate
python manage.py migrate

# Tạo tài khoản admin
python manage.py createsuperuser

# Chạy server backend
python manage.py runserver

# Chạy Redis cho Channels
redis-server
