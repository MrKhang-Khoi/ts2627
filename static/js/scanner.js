/**
 * scanner.js — Module quét tài liệu PDF trên mobile
 * Flow: Camera capture → Crop (yellow frame) → Editor (filters) → PDF → Upload
 */
(function () {
  'use strict';

  var _pages = [], _activeIdx = -1, _docType = '', _studentId = 0, _overlay = null;
  // Crop state
  var _cropImg = null, _cropCorners = [], _dragIdx = -1, _cropCanvas = null, _cropCtx = null;
  var _pendingFiles = [], _pendingFileIdx = 0;

  // === Unsharp Mask helper (kỹ thuật gốc của các app scanner chuyên nghiệp) ===
  // Formula: Sharpened = Original + (Original - Blurred) × Amount
  function _unsharpMask(ctx, w, h, radius, amount) {
    var src = ctx.getImageData(0, 0, w, h);
    // Create blurred copy using box blur (fast approximation of Gaussian)
    var blur = new Uint8ClampedArray(src.data);
    var r = Math.max(1, Math.round(radius));
    // Horizontal pass
    var tmp = new Uint8ClampedArray(blur.length);
    for (var y = 0; y < h; y++) {
      for (var x = 0; x < w; x++) {
        var rr = 0, gg = 0, bb = 0, cnt = 0;
        for (var k = -r; k <= r; k++) {
          var nx = Math.min(w - 1, Math.max(0, x + k));
          var idx = (y * w + nx) * 4;
          rr += blur[idx]; gg += blur[idx + 1]; bb += blur[idx + 2]; cnt++;
        }
        var pi = (y * w + x) * 4;
        tmp[pi] = rr / cnt; tmp[pi + 1] = gg / cnt; tmp[pi + 2] = bb / cnt; tmp[pi + 3] = 255;
      }
    }
    // Vertical pass
    for (var x = 0; x < w; x++) {
      for (var y = 0; y < h; y++) {
        var rr = 0, gg = 0, bb = 0, cnt = 0;
        for (var k = -r; k <= r; k++) {
          var ny = Math.min(h - 1, Math.max(0, y + k));
          var idx = (ny * w + x) * 4;
          rr += tmp[idx]; gg += tmp[idx + 1]; bb += tmp[idx + 2]; cnt++;
        }
        var pi = (y * w + x) * 4;
        blur[pi] = rr / cnt; blur[pi + 1] = gg / cnt; blur[pi + 2] = bb / cnt;
      }
    }
    // Apply: sharpened = original + (original - blurred) * amount
    var d = src.data;
    for (var i = 0; i < d.length; i += 4) {
      d[i]     = Math.min(255, Math.max(0, d[i]     + (d[i]     - blur[i])     * amount));
      d[i + 1] = Math.min(255, Math.max(0, d[i + 1] + (d[i + 1] - blur[i + 1]) * amount));
      d[i + 2] = Math.min(255, Math.max(0, d[i + 2] + (d[i + 2] - blur[i + 2]) * amount));
    }
    ctx.putImageData(src, 0, 0);
  }

  var FILTERS = {
    original: { label: 'Gốc', apply: function(){} },
    document: {
      label: 'Tài liệu',
      apply: function(ctx, w, h) {
        // Kỹ thuật scanner chuyên nghiệp: tăng contrast + làm trắng nền + sharpen nhẹ
        var id = ctx.getImageData(0, 0, w, h), d = id.data;
        for (var i = 0; i < d.length; i += 4) {
          var gray = d[i] * 0.299 + d[i+1] * 0.587 + d[i+2] * 0.114;
          // Adaptive: nền sáng → trắng hơn, chữ tối → đậm hơn
          var factor = gray > 180 ? 1.8 : (gray > 100 ? 1.5 : 1.2);
          var shift  = gray > 180 ? 40 : (gray > 100 ? 15 : 0);
          d[i]     = Math.min(255, Math.max(0, factor * (d[i]     - 128) + 128 + shift));
          d[i + 1] = Math.min(255, Math.max(0, factor * (d[i + 1] - 128) + 128 + shift));
          d[i + 2] = Math.min(255, Math.max(0, factor * (d[i + 2] - 128) + 128 + shift));
        }
        ctx.putImageData(id, 0, 0);
        // Unsharp mask nhẹ để chữ rõ nét
        _unsharpMask(ctx, w, h, 1, 0.4);
      }
    },
    bw: {
      label: 'Đen trắng',
      apply: function(ctx, w, h) {
        // Adaptive thresholding: tính ngưỡng cục bộ thay vì ngưỡng toàn cục
        var id = ctx.getImageData(0, 0, w, h), d = id.data;
        var gray = new Float32Array(w * h);
        for (var i = 0; i < gray.length; i++) {
          gray[i] = d[i*4] * 0.299 + d[i*4+1] * 0.587 + d[i*4+2] * 0.114;
        }
        // Box blur for local average (radius=15)
        var avg = new Float32Array(gray);
        var br = Math.min(15, Math.floor(Math.min(w, h) / 20));
        // Horizontal
        var tmp = new Float32Array(gray.length);
        for (var y = 0; y < h; y++) {
          for (var x = 0; x < w; x++) {
            var sum = 0, cnt = 0;
            for (var k = -br; k <= br; k++) {
              var nx = x + k; if (nx < 0 || nx >= w) continue;
              sum += avg[y * w + nx]; cnt++;
            }
            tmp[y * w + x] = sum / cnt;
          }
        }
        for (var x = 0; x < w; x++) {
          for (var y = 0; y < h; y++) {
            var sum = 0, cnt = 0;
            for (var k = -br; k <= br; k++) {
              var ny = y + k; if (ny < 0 || ny >= h) continue;
              sum += tmp[ny * w + x]; cnt++;
            }
            avg[y * w + x] = sum / cnt;
          }
        }
        // Threshold: pixel tối hơn local average → đen
        for (var i = 0; i < gray.length; i++) {
          var v = gray[i] < (avg[i] - 12) ? 0 : 255;
          d[i*4] = d[i*4+1] = d[i*4+2] = v;
        }
        ctx.putImageData(id, 0, 0);
      }
    },
    grayscale: {
      label: 'Xám',
      apply: function(ctx, w, h) {
        var id = ctx.getImageData(0, 0, w, h), d = id.data;
        for (var i = 0; i < d.length; i += 4) {
          var g = d[i] * 0.299 + d[i+1] * 0.587 + d[i+2] * 0.114;
          d[i] = d[i+1] = d[i+2] = g;
        }
        ctx.putImageData(id, 0, 0);
      }
    },
    bright: {
      label: 'Tăng sáng',
      apply: function(ctx, w, h) {
        var id = ctx.getImageData(0, 0, w, h), d = id.data;
        for (var i = 0; i < d.length; i += 4) {
          // Gamma correction (sáng tự nhiên hơn, không bị washout)
          d[i]     = Math.min(255, Math.pow(d[i]     / 255, 0.8) * 255);
          d[i + 1] = Math.min(255, Math.pow(d[i + 1] / 255, 0.8) * 255);
          d[i + 2] = Math.min(255, Math.pow(d[i + 2] / 255, 0.8) * 255);
        }
        ctx.putImageData(id, 0, 0);
      }
    },
    sharp: {
      label: 'Nét',
      apply: function(ctx, w, h) {
        // Unsharp Mask thực sự (kỹ thuật chuẩn của Adobe/CamScanner)
        _unsharpMask(ctx, w, h, 1, 0.8);
      }
    }
  };

  function _buildHTML() {
    return '<div id="scanner-overlay" class="scanner-overlay hidden">' +
      '<div id="scanner-processing" class="scanner-processing hidden"><div class="scanner-spinner"></div><div class="scanner-processing-text" id="scanner-proc-text">Đang xử lý...</div></div>' +
      '<div class="scanner-header"><div class="scanner-title">📸 Quét tài liệu <span class="scan-badge" id="scanner-doc-label"></span></div><button class="scanner-close" onclick="DocScanner.close()" title="Đóng">✕</button></div>' +
      // STEP 1: Capture
      '<div id="scanner-step-capture" class="scanner-capture">' +
        '<div class="scanner-capture-icon">📄</div>' +
        '<div class="scanner-capture-text"><strong>Chụp hoặc chọn ảnh tài liệu</strong><br>Đặt tài liệu trên nền phẳng, chụp rõ nét</div>' +
        '<div class="scanner-capture-btns">' +
          '<button class="scanner-btn-camera" onclick="DocScanner._triggerCamera()">📸 Chụp ảnh</button>' +
          '<button class="scanner-btn-gallery" onclick="DocScanner._triggerGallery()">🖼️ Chọn từ thư viện</button>' +
        '</div>' +
        '<input type="file" id="scanner-camera-input" class="scanner-input-hidden" accept="image/*" capture="environment">' +
        '<input type="file" id="scanner-gallery-input" class="scanner-input-hidden" accept="image/*" multiple>' +
      '</div>' +
      // STEP 1.5: Crop with yellow frame
      '<div id="scanner-step-crop" class="scanner-crop-step hidden">' +
        '<div class="scanner-crop-hint">⬛ Kéo 4 góc vàng để căn chỉnh tài liệu</div>' +
        '<div class="scanner-crop-canvas-wrap" id="crop-canvas-wrap"><canvas id="crop-canvas"></canvas></div>' +
        '<div class="scanner-crop-actions">' +
          '<button class="scanner-btn-crop-retake" onclick="DocScanner._cropRetake()">↩ Chụp lại</button>' +
          '<button class="scanner-btn-crop-confirm" onclick="DocScanner._cropConfirm()">✅ Xác nhận cắt</button>' +
        '</div>' +
      '</div>' +
      // STEP 2: Editor
      '<div id="scanner-step-editor" class="scanner-editor hidden">' +
        '<div class="scanner-canvas-wrap"><canvas id="scanner-canvas"></canvas></div>' +
        '<div class="scanner-filters" id="scanner-filters"></div>' +
        '<div class="scanner-toolbar">' +
          '<button class="scanner-tool-btn" onclick="DocScanner._rotateCW()"><span class="tool-icon">↻</span>Xoay phải</button>' +
          '<button class="scanner-tool-btn" onclick="DocScanner._rotateCCW()"><span class="tool-icon">↺</span>Xoay trái</button>' +
          '<button class="scanner-tool-btn" onclick="DocScanner._removePage()"><span class="tool-icon">🗑️</span>Xóa trang</button>' +
        '</div>' +
      '</div>' +
      // Pages
      '<div id="scanner-pages" class="scanner-pages hidden"><div class="scanner-pages-header"><div class="scanner-pages-title">Các trang đã chụp</div><div class="scanner-pages-count" id="scanner-page-count">0</div></div><div class="scanner-page-list" id="scanner-page-list"></div></div>' +
      // Bottom bar
      '<div id="scanner-bottom-bar" class="scanner-bottom-bar hidden">' +
        '<button class="scanner-btn-addpage" onclick="DocScanner._addMore()">➕ Thêm trang</button>' +
        '<button class="scanner-btn-create-pdf" id="scanner-btn-pdf" onclick="DocScanner._createAndUpload()">📄 Tạo PDF & Tải lên</button>' +
      '</div>' +
    '</div>';
  }

  function _init() {
    if (document.getElementById('scanner-overlay')) return;
    var c = document.createElement('div');
    c.innerHTML = _buildHTML();
    document.body.appendChild(c.firstChild);
    _overlay = document.getElementById('scanner-overlay');
    document.getElementById('scanner-camera-input').addEventListener('change', function(e){ _handleFiles(e.target.files); e.target.value=''; });
    document.getElementById('scanner-gallery-input').addEventListener('change', function(e){ _handleFiles(e.target.files); e.target.value=''; });
    // Build filter buttons
    var fd = document.getElementById('scanner-filters');
    Object.keys(FILTERS).forEach(function(key){
      var btn = document.createElement('button');
      btn.className = 'scanner-filter-btn' + (key==='original'?' active':'');
      btn.textContent = FILTERS[key].label;
      btn.setAttribute('data-filter', key);
      btn.addEventListener('click', function(){ _applyFilter(key); });
      fd.appendChild(btn);
    });
    // Crop touch/mouse events
    var cw = document.getElementById('crop-canvas-wrap');
    cw.addEventListener('mousedown', _cropDown); cw.addEventListener('mousemove', _cropMove); cw.addEventListener('mouseup', _cropUp);
    cw.addEventListener('touchstart', _cropTouchDown, {passive:false}); cw.addEventListener('touchmove', _cropTouchMove, {passive:false}); cw.addEventListener('touchend', _cropUp);
  }

  // ===== PUBLIC =====
  function open(studentId, docType, docLabel) {
    _init(); _pages=[]; _activeIdx=-1; _studentId=studentId; _docType=docType;
    document.getElementById('scanner-doc-label').textContent = docLabel||docType;
    _showStep('capture');
    document.getElementById('scanner-pages').classList.add('hidden');
    document.getElementById('scanner-bottom-bar').classList.add('hidden');
    _overlay.classList.remove('hidden');
    document.body.style.overflow='hidden';
  }
  function close() {
    if(_overlay){_overlay.classList.add('hidden'); document.body.style.overflow='';}
    _pages=[]; _activeIdx=-1; _pendingFiles=[]; _pendingFileIdx=0;
  }

  function _triggerCamera(){ document.getElementById('scanner-camera-input').click(); }
  function _triggerGallery(){ document.getElementById('scanner-gallery-input').click(); }

  // ===== HANDLE FILES → go to crop step =====
  function _handleFiles(fileList) {
    if(!fileList||!fileList.length) return;
    _showProcessing('Đang xử lý ảnh...');
    _pendingFiles=[]; _pendingFileIdx=0;
    var loaded=0, total=fileList.length;
    for(var i=0;i<total;i++){
      (function(file){
        var reader=new FileReader();
        reader.onload=function(ev){
          var img=new Image();
          img.onload=function(){
            var maxD=3600, w=img.naturalWidth, h=img.naturalHeight;
            if(w>maxD||h>maxD){var r=Math.min(maxD/w,maxD/h);w=Math.round(w*r);h=Math.round(h*r);}
            var cv=document.createElement('canvas'); cv.width=w; cv.height=h;
            var drawCtx=cv.getContext('2d');
            drawCtx.imageSmoothingEnabled=true;
            drawCtx.imageSmoothingQuality='high';
            drawCtx.drawImage(img,0,0,w,h);
            _pendingFiles.push({img:img, canvas:cv});
            loaded++;
            if(loaded===total){ _hideProcessing(); _pendingFileIdx=0; _showCropForPending(); }
          };
          img.src=ev.target.result;
        };
        reader.readAsDataURL(file);
      })(fileList[i]);
    }
  }

  // ===== CROP STEP =====
  function _showCropForPending() {
    if(_pendingFileIdx >= _pendingFiles.length) {
      // All files cropped, go to editor
      if(_pages.length>0){
        _activeIdx=_pages.length-1;
        _showStep('editor');
        // Delay rendering to let DOM layout update after hiding crop step
        setTimeout(function(){ _renderEditor(); _renderPages(); }, 100);
      } else { _showStep('capture'); }
      return;
    }
    var pf = _pendingFiles[_pendingFileIdx];
    _cropImg = pf.canvas;
    // Init corners at 5% margin (normalized 0-1)
    _cropCorners = [{x:0.05,y:0.05},{x:0.95,y:0.05},{x:0.95,y:0.95},{x:0.05,y:0.95}];
    _showStep('crop');
    setTimeout(_renderCrop, 50);
  }

  function _showStep(step) {
    var cap=document.getElementById('scanner-step-capture');
    var crop=document.getElementById('scanner-step-crop');
    var ed=document.getElementById('scanner-step-editor');
    cap.style.display = step==='capture'?'':'none';
    crop.classList.toggle('hidden', step!=='crop');
    ed.classList.toggle('hidden', step!=='editor');
    // Hide/show bottom bar and pages for crop step
    if(step==='crop'){
      document.getElementById('scanner-pages').classList.add('hidden');
      document.getElementById('scanner-bottom-bar').classList.add('hidden');
    }
  }

  function _renderCrop() {
    var wrap = document.getElementById('crop-canvas-wrap');
    var cv = document.getElementById('crop-canvas');
    if(!_cropImg) return;
    var ww=wrap.clientWidth, wh=wrap.clientHeight;
    if(ww<1||wh<1) return;

    // === DPR fix: render at device pixel resolution for sharp display ===
    var dpr = window.devicePixelRatio || 1;
    cv.width = Math.round(ww * dpr);
    cv.height = Math.round(wh * dpr);
    cv.style.width = ww + 'px';
    cv.style.height = wh + 'px';
    _cropCanvas=cv; _cropCtx=cv.getContext('2d');
    var ctx = _cropCtx;
    ctx.scale(dpr, dpr);
    // All coordinates below are in CSS pixels (auto-scaled by ctx.scale)

    var iw=_cropImg.width, ih=_cropImg.height;
    var scale=Math.min(ww/iw, wh/ih);
    var dw=iw*scale, dh=ih*scale;
    var ox=(ww-dw)/2, oy=(wh-dh)/2;

    // Draw image (high quality)
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.clearRect(0, 0, ww, wh);
    ctx.drawImage(_cropImg, ox, oy, dw, dh);

    // Dark overlay outside crop area
    ctx.fillStyle='rgba(0,0,0,0.55)';
    ctx.fillRect(0, 0, ww, wh);

    // Clear crop area (draw image only inside polygon)
    ctx.save();
    ctx.beginPath();
    var pts=_cropCorners.map(function(p){return{x:ox+p.x*dw, y:oy+p.y*dh};});
    ctx.moveTo(pts[0].x, pts[0].y);
    for(var i=1;i<pts.length;i++) ctx.lineTo(pts[i].x, pts[i].y);
    ctx.closePath(); ctx.clip();
    ctx.drawImage(_cropImg, ox, oy, dw, dh);
    ctx.restore();

    // Yellow border
    ctx.strokeStyle='#FFD54F'; ctx.lineWidth=2.5; ctx.setLineDash([]);
    ctx.beginPath(); ctx.moveTo(pts[0].x,pts[0].y);
    for(var i=1;i<pts.length;i++) ctx.lineTo(pts[i].x,pts[i].y);
    ctx.closePath(); ctx.stroke();

    // Corner handles (crisp circles)
    for(var i=0;i<pts.length;i++){
      ctx.beginPath(); ctx.arc(Math.round(pts[i].x), Math.round(pts[i].y), 12, 0, Math.PI*2);
      ctx.fillStyle='#FFD54F'; ctx.fill();
      ctx.strokeStyle='#F9A825'; ctx.lineWidth=2; ctx.stroke();
      ctx.beginPath(); ctx.arc(Math.round(pts[i].x), Math.round(pts[i].y), 4, 0, Math.PI*2);
      ctx.fillStyle='#1a1a2e'; ctx.fill();
    }
    // Edge midpoint handles
    for(var i=0;i<pts.length;i++){
      var j=(i+1)%pts.length;
      var mx=Math.round((pts[i].x+pts[j].x)/2), my=Math.round((pts[i].y+pts[j].y)/2);
      ctx.beginPath(); ctx.arc(mx,my,5,0,Math.PI*2);
      ctx.fillStyle='rgba(255,213,79,0.6)'; ctx.fill();
    }
  }

  function _getCropCoords(clientX, clientY) {
    var wrap=document.getElementById('crop-canvas-wrap');
    var rect=wrap.getBoundingClientRect();
    return {x:clientX-rect.left, y:clientY-rect.top};
  }
  function _findCorner(cx,cy) {
    var wrap=document.getElementById('crop-canvas-wrap');
    var ww=wrap.clientWidth, wh=wrap.clientHeight;
    var iw=_cropImg.width, ih=_cropImg.height;
    var scale=Math.min(ww/iw, wh/ih);
    var dw=iw*scale, dh=ih*scale, ox=(ww-dw)/2, oy=(wh-dh)/2;
    var best=-1, bestD=40;
    for(var i=0;i<_cropCorners.length;i++){
      var px=ox+_cropCorners[i].x*dw, py=oy+_cropCorners[i].y*dh;
      var d=Math.sqrt((cx-px)*(cx-px)+(cy-py)*(cy-py));
      if(d<bestD){bestD=d;best=i;}
    }
    return best;
  }
  function _moveCorner(idx,cx,cy){
    var wrap=document.getElementById('crop-canvas-wrap');
    var ww=wrap.clientWidth, wh=wrap.clientHeight;
    var iw=_cropImg.width, ih=_cropImg.height;
    var scale=Math.min(ww/iw, wh/ih);
    var dw=iw*scale, dh=ih*scale, ox=(ww-dw)/2, oy=(wh-dh)/2;
    var nx=Math.max(0,Math.min(1,(cx-ox)/dw));
    var ny=Math.max(0,Math.min(1,(cy-oy)/dh));
    _cropCorners[idx]={x:nx,y:ny};
    _renderCrop();
  }
  function _cropDown(e){var c=_getCropCoords(e.clientX,e.clientY);_dragIdx=_findCorner(c.x,c.y);}
  function _cropMove(e){if(_dragIdx<0)return;var c=_getCropCoords(e.clientX,e.clientY);_moveCorner(_dragIdx,c.x,c.y);}
  function _cropUp(){_dragIdx=-1;}
  function _cropTouchDown(e){e.preventDefault();var t=e.touches[0];var c=_getCropCoords(t.clientX,t.clientY);_dragIdx=_findCorner(c.x,c.y);}
  function _cropTouchMove(e){e.preventDefault();if(_dragIdx<0)return;var t=e.touches[0];var c=_getCropCoords(t.clientX,t.clientY);_moveCorner(_dragIdx,c.x,c.y);}

  function _cropConfirm() {
    if(!_cropImg) return;
    var corners=_cropCorners;
    var iw=_cropImg.width, ih=_cropImg.height;
    // Get bounding box from corners
    var minX=1,minY=1,maxX=0,maxY=0;
    for(var i=0;i<corners.length;i++){
      if(corners[i].x<minX)minX=corners[i].x; if(corners[i].x>maxX)maxX=corners[i].x;
      if(corners[i].y<minY)minY=corners[i].y; if(corners[i].y>maxY)maxY=corners[i].y;
    }
    var sx=Math.round(minX*iw), sy=Math.round(minY*ih);
    var sw=Math.round((maxX-minX)*iw), sh=Math.round((maxY-minY)*ih);
    if(sw<20||sh<20){sw=iw; sh=ih; sx=0; sy=0;}
    var cv=document.createElement('canvas'); cv.width=sw; cv.height=sh;
    cv.getContext('2d').drawImage(_cropImg, sx, sy, sw, sh, 0, 0, sw, sh);
    var img = _pendingFiles[_pendingFileIdx].img;
    _pages.push({img:img, canvas:cv, filter:'original', rotation:0, cropped:true});
    _pendingFileIdx++;
    _showCropForPending();
  }
  function _cropRetake() { _pendingFiles=[]; _pendingFileIdx=0; _showStep('capture'); }

  // ===== PROCESSING =====
  function _showProcessing(t){var e=document.getElementById('scanner-processing');document.getElementById('scanner-proc-text').textContent=t||'Đang xử lý...';e.classList.remove('hidden');}
  function _hideProcessing(){document.getElementById('scanner-processing').classList.add('hidden');}

  // ===== EDITOR =====
  function _renderEditor() {
    if(_activeIdx<0||_activeIdx>=_pages.length) return;
    var page=_pages[_activeIdx], dc=document.getElementById('scanner-canvas'), sc=page.canvas;
    if(page.cropped){
      // Already cropped, just apply filter
      var cw=sc.width, ch=sc.height;
      dc.width=cw; dc.height=ch;
      var ctx=dc.getContext('2d');
      ctx.drawImage(sc,0,0);
      if(page.filter&&page.filter!=='original'&&FILTERS[page.filter]) FILTERS[page.filter].apply(ctx,cw,ch);
    } else {
      var w=page.img.naturalWidth, h=page.img.naturalHeight, maxD=3600;
      if(w>maxD||h>maxD){var r=Math.min(maxD/w,maxD/h);w=Math.round(w*r);h=Math.round(h*r);}
      var rot=page.rotation||0, rotated=(rot===90||rot===270);
      var cw=rotated?h:w, ch=rotated?w:h;
      sc.width=cw; sc.height=ch;
      var ctx=sc.getContext('2d');
      ctx.save(); ctx.translate(cw/2,ch/2); ctx.rotate(rot*Math.PI/180); ctx.drawImage(page.img,-w/2,-h/2,w,h); ctx.restore();
      if(page.filter&&page.filter!=='original'&&FILTERS[page.filter]) FILTERS[page.filter].apply(ctx,cw,ch);
      dc.width=cw; dc.height=ch; dc.getContext('2d').drawImage(sc,0,0);
    }
    var btns=document.querySelectorAll('.scanner-filter-btn');
    for(var i=0;i<btns.length;i++) btns[i].classList.toggle('active',btns[i].getAttribute('data-filter')===page.filter);
  }

  function _renderPages() {
    var pd=document.getElementById('scanner-pages'), ld=document.getElementById('scanner-page-list');
    var bb=document.getElementById('scanner-bottom-bar'), cnt=document.getElementById('scanner-page-count');
    if(!_pages.length){pd.classList.add('hidden');bb.classList.add('hidden');return;}
    pd.classList.remove('hidden'); bb.classList.remove('hidden'); cnt.textContent=_pages.length;
    var html='';
    for(var i=0;i<_pages.length;i++){
      var u=_pages[i].canvas.toDataURL('image/jpeg',0.4);
      html+='<div class="scanner-page-thumb'+(i===_activeIdx?' active':'')+'" onclick="DocScanner._selectPage('+i+')"><img src="'+u+'" alt="Trang '+(i+1)+'"><span class="scanner-page-num">'+(i+1)+'</span><button class="scanner-page-rm" onclick="event.stopPropagation();DocScanner._removePageAt('+i+')">✕</button></div>';
    }
    ld.innerHTML=html;
  }

  function _applyFilter(k){if(_activeIdx<0||!_pages[_activeIdx])return;_pages[_activeIdx].filter=k;_renderEditor();_renderPages();}
  function _rotateCW(){if(_activeIdx<0)return;var p=_pages[_activeIdx];p.rotation=((p.rotation||0)+90)%360;p.cropped=false;_renderEditor();_renderPages();}
  function _rotateCCW(){if(_activeIdx<0)return;var p=_pages[_activeIdx];p.rotation=((p.rotation||0)+270)%360;p.cropped=false;_renderEditor();_renderPages();}
  function _removePage(){if(_activeIdx<0)return;_removePageAt(_activeIdx);}
  function _removePageAt(idx){
    _pages.splice(idx,1);
    if(!_pages.length){_activeIdx=-1;_showStep('capture');_renderPages();}
    else{_activeIdx=Math.min(idx,_pages.length-1);_renderEditor();_renderPages();}
  }
  function _selectPage(i){_activeIdx=i;_renderEditor();_renderPages();}
  function _addMore(){_showStep('capture');}

  // ===== PDF + UPLOAD =====
  // Load jsPDF dynamically if not available
  function _ensureJsPDF(cb) {
    var cls = (window.jspdf&&window.jspdf.jsPDF)||window.jsPDF;
    if(cls){ cb(cls); return; }
    // Try loading dynamically
    var s = document.createElement('script');
    s.src = '/static/js/jspdf.umd.min.js';
    s.onload = function(){ cb((window.jspdf&&window.jspdf.jsPDF)||window.jsPDF); };
    s.onerror = function(){ cb(null); };
    document.head.appendChild(s);
  }

  function _createAndUpload() {
    if(!_pages.length){if(typeof showToast==='function')showToast('Chưa có trang nào.','error');return;}
    var btn=document.getElementById('scanner-btn-pdf'); btn.disabled=true;
    _showProcessing('Đang tải thư viện PDF...');
    _ensureJsPDF(function(jsPDFClass){
      if(!jsPDFClass){
        _hideProcessing(); btn.disabled=false;
        if(typeof showToast==='function')showToast('Không thể tải thư viện PDF. Kiểm tra kết nối mạng.','error');
        return;
      }
      _showProcessing('Đang tạo PDF ('+_pages.length+' trang)...');
      setTimeout(function(){
        try{
          var doc=new jsPDFClass({orientation:'portrait',unit:'mm',format:'a4'});
          for(var i=0;i<_pages.length;i++){
            if(i>0)doc.addPage();
            var cv=_pages[i].canvas, imgData=cv.toDataURL('image/jpeg',0.95);
            var iw=cv.width,ih=cv.height,r=Math.min(210/iw,297/ih);
            var fw=iw*r,fh=ih*r;
            doc.addImage(imgData,'JPEG',(210-fw)/2,(297-fh)/2,fw,fh);
          }
          var blob=doc.output('blob');
          _showProcessing('Đang tải lên...');
          _uploadPDF(blob,function(ok,msg){
            _hideProcessing(); btn.disabled=false;
            if(ok){if(typeof showToast==='function')showToast(msg||'Thành công!','success');close();setTimeout(function(){location.reload();},1200);}
            else{if(typeof showToast==='function')showToast(msg||'Lỗi tải lên.','error');}
          });
        }catch(e){_hideProcessing();btn.disabled=false;if(typeof showToast==='function')showToast('Lỗi: '+e.message,'error');}
      },100);
    });
  }

  function _uploadPDF(blob,cb) {
    var fd=new FormData(), fn=_docType+'_scan_'+Date.now()+'.pdf';
    if(_docType==='HOCBA_6_9'){fd.append('files',blob,fn);fetch('/api/append-hocba/'+_studentId,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(d){cb(d.success,d.message||d.error);}).catch(function(e){cb(false,'Lỗi: '+e.message);});}
    else if(_docType==='CCCD'){fd.append('files',blob,fn);fetch('/api/upload-multi/'+_studentId+'/'+_docType,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(d){cb(d.success,d.message||d.error);}).catch(function(e){cb(false,'Lỗi: '+e.message);});}
    else{fd.append('student_id',_studentId);fd.append('doc_type',_docType);fd.append('file',blob,fn);fetch('/api/upload',{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(d){cb(d.success,d.message||d.error);}).catch(function(e){cb(false,'Lỗi: '+e.message);});}
  }

  window.DocScanner = {
    open:open, close:close, _triggerCamera:_triggerCamera, _triggerGallery:_triggerGallery,
    _rotateCW:_rotateCW, _rotateCCW:_rotateCCW, _removePage:_removePage, _removePageAt:_removePageAt,
    _selectPage:_selectPage, _addMore:_addMore, _createAndUpload:_createAndUpload, _applyFilter:_applyFilter,
    _cropConfirm:_cropConfirm, _cropRetake:_cropRetake
  };
})();
