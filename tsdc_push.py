"""
tsdc_push.py — Chay tren may LOCAL de scrape TSDC va push len PythonAnywhere.

Cach dung:
  py tsdc_push.py                     # Chay 1 lan
  py tsdc_push.py --loop              # Chay tu dong moi 30 phut
  py tsdc_push.py --url https://...   # Chi dinh URL PythonAnywhere tuy chinh
"""
import asyncio, json, sys, time, argparse
import urllib.request, urllib.error

# ============================================================
# CAU HINH — chinh o day
# ============================================================
PYTHONANYWHERE_URL = 'https://ts102627.pythonanywhere.com'
TSDC_PUSH_TOKEN    = 'chuvanan_tsdc_push_2026'   # phai khop voi app.py va Apps Script
PUSH_INTERVAL_MIN  = 30   # push moi 30 phut khi chay --loop

# Google Apps Script Web App URL
APPS_SCRIPT_URL = 'https://script.google.com/macros/s/AKfycbzIxSlNum5oRdASLpAKRgnt_GYefUx2uwtCmu9OzKmtpKr0Zi3AnYyKOhaDSunvhsxC/exec'
# ============================================================

TSDC_USERNAME = 'qni_thcs_chuvanan1'
TSDC_PASSWORD = 'QuangNgai@06'

# ============================================================
# DOT TUYEN SINH — mapping tu so nguoi dung nhap sang keyword tim trong dropdown
# ============================================================
DOT_MODE_MAP = {
    1: {'keyword': 'CHÍNH THỨC',  'label': 'Đợt Thi Thật (CHÍNH THỨC)'},
    2: {'keyword': 'THỬ',         'label': 'Đợt Thi Thử (THỬ)'},
    3: {'keyword': 'Tập huấn',    'label': 'Đợt Tập huấn'},
}

# ============================================================
# JS PARSER — lay y nguyen tu tsdc_monitor.py (dang chay dung)
# ============================================================
_JS_EXTRACT = r"""
() => {
    /* CAU TRUC DOM TSDC (da xac nhan bang debug):
     *  tbody[0]: HS rows   (row 0 = HS thu 1, row 1 = HS thu 2, ...)
     *  tbody[1]: HSO rows  (row 0 = HSO cua HS thu 1, row 1 = HSO cua HS thu 2, ...)
     *  tbody[2]: empty rows
     *  tbody[3]: Tai xuong menu
     * => Match by SAME INDEX giua tbody[0] va tbody[1]
     */
    var tbodies = document.querySelectorAll('tbody');
    var hsRows  = tbodies[0] ? Array.from(tbodies[0].querySelectorAll('tr')) : [];
    var hsoRows = tbodies[1] ? Array.from(tbodies[1].querySelectorAll('tr')) : [];

    function isMaHS(t) {
        return t.startsWith('HS') && !t.startsWith('HSO') &&
               t.length > 5 && t.charCodeAt(2) >= 48 && t.charCodeAt(2) <= 57;
    }
    function isDate(t) {
        return t.length === 10 && t.charAt(2) === '/' && t.charAt(5) === '/';
    }
    function allDigits(t) {
        for (var i=0; i<t.length; i++) if (t.charCodeAt(i)<48||t.charCodeAt(i)>57) return false;
        return true;
    }
    function isIdOrCCCD(t) {
        if (t.length<9||t.length>12||!allDigits(t)) return false;
        if (t.length===10 && t.charAt(0)==='0') return false;
        return true;
    }
    function isLop(t) {
        if (t.length<2||t.length>5) return false;
        if (t.charAt(0)==='9') { var c=t.charCodeAt(1); return c>=65&&c<=90; }
        if (t.charAt(0)==='1'&&t.charAt(1)==='0'&&t.length>2) { var c=t.charCodeAt(2); return c>=65&&c<=90; }
        return false;
    }
    function isNVSchool(t) {
        return t.indexOf('THPT')!==-1 || t.indexOf('PTDT')!==-1;
    }
    function isPhone(t) {
        /* SĐT Viet Nam: 10 chu so, bat dau 0, loai tru CCCD 12 chu so */
        var clean = t.replace(/[\s\-\.]/g,'');
        if (clean.length!==10 && clean.length!==11) return false;
        if (clean.charAt(0)!=='0') return false;
        return allDigits(clean);
    }
    function getHSO(row) {
        var cells = Array.from(row.querySelectorAll('td')).map(function(c){ return c.innerText.trim(); });
        for (var i=0; i<cells.length; i++) {
            if (cells[i].startsWith('HSO') && cells[i].length > 8) return cells[i];
        }
        return '';
    }

    var students = [];
    for (var i = 0; i < hsRows.length; i++) {
        var cells = Array.from(hsRows[i].querySelectorAll('td')).map(function(c){ return c.innerText.trim(); });
        if (!cells.some(isMaHS)) continue;

        var s = {maHoSo:'',maHocSinh:'',hoTen:'',trangThai:'',
                 ngaySinh:'',gioiTinh:'',soDienThoai:'',email:'',
                 maDinhDanh:'',soCCCD:'',lop:'',nv1:'',nv2:'',nv3:''};
        var afterLop=false, nvs=[];

        cells.forEach(function(t) {
            if (!t) return;
            if (isMaHS(t))               { s.maHocSinh=t; }
            else if (isDate(t))          { s.ngaySinh=t; }
            else if (t==='\u0110\u1ea1'||t==='N\u1eef') { s.gioiTinh=t; }
            else if (t==='Nam')          { s.gioiTinh='Nam'; }
            else if (t.indexOf('@')!==-1) { s.email=t; }
            else if (isPhone(t))         { s.soDienThoai=t.replace(/[\s\-\.]/g,''); }
            else if (isIdOrCCCD(t)) {
                if (!s.maDinhDanh) s.maDinhDanh=t; else s.soCCCD=t;
            }
            else if (t.indexOf('x\u00e9t duy\u1ec7t')!==-1||t.indexOf('ti\u1ebfp nh\u1eadn')!==-1||t.indexOf('Ch\u1edd')!==-1) {
                s.trangThai=t;
            }
            else if (isLop(t))           { s.lop=t; afterLop=true; }
            else if (afterLop && isNVSchool(t)) { nvs.push(t.substring(0,80)); }
        });

        /* Tim ho ten */
        for (var j=0; j<cells.length; j++) {
            var t=cells[j];
            if (t&&t.length>2&&!t.startsWith('HS')&&!isDate(t)&&!isIdOrCCCD(t)&&
                t!=='Nam'&&t!=='\u0110\u1ea1'&&t!=='N\u1eef'&&t.indexOf('@')===-1&&
                t.indexOf('Tr\u01b0\u1eddng')===-1&&t.indexOf('THPT')===-1&&t.indexOf('PTDT')===-1&&
                !isLop(t)&&!allDigits(t)&&
                t.indexOf('duy\u1ec7t')===-1&&t.indexOf('nh\u1eadn')===-1&&t.indexOf('Thao')===-1) {
                if (!s.hoTen) s.hoTen=t;
            }
        }

        if (nvs[0]) s.nv1=nvs[0];
        if (nvs[1]) s.nv2=nvs[1];
        if (nvs[2]) s.nv3=nvs[2];

        /* Lay HSO tu tbody[1] cung index */
        if (hsoRows[i]) s.maHoSo = getHSO(hsoRows[i]);

        if (s.maHocSinh || s.hoTen) students.push(s);
    }

    /* Loc theo truong Chu Van An */
    var filtered = students.filter(function(s) {
        return hsRows.some(function(row, idx) {
            var txt = row.innerText || '';
            return txt.indexOf('Chu V\u0103n An') !== -1 &&
                   (row.innerText || '').indexOf(s.maHocSinh) !== -1;
        });
    });
    if (filtered.length === 0) filtered = students;
    return {students:filtered, rowCount:hsRows.length, total:students.length};
}
"""


async def select_option(page, option_text):
    """Chon option trong el-select - giong tsdc_monitor.select_el_option"""
    all_selects = await page.query_selector_all('.el-select')
    for sel in all_selects:
        try:
            await sel.click()
            await asyncio.sleep(0.8)
            opts = page.locator('.el-select-dropdown:not([style*="display: none"]) .el-select-dropdown__item')
            cnt = await opts.count()
            for j in range(cnt):
                txt = await opts.nth(j).inner_text()
                if option_text.lower()[:8] in txt.lower():
                    await opts.nth(j).click()
                    print(f'[PUSH]   Da chon: {txt.strip()[:50]}', flush=True)
                    return True
            await page.keyboard.press('Escape')
        except:
            await page.keyboard.press('Escape')
    return False


async def select_option_nth(page, nth_index, option_text):
    """Chon option trong el-select thu nth_index (0-based) - tranh click nham dropdown khac.
    Uu tien khop chinh xac truoc, fallback substring 8 ky tu.
    """
    all_selects = await page.query_selector_all('.el-select')
    if nth_index >= len(all_selects):
        print(f'[PUSH]   Khong tim thay el-select index {nth_index} (chi co {len(all_selects)})', flush=True)
        return False
    sel = all_selects[nth_index]
    try:
        await sel.click()
        await asyncio.sleep(1.0)
        opts = page.locator('.el-select-dropdown:not([style*="display: none"]) .el-select-dropdown__item')
        cnt = await opts.count()
        if cnt == 0:
            print(f'[PUSH]   el-select[{nth_index}]: khong co option nao mo', flush=True)
            await page.keyboard.press('Escape')
            return False
        # Uu tien khop chinh xac (case-insensitive)
        for j in range(cnt):
            txt = await opts.nth(j).inner_text()
            if option_text.lower() in txt.lower():
                await opts.nth(j).click()
                print(f'[PUSH]   el-select[{nth_index}] chon: {txt.strip()[:60]}', flush=True)
                return True
        # Fallback: khop 8 ky tu dau
        for j in range(cnt):
            txt = await opts.nth(j).inner_text()
            if option_text.lower()[:8] in txt.lower():
                await opts.nth(j).click()
                print(f'[PUSH]   el-select[{nth_index}] chon (fallback): {txt.strip()[:60]}', flush=True)
                return True
        # Debug: in tat ca option tim thay
        all_opts = [await opts.nth(j).inner_text() for j in range(cnt)]
        print(f'[PUSH]   el-select[{nth_index}]: khong khop "{option_text}". Options: {all_opts}', flush=True)
        await page.keyboard.press('Escape')
    except Exception as e:
        print(f'[PUSH]   el-select[{nth_index}] loi: {e}', flush=True)
        await page.keyboard.press('Escape')
    return False


async def extract_page(page):
    """Extract hoc sinh tu bang hien tai (1 trang)"""
    raw = await page.evaluate(_JS_EXTRACT)
    students = raw.get('students', [])
    rows = raw.get('rowCount', 0)
    print(f'[PUSH]   Trang: {rows} rows -> {len(students)} hoc sinh', flush=True)
    return students


async def scrape_tsdc(dot_mode=1):
    from playwright.async_api import async_playwright
    print('[PUSH] Bat dau scrape TSDC...', flush=True)
    async with async_playwright() as pw:
        br   = await pw.chromium.launch(headless=True, slow_mo=0)
        page = await br.new_page(viewport={'width':1400,'height':900})

        # 1. Login
        print('[PUSH] Login...', flush=True)
        await page.goto('https://qlts.tsdc.edu.vn', wait_until='domcontentloaded', timeout=20000)
        await asyncio.sleep(2)
        if await page.is_visible('input[type="password"]'):
            await page.fill('input[type="text"]',  TSDC_USERNAME)
            await page.fill('input[type="password"]', TSDC_PASSWORD)
            await page.click('button[type="submit"]')
            await asyncio.sleep(5)

        # 2. Navigate
        print('[PUSH] Navigate...', flush=True)
        await page.goto('https://qlts.tsdc.edu.vn/quan-ly-ho-so', wait_until='networkidle', timeout=25000)
        await asyncio.sleep(2)
        await page.keyboard.press('Escape'); await asyncio.sleep(0.3)

        # 3. Click menu Ho so du tuyen
        print('[PUSH] Click menu...', flush=True)
        for item in await page.query_selector_all('li, a'):
            try:
                txt = await item.inner_text()
                if '\u1ef1 tuy\u1ec3n' in txt and len(txt) < 50:
                    await item.click(); await asyncio.sleep(2); break
            except: pass
        await asyncio.sleep(2)
        try: await page.keyboard.press('Escape'); await asyncio.sleep(0.3)
        except: pass

        # 4. Chon Cap 3
        # DEBUG xac nhan: el-select[0]=Don vi, [1]=component con Don vi (khong mo duoc),
        #                 [2]=Cap hoc, [3]=Dot tuyen sinh
        print('[PUSH] Chon Cap 3 (el-select[2])...', flush=True)
        await select_option_nth(page, 2, 'C\u1ea5p 3')
        await asyncio.sleep(0.5)
        await page.keyboard.press('Escape'); await asyncio.sleep(0.2)

        # 5. Chon Dot tuyen sinh — el-select index 3
        # Cho phep nguoi dung chon qua tham so --dot (1=Chinh thuc, 2=Thu, 3=Tap huan)
        dot_info = DOT_MODE_MAP.get(dot_mode, DOT_MODE_MAP[1])
        dot_keyword = dot_info['keyword']
        dot_label   = dot_info['label']
        print(f'[PUSH] Chon Dot: {dot_label} (keyword="{dot_keyword}", el-select[3])...', flush=True)
        if not await select_option_nth(page, 3, dot_keyword):
            print(f'[PUSH] Khong tim thay "{dot_keyword}" trong dropdown!', flush=True)
            # Fallback: thu chon CHINH THUC neu dang chon dot khac
            if dot_mode != 1:
                print('[PUSH] Fallback: thu chon CHINH THUC...', flush=True)
                await select_option_nth(page, 3, 'CHÍNH THỨC')
        await asyncio.sleep(0.5)

        # 6. Dong modal neu co
        print('[PUSH] Dong modal neu co...', flush=True)
        try:
            modal = page.locator('.modal.in, .bootstrap-dialog.in')
            if await modal.count() > 0:
                close_btn = modal.locator('.close, .btn-default, button').first
                if await close_btn.count() > 0: await close_btn.click()
                else: await page.keyboard.press('Escape')
                await asyncio.sleep(1)
        except: pass
        await page.keyboard.press('Escape'); await asyncio.sleep(0.5)

        # 7. CHON 500/TRANG TRUOC KHI TIM KIEM
        # Theo debug: "Xem tren trang" dropdown nam cuoi trang
        # Can chon truoc roi tim kiem de ket qua hien thi du
        # Dau tien lam search 1 lan de page render xong
        print('[PUSH] Tim kiem lan 1 (de page render)...', flush=True)
        btn = page.locator('button').filter(has_text='T\u00ecm ki\u1ebfm')
        if await btn.count() > 0:
            await btn.first.click()
            await asyncio.sleep(5)

        # 8. CHON 500/TRANG sau khi page render
        print('[PUSH] Chon hien thi 500 ban ghi/trang...', flush=True)
        try:
            # Scroll xuong cuoi de thay "Xem tren trang"
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(1.5)

            # Lay tat ca el-select sau khi ket qua hien ra
            # "Xem tren trang" la el-select cuoi cung tren trang
            all_selects_now = await page.query_selector_all('.el-select')
            print(f'[PUSH] So el-select tim thay: {len(all_selects_now)}', flush=True)
            page_size_chosen = False
            for sel in reversed(all_selects_now):
                try:
                    inner = await sel.query_selector('.el-input__inner')
                    if not inner:
                        continue
                    cur_val = await inner.input_value()
                    print(f'[PUSH]   el-select gia tri: "{cur_val}"', flush=True)
                    # Chi chon khi gia tri la so NGUYEN (10, 20, 50, 100...) - tranh chon --Chon--
                    if cur_val.strip().isdigit():
                        await inner.click()
                        await asyncio.sleep(1)
                        opt = page.locator('.el-select-dropdown__item').filter(has_text='500')
                        if await opt.count() > 0:
                            await opt.first.click()
                            print('[PUSH] Da chon 500/trang!', flush=True)
                            page_size_chosen = True
                            await asyncio.sleep(1)
                            break
                        else:
                            await page.keyboard.press('Escape')
                            await asyncio.sleep(0.3)
                except:
                    await page.keyboard.press('Escape')

            if not page_size_chosen:
                print('[PUSH] Khong doi duoc page size, se tim kiem truc tiep', flush=True)
        except Exception as pe:
            print(f'[PUSH] Loi chon page size: {pe}', flush=True)

        # 9. TIM KIEM LAI (de ap dung page size moi)
        print('[PUSH] Tim kiem lai voi page size moi...', flush=True)
        await page.evaluate('window.scrollTo(0, 0)')
        await asyncio.sleep(0.5)
        btn = page.locator('button').filter(has_text='T\u00ecm ki\u1ebfm')
        if await btn.count() > 0:
            await btn.first.click()
            await asyncio.sleep(8)  # Cho du toan bo ket qua load

        # 10. EXTRACT (1 lan - tat ca hs da hien thi)
        print('[PUSH] Extract tat ca hoc sinh...', flush=True)
        await asyncio.sleep(2)
        raw = await page.evaluate(_JS_EXTRACT)
        await br.close()
        students = raw.get('students', [])
        print(f'[PUSH] Tim duoc {len(students)} hoc sinh (tu {raw.get("rowCount",0)} rows)', flush=True)
        return students


def build_stats(students):
    from datetime import datetime
    status_map, nv1, nv2, nv3 = {}, {}, {}, {}
    for s in students:
        st = s.get('trangThai','') or 'Kh\u00f4ng r\u00f5'
        status_map[st] = status_map.get(st, 0) + 1
        for field, mp in [('nv1',nv1),('nv2',nv2),('nv3',nv3)]:
            v = s.get(field,'')
            if v: mp[v] = mp.get(v,0) + 1
    return {
        'total': len(students),
        'status': dict(sorted(status_map.items(), key=lambda x: -x[1])),
        'nv1': sorted(nv1.items(), key=lambda x: -x[1]),
        'nv2': sorted(nv2.items(), key=lambda x: -x[1]),
        'nv3': sorted(nv3.items(), key=lambda x: -x[1]),
        'students': [{'hoTen':s.get('hoTen',''),'lop':s.get('lop',''),
                      'gioiTinh':s.get('gioiTinh',''),
                      'soDienThoai':s.get('soDienThoai',''),
                      'email':s.get('email',''),
                      'trangThai':s.get('trangThai',''),
                      'ngaySinh':s.get('ngaySinh',''),
                      'soCCCD':s.get('soCCCD',''),
                      'maDinhDanh':s.get('maDinhDanh',''),
                      'maHocSinh':s.get('maHocSinh',''),
                      'maHoSo':s.get('maHoSo',''),
                      'nv1':s.get('nv1',''),'nv2':s.get('nv2',''),'nv3':s.get('nv3','')}
                     for s in students],
        'updated_at': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    }


def push_to_pythonanywhere(data, base_url):
    url = base_url.rstrip('/') + '/api/tsdc-push'
    payload = json.dumps({'token': TSDC_PUSH_TOKEN, **data}, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(url, data=payload,
                                  headers={'Content-Type': 'application/json; charset=utf-8'},
                                  method='POST')
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            print(f'[PUSH] PythonAnywhere: Thanh cong! {result}', flush=True)
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f'[PUSH] PythonAnywhere Loi HTTP {e.code}: {body}', flush=True)
    except Exception as e:
        print(f'[PUSH] PythonAnywhere Loi: {e}', flush=True)
    return False


def push_to_sheets(data):
    """Push du lieu len Google Sheets qua Apps Script Web App"""
    if not APPS_SCRIPT_URL:
        print('[PUSH] Chua cau hinh APPS_SCRIPT_URL, bo qua', flush=True)
        return False
    print(f'[PUSH] Dang dong bo len Google Sheets ({data["total"]} HS)...', flush=True)
    payload = json.dumps({'token': TSDC_PUSH_TOKEN, **data}, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        APPS_SCRIPT_URL, data=payload,
        headers={'Content-Type': 'application/json; charset=utf-8'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            if result.get('success'):
                print(f'[PUSH] Google Sheets: OK! {result.get("total")} HS | {result.get("updated_at")}', flush=True)
                if result.get('sheet_url'):
                    print(f'[PUSH] Xem tai: {result["sheet_url"]}', flush=True)
                return True
            else:
                print(f'[PUSH] Google Sheets Loi: {result}', flush=True)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f'[PUSH] Google Sheets HTTP {e.code}: {body[:200]}', flush=True)
    except Exception as e:
        print(f'[PUSH] Google Sheets Loi: {e}', flush=True)
    return False


def run_once(base_url, dot_mode=1):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        students = loop.run_until_complete(scrape_tsdc(dot_mode=dot_mode))
    finally:
        loop.close()
    data = build_stats(students)
    # Push len ca hai noi song song
    ok_pa     = push_to_pythonanywhere(data, base_url)
    ok_sheets = push_to_sheets(data)
    return ok_pa or ok_sheets


def main():
    parser = argparse.ArgumentParser(description='TSDC Push - Scrape va push len PythonAnywhere')
    parser.add_argument('--loop', action='store_true', help=f'Lap lai moi {PUSH_INTERVAL_MIN} phut')
    parser.add_argument('--url', default=PYTHONANYWHERE_URL, help='URL PythonAnywhere')
    parser.add_argument('--dot', type=int, default=1, choices=[1, 2, 3],
                        help='Chon dot tuyen sinh: 1=Thi That (CHINH THUC), 2=Thi Thu, 3=Tap huan')
    args = parser.parse_args()

    dot_info = DOT_MODE_MAP.get(args.dot, DOT_MODE_MAP[1])
    print('='*55, flush=True)
    print('  TSDC PUSH TOOL — THCS Chu Van An', flush=True)
    print(f'  Target: {args.url}', flush=True)
    print(f'  Dot thi: {dot_info["label"]}', flush=True)
    print(f'  Mode: {"Tu dong moi " + str(PUSH_INTERVAL_MIN) + " phut" if args.loop else "Chay 1 lan"}', flush=True)
    print('='*55, flush=True)

    if args.loop:
        while True:
            try:
                run_once(args.url, dot_mode=args.dot)
            except Exception as e:
                print(f'[PUSH] Loi: {e}', flush=True)
            print(f'[PUSH] Cho {PUSH_INTERVAL_MIN} phut roi push lai...', flush=True)
            time.sleep(PUSH_INTERVAL_MIN * 60)
    else:
        ok = run_once(args.url, dot_mode=args.dot)
        sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
