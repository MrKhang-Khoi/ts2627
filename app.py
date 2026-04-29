from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os, io, shutil, openpyxl
from datetime import datetime
from database import get_db, init_db, add_log, get_setting, set_setting, update_overall_status
from file_utils import (to_ascii, get_student_folder, save_uploaded_file, delete_file_to_backup,
                        DOC_TYPES, DOC_LABELS, STATUS_LABELS, OVERALL_LABELS, UPLOAD_FOLDER,
                        DISPLAY_ORDER, OPTIONAL_DOCS, MULTI_FILE_DOCS)
from pdf_utils import (merge_transcripts, export_excel, create_student_zip,
                       create_class_zip, create_all_zip, append_to_existing_pdf)

app = Flask(__name__)
# Đọc secret key từ biến môi trường (bắt buộc trên Render)
app.secret_key = os.environ.get('SECRET_KEY', 'hoso_lop10_secret_key_2026_local')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB — file lên Drive, không lo quota disk

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Bạn không có quyền truy cập trang này.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

def get_student_docs(student_id):
    conn = get_db()
    rows = conn.execute("SELECT * FROM documents WHERE student_id=?", (student_id,)).fetchall()
    conn.close()
    doc_map = {}
    for r in rows:
        doc_map[r['doc_type']] = dict(r)
    return doc_map

def get_student_with_docs(student_id):
    conn = get_db()
    s = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    conn.close()
    if not s:
        return None, {}
    return dict(s), get_student_docs(student_id)

def enrich_students(students):
    """Thêm docs và doc_count cho mỗi học sinh."""
    result = []
    for s in students:
        sd = dict(s)
        docs = get_student_docs(s['id'])
        sd['docs'] = docs
        # Đếm số tài liệu đã nộp (có file, không tính CHUA_NOP)
        sd['doc_count'] = sum(1 for d in docs.values() if d.get('file_path'))
        sd['doc_total'] = len(DISPLAY_ORDER)  # tổng số mục
        result.append(sd)
    return result

@app.route('/')
def index():
    conn = get_db()
    classes = [r['lop'] for r in conn.execute("SELECT DISTINCT lop FROM students ORDER BY lop").fetchall()]
    conn.close()
    return render_template('index.html', classes=classes)

@app.route('/huong-dan')
def huong_dan():
    """Trang hướng dẫn nộp hồ sơ dành cho học sinh"""
    return send_file('static/huong_dan_hoso.html')

@app.route('/class/<class_name>')
def student_list(class_name):
    conn = get_db()
    students = conn.execute("SELECT * FROM students WHERE lop=? ORDER BY CAST(stt AS INTEGER)", (class_name,)).fetchall()
    conn.close()
    students = enrich_students(students)
    return render_template('student_list.html', students=students, class_name=class_name,
                           DOC_LABELS=DOC_LABELS, STATUS_LABELS=STATUS_LABELS, OVERALL_LABELS=OVERALL_LABELS)

@app.route('/student/<int:student_id>')
def student_profile(student_id):
    student, doc_map = get_student_with_docs(student_id)
    if not student:
        flash('Không tìm thấy học sinh.', 'error')
        return redirect(url_for('index'))
    # Bảo mật: học sinh phải xác minh mã CCCD trước khi xem hồ sơ
    if session.get('role') not in ('teacher', 'admin'):
        verified = session.get('verified_students', [])
        if student_id not in verified:
            # Redirect về trang lớp, front-end sẽ mở modal xác minh
            return redirect(url_for('student_list', class_name=student['lop']) + f'?verify={student_id}')
    phase = get_setting('phase', '1')
    max_mb = int(get_setting('max_file_size_mb', '20'))
    active_docs = list(DISPLAY_ORDER)
    return render_template('student_profile.html', student=student, doc_map=doc_map,
                           DOC_TYPES=DOC_TYPES, DOC_LABELS=DOC_LABELS, STATUS_LABELS=STATUS_LABELS,
                           OVERALL_LABELS=OVERALL_LABELS, active_docs=active_docs, phase=phase,
                           max_mb=max_mb, DISPLAY_ORDER=DISPLAY_ORDER, OPTIONAL_DOCS=OPTIONAL_DOCS,
                           MULTI_FILE_DOCS=MULTI_FILE_DOCS)

@app.route('/api/download-hoso/<int:student_id>')
def api_download_hoso(student_id):
    """Tải toàn bộ hồ sơ của một học sinh dạng ZIP"""
    student, doc_map = get_student_with_docs(student_id)
    if not student:
        flash('Không tìm thấy học sinh.', 'error')
        return redirect(url_for('index'))
    buf = create_student_zip(student, doc_map)
    filename = f"HoSo_{student['ho_ten_khong_dau']}_{student['lop']}.zip"
    return send_file(buf, mimetype='application/zip',
                     as_attachment=True, download_name=filename)
@app.route('/api/verify-student-code', methods=['POST'])
def api_verify_student_code():
    """Học sinh nhập CCCD để xác minh danh tính trước khi xem hồ sơ."""
    data = request.get_json(force=True) or {}
    student_id = data.get('student_id')
    code = (data.get('code') or '').strip().replace(' ', '').replace('-', '')
    if not student_id or not code:
        return jsonify({'error': 'Vui lòng nhập mã bảo mật.'}), 400
    conn = get_db()
    row = conn.execute("SELECT id, ma_hoso, ho_ten, lop FROM students WHERE id=?", (student_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'Không tìm thấy học sinh.'}), 404
    # Normalize: chuẩn hoá về 12 chữ số để xử lý trường hợp
    # Excel lưu CCCD là số (mất số 0 đầu, ví dụ: 064311001234 → 64311001234)
    code_norm    = code.zfill(12)
    db_norm      = str(row['ma_hoso']).strip().replace(' ', '').zfill(12)
    if code_norm == db_norm:
        verified = session.get('verified_students', [])
        sid = int(student_id)
        if sid not in verified:
            verified.append(sid)
        session['verified_students'] = verified
        session.modified = True
        add_log(None, 'STUDENT_VERIFY', student_id, None, f"HS xác minh: {row['ho_ten']}")
        return jsonify({'success': True,
                        'redirect': url_for('student_profile', student_id=student_id)})
    else:
        add_log(None, 'VERIFY_FAIL', student_id, None,
                f"Sai mã: {row['ho_ten']} | nhập={code_norm} | db={db_norm}")
        return jsonify({'error': 'Mã bảo mật không đúng. Kiểm tra lại số CCCD của em.'}), 401


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['full_name'] = user['full_name'] or username
            session['assigned_class'] = user['assigned_class']
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('teacher_dashboard'))
        flash('Tên đăng nhập hoặc mật khẩu không đúng.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/teacher')
@login_required
def teacher_dashboard():
    assigned = session.get('assigned_class')
    conn = get_db()
    if session.get('role') == 'admin':
        classes = [r['lop'] for r in conn.execute("SELECT DISTINCT lop FROM students ORDER BY lop").fetchall()]
        selected = request.args.get('class', classes[0] if classes else None)
    else:
        classes = [assigned] if assigned else []
        selected = assigned
    students = []
    if selected:
        rows = conn.execute("SELECT * FROM students WHERE lop=? ORDER BY CAST(stt AS INTEGER)", (selected,)).fetchall()
        students = enrich_students(rows)
    conn.close()
    stats = compute_stats(students)
    return render_template('teacher_dashboard.html', students=students, classes=classes,
                           selected_class=selected, stats=stats, DOC_LABELS=DOC_LABELS,
                           STATUS_LABELS=STATUS_LABELS, OVERALL_LABELS=OVERALL_LABELS, DOC_TYPES=DOC_TYPES)

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    conn = get_db()
    classes = [r['lop'] for r in conn.execute("SELECT DISTINCT lop FROM students ORDER BY lop").fetchall()]
    selected = request.args.get('class', 'ALL')
    filter_status = request.args.get('filter', '')
    query = "SELECT * FROM students"
    params = []
    if selected and selected != 'ALL':
        query += " WHERE lop=?"
        params.append(selected)
    query += " ORDER BY lop, CAST(stt AS INTEGER)"
    students = enrich_students(conn.execute(query, params).fetchall())
    if filter_status:
        students = [s for s in students if s['status_overall'] == filter_status]
    teachers = conn.execute("SELECT * FROM users WHERE role='teacher' ORDER BY full_name").fetchall()
    phase = get_setting('phase', '1')
    max_mb = get_setting('max_file_size_mb', '20')
    conn.close()
    stats = compute_stats(students)
    return render_template('admin_dashboard.html', students=students, classes=classes,
                           selected_class=selected, filter_status=filter_status, stats=stats,
                           teachers=teachers, phase=phase, max_mb=max_mb,
                           DOC_LABELS=DOC_LABELS, STATUS_LABELS=STATUS_LABELS,
                           OVERALL_LABELS=OVERALL_LABELS, DOC_TYPES=DOC_TYPES)

def compute_stats(students):
    total = len(students)
    stats = {'total': total, 'DU_HO_SO_CHINH_THUC': 0, 'CHUA_DU': 0, 'CAN_SUA': 0,
             'CHUA_NOP': 0, 'TAM_DU_GIAI_DOAN_1': 0}
    for s in students:
        key = s.get('status_overall', 'CHUA_NOP')
        if key in stats:
            stats[key] += 1
        else:
            stats['CHUA_DU'] += 1
    return stats

# ===== API ROUTES =====
@app.route('/api/classes')
def api_classes():
    conn = get_db()
    classes = [r['lop'] for r in conn.execute("SELECT DISTINCT lop FROM students ORDER BY lop").fetchall()]
    conn.close()
    return jsonify(classes)

@app.route('/api/students')
def api_students():
    lop = request.args.get('class', '')
    conn = get_db()
    rows = conn.execute("SELECT * FROM students WHERE lop=? ORDER BY stt", (lop,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/student/<int:sid>')
def api_student(sid):
    student, doc_map = get_student_with_docs(sid)
    if not student:
        return jsonify({'error': 'Không tìm thấy'}), 404
    return jsonify({'student': student, 'docs': doc_map})

@app.route('/api/upload', methods=['POST'])
def api_upload():
    student_id = request.form.get('student_id', type=int)
    doc_type = request.form.get('doc_type', '').upper()
    file = request.files.get('file')
    if not student_id or doc_type not in DOC_TYPES:
        return jsonify({'error': 'Dữ liệu không hợp lệ.'}), 400
    student, doc_map = get_student_with_docs(student_id)
    if not student:
        return jsonify({'error': 'Không tìm thấy học sinh.'}), 404
    # Kiểm tra khóa
    existing = doc_map.get(doc_type, {})
    if existing.get('locked') and existing.get('status') == 'DAT':
        return jsonify({'error': 'File đã được đánh dấu Đạt. Liên hệ giáo viên để mở khóa.'}), 403
    max_mb = int(get_setting('max_file_size_mb', '20'))
    file_path, err = save_uploaded_file(file, student, doc_type, max_mb)
    if err:
        return jsonify({'error': err}), 400
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute("DELETE FROM documents WHERE student_id=? AND doc_type=?", (student_id, doc_type))
    conn.execute("""INSERT INTO documents (student_id,doc_type,file_name,file_path,status,uploaded_at)
                    VALUES (?,?,?,?,?,?)""",
                 (student_id, doc_type, f"{doc_type}.pdf", file_path, 'DA_NOP_CHO_KIEM_TRA', now))
    conn.commit()
    conn.close()
    update_overall_status(student_id)
    add_log(session.get('user_id'), 'UPLOAD', student_id, doc_type, f"Nộp file {doc_type}")
    label = DOC_LABELS.get(doc_type, doc_type)
    return jsonify({'success': True, 'message': f"Đã nộp thành công {label} cho {student['ho_ten']} - Lớp {student['lop']}."})

@app.route('/api/append-hocba/<int:student_id>', methods=['POST'])
def api_append_hocba(student_id):
    """Thêm trang vào học bạ đã nộp. Nếu chưa có thì tạo mới."""
    try:
        student, doc_map = get_student_with_docs(student_id)
        if not student:
            return jsonify({'error': 'Không tìm thấy học sinh.'}), 404
        existing = doc_map.get('HOCBA_6_8', {})
        if existing.get('locked') and existing.get('status') == 'DAT':
            return jsonify({'error': 'Học bạ đã được xác nhận Đạt. Liên hệ giáo viên để mở khóa.'}), 403
        files = request.files.getlist('files')
        if not files:
            return jsonify({'error': 'Chưa chọn file nào.'}), 400
        max_mb = int(get_setting('max_file_size_mb', '20'))

        # Lấy bytes của file hiện tại (local hoặc Drive)
        # Nếu không tải được (Drive trả về HTML, file bị xóa...) → bắt đầu mới
        from pdf_utils import append_bytes, _get_bytes
        existing_bytes = None
        existing_path = existing.get('file_path')
        if existing_path:
            try:
                raw, dl_err = _get_bytes(existing_path)
                if not dl_err and raw and len(raw) > 100:
                    # Kiểm tra đây có phải PDF thực không
                    if raw[:4] == b'%PDF':
                        existing_bytes = raw
            except Exception:
                pass  # Không tải được → coi như chưa có file cũ

        pdf_bytes, page_count, err = append_bytes(existing_bytes, files, max_mb)
        if err:
            return jsonify({'error': err}), 400

        # Lưu vào Drive hoặc local
        import drive_utils
        if drive_utils.DRIVE_MODE:
            dest_path, err = drive_utils.upload(pdf_bytes, dict(student), 'HOCBA_6_8')
            if err:
                return jsonify({'error': err}), 500
        else:
            folder = get_student_folder(student['lop'], student['ma_hoso'], student['ho_ten_khong_dau'])
            dest_path = os.path.join(folder, 'HOCBA_6_8.pdf')
            bk_dir = os.path.join(os.environ.get('DATA_DIR', os.path.dirname(__file__)), 'backups', student['ma_hoso'])
            if existing_path and os.path.exists(existing_path):
                os.makedirs(bk_dir, exist_ok=True)
                ts = datetime.now().strftime('%Y-%m-%d_%H%M%S')
                shutil.copy2(existing_path, os.path.join(bk_dir, f'backup_HOCBA_6_8_{ts}.pdf'))
            with open(dest_path, 'wb') as f:
                f.write(pdf_bytes)

        conn = get_db()
        now = datetime.now().isoformat()
        conn.execute("DELETE FROM documents WHERE student_id=? AND doc_type='HOCBA_6_8'", (student_id,))
        conn.execute("""INSERT INTO documents (student_id,doc_type,file_name,file_path,status,uploaded_at,note)
                        VALUES (?,?,?,?,?,?,?)""",
                     (student_id, 'HOCBA_6_8', 'HOCBA_6_8.pdf', dest_path,
                      'DA_NOP_CHO_KIEM_TRA', now, f'{page_count} trang'))
        conn.commit()
        conn.close()
        update_overall_status(student_id)
        action = 'APPEND_HOCBA' if existing_path else 'UPLOAD_HOCBA'
        add_log(session.get('user_id'), action, student_id, 'HOCBA_6_8',
                f"{'Thêm' if existing_path else 'Tạo'} học bạ: {page_count} trang")
        return jsonify({'success': True,
                        'message': f'Đã cập nhật học bạ ({page_count} trang tổng cộng).',
                        'page_count': page_count})
    except Exception as e:
        return jsonify({'error': f'Lỗi máy chủ: {str(e)}'}), 500

@app.route('/api/upload-multi/<int:student_id>/<doc_type>', methods=['POST'])
def api_upload_multi(student_id, doc_type):
    """Upload nhiều file cùng lúc, gộp thành 1 PDF (CCCD 2 mặt, v.v.)"""
    doc_type = doc_type.upper()
    if doc_type not in MULTI_FILE_DOCS:
        return jsonify({'error': f'Loại tài liệu {doc_type} không hỗ trợ multi-upload.'}), 400
    student, doc_map = get_student_with_docs(student_id)
    if not student:
        return jsonify({'error': 'Không tìm thấy học sinh.'}), 404
    existing = doc_map.get(doc_type, {})
    if existing.get('locked') and existing.get('status') == 'DAT':
        return jsonify({'error': 'Tài liệu đã được xác nhận Đạt. Liên hệ giáo viên để mở khóa.'}), 403
    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'Chưa chọn file nào.'}), 400
    max_mb = int(get_setting('max_file_size_mb', '20'))

    from pdf_utils import merge_to_bytes
    pdf_bytes, page_count, err = merge_to_bytes(files, max_mb)
    if err:
        return jsonify({'error': err}), 400

    import drive_utils
    if drive_utils.DRIVE_MODE:
        dest_path, err = drive_utils.upload(pdf_bytes, dict(student), doc_type)
        if err:
            return jsonify({'error': err}), 500
    else:
        folder = get_student_folder(student['lop'], student['ma_hoso'], student['ho_ten_khong_dau'])
        dest_path = os.path.join(folder, f'{doc_type}.pdf')
        bk_dir = os.path.join(os.environ.get('DATA_DIR', os.path.dirname(__file__)), 'backups', student['ma_hoso'])
        if os.path.exists(dest_path):
            os.makedirs(bk_dir, exist_ok=True)
            ts = datetime.now().strftime('%Y-%m-%d_%H%M%S')
            shutil.copy2(dest_path, os.path.join(bk_dir, f'backup_{doc_type}_{ts}.pdf'))
        with open(dest_path, 'wb') as f:
            f.write(pdf_bytes)

    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute("DELETE FROM documents WHERE student_id=? AND doc_type=?", (student_id, doc_type))
    conn.execute("""INSERT INTO documents (student_id,doc_type,file_name,file_path,status,uploaded_at,note)
                    VALUES (?,?,?,?,?,?,?)""",
                 (student_id, doc_type, f'{doc_type}.pdf', dest_path,
                  'DA_NOP_CHO_KIEM_TRA', now, f'{page_count} trang'))
    conn.commit()
    conn.close()
    update_overall_status(student_id)
    add_log(session.get('user_id'), f'UPLOAD_MULTI_{doc_type}', student_id, doc_type,
            f"Nộp {doc_type}: {len(files)} file → {page_count} trang")
    return jsonify({'success': True,
                    'message': f'Đã nộp {doc_type} ({len(files)} file, {page_count} trang).',
                    'page_count': page_count})

@app.route('/api/delete-file', methods=['POST'])
def api_delete_file():
    try:
        data = request.get_json(force=True) or {}
        student_id = data.get('student_id')
        doc_type = (data.get('doc_type') or '').upper()
        if not student_id or not doc_type:
            return jsonify({'error': 'Dữ liệu không hợp lệ.'}), 400
        student, doc_map = get_student_with_docs(student_id)
        if not student:
            return jsonify({'error': 'Không tìm thấy học sinh.'}), 404
        doc = doc_map.get(doc_type, {})
        if doc.get('status') == 'DAT' and doc.get('locked'):
            return jsonify({'error': 'File đã Đạt và bị khóa. Liên hệ giáo viên để mở khóa.'}), 403
        delete_file_to_backup(doc.get('file_path'), student['ma_hoso'], doc_type)
        conn = get_db()
        conn.execute("DELETE FROM documents WHERE student_id=? AND doc_type=?", (student_id, doc_type))
        conn.commit()
        conn.close()
        update_overall_status(student_id)
        add_log(session.get('user_id'), 'DELETE', student_id, doc_type, f"Xóa file {doc_type}")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': f'Lỗi máy chủ: {str(e)}'}), 500

@app.route('/api/check-file', methods=['POST'])
@login_required
def api_check_file():
    data = request.get_json()
    student_id = data.get('student_id')
    doc_type = data.get('doc_type', '').upper()
    new_status = data.get('status', '')
    note = data.get('note', '')
    valid_statuses = ['DAT', 'FILE_MO', 'SAI_FILE', 'THIEU_TRANG', 'CAN_NOP_LAI']
    if new_status not in valid_statuses:
        return jsonify({'error': 'Trạng thái không hợp lệ.'}), 400
    conn = get_db()
    locked = 1 if new_status == 'DAT' else 0
    now = datetime.now().isoformat()
    conn.execute("""UPDATE documents SET status=?, note=?, checked_by=?, checked_at=?, locked=?
                    WHERE student_id=? AND doc_type=?""",
                 (new_status, note, session.get('username'), now, locked, student_id, doc_type))
    conn.commit()
    conn.close()
    update_overall_status(student_id)
    add_log(session.get('user_id'), 'CHECK', student_id, doc_type, f"Đánh dấu {new_status}: {note}")
    return jsonify({'success': True})

@app.route('/api/unlock-file', methods=['POST'])
@login_required
def api_unlock_file():
    data = request.get_json()
    student_id = data.get('student_id')
    doc_type = data.get('doc_type', '').upper()
    conn = get_db()
    conn.execute("UPDATE documents SET locked=0, status='CAN_NOP_LAI' WHERE student_id=? AND doc_type=?",
                 (student_id, doc_type))
    conn.commit()
    conn.close()
    update_overall_status(student_id)
    add_log(session.get('user_id'), 'UNLOCK', student_id, doc_type, "Mở khóa cho nộp lại")
    return jsonify({'success': True})

@app.route('/api/merge-hocba-parts/<int:student_id>', methods=['POST'])
def api_merge_hocba_parts(student_id):
    """Nối nhiều file PDF thành HOCBA_6_8 — học sinh có thể tự thực hiện"""
    try:
        from pdf_utils import merge_multiple_pdfs
        student, doc_map = get_student_with_docs(student_id)
        if not student:
            return jsonify({'error': 'Không tìm thấy học sinh.'}), 404
        files = request.files.getlist('files')
        if not files or len(files) == 0:
            return jsonify({'error': 'Chưa chọn file nào.'}), 400
        max_mb = int(get_setting('max_file_size_mb', '20'))
        folder = get_student_folder(student['lop'], student['ma_hoso'], student['ho_ten_khong_dau'])
        dest = os.path.join(folder, 'HOCBA_6_8.pdf')
        bk_dir = os.path.join(os.environ.get('DATA_DIR', os.path.dirname(__file__)), 'backups', student['ma_hoso'])
        dest_path, err = merge_multiple_pdfs(files, dest, bk_dir, 'HOCBA_6_8', max_mb)
        if err:
            return jsonify({'error': err}), 400
        conn = get_db()
        now = datetime.now().isoformat()
        conn.execute("DELETE FROM documents WHERE student_id=? AND doc_type='HOCBA_6_8'", (student_id,))
        conn.execute("INSERT INTO documents (student_id,doc_type,file_name,file_path,status,uploaded_at) VALUES (?,?,?,?,?,?)",
                     (student_id, 'HOCBA_6_8', 'HOCBA_6_8.pdf', dest_path, 'DA_NOP_CHO_KIEM_TRA', now))
        conn.commit()
        conn.close()
        update_overall_status(student_id)
        add_log(None, 'UPLOAD_MERGE', student_id, 'HOCBA_6_8', f"Nối {len(files)} file thành HOCBA_6_8")
        return jsonify({'success': True, 'message': f'Đã nối {len(files)} file thành Học bạ 6-8 thành công!'})
    except Exception as e:
        return jsonify({'error': f'Lỗi: {str(e)}'}), 500

@app.route('/api/merge-transcript/<int:student_id>', methods=['POST'])
def api_merge_transcript(student_id):
    student, doc_map = get_student_with_docs(student_id)
    if not student:
        return jsonify({'error': 'Không tìm thấy học sinh.'}), 404
    folder = get_student_folder(student['lop'], student['ma_hoso'], student['ho_ten_khong_dau'])
    dest, err = merge_transcripts(folder, student['ma_hoso'], doc_map)
    if err:
        return jsonify({'error': err}), 400
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute("DELETE FROM documents WHERE student_id=? AND doc_type='HOCBA'", (student_id,))
    conn.execute("INSERT INTO documents (student_id,doc_type,file_name,file_path,status,uploaded_at) VALUES (?,?,?,?,?,?)",
                 (student_id, 'HOCBA', 'HOCBA.pdf', dest, 'DA_NOP_CHO_KIEM_TRA', now))
    conn.commit()
    conn.close()
    update_overall_status(student_id)
    add_log(session.get('user_id'), 'MERGE', student_id, 'HOCBA', "Nối học bạ thành công")
    return jsonify({'success': True, 'message': f"Đã nối học bạ cho {student['ho_ten']}."})

@app.route('/api/merge-transcript-class/<class_name>', methods=['POST'])
@login_required
def api_merge_class(class_name):
    conn = get_db()
    students = conn.execute("SELECT * FROM students WHERE lop=?", (class_name,)).fetchall()
    conn.close()
    ok, fail = [], []
    for s in students:
        s = dict(s)
        doc_map = get_student_docs(s['id'])
        folder = get_student_folder(s['lop'], s['ma_hoso'], s['ho_ten_khong_dau'])
        dest, err = merge_transcripts(folder, s['ma_hoso'], doc_map)
        if err:
            fail.append({'ho_ten': s['ho_ten'], 'ly_do': err})
        else:
            conn2 = get_db()
            now = datetime.now().isoformat()
            conn2.execute("DELETE FROM documents WHERE student_id=? AND doc_type='HOCBA'", (s['id'],))
            conn2.execute("INSERT INTO documents (student_id,doc_type,file_name,file_path,status,uploaded_at) VALUES (?,?,?,?,?,?)",
                         (s['id'], 'HOCBA', 'HOCBA.pdf', dest, 'DA_NOP_CHO_KIEM_TRA', now))
            conn2.commit()
            conn2.close()
            update_overall_status(s['id'])
            ok.append(s['ho_ten'])
    return jsonify({'success_count': len(ok), 'fail_count': len(fail), 'failures': fail})

@app.route('/api/merge-transcript-all', methods=['POST'])
@login_required
@admin_required
def api_merge_all():
    conn = get_db()
    students = conn.execute("SELECT * FROM students").fetchall()
    conn.close()
    ok, fail = [], []
    for s in students:
        s = dict(s)
        doc_map = get_student_docs(s['id'])
        folder = get_student_folder(s['lop'], s['ma_hoso'], s['ho_ten_khong_dau'])
        dest, err = merge_transcripts(folder, s['ma_hoso'], doc_map)
        if err:
            fail.append({'ho_ten': s['ho_ten'], 'lop': s['lop'], 'ly_do': err})
        else:
            conn2 = get_db()
            now = datetime.now().isoformat()
            conn2.execute("DELETE FROM documents WHERE student_id=? AND doc_type='HOCBA'", (s['id'],))
            conn2.execute("INSERT INTO documents (student_id,doc_type,file_name,file_path,status,uploaded_at) VALUES (?,?,?,?,?,?)",
                         (s['id'], 'HOCBA', 'HOCBA.pdf', dest, 'DA_NOP_CHO_KIEM_TRA', now))
            conn2.commit()
            conn2.close()
            update_overall_status(s['id'])
            ok.append(s['ho_ten'])
    return jsonify({'success_count': len(ok), 'fail_count': len(fail), 'failures': fail})

@app.route('/api/export-excel')
@login_required
def api_export_excel():
    class_name = request.args.get('class', 'ALL')
    conn = get_db()
    if class_name == 'ALL':
        rows = conn.execute("SELECT * FROM students ORDER BY lop, stt").fetchall()
    else:
        rows = conn.execute("SELECT * FROM students WHERE lop=? ORDER BY stt", (class_name,)).fetchall()
    conn.close()
    students = enrich_students(rows)
    buf = export_excel(students, class_name)
    fname = f"HoSo_{class_name}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return send_file(buf, as_attachment=True, download_name=fname,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/download-template')
@login_required
@admin_required
def download_template():
    """Tạo và tải file Excel mẫu để import danh sách học sinh"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Danh sách học sinh"
    from openpyxl.styles import Font, PatternFill, Alignment
    # Header
    headers = ['ma_hoso', 'lop', 'stt', 'ho_ten', 'ngay_sinh', 'ghi_chu']
    header_labels = ['Mã hồ sơ', 'Lớp', 'STT', 'Họ tên', 'Ngày sinh', 'Ghi chú']
    for col, (key, label) in enumerate(zip(headers, header_labels), 1):
        cell = ws.cell(row=1, column=col, value=key)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='1565C0')
        cell.alignment = Alignment(horizontal='center')
        ws.column_dimensions[cell.column_letter].width = 18
        ws.cell(row=2, column=col, value=label).font = Font(italic=True, color='555555')
    # Dữ liệu mẫu
    samples = [
        ['9B1_001', '9B1', 1, 'Nguyễn Văn An', '12/05/2011', ''],
        ['9B1_002', '9B1', 2, 'Trần Thị Bình', '03/07/2011', ''],
        ['9B2_001', '9B2', 1, 'Lê Minh Châu',  '25/09/2011', ''],
    ]
    for i, row in enumerate(samples, 3):
        for j, val in enumerate(row, 1):
            ws.cell(row=i, column=j, value=val)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True,
                     download_name='danh_sach_hoc_sinh_mau.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/api/download-student-zip/<int:student_id>')
@login_required
def api_download_student_zip(student_id):
    student, doc_map = get_student_with_docs(student_id)
    if not student:
        return jsonify({'error': 'Không tìm thấy'}), 404
    buf = create_student_zip(student, doc_map)
    fname = f"{student['ma_hoso']}_{student['ho_ten_khong_dau']}.zip"
    return send_file(buf, as_attachment=True, download_name=fname, mimetype='application/zip')

@app.route('/api/download-class-zip/<class_name>')
@login_required
def api_download_class_zip(class_name):
    conn = get_db()
    rows = conn.execute("SELECT * FROM students WHERE lop=? ORDER BY stt", (class_name,)).fetchall()
    conn.close()
    students = enrich_students(rows)
    buf = create_class_zip(class_name, students)
    fname = f"HoSo_Lop_{class_name}_{datetime.now().strftime('%Y%m%d')}.zip"
    return send_file(buf, as_attachment=True, download_name=fname, mimetype='application/zip')

@app.route('/api/download-all-zip')
@login_required
@admin_required
def api_download_all_zip():
    conn = get_db()
    rows = conn.execute("SELECT * FROM students ORDER BY lop, stt").fetchall()
    conn.close()
    students = enrich_students(rows)
    buf = create_all_zip(students)
    fname = f"HoSo_ToanKhoi_{datetime.now().strftime('%Y%m%d')}.zip"
    return send_file(buf, as_attachment=True, download_name=fname, mimetype='application/zip')

@app.route('/api/import-students', methods=['POST'])
@login_required
@admin_required
def api_import_students():
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'Chưa chọn file.'}), 400
    ext = file.filename.rsplit('.', 1)[-1].lower()
    rows_data = []
    try:
        if ext in ('xlsx', 'xls'):
            wb = openpyxl.load_workbook(file, read_only=True)
            ws = wb.active
            headers = [str(c.value).strip() if c.value else '' for c in next(ws.iter_rows())]
            for row in ws.iter_rows(min_row=2, values_only=True):
                if any(v for v in row):
                    def _cell_str(v):
                        if v is None:
                            return ''
                        # openpyxl trả ngày dưới dạng datetime
                        try:
                            from datetime import datetime as _dt
                            if isinstance(v, _dt):
                                return v.strftime('%d/%m/%Y')
                        except Exception:
                            pass
                        return str(v).strip()
                    rows_data.append(dict(zip(headers, [_cell_str(v) for v in row])))
        elif ext == 'csv':
            import csv, io as _io
            content = file.read().decode('utf-8-sig')
            reader = csv.DictReader(_io.StringIO(content))
            for row in reader:
                rows_data.append({k.strip(): v.strip() for k, v in row.items()})
        else:
            return jsonify({'error': 'Chỉ hỗ trợ Excel (.xlsx) hoặc CSV.'}), 400
    except Exception as e:
        return jsonify({'error': f'Lỗi đọc file: {str(e)}'}), 400

    conn = get_db()
    overwrite = request.form.get('overwrite', '1') == '1'  # mặc định ghi đè (hành vi cũ)
    # Lấy danh sách ma_hoso đã tồn tại
    existing_ma = {r['ma_hoso'] for r in conn.execute('SELECT ma_hoso FROM students').fetchall()}
    count, skipped, errors = 0, 0, []
    for i, r in enumerate(rows_data, 2):
        ma_hoso = r.get('ma_hoso', '').strip()
        lop = r.get('lop', '').strip()
        stt_raw = r.get('stt', '').strip()
        try:
            stt = str(int(float(stt_raw))) if stt_raw else ''
        except (ValueError, TypeError):
            stt = stt_raw
        ho_ten = r.get('ho_ten', '').strip()
        ngay_sinh_raw = r.get('ngay_sinh', '').strip()
        if ngay_sinh_raw:
            import re as _re
            m = _re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})', ngay_sinh_raw)
            if m:
                ngay_sinh = f"{m.group(3).zfill(2)}/{m.group(2).zfill(2)}/{m.group(1)}"
            else:
                ngay_sinh = ngay_sinh_raw
        else:
            ngay_sinh = ''
        if not all([ma_hoso, lop, ho_ten]):
            errors.append(f"Dòng {i}: thiếu thông tin bắt buộc.")
            continue
        # Kiểm tra trùng
        if ma_hoso in existing_ma and not overwrite:
            skipped += 1
            continue
        ho_ten_khong_dau = to_ascii(ho_ten)
        now = datetime.now().isoformat()
        try:
            conn.execute("""INSERT OR REPLACE INTO students
                            (ma_hoso,lop,stt,ho_ten,ho_ten_khong_dau,ngay_sinh,status_overall,created_at,updated_at)
                            VALUES (?,?,?,?,?,?,?,?,?)""",
                         (ma_hoso, lop, stt, ho_ten, ho_ten_khong_dau, ngay_sinh, 'CHUA_NOP', now, now))
            count += 1
        except Exception as e:
            errors.append(f"Dòng {i}: {str(e)}")
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'imported': count, 'skipped': skipped, 'errors': errors})

@app.route('/api/preview-import', methods=['POST'])
@login_required
@admin_required
def api_preview_import():
    """Phân tích file Excel: trả về danh sách mới / trùng (dựa vào ma_hoso)."""
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'Chưa chọn file.'}), 400
    ext = file.filename.rsplit('.', 1)[-1].lower()
    rows_data = []
    try:
        if ext in ('xlsx', 'xls'):
            wb = openpyxl.load_workbook(file, read_only=True)
            ws = wb.active
            headers = [str(c.value).strip() if c.value else '' for c in next(ws.iter_rows())]
            for row in ws.iter_rows(min_row=2, values_only=True):
                if any(v for v in row):
                    def _cs(v):
                        if v is None: return ''
                        try:
                            from datetime import datetime as _dt
                            if isinstance(v, _dt): return v.strftime('%d/%m/%Y')
                        except Exception: pass
                        return str(v).strip()
                    rows_data.append(dict(zip(headers, [_cs(v) for v in row])))
        elif ext == 'csv':
            import csv, io as _io
            content = file.read().decode('utf-8-sig')
            reader = csv.DictReader(_io.StringIO(content))
            for row in reader:
                rows_data.append({k.strip(): v.strip() for k, v in row.items()})
        else:
            return jsonify({'error': 'Chỉ hỗ trợ .xlsx hoặc .csv'}), 400
    except Exception as e:
        return jsonify({'error': f'Lỗi đọc file: {str(e)}'}), 400

    conn = get_db()
    existing_ma = {r['ma_hoso']: dict(r) for r in conn.execute('SELECT ma_hoso, ho_ten, lop FROM students').fetchall()}
    conn.close()

    new_list, dup_list, err_list = [], [], []
    for i, r in enumerate(rows_data, 2):
        ma = r.get('ma_hoso', '').strip()
        ho_ten = r.get('ho_ten', '').strip()
        lop = r.get('lop', '').strip()
        if not all([ma, ho_ten, lop]):
            err_list.append({'row': i, 'reason': 'Thiếu thông tin bắt buộc'})
            continue
        if ma in existing_ma:
            dup_list.append({'ma_hoso': ma, 'ho_ten_moi': ho_ten, 'lop_moi': lop,
                             'ho_ten_cu': existing_ma[ma]['ho_ten'], 'lop_cu': existing_ma[ma]['lop']})
        else:
            new_list.append({'ma_hoso': ma, 'ho_ten': ho_ten, 'lop': lop})
    return jsonify({'success': True, 'new': new_list, 'duplicates': dup_list, 'errors': err_list,
                    'total': len(rows_data)})

@app.route('/api/fix-data', methods=['POST'])
@login_required
@admin_required
def api_fix_data():
    """Dọn dữ liệu cũ: chuẩn hóa stt (1.0→1) và ngày sinh (YYYY-MM-DD→dd/mm/YYYY)."""
    import re
    conn = get_db()
    rows = conn.execute("SELECT id, stt, ngay_sinh FROM students").fetchall()
    fixed = 0
    for row in rows:
        new_stt = row['stt']
        new_date = row['ngay_sinh']
        changed = False
        # Fix STT: "1.0" → "1"
        if new_stt:
            try:
                clean = str(int(float(new_stt.strip())))
                if clean != new_stt.strip():
                    new_stt = clean
                    changed = True
            except (ValueError, AttributeError):
                pass
        # Fix ngày sinh: YYYY-MM-DD... → dd/mm/YYYY
        if new_date:
            m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})', new_date.strip())
            if m:
                new_date = f"{m.group(3).zfill(2)}/{m.group(2).zfill(2)}/{m.group(1)}"
                changed = True
        if changed:
            conn.execute("UPDATE students SET stt=?, ngay_sinh=? WHERE id=?",
                         (new_stt, new_date, row['id']))
            fixed += 1
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'fixed': fixed, 'message': f'Đã chuẩn hóa {fixed} bản ghi.'})

@app.route('/api/settings', methods=['POST'])
@login_required
@admin_required
def api_settings():
    data = request.get_json()
    for key in ['phase', 'max_file_size_mb']:
        if key in data:
            set_setting(key, str(data[key]))
    return jsonify({'success': True})

@app.route('/admin/import')
@login_required
@admin_required
def admin_import():
    return render_template('admin_import.html')

@app.route('/admin/settings')
@login_required
@admin_required
def admin_settings():
    phase = get_setting('phase', '1')
    max_mb = get_setting('max_file_size_mb', '5')
    conn = get_db()
    teachers = conn.execute("SELECT * FROM users WHERE role IN ('teacher','admin') ORDER BY full_name").fetchall()
    classes = [r['lop'] for r in conn.execute("SELECT DISTINCT lop FROM students ORDER BY lop").fetchall()]
    conn.close()
    # Tính dung lượng để monitor quota PythonAnywhere
    disk_info = {'uploads_mb': 0, 'backups_mb': 0, 'db_mb': 0, 'total_mb': 0, 'pct': 0, 'quota_mb': 512}
    try:
        from file_utils import UPLOAD_FOLDER, BACKUP_FOLDER
        from database import DB_PATH as _db_path
        def _folder_mb(path):
            total = 0
            if os.path.exists(path):
                for root, _, files in os.walk(path):
                    for fn in files:
                        try: total += os.path.getsize(os.path.join(root, fn))
                        except OSError: pass
            return round(total / 1024 / 1024, 1)
        disk_info['uploads_mb'] = _folder_mb(UPLOAD_FOLDER)
        disk_info['backups_mb'] = _folder_mb(BACKUP_FOLDER)
        disk_info['db_mb']      = round(os.path.getsize(_db_path) / 1024 / 1024, 2) if os.path.exists(_db_path) else 0
        disk_info['total_mb']   = disk_info['uploads_mb'] + disk_info['backups_mb'] + disk_info['db_mb']
        disk_info['pct']        = min(round(disk_info['total_mb'] / disk_info['quota_mb'] * 100, 1), 100)
    except Exception:
        pass
    return render_template('admin_settings.html', phase=phase, max_mb=max_mb,
                           teachers=teachers, classes=classes, disk_info=disk_info)

@app.route('/api/add-teacher', methods=['POST'])
@login_required
@admin_required
def api_add_teacher():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    full_name = data.get('full_name', '').strip()
    assigned_class = data.get('assigned_class', '').strip()
    if not username or not password:
        return jsonify({'error': 'Thiếu tên đăng nhập hoặc mật khẩu.'}), 400
    conn = get_db()
    try:
        conn.execute("INSERT INTO users (username,password_hash,role,full_name,assigned_class,created_at) VALUES (?,?,?,?,?,?)",
                     (username, generate_password_hash(password), 'teacher', full_name, assigned_class, datetime.now().isoformat()))
        conn.commit()
    except Exception as e:
        conn.close()
        return jsonify({'error': f'Lỗi: {str(e)}'}), 400
    conn.close()
    return jsonify({'success': True})

@app.route('/api/change-password', methods=['POST'])
@login_required
def api_change_password():
    data = request.get_json()
    old_pw = data.get('old_password', '')
    new_pw = data.get('new_password', '').strip()
    if not new_pw or len(new_pw) < 6:
        return jsonify({'error': 'Mật khẩu mới phải có ít nhất 6 ký tự.'}), 400
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (session['user_id'],)).fetchone()
    if not check_password_hash(user['password_hash'], old_pw):
        conn.close()
        return jsonify({'error': 'Mật khẩu cũ không đúng.'}), 400
    conn.execute("UPDATE users SET password_hash=? WHERE id=?",
                 (generate_password_hash(new_pw), session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/edit-student', methods=['POST'])
@login_required
def api_edit_student():
    """Chỉnh sửa thông tin học sinh. Giáo viên/admin được phép."""
    data = request.get_json()
    student_id = data.get('student_id')
    if not student_id:
        return jsonify({'error': 'Thiếu student_id.'}), 400
    # Kiểm tra quyền: chỉ teacher/admin mới được sửa
    if session.get('role') not in ('teacher', 'admin'):
        return jsonify({'error': 'Bạn không có quyền chỉnh sửa.'}), 403
    ho_ten = (data.get('ho_ten') or '').strip()
    ngay_sinh = (data.get('ngay_sinh') or '').strip()
    lop = (data.get('lop') or '').strip()
    stt = (data.get('stt') or '').strip()
    ghi_chu = (data.get('ghi_chu') or '').strip()
    if not ho_ten:
        return jsonify({'error': 'Họ tên không được để trống.'}), 400
    ho_ten_khong_dau = to_ascii(ho_ten)
    try:
        conn = get_db()
        conn.execute("""UPDATE students SET ho_ten=?, ho_ten_khong_dau=?, ngay_sinh=?,
                        lop=?, stt=?, note=?, updated_at=? WHERE id=?""",
                     (ho_ten, ho_ten_khong_dau, ngay_sinh, lop, stt, ghi_chu,
                      datetime.now().isoformat(), student_id))
        conn.commit()
        conn.close()
        add_log(None, 'edit_student', student_id=student_id, detail=f"GV sửa: {ho_ten}")
    except Exception as e:
        return jsonify({'error': f'Lỗi cập nhật: {str(e)}'}), 500
    return jsonify({'success': True, 'message': 'Đã cập nhật thông tin học sinh.'})

@app.route('/api/delete-student', methods=['POST'])
@login_required
def api_delete_student():
    """Xóa học sinh và toàn bộ file đi kèm (chỉ teacher/admin)."""
    if session.get('role') not in ('teacher', 'admin'):
        return jsonify({'error': 'Bạn không có quyền xóa học sinh.'}), 403
    data = request.get_json(force=True) or {}
    student_id = data.get('student_id')
    if not student_id:
        return jsonify({'error': 'Thiếu student_id.'}), 400
    conn = get_db()
    row = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Không tìm thấy học sinh.'}), 404
    # Xóa document records + backup file_path (tuỳ chọn – chỉ xóa record, giữ file)
    conn.execute("DELETE FROM documents WHERE student_id=?", (student_id,))
    conn.execute("DELETE FROM students WHERE id=?", (student_id,))
    conn.commit()
    conn.close()
    add_log(session.get('user_id'), 'DELETE_STUDENT', student_id, None,
            f"Xóa HS: {row['ho_ten']} - Lớp {row['lop']}")
    return jsonify({'success': True, 'message': f"Đã xóa học sinh {row['ho_ten']}."})

@app.route('/api/add-student', methods=['POST'])
@login_required
def api_add_student():
    """Thêm học sinh thủ công (chỉ teacher/admin)."""
    if session.get('role') not in ('teacher', 'admin'):
        return jsonify({'error': 'Bạn không có quyền thêm học sinh.'}), 403
    data = request.get_json(force=True) or {}
    ho_ten = (data.get('ho_ten') or '').strip()
    lop = (data.get('lop') or '').strip()
    stt = (data.get('stt') or '1').strip()
    ngay_sinh = (data.get('ngay_sinh') or '').strip()
    if not ho_ten or not lop:
        return jsonify({'error': 'Họ tên và lớp không được để trống.'}), 400
    ho_ten_khong_dau = to_ascii(ho_ten)
    now = datetime.now().isoformat()
    # Tạo mã hồ sơ tự động: LOP_STT_HOTENKD
    ma_hoso = f"{to_ascii(lop)}_{stt}_{ho_ten_khong_dau}"[:60]
    try:
        conn = get_db()
        conn.execute("""INSERT INTO students
                        (ma_hoso,lop,stt,ho_ten,ho_ten_khong_dau,ngay_sinh,status_overall,created_at,updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                     (ma_hoso, lop, stt, ho_ten, ho_ten_khong_dau, ngay_sinh,
                      'CHUA_NOP', now, now))
        conn.commit()
        new_id = conn.execute("SELECT id FROM students WHERE ma_hoso=?", (ma_hoso,)).fetchone()['id']
        conn.close()
        add_log(session.get('user_id'), 'ADD_STUDENT', new_id, None,
                f"Thêm HS: {ho_ten} - Lớp {lop}")
        return jsonify({'success': True, 'message': f"Đã thêm học sinh {ho_ten}.", 'id': new_id})
    except Exception as e:
        return jsonify({'error': f'Lỗi: {str(e)}'}), 500

@app.route('/view-file/<int:student_id>/<doc_type>')
def view_file(student_id, doc_type):
    """Xem file PDF — redirect sang Drive URL nếu là Drive file."""
    student, doc_map = get_student_with_docs(student_id)
    doc = doc_map.get(doc_type.upper(), {})
    fp  = doc.get('file_path')
    if not fp:
        return '<p style="font-family:sans-serif;padding:20px">❌ File chưa được nộp. Vui lòng nộp lại.</p>', 404
    import drive_utils
    if drive_utils.is_drive(fp):
        return redirect(drive_utils.view_url(fp))
    if not os.path.exists(fp):
        return '<p style="font-family:sans-serif;padding:20px">❌ File không tồn tại. Vui lòng nộp lại.</p>', 404
    return send_file(fp, mimetype='application/pdf')

def create_dirs():
    """Tạo thư mục cần thiết khi khởi động"""
    _base = os.environ.get('DATA_DIR', os.path.dirname(__file__))
    os.makedirs(os.path.join(_base, 'uploads'), exist_ok=True)
    os.makedirs(os.path.join(_base, 'backups'), exist_ok=True)

if __name__ == '__main__':
    create_dirs()
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
else:
    # Chạy qua gunicorn (Render)
    create_dirs()
    init_db()
