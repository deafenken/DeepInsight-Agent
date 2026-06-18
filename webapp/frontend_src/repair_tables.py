"""Repair tables whose sc-for/sc-if loops were foster-parented out of <table> during bundling."""
import re
src = open('template.html', encoding='utf-8').read()
orig = src

# Pattern A: cells-based tables (chat / whitebox / database): cols + rows + cells loops
patA = re.compile(
    r'<sc-for list="\{\{ (?P<cols>[^}]+?) \}\}" as="(?P<cv>\w+)">\s*</sc-for>\s*'
    r'<sc-for list="\{\{ (?P<rows>[^}]+?) \}\}" as="r">\s*</sc-for>\s*'
    r'<sc-for list="\{\{ r\.cells \}\}" as="cell">\s*</sc-for>\s*'
    r'(?P<tbl><table[^>]*>)\s*'
    r'<thead>\s*<tr>\s*(?P<th><th[^>]*>)\{\{ (?P=cv) \}\}</th>\s*</tr>\s*</thead>\s*'
    r'<tbody>\s*<tr>\s*(?P<td><td[^>]*>)\{\{ cell \}\}</td>\s*</tr>\s*</tbody>\s*</table>',
    re.S)
def repA(m):
    return (m['tbl']
        + '<thead><tr><sc-for list="{{ ' + m['cols'] + ' }}" as="' + m['cv'] + '">'
        + m['th'] + '{{ ' + m['cv'] + ' }}</th></sc-for></tr></thead>'
        + '<tbody><sc-for list="{{ ' + m['rows'] + ' }}" as="r"><tr>'
        + '<sc-for list="{{ r.cells }}" as="cell">' + m['td'] + '{{ cell }}</td></sc-for>'
        + '</tr></sc-for></tbody></table>')
src, nA = patA.subn(repA, src)

# Pattern B: cmp_rows table (single loop, fixed columns)
patB = re.compile(
    r'<sc-for list="\{\{ cmp_rows \}\}" as="r" hint-placeholder-count="6">\s*</sc-for>\s*'
    r'(?P<tbl><table[^>]*>)\s*'
    r'(?P<thead><thead>.*?</thead>)\s*'
    r'<tbody>\s*(?P<tr><tr>.*?</tr>)\s*</tbody>\s*</table>',
    re.S)
def repB(m):
    return (m['tbl'] + m['thead']
        + '<tbody><sc-for list="{{ cmp_rows }}" as="r" hint-placeholder-count="6">'
        + m['tr'] + '</sc-for></tbody></table>')
src, nB = patB.subn(repB, src)

print(f'Pattern A (cells tables) repaired: {nA}')
print(f'Pattern B (cmp_rows) repaired:    {nB}')
leftover = len(re.findall(r'<sc-(for|if)\b[^>]*>\s*</sc-\1>', src))
print(f'remaining empty sc-for/sc-if:     {leftover}')
assert nA == 3 and nB == 1, f'expected 3+1 repairs, got {nA}+{nB}'
assert leftover == 0, f'still {leftover} empty directives'
open('template.html','w',encoding='utf-8').write(src)
print('template.html repaired.')
