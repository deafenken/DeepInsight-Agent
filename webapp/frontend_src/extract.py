"""One-time extractor: turn the Claude-design bundle into clean served static files.

Outputs:
  webapp/static/fonts/<uuid>.woff2     (114 font assets)
  webapp/static/dc-runtime.js          (DC/React runtime)
  webapp/frontend_src/template.html     (page shell, URLs rewritten, __COMPONENT__ placeholder)
  webapp/frontend_src/component.orig.js (original Component class, reference)

After this, edit frontend_src/component.js and run build.py to regenerate static/index.html.
"""
import re, json, base64, gzip, os, sys

SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/Downloads/DeepInsight.html')
HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.normpath(os.path.join(HERE, '..', 'static'))
FONTS = os.path.join(STATIC, 'fonts')
os.makedirs(FONTS, exist_ok=True)

html = open(SRC, 'r', encoding='utf-8').read()

def grab(tag):
    m = re.search(r'<script type="__bundler/%s">(.*?)</script>' % re.escape(tag), html, re.S)
    return m.group(1) if m else None

manifest = json.loads(grab('manifest'))
template = json.loads(grab('template'))

RUNTIME_UUID = None
font_uuids = []
for uuid, entry in manifest.items():
    data = base64.b64decode(entry['data'])
    if entry.get('compressed'):
        data = gzip.decompress(data)
    mime = entry.get('mime', '')
    if mime == 'font/woff2':
        open(os.path.join(FONTS, uuid + '.woff2'), 'wb').write(data)
        font_uuids.append(uuid)
    elif 'javascript' in mime or mime == 'text/babel':
        RUNTIME_UUID = uuid
        open(os.path.join(STATIC, 'dc-runtime.js'), 'wb').write(data)
    else:
        print('  ! unexpected asset mime', mime, uuid)

print(f'fonts: {len(font_uuids)}   runtime: {RUNTIME_UUID}')

# Rewrite the runtime <script src="UUID"> -> /static/dc-runtime.js
template = template.replace(f'src="{RUNTIME_UUID}"', 'src="/static/dc-runtime.js"')

# Rewrite every font uuid reference (CSS url("UUID")) -> /static/fonts/UUID.woff2
for u in font_uuids:
    template = template.replace(f'"{u}"', f'"/static/fonts/{u}.woff2"')

# Split out the component class so it lives in an editable file.
m = re.search(r'(<script type="text/x-dc"[^>]*>)(.*?)(</script>)', template, re.S)
open(os.path.join(HERE, 'component.orig.js'), 'w', encoding='utf-8').write(m.group(2))
template = template[:m.start()] + m.group(1) + '\n/*__COMPONENT__*/\n' + m.group(3) + template[m.end():]

open(os.path.join(HERE, 'template.html'), 'w', encoding='utf-8').write(template)
print('template.html + component.orig.js written; static assets populated.')
# sanity
assert '/*__COMPONENT__*/' in template
assert RUNTIME_UUID not in template, 'runtime uuid still present!'
remaining = [u for u in font_uuids if u in template]
print('font uuids still referenced raw (should be 0):', len(remaining))
