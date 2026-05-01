"""
debug_pagination.py - Mo browser co UI, vao TSDC, tim kiem, in ra TAT CA element
lien quan den phan trang de biet selector chinh xac
"""
import asyncio

USERNAME = 'qni_thcs_chuvanan1'
PASSWORD = 'QuangNgai@06'

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        br   = await pw.chromium.launch(headless=False, slow_mo=200)
        page = await br.new_page(viewport={'width':1400,'height':900})

        print('[DBG] Login...')
        await page.goto('https://qlts.tsdc.edu.vn', wait_until='domcontentloaded')
        await asyncio.sleep(2)
        if await page.is_visible('input[type="password"]'):
            await page.fill('input[type="text"]', USERNAME)
            await page.fill('input[type="password"]', PASSWORD)
            await page.click('button[type="submit"]')
            await asyncio.sleep(5)

        print('[DBG] Navigate...')
        await page.goto('https://qlts.tsdc.edu.vn/quan-ly-ho-so', wait_until='networkidle')
        await asyncio.sleep(2)

        # Click menu Ho so du tuyen
        for item in await page.query_selector_all('li, a'):
            try:
                txt = await item.inner_text()
                if '\u1ef1 tuy\u1ec3n' in txt and len(txt) < 50:
                    await item.click(); await asyncio.sleep(2); break
            except: pass

        # Chon Cap 3
        all_s = await page.query_selector_all('.el-select')
        for sel in all_s:
            try:
                await sel.click(); await asyncio.sleep(0.8)
                opts = page.locator('.el-select-dropdown:not([style*="display: none"]) .el-select-dropdown__item')
                for j in range(await opts.count()):
                    txt = await opts.nth(j).inner_text()
                    if 'c\u1ea5p 3' in txt.lower():
                        await opts.nth(j).click(); break
                else:
                    await page.keyboard.press('Escape')
                    continue
                break
            except: await page.keyboard.press('Escape')
        await asyncio.sleep(0.5)
        await page.keyboard.press('Escape'); await asyncio.sleep(0.3)

        # Chon Dot THU
        all_s = await page.query_selector_all('.el-select')
        for sel in all_s:
            try:
                await sel.click(); await asyncio.sleep(0.8)
                opts = page.locator('.el-select-dropdown:not([style*="display: none"]) .el-select-dropdown__item')
                for j in range(await opts.count()):
                    txt = await opts.nth(j).inner_text()
                    if 'th\u1EED' in txt.lower():
                        await opts.nth(j).click(); break
                else:
                    await page.keyboard.press('Escape')
                    continue
                break
            except: await page.keyboard.press('Escape')
        await asyncio.sleep(0.5)
        await page.keyboard.press('Escape'); await asyncio.sleep(0.3)

        # Tim kiem
        btn = page.locator('button').filter(has_text='T\u00ecm ki\u1ebfm')
        if await btn.count() > 0:
            await btn.first.click()
            await asyncio.sleep(6)

        # Scroll xuong cuoi
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await asyncio.sleep(2)

        # ==================================================
        # INSPECT TAT CA element lien quan pagination
        # ==================================================
        print('\n' + '='*60)
        result = await page.evaluate("""
        () => {
            var info = {};
            // 1. Tim tat ca class co chu "pagination"
            info.pagination_classes = [...new Set(
                Array.from(document.querySelectorAll('[class*="pagination"]'))
                    .map(el => el.className)
            )];
            // 2. Tim tat ca class co chu "pager" hoac "size"  
            info.pager_classes = [...new Set(
                Array.from(document.querySelectorAll('[class*="pager"],[class*="size"],[class*="page-"]'))
                    .map(el => el.className.substring(0,80))
            )].slice(0,10);
            // 3. Tim div/span co text "Xem tren trang" hoac so ban ghi
            info.xem_element = '';
            Array.from(document.querySelectorAll('*')).forEach(el => {
                if (el.innerText && el.innerText.includes('Xem tr\u00ean trang') && el.children.length < 5) {
                    info.xem_element = el.outerHTML.substring(0,500);
                }
            });
            // 4. Tim select elements
            info.native_selects = Array.from(document.querySelectorAll('select')).map(s => ({
                id: s.id, name: s.name, class: s.className,
                options: Array.from(s.options).map(o => o.value + ':' + o.text)
            }));
            // 5. Dem tbody rows
            info.tbody_rows = document.querySelectorAll('tbody tr').length;
            // 6. Tim "Tong" text
            info.tong = Array.from(document.querySelectorAll('*'))
                .filter(el => el.innerText && /T\u1ed5ng/.test(el.innerText) && el.children.length < 3)
                .map(el => el.innerText.trim()).join(' | ');
            return info;
        }
        """)

        print('PAGINATION CLASSES:')
        for c in result.get('pagination_classes', []):
            print(' ', c)

        print('\\nPAGER/SIZE CLASSES:')
        for c in result.get('pager_classes', []):
            print(' ', c)

        print('\\nXEM TREN TRANG ELEMENT:')
        print(result.get('xem_element', 'NOT FOUND'))

        print('\\nNATIVE SELECT ELEMENTS:')
        for s in result.get('native_selects', []):
            print(f'  id={s["id"]} name={s["name"]} class={s["class"]}')
            for o in s.get('options', []):
                print(f'    option: {o}')

        print(f'\\nTBODY ROWS: {result.get("tbody_rows")}')
        print(f'TONG: {result.get("tong")}')

        print('\n[DBG] Giu nguyen browser 10 giay de ban kiem tra...')
        await asyncio.sleep(10)
        await br.close()

asyncio.run(main())
