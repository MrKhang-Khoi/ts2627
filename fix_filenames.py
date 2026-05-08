"""Fix file_name trong documents DB: drive:xxx -> ten chuan, CNTN_THCS -> CNHT_Lop_9"""
import sqlite3

DOC_FILE_NAMES = {
    'GIAYKHAISINH': 'GIAYKHAISINH',
    'CNTN_THCS':    'CNHT_Lop_9',
    'HOCBA':        'HOCBA',
    'HOCBA_6_9':    'HOCBA_6_9',
    'CCCD':         'CCCD',
    'ANH_THE':      'ANH_THE',
    'UU_TIEN':      'UU_TIEN',
}

conn = sqlite3.connect('database.db')
conn.row_factory = sqlite3.Row

# 1. Fix drive:xxx file names
rows = conn.execute("SELECT id, doc_type, file_name FROM documents WHERE file_name LIKE 'drive:%'").fetchall()
print(f"Found {len(rows)} records with drive:ID as file_name")
for r in rows:
    base = DOC_FILE_NAMES.get(r['doc_type'], r['doc_type'])
    new_name = f"{base}.pdf"
    conn.execute("UPDATE documents SET file_name=? WHERE id=?", (new_name, r['id']))
    print(f"  Fixed id={r['id']}: {r['file_name'][:40]}... -> {new_name}")

# 2. Fix CNTN_THCS.pdf -> CNHT_Lop_9.pdf
rows2 = conn.execute("SELECT id, file_name FROM documents WHERE doc_type='CNTN_THCS' AND file_name != 'CNHT_Lop_9.pdf'").fetchall()
print(f"\nFound {len(rows2)} CNTN_THCS with old name")
for r in rows2:
    conn.execute("UPDATE documents SET file_name='CNHT_Lop_9.pdf' WHERE id=?", (r['id'],))
    print(f"  Fixed id={r['id']}: {r['file_name']} -> CNHT_Lop_9.pdf")

conn.commit()
conn.close()
print("\nDone!")
