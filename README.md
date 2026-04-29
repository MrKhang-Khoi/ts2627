# HỆ THỐNG NỘP HỒ SƠ TUYỂN SINH LỚP 10

## Giới thiệu
Ứng dụng web nội bộ quản lý việc học sinh lớp 9 nộp hồ sơ tuyển sinh lớp 10.
Chạy trên mạng LAN trường, không cần Internet.

## Cài đặt và chạy

### Bước 1: Cài Python
- Tải Python 3.9+ tại https://python.org
- Nhớ chọn "Add Python to PATH" khi cài đặt

### Bước 2: Cài thư viện
```
pip install -r requirements.txt
```

### Bước 3: Chạy ứng dụng
```
py app.py
```

### Bước 4: Truy cập
- Trên máy chủ: http://127.0.0.1:5000
- Trên điện thoại cùng Wi-Fi: http://IP_MAY_CHU:5000

### Xem địa chỉ IP máy chủ
```
ipconfig
```
Tìm dòng "IPv4 Address" ví dụ: 192.168.1.10

---

## Tài khoản mặc định
| Username | Mật khẩu | Vai trò |
|----------|----------|---------|
| admin | admin123 | Quản trị viên |

**Đổi mật khẩu ngay sau khi đăng nhập!**

---

## Hướng dẫn sử dụng

### Import danh sách học sinh
1. Đăng nhập bằng tài khoản admin
2. Vào **Quản trị > Import danh sách**
3. Tải file Excel mẫu, điền thông tin học sinh
4. Upload file lên hệ thống

File Excel cần có các cột: `ma_hoso, lop, stt, ho_ten, ngay_sinh, ghi_chu`

Ví dụ:
```
ma_hoso  | lop | stt | ho_ten         | ngay_sinh  | ghi_chu
9B1_001  | 9B1 | 01  | Nguyễn Văn An  | 12/05/2011 |
```

### Học sinh nộp hồ sơ
1. Mở trình duyệt, vào địa chỉ IP máy chủ
2. Chọn lớp của mình
3. Tìm và bấm vào tên mình
4. Bấm "Chọn file" rồi "Tải lên" cho từng loại giấy tờ

Các loại file chấp nhận: **PDF, JPG, JPEG, PNG** (tối đa 20MB)

### Giáo viên kiểm tra hồ sơ
1. Đăng nhập bằng tài khoản giáo viên
2. Vào **Bảng theo dõi**
3. Bấm **Kiểm tra** bên cạnh từng học sinh
4. Xem file, đánh dấu Đạt / File mờ / Sai file / Thiếu trang / Cần nộp lại

### Nối học bạ
**Yêu cầu:** Học sinh đã nộp đủ HOCBA_6_8.pdf và HOCBA_9.pdf

- Nối 1 học sinh: Bảng giáo viên > Kiểm tra > Nối học bạ
- Nối cả lớp: Bấm nút "Nối học bạ cả lớp"
- Nối toàn khối: Đăng nhập admin > Nối toàn khối

### Xuất Excel danh sách
- Giáo viên: Bảng theo dõi > Xuất Excel
- Admin: Quản trị > Xuất Excel (có thể xuất theo lớp hoặc toàn khối)

### Tải ZIP hồ sơ
- Hồ sơ 1 học sinh: Bảng admin > nút 📦
- Hồ sơ cả lớp: Bảng theo dõi > Tải ZIP lớp
- Toàn khối: Quản trị > ZIP toàn khối

---

## Cấu trúc dự án
```
hoso_lop10_app/
├── app.py              # Ứng dụng Flask chính
├── database.py         # Cơ sở dữ liệu SQLite
├── file_utils.py       # Xử lý file upload
├── pdf_utils.py        # Nối PDF, xuất Excel, ZIP
├── requirements.txt    # Thư viện Python
├── database.db         # Database (tạo tự động)
├── uploads/            # Thư mục lưu file hồ sơ
├── backups/            # File backup khi nộp lại
├── data/               # File mẫu
├── static/
│   ├── css/style.css
│   └── js/main.js
└── templates/          # Giao diện HTML
```

---

## Giai đoạn nộp hồ sơ
- **Giai đoạn 1:** GKS + CCCD + Học bạ 6-8
- **Giai đoạn 2:** Thêm Học bạ 9 + CNTN THCS, bật nối học bạ

Admin chuyển giai đoạn tại: Quản trị > Cài đặt

---

## Hỗ trợ
Liên hệ ban quản trị trường nếu gặp sự cố.
