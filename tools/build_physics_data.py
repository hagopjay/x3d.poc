#!/usr/bin/env python3
"""Distil the physics stress test and the X3D export conformance suite into the small files the
'Physics and fidelity' page uses. Run it by hand when the source runs change; the output is committed.

    python3 tools/build_physics_data.py PHYSICS_STRESS_DIR SUITE_OUT_DIR [OUT_DIR]

PHYSICS_STRESS_DIR  has metrics/*.jsonl and out/analyst/analysis.json (the analyst's derived numbers).
SUITE_OUT_DIR       has report.html (its DATA block carries every case's tier and verdict),
                    x3d_suite_manifest.json and x3d_suite_main.x3d (the Z13 physics scene).
OUT_DIR             defaults to assets/gifts/physics. Writes physics-data.json (a few KB) and ball.x3d.

Everything is read, rounded and written in a fixed order with no timestamps, so a rerun on the same inputs
produces byte-identical files. Nothing here is estimated: each number is a metric record, an analysis.json
value, or a count over the suite results.
"""
import collections, json, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PS, SUITE = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
OUT = os.path.abspath(sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, '..', 'assets', 'gifts', 'physics'))
os.makedirs(OUT, exist_ok=True)


def jsonl(path):
    return [json.loads(l) for l in open(path, encoding='utf-8') if l.lstrip().startswith('{')]


def sig(x, n=4):
    """Round to n significant figures (keeps tiny errors such as 4.8e-7 readable)."""
    return x if x == 0 else round(x, n - 1 - int(math.floor(math.log10(abs(x)))))


def slope(pts):
    """Least-squares slope of ln y on ln x."""
    xs, ys = [math.log(p[0]) for p in pts], [math.log(p[1]) for p in pts]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    return sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / sum((a - mx) ** 2 for a in xs)


B = jsonl(os.path.join(PS, 'metrics', 'blender.jsonl'))
X = jsonl(os.path.join(PS, 'metrics', 'x3d.jsonl'))
AN = json.load(open(os.path.join(PS, 'out', 'analyst', 'analysis.json'), encoding='utf-8'))

# ---- headline composites (the analyst's own numbers) -------------------------------------------------
NAMES = {'ppi': 'Physics Preservation Index', 'vbs': 'Validator Blind-Spot rate', 'pfs': 'Physics Fidelity Score',
         'si': 'Stability Index', 'rth': 'Real-Time Headroom'}
comp = {c['key']: c for c in AN['composites']}
composites = []
for k in ('ppi', 'vbs', 'pfs', 'si', 'rth'):
    c = comp[k]
    composites.append(dict(key=k, name=NAMES[k], value=sig(c['value'], 3), unit=c['unit'], status=c['status'], aux=sig(c['aux'], 3), auxLabel=c['aux_label'],
                           n=c['n'], meaning=c['meaning']))

# ---- real-time body limits per shape (rigid_scale_derived) -------------------------------------------
rt = collections.defaultdict(dict)
for r in B:
    if r['suite'] == 'rigid_scale_derived' and r['metric'].startswith('max_bodies_realtime_'):
        fps = int(re.search(r'_(\d+)fps', r['metric']).group(1))
        rt[r['params']['shape']].setdefault(r['params']['stat'], {})[fps] = r['value']
FPS = (24, 30, 60)
realtime = [dict(shape=s, p50=[rt[s]['step_ms_p50'][f] for f in FPS], p95=[rt[s]['step_ms_p95'][f] for f in FPS])
            for s in sorted(rt, key=lambda s: -rt[s]['step_ms_p95'][24])]

# ---- convergence --------------------------------------------------------------------------------------
free = sorted((r['params']['h_s'], r['value']) for r in B if r['suite'] == 'rigid_accuracy' and r['case'] == 'freefall_4s' and r['metric'] == 'max_abs_err')
pend = sorted((r['params']['h_s'], r['value']) for r in B if r['suite'] == 'rigid_accuracy' and r['case'] == 'pendulum_convergence' and r['metric'] == 'period_err_pct')
free_order = [r['value'] for r in B if r['metric'] == 'convergence_order' and r['case'] == 'freefall_4s'][0]
convergence = dict(
    freefall=dict(unit='m', order=sig(free_order, 4), points=[[sig(h, 4), sig(e, 4)] for h, e in free]),
    pendulum=dict(unit='% of period', order=sig(slope(pend), 3), points=[[sig(h, 4), sig(e, 4)] for h, e in pend]))

# ---- determinism and chaos ----------------------------------------------------------------------------
det = [r for r in B if r['suite'] == 'determinism']
xproc = [r['value'] for r in det if r['case'] == 'cross_process_5x' and r['metric'] == 'bitwise_equal']
ts = ('0p5', '1', '2', '3', '4', '5')
perturb = []
for case in ('perturb_1e-3', 'perturb_1e-6', 'perturb_1ulp_f32'):
    d = {r['metric']: r['value'] for r in det if r['case'] == case}
    perturb.append(dict(case=case.replace('perturb_', ''), start=sig(d['stored_delta'], 3), t=[0.5, 1, 2, 3, 4, 5],
                        div=[sig(d['max_pos_div_t%ss' % t], 3) for t in ts], to1cm=sig(d['time_to_1cm_divergence'], 3), lyapunov=sig(d['lyapunov_rate'], 3)))
bake = {}
for r in det:
    if r['case'] == 'bake_vs_live_by_shape' and r['metric'] == 'first_diverging_frame':
        bake[r['params']['shape']] = r['value']
z13 = {r['metric']: r['value'] for r in det if r['case'] == 'Z13.physics_vs_exported_x3d'}
determinism = dict(rerunsBitIdentical=sum(1 for v in xproc if v), reruns=len(xproc), frames=det[0]['params']['frames'], bodies=det[0]['params']['n_bodies'],
                   perturb=perturb, bakeFramesChecked=60, bakeFirstDivergence=[[s, bake[s]] for s in ('SPHERE', 'BOX', 'CONVEX_HULL', 'MIXED', 'MESH')],
                   z13MaxErrM=sig(max(z13['max_abs_diff_height'], z13['max_abs_diff_horizontal']), 2))

# ---- what survives the boundary (physics_loss_split) --------------------------------------------------
LAB = {'export_X3D40_X3D41_use_animation': 'Blender to X3D 4.0 / 4.1, animation on', 'export_default_use_animation_false': 'Blender to X3D, default (animation off)',
       'export_X3D33': 'Blender to X3D 3.3', 'import_X3D_to_blender': 'X3D to Blender (import)'}
split = collections.defaultdict(dict)
for r in X:
    m = re.match(r'physics_loss_split:(.+)', r['case'])
    if m and r['metric'] in ('definition_loss_rate', 'motion_loss_rate'):
        split[m.group(1)][r['metric']] = r['value']
loss = [dict(path=LAB[k], definitions=split[k]['definition_loss_rate'], motion=split[k]['motion_loss_rate']) for k in LAB]

det40 = {r['metric']: r['value'] for r in X if r['suite'] == 'detection' and r['case'] == 'all'}
validator = dict(classesTested=40, undetected=int(det40['classes_undetected_by_any_err_or_warn']), silentOps=int(comp['vbs']['aux']))

# ---- the 194-case conformance scoreboard --------------------------------------------------------------
html = open(os.path.join(SUITE, 'report.html'), encoding='utf-8').read()
D = json.loads(re.search(r'const DATA=(\{.*?\});\s*\n', html, re.S).group(1))
MF = json.load(open(os.path.join(SUITE, 'x3d_suite_manifest.json'), encoding='utf-8'))
R = D['results']
zones = []
for z in MF['zones']:
    rs = [r for r in R if r['zone'] == z['id']]
    c = collections.Counter((r['tier'], r['verdict']) for r in rs)
    zones.append(dict(id=z['id'], name=z['name'], title=z['title'], core=c[('CORE', 'PASS')], fidelityPass=c[('FIDELITY', 'PASS')], fidelityWarn=c[('FIDELITY', 'WARN')],
                      roadmap=c[('ROADMAP', 'MISSING')], other=len(rs) - c[('CORE', 'PASS')] - c[('FIDELITY', 'PASS')] - c[('FIDELITY', 'WARN')] - c[('ROADMAP', 'MISSING')]))
tot = collections.Counter((r['tier'], r['verdict']) for r in R)
conformance = dict(suiteVersion=MF['suite_version'], exporter=D['generator'], blender=MF['blender'], created=MF['created'][:10], cases=len(R),
                   core=dict(total=sum(v for (t, _), v in tot.items() if t == 'CORE'), passed=tot[('CORE', 'PASS')]),
                   fidelity=dict(total=sum(v for (t, _), v in tot.items() if t == 'FIDELITY'), passed=tot[('FIDELITY', 'PASS')], warn=tot[('FIDELITY', 'WARN')]),
                   roadmap=dict(total=sum(v for (t, _), v in tot.items() if t == 'ROADMAP'), missing=tot[('ROADMAP', 'MISSING')]),
                   skippedZones=[[s['zone'], s['reason']] for s in MF['skipped_zones']], zones=zones,
                   warn=[[r['id'], r['title']] for r in R if r['verdict'] == 'WARN'], missing=[[r['id'], r['title']] for r in R if r['verdict'] == 'MISSING'])
assert conformance['core']['total'] + conformance['fidelity']['total'] + conformance['roadmap']['total'] == len(R)

# ---- the Z13.physics ball: the exported PositionInterpolator, re-staged in a tiny scene ------------------
main = open(os.path.join(SUITE, 'x3d_suite_main.x3d'), encoding='utf-8').read()
pi = re.search(r'<PositionInterpolator DEF="PI_Z13_ball" key="([^"]+)" keyValue="([^"]+)"', main)
keys = [float(v) for v in pi.group(1).split()]
kv = [float(v) for v in pi.group(2).split()]
ys = kv[1::3]
assert len(keys) == len(ys) == 49 and len(set(kv[0::3])) == 1 and len(set(kv[2::3])) == 1
timer = float(re.search(r'<TimeSensor DEF="SceneTimer" cycleInterval="([\d.]+)"', main).group(1))
rest = ys[-1]
land = next(i for i, y in enumerate(ys) if y <= rest + 1e-3)           # first key at rest height
rebound = max(ys[i] - min(ys[:i + 1]) for i in range(land, len(ys)))    # any rise after touchdown
# drag-free fall time from the start height to the rest height at g = 9.81, for comparison with the landing key
t_fall = math.sqrt(2 * (ys[0] - rest) / 9.81)
ball = dict(keys=len(keys), cycleSeconds=timer, startM=sig(ys[0], 4), restM=sig(rest, 4), landingKey=land + 1, landingSeconds=sig(keys[land] * timer, 3),
            freeFallSeconds=sig(t_fall, 3), reboundM=sig(rebound, 2), source='x3d_suite_main.x3d: PI_Z13_ball (Z13.physics)')

meta = dict(physicsStress=dict(fingerprint=AN['meta']['fingerprint'], generated=AN['meta']['generated'][:10], x3dRecords=AN['status']['x3d'].get('records'), blenderRecords=AN['status']['blender'].get('records')),
            machine='one 8-core Apple M3, 8 GB RAM, with the other test agents running at the same time; timings are medians of repeats')
data = dict(meta=meta, composites=composites, realtime=dict(fps=list(FPS), shapes=realtime), convergence=convergence, determinism=determinism,
            loss=loss, validator=validator, conformance=conformance, ball=ball)
with open(os.path.join(OUT, 'physics-data.json'), 'w', encoding='utf-8') as f:
    json.dump(data, f, separators=(',', ':'), ensure_ascii=False)
    f.write('\n')

# ---- ball.x3d: small, hand-laid-out, the baked track verbatim -------------------------------------------
fmt = lambda v: ('%.6f' % v).rstrip('0').rstrip('.')
kvs = ' '.join('0 %s 0' % fmt(y) for y in ys)
dots = '\n'.join('    <Transform translation="0 %s 0"><Shape USE="Dot"/></Transform>' % fmt(y) for y in ys)
ruler_pts = ['0 0 0', '0 %s 0' % fmt(math.ceil(ys[0]))]
ruler_idx = ['0 1 -1']
for m in range(0, int(math.ceil(ys[0])) + 1):
    ruler_pts += ['-0.18 %d 0' % m, '0.18 %d 0' % m]
    i = len(ruler_pts) - 2
    ruler_idx.append('%d %d -1' % (i, i + 1))
x3d = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE X3D PUBLIC "ISO//Web3D//DTD X3D 4.0//EN" "https://www.web3d.org/specifications/x3d-4.0.dtd">
<X3D profile='Immersive' version='4.0' xmlns:xsd='http://www.w3.org/2001/XMLSchema-instance' xsd:noNamespaceSchemaLocation='https://www.web3d.org/specifications/x3d-4.0.xsd'>
  <head>
    <component name='Shape' level='2'/>
    <component name='Lighting' level='3'/>
    <meta name='title' content='ball.x3d'/>
    <meta name='description' content='The Z13.physics ball from the X3D export conformance suite. Blender simulated a rigid-body drop and the exporter baked it into a PositionInterpolator with %(n)d keys; the keyValues here are those keys, unchanged (x and z fixed, only the height varies). The gold dots mark every key. The ball lands at key %(land)d and stays: the baked motion is faithful, and the simulation it came from never bounced. No Script.'/>
    <meta name='creator' content='HagopJay'/>
  </head>
  <Scene>
    <WorldInfo title='Z13.physics: a baked rigid-body drop'/>
    <Background skyColor='0.016 0.013 0.02'/>
    <NavigationInfo type='"EXAMINE" "ANY"' headlight='false'/>
    <Viewpoint DEF='Side' description='Side view' position='-0.3 2.55 8.4' orientation='1 0 0 -0.03' centerOfRotation='-0.3 2.5 0' fieldOfView='0.78'/>
    <Viewpoint DEF='Landing' description='Landing' position='2.2 0.9 3.4' orientation='0 1 0 0.6' centerOfRotation='0 0.3 0' fieldOfView='0.7'/>
    <DirectionalLight direction='-0.4 -1 -0.5' intensity='1.1' color='1 0.96 0.88'/>
    <PointLight location='-3 4 4' intensity='0.8' radius='30' color='0.7 0.8 1'/>
    <Transform translation='0 -0.2 0'>
      <Shape>
        <Appearance><PhysicalMaterial baseColor='0.2 0.18 0.22' roughness='0.8' metallic='0'/></Appearance>
        <Box size='5.2 0.4 2.4'/>
      </Shape>
    </Transform>
    <Transform translation='-1.3 0 0'>
      <Shape>
        <Appearance><Material emissiveColor='0.5 0.45 0.3'/></Appearance>
        <IndexedLineSet coordIndex='%(ridx)s'><Coordinate point='%(rpts)s'/></IndexedLineSet>
      </Shape>
    </Transform>
    <Transform translation='-0.9 0 0'><Group>
      <Shape DEF='Dot'>
        <Appearance><Material diffuseColor='0.91 0.81 0.54' emissiveColor='0.5 0.43 0.2'/></Appearance>
        <Sphere radius='0.05'/>
      </Shape>
%(dots)s
    </Group></Transform>
    <Transform DEF='Ball' translation='0 %(y0)s 0'>
      <Shape>
        <Appearance><PhysicalMaterial baseColor='0.75 0.17 0.27' roughness='0.35' metallic='0.1'/></Appearance>
        <Sphere radius='0.3'/>
      </Shape>
    </Transform>
    <TimeSensor DEF='Clock' cycleInterval='%(cyc)s' loop='true'/>
    <PositionInterpolator DEF='Track' key='%(keys)s' keyValue='%(kv)s'/>
    <ROUTE fromNode='Clock' fromField='fraction_changed' toNode='Track' toField='set_fraction'/>
    <ROUTE fromNode='Track' fromField='value_changed' toNode='Ball' toField='set_translation'/>
  </Scene>
</X3D>
''' % dict(n=len(keys), land=land + 1, ridx=' '.join(ruler_idx), rpts=' '.join(ruler_pts), dots=dots, y0=fmt(ys[0]), cyc=fmt(timer),
           keys=' '.join(fmt(k) for k in keys), kv=kvs)
open(os.path.join(OUT, 'ball.x3d'), 'w', encoding='utf-8').write(x3d)
print('wrote %s (%d B) and ball.x3d (%d B); ball lands at key %d, rebound %.3g m' % (os.path.join(OUT, 'physics-data.json'), os.path.getsize(os.path.join(OUT, 'physics-data.json')),
                                                                                      os.path.getsize(os.path.join(OUT, 'ball.x3d')), land + 1, rebound))
