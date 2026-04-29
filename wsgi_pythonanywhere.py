# File này dùng cho PythonAnywhere WSGI configuration
# Đặt nội dung này vào file WSGI trên PythonAnywhere
# (xem hướng dẫn chi tiết trong README_PYTHONANYWHERE.md)

import sys
import os

# Đường dẫn đến thư mục ứng dụng — thay USERNAME bằng username của bạn
USERNAME = 'tentruong'  # <<< ĐỔI THÀNH USERNAME CỦA BẠN
APP_DIR = f'/home/{USERNAME}/hoso_lop10_app'
DATA_DIR = f'/home/{USERNAME}/data'

# Thêm đường dẫn vào Python path
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# Cấu hình biến môi trường
os.environ['DATA_DIR'] = DATA_DIR
os.environ['SECRET_KEY'] = 'thay-bang-chuoi-bi-mat-cua-ban-2026'

# Tạo thư mục dữ liệu nếu chưa có
os.makedirs(os.path.join(DATA_DIR, 'uploads'), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, 'backups'), exist_ok=True)

# Import Flask app
from app import app as application
