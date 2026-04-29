"""
drive_utils.py — Tích hợp Google Drive qua Apps Script Web App

Lưu file hồ sơ học sinh lên Google Drive (15 GB miễn phí) thay vì
disk PythonAnywhere Free (512 MB).

Cách bật: đặt 2 biến môi trường trên PythonAnywhere:
    APPS_SCRIPT_URL    = https://script.google.com/macros/s/AKfy.../exec
    APPS_SCRIPT_SECRET = chuỗi-bí-mật-bất-kỳ (giống với Script Properties trên Apps Script)

Nếu không đặt → ứng dụng tự động dùng chế độ lưu local (backward compatible).
"""

import os
import io
import base64
import json
import logging

logger = logging.getLogger(__name__)

# ===== CONFIGURATION =====
APPS_SCRIPT_URL    = os.environ.get('APPS_SCRIPT_URL', '').strip()
APPS_SCRIPT_SECRET = os.environ.get('APPS_SCRIPT_SECRET', '').strip()

# Chỉ bật Drive mode khi cả URL và SECRET đều được cấu hình
DRIVE_MODE = bool(APPS_SCRIPT_URL and APPS_SCRIPT_SECRET)

DRIVE_PREFIX = 'drive:'
_TIMEOUT     = 60  # giây timeout cho mỗi request


# ===== PATH HELPERS =====

def is_drive(path):
    """True nếu file_path là Drive file (bắt đầu bằng 'drive:')."""
    return bool(path) and str(path).startswith(DRIVE_PREFIX)


def get_id(path):
    """Lấy Drive file ID từ file_path dạng 'drive:FILE_ID'."""
    return path[len(DRIVE_PREFIX):] if is_drive(path) else None


def make_path(file_id):
    """Tạo file_path để lưu vào DB từ Drive file ID."""
    return DRIVE_PREFIX + file_id


def view_url(path):
    """URL xem file trực tiếp trên Drive (không cần đăng nhập)."""
    fid = get_id(path)
    return f'https://drive.google.com/file/d/{fid}/view' if fid else None


def download_direct_url(path):
    """URL tải file trực tiếp từ Drive."""
    fid = get_id(path)
    return f'https://drive.google.com/uc?id={fid}&export=download' if fid else None


# ===== INTERNAL API CALL =====

def _call(payload, timeout=_TIMEOUT):
    """
    Gọi Apps Script Web App với payload JSON.
    Tự động thêm secret key. Trả về dict.
    """
    if not APPS_SCRIPT_URL:
        return {'error': 'APPS_SCRIPT_URL chưa được cấu hình'}

    try:
        import requests
    except ImportError:
        return {'error': 'Thư viện requests chưa cài. Chạy: pip install requests'}

    body = dict(payload)
    body['secret'] = APPS_SCRIPT_SECRET

    try:
        resp = requests.post(
            APPS_SCRIPT_URL,
            data=json.dumps(body),
            headers={'Content-Type': 'application/json'},
            timeout=timeout,
            allow_redirects=True  # Apps Script thường redirect
        )
        resp.raise_for_status()
        result = resp.json()
        if result.get('error'):
            logger.warning(f'[drive_utils] Apps Script error: {result["error"]}')
        return result
    except Exception as ex:
        logger.error(f'[drive_utils] Request failed: {ex}')
        return {'error': f'Lỗi kết nối Drive: {str(ex)}'}


# ===== PUBLIC API =====

def upload(file_bytes, student, doc_type):
    """
    Upload PDF bytes lên Google Drive qua Apps Script.

    Args:
        file_bytes: bytes của file PDF
        student:    dict học sinh (cần 'lop', 'ma_hoso', 'ho_ten_khong_dau')
        doc_type:   loại tài liệu (GIAYKHAISINH, CCCD, v.v.)

    Returns:
        (drive_path, error) — drive_path = 'drive:FILE_ID' hoặc None nếu lỗi
    """
    if not file_bytes:
        return None, 'Không có dữ liệu file'

    content_b64 = base64.b64encode(file_bytes).decode('utf-8')
    result = _call({
        'action':      'upload',
        'lop':         student.get('lop', ''),
        'ma_hoso':     student.get('ma_hoso', ''),
        'ho_ten':      student.get('ho_ten_khong_dau', ''),
        'doc_type':    doc_type,
        'content_b64': content_b64,
    })

    if result.get('success'):
        return make_path(result['file_id']), None
    return None, result.get('error', 'Upload Drive thất bại')


def delete(file_path):
    """
    Chuyển file Drive vào Trash (không xóa vĩnh viễn).
    An toàn — không báo lỗi nếu file không tồn tại.
    """
    fid = get_id(file_path)
    if not fid:
        return
    _call({'action': 'delete', 'file_id': fid})


def download_bytes(file_path):
    """
    Tải file từ Drive về dạng bytes.

    Returns:
        (bytes, error) — bytes là None nếu có lỗi
    """
    try:
        import requests
    except ImportError:
        return None, 'requests not installed'

    url = download_direct_url(file_path)
    if not url:
        return None, 'Invalid Drive path'

    try:
        r = requests.get(url, timeout=_TIMEOUT, allow_redirects=True)
        r.raise_for_status()
        if len(r.content) < 10:
            return None, 'Drive trả về file rỗng (file có thể bị xóa hoặc không chia sẻ)'
        return r.content, None
    except Exception as ex:
        logger.error(f'[drive_utils] Download failed: {ex}')
        return None, f'Lỗi tải file từ Drive: {str(ex)}'


def test_connection():
    """
    Kiểm tra kết nối tới Apps Script. Dùng để debug.
    Returns dict với status.
    """
    if not DRIVE_MODE:
        return {'ok': False, 'reason': 'DRIVE_MODE chưa bật (thiếu APPS_SCRIPT_URL hoặc APPS_SCRIPT_SECRET)'}
    result = _call({'action': 'info', 'file_id': 'test'}, timeout=10)
    # Nếu nhận được JSON (dù là error) → kết nối thành công
    if 'error' in result and 'connect' not in result.get('error', '').lower():
        return {'ok': True, 'message': 'Kết nối Apps Script thành công'}
    if 'error' in result:
        return {'ok': False, 'reason': result['error']}
    return {'ok': True, 'message': 'Kết nối OK'}
