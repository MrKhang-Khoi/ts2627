import os
import re
import shutil
from datetime import datetime
from werkzeug.utils import secure_filename

# DATA_DIR: trỏ đến Persistent Disk trên Render, hoặc thư mục local
_BASE = os.environ.get('DATA_DIR', os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(_BASE, 'uploads')
BACKUP_FOLDER = os.path.join(_BASE, 'backups')
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}
MAX_FILE_SIZE_MB = 20

DOC_TYPES = ['GIAYKHAISINH', 'CCCD', 'HOCBA_6_8', 'HOCBA_9', 'HOCBA', 'CNTN_THCS', 'ANH_THE', 'UU_TIEN']

# Thứ tự hiển thị và nộp theo hệ thống chính thức
DISPLAY_ORDER = ['GIAYKHAISINH', 'CNTN_THCS', 'HOCBA_6_8', 'CCCD', 'ANH_THE', 'UU_TIEN']
# Tài liệu không bắt buộc (không có dấu *)
OPTIONAL_DOCS = {'UU_TIEN'}
# Thứ tự file trong ZIP tải xuống
ZIP_ORDER = [
    ('GIAYKHAISINH', '01_GiayKhaiSinh'),
    ('CNTN_THCS',    '02_ChungNhanTotNghiep'),
    ('HOCBA',        '03_HocBa'),
    ('HOCBA_6_8',    '03_HocBa'),
    ('CCCD',         '04_CCCD'),
    ('ANH_THE',      '05_AnhThe'),
    ('UU_TIEN',      '06_UuTien'),
]
DOC_LABELS = {
    'GIAYKHAISINH': 'Bản sao Giấy khai sinh',
    'CCCD': 'CCCD / Mã định danh',
    'HOCBA_6_8': 'Học bạ (lớp 6-9)',
    'HOCBA_9': 'Học bạ lớp 9',
    'HOCBA': 'Học bạ hoàn chỉnh',
    'CNTN_THCS': 'Chứng nhận tốt nghiệp THCS',
    'ANH_THE': 'Ảnh thẻ 4x6',
    'UU_TIEN': 'Giấy xác nhận ưu tiên (nếu có)',
}
STATUS_LABELS = {
    'CHUA_NOP': 'Chưa nộp',
    'DA_NOP_CHO_KIEM_TRA': 'Đã nộp - Chờ kiểm tra',
    'DAT': 'Đạt',
    'FILE_MO': 'File mờ',
    'SAI_FILE': 'Sai file',
    'THIEU_TRANG': 'Thiếu trang',
    'CAN_NOP_LAI': 'Cần nộp lại',
    'DA_KHOA': 'Đã khóa',
}
OVERALL_LABELS = {
    'CHUA_NOP': 'Chưa nộp',
    'TAM_DU_GIAI_DOAN_1': 'Tạm đủ giai đoạn 1',
    'CHUA_DU': 'Chưa đủ hồ sơ',
    'CAN_SUA': 'Cần nộp lại',
    'DU_HO_SO_CHINH_THUC': 'Đủ hồ sơ chính thức',
}

def to_ascii(text):
    """Chuyển tiếng Việt có dấu sang không dấu"""
    replacements = {
        'à':'a','á':'a','ả':'a','ã':'a','ạ':'a',
        'ă':'a','ắ':'a','ằ':'a','ẳ':'a','ẵ':'a','ặ':'a',
        'â':'a','ấ':'a','ầ':'a','ẩ':'a','ẫ':'a','ậ':'a',
        'è':'e','é':'e','ẻ':'e','ẽ':'e','ẹ':'e',
        'ê':'e','ế':'e','ề':'e','ể':'e','ễ':'e','ệ':'e',
        'ì':'i','í':'i','ỉ':'i','ĩ':'i','ị':'i',
        'ò':'o','ó':'o','ỏ':'o','õ':'o','ọ':'o',
        'ô':'o','ố':'o','ồ':'o','ổ':'o','ỗ':'o','ộ':'o',
        'ơ':'o','ớ':'o','ờ':'o','ở':'o','ỡ':'o','ợ':'o',
        'ù':'u','ú':'u','ủ':'u','ũ':'u','ụ':'u',
        'ư':'u','ứ':'u','ừ':'u','ử':'u','ữ':'u','ự':'u',
        'ỳ':'y','ý':'y','ỷ':'y','ỹ':'y','ỵ':'y',
        'đ':'d',
    }
    result = text.lower()
    for k, v in replacements.items():
        result = result.replace(k, v)
        result = result.replace(k.upper(), v.upper())
    # Giữ chữ cái và số, xóa khoảng trắng và ký tự đặc biệt
    words = re.findall(r'[a-zA-Z0-9]+', result)
    return ''.join(w.capitalize() for w in words)

def get_student_folder(lop, ma_hoso, ho_ten_khong_dau):
    folder = os.path.join(UPLOAD_FOLDER, lop, f"{ma_hoso}_{ho_ten_khong_dau}")
    os.makedirs(folder, exist_ok=True)
    return folder

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file, student, doc_type, max_mb=None):
    """Lưu file upload, trả về (file_path, error_msg)"""
    if max_mb is None:
        max_mb = MAX_FILE_SIZE_MB
    if not file or file.filename == '':
        return None, 'Không có file nào được chọn.'
    if not allowed_file(file.filename):
        return None, 'File không hợp lệ. Vui lòng chọn file PDF, JPG hoặc PNG.'
    # Kiểm tra kích thước (đọc vào bộ nhớ tạm)
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > max_mb * 1024 * 1024:
        return None, f'File quá lớn. Vui lòng giảm dung lượng hoặc scan lại (tối đa {max_mb}MB).'
    if size == 0:
        return None, 'File rỗng, vui lòng chọn lại.'

    ext = file.filename.rsplit('.', 1)[1].lower()
    folder = get_student_folder(student['lop'], student['ma_hoso'], student['ho_ten_khong_dau'])
    dest_path = os.path.join(folder, f"{doc_type}.pdf")

    # Backup file cũ nếu tồn tại
    if os.path.exists(dest_path):
        ts = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        bk_dir = os.path.join(BACKUP_FOLDER, student['ma_hoso'])
        os.makedirs(bk_dir, exist_ok=True)
        shutil.copy2(dest_path, os.path.join(bk_dir, f"backup_{doc_type}_{ts}.pdf"))

    if ext == 'pdf':
        file.save(dest_path)
    else:
        # Chuyển ảnh sang PDF bằng Pillow
        try:
            from PIL import Image
            img = Image.open(file)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(dest_path, 'PDF', resolution=150)
        except Exception as e:
            return None, f'Không thể chuyển ảnh sang PDF: {str(e)}'

    return dest_path, None

def delete_file_to_backup(file_path, ma_hoso, doc_type):
    """Chuyển file vào backup thay vì xóa vĩnh viễn"""
    if not file_path or not os.path.exists(file_path):
        return
    ts = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    bk_dir = os.path.join(BACKUP_FOLDER, ma_hoso)
    os.makedirs(bk_dir, exist_ok=True)
    shutil.move(file_path, os.path.join(bk_dir, f"backup_{doc_type}_{ts}.pdf"))
