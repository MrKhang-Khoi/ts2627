"""
Chay script nay de sync du lieu TSDC tu cache vao DB local truc tiep.
Khong can chay lai Playwright.
"""
import sys, unicodedata, sqlite3, json
from datetime import datetime
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DB_PATH = 'database.db'

# Du lieu 5 hoc sinh lay duoc tu TSDC (update thu cong neu can)
TSDC_DATA = [
    {'hoTen': 'Le Yen Nhi',      'ngaySinh': '11/03/2011', 'cccd': '', 'trangThai': 'Ho so cho tiep nhan', 'nv1': 'Truong THPT Tran Hung Dao'},
    {'hoTen': 'Le Tan Khoi Nguyen','ngaySinh': '15/08/2011','cccd': '', 'trangThai': 'Ho so cho tiep nhan', 'nv1': 'Truong THPT Chuyen Nguyen Tat Thanh'},
    {'hoTen': 'Nong Hong Nin',    'ngaySinh': '12/06/2011', 'cccd': '', 'trangThai': 'Cho xet duyet',        'nv1': 'Truong THPT Tran Hung Dao'},
    {'hoTen': 'Pham Huy Phuc',   'ngaySinh': '22/09/2011', 'cccd': '', 'trangThai': 'Cho xet duyet',        'nv1': 'Truong THPT Tran Hung Dao'},
    {'hoTen': 'Doan The Quyet',  'ngaySinh': '05/11/2011', 'cccd': '', 'trangThai': 'Ho so cho tiep nhan', 'nv1': 'Truong THPT Tran Hung Dao'},
]

def normalize_name(name):
    name = name.strip().lower()
    name = unicodedata.normalize('NFD', name)
    name = ''.join(c for c in name if unicodedata.category(c) != 'Mn')
    return ' '.join(name.split())

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# Bao dam cac cot ton tai
for col in ['cccd','tsdc_ma_hoso','tsdc_trang_thai','tsdc_nv1','tsdc_nv2','tsdc_nv3','tsdc_updated_at']:
    try:
        conn.execute(f'ALTER TABLE students ADD COLUMN {col} TEXT')
        print(f'[SYNC] Them cot: {col}')
    except: pass

all_local = conn.execute('SELECT id, ho_ten, ho_ten_khong_dau, ngay_sinh, cccd FROM students').fetchall()

print('\n=== TAT CA HS TRONG DB LOCAL ===')
for s in all_local:
    dob = (s['ngay_sinh'] or '').strip()
    name_raw = s['ho_ten_khong_dau'] or s['ho_ten'] or ''
    print(f'  DB: ho_ten="{s["ho_ten"]}" | ho_ten_khong_dau="{s["ho_ten_khong_dau"]}" | ngay_sinh={repr(dob)} | norm="{normalize_name(name_raw)}"')

print('\n=== TSDC STUDENTS ===')
for ts in TSDC_DATA:
    print(f'  TSDC: "{ts["hoTen"]}" | ngaySinh={repr(ts["ngaySinh"])} | norm="{normalize_name(ts["hoTen"])}"')

print()
