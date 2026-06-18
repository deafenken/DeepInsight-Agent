"""Inject component.js into template.html -> webapp/static/index.html."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.normpath(os.path.join(HERE, '..', 'static'))
template = open(os.path.join(HERE, 'template.html'), encoding='utf-8').read()
component = open(os.path.join(HERE, 'component.js'), encoding='utf-8').read()
assert '/*__COMPONENT__*/' in template, 'placeholder missing'
out = template.replace('/*__COMPONENT__*/', component)
open(os.path.join(STATIC, 'index.html'), 'w', encoding='utf-8').write(out)
print('static/index.html written:', len(out), 'bytes')
