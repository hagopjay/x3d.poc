"""Schematic Osiris Shaft as X3D 4.0, generated from a depth table.

Two depth tables, taken from two published diagrams that disagree:
  'paganini'  levels at 4 / 20 / 30 m (the "30 m" figure)
  'author'    cumulative 9.67 + 2.7 + 13.25 + 2.6 + 7.5 + 5.76 = 41.48 m, with four wells C-F
Plan shapes (gallery lengths, chamber footprints, the island and four pillars) are schematic, not surveyed.
"""
import math

TABLES = {
    'paganini': dict(L1_top=-4.0, L1_bot=-6.7, B_from=-4.0, L2_top=-20.0, L2_bot=-22.6, C_from=-20.0, L3_top=-30.0, L3_bot=-35.0, wells=False),
    'author':   dict(L1_top=-9.67, L1_bot=-12.37, B_from=-12.37, L2_top=-25.62, L2_bot=-28.22, C_from=-28.22, L3_top=-35.72, L3_bot=-41.48, wells=True),
}
XE, XB, XC = 0.0, 11.6, 19.8            # entrance, shaft B and shaft C axes (m east); schematic
S = 0.8                                  # half width of a shaft (m)


def norm(v):
    l = math.sqrt(sum(c * c for c in v)) or 1.0
    return [c / l for c in v]


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def look_at(pos, tgt):
    f = norm([tgt[0] - pos[0], tgt[1] - pos[1], tgt[2] - pos[2]])
    up = [0, 0, -1] if abs(f[1]) > 0.999 else [0, 1, 0]
    r = norm(cross(f, up)); u = cross(r, f); z = [-f[0], -f[1], -f[2]]
    m = [[r[0], u[0], z[0]], [r[1], u[1], z[1]], [r[2], u[2], z[2]]]
    tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1) * 2; qw = s / 4; qx = (m[2][1] - m[1][2]) / s; qy = (m[0][2] - m[2][0]) / s; qz = (m[1][0] - m[0][1]) / s
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1 + m[0][0] - m[1][1] - m[2][2]) * 2; qw = (m[2][1] - m[1][2]) / s; qx = s / 4; qy = (m[0][1] + m[1][0]) / s; qz = (m[0][2] + m[2][0]) / s
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1 + m[1][1] - m[0][0] - m[2][2]) * 2; qw = (m[0][2] - m[2][0]) / s; qx = (m[0][1] + m[1][0]) / s; qy = s / 4; qz = (m[1][2] + m[2][1]) / s
    else:
        s = math.sqrt(1 + m[2][2] - m[0][0] - m[1][1]) * 2; qw = (m[1][0] - m[0][1]) / s; qx = (m[0][2] + m[2][0]) / s; qy = (m[1][2] + m[2][1]) / s; qz = s / 4
    ang = 2 * math.acos(max(-1, min(1, qw))); sn = math.sqrt(max(0, 1 - qw * qw))
    return [0, 1, 0, 0] if sn < 1e-6 else [qx / sn, qy / sn, qz / sn, ang]


def box(cx, cy, cz, sx, sy, sz, app):
    return "<Transform translation='%.3f %.3f %.3f'><Shape><Appearance USE='%s'/><Box size='%.3f %.3f %.3f' solid='false'/></Shape></Transform>" % (cx, cy, cz, app, sx, sy, sz)


def vbox(x, z, y_hi, y_lo, half, app):
    """vertical shaft between two heights"""
    return box(x, (y_hi + y_lo) / 2, z, 2 * half, abs(y_hi - y_lo), 2 * half, app)


def voids(t, app):
    out = []
    # entrance shaft, level 1 gallery, shaft B, level 2 hall and six rooms, shaft C, level 3
    out.append(vbox(XE, 0, 0.0, t['L1_top'], S, app))
    out.append(box(5.8, (t['L1_top'] + t['L1_bot']) / 2, 0, 14.0, t['L1_top'] - t['L1_bot'], 4.0, app))
    out.append(vbox(XB, 0, t['B_from'], t['L2_top'], S, app))
    h2 = t['L2_top'] - t['L2_bot']; y2 = (t['L2_top'] + t['L2_bot']) / 2
    out.append(box(7.75, y2, 0, 27.5, h2, 16.0, app))
    for i, x in enumerate((-2.0, 6.5, 15.0)):
        out.append(box(x, y2, -9.75, 5.0, h2, 3.5, app))
        out.append(box(x, y2, 9.75, 5.0, h2, 3.5, app))
    out.append(vbox(XC, 0, t['C_from'], t['L3_top'], S, app))
    h3 = t['L3_top'] - t['L3_bot']; y3 = (t['L3_top'] + t['L3_bot']) / 2
    out.append(box(24.0, y3, 0, 21.0, h3, 18.0, app))
    return ''.join(out)


def build(name):
    t = TABLES[name]
    floor3 = t['L3_bot']; water = floor3 + 1.8; island_top = floor3 + 2.4
    appI = "<Appearance DEF='Stone'><Material diffuseColor='0.56 0.44 0.31' specularColor='0.05 0.05 0.05' shininess='0.1'/></Appearance>"
    appX = "<Appearance DEF='Ghost'><Material diffuseColor='0.95 0.75 0.3' emissiveColor='0.9 0.62 0.16' transparency='0.7'/></Appearance>"
    sand = "<Appearance DEF='Sand'><Material diffuseColor='0.42 0.34 0.22'/></Appearance>"
    sandX = "<Appearance DEF='SandGhost'><Material diffuseColor='0.42 0.34 0.22' transparency='0.82'/></Appearance>"

    def ground(app):
        sl = []
        for (cx, cz, sx, sz) in ((0, -50.4, 200, 99.2), (0, 50.4, 200, 99.2), (-50.4, 0, 99.2, 1.6), (50.4, 0, 99.2, 1.6)):
            sl.append("<Transform translation='%.2f -0.5 %.2f'><Shape><Appearance USE='%s'/><Box size='%.2f 1 %.2f'/></Shape></Transform>" % (cx, cz, app, sx, sz))
        return ''.join(sl)

    wells = ''
    if t['wells']:
        for (x, col) in ((-3.0, '0.25 0.35 1'), (1.5, '0.55 0.33 0.15'), (6.0, '0.2 0.8 0.5'), (10.5, '1 0.85 0.2')):
            h = abs(t['L2_top'])
            wells += "<Transform translation='%.2f %.2f 5'><Shape><Appearance><Material diffuseColor='%s' emissiveColor='%s' transparency='0.2'/></Appearance><Box size='1.0 %.2f 1.0'/></Shape></Transform>" % (x, -h / 2, col, col, h)

    sarc = ("<Transform translation='24 %.2f 0'>"
            "<Shape><Appearance><Material diffuseColor='0.08 0.08 0.09' specularColor='0.4 0.4 0.4' shininess='0.6'/></Appearance><Box size='3.4 1.15 1.2'/></Shape>"
            "<Transform translation='0 0.7 0'><Shape><Appearance><Material diffuseColor='0.1 0.1 0.11' specularColor='0.4 0.4 0.4' shininess='0.6'/></Appearance><Box size='3.6 0.25 1.4'/></Shape></Transform></Transform>") % (island_top + 0.58)
    pillars = ''.join("<Transform translation='%.2f %.2f %.2f'><Shape><Appearance><Material diffuseColor='0.6 0.52 0.4'/></Appearance><Cylinder radius='0.22' height='2.6'/></Shape></Transform>" % (24 + dx, island_top + 1.3, dz)
                      for dx in (-2.3, 2.3) for dz in (-2.3, 2.3))
    island = "<Transform translation='24 %.2f 0'><Shape><Appearance USE='Stone'/><Box size='7 %.2f 7'/></Shape></Transform>" % ((floor3 + island_top) / 2, island_top - floor3)
    waterbox = ("<Transform translation='24 %.2f 0'><Shape><Appearance><Material diffuseColor='0.02 0.07 0.1' specularColor='0.8 0.9 1' shininess='0.9' transparency='0.28'/></Appearance>"
                "<Box size='20.6 0.05 17.6'/></Shape></Transform>") % water

    # camera keys: [time, px, py, pz, tx, ty, tz]
    L1m = (t['L1_top'] + t['L1_bot']) / 2; L2m = (t['L2_top'] + t['L2_bot']) / 2; L3m = floor3 + 3.2
    keys = [
        [0, 0, 12, 0.01, 0, 0, 0],
        [6, 0, 0.5, 0.01, 0, t['L1_top'] - 6, 0],
        [9, 0, t['L1_top'] + 1.0, 0.01, 0, t['L1_top'] - 3, 0],
        [11, 0, L1m, 0, 6, L1m, 0],
        [15, 5, L1m, 0, 14, L1m, 0],
        [19, XB - 0.4, L1m, 0, XB, t['L1_bot'] - 4, 0],
        [26, XB, t['L2_top'] + 1.4, 0, XB, t['L2_top'] - 4, 0],
        [29, XB, L2m, 0, 20, L2m, 0],
        [34, XC - 2, L2m, 0, XC, t['L2_bot'] - 5, 0],
        [38, XC, t['L3_top'] - 2.2, 0, XC, t['L3_top'] - 9, 0],
        [42, XC, L3m + 0.6, 0, 24, floor3 + 2.8, 0],
        [48, 17.5, L3m, 4.8, 24, floor3 + 2.9, 0],
    ]
    out_pos = [-34, t['L3_top'] * 0.45, 62]
    outside_o = look_at(out_pos, [14, t['L3_top'] * 0.5, 0])

    x3d = ("<?xml version='1.0' encoding='UTF-8'?>\n<X3D profile='Immersive' version='4.0' xmlns:xsd='http://www.w3.org/2001/XMLSchema-instance' xsd:noNamespaceSchemaLocation='https://www.web3d.org/specifications/x3d-4.0.xsd'>\n"
           "<head><meta name='title' content='Osiris Shaft, schematic (%s depth table)'/>"
           "<meta name='description' content='Schematic, not surveyed. Level depths from a published diagram; plan shapes are invented for the picture.'/></head>\n<Scene>\n" % name +
           "<WorldInfo title='Osiris Shaft, schematic'/>\n"
           "<Background skyAngle='1.45' skyColor='0.01 0.01 0.04 0.30 0.14 0.18'/>\n"
           "<NavigationInfo type='\"EXAMINE\" \"ANY\"' headlight='true' speed='4'/>\n"
           "<Fog fogType='EXPONENTIAL' color='0.03 0.02 0.04' visibilityRange='170'/>\n"
           "<Viewpoint DEF='Outside' description='Outside' position='%.2f %.2f %.2f' orientation='%.5f %.5f %.5f %.5f' fieldOfView='0.8'/>\n" % (out_pos[0], out_pos[1], out_pos[2], *outside_o) +
           "<DirectionalLight direction='0.3 -1 -0.5' intensity='0.35' color='0.55 0.6 1'/>\n"
           "<PointLight DEF='TorchA' location='5 %.2f 0' color='1 0.55 0.2' intensity='0.9' radius='16' global='true'/>\n" % L1m +
           "<PointLight DEF='TorchB' location='10 %.2f 0' color='1 0.55 0.2' intensity='0.9' radius='18' global='true'/>\n" % L2m +
           "<PointLight DEF='Ghost' location='24 %.2f 0' color='0.3 1 0.7' intensity='0.8' radius='14' global='true'/>\n" % (island_top + 2.2) +
           "<TimeSensor DEF='Clock' cycleInterval='2.9' loop='true'/>\n"
           "<ScalarInterpolator DEF='Flick' key='0 0.15 0.3 0.5 0.7 0.85 1' keyValue='0.9 0.55 1 0.65 0.95 0.5 0.9'/>\n"
           "<ScalarInterpolator DEF='Pulse' key='0 0.5 1' keyValue='0.5 1.1 0.5'/>\n"
           "<ROUTE fromNode='Clock' fromField='fraction_changed' toNode='Flick' toField='set_fraction'/>\n"
           "<ROUTE fromNode='Clock' fromField='fraction_changed' toNode='Pulse' toField='set_fraction'/>\n"
           "<ROUTE fromNode='Flick' fromField='value_changed' toNode='TorchA' toField='set_intensity'/>\n"
           "<ROUTE fromNode='Flick' fromField='value_changed' toNode='TorchB' toField='set_intensity'/>\n"
           "<ROUTE fromNode='Pulse' fromField='value_changed' toNode='Ghost' toField='set_intensity'/>\n"
           + "<Shape>" + appI + "</Shape><Shape>" + sand + "</Shape><Shape>" + appX + "</Shape><Shape>" + sandX + "</Shape>" +
           "<Switch DEF='Look' whichChoice='0'>"
           "<Group>" + voids(t, 'Stone') + ground('Sand') + "</Group>"
           "<Group>" + voids(t, 'Ghost') + ground('SandGhost') + wells + "</Group>"
           "</Switch>\n"
           "<Switch DEF='Flood' whichChoice='0'><Group>" + waterbox + "</Group></Switch>\n"
           "<Group>" + island + pillars + sarc + "</Group>\n"
           "</Scene>\n</X3D>\n")
    return x3d, keys, dict(depth=abs(t['L3_bot']), levels=[t['L1_top'], t['L2_top'], t['L3_top']])


if __name__ == '__main__':
    import sys
    for n in TABLES:
        x, k, m = build(n)
        open(sys.argv[1] + '/osiris-%s.x3d' % n, 'w').write(x)
        print(n, len(x), m)
