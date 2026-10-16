"""Shared helpers for the Shroud knowledge-base tools.

The constants registry (data/constants.json), file writers that keep data textures linear (no gamma chunks), the
JJE 1984 spectral model and its illuminant LUT, the herringbone weave rule, and the perceptual dissolve model.
Needs numpy and scipy; the LUT bake also needs colour-science, EXR output needs the OpenEXR module.
"""
import json
import os
import struct
import zlib

import numpy as np
from scipy import ndimage

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------- registry
def load_constants(pkg=PKG):
    with open(os.path.join(pkg, "data", "constants.json"), encoding="utf-8") as f:
        return {c["id"]: c for c in json.load(f)["constants"]}


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def ref(C, cid):
    """A short provenance record for a constant: id, value, unit, tag, citations."""
    c = C[cid]
    return {"id": cid, "value": c["value"], "unit": c["unit"], "tag": c["tag"], "citations": c["citations"]}


# ---------------------------------------------------------------- writers
def write_png(path, arr, text=None):
    """PNG writer for uint8 or uint16 arrays shaped (H, W), (H, W, 3) or (H, W, 4). Row 0 is the top of the image.
    Writes no gAMA, sRGB or iCCP chunk, so browsers and WebGL upload the stored values unchanged."""
    arr = np.ascontiguousarray(arr)
    if arr.dtype not in (np.uint8, np.uint16):
        raise TypeError("write_png needs uint8 or uint16")
    bits = 8 if arr.dtype == np.uint8 else 16
    if arr.ndim == 2:
        arr = arr[:, :, None]
    h, w, n = arr.shape
    ctype = {1: 0, 3: 2, 4: 6}[n]
    raw = arr.astype(">u2" if bits == 16 else "u1").reshape(h, -1).view(np.uint8)
    up = np.empty_like(raw)                          # filter type 2 (Up) on every row: compresses smooth data well
    up[0] = raw[0]
    up[1:] = raw[1:] - raw[:-1]
    data = np.concatenate([np.full((h, 1), 2, np.uint8), up], axis=1).tobytes()

    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    out = [b"\x89PNG\r\n\x1a\n", chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, bits, ctype, 0, 0, 0))]
    for k, v in (text or {}).items():
        out.append(chunk(b"tEXt", k.encode("latin-1") + b"\x00" + v.encode("latin-1", "replace")))
    out += [chunk(b"IDAT", zlib.compress(data, 9)), chunk(b"IEND", b"")]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"".join(out))


def write_exr(path, arr):
    """OpenEXR, ZIP compressed, float32 (or half when given float16): (H, W) as Y, (H, W, 3) as RGB. Row 0 is the top."""
    import OpenEXR
    arr = np.ascontiguousarray(arr, dtype=np.float16 if np.asarray(arr).dtype == np.float16 else np.float32)
    ch = {"Y": arr} if arr.ndim == 2 else {"RGB": arr}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with OpenEXR.File({"compression": OpenEXR.ZIP_COMPRESSION, "type": OpenEXR.scanlineimage}, ch) as f:
        f.write(path)


def to_u16(x):
    return np.round(np.clip(x, 0.0, 1.0) * 65535.0).astype(np.uint16)


def to_u8(x):
    return np.round(np.clip(x, 0.0, 1.0) * 255.0).astype(np.uint8)


def srgb_encode(lin):
    lin = np.clip(lin, 0.0, 1.0)
    return np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * np.power(lin, 1 / 2.4) - 0.055)


REC709_Y = np.array([0.2126, 0.7152, 0.0722])


# ---------------------------------------------------------------- JJE 1984 spectral model
def jje_params(C):
    return dict(a=C["jje.a"]["value"], b=C["jje.b"]["value"], c=C["jje.c"]["value"],
                lambda_prime=C["jje.lambda_prime_nm"]["value"], valid=tuple(C["jje.validity_nm"]["value"]))


def jje_reflectance(lam_nm, h, p):
    """r(lambda, h) = (a + b*lambda) * [1 + c*(lambda - lambda')*h]; lambda held at the edges of the fitted range."""
    lam = np.clip(lam_nm, *p["valid"])
    return (p["a"] + p["b"] * lam) * (1.0 + p["c"] * (lam - p["lambda_prime"]) * h)


# Rows of the LUT, in the order of the v3 baker (unity/v3-collateral/bake_shroud_spectral_lut.py).
ILLUMINANTS = [
    ("D65_daylight", "CIE D65", None, "standard", "CIE standard daylight"),
    ("A_tungsten_2856K", "CIE A", None, "standard", "CIE standard tungsten"),
    ("candle_1850K", "blackbody", 1850, "aesthetic", "candle, as a 1850 K blackbody"),
    ("oil_lamp_2000K", "blackbody", 2000, "aesthetic", "oil lamp, as a 2000 K blackbody"),
    ("halogen_3200K", "blackbody", 3200, "aesthetic", "halogen, as a 3200 K blackbody"),
    ("strobe_5500K", "blackbody", 5500, "aesthetic", "STURP 1978 flash, approximated by a 5500 K blackbody"),
    ("led_museum_4000K", "blackbody", 4000, "aesthetic", "museum LED, approximated by a 4000 K blackbody"),
]


def bake_lut(p, n=256):
    """Linear sRGB albedo (D65-adapted) for h = 0..1 under each illuminant, exactly as the v3 baker computes it:
    CIE 1931 2 degree observer, 380-780 nm in 5 nm steps, CAT02 adaptation of the illuminant white to D65."""
    import colour
    from colour import MSDS_CMFS, SDS_ILLUMINANTS, SpectralDistribution, SpectralShape, sd_blackbody, sd_to_XYZ
    shape = SpectralShape(380, 780, 5)
    lam = shape.wavelengths
    cmfs = MSDS_CMFS["CIE 1931 2 Degree Standard Observer"].copy().align(shape)
    flat = SpectralDistribution(dict(zip(lam, np.ones_like(lam))))
    hs = np.linspace(0.0, 1.0, n)
    lut = np.zeros((len(ILLUMINANTS), n, 3), np.float64)
    info = []
    for row, (name, kind, cct, tag, label) in enumerate(ILLUMINANTS):
        illum = (SDS_ILLUMINANTS[kind.split()[1]].copy().align(shape) if kind.startswith("CIE")
                 else sd_blackbody(cct, shape))
        white_XYZ = sd_to_XYZ(flat, cmfs, illum) / 100.0
        white_xy = colour.XYZ_to_xy(white_XYZ)
        for col, h in enumerate(hs):
            sd = SpectralDistribution(dict(zip(lam, jje_reflectance(lam, float(h), p))))
            XYZ = sd_to_XYZ(sd, cmfs, illum) / 100.0
            lut[row, col] = np.clip(colour.XYZ_to_sRGB(XYZ, illuminant=white_xy, apply_cctf_encoding=False), 0, 1)
        info.append({"name": name, "kind": kind, "cct_K": cct, "tag": tag, "label": label,
                     "white_xy": [round(float(v), 5) for v in white_xy]})
    return hs, lut, info, lam


# ---------------------------------------------------------------- herringbone weave
def herringbone_phase(i, repeat):
    """Twill phase of warp thread i in a pointed herringbone of `repeat` = (threads one way, threads back)."""
    period = repeat[0] + repeat[1]
    p = np.mod(i, period)
    return np.where(p < repeat[0], p, period - p)


def weft_on_top(i, j, repeat, float_len=4):
    """True where the weft crosses over warp thread i at weft pick j: a 3/1 twill (warp over three, under one)."""
    return np.mod(herringbone_phase(i, repeat) + j, float_len) == 0


def weave_tile(warp_per_m, weft_per_m, repeat, n_weft, texels_per_thread, yarn_d_m, cover=0.9):
    """Height field (metres) of one seamless weave tile, indexed [t, s] with t along the length (weft count) and
    s across the width (warp count), t increasing upward as in X3D texture space. Threads have elliptical sections
    of `cover` times their pitch; a thread passing over sits a full yarn height up, under it 0.45 of it.
    A power-of-two number of texels per thread keeps every mip level an exact average over whole threads and whole
    twill repeats, so the weave fades to flat with distance instead of beating into moire."""
    n_warp = repeat[0] + repeat[1]
    px_s, px_t = n_warp * texels_per_thread, n_weft * texels_per_thread
    ts, ss = np.meshgrid((np.arange(px_t) + 0.5) / px_t, (np.arange(px_s) + 0.5) / px_s, indexing="ij")
    a, b = ss * n_warp, ts * n_weft                      # continuous warp and weft coordinates in threads
    i, j = np.floor(a).astype(int), np.floor(b).astype(int)
    fa, fb = a - i, b - j

    def profile(f):
        return np.sqrt(np.clip(1.0 - ((f - 0.5) / (cover / 2)) ** 2, 0.0, 1.0)) ** 0.7

    def blend(lo, hi, t):
        s = (1.0 - np.cos(np.pi * t)) / 2.0
        return lo * (1 - s) + hi * s

    # warp i runs along t: its level changes between crossing centres j + 0.5
    jb = np.floor(b - 0.5).astype(int)
    tb = b - 0.5 - jb
    lw = blend((~weft_on_top(i, jb, repeat)).astype(float), (~weft_on_top(i, jb + 1, repeat)).astype(float), tb)
    # weft j runs along s: its level changes between crossing centres i + 0.5
    ia = np.floor(a - 0.5).astype(int)
    ta = a - 0.5 - ia
    lf = blend(weft_on_top(ia, j, repeat).astype(float), weft_on_top(ia + 1, j, repeat).astype(float), ta)
    hw = (0.45 + 0.55 * lw) * profile(fa)
    hf = (0.45 + 0.55 * lf) * profile(fb)
    height = np.maximum(hw, hf) * yarn_d_m
    top_is_warp = hw >= hf
    size = (n_warp / warp_per_m, n_weft / weft_per_m)     # metres (s, t)
    return height, top_is_warp, size


def normal_map(height, size_s, size_t, max_slope=2.5):
    """Tangent-space normals (x along +s, y along +t, z out), OpenGL convention, from a seamless height tile [t, s],
    in slope space: (-dh/ds, -dh/dt, 1) / max_slope, slopes clipped at max_slope. Every renderer normalizes the
    sampled vector, so the direction is exact; and because mipmaps then average slopes rather than unit normals,
    a whole twill repeat averages to flat, as the real cloth does, instead of tilting band by band into stripes."""
    ds, dt = size_s / height.shape[1], size_t / height.shape[0]
    gs = np.clip((np.roll(height, -1, 1) - np.roll(height, 1, 1)) / (2 * ds), -max_slope, max_slope)
    gt = np.clip((np.roll(height, -1, 0) - np.roll(height, 1, 0)) / (2 * dt), -max_slope, max_slope)
    return np.stack([-gs, -gt, np.ones_like(height)], -1) / max_slope


# ---------------------------------------------------------------- perception
def csf_mannos_sakrison(f_cpd):
    """Mannos and Sakrison (1974) contrast sensitivity, relative (peak about 1 near 8 cycles per degree)."""
    f = np.asarray(f_cpd, dtype=float)
    return 2.6 * (0.0192 + 0.114 * f) * np.exp(-np.power(0.114 * f, 1.1))


CSF_PEAK_CPD = 8.0


def csf_peak_value():
    f = np.linspace(1, 20, 20001)
    s = csf_mannos_sakrison(f)
    return float(f[np.argmax(s)]), float(s.max())


def gaussian_stack(img, sigmas_px):
    """Low-pass images at each sigma (pixels); the first entry is the image itself (sigma 0). Large sigmas are
    filtered on a block-averaged copy and interpolated back, which keeps the cost flat."""
    out = [img]
    for s in sigmas_px:
        f = int(2 ** max(0, int(np.floor(np.log2(s / 2.0)))))
        if f == 1:
            out.append(ndimage.gaussian_filter(img, s, mode="nearest"))
            continue
        hh, ww = (img.shape[0] // f) * f, (img.shape[1] // f) * f
        small = img[:hh, :ww].reshape(hh // f, f, ww // f, f).mean(axis=(1, 3))
        small = ndimage.gaussian_filter(small, np.sqrt(max(s * s - (f * f - 1) / 12.0, 0.25)) / f, mode="nearest")
        rows = (np.arange(img.shape[0]) + 0.5) / f - 0.5
        cols = (np.arange(img.shape[1]) + 0.5) / f - 0.5
        R, Cc = np.meshgrid(rows, cols, indexing="ij")
        out.append(ndimage.map_coordinates(small, [R, Cc], order=1, mode="nearest").astype(img.dtype))
    return out


def dog_peak_frequency(s1, s2):
    """Peak spatial frequency (cycles per unit) of the difference of Gaussians with sigmas s1 < s2 (same unit)."""
    if s1 == 0:
        s1 = 0.5 * s2 / np.sqrt(3)       # an unblurred image acts like a narrow Gaussian at half a pixel
    return float(np.sqrt(np.log((s2 * s2) / (s1 * s1)) / (2 * np.pi ** 2 * (s2 * s2 - s1 * s1))))


def angular_frequency(f_cycles_per_m, distance_m):
    """Cycles per degree of a pattern of f cycles per metre seen face-on from `distance_m` metres."""
    return f_cycles_per_m * distance_m * np.pi / 180.0


def soft_threshold(v, n=3.0):
    """Fraction of a band's contrast an observer sees, from its visibility v (1 = threshold): v^n / (1 + v^n)."""
    vn = np.power(np.maximum(v, 0.0), n)
    return vn / (1.0 + vn)
