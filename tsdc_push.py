"""
tsdc_push.py — Chay tren may LOCAL de scrape TSDC va push len PythonAnywhere.

Cach dung:
  py tsdc_push.py                     # Chay 1 lan
  py tsdc_push.py --loop              # Chay tu dong moi 30 phut
  py tsdc_push.py --url https://...   # Chi dinh URL PythonAnywhere tuy chinh

Hoac tich hop vao CHAY_MONITOR_TSDC.bat de chay nen.
"""
import asyncio, json, sys, time, argparse
import urllib.request, urllib.error

# ============================================================
# CAU HINH — chinh o day
# ============================================================
PYTHONANYWHERE_URL = 'https://ts102627.pythonanywhere.com'
TSDC_PUSH_TOKEN    = 'chuvanan_tsdc_push_2026'   # phai khop voi app.py
PUSH_INTERVAL_MIN  = 30   # push moi 30 phut khi chay --loop
# ============================================================

TSDC_USERNAME = 'qni_thcs_chuvanan1'
TSDC_PASSWORD = 'QuangNgai@06'

async def scrape_tsdc():
    from playwright.async_api import async_playwright
    print('[PUSH] Bat dau scrape TSDC...', flush=True)
    async with async_playwright() as pw:
        br   = await pw.chromium.launch(headless=True, slow_mo=0)
        page = await br.new_page(viewport={'width':1400,'height':900})
        # Login
        print('[PUSH] Login...', flush=True)
        await page.goto('https://qlts.tsdc.edu.vn', wait_until='domcontentloaded', timeout=20000)
        await asyncio.sleep(1.5)
        if await page.is_visible('input[type="password"]'):
            await page.fill('input[type="text"]',  TSDC_USERNAME)
            await page.fill('input[type="password"]', TSDC_PASSWORD)
            await page.click('button[type="submit"]')
            await asyncio.sleep(4)
        print('[PUSH] Navigate...', flush=True)
        await page.goto('https://qlts.tsdc.edu.vn/quan-ly-ho-so', wait_until='networkidle', timeout=25000)
        await asyncio.sleep(1.5)
        await page.keyboard.press('Escape'); await asyncio.sleep(0.3)
        # Click menu Ho so du tuyen
        print('[PUSH] Click menu...', flush=True)
        for item in await page.query_selector_all('li, a'):
            try:
                txt = await item.inner_text()
                if ('\u1ef1 tuy\u1ec3n' in txt or 'du tuyen' in txt.lower()) and len(txt) < 50:
                    await item.click(); await asyncio.sleep(2.5); break
            except: pass
        await asyncio.sleep(0.5)
        # Chon Cap 3
        print('[PUSH] Chon Cap 3...', flush=True)
        for sel in await page.query_selector_all('.el-select'):
            try:
                await sel.click(); await asyncio.sleep(0.5)
                opts = page.locator('.el-select-dropdown:not([style*="display: none"]) .el-select-dropdown__item')
                found = False
                for j in range(await opts.count()):
                    if 'c\u1ea5p 3' in (await opts.nth(j).inner_text()).lower():
                        await opts.nth(j).click(); found = True; break
                if not found: await page.keyboard.press('Escape'); await asyncio.sleep(0.2)
                else: break
            except: await page.keyboard.press('Escape')
        await asyncio.sleep(1.2)
        # Chon Dot THU
        print('[PUSH] Chon Dot THU...', flush=True)
        for sel in await page.query_selector_all('.el-select'):
            try:
                await sel.click(); await asyncio.sleep(0.5)
                opts = page.locator('.el-select-dropdown:not([style*="display: none"]) .el-select-dropdown__item')
                found = False
                for j in range(await opts.count()):
                    txt = await opts.nth(j).inner_text()
                    if 'th\u1EED' in txt.lower() or 'th\u1EEC' in txt:
                        await opts.nth(j).click(); found = True; break
                if not found: await page.keyboard.press('Escape'); await asyncio.sleep(0.2)
                else: break
            except: await page.keyboard.press('Escape')
        await asyncio.sleep(0.4)
        # Dong modal popup neu co (bootstrap-dialog chan click)
        print('[PUSH] Dong modal neu co...', flush=True)
        try:
            modal = page.locator('.modal.in, .bootstrap-dialog.in')
            if await modal.count() > 0:
                close_btn = modal.locator('.close, .btn-default, button').first
                if await close_btn.count() > 0:
                    await close_btn.click()
                else:
                    await page.keyboard.press('Escape')
                await asyncio.sleep(1)
        except: pass
        # Bam Escape de dam bao khong con popup nao
        await page.keyboard.press('Escape'); await asyncio.sleep(0.5)
        # Tim kiem
        print('[PUSH] Tim kiem...', flush=True)
        btn = page.locator('button').filter(has_text='T\u00ecm ki\u1ebfm')
        if await btn.count() > 0:
            # Scroll vao view va click bang JS (tranh bi chan boi overlay)
            await btn.first.scroll_into_view_if_needed()
            await page.evaluate("document.querySelector('button.el-button--primary').click()")
            await asyncio.sleep(6)
        # =====================================================
        # CHON PAGE SIZE 500 - selector xac nhan tu browser
        # Selector that: .el-pagination__sizes .el-input__inner
        # Click dropdown -> chon "500" -> doi reload -> extract
        # =====================================================
        print('[PUSH] Chon hien thi 500 ban ghi/trang...', flush=True)
        try:
            # Selector chinh xac da xac nhan tu browser inspection
            page_size_input = page.locator('.el-pagination__sizes .el-input__inner')
            if await page_size_input.count() > 0:
                await page_size_input.first.click()
                await asyncio.sleep(1)
                # Chon option "500" tu dropdown
                opt_500 = page.locator('.el-select-dropdown__item').filter(has_text='500')
                if await opt_500.count() > 0:
                    await opt_500.first.click()
                    print('[PUSH] Da chon 500/trang - doi reload...', flush=True)
                    await asyncio.sleep(4)
                else:
                    # Fallback: thu tat ca option, chon cai lon nhat
                    await page.keyboard.press('Escape')
                    await asyncio.sleep(0.3)
                    print('[PUSH] Khong co option 500, tim option lon nhat...', flush=True)
                    all_visible_opts = page.locator('.el-select-dropdown:not([style*="display: none"]) .el-select-dropdown__item')
                    best = None
                    best_val = 0
                    for j in range(await all_visible_opts.count()):
                        txt = (await all_visible_opts.nth(j).inner_text()).strip()
                        nums = [int(x) for x in txt.split() if x.isdigit()]
                        if nums and nums[0] > best_val:
                            best_val = nums[0]; best = all_visible_opts.nth(j)
                    if best:
                        await best.click()
                        print(f'[PUSH] Da chon {best_val}/trang', flush=True)
                        await asyncio.sleep(4)
                    else:
                        await page.keyboard.press('Escape')
                        print('[PUSH] Khong doi duoc page size - chi lay trang hien tai', flush=True)
            else:
                print('[PUSH] Khong tim thay .el-pagination__sizes, bo qua', flush=True)
        except Exception as pe:
            print(f'[PUSH] Loi chon page size: {pe}', flush=True)

        await asyncio.sleep(2)
        # Extract
        print('[PUSH] Extract data...', flush=True)
        JS = r"""
() => {
    var rows = Array.from(document.querySelectorAll('tbody tr'));
    var students = [];
    /* Nhan dang ma ho so TSDC: HSO2651900039... hoac HS2... */
    function isMaHS(t){
        if(t.startsWith('HSO') && t.length > 8) return true;
        return t.startsWith('HS') && t.length > 5 &&
               t.charCodeAt(2) >= 48 && t.charCodeAt(2) <= 57;
    }
    function isDate(t){return t.length===10&&t.charAt(2)==='/'&&t.charAt(5)==='/';}
    function isNVSchool(t){
        return t.indexOf('THPT')!==-1||t.indexOf('PTDT')!==-1||
               t.indexOf('Lien Viet')!==-1||t.indexOf('THCS')!==-1;
    }
    function isLop(t){
        if(t.length<2||t.length>5) return false;
        if(t.charAt(0)==='9'){var c=t.charCodeAt(1);return c>=65&&c<=90;}
        if(t.charAt(0)==='1'&&t.charAt(1)==='0'&&t.length>2){
            var c=t.charCodeAt(2);return c>=65&&c<=90;
        }
        return false;
    }
    rows.forEach(function(row){
        var cells=Array.from(row.querySelectorAll('td')).map(function(c){return c.innerText.trim();});
        /* Chi xu ly row co ma ho so (HSO...) */
        if(!cells.some(function(t){return isMaHS(t);})) return;
        var s={maHocSinh:'',hoTen:'',trangThai:'',ngaySinh:'',lop:'',
               nv1:'',nv2:'',nv3:'',cccd:'',maDinhDanh:'',gioiTinh:''};
        var nvs=[], nums12=[], nums9=[], nums10=[];
        cells.forEach(function(t){
            if(!t) return;
            if(isMaHS(t)){s.maHocSinh=t;}
            if(isDate(t)&&!s.ngaySinh){s.ngaySinh=t;}
            else if(t==='Nam'||t==='\u0110\u1ea1'||t==='N\u1eef'){s.gioiTinh=t;}
            /* Bat moi trang thai TSDC - khong gioi han tu khoa */
            else if(
                t.includes('ti\u1ebfp nh\u1eadn') || t.includes('Ti\u1ebfp nh\u1eadn') ||
                t.includes('x\u00e9t duy\u1ec7t') || t.includes('Ch\u1edd') ||
                t.includes('xet duyet') || t.includes('\u0110\u00e3 ti\u1ebfp') ||
                t.includes('duy\u1ec7t') || t.includes('x\u1eed l\u00fd') ||
                t.includes('b\u1ecb t\u1eeb ch\u1ed1i') || t.includes('ho\u00e0n th\u00e0nh') ||
                t.includes('tr\u1ea1ng th\u00e1i')
            ){s.trangThai=t;}
            else if(t.includes('@')){/* skip email */}
            else if(isLop(t)){s.lop=t;}
            else if(isNVSchool(t)){nvs.push(t);}
            /* So dinh danh/CCCD: 12 chu so; Ma dinh danh GD: 9-10 chu so */
            else if(/^\d{12}$/.test(t)){nums12.push(t);}
            else if(/^\d{10}$/.test(t)){nums10.push(t);}
            else if(/^\d{9}$/.test(t)){nums9.push(t);}
            /* Ho ten: text dai hon 1 tu, khong phai so, khong phai truong */
            else if(!s.hoTen && t.length>3 && !/^\d+$/.test(t) &&
                    !isNVSchool(t) && !isMaHS(t) && !isLop(t) &&
                    t.indexOf('Tr\u01b0\u1eddng')===-1){
                s.hoTen=t;
            }
        });
        /* 12 so = CCCD; 10 so = Ma dinh danh GD; 9 so = CMND cu */
        if(nums12.length>0) s.cccd=nums12[0];
        if(nums10.length>0) s.maDinhDanh=nums10[0];
        else if(nums9.length>0) s.maDinhDanh=nums9[0];
        if(nvs[0])s.nv1=nvs[0]; if(nvs[1])s.nv2=nvs[1]; if(nvs[2])s.nv3=nvs[2];
        if(s.maHocSinh || s.hoTen) students.push(s);
    });
    return {students:students, rowCount:rows.length};
}
"""

        raw = await page.evaluate(JS)
        await br.close()
        students = raw.get('students', [])
        print(f'[PUSH] Tim duoc {len(students)} hoc sinh', flush=True)
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
                      'trangThai':s.get('trangThai',''),
                      'ngaySinh':s.get('ngaySinh',''),
                      'cccd':s.get('cccd',''),
                      'maDinhDanh':s.get('maDinhDanh',''),
                      'maHocSinh':s.get('maHocSinh',''),
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
            print(f'[PUSH] Thanh cong! {result}', flush=True)
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f'[PUSH] Loi HTTP {e.code}: {body}', flush=True)
    except Exception as e:
        print(f'[PUSH] Loi: {e}', flush=True)
    return False

def run_once(base_url):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        students = loop.run_until_complete(scrape_tsdc())
    finally:
        loop.close()
    data = build_stats(students)
    print(f'[PUSH] Dang push {data["total"]} HS len {base_url}...', flush=True)
    return push_to_pythonanywhere(data, base_url)

def main():
    parser = argparse.ArgumentParser(description='TSDC Push - Scrape va push len PythonAnywhere')
    parser.add_argument('--loop', action='store_true', help=f'Lap lai moi {PUSH_INTERVAL_MIN} phut')
    parser.add_argument('--url', default=PYTHONANYWHERE_URL, help='URL PythonAnywhere')
    args = parser.parse_args()

    print('='*55, flush=True)
    print('  TSDC PUSH TOOL — THCS Chu Van An', flush=True)
    print(f'  Target: {args.url}', flush=True)
    print(f'  Mode: {"Tu dong moi " + str(PUSH_INTERVAL_MIN) + " phut" if args.loop else "Chay 1 lan"}', flush=True)
    print('='*55, flush=True)

    if args.loop:
        while True:
            try:
                run_once(args.url)
            except Exception as e:
                print(f'[PUSH] Loi: {e}', flush=True)
            print(f'[PUSH] Cho {PUSH_INTERVAL_MIN} phut roi push lai...', flush=True)
            time.sleep(PUSH_INTERVAL_MIN * 60)
    else:
        ok = run_once(args.url)
        sys.exit(0 if ok else 1)

if __name__ == '__main__':
    main()
