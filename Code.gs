/**
 * Code.gs — Apps Script Web App để lưu file hồ sơ học sinh lên Google Drive
 * 
 * HƯỚNG DẪN TRIỂN KHAI:
 * 1. Vào script.google.com → Tạo project mới
 * 2. Dán toàn bộ code này vào Code.gs
 * 3. Extensions > Apps Script > Project Settings > Script Properties
 *    → Thêm property: SECRET_KEY = <chuỗi bí mật giống APPS_SCRIPT_SECRET trong Flask>
 * 4. Deploy > New Deployment > Web App
 *    - Execute as: Me
 *    - Who has access: Anyone
 * 5. Copy Web App URL → đặt vào biến môi trường APPS_SCRIPT_URL trên PythonAnywhere
 */

const ROOT_FOLDER_NAME = 'HoSo_Lop10';

function getSecretKey() {
  return PropertiesService.getScriptProperties().getProperty('SECRET_KEY') || '';
}

// ===== ENTRY POINTS =====
function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);

    // Kiểm tra secret key
    const secret = getSecretKey();
    if (!secret || data.secret !== secret) {
      return json({ error: 'Unauthorized — sai secret key' });
    }

    switch (data.action) {
      case 'upload': return handleUpload(data);
      case 'delete': return handleDelete(data);
      case 'info':   return handleInfo(data);
      default:       return json({ error: 'Unknown action: ' + data.action });
    }
  } catch (err) {
    return json({ error: 'Server error: ' + err.message });
  }
}

function doGet(e) {
  // Dùng để kiểm tra Apps Script đang hoạt động
  return json({ status: 'running', root: ROOT_FOLDER_NAME, version: '1.2' });
}

// ===== UPLOAD FILE =====
function handleUpload(data) {
  const { lop, ma_hoso, ho_ten, doc_type, content_b64 } = data;

  if (!lop || !ma_hoso || !doc_type || !content_b64) {
    return json({ error: 'Thiếu trường: lop, ma_hoso, doc_type, content_b64' });
  }

  // Tạo cây thư mục: HoSo_Lop10 / LOP / MA_HOSO_HOTEN /
  const rootFolder = getOrCreate(null, ROOT_FOLDER_NAME);
  const lopFolder  = getOrCreate(rootFolder, lop);
  const stuName    = ma_hoso + (ho_ten ? '_' + ho_ten : '');
  const stuFolder  = getOrCreate(lopFolder, stuName);

  const fileName = doc_type + '.pdf';

  // Xóa file cũ cùng tên (thay thế bằng file mới)
  const oldFiles = stuFolder.getFilesByName(fileName);
  while (oldFiles.hasNext()) {
    oldFiles.next().setTrashed(true);
  }

  // Tạo file PDF mới từ base64
  const bytes = Utilities.base64Decode(content_b64);
  const blob  = Utilities.newBlob(bytes, 'application/pdf', fileName);
  const file  = stuFolder.createFile(blob);

  // Cho phép xem qua link (không cần đăng nhập Google)
  file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);

  const fileId = file.getId();
  return json({
    success:      true,
    file_id:      fileId,
    view_url:     'https://drive.google.com/file/d/' + fileId + '/view',
    download_url: 'https://drive.google.com/uc?id=' + fileId + '&export=download'
  });
}

// ===== XÓA FILE =====
function handleDelete(data) {
  if (!data.file_id) return json({ error: 'Thiếu file_id' });
  try {
    DriveApp.getFileById(data.file_id).setTrashed(true);
    return json({ success: true });
  } catch (e) {
    // File không tìm thấy hoặc đã xóa — vẫn trả success
    return json({ success: true, warning: 'File không tồn tại: ' + e.message });
  }
}

// ===== THÔNG TIN FILE =====
function handleInfo(data) {
  if (!data.file_id) return json({ error: 'Thiếu file_id' });
  try {
    const file = DriveApp.getFileById(data.file_id);
    const id   = data.file_id;
    return json({
      success:      true,
      name:         file.getName(),
      size_bytes:   file.getSize(),
      view_url:     'https://drive.google.com/file/d/' + id + '/view',
      download_url: 'https://drive.google.com/uc?id=' + id + '&export=download'
    });
  } catch (e) {
    return json({ error: 'File không tồn tại: ' + e.message });
  }
}

// ===== HELPERS =====

/**
 * Lấy hoặc tạo thư mục theo tên trong parent (hoặc root Drive nếu parent=null).
 */
function getOrCreate(parent, name) {
  const list = parent
    ? parent.getFoldersByName(name)
    : DriveApp.getFoldersByName(name);
  if (list.hasNext()) return list.next();
  return parent
    ? parent.createFolder(name)
    : DriveApp.createFolder(name);
}

/**
 * Trả về JSON response cho Apps Script.
 */
function json(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

/**
 * Hàm test — chạy thủ công để kiểm tra kết nối Drive.
 * Vào Apps Script editor > Run > testDriveAccess
 */
function testDriveAccess() {
  const root = getOrCreate(null, ROOT_FOLDER_NAME);
  Logger.log('✅ Drive hoạt động. Thư mục root: ' + root.getName() + ' (' + root.getId() + ')');
}
