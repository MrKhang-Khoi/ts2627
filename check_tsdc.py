import sqlite3
conn = sqlite3.connect('database.db')
conn.row_factory = sqlite3.Row

total = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
count = conn.execute("SELECT COUNT(*) FROM students WHERE tsdc_trang_thai IS NOT NULL AND TRIM(tsdc_trang_thai) != ''").fetchone()[0]
print(f"Total students: {total}, With TSDC data: {count}")

samples = conn.execute("SELECT ho_ten, lop, tsdc_trang_thai, tsdc_nv1 FROM students WHERE tsdc_trang_thai IS NOT NULL AND TRIM(tsdc_trang_thai) != '' LIMIT 5").fetchall()
print("Sample with TSDC:")
for s in samples:
    print(f"  {s['ho_ten']} ({s['lop']}): tt={repr(s['tsdc_trang_thai'])}, nv1={repr(s['tsdc_nv1'])}")

# Check enrich_students function
import sys
sys.path.insert(0, '.')
from app import enrich_students
rows = conn.execute("SELECT * FROM students WHERE tsdc_trang_thai IS NOT NULL AND TRIM(tsdc_trang_thai) != '' LIMIT 2").fetchall()
enriched = enrich_students(rows)
print("\nAfter enrich:")
for e in enriched:
    print(f"  tsdc_trang_thai={repr(e.get('tsdc_trang_thai'))}")

conn.close()
