#!/usr/bin/env python3
"""inject.py SITE_DIR: add the beacon to every page and the public stats strip to index.html. Idempotent."""
import sys, os, re
root = sys.argv[1]
STRIP = '''<section id="poc-stats" style="max-width:1100px;margin:36px auto 48px;padding:0 16px;font:14px/1.5 Inter,system-ui,sans-serif;color:#b9b2a3" hidden>
<div style="display:flex;flex-wrap:wrap;gap:22px;justify-content:center;border-top:1px solid #3a352a;padding-top:18px">
<span><b id="ps-now" style="color:#d9b45a;font-size:22px">0</b><br>viewing now</span>
<span><b id="ps-24" style="color:#d9b45a;font-size:22px">0</b><br>visitors, 24 h</span>
<span><b id="ps-7" style="color:#d9b45a;font-size:22px">0</b><br>visitors, 7 days</span>
<span><b id="ps-loads" style="color:#d9b45a;font-size:22px">0</b><br>demo loads today</span></div>
<p style="text-align:center;margin:10px 0 0;font-size:12px;color:#8d8678">Live from this site's own request log. No cookies. Addresses are stored only as a daily salted hash. <span id="ps-asof"></span></p></section>
<script>(function(){function g(i){return document.getElementById(i)}function t(){fetch('/stats.json').then(function(r){return r.json()}).then(function(s){g('poc-stats').hidden=false;g('ps-now').textContent=s.now_viewing||0;g('ps-24').textContent=s.visitors_24h||0;g('ps-7').textContent=s.visitors_7d||0;g('ps-loads').textContent=s.loads_today||0;g('ps-asof').textContent='Updated '+new Date(s.as_of).toLocaleTimeString()}).catch(function(){})}t();setInterval(t,15000)})();</script>
'''
LINKS = '<section style="max-width:1100px;margin:30px auto 0;padding:0 16px;font:15px/1.6 Inter,system-ui,sans-serif;color:#d8d1c0"><h2 style="font:500 26px Cormorant Garamond,serif;color:#d9b45a;margin:0 0 8px">More exhibits</h2><p style="margin:0"><a style="color:#d9b45a" href="doha/">Library of PolyXandria</a> · <a style="color:#d9b45a" href="canopy/">The Accountable Canopy</a> · <a style="color:#d9b45a" href="heritage/">Sovereign Heritage Twin</a></p></section>\n'
n = 0
for d, _, fs in os.walk(root):
    if os.sep + 'vendor' in d + os.sep: continue
    for f in fs:
        if not f.endswith('.html'): continue
        p = os.path.join(d, f); s = open(p, encoding='utf-8').read()
        if '/_b.js' in s: continue
        add = '<script src="/_b.js" defer></script>\n' + ((LINKS if os.path.isdir(os.path.join(root,'doha')) else '') + STRIP if f == 'index.html' and d == root else '')
        s = s.replace('</body>', add + '</body>', 1) if '</body>' in s else s + add
        open(p, 'w', encoding='utf-8').write(s); n += 1
print('injected', n, 'pages')
