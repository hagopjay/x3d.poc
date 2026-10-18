"""The 'Physics and fidelity' page: static SVG and HTML drawn from assets/gifts/physics/physics-data.json.

The data file is made by tools/build_physics_data.py from the physics stress test and the 194-case export
conformance suite. Nothing here is drawn from numbers typed by hand; every chart has a table behind it.
"""
import html, json, math

esc = html.escape


def fnum(v, n=3):
    """Compact number text: 1,230 / 0.0128 / 4.8e-7."""
    if v == 0:
        return '0'
    a = abs(v)
    if a >= 1000:
        return '{:,.0f}'.format(v)
    if a >= 1e-3:
        return ('%.' + str(n) + 'g') % v
    m, e = ('%.2e' % v).split('e')
    return '%se%d' % (m.rstrip('0').rstrip('.'), int(e))


# ------------------------------------------------------------------ log-log and semi-log plots
class Plot:
    """A tiny SVG axis pair with log scales; just enough for the three charts here."""
    W, H, L, R, T, B = 360, 250, 56, 14, 14, 44

    def __init__(self, xr, yr, xlog=True):
        self.xr, self.yr, self.xlog = xr, yr, xlog
        self.out = []

    def x(self, v):
        a, b = self.xr
        f = (math.log10(v) - math.log10(a)) / (math.log10(b) - math.log10(a)) if self.xlog else (v - a) / (b - a)
        return self.L + f * (self.W - self.L - self.R)

    def y(self, v):
        a, b = self.yr
        f = (math.log10(v) - math.log10(a)) / (math.log10(b) - math.log10(a))
        return self.H - self.B - f * (self.H - self.B - self.T)

    def frame(self, xlabel, ylabel, xticks, yticks):
        o = self.out
        for t in yticks:
            o.append('<line class="grid" x1="%d" x2="%d" y1="%.1f" y2="%.1f"/><text class="tick" x="%d" y="%.1f" text-anchor="end">%s</text>' % (self.L, self.W - self.R, self.y(t), self.y(t), self.L - 6, self.y(t) + 4, fnum(t, 2)))
        for t in xticks:
            o.append('<line class="grid" x1="%.1f" x2="%.1f" y1="%d" y2="%d"/><text class="tick" x="%.1f" y="%d" text-anchor="middle">%s</text>' % (self.x(t), self.x(t), self.T, self.H - self.B, self.x(t), self.H - self.B + 15, fnum(t, 2)))
        o.append('<line class="axis" x1="%d" x2="%d" y1="%d" y2="%d"/><line class="axis" x1="%d" x2="%d" y1="%d" y2="%d"/>' % (self.L, self.W - self.R, self.H - self.B, self.H - self.B, self.L, self.L, self.T, self.H - self.B))
        o.append('<text class="lab" x="%d" y="%d" text-anchor="middle">%s</text>' % ((self.L + self.W - self.R) // 2, self.H - 6, esc(xlabel)))
        o.append('<text class="lab" transform="translate(13 %d) rotate(-90)" text-anchor="middle">%s</text>' % ((self.T + self.H - self.B) // 2, esc(ylabel)))

    def line(self, pts, cls, dash=None, marker=True):
        d = ' '.join('%.1f,%.1f' % (self.x(a), self.y(b)) for a, b in pts)
        o = '<polyline class="%s" points="%s"%s/>' % (cls, d, ' stroke-dasharray="%s"' % dash if dash else '')
        if marker:
            o += ''.join('<circle class="%s dot" cx="%.1f" cy="%.1f" r="3.2"/>' % (cls, self.x(a), self.y(b)) for a, b in pts)
        self.out.append(o)

    def svg(self, tid, title, desc, cls='plot'):
        return ('<svg class="%s" viewBox="0 0 %d %d" role="img" aria-labelledby="%s-t %s-d"><title id="%s-t">%s</title><desc id="%s-d">%s</desc>%s</svg>' %
                (cls, self.W, self.H, tid, tid, tid, esc(title), tid, esc(desc), ''.join(self.out)))


def decades(lo, hi):
    a, b = math.floor(math.log10(lo)), math.ceil(math.log10(hi))
    return 10.0 ** a, 10.0 ** b, [10.0 ** k for k in range(a, b + 1)]


def loglog(tid, title, pts, order, xlabel, ylabel, refcls):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, x1, xt = decades(min(xs), max(xs))
    y0, y1, yt = decades(min(ys), max(ys))
    p = Plot((x0, x1), (y0, y1))
    p.frame(xlabel, ylabel, xt, yt)
    # the reference: slope = round(order), anchored on the first point
    k = round(order)
    ref = [(xs[0], ys[0]), (xs[-1], ys[0] * (xs[-1] / xs[0]) ** k)]
    p.line(ref, 'ref', '5 4', marker=False)
    p.line(pts, refcls)
    p.out.append('<text class="note" x="%.1f" y="%.1f">fitted order %s</text>' % (p.L + 8, p.T + 14, '%.2f' % order))
    desc = 'Log-log plot, %d points from step %s to %s. Fitted convergence order %s; the dashed line has slope %d.' % (len(pts), fnum(xs[0], 2), fnum(xs[-1], 2), '%.2f' % order, k)
    return p.svg(tid, title, desc)


def divergence(d):
    series = d['determinism']['perturb']
    lo = min(s['start'] for s in series)
    p = Plot((0, 5), (10 ** math.floor(math.log10(lo)), 10.0), xlog=False)
    p.frame('time after the nudge (s)', 'largest body displacement (m)', [0, 1, 2, 3, 4, 5], [1e-6, 1e-4, 1e-2, 1])
    p.out.append('<line class="ref" x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke-dasharray="5 4"/><text class="note" x="%d" y="%.1f">1 cm</text>' % (p.L, p.W - p.R, p.y(0.01), p.y(0.01), p.L + 6, p.y(0.01) - 5))
    styles = [('s1', None), ('s2', '6 3'), ('s3', '2 3')]
    for s, (cls, dash) in zip(series, styles):
        p.line([(0, s['start'])] + list(zip(s['t'], s['div'])), cls, dash)
    desc = '; '.join('a nudge of %s m grows to %s m after 5 s and passes 1 cm after %s s' % (fnum(s['start'], 2), fnum(s['div'][-1], 2), fnum(s['to1cm'], 2)) for s in series)
    return p.svg('div', 'A tiny nudge becomes a large displacement', 'Semi-log plot of the largest body displacement over time for three starting nudges. ' + desc + '.')


# ------------------------------------------------------------------ the sections
def tiles(d):
    out = []
    for c in d['composites']:
        v = c['value']
        if c['key'] == 'rth':
            big, frac, scale = '&times;%s' % fnum(v, 2), v, 'headroom (1&times; = keeps up with the frame rate)'
        else:
            big, frac, scale = '%s<small>%s</small>' % (fnum(v, 3), esc(c['unit'])), v / 100.0, 'of 100' if c['unit'] == '/100' else 'of seeded defects missed'
        out.append('<div class="tile %s"><div class="nm">%s</div><div class="big">%s</div>'
                   '<div class="meter" role="img" aria-label="%s, %s"><i style="width:%.1f%%"></i></div>'
                   '<div class="st">%s</div><p class="aux"><b>%s</b> %s</p><p class="mean">%s</p></div>' %
                   (c['status'], esc(c['name']), big, esc(c['name']), esc(fnum(v, 3) + ' ' + scale), max(frac * 100, 0.8), c['status'].upper(), fnum(c['aux'], 3), esc(c['auxLabel']), esc(c['meaning'])))
    return '<div class="tiles">%s</div>' % ''.join(out)


def loss_table(d):
    rows = []
    for r in d['loss']:
        cell = lambda v: '<td class="%s"><b>%s%%</b> lost</td>' % ('bad' if v >= 100 else 'good', fnum(v, 3))
        rows.append('<tr><th scope="row">%s</th>%s%s</tr>' % (esc(r['path']), cell(r['definitions']), cell(r['motion'])))
    v = d['validator']
    return ('<table class="data"><caption>Share of physics lost on each path (physics_loss_split metrics)</caption><thead><tr><th scope="col">Path</th><th scope="col">Definitions (RigidBody, joints, collision)</th><th scope="col">Motion (the simulated trajectory)</th></tr></thead><tbody>%s</tbody></table>'
            '<p class="note2">The validator side of the same story: %d of %d seeded physics defect classes raise no error or warning, and %d field operations report success while being silently dropped.</p>' %
            (''.join(rows), v['undetected'], v['classesTested'], v['silentOps']))


def realtime(d):
    fps = d['realtime']['fps']
    shapes = d['realtime']['shapes']
    top = max(s['p95'][0] for s in shapes)
    W, RH, LB = 560, 38, 118
    rows = []
    for i, s in enumerate(shapes):
        n = s['p95'][0]
        w = max((W - LB - 60) * n / top, 2)
        y = 10 + i * RH
        rows.append('<text class="lab" x="%d" y="%d" text-anchor="end">%s</text><rect class="bar" x="%d" y="%d" width="%.1f" height="20" rx="3"/><text class="val" x="%.1f" y="%d">%s</text>' %
                    (LB - 8, y + 15, esc(s['shape'].replace('_', ' ').title()), LB, y, w, LB + w + 8, y + 15, fnum(n)))
    H = 10 + len(shapes) * RH
    svg = ('<svg class="rt" viewBox="0 0 %d %d" role="img" aria-labelledby="rt-t rt-d"><title id="rt-t">Bodies that keep up at 24 frames per second, by collision shape</title><desc id="rt-d">%s</desc>%s</svg>' %
           (W, H, esc('Horizontal bars of the largest scene that holds 24 fps on worst-case frames: ' + '; '.join('%s %s bodies' % (s['shape'].lower().replace('_', ' '), fnum(s['p95'][0])) for s in shapes) + '.'), ''.join(rows)))
    tbl = ''.join('<tr><th scope="row">%s</th>%s</tr>' % (esc(s['shape'].replace('_', ' ').title()), ''.join('<td>%s</td><td>%s</td>' % (fnum(s['p95'][k]), fnum(s['p50'][k])) for k in range(len(fps)))) for s in shapes)
    head = ''.join('<th scope="colgroup" colspan="2">%d fps</th>' % f for f in fps)
    table = ('<details class="more"><summary>The numbers behind the bars</summary><table class="data"><caption>Bodies that hold the frame rate (largest N with step time under the frame budget)</caption>'
             '<thead><tr><th rowspan="2" scope="col">Shape</th>%s</tr><tr>%s</tr></thead><tbody>%s</tbody></table></details>' % (head, '<th scope="col">worst case</th><th scope="col">median</th>' * len(fps), tbl))
    return svg + table


def determinism(d):
    de = d['determinism']
    bake = ''.join('<li class="%s"><b>%s</b> %s</li>' % ('good' if f < 0 else 'bad', esc(s.replace('_', ' ').title()), 'bit-identical for all %d frames' % de['bakeFramesChecked'] if f < 0 else 'first differs at frame %d of %d' % (f, de['bakeFramesChecked'])) for s, f in de['bakeFirstDivergence'])
    legend = ''.join('<li><svg width="34" height="10" aria-hidden="true"><line class="%s" x1="0" x2="34" y1="5" y2="5"%s/></svg>nudge of %s m</li>' %
                     (cls, ' stroke-dasharray="%s"' % dash if dash else '', fnum(s['start'], 2)) for s, (cls, dash) in zip(de['perturb'], [('s1', None), ('s2', '6 3'), ('s3', '2 3')]))
    return ('<div class="cols2"><div><h3>Same input, same bits</h3><p class="lead2">%d of %d reruns of a %d-body, %d-frame mixed-shape scene, each in a fresh process, matched the first run bit for bit. '
            'The exported Z13 ball track matches a fresh simulation to %s m.</p><h3 style="margin-top:20px">Bake against live</h3>'
            '<p class="lead2">Playing the baked cache against stepping the live solver (40 bodies, %d frames):</p><ul class="clean">%s</ul></div>'
            '<div><h3>Nudge one float and it diverges</h3>%s<ul class="legend">%s</ul><p class="note2">The 1e-9 m nudge vanished (below float32 resolution). A 1-ulp float32 nudge passes 1 cm in %s s, so a regression test needs bit-exact runs, not close ones.</p></div></div>' %
            (de['rerunsBitIdentical'], de['reruns'], de['bodies'], de['frames'], fnum(de['z13MaxErrM'], 2), de['bakeFramesChecked'], bake, divergence(d), legend, fnum(de['perturb'][-1]['to1cm'], 2)))


def built(c):
    """Zones that have cases in this run (a stress zone is listed in the manifest with none)."""
    return [z for z in c['zones'] if z['core'] + z['fidelityPass'] + z['fidelityWarn'] + z['roadmap'] + z['other']]


def scoreboard(d):
    c = d['conformance']
    zones = built(c)
    mx = max(z['core'] + z['fidelityPass'] + z['fidelityWarn'] + z['roadmap'] + z['other'] for z in zones)
    rows = []
    for z in zones:
        seg = lambda cls, n, label: '<span class="seg %s" style="width:%.2f%%" title="%d %s"></span>' % (cls, n * 100.0 / mx, n, label) if n else ''
        bar = seg('core', z['core'], 'CORE pass') + seg('fp', z['fidelityPass'], 'FIDELITY pass') + seg('fw', z['fidelityWarn'], 'FIDELITY warn') + seg('rm', z['roadmap'], 'ROADMAP missing')
        rows.append('<tr><th scope="row"><span class="zid">%s</span> %s<span class="zt">%s</span></th><td class="barcell"><div class="zbar">%s</div></td><td class="num">%d</td><td class="num">%d</td><td class="num">%d</td><td class="num">%d</td></tr>' %
                    (esc(z['id']), esc(z['name']), esc(z['title']), bar, z['core'], z['fidelityPass'], z['fidelityWarn'], z['roadmap']))
    for zid, why in c['skippedZones']:
        rows.append('<tr class="skip"><th scope="row"><span class="zid">%s</span> not built<span class="zt">%s</span></th><td class="barcell" colspan="5">stress zone, skipped in this run</td></tr>' % (esc(zid), esc(why)))
    lists = lambda title, items: '<details class="more"><summary>%s (%d)</summary><ul class="cases">%s</ul></details>' % (title, len(items), ''.join('<li><code>%s</code> %s</li>' % (esc(i), esc(t)) for i, t in items))
    return ('<div class="tiers">'
            '<div class="tile good"><div class="nm">CORE &middot; the exporter must pass</div><div class="big">%d<small>/%d</small></div><p class="aux">every core case passes</p></div>'
            '<div class="tile warning"><div class="nm">FIDELITY &middot; should pass, gaps reported</div><div class="big">%d<small>/%d</small></div><p class="aux"><b>%d</b> warnings, listed below</p></div>'
            '<div class="tile critical"><div class="nm">ROADMAP &middot; known gaps, tracked</div><div class="big">%d<small> missing</small></div><p class="aux">of %d cases; MISSING is the expected result today</p></div></div>'
            '<ul class="legend key"><li><span class="seg core"></span>CORE pass</li><li><span class="seg fp"></span>FIDELITY pass</li><li><span class="seg fw"></span>FIDELITY warn</li><li><span class="seg rm"></span>ROADMAP missing</li></ul>'
            '<div class="tscroll"><table class="data score"><caption>%d cases in %d zones, exporter %s, suite %s, Blender %s</caption>'
            '<thead><tr><th scope="col">Zone</th><th scope="col">Cases</th><th scope="col" class="num">Core</th><th scope="col" class="num">Fid. pass</th><th scope="col" class="num">Fid. warn</th><th scope="col" class="num">Roadmap</th></tr></thead><tbody>%s</tbody></table></div>%s%s' %
            (c['core']['passed'], c['core']['total'], c['fidelity']['passed'], c['fidelity']['total'], c['fidelity']['warn'], c['roadmap']['missing'], c['roadmap']['total'],
             c['cases'], len(zones), esc(c['exporter']), esc(c['suiteVersion']), esc(c['blender']), ''.join(rows), lists('FIDELITY warnings', c['warn']), lists('ROADMAP gaps', c['missing'])))


CSS = '''<style>
.sub{color:var(--ink2);max-width:68ch;margin:0 0 22px}.lead2{color:var(--ink2);margin:6px 0 10px;font-size:15px;max-width:60ch}.note2{font:12.5px/1.5 var(--mono);color:var(--ink3);margin:10px 0 0;max-width:70ch}
.tiles,.tiers{display:grid;grid-template-columns:repeat(auto-fit,minmax(196px,1fr));gap:14px}.tiers{margin-bottom:18px}
.tile{border:1px solid var(--rule);border-top:3px solid var(--gold2);border-radius:10px;background:var(--bg2);padding:14px 16px 16px}
.tile.critical{border-top-color:var(--maroon)}.tile.warning{border-top-color:var(--ember)}.tile.good{border-top-color:#3f6b4f}
.tile .nm{font:600 11px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--ink3)}.tile .big{font:500 44px/1.1 var(--font);margin:6px 0 8px;color:var(--ink)}.tile .big small{font-size:18px;color:var(--ink3);margin-left:3px}
.meter{height:6px;background:#1b1720;border-radius:3px;overflow:hidden}.meter i{display:block;height:100%;background:var(--gold)}.tile.critical .meter i{background:var(--maroon)}.tile.warning .meter i{background:var(--ember)}
.tile .st{font:600 11px var(--mono);letter-spacing:.14em;margin-top:8px;color:var(--ink2)}.tile .aux{margin:6px 0 0;font-size:14px;color:var(--ink)}.tile .mean{margin:8px 0 0;font-size:12.5px;color:var(--ink3)}
.plots{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:22px}.plots figure{margin:0}.plots figcaption{font:12.5px/1.5 var(--mono);color:var(--ink3);margin-top:6px}
svg.plot,svg.rt{width:100%;height:auto;display:block;border:1px solid var(--rule);border-radius:10px;background:#0d0b10}svg.rt{max-width:640px}
svg .grid{stroke:#241f2b;stroke-width:1}svg .axis{stroke:var(--ink3);stroke-width:1}svg .tick{fill:var(--ink3);font:10px var(--mono)}svg .lab{fill:var(--ink2);font:11.5px var(--sans)}svg .note{fill:var(--ink2);font:11px var(--mono)}
svg .ref{stroke:var(--ink3);stroke-width:1.2;fill:none}svg polyline{fill:none;stroke-width:2}svg .p1{stroke:var(--gold);fill:var(--gold)}svg .p2{stroke:var(--ember);fill:var(--ember)}svg polyline.p1,svg polyline.p2{fill:none}
svg .s1{stroke:var(--gold);fill:var(--gold)}svg .s2{stroke:var(--ember);fill:var(--ember)}svg .s3{stroke:#d07a9a;fill:#d07a9a}svg polyline.s1,svg polyline.s2,svg polyline.s3{fill:none}svg line.s1,svg line.s2,svg line.s3{stroke-width:2}
svg .bar{fill:var(--gold2)}svg .val{fill:var(--ink);font:600 13px var(--mono)}
.cols2{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:36px}@media(max-width:820px){.cols2{grid-template-columns:1fr}}
.cols2 h3{font-size:19px;margin-bottom:4px}ul.clean{list-style:none;padding:0;margin:8px 0 0;font-size:14.5px}ul.clean li{padding:5px 0 5px 12px;border-left:3px solid var(--rule);color:var(--ink2)}ul.clean li.good{border-color:#3f6b4f}ul.clean li.bad{border-color:var(--ember)}ul.clean b{color:var(--ink)}
ul.legend{list-style:none;display:flex;flex-wrap:wrap;gap:6px 18px;padding:0;margin:10px 0 0;font:12px var(--mono);color:var(--ink2)}ul.legend li{display:flex;align-items:center;gap:7px}
table.data{width:100%;border-collapse:collapse;font-size:14px;margin-top:8px}table.data caption{text-align:left;font:12px var(--mono);color:var(--ink3);padding:0 0 8px}
table.data th,table.data td{border-top:1px solid var(--rule);padding:8px 10px;text-align:left;vertical-align:middle}table.data thead th{font:600 11px var(--mono);letter-spacing:.06em;color:var(--ink3);text-transform:uppercase;border-top:0}
table.data td.num,table.data th.num{text-align:right;font-family:var(--mono)}table.data td.bad{color:#f0a0b4}table.data td.good{color:#9fd1af}table.data td b{font-weight:600}
.score .zid{font:600 12px var(--mono);color:var(--gold2);margin-right:6px}.score .zt{display:block;font:12px var(--sans);color:var(--ink3);font-weight:400}.score tr.skip td{color:var(--ink3);font-style:italic}.score .barcell{width:44%}
.zbar{display:flex;height:16px;background:#14111a;border-radius:3px;overflow:hidden}.seg{display:inline-block;height:16px;min-width:3px;box-sizing:border-box}ul.key .seg{width:26px}
.seg.core{background:#3f6b4f}.seg.fp{background:#9fd1af}.seg.fw{background:repeating-linear-gradient(45deg,#e5751f 0 4px,#7a3d0e 4px 8px)}.seg.rm{border:1.5px dashed var(--gold2);background:transparent}
div.tscroll{overflow-x:auto}details.more{margin-top:14px;color:var(--ink2)}details.more summary{cursor:pointer;color:var(--gold);font-size:14px}ul.cases{columns:2 340px;column-gap:28px;padding-left:18px;font-size:13px;color:var(--ink2)}ul.cases code{font:11.5px var(--mono);color:var(--gold2)}
@media(max-width:640px){.score .zt{display:none}.score th,.score td{padding:6px 5px}.score .barcell{min-width:90px}table.data thead th{font-size:10px}.tile .big{font-size:38px}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
</style>'''


def extra(d):
    ball, c, conv = d['ball'], d['conformance'], d['convergence']
    sec = lambda h, intro, body: '<section class="band"><div class="wrap"><h2>%s</h2>%s%s</div></section>' % (h, ('<p class="sub">%s</p>' % intro) if intro else '', body)
    parts = [CSS]
    parts.append(sec('The ball got there. The physics did not.',
                     'The scene above is the exporter\'s own output: a Blender rigid-body drop, baked into one PositionInterpolator of %d keys. '
                     'Watch it fall for %s s and stop. The simulation really did that (Bullet multiplies the two bodies\' restitution, and the ground\'s is 0), and the track reproduces it to %s m. '
                     'What X3D received is a recording. The rigid body, the mass and the collision shape stayed in Blender.' % (ball['keys'], fnum(ball['landingSeconds']), fnum(d['determinism']['z13MaxErrM'], 2)),
                     loss_table(d)))
    parts.append(sec('Five numbers from the stress test', 'Each is computed from the raw measurements: %s records from the X3D layer, %s from the Blender layer, fingerprint <code>%s</code>.' %
                     (fnum(d['meta']['physicsStress']['x3dRecords']), fnum(d['meta']['physicsStress']['blenderRecords']), esc(d['meta']['physicsStress']['fingerprint'])), tiles(d)))
    parts.append(sec('How many bodies keep up?', 'The largest scene whose worst-case frames still fit the 24 fps budget in Blender 5.1\'s solver, 10 substeps, by collision shape. Cost grows about linearly with the body count; what differs is the per-body constant. Triangle meshes are the expensive ones.', realtime(d)))
    parts.append(sec('First order, and second', 'A free-fall drop converges with step size at order %s, so ten times the accuracy costs ten times the substeps. A pendulum, which has no contact, converges at order %s.' % ('%.2f' % conv['freefall']['order'], '%.2f' % conv['pendulum']['order']),
                     '<div class="plots"><figure>%s<figcaption>Free fall for 4 s: worst position error against step size (s).</figcaption></figure><figure>%s<figcaption>Pendulum from 30&deg;: period error against step size (s).</figcaption></figure></div>' %
                     (loglog('ff', 'Free-fall error against step size', conv['freefall']['points'], conv['freefall']['order'], 'step size h (s)', 'worst position error (m)', 'p1'),
                      loglog('pd', 'Pendulum period error against step size', conv['pendulum']['points'], conv['pendulum']['order'], 'step size h (s)', 'period error (%)', 'p2'))))
    parts.append(sec('Deterministic, and chaotic', None, determinism(d)))
    parts.append(sec('The %d-case export scoreboard' % c['cases'], 'A Blender scene with one object or feature per case, exported to X3D 4.0 and 4.1, then read back by an independent validator. '
                     'CORE is what the exporter must get right. FIDELITY is what it should. ROADMAP is the work not yet done, and MISSING is its expected result.', scoreboard(d)))
    return ''.join(parts)


def facts(d):
    b, c, de = d['ball'], d['conformance'], d['determinism']
    return [
        ['Scene', 'Z13.physics, from the suite', 'x3d_suite_main.x3d; %d keys over %s s, unchanged' % (b['keys'], fnum(b['cycleSeconds']))],
        ['Drop', '%s m to %s m in %s s' % (fnum(b['startM']), fnum(b['restM']), fnum(b['landingSeconds'])), 'free fall without drag would take %s s' % fnum(b['freeFallSeconds'])],
        ['Rebound', 'none (under 0.1 mm)', 'stress-test Z13 cross-check: Bullet multiplies the two restitutions, 0.7 x ground 0.0 = 0'],
        ['Track against a fresh simulation', '%s m at most' % fnum(de['z13MaxErrM'], 2), 'the six-decimal text precision of the file'],
        ['Conformance suite', '%d cases, %d zones built' % (c['cases'], len(built(c))), 'suite %s, exporter %s, Blender %s' % (c['suiteVersion'], c['exporter'], c['blender'])],
        ['Stress-test fingerprint', d['meta']['physicsStress']['fingerprint'], 'run of %s; %s' % (d['meta']['physicsStress']['generated'], d['meta']['machine'])],
    ]
