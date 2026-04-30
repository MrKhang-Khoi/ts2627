"""
debug_pa.py — Goi API debug PythonAnywhere de xem du lieu DB that va thu match.
Chay: py debug_pa.py
"""
import sys, json, urllib.request, urllib.error
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PA_URL   = 'https://ts102627.pythonanywhere.com'
TOKEN    = 'chuvanan_tsdc_push_2026'

# 5 hoc sinh TSDC tu screenshot (dung tim nguyen nhan)
TSDC_STUDENTS = [
    {'hoTen': 'Nong Hong Nin',      'ngaySinh': '12/06/2011', 'cccd': '', 'lop': '9B1'},
    {'hoTen': 'Le Yen Nhi',         'ngaySinh': '11/03/2011', 'cccd': '', 'lop': '9A5'},
    {'hoTen': 'Pham Huy Phuc',      'ngaySinh': '22/09/2011', 'cccd': '', 'lop': '9B3'},
    {'hoTen': 'Doan The Quyet',     'ngaySinh': '05/11/2011', 'cccd': '', 'lop': '9B3'},
    {'hoTen': 'Le Tan Khoi Nguyen', 'ngaySinh': '15/08/2011', 'cccd': '', 'lop': '9B1'},
]

payload = json.dumps({
    'token': TOKEN,
    'students': TSDC_STUDENTS
}, ensure_ascii=False).encode('utf-8')

req = urllib.request.Request(
    PA_URL + '/api/tsdc-debug',
    data=payload,
    headers={'Content-Type': 'application/json; charset=utf-8'},
    method='POST'
)

try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        result = json.loads(resp.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print(f'Loi HTTP {e.code}: {e.read().decode("utf-8", errors="replace")}')
    sys.exit(1)
except Exception as e:
    print(f'Loi ket noi: {e}')
    sys.exit(1)

print(f'\n=== DB PYTHONANYWHERE: {result["db_count"]} hoc sinh (hien 20 dau) ===')
for s in result.get('db_sample', []):
    print(f'  id={s["id"]} | ma_hoso="{s["ma_hoso"]}" | ho_ten="{s["ho_ten"]}" | '
          f'ngay_sinh="{s["ngay_sinh"]}" | cccd="{s["cccd"]}"')

print(f'\n=== KIEM TRA MATCH (5 TSDC HS) ===')
for m in result.get('match_log', []):
    status = 'MATCH by ' + m['match_by'] if m['match'] else 'KHONG MATCH'
    print(f'\nTSDC: "{m["tsdc_name"]}" ({m["dob"]}) cccd="{m["cccd"]}"')
    print(f'  norm: "{m["name_norm"]}"  key: "{m["key"]}"')
    print(f'  => {status}')
    if m.get('dob_hits_in_db'):
        print(f'  DB co ngay sinh nay: {[(h["ho_ten"]) for h in m["dob_hits_in_db"]]}')
    else:
        print(f'  DB KHONG co ngay sinh "{m["dob"]}"')
    if m['match']:
        print(f'  Match voi: {m["match"]}')

print('\n=== PHAN TICH ===')
print('Neu tat ca KHONG MATCH va DB co HS:')
print('  -> van de: ma_hoso khong phai CCCD (la dang 9A5_001) va TSDC chua lay duoc CCCD')
print('Neu DB_KHONG CO NGAY SINH = HS thatt trong DB co dinh dang ngay sinh khac')
print('=> Dung tsdc_push.py de push lai voi CCCD va ngaySinh day du')
