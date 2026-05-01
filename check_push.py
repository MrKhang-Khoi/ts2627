import ast
with open('tsdc_push.py', encoding='utf-8') as f:
    src = f.read()
ast.parse(src)
print('Syntax OK')
print('Has select_option:', 'select_option' in src)
print('Has _JS_EXTRACT:', '_JS_EXTRACT' in src)
print('isMaHS excludes HSO:', "!t.startsWith('HSO')" in src)
print('Has wait_for_selector:', 'wait_for_selector' in src)
print('Has scrollTo:', 'scrollTo' in src)
print('Has 500 option:', "has_text='500'" in src)
print('Lines:', src.count(chr(10)))
