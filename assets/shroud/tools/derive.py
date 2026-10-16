#!/usr/bin/env python3
"""Derive every computed file of the package from data/constants.json, and check the results against it.

    python3 tools/derive.py            # writes data/spectral, data/weave*, data/dimensions.json,
                                       # data/height_model.json, data/perception*, maps/synthetic, maps/weave
    python3 tools/derive.py --h my_h.png   # use a measured h map (16-bit grey, same layout) instead of the synthetic one

Needs numpy, scipy, colour-science and OpenEXR. Every number written here traces to a constant id or is a parameter
recorded with its tag in the file it lands in. A failed check stops the run.
"""
import argparse
import csv
import os
import sys
import time

import numpy as np
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shroudlib as L                     # noqa: E402
import synthetic_body as SB               # noqa: E402

CHECKS = []


def check(name, got, want, tol):
    ok = bool(np.all(np.abs(np.asarray(got, float) - np.asarray(want, float)) <= tol))
    CHECKS.append({"check": name, "got": np.round(np.asarray(got, float), 4).tolist(),
                   "want": want, "tolerance": tol, "ok": ok})
    print(("ok   " if ok else "FAIL ") + name, np.round(np.asarray(got, float), 4).tolist(), "want", want)
    return ok


def rel(pkg, path):
    return os.path.relpath(path, pkg).replace(os.sep, "/")


# ---------------------------------------------------------------- spectral
def spectral(pkg, C):
    p = L.jje_params(C)
    hs, lut, info, lam = L.bake_lut(p)
    D = os.path.join(pkg, "data", "spectral")
    d65 = lut[0]
    Y = d65 @ L.REC709_Y
    lerp = d65[0] + np.outer(hs, d65[-1] - d65[0])
    check("LUT is linear in h (max deviation from lerp)", np.abs(lerp - d65).max(), 0.0, 1e-6)
    check("linen, D65, linear sRGB", d65[0], C["colour.linen_d65_linear"]["value"], 0.0006)
    check("image at h = 1, D65, linear sRGB", d65[-1], C["colour.image_max_d65_linear"]["value"], 0.0006)
    check("tint at h = 1, D65", d65[-1] / d65[0], C["colour.image_tint_h1_d65"]["value"], 0.0006)
    check("linen luminance Y, D65", Y[0], C["colour.linen_d65_Y"]["value"], 0.0006)
    check("luminance density at h = 1, D65", -np.log10(Y[-1] / Y[0]), C["image.density_luminance_d65"]["value"], 0.0006)
    att = [float(L.jje_reflectance(l, 1.0, p) / L.jje_reflectance(l, 0.0, p)) for l in (440, 550, 680)]
    check("reflectance ratio at h = 1 (440, 550, 680 nm)", att, C["image.attenuation_h1"]["value"], 0.0006)
    check("reflectance at 550 nm, h = 0 and 1", [L.jje_reflectance(550, 0, p), L.jje_reflectance(550, 1, p)],
          [C["image.reflectance_550_background"]["value"], C["image.reflectance_550_max"]["value"]], 0.0006)
    check("density at 550 nm, h = 1", -np.log10(L.jje_reflectance(550, 1, p) / L.jje_reflectance(550, 0, p)),
          C["image.density_range"]["value"], 0.0015)
    check("sRGB-encoded linen and image, D65", [L.srgb_encode(d65[0]), L.srgb_encode(d65[-1])],
          [C["colour.linen_d65_srgb_encoded"]["value"], C["colour.image_max_d65_srgb_encoded"]["value"]], 0.0006)

    names = [i["name"] for i in info]
    L.write_json(os.path.join(D, "shroud_spectral_lut.json"), {
        "title": "Shroud body-image albedo LUT (JJE 1984 model under seven illuminants)",
        "model": "r(lambda, h) = (a + b*lambda) * [1 + c*(lambda - lambda_prime)*h]",
        "params": {k: p[k] for k in ("a", "b", "c", "lambda_prime")}, "valid_nm": list(p["valid"]),
        "constant_ids": ["jje.a", "jje.b", "jje.c", "jje.lambda_prime_nm", "jje.validity_nm"],
        "citations": ["jje1984", "cie1931"],
        "method": "CIE 1931 2 degree observer, 380-780 nm in 5 nm steps; reflectance held at its 300 and 700 nm values "
                  "outside the fitted range; illuminant white adapted to D65 (CAT02); linear sRGB (Rec. 709 primaries); "
                  "clipped to [0, 1]. Identical to unity/v3-collateral/bake_shroud_spectral_lut.py.",
        "encoding": "linear; import as data (no sRGB decoding)",
        "h": [round(float(x), 6) for x in hs],
        "rows": names, "illuminants": info,
        "rgb": {n: np.round(lut[i], 6).tolist() for i, n in enumerate(names)},
        "luminance_Y": {n: np.round(lut[i] @ L.REC709_Y, 6).tolist() for i, n in enumerate(names)},
        "albedo_rule": C["convention.albedo_rule"]["value"],
    })
    with open(os.path.join(D, "shroud_spectral_lut.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["illuminant", "h", "R_linear", "G_linear", "B_linear", "Y"])
        for i, n in enumerate(names):
            for k, h in enumerate(hs):
                w.writerow([n, round(float(h), 6), *np.round(lut[i, k], 6), round(float(lut[i, k] @ L.REC709_Y), 6)])
    L.write_png(os.path.join(D, "shroud_spectral_lut_16bit.png"), L.to_u16(lut),
                {"Description": "rows = illuminants (see shroud_spectral_lut.json), columns = h 0..1; linear sRGB x 65535"})
    L.write_exr(os.path.join(D, "shroud_spectral_lut.exr"), lut.astype(np.float32))
    with open(os.path.join(D, "jje1984_reflectance.csv"), "w", newline="") as f:
        w = csv.writer(f)
        cols = [0.0, 0.25, 0.5, 0.75, 1.0]
        w.writerow(["wavelength_nm"] + ["r_h%.2f" % h for h in cols] + ["ratio_h1_over_h0"])
        for l in lam:
            r = [float(L.jje_reflectance(l, h, p)) for h in cols]
            w.writerow([int(l)] + [round(x, 6) for x in r] + [round(r[-1] / r[0], 6)])
    L.write_json(os.path.join(D, "illuminants.json"), {"illuminants": info, "note": (
        "Blackbody stand-ins for historical light sources are aesthetic; D65 and A are CIE standards. "
        "Each row is adapted to D65, so put the illuminant's colour in the LUT row or in the light, never both.")})
    return {"hs": hs, "lut": lut, "names": names, "Y": Y}


# ---------------------------------------------------------------- weave
def weave(pkg, C):
    warp = C["weave.warp_per_cm"]["value"] * 100
    weft = C["weave.weft_per_cm"]["value"] * 100
    rep = tuple(C["weave.band_repeat_threads"]["value"])
    yarn = C["weave.yarn_diameter_mm"]["value"] / 1000
    n_weft = 52                                     # a multiple of the 4-pick twill repeat, so the tile is near square
    tpt = 8                                         # texels per thread: 640 x 416 texels for 80 warp by 52 weft
    height, warp_top, (size_s, size_t) = L.weave_tile(warp, weft, rep, n_weft, tpt, yarn)
    n = L.normal_map(height, size_s, size_t)
    M = os.path.join(pkg, "maps", "weave")
    flip = lambda a: a[::-1]                        # arrays are [t up, s]; PNG rows run top-down
    L.write_png(os.path.join(M, "weave_height_16bit.png"), L.to_u16(flip(height / yarn)),
                {"Description": "herringbone tile height / yarn diameter; s across the width, t (up) along the length"})
    L.write_png(os.path.join(M, "weave_normal.png"), L.to_u8(flip(n * 0.5 + 0.5)),
                {"Description": "tangent-space normals, OpenGL convention (green = +t), slope space: (-dh/ds, -dh/dt, 1) / 2.5; normalize after sampling"})
    ao = 0.55 + 0.45 * (height / yarn)              # crevices darker: a visual cue, not a measurement
    L.write_png(os.path.join(M, "weave_occlusion.png"), L.to_u8(flip(ao)))
    L.write_png(os.path.join(M, "weave_warp_on_top.png"), (flip(warp_top) * 255).astype(np.uint8))
    W, Lc = C["cloth.width_pre2002_m"]["value"], C["cloth.length_pre2002_m"]["value"]
    i = np.arange(rep[0] + rep[1])
    j = np.arange(8)
    grid = ~L.weft_on_top(i[None, :], j[:, None], rep)
    L.write_json(os.path.join(pkg, "data", "weave.json"), {
        "title": "Weave of the Shroud linen as data",
        "structure": L.ref(C, "weave.structure"),
        "warp_per_m": warp, "weft_per_m": weft,
        "counts": [L.ref(C, "weave.warp_per_cm"), L.ref(C, "weave.weft_per_cm")],
        "band_repeat_threads": L.ref(C, "weave.band_repeat_threads"),
        "band_orientation": L.ref(C, "weave.band_orientation"),
        "yarn_diameter": L.ref(C, "weave.yarn_diameter_mm"),
        "rule": {
            "tag": "convention",
            "text": "i = floor(u_m * warp_per_m) counts warp threads across the width; j = floor(v_m * weft_per_m) "
                    "counts weft picks along the length; p = i mod 80; phase = p if p <= 40 else 80 - p; "
                    "the weft is on top where (phase + j) mod 4 == 0, so the warp floats over three picks and under one.",
            "first_8_picks_by_80_warp": ["".join("W" if x else "f" for x in row) for row in grid],
            "legend": "W = warp on top, f = weft on top",
        },
        "tile": {"warp_threads": int(rep[0] + rep[1]), "weft_picks": n_weft, "pixels": [int(height.shape[1]), int(height.shape[0])], "texels_per_thread": tpt,
                 "size_m": [round(size_s, 7), round(size_t, 7)],
                 "repeats_on_cloth_pre2002": [round(W / size_s, 4), round(Lc / size_t, 4)],
                 "files": ["maps/weave/weave_height_16bit.png", "maps/weave/weave_normal.png",
                           "maps/weave/weave_occlusion.png", "maps/weave/weave_warp_on_top.png"],
                 "orientation": "s across the width (warp count), t along the length (weft count); PNG row 0 is t = 1",
                 "normal_encoding": "slope space: rgb = 0.5 + 0.5 * (-dh/ds, -dh/dt, 1) / 2.5, slopes clipped at 2.5; "
                                    "normalize after sampling (glTF and X3D renderers do). Mipmaps then average slopes, "
                                    "so the weave fades to flat with distance instead of striping.",
                 "profile_tag": "aesthetic",
                 "profile": "elliptical yarn sections at 0.9 of the pitch; a thread passing over sits a full yarn "
                            "height up, under it 0.45 of it; cosine transitions between crossings"},
        "threads_on_cloth_pre2002": [round(W * warp), round(Lc * weft)],
    })
    return {"tile_m": (size_s, size_t)}


# ---------------------------------------------------------------- dimensions and height model
def dimensions(pkg, C, res):
    W, Lc = C["cloth.width_pre2002_m"]["value"], C["cloth.length_pre2002_m"]["value"]
    L.write_json(os.path.join(pkg, "data", "dimensions.json"), {
        "title": "Dimensions and coordinate conventions",
        "restoration_default": L.ref(C, "convention.restoration_default"),
        "states": {
            "pre-2002": {"length_m": Lc, "width_m": W,
                         "constants": [L.ref(C, "cloth.length_pre2002_m"), L.ref(C, "cloth.width_pre2002_m")],
                         "note": "The state Enrie 1931 and STURP 1978 recorded; the default."},
            "post-2002": {"length_m": C["cloth.length_post2002_m"]["value"], "width_m": C["cloth.width_post2002_m"]["value"],
                          "constants": [L.ref(C, "cloth.length_post2002_m"), L.ref(C, "cloth.width_post2002_m")],
                          "note": "After the 2002 restoration removed the 1534 patches and the backing cloth."},
        },
        "thickness": L.ref(C, "cloth.thickness_um"),
        "units": L.ref(C, "convention.units"),
        "axes": L.ref(C, "convention.axes"),
        "uv": {"tag": "convention",
               "text": "u_m runs 0..width across the cloth, v_m runs 0..length along it; texture s = u_m / width, "
                       "t = v_m / length. Placed flat: X = u_m - width/2, Y = 0, Z = v_m - length/2, so s runs along +X "
                       "and t along +Z, as an X3D ElevationGrid maps them. Seen as in the usual horizontal display (dorsal image left, "
                       "frontal right, heads meeting in the middle), v_m = 0 is the left end. In the synthetic maps u_m = width "
                       "is the figure's left side in both images; for a measured map, record its own orientation."},
        "map_grid": L.ref(C, "convention.map_grid"),
        "synthetic_map_grid": {"value": [res, 4 * res], "tag": "convention",
                               "note": "Half the convention grid; the synthetic image has no detail finer than 5 mm. Sample by UV."},
        "png_rows": "Row 0 of every map PNG is t = 1 (v_m = length); the last row is t = 0.",
    })


def height_model(pkg, C, stats):
    L.write_json(os.path.join(pkg, "data", "height_model.json"), {
        "title": "How the image field h relates to cloth-body distance",
        "h": L.ref(C, "convention.h_range"),
        "models": {
            "linear_frontal": {"formula": "z = range * (1 - h)", "range": L.ref(C, "distance.frontal_range_m"),
                               "r2": L.ref(C, "distance.frontal_r2"), "sigma": L.ref(C, "distance.frontal_sigma_m"),
                               "n_points": L.ref(C, "distance.frontal_n_points"), "tag": "fitted",
                               "note": "The default everywhere in this package."},
            "exponential": {"constant": L.ref(C, "distance.exponential_model"), "z0_m": 0.00803, "tag": "hypothesis"},
            "dorsal": {"range": L.ref(C, "distance.dorsal_range_m"), "tag": "hypothesis",
                       "note": "No measured dorsal range exists; the frontal range is reused as a placeholder."},
            "pressure": {"constant": L.ref(C, "distance.pressure_ratio"),
                         "note": "Equal frontal and dorsal amplitudes at about 77x pressure difference (JJE); "
                                 "'dorsal darker = gravity' is retracted (see corrections.json)."},
            "projection": L.ref(C, "distance.vertical_collimation"),
            "relief_display": L.ref(C, "distance.relief_exaggeration_default"),
            "superseded_range": L.ref(C, "distance.range_prd_0p04"),
        },
        "legacy_bakers": {"tag": "superseded", "note": (
            "Three earlier bakers turned photograph luminance into height (PRD Rec.709 luma, the Unity port's "
            "percentile baker, Shader of the Shroud's percentile with polarity detection). None masks blood, scorch "
            "or patches, so those become bumps. The build plan replaces them with one JJE inversion with masks, "
            "which needs the masks and a licensed photograph; until then this package uses the synthetic field below.")},
        "synthetic_forward_model": {
            "module": "tools/synthetic_body.py", "tag": "aesthetic",
            "warning": "A license-free stand-in for the measured image. Not a reconstruction of the man of the Shroud.",
            "mannequin": {"stature_m": SB.STATURE, "tag": "aesthetic",
                          "parts": "ellipsoids and tapered capsules joined by smooth minimum; supine on a flat slab"},
            "drape": {"kind": "slope-limited tent over the front", "slope": stats["slope"], "smooth_m": 0.008, "tag": "inferred"},
            "projection": "vertical, as JJE read the image", "ranges_m": {"frontal": stats["frontal_range"], "dorsal": stats["dorsal_range"]},
            "soften_sigma_m": stats["soften"], "soften_note": "Gaussian of FWHM 5 mm, the image resolution floor (image.resolution_floor_m).",
            "layout": stats["layout"], "statistics": stats["stats"],
        },
    })


# ---------------------------------------------------------------- maps
def synthetic_maps(pkg, C, res, sp, h_override=None):
    W, Lc = C["cloth.width_pre2002_m"]["value"], C["cloth.length_pre2002_m"]["value"]
    layout = dict(fold_v=0.5, head_gap=0.10, frontal_dir=1)
    fr, dr = C["distance.frontal_range_m"]["value"], C["distance.dorsal_range_m"]["value"]
    soften = C["image.resolution_floor_m"]["value"] / 2.3548
    slope = 0.30
    t0 = time.time()
    r = SB.body_image(res, 4 * res, W, Lc, layout, frontal_range=fr, dorsal_range=dr, slope=slope, soften=soften)
    print("synthetic body image %.1f s" % (time.time() - t0))
    h = r["h"].astype(np.float64)
    if h_override is not None:
        from PIL import Image
        h = np.asarray(Image.open(h_override)).astype(np.float64)[::-1] / 65535.0
        assert h.shape == (4 * res, res), "the h map must be %d x %d (width x height)" % (res, 4 * res)
    body, frontal = r["body"], r["frontal"]
    M = os.path.join(pkg, "maps", "synthetic")
    flip = lambda a: a[::-1]
    rng = np.random.default_rng(1984)
    dither = lambda shape: (rng.random(shape) + rng.random(shape) - 1.0) / 255.0   # triangular, one 8-bit step

    L.write_png(os.path.join(M, "h_16bit.png"), L.to_u16(flip(h)), {"Description": "synthetic image field h x 65535"})
    half = lambda a: a.reshape(a.shape[0] // 2, 2, a.shape[1] // 2, 2, *a.shape[2:]).mean(axis=(1, 3))
    h2 = half(h)
    L.write_png(os.path.join(M, "h_8bit_dithered_half.png"), L.to_u8(flip(h2) + dither(h2.shape)),
                {"Description": "h at half resolution for shaders, dithered so mip levels keep sub-step precision"})
    L.write_png(os.path.join(M, "mask_frontal.png"), (flip(frontal) * 255).astype(np.uint8))
    L.write_png(os.path.join(M, "mask_body.png"), (flip(body) * 255).astype(np.uint8))
    for k in ("z", "top", "bottom", "cloth"):              # half resolution, half floats: -1 marks "no body"
        a = r[k].astype(np.float64)[::2, ::2]
        L.write_exr(os.path.join(M, "%s_m_half.exr" % k), flip(np.where(np.isfinite(a), a, -1.0)).astype(np.float16))

    # albedo (D65) and the tint multiplier on linen; both sRGB-encoded with dither
    lut = sp["lut"][0]
    alb = lut[0][None, None, :] + h2[..., None] * (lut[-1] - lut[0])[None, None, :]
    tint = alb / lut[0][None, None, :]
    L.write_png(os.path.join(M, "albedo_d65_srgb.png"), L.to_u8(flip(L.srgb_encode(alb)) + dither(alb.shape)))
    L.write_png(os.path.join(M, "tint_d65_srgb.png"), L.to_u8(flip(L.srgb_encode(tint)) + dither(tint.shape)))
    # human preview: the usual horizontal display, dorsal left, frontal right, figure's left at the top
    from PIL import Image
    prev = Image.fromarray(L.to_u8(h)).rotate(90, expand=True)
    prev.resize((prev.width // 2, prev.height // 2), Image.LANCZOS).save(os.path.join(M, "preview_h.png"))
    stats = {"frontal_mean_h_on_body": round(float(h[body & frontal].mean()), 3),
             "dorsal_mean_h_on_body": round(float(h[body & ~frontal].mean()), 3),
             "frontal_fraction_h_over_0.9": round(float((h[body & frontal] > 0.9).mean()), 3)}
    return {"h": h, "body": body, "frontal": frontal, "stats": stats, "layout": layout, "slope": slope,
            "soften": round(soften, 5), "frontal_range": fr, "dorsal_range": dr, "du": W / res, "dv": Lc / (4 * res)}


# ---------------------------------------------------------------- perception
def perception(pkg, C, sp, mp):
    """Band-limited contrast of the image (Peli 1990) weighted by contrast sensitivity (Mannos and Sakrison 1974)
    at each viewing distance; the peak sensitivity comes from the measured threshold (0.004 optical density)."""
    h = mp["h"].astype(np.float32)
    dx = (mp["du"] + mp["dv"]) / 2
    lut = sp["lut"][0]
    Y0, Y1 = lut[0] @ L.REC709_Y, lut[-1] @ L.REC709_Y
    a = 1.0 - Y1 / Y0                                         # Y = Y0 * (1 - a h)
    thr_od = C["perception.threshold_density"]["value"]
    c_t = 1.0 - 10 ** (-thr_od)
    s_peak = 1.0 / c_t
    f_pk, s_max = L.csf_peak_value()
    sig = [2.0 ** k for k in range(0, 11)]                    # pixels: 1 px .. 1024 px (about 1 mm .. 1.1 m), so the
                                                              # residual G(sigma_K) is close to the cloth's mean and every
                                                              # body-scale band is weighed by the CSF like the rest
    stack = L.gaussian_stack(h, sig)
    sig_m = [0.0] + [s * dx for s in sig]
    bands, f_m = [], []
    for k in range(len(sig)):
        bands.append(stack[k] - stack[k + 1])
        f_m.append(L.dog_peak_frequency(sig_m[k] if k else 0.5 * dx, sig_m[k + 1]))
    low = [stack[k + 1] for k in range(len(sig))]
    sel = ndimage.binary_dilation(mp["body"], iterations=8)
    contr = [np.abs(a * b[sel]) / (1.0 - a * l[sel]) for b, l in zip(bands, low)]
    c99 = [float(np.percentile(c, 99)) for c in contr]
    dists = np.geomspace(0.1, 30.0, 121)
    rows = []
    for d in dists:
        s_abs = s_peak * L.csf_mannos_sakrison(L.angular_frequency(np.array(f_m), d)) / s_max
        v = np.array(c99) * s_abs
        rows.append((d, v))
    V = np.array([r[1].max() for r in rows])

    def d50(scale):
        above = np.nonzero(V * scale >= 1.0)[0]
        if not above.size:
            return None
        k = above[0]
        if k == 0:
            return float(dists[0])
        x0, x1 = np.log(dists[k - 1]), np.log(dists[k])
        y0, y1 = np.log(V[k - 1] * scale), np.log(V[k] * scale)
        return float(np.exp(x0 + (0 - y0) * (x1 - x0) / (y1 - y0)))

    target = C["perception.min_distance_m"]["value"]
    d_pred = d50(1.0)
    vi = np.interp(np.log(target), np.log(dists), np.log(V))
    cal = float(np.exp(-vi))                                   # scale so that V(1.8 m) = 1
    beta = 3.5
    P = 1.0 - np.power(2.0, -np.power(V * cal, beta))
    D = os.path.join(pkg, "data")
    with open(os.path.join(D, "visibility_vs_distance.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["distance_m", "visibility_uncalibrated", "visibility_calibrated", "p_detect_calibrated"]
                   + ["band%d_visibility_uncalibrated" % k for k in range(len(sig))])
        for (d, v), Vi, Pi in zip(rows, V, P):
            w.writerow([round(float(d), 4), round(float(Vi), 5), round(float(Vi * cal), 5), round(float(Pi), 5)]
                       + [round(float(x), 5) for x in v])
    model = {
        "title": "Perceptual dissolve model: why the image is not seen closer than about 1.8 m",
        "tag": "inferred",
        "constant": L.ref(C, "perception.dissolve_model"),
        "measured_target": L.ref(C, "perception.min_distance_m"),
        "threshold": L.ref(C, "perception.threshold_density"),
        "luminance": {"Y_linen_d65": round(float(Y0), 4), "Y_h1_d65": round(float(Y1), 4), "a": round(float(a), 4),
                      "rule": "Y = Y_linen * (1 - a*h), exact for the JJE model (linear in h)"},
        "csf": {"name": "Mannos and Sakrison 1974", "formula": "S(f) = 2.6 (0.0192 + 0.114 f) exp(-(0.114 f)^1.1), f in cycles/degree",
                "peak_cpd": round(f_pk, 3), "peak_value": round(s_max, 5), "citations": ["mannos1974"], "tag": "standard"},
        "peak_sensitivity": {"value": round(s_peak, 2), "from": "1 / (1 - 10^-0.004): the measured threshold read as the CSF peak",
                             "tag": "derived"},
        "bands": {"method": "Gaussian stack on h (large sigmas filtered on block-averaged copies), band k = G(sigma_k) - G(sigma_k+1), local contrast "
                            "c_k = a*band_k / (1 - a*G(sigma_k+1)) (Peli 1990); 99th percentile over the body region",
                  "citations": ["peli1990"],
                  "sigma_m": [round(s, 6) for s in sig_m[1:]], "peak_frequency_cycles_per_m": [round(f, 3) for f in f_m],
                  "contrast_p99": [round(c, 5) for c in c99]},
        "angular_frequency": "f_deg = f_m * distance * pi / 180",
        "visibility": "v_k(d) = c_k * S_peak * S(f_deg) / S(peak); V(d) = max_k v_k; detection P = 1 - 2^(-(V*cal)^3.5)",
        "prediction": {"d50_m_uncalibrated": None if d_pred is None else round(d_pred, 3), "tag": "derived",
                       "note": "Where the uncalibrated model crosses threshold, using only the measured threshold, "
                               "the standard CSF and the synthetic image. It is a consistency check, not a measurement."},
        "calibration": {"factor": round(cal, 4), "tag": "fitted",
                        "note": "Multiplies the sensitivity so detection crosses 50 % at 1.8 m (one measured point)."},
        "renderer_gain": {"formula": "g_k = v^3 / (1 + v^3) with v = c_k(x) * S_peak * cal * S(f_deg) / S(peak)",
                          "use": "h_seen = G(sigma_K) + sum_k g_k * band_k, per fragment; the X_ITE shader and the LOD "
                                 "textures use the same formula", "tag": "inferred"},
        "files": ["data/visibility_vs_distance.csv"],
        "synthetic_input": "maps/synthetic/h_16bit.png",
    }
    print("perception: predicted d50 %.2f m, calibration factor %.3f" % (d_pred or -1, cal))

    # LOD textures: what an observer would see at a few distances (same model, per pixel)
    lod_d = [0.5, 1.0, 1.4, 1.8, 2.5, 4.0, 8.0]
    M = os.path.join(pkg, "maps", "synthetic", "lod")
    lod_files = []
    for d in lod_d:
        s_abs = s_peak * cal * L.csf_mannos_sakrison(L.angular_frequency(np.array(f_m), d)) / s_max
        seen = stack[-1].copy()
        for k, (b, l) in enumerate(zip(bands, low)):
            v = np.abs(a * b) / (1.0 - a * l) * s_abs[k]
            seen += L.soft_threshold(v) * b
        alb = lut[0][None, None, :] + np.clip(seen, 0, 1)[..., None] * (lut[-1] - lut[0])[None, None, :]
        alb = alb.reshape(alb.shape[0] // 2, 2, alb.shape[1] // 2, 2, 3).mean(axis=(1, 3))
        name = "perceived_%04.1fm_srgb.png" % d
        L.write_png(os.path.join(M, name), L.to_u8(L.srgb_encode(alb[::-1])))
        hs = np.clip(seen, 0, 1).reshape(seen.shape[0] // 2, 2, seen.shape[1] // 2, 2).mean(axis=(1, 3))
        hname = "h_seen_%04.1fm.png" % d                  # the same, before the colour lookup: any illuminant, any LUT
        L.write_png(os.path.join(M, hname), L.to_u8(hs[::-1]),
                    {"Description": "h as perceived at %g m (perception.json renderer_gain), 2x downsampled, linear 0..1" % d})
        lod_files.append({"distance_m": d, "file": "maps/synthetic/lod/" + name, "h_seen": "maps/synthetic/lod/" + hname})
    model["lod_textures"] = {"tag": "inferred", "levels": lod_files,
                             "note": "Perceived albedo (D65) at each distance, 2x downsampled, for X3D LOD nodes; and h_seen, the "
                                     "perceived h before the colour lookup, for renderers that apply the LUT themselves (Blender)."}
    L.write_json(os.path.join(D, "perception.json"), model)
    return {"cal": cal, "s_peak": s_peak, "s_max": s_max, "f_m": f_m, "sig_m": sig_m, "a": a, "d_pred": d_pred,
            "lod": lod_files}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pkg", default=L.PKG)
    ap.add_argument("--res", type=int, default=1024, help="map width in texels (height is 4x)")
    ap.add_argument("--h", default=None, help="16-bit h PNG to use instead of the synthetic field")
    args = ap.parse_args()
    C = L.load_constants(args.pkg)
    sp = spectral(args.pkg, C)
    wv = weave(args.pkg, C)
    dimensions(args.pkg, C, args.res)
    mp = synthetic_maps(args.pkg, C, args.res, sp, args.h)
    height_model(args.pkg, C, mp)
    pc = perception(args.pkg, C, sp, mp)
    L.write_json(os.path.join(args.pkg, "data", "derive_report.json"), {
        "checks": CHECKS, "all_ok": all(c["ok"] for c in CHECKS), "weave_tile_m": wv["tile_m"],
        "synthetic_statistics": mp["stats"], "perception": {"d50_predicted_m": pc["d_pred"], "calibration": pc["cal"]}})
    if not all(c["ok"] for c in CHECKS):
        sys.exit("derive: a check failed (see data/derive_report.json)")
    print("derive: all checks passed")


if __name__ == "__main__":
    main()
