/**
 * Code.gs — Apps Script Web App
 * - Upload/Delete/Info file hồ sơ lên Google Drive (doPost)
 * - API danh sách HS + file cho trang tải GitHub Pages (doGet)
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
 *
 * API TRANG TẢI (doGet):
 *   ?action=classes           → Danh sách lớp + số HS
 *   ?action=students&class=9A1 → Danh sách HS + file IDs của 1 lớp
 *   ?action=refresh            → Xóa cache, cập nhật lại
 */

const ROOT_FOLDER_NAME = 'HoSo_Lop10';

// Nhãn tài liệu tiếng Việt
const DOC_LABELS = {
  'GIAYKHAISINH': 'Giấy khai sinh',
  'CNTN_THCS':    'CN tốt nghiệp THCS',
  'CNHT_Lop_9':   'CN tốt nghiệp THCS',
  'HOCBA_6_9':    'Học bạ (lớp 6-9)',
  'HOCBA':        'Học bạ hoàn chỉnh',
  'CCCD':         'CCCD / Mã định danh',
  'ANH_THE':      'Ảnh thẻ 4x6',
  'UU_TIEN':      'Ưu tiên (nếu có)'
};

function getSecretKey() {
  return PropertiesService.getScriptProperties().getProperty('SECRET_KEY') || '';
}

// ===== ENTRY POINTS =====
function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const secret = getSecretKey();
    if (!secret || data.secret !== secret) {
      return json({ error: 'Unauthorized — sai secret key' });
    }

    switch (data.action) {
      case 'upload':
        clearCache_(data.lop); // Xóa cache khi upload
        return handleUpload(data);
      case 'delete':
        clearCache_(); // Xóa cache khi xóa
        return handleDelete(data);
      case 'info':   return handleInfo(data);
      default:       return json({ error: 'Unknown action: ' + data.action });
    }
  } catch (err) {
    return json({ error: 'Server error: ' + err.message });
  }
}

function doGet(e) {
  try {
    var action = (e && e.parameter && e.parameter.action) || 'status';

    switch (action) {
      case 'classes':  return handleListClasses_();
      case 'students': return handleListStudents_(e.parameter['class'] || '');
      case 'zip':      return handleZip_(e.parameter);
      case 'refresh':  return handleRefresh_();
      default:
        return json({ status: 'running', root: ROOT_FOLDER_NAME, version: '2.0' });
    }
  } catch (err) {
    return json({ error: 'Server error: ' + err.message });
  }
}

// ===== API: DANH SÁCH LỚP =====
function handleListClasses_() {
  var cache = CacheService.getScriptCache();
  var cached = cache.get('hoso_classes');
  if (cached) return json(JSON.parse(cached));

  var root = getRootFolder_();
  if (!root) return json({ error: 'Không tìm thấy thư mục ' + ROOT_FOLDER_NAME });

  var classes = [];
  var folders = root.getFolders();
  while (folders.hasNext()) {
    var f = folders.next();
    var name = f.getName();
    // Chỉ lấy folder có tên dạng lớp (9A1, 9B2, ...)
    if (/^9[AB]\d+$/i.test(name)) {
      // Đếm số HS (subfolder)
      var count = 0;
      var subs = f.getFolders();
      while (subs.hasNext()) { subs.next(); count++; }
      classes.push({ name: name, count: count });
    }
  }

  // Sắp xếp: 9A1, 9A2, ..., 9B1, 9B2, ...
  classes.sort(function(a, b) { return a.name.localeCompare(b.name); });

  var result = {
    school: 'Trường THCS Chu Văn An',
    updated_at: Utilities.formatDate(new Date(), 'Asia/Ho_Chi_Minh', 'dd/MM/yyyy HH:mm'),
    classes: classes,
    doc_labels: DOC_LABELS,
    doc_order: ['GIAYKHAISINH', 'CNTN_THCS', 'HOCBA_6_9', 'CCCD', 'ANH_THE', 'UU_TIEN']
  };

  cache.put('hoso_classes', JSON.stringify(result), 1800); // Cache 30 phút
  return json(result);
}

// ===== API: DANH SÁCH HS TRONG 1 LỚP =====
function handleListStudents_(className) {
  if (!className) return json({ error: 'Thiếu tham số class' });

  var cache = CacheService.getScriptCache();
  var cacheKey = 'hoso_class_' + className;
  var cached = cache.get(cacheKey);
  if (cached) return json(JSON.parse(cached));

  var root = getRootFolder_();
  if (!root) return json({ error: 'Không tìm thấy thư mục ' + ROOT_FOLDER_NAME });

  // Tìm folder lớp
  var classFolders = root.getFoldersByName(className);
  if (!classFolders.hasNext()) return json({ error: 'Không tìm thấy lớp ' + className });
  var classFolder = classFolders.next();

  var students = [];
  var stuFolders = classFolder.getFolders();

  while (stuFolders.hasNext()) {
    var stuFolder = stuFolders.next();
    var folderName = stuFolder.getName(); // VD: "9A1_001_Tên" hoặc "62211005976_TenKhongDau"

    // Parse tên thông minh theo format thư mục
    var parts = folderName.split('_');
    var stt = '';
    var hoTen = folderName;
    var maHoso = '';

    if (/^9[ABab]\d+$/i.test(parts[0]) && parts.length >= 3) {
      // Format: 9A1_001_Tên Học Sinh
      maHoso = parts[0] + '_' + parts[1];
      stt = parts[1].replace(/^0+/, '') || '0';
      hoTen = parts.slice(2).join(' ');
    } else if (parts.length >= 2) {
      // Format: 62211005976_TenKhongDau hoặc format khác
      maHoso = parts[0];
      hoTen = parts.slice(1).join(' ');
      // Thêm khoảng trắng vào camelCase: DoNguyenTrungKien → Do Nguyen Trung Kien
      hoTen = hoTen.replace(/([a-zàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ])([A-ZÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ])/g, '$1 $2');
    }

    // Đọc file trong thư mục HS
    var docs = {};
    var docCount = 0;
    var files = stuFolder.getFiles();

    while (files.hasNext()) {
      var file = files.next();
      var fname = file.getName();
      // Bỏ extension để lấy doc_type
      var docType = fname.replace(/\.[^.]+$/, '');
      docs[docType] = {
        file_id: file.getId(),
        name: fname
      };
      docCount++;
    }

    students.push({
      stt: stt,
      ho_ten: hoTen,
      folder_name: folderName,
      doc_count: docCount,
      docs: docs
    });
  }

  // Sắp xếp theo STT
  students.sort(function(a, b) {
    return parseInt(a.stt || '0', 10) - parseInt(b.stt || '0', 10);
  });

  var result = {
    class_name: className,
    count: students.length,
    students: students
  };

  cache.put(cacheKey, JSON.stringify(result), 1800); // Cache 30 phút
  return json(result);
}

// ===== API: XÓA CACHE (CẬP NHẬT LẠI) =====
function handleRefresh_() {
  clearCache_();
  return json({ success: true, message: 'Cache đã được xóa. Lần truy cập tiếp theo sẽ đọc dữ liệu mới.' });
}

// ===== API: TẢI ZIP HỒ SƠ =====
function handleZip_(params) {
  var className = params['class'];
  var folder = params['folder'];
  var prefix = params['prefix'] || '';

  if (!className || !folder) return json({ error: 'Thiếu tham số class và folder' });

  var root = getRootFolder_();
  if (!root) return json({ error: 'Không tìm thấy thư mục gốc' });

  var classFolders = root.getFoldersByName(className);
  if (!classFolders.hasNext()) return json({ error: 'Không tìm thấy lớp ' + className });
  var classFolder = classFolders.next();

  var stuFolders = classFolder.getFoldersByName(folder);
  if (!stuFolders.hasNext()) return json({ error: 'Không tìm thấy thư mục HS' });
  var stuFolder = stuFolders.next();

  var blobs = [];
  var files = stuFolder.getFiles();
  while (files.hasNext()) {
    var f = files.next();
    var blob = f.getBlob();
    // Đổi tên file: TenHS_Lop_TenFile.pdf
    if (prefix) blob.setName(prefix + '_' + f.getName());
    blobs.push(blob);
  }

  if (!blobs.length) return json({ error: 'Thư mục trống, chưa có file nào' });

  var zipName = 'HoSo_' + (prefix || folder) + '.zip';
  var zip = Utilities.zip(blobs, zipName);

  return json({
    success: true,
    content: Utilities.base64Encode(zip.getBytes()),
    name: zipName
  });
}

// ===== UPLOAD FILE =====
function handleUpload(data) {
  const { lop, ma_hoso, ho_ten, doc_type, content_b64 } = data;

  if (!lop || !ma_hoso || !doc_type || !content_b64) {
    return json({ error: 'Thiếu trường: lop, ma_hoso, doc_type, content_b64' });
  }

  const rootFolder = getOrCreate(null, ROOT_FOLDER_NAME);
  const lopFolder  = getOrCreate(rootFolder, lop);
  const stuName    = ma_hoso + (ho_ten ? '_' + ho_ten : '');
  const stuFolder  = getOrCreate(lopFolder, stuName);

  const fileName = doc_type + '.pdf';

  // Xóa file cũ cùng tên
  const oldFiles = stuFolder.getFilesByName(fileName);
  while (oldFiles.hasNext()) {
    oldFiles.next().setTrashed(true);
  }

  // Tạo file PDF mới từ base64
  const bytes = Utilities.base64Decode(content_b64);
  const blob  = Utilities.newBlob(bytes, 'application/pdf', fileName);
  const file  = stuFolder.createFile(blob);

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

function getRootFolder_() {
  var list = DriveApp.getFoldersByName(ROOT_FOLDER_NAME);
  return list.hasNext() ? list.next() : null;
}

function getOrCreate(parent, name) {
  const list = parent
    ? parent.getFoldersByName(name)
    : DriveApp.getFoldersByName(name);
  if (list.hasNext()) return list.next();
  return parent
    ? parent.createFolder(name)
    : DriveApp.createFolder(name);
}

function clearCache_(className) {
  var cache = CacheService.getScriptCache();
  cache.remove('hoso_classes');
  if (className) cache.remove('hoso_class_' + className);
}

function json(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

/**
 * Test — chạy thủ công để kiểm tra kết nối Drive.
 */
function testDriveAccess() {
  const root = getOrCreate(null, ROOT_FOLDER_NAME);
  Logger.log('✅ Drive hoạt động. Thư mục root: ' + root.getName() + ' (' + root.getId() + ')');
}
