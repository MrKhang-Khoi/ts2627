"""
debug_pagination2.py - In HTML chinh xac cua pagination area
"""
import asyncio

USERNAME = 'qni_thcs_chuvanan1'
PASSWORD = 'QuangNgai@06'

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        br   = await pw.chromium.launch(headless=False, slow_mo=300)
        page = await br.new_page(viewport={'width':1400,'height':900})

        print('[DBG] Login...')
        await page.goto('https://qlts.tsdc.edu.vn', wait_until='domcontentloaded')
        await asyncio.sleep(2)
        if await page.is_visible('input[type="password"]'):
            await page.fill('input[type="text"]', USERNAME)
            await page.fill('input[type="password"]', PASSWORD)
            await page.click('button[type="submit"]')
            await asyncio.sleep(5)

        await page.goto('https://qlts.tsdc.edu.vn/quan-ly-ho-so', wait_until='networkidle')
        await asyncio.sleep(2)

        for item in await page.query_selector_all('li, a'):
            try:
                txt = await item.inner_text()
                if '\u1ef1 tuy\u1ec3n' in txt and len(txt) < 50:
                    await item.click(); await asyncio.sleep(2); break
            except: pass

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
        await asyncio.sleep(0.5); await page.keyboard.press('Escape')

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
        await asyncio.sleep(0.5); await page.keyboard.press('Escape')

        btn = page.locator('button').filter(has_text='T\u00ecm ki\u1ebfm')
        if await btn.count() > 0:
            await btn.first.click()
            await asyncio.sleep(6)

        # Scroll xuong cuoi
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await asyncio.sleep(2)

        result = await page.evaluate("""
        () => {
            var info = {};

            // 1. Tim phan tu "Xem tren trang" va lay outerHTML cua parent
            var all = Array.from(document.querySelectorAll('*'));
            for (var el of all) {
                if (el.innerText && el.innerText.trim() === 'Xem tr\u00ean trang:') {
                    var p = el.parentElement;
                    info.xem_parent = p ? p.outerHTML.substring(0, 800) : 'no parent';
                    break;
                }
            }

            // 2. Tim tat ca element co text "Sau" (chi chinh xac)
            info.sau_elements = [];
            for (var el of all) {
                var txt = (el.innerText || '').trim();
                if (txt === 'Sau') {
                    info.sau_elements.push({
                        tag: el.tagName,
                        class: el.className,
                        parent_class: el.parentElement ? el.parentElement.className : '',
                        grandparent_class: el.parentElement && el.parentElement.parentElement ? el.parentElement.parentElement.className : '',
                        is_visible: el.offsetParent !== null,
                        outer: el.outerHTML.substring(0, 200)
                    });
                }
            }

            // 3. Tim tat ca element co text "Truoc" 
            info.truoc_elements = [];
            for (var el of all) {
                var txt = (el.innerText || '').trim();
                if (txt === 'Tr\u01b0\u1edbc') {
                    info.truoc_elements.push({
                        tag: el.tagName,
                        class: el.className,
                        is_visible: el.offsetParent !== null,
                        outer: el.outerHTML.substring(0, 200)
                    });
                }
            }

            // 4. Dem rows hien tai
            info.rows = document.querySelectorAll('tbody tr').length;

            // 5. Tim tong ban ghi text
            info.tong = '';
            for (var el of all) {
                if (el.children.length < 3 && el.innerText && el.innerText.includes('T\u1ed5ng:')) {
                    info.tong += el.innerText.trim() + ' | ';
                }
            }

            return info;
        }
        """)

        print('\n=== XEM TREN TRANG PARENT ===')
        print(result.get('xem_parent', 'NOT FOUND'))

        print('\n=== SAU ELEMENTS ===')
        for e in result.get('sau_elements', []):
            print(f"  tag={e['tag']} class={e['class'][:60]} visible={e['is_visible']}")
            print(f"  parent={e['parent_class'][:60]}")
            print(f"  grandparent={e['grandparent_class'][:60]}")
            print(f"  html={e['outer'][:100]}")
            print()

        print('\n=== TRUOC ELEMENTS ===')
        for e in result.get('truoc_elements', []):
            print(f"  tag={e['tag']} class={e['class'][:60]} visible={e['is_visible']}")

        print(f"\n=== ROWS: {result.get('rows')} ===")
        print(f"=== TONG: {result.get('tong')} ===")

        print('\n[DBG] Giu browser 30 giay...')
        await asyncio.sleep(30)
        await br.close()

asyncio.run(main())
