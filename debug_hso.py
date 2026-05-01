"""
debug_hso.py - Tim chinh xac HSO code trong DOM TSDC
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
                    await page.keyboard.press('Escape'); continue
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
                    await page.keyboard.press('Escape'); continue
                break
            except: await page.keyboard.press('Escape')
        await asyncio.sleep(0.5); await page.keyboard.press('Escape')

        btn = page.locator('button').filter(has_text='T\u00ecm ki\u1ebfm')
        if await btn.count() > 0:
            await btn.first.click(); await asyncio.sleep(6)

        result = await page.evaluate("""
        () => {
            // 1. Bao nhieu tbody tren trang?
            var tbodies = document.querySelectorAll('tbody');
            
            // 2. Lay tat ca rows tu moi tbody rieng le
            var tbodyInfo = [];
            for (var tb = 0; tb < tbodies.length; tb++) {
                var rows = tbodies[tb].querySelectorAll('tr');
                var sample = [];
                for (var r = 0; r < Math.min(rows.length, 5); r++) {
                    var cells = Array.from(rows[r].querySelectorAll('td')).map(function(c){ return c.innerText.trim().substring(0, 50); });
                    sample.push(cells.filter(function(c){ return c.length > 0; }));
                }
                tbodyInfo.push({
                    index: tb,
                    rowCount: rows.length,
                    sample: sample
                });
            }
            
            // 3. Tim tat ca HSO codes
            var allRows = Array.from(document.querySelectorAll('tbody tr'));
            var hsoRows = [];
            for (var i = 0; i < allRows.length; i++) {
                var cells = Array.from(allRows[i].querySelectorAll('td')).map(function(c){ return c.innerText.trim(); });
                var hso = cells.find(function(c){ return c.startsWith('HSO') && c.length > 8; });
                if (hso) {
                    // Xem row truoc no la gi
                    var prevCells = i > 0 ? Array.from(allRows[i-1].querySelectorAll('td')).map(function(c){ return c.innerText.trim().substring(0,30); }).filter(Boolean) : [];
                    var prevPrevCells = i > 1 ? Array.from(allRows[i-2].querySelectorAll('td')).map(function(c){ return c.innerText.trim().substring(0,30); }).filter(Boolean) : [];
                    hsoRows.push({
                        rowIndex: i,
                        hso: hso,
                        prevRow: prevCells.slice(0, 4),
                        prevPrevRow: prevPrevCells.slice(0, 4)
                    });
                    if (hsoRows.length >= 5) break; // Chi lay 5 cai dau
                }
            }
            
            // 4. Tim row dau tien co HS code va xem 5 row tiep theo
            var firstHSRow = -1;
            var around = [];
            for (var i = 0; i < allRows.length; i++) {
                var cells = Array.from(allRows[i].querySelectorAll('td')).map(function(c){ return c.innerText.trim(); });
                var hasHS = cells.some(function(t){ return t.startsWith('HS') && !t.startsWith('HSO') && t.length > 5; });
                if (hasHS) { firstHSRow = i; break; }
            }
            if (firstHSRow >= 0) {
                for (var i = firstHSRow; i < Math.min(firstHSRow+10, allRows.length); i++) {
                    var cells = Array.from(allRows[i].querySelectorAll('td')).map(function(c){ return c.innerText.trim().substring(0,40); }).filter(Boolean);
                    around.push({ idx: i, cells: cells.slice(0,6) });
                }
            }
            
            return {
                totalTbodies: tbodies.length,
                tbodyInfo: tbodyInfo,
                hsoRows: hsoRows,
                firstHSRow: firstHSRow,
                aroundFirstHS: around,
                totalRows: allRows.length
            };
        }
        """)

        print(f"\n=== SO LUONG TBODY: {result['totalTbodies']} ===")
        print(f"=== TONG ROWS (tbody tr): {result['totalRows']} ===\n")

        print("=== THONG TIN TUNG TBODY ===")
        for tb in result['tbodyInfo']:
            print(f"\n--- tbody #{tb['index']}: {tb['rowCount']} rows ---")
            for i, s in enumerate(tb['sample']):
                print(f"  Row {i}: {s[:4]}")

        print("\n=== 5 ROWS DAU TIEN CO HSO CODE ===")
        for h in result['hsoRows']:
            print(f"\nRow #{h['rowIndex']}: HSO={h['hso']}")
            print(f"  Row truoc (#{h['rowIndex']-1}): {h['prevRow']}")
            print(f"  Row truoc nua (#{h['rowIndex']-2}): {h['prevPrevRow']}")

        print(f"\n=== 10 ROWS XUNG QUANH ROW HS DAU TIEN (row {result['firstHSRow']}) ===")
        for r in result['aroundFirstHS']:
            print(f"  Row #{r['idx']}: {r['cells']}")

        print('\n[DBG] Giu 30 giay...')
        await asyncio.sleep(30)
        await br.close()

asyncio.run(main())
