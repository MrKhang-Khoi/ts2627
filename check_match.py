"""
Script kiem tra chinh xac ly do TSDC khong map duoc vao DB.
Chay: py check_match.py
"""
import sys, unicodedata, sqlite3
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DB_PATH = 'database.db'

def normalize_name(name):
    name = name.strip().lower()
    name = unicodedata.normalize('NFD', name)
    name = ''.join(c for c in name if unicodedata.category(c) != 'Mn')
    return ' '.join(name.split())

# Du lieu TSDC tu screenshot (the hien trong popup)
TSDC_STUDENTS = [
    {'hoTen': 'Nong Hong Nin',      'ngaySinh': '12/06/2011', 'cccd': '', 'lop': '9B1'},
    {'hoTen': 'Le Yen Nhi',         'ngaySinh': '11/03/2011', 'cccd': '', 'lop': '9A5'},
    {'hoTen': 'Pham Huy Phuc',      'ngaySinh': '22/09/2011', 'cccd': '', 'lop': '9B3'},
    {'hoTen': 'Doan The Quyet',     'ngaySinh': '05/11/2011', 'cccd': '', 'lop': '9B3'},
    {'hoTen': 'Le Tan Khoi Nguyen', 'ngaySinh': '15/08/2011', 'cccd': '', 'lop': '9B1'},
]

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
all_local = conn.execute(
    'SELECT id, ma_hoso, ho_ten, ho_ten_khong_dau, ngay_sinh, cccd FROM students'
).fetchall()
conn.close()

print(f'=== DB LOCAL: {len(all_local)} hoc sinh ===')
for s in all_local:
    print(f'  id={s["id"]} | ma_hoso="{s["ma_hoso"]}" | ho_ten="{s["ho_ten"]}" | '
          f'ho_ten_khong_dau="{s["ho_ten_khong_dau"]}" | ngay_sinh="{s["ngay_sinh"]}" | cccd="{s["cccd"]}"')

# Build lookup maps
by_ma_hoso = {}
by_cccd    = {}
by_dob_name = {}

for s in all_local:
    # Map 1: ma_hoso (neu la so - CCCD bo so 0 dau)
    mhs = (s['ma_hoso'] or '').strip().lstrip('0')
    if mhs and mhs.isdigit():
        by_ma_hoso[mhs] = s['id']

    # Map 2: cccd stored
    if s['cccd']:
        by_cccd[s['cccd'].strip().lstrip('0')] = s['id']

    # Map 3: DOB + ten
    dob = (s['ngay_sinh'] or '').strip()
    n1 = normalize_name(s['ho_ten'] or '')
    by_dob_name[dob + '|' + n1] = (s['id'], s['ho_ten'])
    if s['ho_ten_khong_dau']:
        n2 = normalize_name(s['ho_ten_khong_dau'])
        by_dob_name[dob + '|' + n2] = (s['id'], s['ho_ten'])

print(f'\n=== KIEM TRA TUNG TSDC STUDENT ===')
for ts in TSDC_STUDENTS:
    cccd     = (ts.get('cccd') or '').strip()
    cccd_raw = cccd.lstrip('0')
    dob      = (ts.get('ngaySinh') or '').strip()
    name     = (ts.get('hoTen') or '').strip()
    name_norm = normalize_name(name)
    key = dob + '|' + name_norm

    print(f'\nTSDC: "{name}" | dob={dob} | cccd="{cccd}" | lop={ts.get("lop","")}')
    print(f'  norm_name="{name_norm}"')
    print(f'  lookup_key="{key}"')

    # Check map 1
    m1 = by_ma_hoso.get(cccd_raw)
    print(f'  [1] ma_hoso match (cccd_raw="{cccd_raw}"): {m1 or "KHONG"}')

    # Check map 2
    m2 = by_cccd.get(cccd_raw)
    print(f'  [2] cccd_stored match: {m2 or "KHONG"}')

    # Check map 3
    m3 = by_dob_name.get(key)
    print(f'  [3] dob+name match: {m3 or "KHONG"}')

    # Debug: tim tat ca key co DOB nay trong by_dob_name
    dob_keys = [(k, v) for k, v in by_dob_name.items() if dob in k]
    if dob_keys:
        print(f'  [3] DB co ngay sinh "{dob}": {[(k.split("|")[1], v[1]) for k, v in dob_keys]}')
    else:
        print(f'  [3] DB KHONG co ngay sinh "{dob}" nao ca!')

    # Tim ten tuong tu trong DB
    similar = [(k.split("|")[1], v[1]) for k, v in by_dob_name.items()
               if name_norm[:6] in k.split("|")[1] if '|' in k]
    if similar:
        print(f'  [~] Ten tuong tu trong DB: {similar[:3]}')

print('\n=== TONG KET ===')
print('Neu tat ca la KHONG -> Van de:')
print('  - DB local chi co du lieu TEST, khong phai HS that')
print('  - HS that chi co tren PythonAnywhere')
print('  - Can chay check_match.py TREN PYTHONANYWHERE (qua Bash console)')
print()
print('Neu co co ngay sinh -> Van de normalize ten:')
print('  So sanh chinh xac ten TSDC va ten DB de phat hien lech')
