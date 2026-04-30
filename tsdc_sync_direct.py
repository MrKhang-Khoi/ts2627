"""
tsdc_sync_direct.py — Sync du lieu TSDC truc tiep vao DB (khong can Flask).
Chay khi: Flask chua start, hoac muon sync local DB nhanh.

Cach dung: py tsdc_sync_direct.py
"""
import asyncio, sys, unicodedata
import sqlite3
from datetime import datetime
# Fix Unicode encoding cho Windows CMD
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TSDC_USERNAME = 'qni_thcs_chuvanan1'
TSDC_PASSWORD = 'QuangNgai@06'
DB_PATH = 'database.db'   # Relative - chay tu thu muc hoso_lop10_app
# ====================================================

def normalize_name(name):
    name = name.strip().lower()
    name = unicodedata.normalize('NFD', name)
    name = ''.join(c for c in name if unicodedata.category(c) != 'Mn')
    return ' '.join(name.split())

async def scrape_tsdc():
    from playwright.async_api import async_playwright
    print('[SYNC] Bat dau scrape TSDC...', flush=True)
    async with async_playwright() as pw:
        br   = await pw.chromium.launch(headless=True, slow_mo=0)
        page = await br.new_page(viewport={'width':1400,'height':900})
        print('[SYNC] Login...', flush=True)
        await page.goto('https://qlts.tsdc.edu.vn', wait_until='domcontentloaded', timeout=20000)
        await asyncio.sleep(1.5)
        if await page.is_visible('input[type="password"]'):
            await page.fill('input[type="text"]',  TSDC_USERNAME)
            await page.fill('input[type="password"]', TSDC_PASSWORD)
            await page.click('button[type="submit"]')
            await asyncio.sleep(4)
        print('[SYNC] Navigate...', flush=True)
        await page.goto('https://qlts.tsdc.edu.vn/quan-ly-ho-so', wait_until='networkidle', timeout=25000)
        await asyncio.sleep(1.5)
        await page.keyboard.press('Escape'); await asyncio.sleep(0.3)
        print('[SYNC] Click menu Ho so du tuyen...', flush=True)
        for item in await page.query_selector_all('li, a'):
            try:
                txt = await item.inner_text()
                if ('\u1ef1 tuy\u1ec3n' in txt or 'du tuyen' in txt.lower()) and len(txt) < 50:
                    await item.click(); await asyncio.sleep(2.5); break
            except: pass
        await asyncio.sleep(0.5)
        print('[SYNC] Chon Cap 3...', flush=True)
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
        print('[SYNC] Chon Dot THU...', flush=True)
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
        # Dong modal neu co
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
        await page.keyboard.press('Escape'); await asyncio.sleep(0.5)
        print('[SYNC] Tim kiem...', flush=True)
        try:
            await page.evaluate("document.querySelector('button.el-button--primary').click()")
        except: pass
        await asyncio.sleep(6)
        print('[SYNC] Extract du lieu...', flush=True)
        JS = r"""
() => {
    var rows = Array.from(document.querySelectorAll('tbody tr'));
    var students = [];
    function isMaHS(t){return t.startsWith('HS')&&t.length>5&&t.charCodeAt(2)>=48&&t.charCodeAt(2)<=57;}
    function isDate(t){return t.length===10&&t.charAt(2)==='/'&&t.charAt(5)==='/';}
    function isNVSchool(t){return t.indexOf('THPT')!==-1||t.indexOf('PTDT')!==-1||t.indexOf('Lien Viet')!==-1||t.indexOf('THCS')!==-1;}
    function isLop(t){if(t.length<2||t.length>5)return false;if(t.charAt(0)==='9'){var c=t.charCodeAt(1);return c>=65&&c<=90;}return false;}
    rows.forEach(function(row){
        var cells=Array.from(row.querySelectorAll('td')).map(function(c){return c.innerText.trim();});
        if(!cells.some(function(t){return isMaHS(t);}))return;
        var s={maHocSinh:'',hoTen:'',trangThai:'',ngaySinh:'',lop:'',nv1:'',nv2:'',nv3:'',cccd:'',maDinhDanh:''};
        var nvs=[], nums12=[], nums9=[];
        cells.forEach(function(t){
            if(!t)return;
            if(isMaHS(t)){s.maHocSinh=t;}
            else if(isDate(t)&&!s.ngaySinh){s.ngaySinh=t;}
            else if(t.includes('ti\u1ebfp nh\u1eadn')||t.includes('Ti\u1ebfp nh\u1eadn')){s.trangThai=t;}
            else if(t.includes('xét duyệt')||t.includes('Ch\u1edd xét')){s.trangThai=t;}
            else if(isLop(t)){s.lop=t;}
            else if(isNVSchool(t)){nvs.push(t);}
            else if(/^\d{12}$/.test(t)){nums12.push(t);}
            else if(/^\d{9,10}$/.test(t)){nums9.push(t);}
            else if(!s.hoTen&&t.length>4&&!isNVSchool(t)&&!isMaHS(t)&&!/^\d+$/.test(t)){s.hoTen=t;}
        });
        if(nums12.length>0)s.cccd=nums12[0];
        if(nums9.length>0)s.maDinhDanh=nums9[0];
        if(nvs[0])s.nv1=nvs[0];if(nvs[1])s.nv2=nvs[1];if(nvs[2])s.nv3=nvs[2];
        if(s.maHocSinh||s.hoTen)students.push(s);
    });
    return {students:students,rowCount:rows.length};
}
"""
        raw = await page.evaluate(JS)
        await br.close()
        return raw.get('students', [])

def sync_to_db(students):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    now_str = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

    # Bao dam cac cot ton tai
    existing_cols = {row[1] for row in conn.execute('PRAGMA table_info(students)').fetchall()}
    for col in ['cccd','ma_dinh_danh_gd','tsdc_ma_hoso','tsdc_trang_thai',
                'tsdc_nv1','tsdc_nv2','tsdc_nv3','tsdc_updated_at']:
        if col not in existing_cols:
            conn.execute(f'ALTER TABLE students ADD COLUMN {col} TEXT')
            print(f'[SYNC] Them cot: {col}')

    # Load tat ca HS local
    all_local = conn.execute('SELECT id, ho_ten, ho_ten_khong_dau, ngay_sinh, cccd FROM students').fetchall()
    by_cccd, by_dob_name = {}, {}
    for s in all_local:
        if s['cccd']:
            by_cccd[s['cccd'].strip()] = s['id']
        dob = (s['ngay_sinh'] or '').strip()
        # Dung ho_ten (co dau cach) de normalize - chinh xac hon ho_ten_khong_dau (CamelCase)
        name_with_space = normalize_name(s['ho_ten'] or '')
        by_dob_name[dob + '|' + name_with_space] = (s['id'], s['ho_ten'])
        if s['ho_ten_khong_dau']:
            name_camel = normalize_name(s['ho_ten_khong_dau'])
            by_dob_name[dob + '|' + name_camel] = (s['id'], s['ho_ten'])

    print(f'\n[SYNC] === So sanh du lieu ===')
    print(f'[SYNC] TSDC co: {len(students)} hoc sinh')
    print(f'[SYNC] DB local co: {len(all_local)} hoc sinh')
    print()

    updated = 0
    for ts in students:
        cccd   = (ts.get('cccd') or '').strip()
        dob    = (ts.get('ngaySinh') or '').strip()
        name   = (ts.get('hoTen') or '').strip()
        nv1    = ts.get('nv1', '')
        nv2    = ts.get('nv2', '')
        nv3    = ts.get('nv3', '')
        trang  = ts.get('trangThai', '')
        mahoso = ts.get('maHocSinh', '')

        sid, match = None, None

        # 1. CCCD
        if cccd and cccd in by_cccd:
            sid = by_cccd[cccd]; match = f'CCCD={cccd}'

        # 2. DOB + ten chuan hoa
        if not sid and dob:
            name_norm = normalize_name(name)
            key = dob + '|' + name_norm
            if key in by_dob_name:
                sid, local_name = by_dob_name[key]
                match = f'DOB+name ({local_name})'
            else:
                # Debug: hien thi tat ca ten trong DB de tim
                print(f'[SYNC] Khong khop: TSDC="{name}" ({dob}) norm="{name_norm}"')
                print(f'       DB keys co: {[k for k in by_dob_name if dob in k]}')

        if sid:
            conn.execute("""UPDATE students
                SET tsdc_nv1=?, tsdc_nv2=?, tsdc_nv3=?,
                    tsdc_trang_thai=?, tsdc_ma_hoso=?, tsdc_updated_at=?
                WHERE id=?""",
                (nv1, nv2, nv3, trang, mahoso, now_str, sid))
            if cccd:
                conn.execute("UPDATE students SET cccd=? WHERE id=?", (cccd, sid))
            updated += 1
            print(f'[SYNC] ✓ [{match}] {name} ({dob}) → NV1: {nv1[:35] if nv1 else "N/A"}')
        else:
            print(f'[SYNC] ✗ Khong tim thay trong DB: "{name}" ({dob})')

    conn.commit()
    conn.close()
    print(f'\n[SYNC] Xong: {updated}/{len(students)} hoc sinh duoc cap nhat DB.')
    return updated

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        students = loop.run_until_complete(scrape_tsdc())
    finally:
        loop.close()
    print(f'\n[SYNC] TSDC tra ve {len(students)} hoc sinh:')
    for s in students:
        print(f'  {s.get("hoTen")} | {s.get("ngaySinh")} | CCCD={s.get("cccd")} | NV1={s.get("nv1","")[:30]}')
    print()
    sync_to_db(students)

if __name__ == '__main__':
    main()
