import os
import zipfile
import io
import shutil
from datetime import datetime
from pypdf import PdfWriter, PdfReader
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

_BASE = os.environ.get('DATA_DIR', os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(_BASE, 'uploads')
BACKUP_FOLDER = os.path.join(_BASE, 'backups')

ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}

def merge_multiple_pdfs(file_objects, dest_path, backup_dir=None, doc_type='FILE', max_mb=20):
    """Nhận danh sách file objects, kiểm tra, nối thành một PDF duy nhất"""
    if not file_objects:
        return None, 'Chưa chọn file nào.'
    writer = PdfWriter()
    for f in file_objects:
        # Kiểm tra dung lượng
        f.seek(0, 2)
        size = f.tell()
        f.seek(0)
        if size == 0:
            return None, f'File "{f.filename}" rỗng.'
        if size > max_mb * 1024 * 1024:
            return None, f'File "{f.filename}" quá lớn (tối đa {max_mb}MB).'
        ext = (f.filename or '').rsplit('.', 1)[-1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return None, f'File "{f.filename}" không hợp lệ. Chỉ nhận PDF, JPG, PNG.'
        try:
            if ext == 'pdf':
                reader = PdfReader(f)
                if len(reader.pages) == 0:
                    return None, f'File PDF "{f.filename}" không có trang nào.'
                for page in reader.pages:
                    writer.add_page(page)
            else:
                # Chuyển ảnh sang PDF rồi thêm vào
                from PIL import Image
                img = Image.open(f)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                tmp = io.BytesIO()
                img.save(tmp, 'PDF', resolution=150)
                tmp.seek(0)
                reader = PdfReader(tmp)
                for page in reader.pages:
                    writer.add_page(page)
        except Exception as e:
            return None, f'Lỗi đọc file "{f.filename}": {str(e)}'
    # Backup file cũ nếu có
    if backup_dir and os.path.exists(dest_path):
        os.makedirs(backup_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        shutil.copy2(dest_path, os.path.join(backup_dir, f"backup_{doc_type}_{ts}.pdf"))
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, 'wb') as out:
            writer.write(out)
        return dest_path, None
    except Exception as e:
        return None, f'Lỗi lưu file: {str(e)}'


def merge_transcripts(student_folder, ma_hoso, doc_map):
    """Nối học bạ 6-8 và học bạ 9 thành học bạ hoàn chỉnh"""
    path_6_8 = doc_map.get('HOCBA_6_8', {}).get('file_path')
    path_9 = doc_map.get('HOCBA_9', {}).get('file_path')

    errors = []
    if not path_6_8 or not os.path.exists(path_6_8):
        errors.append('Thiếu file HOCBA_6_8.pdf')
    if not path_9 or not os.path.exists(path_9):
        errors.append('Thiếu file HOCBA_9.pdf')
    if errors:
        return None, '; '.join(errors)

    dest = os.path.join(student_folder, 'HOCBA.pdf')
    # Backup file cũ
    if os.path.exists(dest):
        import shutil
        ts = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        bk_dir = os.path.join(BACKUP_FOLDER, ma_hoso)
        os.makedirs(bk_dir, exist_ok=True)
        shutil.copy2(dest, os.path.join(bk_dir, f"backup_HOCBA_{ts}.pdf"))

    try:
        writer = PdfWriter()
        for path in [path_6_8, path_9]:
            reader = PdfReader(path)
            for page in reader.pages:
                writer.add_page(page)
        with open(dest, 'wb') as f:
            writer.write(f)
        return dest, None
    except Exception as e:
        return None, f'Lỗi khi nối PDF: {str(e)}'

def export_excel(students_data, class_name=None):
    """Xuất danh sách hồ sơ ra Excel"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = class_name or 'Toàn khối'

    header_fill = PatternFill("solid", fgColor="1565C0")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    thin = Side(style='thin', color='CCCCCC')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    headers = ['STT', 'Lớp', 'Họ tên', 'Ngày sinh', 'Giấy khai sinh',
               'CCCD', 'Học bạ 6-8', 'Học bạ 9', 'Học bạ HT', 'CN Tốt nghiệp', 'Trạng thái', 'Ghi chú', 'Cập nhật lần cuối']
    ws.append(headers)
    for col, cell in enumerate(ws[1], 1):
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center
        cell.border = border

    status_labels = {
        'CHUA_NOP': 'Chưa nộp', 'DA_NOP_CHO_KIEM_TRA': 'Chờ KT',
        'DAT': 'Đạt', 'FILE_MO': 'File mờ', 'SAI_FILE': 'Sai file',
        'THIEU_TRANG': 'Thiếu trang', 'CAN_NOP_LAI': 'Cần nộp lại', 'DA_KHOA': 'Đã khóa',
    }
    overall_labels = {
        'CHUA_NOP': 'Chưa nộp', 'TAM_DU_GIAI_DOAN_1': 'Tạm đủ GĐ1',
        'CHUA_DU': 'Chưa đủ', 'CAN_SUA': 'Cần sửa', 'DU_HO_SO_CHINH_THUC': 'Đủ hồ sơ',
    }
    doc_keys = ['GIAYKHAISINH', 'CCCD', 'HOCBA_6_8', 'HOCBA_9', 'HOCBA', 'CNTN_THCS']

    for i, s in enumerate(students_data, 1):
        docs = s.get('docs', {})
        row = [
            s.get('stt', i), s.get('lop'), s.get('ho_ten'), s.get('ngay_sinh'),
        ]
        for dk in doc_keys:
            st = docs.get(dk, {}).get('status', 'CHUA_NOP')
            row.append(status_labels.get(st, st))
        row.append(overall_labels.get(s.get('status_overall', ''), s.get('status_overall', '')))
        row.append(s.get('note', ''))
        row.append(s.get('updated_at', '')[:10] if s.get('updated_at') else '')
        ws.append(row)
        for cell in ws[i + 1]:
            cell.border = border
            cell.alignment = center

    col_widths = [6, 8, 22, 12, 14, 12, 12, 10, 12, 16, 16, 20, 14]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
    ws.row_dimensions[1].height = 30

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf

def create_student_zip(student, doc_map):
    """Tạo ZIP hồ sơ của một học sinh"""
    buf = io.BytesIO()
    final_docs = ['GIAYKHAISINH', 'CCCD', 'HOCBA', 'CNTN_THCS']
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for dk in final_docs:
            fp = doc_map.get(dk, {}).get('file_path')
            if fp and os.path.exists(fp):
                zf.write(fp, f"{dk}.pdf")
    buf.seek(0)
    return buf

def create_class_zip(class_name, students_data):
    """Tạo ZIP hồ sơ cả lớp"""
    buf = io.BytesIO()
    final_docs = ['GIAYKHAISINH', 'CCCD', 'HOCBA', 'CNTN_THCS']
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for s in students_data:
            folder_name = f"{s['ma_hoso']}_{s['ho_ten_khong_dau']}"
            docs = s.get('docs', {})
            for dk in final_docs:
                fp = docs.get(dk, {}).get('file_path')
                if fp and os.path.exists(fp):
                    zf.write(fp, f"{class_name}/{folder_name}/{dk}.pdf")
    buf.seek(0)
    return buf

def create_all_zip(all_students):
    """Tạo ZIP toàn khối"""
    buf = io.BytesIO()
    final_docs = ['GIAYKHAISINH', 'CCCD', 'HOCBA', 'CNTN_THCS']
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for s in all_students:
            folder_name = f"{s['ma_hoso']}_{s['ho_ten_khong_dau']}"
            docs = s.get('docs', {})
            for dk in final_docs:
                fp = docs.get(dk, {}).get('file_path')
                if fp and os.path.exists(fp):
                    zf.write(fp, f"{s['lop']}/{folder_name}/{dk}.pdf")
    buf.seek(0)
    return buf
