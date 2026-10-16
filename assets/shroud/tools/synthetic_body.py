"""Synthetic forward model of the Shroud body image: a license-free stand-in for a photograph.

A parametric mannequin (ellipsoids and tapered capsules joined by smooth minimum, an implicit surface), supine on a
flat slab, gives the heights of its front and back surfaces by vertical ray marching. The cloth over the front is a slope-limited tent resting on the high points
of the body (see tent_drape); the cloth under the back lies flat on the slab. The vertical cloth-body distance z goes through the JJE linear model,
h = clamp(1 - z / range, 0, 1), with vertical projection onto the flat cloth (JJE's vertical-collimation reading).

Tags (see data/height_model.json): mannequin and drape slope are aesthetic stand-ins; the drape physics and
vertical projection are inferred; the 3.7 cm frontal range is fitted (JJE 1984); the dorsal range is a hypothesis.
This is not a reconstruction of the man of the Shroud and must never be presented as one.
"""
import numpy as np
from scipy import ndimage

STATURE = 1.78   # m, aesthetic choice for the mannequin

# ---------------------------------------------------------------- mannequin as a signed distance field
# Coordinates: x lateral (+ = the figure's left), s along the body from the top of the head toward the feet,
# y height above the slab. Units metres. Parts are ellipsoids ("e": centre, radii) and tapered capsules
# ("c": end A, radius A, end B, radius B); each group is joined with a smooth minimum of blend radius k so the
# figure has no seams. Back surfaces that dip below y = 0 are where soft tissue flattens on the slab (contact).
def _parts():
    head = [
        ("e", (0.000, 0.118, 0.096), (0.073, 0.118, 0.102)),                  # cranium; occiput rests on the slab
        ("e", (0.000, 0.192, 0.118), (0.050, 0.050, 0.072)),                  # jaw and chin
        ("c", (0.040, 0.040, 0.128), 0.008, (0.076, 0.110, 0.150), 0.021),    # hair parted on the crown and held
        ("c", (-0.040, 0.040, 0.128), 0.008, (-0.076, 0.110, 0.150), 0.021),  # up beside the face (as by a chin
        ("c", (0.076, 0.110, 0.150), 0.021, (0.086, 0.285, 0.116), 0.019),    # band; an aesthetic choice)
        ("c", (-0.076, 0.110, 0.150), 0.021, (-0.086, 0.285, 0.116), 0.019),
        ("c", (0.000, 0.205, 0.070), 0.050, (0.000, 0.300, 0.078), 0.058),    # neck
    ]
    torso = [
        ("c", (-0.150, 0.300, 0.080), 0.058, (0.150, 0.300, 0.080), 0.058),   # shoulder girdle
        ("e", (0.195, 0.335, 0.074), (0.055, 0.075, 0.060)),                  # deltoids
        ("e", (-0.195, 0.335, 0.074), (0.055, 0.075, 0.060)),
        ("e", (0.000, 0.460, 0.090), (0.155, 0.175, 0.105)),                  # rib cage
        ("e", (0.070, 0.410, 0.160), (0.078, 0.068, 0.056)),                  # pectorals
        ("e", (-0.070, 0.410, 0.160), (0.078, 0.068, 0.056)),
        ("e", (0.000, 0.665, 0.078), (0.135, 0.150, 0.075)),                  # abdomen, sunken
        ("e", (0.000, 0.835, 0.090), (0.165, 0.115, 0.075)),                  # pelvis
        ("e", (0.072, 0.885, 0.060), (0.085, 0.100, 0.073)),                  # buttocks
        ("e", (-0.072, 0.885, 0.060), (0.085, 0.100, 0.073)),
        ("e", (0.105, 0.400, 0.050), (0.075, 0.105, 0.060)),                  # shoulder blades
        ("e", (-0.105, 0.400, 0.050), (0.075, 0.105, 0.060)),
    ]
    arms = [
        ("c", (0.205, 0.335, 0.072), 0.048, (0.222, 0.585, 0.080), 0.040),    # upper arms along the sides,
        ("c", (-0.205, 0.335, 0.072), 0.048, (-0.222, 0.585, 0.080), 0.040),  # elbows a little off the slab
        ("c", (-0.222, 0.585, 0.080), 0.040, (0.030, 0.778, 0.166), 0.027),   # right forearm (under)
        ("c", (0.222, 0.585, 0.082), 0.040, (-0.034, 0.768, 0.184), 0.027),   # left forearm (over)
    ]
    hands = []
    for hx, hs, hy, d in ((0.048, 0.815, 0.166, 1), (-0.050, 0.805, 0.184, -1)):   # right hand under the left
        hands.append(("e", (hx, hs, hy), (0.040, 0.056, 0.016)))
        for k in range(4):                                                        # long fingers, no thumbs
            x0 = hx + 0.0142 * (k - 1.5) - d * 0.004
            hands.append(("c", (x0, hs + 0.036, hy - 0.002), 0.0066, (x0 - d * 0.006, hs + 0.118, hy - 0.014), 0.0054))
    legs = []
    for d in (1, -1):
        legs += [
            ("c", (d * 0.090, 0.900, 0.085), 0.088, (d * 0.078, 1.225, 0.076), 0.056),   # thigh
            ("e", (d * 0.076, 1.280, 0.080), (0.046, 0.048, 0.048)),                     # knee
            ("c", (d * 0.074, 1.310, 0.072), 0.048, (d * 0.066, 1.665, 0.042), 0.030),   # shin
            ("e", (d * 0.072, 1.430, 0.052), (0.052, 0.115, 0.056)),                     # calf, resting on the slab
            ("e", (d * 0.064, 1.712, 0.036), (0.032, 0.040, 0.040)),                     # heel
            ("c", (d * 0.064, 1.712, 0.046), 0.033, (d * 0.070, 1.800, 0.138), 0.026),   # foot, toes up
        ]
    return [(head, 0.016), (torso, 0.035), (arms, 0.020), (hands, 0.004), (legs, 0.030)], [0.030, 0.022, 0.010, 0.032]

GROUPS, JOINS = _parts()

# Relief detail on the front surface (metres): ("bump"|"dent", x, s, ax, as, height), Gaussian profiles
FACE = [
    ("bump", 0.000, 0.088, 0.048, 0.012, 0.006),     # brow ridge
    ("dent", 0.026, 0.104, 0.015, 0.010, 0.010),     # eye sockets
    ("dent", -0.026, 0.104, 0.015, 0.010, 0.010),
    ("bump", 0.000, 0.124, 0.008, 0.030, 0.016),     # nose ridge
    ("bump", 0.000, 0.146, 0.011, 0.010, 0.010),     # nose tip
    ("bump", 0.034, 0.133, 0.018, 0.019, 0.008),     # cheekbones
    ("bump", -0.034, 0.133, 0.018, 0.019, 0.008),
    ("bump", 0.000, 0.163, 0.024, 0.007, 0.005),     # moustache
    ("bump", 0.000, 0.177, 0.014, 0.006, 0.003),     # lips
    ("bump", 0.014, 0.212, 0.014, 0.030, 0.010),     # forked beard
    ("bump", -0.014, 0.212, 0.014, 0.030, 0.010),
    ("bump", 0.000, 0.036, 0.048, 0.028, 0.006),     # hair over the crown
]


def _ellipsoid(px, ps, py, c, r):
    x, s, y = (px - c[0]) / r[0], (ps - c[1]) / r[1], (py - c[2]) / r[2]
    k0 = np.sqrt(x * x + s * s + y * y)
    k1 = np.sqrt((x / r[0]) ** 2 + (s / r[1]) ** 2 + (y / r[2]) ** 2)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


def _capsule(px, ps, py, a, ra, b, rb):
    ba = np.subtract(b, a)
    l2 = float(ba @ ba)
    qx, qs, qy = px - a[0], ps - a[1], py - a[2]
    t = np.clip((qx * ba[0] + qs * ba[1] + qy * ba[2]) / l2, 0.0, 1.0)
    return np.sqrt((qx - t * ba[0]) ** 2 + (qs - t * ba[1]) ** 2 + (qy - t * ba[2]) ** 2) - (ra + t * (rb - ra))


def _smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def sdf(px, ps, py):
    """Signed distance (approximate, a bound) from points to the mannequin; negative inside."""
    out = None
    for gi, (parts, k) in enumerate(GROUPS):
        g = None
        for p in parts:
            d = _ellipsoid(px, ps, py, *p[1:]) if p[0] == "e" else _capsule(px, ps, py, *p[1:])
            g = d if g is None else _smin(g, d, k)
        out = g if out is None else _smin(out, g, JOINS[gi - 1])
    return out


def _trace(X, S, y0, direction, iters=160, eps=2e-4, fac=0.7, y_stop=None):
    """March vertically from y0 (direction -1: down onto the front, +1: up onto the back); returns y or NaN."""
    y = np.full(X.size, y0)
    x, s = X.ravel(), S.ravel()
    live = np.arange(X.size)
    hit = np.zeros(X.size, bool)
    for _ in range(iters):
        if live.size == 0:
            break
        d = sdf(x[live], s[live], y[live])
        got = d < eps
        hit[live[got]] = True
        y[live] += direction * fac * np.maximum(d, 0.0) * (~got)
        gone = (y[live] - y_stop) * direction > 0
        live = live[~got & ~gone]
    for _ in range(3):                      # pull slightly overshot hits back onto the surface
        idx = np.nonzero(hit)[0]
        y[idx] -= direction * np.minimum(sdf(x[idx], s[idx], y[idx]), 0.0)
    y[~hit] = np.nan
    return y.reshape(X.shape)


def mannequin_heights(dx=0.0025, x_half=0.32, s_lo=-0.02, s_hi=1.86):
    """Front (top) and back (bottom) heights of the mannequin on a regular (s, x) grid, before face relief."""
    xs = np.arange(-x_half, x_half + dx / 2, dx)
    ss = np.arange(s_lo, s_hi + dx / 2, dx)
    X, S = np.meshgrid(xs, ss)
    top = _trace(X, S, 0.40, -1, y_stop=-0.08)
    body = np.isfinite(top)
    bot = np.full(X.shape, np.nan)
    bot[body] = _trace(X[body], S[body], -0.10, +1, y_stop=0.40)
    return xs, ss, top, bot


_CACHE = {}


def surfaces(X, S, dx=0.0025):
    """Front (top) and back (bottom) heights above the slab at points (X, S), metres; NaN outside the body."""
    if dx not in _CACHE:
        _CACHE[dx] = mannequin_heights(dx)
    xs, ss, top, bot = _CACHE[dx]
    body = np.isfinite(top)
    ci = (X - xs[0]) / dx
    ri = (S - ss[0]) / dx
    m = ndimage.map_coordinates(body.astype(float), [ri, ci], order=1, mode="constant", cval=0.0)
    t = ndimage.map_coordinates(np.where(body, top, 0.0), [ri, ci], order=1, mode="constant", cval=0.0)
    b = ndimage.map_coordinates(np.where(body, bot, 0.12), [ri, ci], order=1, mode="constant", cval=0.12)
    inside = m > 0.5
    t = t / np.maximum(m, 1e-6)                       # undo the dilution by the zero fill at the silhouette
    b = (b - 0.12 * (1 - m)) / np.maximum(m, 1e-6)
    for kind, x, s, ax, as_, hgt in FACE:
        t = t + (hgt if kind == "bump" else -hgt) * np.exp(-(((X - x) / ax) ** 2 + ((S - s) / as_) ** 2))
    top = np.where(inside, t, np.nan)
    bot = np.where(inside, np.maximum(b, 0.0), np.nan)   # soft tissue flattens on the slab: contact patches at y = 0
    return top, bot, inside


def tent_drape(top, dx, slope=0.30, smooth=0.008, step_px=8):
    """Cloth laid over the front as a slope-limited envelope ("tent"): it rests on the high points of the body and
    descends from them no steeper than `slope` (rise over run), then is smoothed by a Gaussian of `smooth` metres.
    Computed as grey dilation by a cone (iterated small cones compose exactly), so it bridges hollows such as the
    eye sockets and leaves the steep sides of the body, where the vertical gap grows and the image fades.
    A hanging membrane would wrap every convex part of the body and image the whole silhouette at full strength,
    which the Shroud does not show; the tent is the simplest drape that fades at the sides (inferred, not measured)."""
    r = step_px
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    dist = np.hypot(xx, yy) * dx
    foot = dist <= r * dx
    cone = -slope * dist
    reach = np.nanmax(top) / slope
    c = top.copy()
    for _ in range(int(np.ceil(reach / (r * dx))) + 1):
        c = np.maximum(c, ndimage.grey_dilation(c, footprint=foot, structure=np.where(foot, cone, 0.0), mode="constant", cval=0.0))
    c = ndimage.gaussian_filter(c, smooth / dx)
    return np.maximum(c, top)


def body_image(u_px, v_px, cloth_w, cloth_l, layout, frontal_range=0.037, dorsal_range=0.037, slope=0.30, drape_dx=0.0045, soften=0.002):
    """h on the cloth grid (rows = v along the length, cols = u across the width), plus diagnostics.

    layout: fold_v (fold line as a fraction of the length), head_gap (metres from the fold to each head top along
    the cloth), frontal_dir (+1: the frontal figure extends toward v = 1)."""
    du, dv = cloth_w / u_px, cloth_l / v_px
    X1 = (np.arange(u_px) + 0.5) * du - cloth_w / 2
    Z1 = (np.arange(v_px) + 0.5) * dv
    Xc, Zc = np.meshgrid(X1, Z1)
    fold = layout["fold_v"] * cloth_l
    d = layout["frontal_dir"]
    front_half = (Zc - fold) * d >= 0
    S = np.where(front_half, (Zc - fold) * d, (fold - Zc) * d) - layout["head_gap"]
    top, bot, body = surfaces(Xc, S)

    # tent drape over the frontal half on its own (coarser) grid, sampled back bilinearly
    nu = int(round(cloth_w / drape_dx))
    nv = int(round(cloth_l / drape_dx))
    Xd, Zd = np.meshgrid((np.arange(nu) + 0.5) * cloth_w / nu - cloth_w / 2, (np.arange(nv) + 0.5) * cloth_l / nv)
    Sd = (Zd - fold) * d - layout["head_gap"]
    td, _, bd = surfaces(Xd, Sd)
    obstacle = np.where(bd, td, 0.0)
    obstacle[(Zd - fold) * d < 0] = 0.0
    cloth_d = tent_drape(obstacle, cloth_w / nu, slope)
    cloth = ndimage.map_coordinates(cloth_d, [(Zc / cloth_l) * nv - 0.5, ((Xc + cloth_w / 2) / cloth_w) * nu - 0.5], order=1, mode="nearest")
    cloth = np.maximum(cloth, np.where(body, top, 0.0))

    z = np.where(front_half, cloth - top, bot)
    z = np.where(body, z, np.nan)
    rng = np.where(front_half, frontal_range, dorsal_range)
    h = np.where(body, np.clip(1.0 - z / rng, 0.0, 1.0), 0.0)
    # Soften silhouette steps where a part ends above the slab (hair, fingers): Gaussian, sigma `soften` metres.
    # An aesthetic choice, not a measured image resolution.
    if soften > 0:
        h = ndimage.gaussian_filter(h, (soften / dv, soften / du))
    return dict(h=h.astype(np.float32), z=z.astype(np.float32), top=top.astype(np.float32), bottom=bot.astype(np.float32),
                cloth=np.where(front_half, cloth, 0.0).astype(np.float32), frontal=front_half, body=body, S=S.astype(np.float32))
