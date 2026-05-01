import re
with open('templates/index.html', encoding='utf-8') as f:
    c = f.read()

checks = {
    'UTF-8 Tieng Viet OK': 'khai sinh' in c,
    'Spinner CSS da xoa': '.tsdc-spinner' not in c,
    'Spinner HTML da xoa': 'class="tsdc-spinner"' not in c,
    'Trigger button con': 'openTsdc()' in c,
    'Modal overlay con': 'tsdc-overlay' in c,
    'Fetch API con': '/api/tsdc-stats' in c,
    'renderTsdc con': 'renderTsdc' in c,
    'switchNv con': 'switchNv' in c,
    'Blocks OK': len(re.findall(r'\{%-?\s*block\s+\w+', c)) == len(re.findall(r'\{%-?\s*endblock', c)),
    'Div balanced': c.count('<div') == c.count('</div>'),
}
for k, v in checks.items():
    print(f'  {"OK" if v else "FAIL"}: {k}')

all_ok = all(checks.values())
print()
print('ALL PASS!' if all_ok else 'SOME FAILED!')
