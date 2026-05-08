/**
 * scanner.js — Module quét tài liệu PDF trên mobile
 * Tích hợp: Camera capture → Image processing → PDF generation → Upload
 *
 * Dependencies: jsPDF (loaded from CDN in base.html)
 * Sử dụng: Canvas API để xử lý ảnh trực tiếp trên client
 */

(function () {
  'use strict';

  // ==========================================================
  // STATE
  // ==========================================================
  let _pages = [];         // Array of {img: HTMLImageElement, canvas: HTMLCanvasElement, filter: string}
  let _activeIdx = -1;     // Index trang đang chỉnh sửa
  let _docType = '';       // doc_type đang upload (GIAYKHAISINH, CCCD, etc.)
  let _studentId = 0;      // student_id
  let _uploadEndpoint = ''; // API endpoint tùy doc_type
  let _overlay = null;     // DOM overlay element

  // ==========================================================
  // FILTERS — xử lý ảnh trên Canvas
  // ==========================================================
  const FILTERS = {
    original: { label: 'Gốc', apply: function (ctx, w, h) { /* no-op */ } },
    document: {
      label: 'Tài liệu',
      apply: function (ctx, w, h) {
        var id = ctx.getImageData(0, 0, w, h);
        var d = id.data;
        for (var i = 0; i < d.length; i += 4) {
          // Increase contrast + brightness for document
          var avg = (d[i] + d[i + 1] + d[i + 2]) / 3;
          var factor = 1.5;
          d[i]     = Math.min(255, Math.max(0, factor * (d[i] - 128) + 128 + 20));
          d[i + 1] = Math.min(255, Math.max(0, factor * (d[i + 1] - 128) + 128 + 20));
          d[i + 2] = Math.min(255, Math.max(0, factor * (d[i + 2] - 128) + 128 + 20));
        }
        ctx.putImageData(id, 0, 0);
      }
    },
    bw: {
      label: 'Đen trắng',
      apply: function (ctx, w, h) {
        var id = ctx.getImageData(0, 0, w, h);
        var d = id.data;
        for (var i = 0; i < d.length; i += 4) {
          var gray = d[i] * 0.299 + d[i + 1] * 0.587 + d[i + 2] * 0.114;
          // Threshold for clean B&W
          var val = gray > 140 ? 255 : 0;
          d[i] = d[i + 1] = d[i + 2] = val;
        }
        ctx.putImageData(id, 0, 0);
      }
    },
    grayscale: {
      label: 'Xám',
      apply: function (ctx, w, h) {
        var id = ctx.getImageData(0, 0, w, h);
        var d = id.data;
        for (var i = 0; i < d.length; i += 4) {
          var gray = d[i] * 0.299 + d[i + 1] * 0.587 + d[i + 2] * 0.114;
          d[i] = d[i + 1] = d[i + 2] = gray;
        }
        ctx.putImageData(id, 0, 0);
      }
    },
    bright: {
      label: 'Tăng sáng',
      apply: function (ctx, w, h) {
        var id = ctx.getImageData(0, 0, w, h);
        var d = id.data;
        for (var i = 0; i < d.length; i += 4) {
          d[i]     = Math.min(255, d[i] + 40);
          d[i + 1] = Math.min(255, d[i + 1] + 40);
          d[i + 2] = Math.min(255, d[i + 2] + 40);
        }
        ctx.putImageData(id, 0, 0);
      }
    },
    sharp: {
      label: 'Nét',
      apply: function (ctx, w, h) {
        // Increase contrast slightly
        var id = ctx.getImageData(0, 0, w, h);
        var d = id.data;
        var factor = 1.3;
        for (var i = 0; i < d.length; i += 4) {
          d[i]     = Math.min(255, Math.max(0, factor * (d[i] - 128) + 128));
          d[i + 1] = Math.min(255, Math.max(0, factor * (d[i + 1] - 128) + 128));
          d[i + 2] = Math.min(255, Math.max(0, factor * (d[i + 2] - 128) + 128));
        }
        ctx.putImageData(id, 0, 0);
      }
    }
  };

  // ==========================================================
  // HTML TEMPLATE
  // ==========================================================
  function _buildHTML() {
    return '<div id="scanner-overlay" class="scanner-overlay hidden">' +
      '<!-- Processing overlay -->' +
      '<div id="scanner-processing" class="scanner-processing hidden">' +
        '<div class="scanner-spinner"></div>' +
        '<div class="scanner-processing-text" id="scanner-proc-text">Đang xử lý...</div>' +
      '</div>' +

      '<!-- Header -->' +
      '<div class="scanner-header">' +
        '<div class="scanner-title">' +
          '📸 Quét tài liệu <span class="scan-badge" id="scanner-doc-label"></span>' +
        '</div>' +
        '<button class="scanner-close" onclick="DocScanner.close()" title="Đóng">✕</button>' +
      '</div>' +

      '<!-- STEP 1: Capture -->' +
      '<div id="scanner-step-capture" class="scanner-capture">' +
        '<div class="scanner-capture-icon">📄</div>' +
        '<div class="scanner-capture-text">' +
          '<strong>Chụp hoặc chọn ảnh tài liệu</strong><br>' +
          'Đặt tài liệu trên nền phẳng, chụp rõ nét' +
        '</div>' +
        '<div class="scanner-capture-btns">' +
          '<button class="scanner-btn-camera" onclick="DocScanner._triggerCamera()">' +
            '📸 Chụp ảnh' +
          '</button>' +
          '<button class="scanner-btn-gallery" onclick="DocScanner._triggerGallery()">' +
            '🖼️ Chọn từ thư viện' +
          '</button>' +
        '</div>' +
        '<input type="file" id="scanner-camera-input" class="scanner-input-hidden" accept="image/*" capture="environment" multiple>' +
        '<input type="file" id="scanner-gallery-input" class="scanner-input-hidden" accept="image/*" multiple>' +
      '</div>' +

      '<!-- STEP 2: Editor -->' +
      '<div id="scanner-step-editor" class="scanner-editor hidden">' +
        '<div class="scanner-canvas-wrap">' +
          '<canvas id="scanner-canvas"></canvas>' +
        '</div>' +

        '<!-- Filters -->' +
        '<div class="scanner-filters" id="scanner-filters"></div>' +

        '<!-- Tool buttons -->' +
        '<div class="scanner-toolbar">' +
          '<button class="scanner-tool-btn" onclick="DocScanner._rotateCW()">' +
            '<span class="tool-icon">↻</span>Xoay phải' +
          '</button>' +
          '<button class="scanner-tool-btn" onclick="DocScanner._rotateCCW()">' +
            '<span class="tool-icon">↺</span>Xoay trái' +
          '</button>' +
          '<button class="scanner-tool-btn" onclick="DocScanner._cropToggle()">' +
            '<span class="tool-icon">✂️</span>Cắt' +
          '</button>' +
          '<button class="scanner-tool-btn" onclick="DocScanner._removePage()">' +
            '<span class="tool-icon">🗑️</span>Xóa trang' +
          '</button>' +
        '</div>' +
      '</div>' +

      '<!-- Pages thumbnails -->' +
      '<div id="scanner-pages" class="scanner-pages hidden">' +
        '<div class="scanner-pages-header">' +
          '<div class="scanner-pages-title">Các trang đã chụp</div>' +
          '<div class="scanner-pages-count" id="scanner-page-count">0</div>' +
        '</div>' +
        '<div class="scanner-page-list" id="scanner-page-list"></div>' +
      '</div>' +

      '<!-- Bottom bar -->' +
      '<div id="scanner-bottom-bar" class="scanner-bottom-bar hidden">' +
        '<button class="scanner-btn-addpage" onclick="DocScanner._addMore()">' +
          '➕ Thêm trang' +
        '</button>' +
        '<button class="scanner-btn-create-pdf" id="scanner-btn-pdf" onclick="DocScanner._createAndUpload()">' +
          '📄 Tạo PDF & Tải lên' +
        '</button>' +
      '</div>' +
    '</div>';
  }

  // ==========================================================
  // INIT — Inject HTML + bind events
  // ==========================================================
  function _init() {
    if (document.getElementById('scanner-overlay')) return;
    var container = document.createElement('div');
    container.innerHTML = _buildHTML();
    document.body.appendChild(container.firstChild);
    _overlay = document.getElementById('scanner-overlay');

    // Camera input change
    document.getElementById('scanner-camera-input').addEventListener('change', function (e) {
      _handleFiles(e.target.files);
      e.target.value = '';
    });
    // Gallery input change
    document.getElementById('scanner-gallery-input').addEventListener('change', function (e) {
      _handleFiles(e.target.files);
      e.target.value = '';
    });

    // Build filter buttons
    var filtersDiv = document.getElementById('scanner-filters');
    var filterKeys = Object.keys(FILTERS);
    for (var i = 0; i < filterKeys.length; i++) {
      (function (key) {
        var btn = document.createElement('button');
        btn.className = 'scanner-filter-btn' + (key === 'original' ? ' active' : '');
        btn.textContent = FILTERS[key].label;
        btn.setAttribute('data-filter', key);
        btn.addEventListener('click', function () { _applyFilter(key); });
        filtersDiv.appendChild(btn);
      })(filterKeys[i]);
    }
  }

  // ==========================================================
  // PUBLIC: Open scanner for a specific doc_type
  // ==========================================================
  function open(studentId, docType, docLabel) {
    _init();
    _pages = [];
    _activeIdx = -1;
    _studentId = studentId;
    _docType = docType;

    // Determine upload endpoint based on doc type
    // For HOCBA_6_8 we use append endpoint, others use standard upload
    _uploadEndpoint = '/api/upload';

    document.getElementById('scanner-doc-label').textContent = docLabel || docType;

    // Reset UI
    _showStep('capture');
    document.getElementById('scanner-pages').classList.add('hidden');
    document.getElementById('scanner-bottom-bar').classList.add('hidden');

    _overlay.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }

  // ==========================================================
  // PUBLIC: Close scanner
  // ==========================================================
  function close() {
    if (_overlay) {
      _overlay.classList.add('hidden');
      document.body.style.overflow = '';
    }
    _pages = [];
    _activeIdx = -1;
  }

  // ==========================================================
  // INTERNAL: Trigger camera / gallery
  // ==========================================================
  function _triggerCamera() {
    document.getElementById('scanner-camera-input').click();
  }
  function _triggerGallery() {
    document.getElementById('scanner-gallery-input').click();
  }

  // ==========================================================
  // INTERNAL: Handle selected files
  // ==========================================================
  function _handleFiles(fileList) {
    if (!fileList || !fileList.length) return;
    _showProcessing('Đang xử lý ảnh...');

    var loaded = 0;
    var total = fileList.length;

    for (var i = 0; i < total; i++) {
      (function (file) {
        var reader = new FileReader();
        reader.onload = function (ev) {
          var img = new Image();
          img.onload = function () {
            // Auto-resize nếu quá lớn (giữ chất lượng)
            var maxDim = 2400;
            var w = img.naturalWidth;
            var h = img.naturalHeight;
            if (w > maxDim || h > maxDim) {
              var ratio = Math.min(maxDim / w, maxDim / h);
              w = Math.round(w * ratio);
              h = Math.round(h * ratio);
            }

            var canvas = document.createElement('canvas');
            canvas.width = w;
            canvas.height = h;
            var ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, w, h);

            _pages.push({ img: img, canvas: canvas, filter: 'original', rotation: 0 });
            loaded++;

            if (loaded === total) {
              _hideProcessing();
              _activeIdx = _pages.length - total; // Select first new page
              _showStep('editor');
              _renderEditor();
              _renderPages();
            }
          };
          img.src = ev.target.result;
        };
        reader.readAsDataURL(file);
      })(fileList[i]);
    }
  }

  // ==========================================================
  // UI: Switch steps
  // ==========================================================
  function _showStep(step) {
    var capture = document.getElementById('scanner-step-capture');
    var editor = document.getElementById('scanner-step-editor');
    if (step === 'capture') {
      capture.style.display = '';
      editor.classList.add('hidden');
    } else {
      capture.style.display = 'none';
      editor.classList.remove('hidden');
    }
  }

  function _showProcessing(text) {
    var el = document.getElementById('scanner-processing');
    document.getElementById('scanner-proc-text').textContent = text || 'Đang xử lý...';
    el.classList.remove('hidden');
  }
  function _hideProcessing() {
    document.getElementById('scanner-processing').classList.add('hidden');
  }

  // ==========================================================
  // RENDER: Main canvas editor
  // ==========================================================
  function _renderEditor() {
    if (_activeIdx < 0 || _activeIdx >= _pages.length) return;
    var page = _pages[_activeIdx];
    var displayCanvas = document.getElementById('scanner-canvas');
    var srcCanvas = page.canvas;

    // Recreate from original image with current rotation + filter
    var w = page.img.naturalWidth;
    var h = page.img.naturalHeight;
    var maxDim = 2400;
    if (w > maxDim || h > maxDim) {
      var ratio = Math.min(maxDim / w, maxDim / h);
      w = Math.round(w * ratio);
      h = Math.round(h * ratio);
    }

    var rot = page.rotation || 0;
    var rotated = (rot === 90 || rot === 270);
    var cw = rotated ? h : w;
    var ch = rotated ? w : h;

    srcCanvas.width = cw;
    srcCanvas.height = ch;
    var ctx = srcCanvas.getContext('2d');
    ctx.save();
    ctx.translate(cw / 2, ch / 2);
    ctx.rotate(rot * Math.PI / 180);
    ctx.drawImage(page.img, -w / 2, -h / 2, w, h);
    ctx.restore();

    // Apply filter
    if (page.filter && page.filter !== 'original' && FILTERS[page.filter]) {
      FILTERS[page.filter].apply(ctx, cw, ch);
    }

    // Copy to display canvas
    displayCanvas.width = cw;
    displayCanvas.height = ch;
    displayCanvas.getContext('2d').drawImage(srcCanvas, 0, 0);

    // Update filter buttons
    var btns = document.querySelectorAll('.scanner-filter-btn');
    for (var i = 0; i < btns.length; i++) {
      btns[i].classList.toggle('active', btns[i].getAttribute('data-filter') === page.filter);
    }
  }

  // ==========================================================
  // RENDER: Page thumbnails
  // ==========================================================
  function _renderPages() {
    var pagesDiv = document.getElementById('scanner-pages');
    var listDiv = document.getElementById('scanner-page-list');
    var bottomBar = document.getElementById('scanner-bottom-bar');
    var countEl = document.getElementById('scanner-page-count');

    if (_pages.length === 0) {
      pagesDiv.classList.add('hidden');
      bottomBar.classList.add('hidden');
      return;
    }

    pagesDiv.classList.remove('hidden');
    bottomBar.classList.remove('hidden');
    countEl.textContent = _pages.length;

    var html = '';
    for (var i = 0; i < _pages.length; i++) {
      var thumbUrl = _pages[i].canvas.toDataURL('image/jpeg', 0.4);
      html += '<div class="scanner-page-thumb' + (i === _activeIdx ? ' active' : '') + '" ' +
              'onclick="DocScanner._selectPage(' + i + ')">' +
        '<img src="' + thumbUrl + '" alt="Trang ' + (i + 1) + '">' +
        '<span class="scanner-page-num">' + (i + 1) + '</span>' +
        '<button class="scanner-page-rm" onclick="event.stopPropagation();DocScanner._removePageAt(' + i + ')">✕</button>' +
      '</div>';
    }
    listDiv.innerHTML = html;
  }

  // ==========================================================
  // ACTIONS: Filter
  // ==========================================================
  function _applyFilter(filterKey) {
    if (_activeIdx < 0 || !_pages[_activeIdx]) return;
    _pages[_activeIdx].filter = filterKey;
    _renderEditor();
    _renderPages();
  }

  // ==========================================================
  // ACTIONS: Rotate
  // ==========================================================
  function _rotateCW() {
    if (_activeIdx < 0) return;
    var p = _pages[_activeIdx];
    p.rotation = ((p.rotation || 0) + 90) % 360;
    _renderEditor();
    _renderPages();
  }
  function _rotateCCW() {
    if (_activeIdx < 0) return;
    var p = _pages[_activeIdx];
    p.rotation = ((p.rotation || 0) + 270) % 360;
    _renderEditor();
    _renderPages();
  }

  // ==========================================================
  // ACTIONS: Crop (simple center crop toggle)
  // ==========================================================
  var _cropMode = false;
  function _cropToggle() {
    if (_activeIdx < 0) return;
    var page = _pages[_activeIdx];
    var c = page.canvas;
    if (!_cropMode) {
      // Crop 10% from each edge
      var ctx = c.getContext('2d');
      var w = c.width, h = c.height;
      var cropX = Math.floor(w * 0.05);
      var cropY = Math.floor(h * 0.05);
      var cropW = w - cropX * 2;
      var cropH = h - cropY * 2;
      var imgData = ctx.getImageData(cropX, cropY, cropW, cropH);
      c.width = cropW;
      c.height = cropH;
      ctx.putImageData(imgData, 0, 0);
      _cropMode = true;
    } else {
      // Restore: re-render from original
      _renderEditor();
      _cropMode = false;
    }
    var displayCanvas = document.getElementById('scanner-canvas');
    displayCanvas.width = c.width;
    displayCanvas.height = c.height;
    displayCanvas.getContext('2d').drawImage(c, 0, 0);
    _renderPages();
  }

  // ==========================================================
  // ACTIONS: Remove page
  // ==========================================================
  function _removePage() {
    if (_activeIdx < 0) return;
    _removePageAt(_activeIdx);
  }
  function _removePageAt(idx) {
    _pages.splice(idx, 1);
    if (_pages.length === 0) {
      _activeIdx = -1;
      _showStep('capture');
      _renderPages();
    } else {
      _activeIdx = Math.min(idx, _pages.length - 1);
      _renderEditor();
      _renderPages();
    }
  }

  // ==========================================================
  // ACTIONS: Select page
  // ==========================================================
  function _selectPage(idx) {
    _activeIdx = idx;
    _renderEditor();
    _renderPages();
  }

  // ==========================================================
  // ACTIONS: Add more pages
  // ==========================================================
  function _addMore() {
    _showStep('capture');
  }

  // ==========================================================
  // CORE: Create PDF and upload
  // ==========================================================
  function _createAndUpload() {
    if (_pages.length === 0) {
      if (typeof showToast === 'function') showToast('Chưa có trang nào để tạo PDF.', 'error');
      return;
    }

    var btn = document.getElementById('scanner-btn-pdf');
    btn.disabled = true;
    _showProcessing('Đang tạo PDF (' + _pages.length + ' trang)...');

    // Sử dụng setTimeout để UI kịp cập nhật
    setTimeout(function () {
      try {
        _generatePDF(function (pdfBlob) {
          _showProcessing('Đang tải lên...');
          _uploadPDF(pdfBlob, function (success, message) {
            _hideProcessing();
            btn.disabled = false;
            if (success) {
              if (typeof showToast === 'function') showToast(message || 'Tải lên thành công!', 'success');
              close();
              setTimeout(function () { location.reload(); }, 1200);
            } else {
              if (typeof showToast === 'function') showToast(message || 'Lỗi tải lên.', 'error');
            }
          });
        });
      } catch (e) {
        _hideProcessing();
        btn.disabled = false;
        if (typeof showToast === 'function') showToast('Lỗi tạo PDF: ' + e.message, 'error');
      }
    }, 100);
  }

  // ==========================================================
  // PDF Generation using jsPDF
  // ==========================================================
  function _generatePDF(callback) {
    if (typeof window.jspdf === 'undefined' && typeof window.jsPDF === 'undefined') {
      throw new Error('Thư viện jsPDF chưa được tải. Vui lòng thử lại.');
    }
    var jsPDFClass = (window.jspdf && window.jspdf.jsPDF) || window.jsPDF;
    // A4 dimensions in mm
    var A4_W = 210, A4_H = 297;

    var doc = new jsPDFClass({ orientation: 'portrait', unit: 'mm', format: 'a4' });

    for (var i = 0; i < _pages.length; i++) {
      if (i > 0) doc.addPage();

      var canvas = _pages[i].canvas;
      var imgData = canvas.toDataURL('image/jpeg', 0.85);

      // Fit to A4 preserving aspect ratio
      var imgW = canvas.width;
      var imgH = canvas.height;
      var ratio = Math.min(A4_W / imgW, A4_H / imgH);
      var fitW = imgW * ratio;
      var fitH = imgH * ratio;
      var offX = (A4_W - fitW) / 2;
      var offY = (A4_H - fitH) / 2;

      doc.addImage(imgData, 'JPEG', offX, offY, fitW, fitH);
    }

    var blob = doc.output('blob');
    callback(blob);
  }

  // ==========================================================
  // Upload PDF to server
  // ==========================================================
  function _uploadPDF(pdfBlob, callback) {
    var fd = new FormData();
    var fileName = _docType + '_scan_' + Date.now() + '.pdf';

    if (_docType === 'HOCBA_6_8') {
      // Sử dụng endpoint append-hocba cho học bạ
      fd.append('files', pdfBlob, fileName);
      fetch('/api/append-hocba/' + _studentId, { method: 'POST', body: fd })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          callback(d.success, d.message || d.error);
        })
        .catch(function (e) {
          callback(false, 'Lỗi kết nối: ' + e.message);
        });
    } else if (_docType === 'CCCD') {
      // Sử dụng endpoint upload-multi cho CCCD
      fd.append('files', pdfBlob, fileName);
      fetch('/api/upload-multi/' + _studentId + '/' + _docType, { method: 'POST', body: fd })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          callback(d.success, d.message || d.error);
        })
        .catch(function (e) {
          callback(false, 'Lỗi kết nối: ' + e.message);
        });
    } else {
      // Standard upload
      fd.append('student_id', _studentId);
      fd.append('doc_type', _docType);
      fd.append('file', pdfBlob, fileName);
      fetch('/api/upload', { method: 'POST', body: fd })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          callback(d.success, d.message || d.error);
        })
        .catch(function (e) {
          callback(false, 'Lỗi kết nối: ' + e.message);
        });
    }
  }

  // ==========================================================
  // PUBLIC API
  // ==========================================================
  window.DocScanner = {
    open: open,
    close: close,
    _triggerCamera: _triggerCamera,
    _triggerGallery: _triggerGallery,
    _rotateCW: _rotateCW,
    _rotateCCW: _rotateCCW,
    _cropToggle: _cropToggle,
    _removePage: _removePage,
    _removePageAt: _removePageAt,
    _selectPage: _selectPage,
    _addMore: _addMore,
    _createAndUpload: _createAndUpload,
    _applyFilter: _applyFilter
  };

})();
