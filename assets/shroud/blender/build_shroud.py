#!/usr/bin/env python3
"""Build the Shroud of Turin in Blender from this package's data, and render test frames.

  blender -b -P blender/build_shroud.py -- --render renders/blender
  python3 blender/build_shroud.py --render renders/blender        # with the bpy module (pip install bpy)

Or open this file in Blender's Text Editor and press Run Script: it builds the scenes and renders nothing.
Tested with Blender 5.2 (the bpy module); it uses no API newer than Blender 4.2.

Options (after "--" when Blender runs the script)
  --pkg PATH              package root, the folder holding data/ and maps/ (default: this script's parent folder)
  --weave procedural|maps procedural 3/1 herringbone from the thread counts (default), or the baked weave maps
  --illuminant NAME       a row of data/spectral/shroud_spectral_lut.json (default D65_daylight)
  --contrast K            display contrast around the bare linen; 1 is the physical image (default 1)
  --relief-exaggeration E height scale of the relief scene (default: constant distance.relief_exaggeration_default)
  --render DIR            render the test frames into DIR
  --samples N             Cycles samples per pixel (default 48)
  --size WxH              render size (default 960x540)
  --format png|jpeg       file format of the frames (default png; jpeg at quality 90)
  --animation             also render the walk-up toward the face (240 frames) into DIR/walk/
  --save FILE.blend       save the scenes
  --export-x3d FILE.x3d   export the cloth as X3D 4.0 through blender/x3d_io.py

What it builds (Blender is Z up; the X3D scenes are Y up and blender/x3d_io.py converts between them)
  scene "Shroud"         the cloth hanging flat at eye height, dorsal image left, frontal image right, heads meeting in
                         the middle, as in the usual horizontal display; a dark wall behind it; seven cameras
  scene "Shroud relief"  the same field displaced by h, the 1976 VP-8 reading, under a grazing light

The material "Shroud linen (JJE 1984)" is driven by data, not painted:
  colour       the JJE 1984 reflectance model r(lambda, h) = (a + b lambda)[1 + c (lambda - lambda') h], baked per
               illuminant into data/spectral/shroud_spectral_lut_16bit.png and looked up by h
  dissolve     h as an observer would perceive it at the camera's distance (data/perception.json, inferred,
               calibrated to the 1.8 m of JJE 1984), interpolated between the seven maps in maps/synthetic/lod
  weave        3/1 herringbone from Vial's 38.3 warp and 25.4 weft per cm, bands about 40 warps wide, lengthwise
The body image is the package's synthetic stand-in (maps/synthetic), not the Shroud's measured image. Replace
maps/synthetic/h_16bit.png (and rerun tools/derive.py --h) when a licensed, registered photograph is available.
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

HANG_Z = 1.6            # height of the cloth's centre line, metres (eye level; display choice)
FACE_BELOW_HEAD = 0.12  # the synthetic face centre lies this far along the cloth from the top of the head (make_x3d.py)


# ---------------------------------------------------------------- arguments and data
def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    elif argv and argv[0].endswith(".py"):          # python3 build_shroud.py ... (the bpy module)
        argv = argv[1:]
    else:                                           # Blender's Text Editor
        argv = []
    ap = argparse.ArgumentParser(prog="build_shroud.py", description=__doc__.split("\n")[0])
    ap.add_argument("--pkg")
    ap.add_argument("--weave", choices=["procedural", "maps"], default="procedural")
    ap.add_argument("--illuminant", default="D65_daylight")
    ap.add_argument("--contrast", type=float, default=1.0)
    ap.add_argument("--relief-exaggeration", type=float)
    ap.add_argument("--render")
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--size", default="960x540")
    ap.add_argument("--format", choices=["png", "jpeg"], default="png")
    ap.add_argument("--animation", action="store_true")
    ap.add_argument("--save")
    ap.add_argument("--export-x3d")
    return ap.parse_args(argv)


def find_pkg(given):
    here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else ""
    for cand in [given, os.environ.get("SHROUD_PKG"), os.path.dirname(here), bpy.path.abspath("//"), os.getcwd()]:
        if cand and os.path.isfile(os.path.join(cand, "data", "constants.json")):
            return os.path.abspath(cand)
    raise SystemExit("Package not found: pass --pkg PATH (the folder that holds data/ and maps/) or set SHROUD_PKG.")


class Data:
    """Everything the scenes need, read from the package; nothing measured is typed into this script."""

    def __init__(self, pkg):
        self.pkg = pkg
        J = lambda *p: json.load(open(os.path.join(pkg, *p), encoding="utf-8"))
        self.constants = {c["id"]: c for c in J("data", "constants.json")["constants"]}
        dims = J("data", "dimensions.json")
        self.state = dims["restoration_default"]["value"]
        self.W = dims["states"][self.state]["width_m"]
        self.L = dims["states"][self.state]["length_m"]
        self.weave = J("data", "weave.json")
        self.lut = J("data", "spectral", "shroud_spectral_lut.json")
        self.perception = J("data", "perception.json")
        lay = J("data", "height_model.json")["synthetic_forward_model"]["layout"]
        self.face_v = lay["fold_v"] * self.L + lay["head_gap"] + FACE_BELOW_HEAD
        self.lod = self.perception["lod_textures"]["levels"]

    def value(self, cid):
        return self.constants[cid]["value"]

    def path(self, rel):
        p = os.path.join(self.pkg, rel)
        if not os.path.isfile(p):
            raise SystemExit("Missing %s: run tools/derive.py first." % rel)
        return p

    def provenance(self):
        ids = ["cloth.length_pre2002_m", "cloth.width_pre2002_m", "weave.warp_per_cm", "weave.weft_per_cm",
               "perception.min_distance_m", "distance.frontal_range_m", "distance.relief_exaggeration_default"]
        return {i: {k: self.constants[i][k] for k in ("value", "unit", "tag", "citations")} for i in ids if i in self.constants}


# ---------------------------------------------------------------- node helpers
def node(nt, kind, label=None, loc=(0, 0), **props):
    n = nt.nodes.new(kind)
    n.location = loc
    if label:
        n.label = n.name = label
    for k, v in props.items():
        setattr(n, k, v)
    return n


def math_node(nt, op, a=None, b=None, c=None, loc=(0, 0), clamp=False, label=None):
    n = node(nt, "ShaderNodeMath", label, loc, operation=op, use_clamp=clamp)
    for i, v in enumerate((a, b, c)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def mix_float(nt, a, b, fac, loc=(0, 0), label=None):
    n = node(nt, "ShaderNodeMix", label, loc, data_type="FLOAT", clamp_factor=True)
    by_id = {sock.identifier: sock for sock in n.inputs}          # names repeat across data types; identifiers do not
    for sock, v in (("Factor_Float", fac), ("A_Float", a), ("B_Float", b)):
        if isinstance(v, (int, float)):
            by_id[sock].default_value = v
        else:
            nt.links.new(v, by_id[sock])
    return next(o for o in n.outputs if o.identifier == "Result_Float")


def value_node(nt, label, v, loc):
    n = node(nt, "ShaderNodeValue", label, loc)
    n.outputs[0].default_value = v
    return n


def image(path, colorspace="Non-Color"):
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = colorspace
    return img


def tex(nt, img, vector, loc, interpolation="Linear", extension="EXTEND", label=None):
    n = node(nt, "ShaderNodeTexImage", label, loc, image=img, interpolation=interpolation, extension=extension)
    if vector is not None:
        nt.links.new(vector, n.inputs["Vector"])
    return n


def new_material(name):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    if bpy.app.version < (5, 0, 0):
        mat.use_nodes = True                     # always on from Blender 5
    mat.node_tree.nodes.clear()
    return mat


# ---------------------------------------------------------------- the weave
def herringbone_group(d):
    """3/1 herringbone twill as a shader node group: Height (0..1) and Warp on top, from UV and the thread counts.

    Warp threads run along the length (t) and are counted across the width: index i = floor(u * warp_per_m).
    Weft threads run across and are counted along the length: j = floor(v * weft_per_m).
    A 3/1 twill floats each warp over three wefts and under one, stepping one weft per warp; the herringbone
    reverses that step every band of about 40 warps (Vial 1989 counts bands of 41 and 39), so the bands run lengthwise.
    """
    name = "Herringbone 3/1 (Vial 1989)"
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    g = bpy.data.node_groups.new(name, "ShaderNodeTree")
    io = g.interface
    sockets = [("UV", "NodeSocketVector", None), ("Width m", "NodeSocketFloat", d.W), ("Length m", "NodeSocketFloat", d.L),
               ("Warp per m", "NodeSocketFloat", d.weave["warp_per_m"]), ("Weft per m", "NodeSocketFloat", d.weave["weft_per_m"]),
               ("Band warps", "NodeSocketFloat", sum(d.weave["band_repeat_threads"]["value"]) / 2.0),
               ("Slubs", "NodeSocketFloat", 0.3)]
    for nm, kind, dv in sockets:
        s = io.new_socket(nm, in_out="INPUT", socket_type=kind)
        if dv is not None:
            s.default_value = dv
    io.new_socket("Height", in_out="OUTPUT", socket_type="NodeSocketFloat")
    io.new_socket("Warp on top", in_out="OUTPUT", socket_type="NodeSocketFloat")
    gi = node(g, "NodeGroupInput", loc=(-1400, 0))
    go = node(g, "NodeGroupOutput", loc=(900, 0))
    sep = node(g, "ShaderNodeSeparateXYZ", loc=(-1200, 0))
    g.links.new(gi.outputs["UV"], sep.inputs[0])
    x = math_node(g, "MULTIPLY", math_node(g, "MULTIPLY", sep.outputs[0], gi.outputs["Width m"], loc=(-1000, 150)),
                  gi.outputs["Warp per m"], loc=(-850, 150), label="x (warps)")
    y = math_node(g, "MULTIPLY", math_node(g, "MULTIPLY", sep.outputs[1], gi.outputs["Length m"], loc=(-1000, -150)),
                  gi.outputs["Weft per m"], loc=(-850, -150), label="y (wefts)")
    i = math_node(g, "FLOOR", x, loc=(-650, 250), label="warp index i")
    j = math_node(g, "FLOOR", y, loc=(-650, -250), label="weft index j")
    fx = math_node(g, "FRACT", x, loc=(-650, 80))
    fy = math_node(g, "FRACT", y, loc=(-650, -80))
    band = math_node(g, "FLOOR", math_node(g, "DIVIDE", i, gi.outputs["Band warps"], loc=(-500, 350)), loc=(-350, 350))
    parity = math_node(g, "FLOORED_MODULO", band, 2.0, loc=(-200, 350), label="band parity")
    diag = math_node(g, "MULTIPLY_ADD", parity, math_node(g, "MULTIPLY", i, 2.0, loc=(-350, 200)),
                     math_node(g, "SUBTRACT", j, i, loc=(-350, 50)), loc=(-50, 250), label="j - i, or j + i in odd bands")
    phase = math_node(g, "FLOORED_MODULO", diag, 4.0, loc=(100, 250))
    up = math_node(g, "LESS_THAN", phase, 2.5, loc=(250, 250), label="warp on top (3 of 4)")
    yarn_w = math_node(g, "POWER", math_node(g, "SINE", math_node(g, "MULTIPLY", fx, math.pi, loc=(-450, 80)), loc=(-300, 80)),
                       0.6, loc=(-150, 80), label="warp yarn profile")
    yarn_f = math_node(g, "MULTIPLY", math_node(g, "POWER", math_node(g, "SINE", math_node(g, "MULTIPLY", fy, math.pi, loc=(-450, -80)),
                                                                      loc=(-300, -80)), 0.6, loc=(-150, -80)), 0.85, loc=(0, -80),
                       label="weft yarn profile")
    # slubs (aesthetic): each yarn thickens and thins slowly along its length, independently of its neighbours
    def slub(index, along, loc):
        v = node(g, "ShaderNodeCombineXYZ", loc=loc)
        g.links.new(math_node(g, "MULTIPLY", index, 0.731, loc=(loc[0] - 160, loc[1] + 40)), v.inputs[0])
        g.links.new(math_node(g, "MULTIPLY", along, 1.0 / 23.0, loc=(loc[0] - 160, loc[1] - 40)), v.inputs[1])
        n = node(g, "ShaderNodeTexNoise", loc=(loc[0] + 160, loc[1]))
        n.inputs["Scale"].default_value = 1.0
        n.inputs["Detail"].default_value = 1.0
        g.links.new(v.outputs[0], n.inputs["Vector"])
        return mix_float(g, 1.0, math_node(g, "MULTIPLY_ADD", n.outputs["Fac"], 1.4, 0.3, clamp=True, loc=(loc[0] + 320, loc[1])),
                         gi.outputs["Slubs"], loc=(loc[0] + 480, loc[1]))
    yarn_w = math_node(g, "MULTIPLY", yarn_w, slub(i, y, (-500, 600)), loc=(100, 80))
    yarn_f = math_node(g, "MULTIPLY", yarn_f, slub(j, x, (-500, -600)), loc=(100, -80))

    # each float dives where it passes under: a warp at the first (phase 0) and last (phase 2) weft of its float,
    # a weft at both sides of the one warp it crosses (phase 3)
    def ramp(f, loc):                                # 0 at the crossing, 1 from 0.45 of a pitch inward
        return math_node(g, "SINE", math_node(g, "MULTIPLY", math_node(g, "DIVIDE", f, 0.45, clamp=True, loc=loc),
                                              math.pi / 2, loc=(loc[0] + 120, loc[1])), loc=(loc[0] + 240, loc[1]))
    start = mix_float(g, 1.0, ramp(fy, (-200, -400)), math_node(g, "COMPARE", phase, 0.0, 0.5, loc=(150, -350)), loc=(350, -400))
    end = mix_float(g, 1.0, ramp(math_node(g, "SUBTRACT", 1.0, fy, loc=(-320, -520)), (-200, -520)),
                    math_node(g, "COMPARE", phase, 2.0, 0.5, loc=(150, -470)), loc=(350, -520))
    dive_w = math_node(g, "MULTIPLY_ADD", math_node(g, "MULTIPLY", start, end, loc=(500, -450)), 0.55, 0.45, loc=(650, -450))
    yarn_w = math_node(g, "MULTIPLY", yarn_w, dive_w, loc=(800, 80))
    dive_f = math_node(g, "MULTIPLY_ADD", math_node(g, "SINE", math_node(g, "MULTIPLY", fx, math.pi, loc=(500, -650)), loc=(650, -650)),
                       0.55, 0.45, loc=(800, -650))
    yarn_f = math_node(g, "MULTIPLY", yarn_f, dive_f, loc=(950, -80))
    height = math_node(g, "MULTIPLY_ADD", up, math_node(g, "SUBTRACT", yarn_w, yarn_f, loc=(250, 50)), yarn_f, loc=(500, 0))
    g.links.new(height, go.inputs["Height"])
    g.links.new(up, go.inputs["Warp on top"])
    return g


# ---------------------------------------------------------------- the linen material
def linen_material(d, a):
    """Principled linen whose base colour is the JJE LUT looked up by h (dissolved by view distance) and whose
    normal is the weave. Value nodes 'Illuminant', 'Display contrast', 'Dissolve' and 'Weave' are the controls."""
    mat = new_material("Shroud linen (JJE 1984)")
    nt = mat.node_tree
    out = node(nt, "ShaderNodeOutputMaterial", loc=(1900, 0))
    bsdf = node(nt, "ShaderNodeBsdfPrincipled", loc=(1550, 0))
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = 0.92
    bsdf.inputs["Specular IOR Level"].default_value = 0.3
    bsdf.inputs["Sheen Weight"].default_value = 0.2
    bsdf.inputs["Sheen Roughness"].default_value = 0.45

    rows = d.lut["rows"]
    if a.illuminant not in rows:
        raise SystemExit("Unknown illuminant %r; choose one of %s" % (a.illuminant, ", ".join(rows)))
    v_illum = value_node(nt, "Illuminant", float(rows.index(a.illuminant)), (-1500, 650))
    v_contrast = value_node(nt, "Display contrast", a.contrast, (-1500, 520))
    v_dissolve = value_node(nt, "Dissolve", 1.0, (-1500, 390))
    v_weave = value_node(nt, "Weave", 1.0, (-1500, 260))

    uv = node(nt, "ShaderNodeUVMap", loc=(-1700, 0))
    uv.uv_map = "UVMap"
    # h as recorded, and as perceived at the camera's distance
    h_raw = tex(nt, image(d.path("maps/synthetic/h_16bit.png")), uv.outputs["UV"], (-1300, 120), label="h")
    cam = node(nt, "ShaderNodeCameraData", loc=(-1500, -120))
    ld = math_node(nt, "LOGARITHM", cam.outputs["View Distance"], math.e, loc=(-1300, -120), label="ln distance")
    acc, prev = None, None
    for k, lv in enumerate(d.lod):
        t = tex(nt, image(d.path(lv["h_seen"])), uv.outputs["UV"], (-1100 + 160 * k, -320 - 40 * k),
                label="h seen at %g m" % lv["distance_m"])
        if acc is None:
            acc = t.outputs["Color"]
        else:                                        # piecewise linear in ln(distance) between neighbouring levels
            l0, l1 = math.log(prev), math.log(lv["distance_m"])
            f = math_node(nt, "MULTIPLY_ADD", ld, 1.0 / (l1 - l0), -l0 / (l1 - l0), clamp=True, loc=(-1000 + 160 * k, -120))
            acc = mix_float(nt, acc, t.outputs["Color"], f, loc=(-900 + 160 * k, -40))
        prev = lv["distance_m"]
    h = mix_float(nt, h_raw.outputs["Color"], acc, v_dissolve.outputs[0], loc=(100, 120), label="h used")

    # the JJE LUT: column = h, row = illuminant (row 0, the top of the PNG, is D65)
    lut_img = image(d.path("data/spectral/shroud_spectral_lut_16bit.png"))
    n_rows = len(rows)
    row_v = math_node(nt, "MULTIPLY_ADD", v_illum.outputs[0], -1.0 / n_rows, (n_rows - 0.5) / n_rows, loc=(250, 420))
    col_u = math_node(nt, "MULTIPLY_ADD", h, 255.0 / 256.0, 0.5 / 256.0, loc=(250, 160))
    xyz = node(nt, "ShaderNodeCombineXYZ", loc=(420, 200))
    nt.links.new(col_u, xyz.inputs[0])
    nt.links.new(row_v, xyz.inputs[1])
    xyz0 = node(nt, "ShaderNodeCombineXYZ", loc=(420, 380))
    xyz0.inputs[0].default_value = 0.5 / 256.0
    nt.links.new(row_v, xyz0.inputs[1])
    lut_h = tex(nt, lut_img, xyz.outputs[0], (600, 200), label="LUT at h")
    lut_0 = tex(nt, lut_img, xyz0.outputs[0], (600, 420), label="LUT at h = 0 (bare linen)")
    diff = node(nt, "ShaderNodeVectorMath", loc=(850, 300), operation="SUBTRACT")
    nt.links.new(lut_h.outputs["Color"], diff.inputs[0])
    nt.links.new(lut_0.outputs["Color"], diff.inputs[1])
    albedo = node(nt, "ShaderNodeVectorMath", "albedo", (1020, 300), operation="MULTIPLY_ADD")
    nt.links.new(diff.outputs[0], albedo.inputs[0])
    nt.links.new(v_contrast.outputs[0], albedo.inputs[1])
    nt.links.new(lut_0.outputs["Color"], albedo.inputs[2])

    # the weave: shading only (bump or normal map) plus a little darkening between yarns
    shade = node(nt, "ShaderNodeVectorMath", loc=(1250, 250), operation="SCALE")
    nt.links.new(albedo.outputs[0], shade.inputs[0])
    if a.weave == "procedural":
        hb = node(nt, "ShaderNodeGroup", "Herringbone", (300, -400))
        hb.node_tree = herringbone_group(d)
        nt.links.new(uv.outputs["UV"], hb.inputs["UV"])
        bump = node(nt, "ShaderNodeBump", loc=(1250, -300))
        bump.inputs["Distance"].default_value = d.value("weave.yarn_diameter_mm") / 2000.0   # yarn radius, metres
        nt.links.new(hb.outputs["Height"], bump.inputs["Height"])
        nt.links.new(v_weave.outputs[0], bump.inputs["Strength"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        occl = hb.outputs["Height"]
    else:
        rep_s, rep_t = d.W / d.weave["tile"]["size_m"][0], d.L / d.weave["tile"]["size_m"][1]   # 53.14 x 213.46
        mapping = node(nt, "ShaderNodeMapping", loc=(300, -400))
        mapping.inputs["Scale"].default_value = (rep_s, rep_t, 1.0)
        nt.links.new(uv.outputs["UV"], mapping.inputs["Vector"])
        nrm = tex(nt, image(d.path("maps/weave/weave_normal.png")), mapping.outputs[0], (550, -400), extension="REPEAT")
        occ = tex(nt, image(d.path("maps/weave/weave_occlusion.png")), mapping.outputs[0], (550, -650), extension="REPEAT")
        nmap = node(nt, "ShaderNodeNormalMap", loc=(1250, -300))
        nmap.uv_map = "UVMap"
        nt.links.new(nrm.outputs["Color"], nmap.inputs["Color"])
        nt.links.new(math_node(nt, "MULTIPLY", v_weave.outputs[0], 0.8, loc=(1050, -250)), nmap.inputs["Strength"])
        nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
        occl = occ.outputs["Color"]
    dark = mix_float(nt, 1.0, mix_float(nt, 0.88, 1.0, occl, loc=(1050, 80)), v_weave.outputs[0], loc=(1150, 120),
                     label="weave shading")
    nt.links.new(dark, shade.inputs["Scale"])
    nt.links.new(shade.outputs[0], bsdf.inputs["Base Color"])
    return mat


def plain_material(name, rgb, roughness, specular=0.5):
    mat = new_material(name)
    nt = mat.node_tree
    out = node(nt, "ShaderNodeOutputMaterial", loc=(300, 0))
    bsdf = node(nt, "ShaderNodeBsdfPrincipled", loc=(0, 0))
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Specular IOR Level"].default_value = specular
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return mat


# ---------------------------------------------------------------- geometry
def cloth_grid(name, d, cols, rows):
    """The cloth as a grid hanging in the XZ plane, facing -Y. u runs up (Z), v runs along X from the dorsal end.
    UV: s = u / width, t = v / length, the package convention (data/dimensions.json)."""
    import numpy as np
    me = bpy.data.meshes.new(name)
    s = np.linspace(0.0, 1.0, cols)
    t = np.linspace(0.0, 1.0, rows)
    S, T = np.meshgrid(s, t)                                     # rows along t, columns along s
    co = np.stack([T * d.L - d.L / 2, np.zeros_like(S), HANG_Z + S * d.W - d.W / 2], axis=-1).reshape(-1, 3)
    me.vertices.add(len(co))
    me.vertices.foreach_set("co", co.astype(np.float32).ravel())
    r, c = np.meshgrid(np.arange(rows - 1), np.arange(cols - 1), indexing="ij")
    v0 = (r * cols + c).ravel()
    quads = np.stack([v0, v0 + cols, v0 + cols + 1, v0 + 1], axis=1)   # winding gives a -Y normal
    me.loops.add(quads.size)
    me.polygons.add(len(quads))
    me.loops.foreach_set("vertex_index", quads.ravel().astype(np.int32))
    me.polygons.foreach_set("loop_start", np.arange(0, quads.size, 4, dtype=np.int32))
    uvl = me.uv_layers.new(name="UVMap")
    uv = np.stack([S.ravel(), T.ravel()], axis=1)[quads.ravel()]
    uvl.data.foreach_set("uv", uv.astype(np.float32).ravel())
    me.update(calc_edges=True)
    me.validate()
    return me


def add_object(scene, name, data, collection=None):
    ob = bpy.data.objects.new(name, data)
    (collection or scene.collection).objects.link(ob)
    return ob


def look(ob, target, up=(0, 0, 1)):
    """Point a camera (it looks along its local -Z, local +Y up) at a target, with the frame's top toward up."""
    back = (ob.location - Vector(target)).normalized()          # local +Z
    right = Vector(up).cross(back).normalized()                  # local +X
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = Matrix((right, back.cross(right), back)).transposed().to_quaternion()


def camera(scene, name, loc, target, lens_mm, clip_start=0.01, up=(0, 0, 1)):
    cam = bpy.data.cameras.new(name)
    cam.lens = lens_mm
    cam.sensor_width = 36.0
    cam.sensor_fit = "HORIZONTAL"
    cam.clip_start = clip_start
    cam.clip_end = 200.0
    ob = add_object(scene, name, cam)
    ob.location = loc
    look(ob, target, up)
    return ob


def sun(scene, name, strength, angle_deg=2.0):
    light = bpy.data.lights.new(name, "SUN")
    light.energy = strength                       # W/m2: strength pi shows a white Lambert surface at 1.0
    light.angle = math.radians(angle_deg)
    return add_object(scene, name, light)


def aim_light(ob, travel):
    """Orient a sun so its light travels along the given direction."""
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = Vector(travel).normalized().to_track_quat("-Z", "Y")


def world(scene, rgb, strength):
    w = bpy.data.worlds.new(scene.name + " world")
    if bpy.app.version < (5, 0, 0):
        w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (*rgb, 1.0)
    bg.inputs["Strength"].default_value = strength
    scene.world = w


def setup_render(scene, a):
    w, h = (int(x) for x in a.size.lower().split("x"))
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = a.samples
    scene.cycles.use_denoising = True
    try:
        scene.cycles.denoiser = "OPENIMAGEDENOISE"
    except TypeError:
        pass
    scene.cycles.max_bounces = 4
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "JPEG" if a.format == "jpeg" else "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.quality = 90
    scene.view_settings.view_transform = "Standard"     # the LUT is colorimetric: no filmic curve on top
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.unit_settings.system = "METRIC"


# ---------------------------------------------------------------- the scenes
def build_cloth_scene(d, a):
    scene = bpy.data.scenes.get("Shroud") or bpy.data.scenes.new("Shroud")
    scene["shroud_provenance"] = json.dumps(d.provenance())
    scene["shroud_note"] = "Body image: synthetic stand-in (maps/synthetic). Colours: JJE 1984 model. Dissolve: inferred."
    setup_render(scene, a)
    world(scene, (0.03, 0.032, 0.04), 1.0)
    col = bpy.data.collections.new("Shroud cloth")
    scene.collection.children.link(col)
    me = cloth_grid("Shroud", d, 2, 2)                  # flat: every detail lives in the material
    cloth = add_object(scene, "Shroud", me, col)
    cloth.data.materials.append(linen_material(d, a))
    cloth["restoration_state"] = d.state
    cloth["size_m"] = [d.L, d.W]
    wall = bpy.data.meshes.new("Wall")
    wall.from_pydata([(-9, 0.01, -1.5), (9, 0.01, -1.5), (9, 0.01, 5.5), (-9, 0.01, 5.5)], [], [(0, 1, 2, 3)])
    wall_ob = add_object(scene, "Wall", wall, col)
    wall_ob.data.materials.append(plain_material("Wall (dark)", (0.01, 0.011, 0.014), 0.95, specular=0.0))

    key = sun(scene, "Key", 3.4, 3.0)
    aim_light(key, (0.45, 0.8, -0.4))               # from the front, upper left
    fill = sun(scene, "Fill", 0.5, 10.0)
    aim_light(fill, (-0.6, 0.7, 0.2))
    fx = d.face_v - d.L / 2                          # the frontal face, on the right half
    face = (fx, 0.0, HANG_Z)
    head_up = (-1, 0, 0)                             # the frontal figure's head points to -X, toward the fold
    cams = {"whole_6m": camera(scene, "Cam_whole_6m", (0, -6.0, HANG_Z), (0, 0, HANG_Z), 45.0)}
    for dist in (6.0, 1.8, 1.0, 0.5):                # the same 0.36 m wide field at every distance: only the dissolve changes
        cams["face_%.1fm" % dist] = camera(scene, "Cam_face_%.1fm" % dist, (fx, -dist, HANG_Z), face, 100.0 * dist, up=head_up)
    cams["weave_6cm"] = camera(scene, "Cam_weave_6cm", (fx - 0.31, -0.06, HANG_Z + 0.33), (fx - 0.31, 0, HANG_Z + 0.33),
                               72.0, clip_start=0.002)  # a 3 cm field
    walk = camera(scene, "Cam_walk", (fx, -8.0, HANG_Z), face, 40.0)
    for f in range(0, 241, 10):                      # 8 m to 0.5 m, evenly in ln(distance)
        dist = 8.0 * (0.5 / 8.0) ** (f / 240.0)
        walk.location = (fx, -dist, HANG_Z)
        walk.keyframe_insert("location", frame=f + 1)
    scene.frame_start, scene.frame_end = 1, 241
    scene.camera = cams["whole_6m"]
    return scene, cams, cloth


def build_relief_scene(d, a):
    scene = bpy.data.scenes.get("Shroud relief") or bpy.data.scenes.new("Shroud relief")
    setup_render(scene, a)
    world(scene, (0.03, 0.03, 0.035), 1.0)
    exag = a.relief_exaggeration or d.value("distance.relief_exaggeration_default")
    rng = d.value("distance.frontal_range_m")
    me = cloth_grid("Shroud relief", d, 513, 2049)          # 2.2 mm spacing, the synthetic map's half resolution
    ob = add_object(scene, "Shroud relief", me)
    t = bpy.data.textures.new("h", type="IMAGE")
    t.image = image(d.path("maps/synthetic/h_16bit.png"))
    t.extension = "EXTEND"
    mod = ob.modifiers.new("h as height", "DISPLACE")
    mod.texture = t
    mod.texture_coords = "UV"
    mod.uv_layer = "UVMap"
    mod.direction = "NORMAL"                         # toward the viewer (-Y)
    mod.mid_level = 0.0
    mod.strength = rng * exag
    ob["relief_m_per_unit_h"] = rng * exag
    ob["relief_range_m"] = rng
    ob["relief_note"] = "height = %g m x h x %g (exaggeration, aesthetic); JJE 1984 linear fit, r2 = 0.60" % (rng, exag)
    for p in me.polygons:
        p.use_smooth = True
    ob.data.materials.append(plain_material("Plaster", (0.82, 0.8, 0.76), 0.75))
    wall = bpy.data.meshes.new("Relief wall")
    wall.from_pydata([(-9, 0.01, -1.5), (9, 0.01, -1.5), (9, 0.01, 5.5), (-9, 0.01, 5.5)], [], [(0, 1, 2, 3)])
    add_object(scene, "Relief wall", wall).data.materials.append(bpy.data.materials["Wall (dark)"])
    key = sun(scene, "Key", 3.6, 1.5)
    aim_light(key, (0.93, 0.32, -0.18))              # grazing, from the head end of the dorsal image
    fill = sun(scene, "Fill", 0.35, 10.0)
    aim_light(fill, (-0.3, 0.9, 0.3))
    fx = d.face_v - d.L / 2
    cams = {"relief_whole": camera(scene, "Cam_relief_whole", (-2.4, -4.4, HANG_Z - 1.0), (0.2, 0, HANG_Z), 38.0),
            "relief_face": camera(scene, "Cam_relief_face", (fx + 0.2, -1.15, HANG_Z + 0.3), (fx - 0.01, -0.01, HANG_Z),
                                  135.0, up=(-1, 0, 0))}
    scene.camera = cams["relief_whole"]
    return scene, cams


# ---------------------------------------------------------------- rendering
PORTRAIT = 0.8          # width / height of the face frames
SHOTS = [  # scene key, camera, display contrast, file stem, note, extras (portrait frame, key light travel, relief scale)
    ("cloth", "whole_6m", 1.0, "cloth_whole_6m_physical", "the whole cloth from 6 m, physical contrast", {}),
    ("cloth", "whole_6m", 3.0, "cloth_whole_6m_contrast3", "the same with display contrast x3", {}),
    ("cloth", "face_6.0m", 3.0, "face_6.0m_contrast3", "the face, a 0.36 m wide field, from 6 m", {"portrait": True}),
    ("cloth", "face_1.8m", 3.0, "face_1.8m_contrast3", "the same field from 1.8 m, the measured threshold", {"portrait": True}),
    ("cloth", "face_1.0m", 3.0, "face_1.0m_contrast3", "from 1.0 m", {"portrait": True}),
    ("cloth", "face_0.5m", 3.0, "face_0.5m_contrast3", "from 0.5 m", {"portrait": True}),
    ("cloth", "weave_6cm", 1.0, "weave_6cm", "3 cm of linen from 6 cm, grazing light", {"key": (0.5, 0.3, -0.81)}),
    ("relief", "relief_whole", None, "relief_whole", "h as height, exaggerated", {}),
    ("relief", "relief_face", None, "relief_face", "the face as relief at true scale (3.7 cm range)",
     {"relief_scale": 1.0, "key": (0.6, 0.55, -0.58), "portrait": True}),
]


def render_all(scenes, out, a):
    os.makedirs(out, exist_ok=True)
    mat = bpy.data.materials["Shroud linen (JJE 1984)"]
    contrast = mat.node_tree.nodes["Display contrast"].outputs[0]
    relief = bpy.data.objects["Shroud relief"].modifiers["h as height"]
    exag = relief.strength
    done = []
    ext = ".jpg" if a.format == "jpeg" else ".png"
    for key, cam, k, stem, note, extra in SHOTS:
        scene, cams = scenes[key]
        w, h = scene.render.resolution_x, scene.render.resolution_y
        keylight = scene.objects.get("Key")
        keep = keylight.rotation_quaternion.copy() if keylight else None
        if k is not None:
            contrast.default_value = k
        if extra.get("portrait"):
            scene.render.resolution_x = int(round(h * PORTRAIT))
        if extra.get("key") and keylight:
            aim_light(keylight, extra["key"])
        if extra.get("relief_scale"):
            relief.strength = bpy.data.objects["Shroud relief"]["relief_range_m"] * extra["relief_scale"]
        scene.camera = cams[cam]
        scene.render.filepath = os.path.join(out, stem + ext)
        bpy.ops.render.render(write_still=True, scene=scene.name)
        scene.render.resolution_x, scene.render.resolution_y = w, h
        if keylight:
            keylight.rotation_quaternion = keep
        relief.strength = exag
        done.append({"file": stem + ext, "scene": scene.name, "camera": cams[cam].name, "display_contrast": k, "note": note})
        print("rendered", stem)
    contrast.default_value = a.contrast
    if a.animation:
        scene, cams = scenes["cloth"]
        scene.camera = scene.objects["Cam_walk"]
        scene.render.filepath = os.path.join(out, "walk", "walk_")
        bpy.ops.render.render(animation=True, scene=scene.name)
    with open(os.path.join(out, "renders.json"), "w", encoding="utf-8") as f:
        json.dump({"generator": "blender/build_shroud.py", "blender": bpy.app.version_string, "samples": a.samples,
                   "size": a.size, "weave": a.weave, "illuminant": a.illuminant, "frames": done,
                   "note": "Body image: synthetic stand-in. Display contrast > 1 is a viewing aid, not the cloth."}, f, indent=1)


def main():
    a = parse_args()
    d = Data(find_pkg(a.pkg))
    print("package:", d.pkg, "| cloth %.3f x %.3f m (%s)" % (d.L, d.W, d.state))
    cloth_scene, cloth_cams, cloth = build_cloth_scene(d, a)
    relief_scene, relief_cams = build_relief_scene(d, a)
    for s in list(bpy.data.scenes):                  # drop the empty startup scene
        if s.name not in ("Shroud", "Shroud relief") and not s.objects:
            bpy.data.scenes.remove(s)
    if bpy.context.window:
        bpy.context.window.scene = cloth_scene
    if a.export_x3d:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import x3d_io
        x3d_io.export_cloth(cloth_scene, a.export_x3d, d)
    if a.render:
        render_all({"cloth": (cloth_scene, cloth_cams), "relief": (relief_scene, relief_cams)}, os.path.abspath(a.render), a)
    if a.save:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.save))


if __name__ == "__main__":
    main()
