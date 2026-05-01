#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Restore TSDC modal - remove ONLY spinner, keep all functionality."""

# Read backup (full version with modal)
with open('templates/index.html.bak', encoding='utf-8', errors='replace') as f:
    c = f.read()

print(f"Backup: {len(c)} chars, modal={('tsdcOverlay' in c)}, trigger={('openTsdc()' in c)}")

# Fix 1: Remove spinner CSS
c = c.replace('.tsdc-spinner{width:48px;height:48px;border:5px solid #e3eaf5;border-top-color:#1565C0;border-radius:50%;animation:tspin .8s linear infinite;margin:0 auto 16px}', '')
c = c.replace('@keyframes tspin{to{transform:rotate(360deg)}}', '')

# Fix 2: Remove spinner <div> from loading section using simple string search
import re
# Replace the loading div content (has spinner div + p tag with 30-60s warning)
c = re.sub(
    r'<div class="tsdc-loading" id="tsdcLoading">[\s\S]{0,500}?</div>',
    lambda m: (
        '<div class="tsdc-loading" id="tsdcLoading">\n'
        '      <p id="tsdcLoadMsg" style="color:#666;font-size:.9rem;'
        'padding:32px 24px;text-align:center">'
        '\u0110ang t\u1ea3i d\u1eef li\u1ec7u TSDC...</p>\n    </div>'
        if 'tsdc-spinner' in m.group(0) or 'tsdcLoadMsg' in m.group(0)
        else m.group(0)
    ),
    c,
    count=1
)

# Fix 3: Remove "30-60 giay" text from JS _showLoading
c = re.sub(r"'\s*<br>\s*<small\s+style=[^']*>[^']*</small>'\s*;", "';", c)

# Verify
blocks = re.findall(r'\{%-?\s*block\s+(\w+)', c)
ends   = re.findall(r'\{%-?\s*endblock', c)
divs   = c.count('<div') - c.count('</div>')
print(f"Structure OK: blocks={blocks}, ends={len(ends)}, divs={divs}")
print(f"Has openTsdc: {'openTsdc' in c}")
print(f"Has modal overlay: {'tsdc-overlay' in c}")
print(f"Has fetch call: {'/api/tsdc-stats' in c}")
print(f"Spinner CSS gone: {'.tsdc-spinner' not in c}")

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(c)
print("SUCCESS!")
