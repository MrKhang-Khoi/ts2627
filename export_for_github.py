#!/usr/bin/env python3
"""
Export danh sách HS + link Google Drive → JSON cho trang tải hồ sơ GitHub Pages.

CÁCH DÙNG (trên PythonAnywhere console):
    cd ~/hoso_lop10_app
    python export_for_github.py

File JSON sẽ được tạo tại: students_data.json
Sau đó tải file này về và đặt vào repo GitHub Pages.
"""

import sqlite3
import json
import os
from datetime import datetime

# Sử dụng cùng DATA_DIR như app.py
DATA_DIR = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(DATA_DIR, 'database.db')

# Thứ tự hiển thị tài liệu
DISPLAY_ORDER = ['GIAYKHAISINH', 'CNTN_THCS', 'HOCBA_6_9', 'CCCD', 'ANH_THE', 'UU_TIEN']

DOC_LABELS = {
    'GIAYKHAISINH': 'Giấy khai sinh',
    'CNTN_THCS':    'CN tốt nghiệp THCS',
    'HOCBA_6_9':    'Học bạ (lớp 6-9)',
    'HOCBA':        'Học bạ hoàn chỉnh',
    'CCCD':         'CCCD / Mã định danh',
    'ANH_THE':      'Ảnh thẻ 4x6',
    'UU_TIEN':      'Ưu tiên (nếu có)',
}

OVERALL_LABELS = {
    'CHUA_NOP':             'Chưa nộp',
    'TAM_DU_GIAI_DOAN_1':  'Tạm đủ giai đoạn 1',
    'CHUA_DU':              'Chưa đủ hồ sơ',
    'CAN_SUA':              'Cần nộp lại',
    'DU_HO_SO_CHINH_THUC': 'Đủ hồ sơ chính thức',
}


def export():
    if not os.path.exists(DB_PATH):
        print(f'❌ Không tìm thấy database: {DB_PATH}')
        return None

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Lấy danh sách lớp
    classes = [r[0] for r in conn.execute(
        'SELECT DISTINCT lop FROM students ORDER BY lop'
    ).fetchall()]

    students_by_class = {}
    total_students = 0
    total_files = 0

    for cls in classes:
        rows = conn.execute(
            'SELECT id, stt, ho_ten, ngay_sinh, status_overall '
            'FROM students WHERE lop=? ORDER BY CAST(stt AS INTEGER)',
            (cls,)
        ).fetchall()

        class_students = []
        for s in rows:
            # Lấy tất cả documents của HS này
            docs = conn.execute(
                'SELECT doc_type, file_path, file_name, status '
                'FROM documents WHERE student_id=?',
                (s['id'],)
            ).fetchall()

            doc_map = {}
            for d in docs:
                fp = d['file_path']
                if fp and fp.startswith('drive:'):
                    file_id = fp[6:]  # Bỏ prefix 'drive:'
                    doc_map[d['doc_type']] = {
                        'file_id': file_id,
                        'name': d['file_name'] or (d['doc_type'] + '.pdf'),
                        'status': d['status'] or 'DA_NOP_CHO_KIEM_TRA',
                    }
                    total_files += 1

            class_students.append({
                'stt': s['stt'],
                'ho_ten': s['ho_ten'],
                'ngay_sinh': s['ngay_sinh'] or '',
                'status': s['status_overall'] or 'CHUA_NOP',
                'doc_count': len(doc_map),
                'docs': doc_map,
            })
            total_students += 1

        if class_students:
            students_by_class[cls] = class_students

    conn.close()

    data = {
        'exported_at': datetime.now().strftime('%d/%m/%Y %H:%M'),
        'school': 'Trường THCS Chu Văn An',
        'year': '2025-2026',
        'classes': [c for c in classes if c in students_by_class],
        'doc_labels': DOC_LABELS,
        'doc_order': DISPLAY_ORDER,
        'overall_labels': OVERALL_LABELS,
        'students': students_by_class,
    }

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'students_data.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f'✅ Export thành công!')
    print(f'   📁 File: {output_path}')
    print(f'   📊 {total_students} học sinh | {len(students_by_class)} lớp | {total_files} files')
    print(f'   📋 Lớp: {", ".join(data["classes"])}')
    print(f'\n👉 Bước tiếp: Tải file students_data.json về và đặt vào repo GitHub Pages.')
    return output_path


if __name__ == '__main__':
    export()
