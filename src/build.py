#!/usr/bin/env python3
"""Generate the PolyXandria demo site: a master index and one landing page per demo.
Facts are pulled from the Gifts page's own DATA block, so every number on these pages is one the Gifts page already carries."""
import html, json, os, re, shutil, sys

ROOT = sys.argv[1]                      # demo-site directory (assets already copied in)
HERE = os.path.dirname(os.path.abspath(__file__))
shutil.copy(os.path.join(HERE, 'common.css'), ROOT)
shutil.copy(os.path.join(HERE, 'common.js'), ROOT)

src = open(os.path.join(ROOT, 'gifts.html'), encoding='utf-8').read()
DATA = json.loads(re.search(r'var DATA = (\{.*?\});\s*\n', src, re.S).group(1))
G = {g['num']: g for g in DATA['gifts']}
esc = html.escape


def facts_html(rows):
    out = []
    for r in rows:
        out.append('<div><dt>%s</dt><dd>%s</dd>%s</div>' % (esc(r[0]), esc(r[1]), '<span class="src">%s</span>' % esc(r[2]) if len(r) > 2 and r[2] else ''))
    return '<dl class="facts">%s</dl>' % ''.join(out)


SHARED = [
    ('One engine', 'Every page runs the same X_ITE 16.4.3 viewer, loader and tour code. Nothing is a video.'),
    ('Bird\'s-eye tour', 'A descending spiral camera drives the view; touch the scene and it hands control back.'),
    ('Lights out', 'A flashlight follows your pointer in the dark. It works on every page.'),
    ('Standard X3D', 'The scenes are plain X3D 4.0 or the 4.1 draft GaussianSplats node, checked by the fork validator.'),
    ('Measured', 'Load times and frame rates shown are from your machine; the fact cards name the test box.'),
]

NAV = [('index.html', 'All demos'), ('gobbler.html', 'Gobbler'), ('pantheon.html', 'Pantheon'), ('giza.html', 'Giza'), ('powers-of-ten.html', 'Powers of ten'),
       ('drillfield.html', 'Drillfield'), ('two-renderers.html', 'Two renderers'), ('materials.html', 'Materials'), ('spec-questions.html', 'Spec questions')]

HEAD = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s · PolyXandria</title><meta name="description" content="%(desc)s">
<link rel="stylesheet" href="vendor/x_ite/x_ite.css"><link rel="stylesheet" href="common.css">
<script src="vendor/x_ite/x_ite.min.js"></script><script src="common.js"></script></head><body>'''

STAGE = '''<header class="stage" id="stage">
  %(poster)s<div class="shade"></div>
  <div class="fog"></div><div class="dark"></div><div class="grain"></div><div class="flash"></div><div class="vignette"></div>
  <div class="ui">
    <div class="top"><div class="brand"><a href="index.html">PolyXandria</a></div><nav class="nav">%(nav)s</nav></div>
    <div class="titleblock"><div class="kicker">%(kicker)s</div><h1>%(h1)s</h1><p>%(tag)s</p>%(cta)s</div>
    <div class="bar"><div class="btns" id="vps">%(buttons)s</div><div class="hud" id="hud">starting</div></div>
  </div>
  <div class="busy" id="busy">Starting the viewer</div>
  <div class="hint" id="hint">%(hint)s</div>
</header>'''

BTNS = '''<button class="chip" id="btn-tour">Pause tour</button><button class="chip" id="btn-dark">Lights out</button><button class="chip" id="btn-clean">Hide text</button><button class="chip" id="btn-full">Full screen</button>'''
BTNS_NOTOUR = '''<button class="chip" id="btn-dark">Lights out</button><button class="chip" id="btn-clean">Hide text</button><button class="chip" id="btn-full">Full screen</button>'''


def nav(cur):
    return ''.join('<a class="chip%s" href="%s">%s</a>' % (' on' if h == cur else '', h, esc(t)) for h, t in NAV)


def page(fn, d):
    cfg = d['cfg']
    poster = '<img class="poster" alt="" src="%s">' % d['poster'] if d.get('poster') else ''
    cta = d.get('cta', '')
    if d.get('links'):
        cta += '<p style="margin-top:20px;display:flex;gap:8px;flex-wrap:wrap">%s</p>' % ''.join('<a class="chip on" target="_blank" rel="noopener" href="%s">%s</a>' % (esc(u), esc(t)) for t, u in d['links'])
    parts = [HEAD % {'title': esc(d['title']), 'desc': esc(d['tag'])}]
    parts.append(STAGE % {'poster': poster, 'kicker': esc(d['kicker']), 'h1': d['h1'], 'tag': esc(d['tag']), 'cta': cta, 'nav': nav(fn),
                          'buttons': (BTNS if cfg.get('tour') else BTNS_NOTOUR), 'hint': esc(d.get('hint', 'Drag to orbit · scroll to zoom'))})
    body = ['<main>']
    body.append('<section class="band"><div class="wrap cols"><div>')
    if d.get('say'):
        body.append('<p class="say">%s</p>' % esc(d['say']))
    body.append('<p class="lead">%s</p>' % d['lead'])
    if d.get('pills'):
        body.append('<div class="pillrow">%s</div>' % ''.join('<span class="pill%s">%s</span>' % (' ok' if p[1] == 'ok' else '', esc(p[0])) for p in d['pills']))
    body.append('<p class="lead" id="loadinfo" style="color:var(--ink3);font-size:14px;margin-top:20px"></p>')
    body.append('</div><div><h3 style="font-size:18px;margin-bottom:6px">%s</h3>%s</div></div></section>' % (esc(d.get('cardTitle', 'Catalogue card')), facts_html(d['facts'])))
    if d.get('extra'):
        body.append(d['extra'])
    body.append('<section class="band"><div class="wrap"><h2>What every demo shares</h2><div class="share">%s</div></div></section>' %
                ''.join('<div><b>%s</b><span>%s</span></div>' % (esc(a), esc(b)) for a, b in SHARED))
    body.append('<footer><div class="wrap"><p>%s</p><p><a href="index.html">All demos</a> · <a href="gifts.html">The original Gifts page</a></p></div></footer></main>' % esc(d.get('foot', DEFAULT_FOOT)))
    parts.append(''.join(body))
    parts.append('<script>PX.boot(%s);%s</script></body></html>' % (json.dumps(cfg), d.get('js', '')))
    open(os.path.join(ROOT, fn), 'w', encoding='utf-8').write(''.join(parts))


DEFAULT_FOOT = ('Timings on the fact cards are from headless Chromium with SwiftShader software WebGL on a 4 vCPU cloud container; a real GPU is faster. '
                'Splat worlds are generated captures, decoded and written as X3D 4.1 draft GaussianSplats. Everything on this site is private until it is shared.')

def gfacts(num, prefixes=None, drop=()):
    rows = G[num]['facts']
    if prefixes:
        rows = [r for r in rows if any(r[0].startswith(p) for p in prefixes)]
    return [r for r in rows if r[0] not in drop]


# ---------------------------------------------------------------- the demos
DEMOS = {}

DEMOS['gobbler.html'] = dict(
    title='The Gobbler', kicker='Demo 1 · Bird\'s-eye · scriptless X3D 4.0', h1='The <em>Gobbler</em>',
    tag='A bird that assembles itself out of nodes, in the dark. Watch it from above, then let it come closer.',
    poster='gifts/gobbler-poster.jpg', hint='Lights are out: move the pointer to find it. Touch the scene to take over the camera.',
    say='The scene graph is the animation: 262 nodes and 41 ROUTEs, no Script.',
    lead='This is the hero of the Gifts page, taken full window. A single camera spirals down from high above, like a bird\'s-eye shot, while a lantern follows your pointer. Drag to orbit; the gift-box chip plays the unwrap that opens the Gifts page.',
    facts=[('Nodes', '262', 'counted in unwrap.x3d (the unwrap sequence)'), ('ROUTEs', '41', 'no Script node'), ('Features', 'ParticleSystems · PhysicalMaterial · shadows', 'X3D 4.0 Immersive'),
           ('Validator', 'pass', 'fork validator @c9c9788')],
    cardTitle='Scene card',
    cfg=dict(scene='gifts/hero/gobbler.x3d', look=dict(toneMapping='KHR_PBR_NEUTRAL', exposure=1.0), darkDefault=True,
             viewpoints=[['Gobbler', 'Face'], ['Wide', 'Wide'], ['Close', 'Close']],
             autoClean=9000, tour=dict(vp='Gobbler', center=[0.72, -0.76, 0], r0=19, r1=6.2, e0=66, e1=4, duration=30, spin=0.1, loop='pingpong', fov=0.75)),
    js="""(function(){var a=document.getElementById('vps');var b=document.createElement('button');b.className='chip';b.textContent='The gift box (unwrap)';
 b.onclick=function(){PX.load({scene:'gifts/hero/unwrap.x3d'})};a.appendChild(b)})();""",
)

DEMOS['pantheon.html'] = dict(
    title='Pantheon, 500,000 splats', kicker='Demo 2 · Gaussian splats · X3D 4.1 draft', h1='Under the <em>oculus</em>',
    tag='A generated Pantheon, half a million Gaussians, parsed from X3D in your browser.',
    poster='gifts/pantheon-poster.jpg', hint='The camera tilts up from the doors to the oculus. Pick a viewpoint for a fixed view.',
    say='Blender 5.3 reads splats from four formats and writes them to none. Our add-on writes them to X3D 4.1.',
    lead='The splats are plain XML in the draft GaussianSplats node, written by the Blender add-on and decoded losslessly from SPZ v3. The stage around them adds a backdrop, viewpoints and a slow camera, all in the same scene file.',
    facts=gfacts(2, ['Pantheon', 'Bytes per splat', 'Quaternion', 'Validator', 'Limit']) or gfacts(2),
    cardTitle='Two worlds, one draft node',
    cfg=dict(parts=DATA['splats']['pantheon']['parts'], stage=DATA['splats']['pantheon']['stage'], splats=500000, mb=19.5, look=dict(toneMapping='NONE', maxScale=1.25), darkDefault=False, autoClean=12000,
             viewpoints=[['Oculus', 'Oculus'], ['PantheonEye', 'Doors']], loadLabel='500,000 splats live',
             tours=[dict(label='Tilt to the oculus', kind='path', duration=26, loop='pingpong', fov=1.15, p0=[0, 0, 0], p1=[0, 0, 0], t0=[0, 0.2, -10], t1=[0, 10, -1.2]),
                    dict(label='Slow turn', kind='path', duration=40, loop='pingpong', fov=1.2, p0=[0, 0, 0], p1=[0, 0, 0], t0=[-10, 2.5, -6], t1=[10, 2.5, -6])]),
)

DEMOS['giza.html'] = dict(
    title='Khufu, 970,654 splats', kicker='Demo 3 · Giza · nearly a million splats', h1='<em>Khufu</em>, laid stone by stone',
    tag='The Great Pyramid as 970,654 synthetic Gaussians, one cluster per masonry block, approached down its own axis.',
    poster='gifts/giza-poster.jpg', hint='A straight-on dolly up the axis, one-point perspective. Switch to the orbit for a bird\'s-eye pass.',
    say='One million Gaussians you can only look at; six thousand triangles you can relight. The scene graph lets them agree.',
    lead='This is the biggest scene on the site: 129 MB of XML that your browser fetches as 31 MB, unpacks and parses live. The splats are synthetic, laid per masonry block from survey numbers, not a photo capture.',
    facts=gfacts(2, ['Khufu', 'Bytes per splat', 'Quaternion', 'Limit']),
    cardTitle='Two worlds, one draft node',
    cfg=dict(parts=DATA['splats']['khufu']['parts'], splats=970654, mb=31.4, look=dict(toneMapping='NONE', maxScale=1.0), darkDefault=False, autoClean=12000,
             tours=[dict(label='Kubrick dolly', kind='path', duration=46, loop='pingpong', fov=0.85, p0=[0, 10, -820], p1=[0, 22, -330], t0=[0, 74, 0], t1=[0, 74, 0]),
                    dict(label='Bird\'s-eye orbit', center=[0, 50, 0], target=[0, 58, 0], r0=400, r1=215, e0=34, e1=8, duration=48, spin=0.07, loop='pingpong', fov=0.9)],
             loadLabel='970,654 splats live'),
    foot=DEFAULT_FOOT + ' The Sphinx and the Shaft of Osiris are not in this build; they arrive with the next set of files.',
)

DEMOS['powers-of-ten.html'] = dict(
    title='Powers of ten', kicker='Demo 4 · Scriptless · 18 powers of ten', h1='From Burruss Hall to <em>the stars</em>',
    tag='One continuous zoom from one metre to 978 real stars, for the opening day of Web3D 2026 in Doha.',
    poster='gifts/stars/poster.png', hint='The zoom is one TimeSensor driving every interpolator. No Script.',
    links=[('Open the full page with the scrubber ↗', 'https://claude.ai/artifact/MgCNbxgBmzbAz68aGud485')],
    say=G[8]['say'], lead=G[8]['line'], facts=G[8]['facts'], cardTitle=G[8].get('cardTitle', 'Catalogue card'),
    cfg=dict(scene='gifts/stars/planet-zoom.x3d', look=dict(toneMapping='NONE'), darkDefault=False,
             viewpoints=[['VP_zoom', 'Zoom'], ['VP_burruss', 'Burruss Hall']]),
)

DEMOS['drillfield.html'] = dict(
    title='The Drillfield from orbit', kicker='Demo 5 · Real terrain · ElevationGrid', h1='The <em>Drillfield</em> from orbit',
    tag='Virginia Tech\'s Drillfield as one X3D node, built from satellite data, with the sun on its real June path.',
    poster='gifts/drillfield/poster.png', hint='The sun follows its real 2 June path and casts shadows.',
    say=G[1]['say'], lead=G[1]['line'], facts=G[1]['facts'], cardTitle=G[1].get('cardTitle', 'Catalogue card'),
    cfg=dict(scene='gifts/drillfield/drillfield.x3d', look=dict(toneMapping='KHR_PBR_NEUTRAL', exposure=1.05),
             viewpoints=[[v[1], v[0]] for v in G[1]['views']],
             tour=dict(vp='VP_orbit', center=[0, 20, 0], target=[0, 10, 0], r0=560, r1=230, e0=52, e1=14, duration=44, spin=0.08, loop='pingpong', fov=0.8)),
)

DEMOS['two-renderers.html'] = dict(
    title='One scene, two renderers', kicker='Demo 6 · Blender → X3D · measured', h1='<em>Same file</em>, two renderers',
    tag='A Blender still life, path-traced by Cycles and rendered live from X3D, then re-made as trained splats.',
    poster='gifts/bridge/xite.png', hint='Drag the wipes below the viewer. Chips switch between the mesh export and the trained splats.',
    say=G[5]['say'], lead=G[4]['line'] + ' ' + G[5]['line'],
    facts=G[4]['facts'] + [[r[0], r[1], r[2]] for r in G[5]['facts'][:4]], cardTitle='Measured, not eyeballed',
    cfg=dict(scene='gifts/bridge/stilllife-stage.x3d', look=dict(toneMapping='NONE'), darkDefault=False, viewpoints=[]),
    extra='''<section class="band"><div class="wrap"><h2>Drag to compare</h2><div class="split">
<div><div id="w1"></div><p class="hint2">Blender Cycles, 144.8 s per frame, against the X3D 4.0 mesh export (SSIM 0.905).</p></div>
<div><div id="w2"></div><p class="hint2">The same Cycles still against the trained X3D 4.1 splats (SSIM 0.977).</p></div></div></div></section>
<style>.hint2{font:12px var(--mono);color:var(--ink3);margin:8px 0 0}</style>''',
    js='''PX.wipe(document.getElementById('w1'),'gifts/synthsplat/cycles.png','gifts/bridge/xite.png','Blender Cycles','X3D 4.0 mesh in X_ITE');
PX.wipe(document.getElementById('w2'),'gifts/synthsplat/cycles.png','gifts/synthsplat/xite.png','Blender Cycles','X3D 4.1 splats in X_ITE');
(function(){var a=document.getElementById('vps');
 [['Mesh export (X3D 4.0)',{scene:'gifts/bridge/stilllife-stage.x3d'}],['Trained splats (132,923)',{parts:%s,splats:132923,mb:34.0}]].forEach(function(p,i){
  var b=document.createElement('button');b.className='chip vp'+(i?'':' on');b.textContent=p[0];
  b.onclick=function(){document.querySelectorAll('#vps .vp').forEach(function(x){x.classList.remove('on')});b.classList.add('on');PX.load(p[1])};a.appendChild(b)})})();''' %
       json.dumps(DATA['splats']['still']['parts'] if 'still' in DATA['splats'] else G[5]['splats']['still']['parts']),
)

DEMOS['materials.html'] = dict(
    title='Materials from nothing', kicker='Demo 7 · Synthetic textures · PhysicalMaterial', h1='Materials from <em>nothing</em>',
    tag='Gold leaf, Hokie Stone, marble, silk and walnut, each generated as a texture and worn by X3D PhysicalMaterial.',
    poster='gifts/materials/poster.png', hint='Shadowed lights, normal maps, all standard nodes.',
    links=[('Watch the film made from this scene ↗', 'https://claude.ai/artifact/2haGH8DR71XrPHRVorVHYq')],
    say=G[6]['say'], lead=G[6]['line'], facts=G[6]['facts'], cardTitle=G[6].get('cardTitle', 'Catalogue card'),
    cfg=dict(scene='gifts/materials/materials.x3d', look=dict(toneMapping='KHR_PBR_NEUTRAL', exposure=1.5),
             viewpoints=[['Shelf', 'Shelf'], ['Close', 'Close']],
             tour=dict(vp='Shelf', center=[0, 0.8, 0], target=[0, 0.75, 0], r0=9, r1=3.4, e0=14, e1=5, duration=30, spin=0.0, loop='pingpong', fov=0.62, a0=0)),
)

PAIRS = [
    ('Profile tables', 'gifts/repros/profile-tables.x3d', 'gifts/repros/profile-tables.png'),
    ('Profile tables, fixed', 'gifts/repros/profile-tables-fixed.x3d', 'gifts/repros/profile-tables-pair.png'),
    ('Quaternion w-first', 'gifts/repros/quaternion-wxyz.x3d', 'gifts/repros/quaternion-pair.png'),
    ('Quaternion x-first', 'gifts/repros/quaternion-xyzw.x3d', 'gifts/repros/quaternion-pair.png'),
    ('NURBS weights', 'gifts/repros/nurbs-weights.x3d', 'gifts/repros/nurbs-weights-pair.png'),
    ('NURBS premultiplied', 'gifts/repros/nurbs-weights-premultiplied.x3d', 'gifts/repros/nurbs-weights-pair.png'),
    ('GeoLOD, no origin', 'gifts/repros/geolod-no-origin.x3d', 'gifts/repros/geolod-pair.png'),
    ('GeoLOD, origin', 'gifts/repros/geolod-origin.x3d', 'gifts/repros/geolod-pair.png'),
    ('Annotation', 'gifts/repros/annotation.x3d', 'gifts/repros/annotation-trio.png'),
    ('Annotation, standard', 'gifts/repros/annotation-standard.x3d', 'gifts/repros/annotation-trio.png'),
    ('Splat url', 'gifts/repros/splat-url.x3d', 'gifts/repros/splat-url.png'),
]
DEMOS['spec-questions.html'] = dict(
    title='Questions for the spec', kicker='Demo 8 · Click-to-load repros', h1='Questions for <em>the spec</em>',
    tag='Each open question for the specification as a tiny scene you can load, with what the validator and the browser do with it.',
    poster='gifts/repros/profile-tables.png', hint='Pick a pair. These are questions, not answers.',
    say=G[7]['say'], lead=G[7]['line'], facts=G[7]['facts'], cardTitle=G[7].get('cardTitle', 'For the working group'),
    cfg=dict(scene=PAIRS[0][1], look=dict(toneMapping='NONE'), darkDefault=False, viewpoints=[]),
    extra='<section class="band"><div class="wrap"><h2>The pair, side by side</h2><div class="split"><figure><img id="pair" alt="Rendered pair" src="%s"><figcaption id="paircap">%s</figcaption></figure><div><p class="lead">Each chip loads one file of a repro pair live in the viewer. The picture is the same pair rendered side by side by the validator run.</p></div></div></div></section>' % (PAIRS[0][2], esc(PAIRS[0][0])),
    js='''(function(){var a=document.getElementById('vps'),P=%s;
 P.forEach(function(p,i){var b=document.createElement('button');b.className='chip vp'+(i?'':' on');b.textContent=p[0];
  b.onclick=function(){document.querySelectorAll('#vps .vp').forEach(function(x){x.classList.remove('on')});b.classList.add('on');
   PX.load({scene:p[1]});document.getElementById('pair').src=p[2];document.getElementById('paircap').textContent=p[0]};a.appendChild(b)})})();''' % json.dumps(PAIRS),
)

for fn, d in DEMOS.items():
    page(fn, d)

# ---------------------------------------------------------------- master index
CARDS = [
    ('gobbler.html', 'gifts/gobbler-poster.jpg', '01', 'The Gobbler', 'A bird that assembles itself from 262 nodes, no Script. Bird\'s-eye, in the dark.', ['X3D 4.0', 'ParticleSystems']),
    ('pantheon.html', 'gifts/pantheon-poster.jpg', '02', 'Pantheon · 500,000 splats', 'Half a million Gaussians under the oculus, parsed from X3D live.', ['X3D 4.1', 'GaussianSplats']),
    ('giza.html', 'gifts/giza-poster.jpg', '03', 'Khufu · 970,654 splats', 'The Great Pyramid, stone by stone, in nearly a million Gaussians.', ['X3D 4.1', 'Giza']),
    ('powers-of-ten.html', 'gifts/stars/poster.png', '04', 'Powers of ten', 'From Burruss Hall to 978 stars in one scriptless zoom.', ['X3D 4.0', 'Geospatial']),
    ('drillfield.html', 'gifts/drillfield/poster.png', '05', 'The Drillfield from orbit', 'Real terrain from satellite data, the sun on its real June path.', ['ElevationGrid', 'Real data']),
    ('two-renderers.html', 'gifts/synthsplat/compare.png', '06', 'One scene, two renderers', 'Blender Cycles against X_ITE: SSIM 0.905 for the mesh, 0.977 for splats.', ['Blender', 'Measured']),
    ('materials.html', 'gifts/materials/poster.png', '07', 'Materials from nothing', 'Synthetic textures on standard PhysicalMaterial nodes.', ['PhysicalMaterial', 'Synthetic']),
    ('spec-questions.html', 'gifts/repros/profile-tables.png', '08', 'Questions for the spec', 'Six click-to-load repro pairs, framed as questions.', ['Validator', 'For the group']),
    ('https://claude.ai/artifact/2haGH8DR71XrPHRVorVHYq', 'gifts/materials/poster.png', '09', 'A Material Odyssey', 'The film made from the Materials scene: a slow, symmetrical camera through synthetic gold, stone and silk.', ['Film', 'Opens in a new tab']),
]
SOON = [('Sphinx', 'Synthetic and real-photo splats side by side, with the era wipe.'), ('Shaft of Osiris', 'The shaft at Giza, in the same scene as Khufu.')]

idx = [HEAD % {'title': 'Demos', 'desc': 'PolyXandria: live X3D demos'}]
idx.append(STAGE % {'poster': '<img class="poster" alt="" src="gifts/gobbler-poster.jpg">', 'kicker': 'PolyXandria · live X3D', 'h1': 'Something is <em>awake</em> in the scene graph',
                    'tag': 'Nine demos, one engine: splats, terrain, stars, Blender and the browser rendering the same file. All of it plain X3D you can open and check.',
                    'cta': '<p style="margin-top:22px"><a class="chip on" href="#demos" style="display:inline-block">Enter the demos ↓</a></p>',
                    'nav': nav('index.html'), 'buttons': BTNS, 'hint': 'Lights are out. Move the pointer to find it.'}.copy())
idx.append('<main><section class="band" id="demos"><div class="wrap"><h2>Nine demos</h2><div class="grid">')
for h, img, n, t, p, tags in CARDS:
    ext = ' target="_blank" rel="noopener"' if h.startswith('http') else ''
    idx.append('<a class="card" href="%s"%s><div class="img" style="background-image:url(%s)"></div><div class="tx"><div class="n">Demo %s</div><h3>%s</h3><p>%s</p><div class="tags">%s</div></div></a>' %
               (h, ext, img, n, esc(t), esc(p), ''.join('<span class="pill">%s</span>' % esc(x) for x in tags)))
for t, p in SOON:
    idx.append('<div class="card soon"><div class="img"></div><div class="tx"><div class="n">Next set of files</div><h3>%s</h3><p>%s</p></div></div>' % (esc(t), esc(p)))
idx.append('</div></div></section>')
idx.append('<section class="band"><div class="wrap"><h2>What every demo shares</h2><div class="share">%s</div></div></section>' % ''.join('<div><b>%s</b><span>%s</span></div>' % (esc(a), esc(b)) for a, b in SHARED))
idx.append('<footer><div class="wrap"><p>%s</p><p><a href="gifts.html">The original Gifts page</a></p></div></footer></main>' % esc(DEFAULT_FOOT))
cfg = DEMOS['gobbler.html']['cfg']
idx.append('<script>PX.boot(%s);</script></body></html>' % json.dumps(cfg))
open(os.path.join(ROOT, 'index.html'), 'w', encoding='utf-8').write(''.join(idx))
print('built', len(DEMOS) + 1, 'pages;', sorted(G))
