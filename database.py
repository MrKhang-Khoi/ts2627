import sqlite3
import os
from datetime import datetime

# DATA_DIR: trỏ đến Persistent Disk trên Render, hoặc thư mục local
DATA_DIR = os.environ.get('DATA_DIR', os.path.dirname(__file__))
DB_PATH = os.path.join(DATA_DIR, 'database.db')

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # WAL mode: cho phép đọc đồng thời khi đang ghi, tốt hơn cho web app nhiều user
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")   # Cân bằng tốc độ & an toàn
    conn.execute("PRAGMA busy_timeout=8000")    # Chờ tối đa 8s nếu DB bị lock
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ma_hoso TEXT UNIQUE NOT NULL,
            lop TEXT NOT NULL,
            stt TEXT NOT NULL,
            ho_ten TEXT NOT NULL,
            ho_ten_khong_dau TEXT NOT NULL,
            ngay_sinh TEXT,
            folder_path TEXT,
            status_overall TEXT DEFAULT 'CHUA_NOP',
            note TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            assigned_class TEXT,
            full_name TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            doc_type TEXT NOT NULL,
            file_name TEXT,
            file_path TEXT,
            status TEXT DEFAULT 'CHUA_NOP',
            note TEXT,
            uploaded_at TEXT,
            checked_by TEXT,
            checked_at TEXT,
            locked INTEGER DEFAULT 0,
            FOREIGN KEY (student_id) REFERENCES students(id)
        );
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            student_id INTEGER,
            doc_type TEXT,
            detail TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS tsdc_cache (
            id INTEGER PRIMARY KEY DEFAULT 1,
            data_json TEXT,
            pushed_at TEXT,
            pushed_by TEXT
        );
    ''')
    # Tài khoản admin mặc định
    from werkzeug.security import generate_password_hash
    existing = c.execute("SELECT id FROM users WHERE username='admin'").fetchone()
    if not existing:
        c.execute("INSERT INTO users (username,password_hash,role,full_name,created_at) VALUES (?,?,?,?,?)",
                  ('admin', generate_password_hash('admin123'), 'admin', 'Quản trị viên', datetime.now().isoformat()))
    # File lên Google Drive — không lo quota disk, cho phép 20MB/file
    for key, val in [('phase', '1'), ('max_file_size_mb', '20')]:
        c.execute("INSERT OR IGNORE INTO settings (key,value) VALUES (?,?)", (key, val))
    conn.commit()
    conn.close()

def add_log(user_id, action, student_id=None, doc_type=None, detail=None):
    conn = get_db()
    conn.execute("INSERT INTO logs (user_id,action,student_id,doc_type,detail,created_at) VALUES (?,?,?,?,?,?)",
                 (user_id, action, student_id, doc_type, detail, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_setting(key, default=None):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row['value'] if row else default

def set_setting(key, value):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()

def compute_overall_status(student_id):
    """Tính trạng thái tổng hồ sơ của học sinh"""
    conn = get_db()
    docs = conn.execute("SELECT doc_type, status FROM documents WHERE student_id=?", (student_id,)).fetchall()
    conn.close()
    doc_map = {d['doc_type']: d['status'] for d in docs}

    required_all = ['GIAYKHAISINH', 'CCCD', 'HOCBA', 'CNTN_THCS']
    required_phase1 = ['GIAYKHAISINH', 'CCCD', 'HOCBA_6_8']
    bad_statuses = {'FILE_MO', 'SAI_FILE', 'THIEU_TRANG', 'CAN_NOP_LAI'}

    if not doc_map:
        return 'CHUA_NOP'

    # Kiểm tra có file lỗi không
    has_bad = any(s in bad_statuses for s in doc_map.values())
    if has_bad:
        return 'CAN_SUA'

    # Đủ hồ sơ chính thức
    all_full = all(doc_map.get(d) == 'DAT' for d in required_all)
    if all_full:
        return 'DU_HO_SO_CHINH_THUC'

    # Tạm đủ giai đoạn 1
    phase1_ok = all(doc_map.get(d) in ('DAT', 'DA_NOP_CHO_KIEM_TRA') for d in required_phase1)
    if phase1_ok and doc_map.get('HOCBA_6_8'):
        return 'TAM_DU_GIAI_DOAN_1'

    submitted_any = any(s != 'CHUA_NOP' for s in doc_map.values())
    if submitted_any:
        return 'CHUA_DU'

    return 'CHUA_NOP'

def update_overall_status(student_id):
    status = compute_overall_status(student_id)
    conn = get_db()
    conn.execute("UPDATE students SET status_overall=?, updated_at=? WHERE id=?",
                 (status, datetime.now().isoformat(), student_id))
    conn.commit()
    conn.close()
    return status
