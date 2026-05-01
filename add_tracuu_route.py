content = open('app.py', 'rb').read().decode('utf-8', errors='replace')
insert = '''
@app.route('/tracuu')
def tracuu():
    return render_template('tracuu.html')

'''
target = "@app.route('/huong-dan')"
if '/tracuu' not in content:
    content = content.replace(target, insert + target, 1)
    open('app.py', 'w', encoding='utf-8').write(content)
    print('OK: route /tracuu added')
else:
    print('SKIP: already exists')
