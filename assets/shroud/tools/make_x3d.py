#!/usr/bin/env python3
"""Write the X3D 4.0 scenes of the package from its data (run tools/derive.py and tools/make_graph.py first).

    python3 tools/make_x3d.py

x3d/shroud_cloth.x3d      the cloth hung at true scale: PhysicalMaterial from the JJE linen values, the image as a
                          texture, the weave as a normal map at true thread counts, an LOD that dissolves the image
                          below 1.8 m, viewpoints from 5.5 m down to 0.3 m, and the constants as metadata.
x3d/shroud_lab.x3d        the spectral and perception laboratory: a GLSL ComposedShader (X_ITE) with a
                          PhysicalMaterial fallback. Seven illuminants or one wavelength, the dissolve per fragment.
x3d/shroud_relief.x3d     h as height, as the VP-8 showed it in 1976: the whole cloth and the face at 1.5 mm.
x3d/shroud_formation.x3d  the image-formation hypothesis: a mannequin, the cloth over it coloured by the image it
                          would form, and the same cloth laid flat.
x3d/shroud_timeline.x3d   the knowledge graph's dated nodes on a timeline, one lane per lineage.
x3d/scenes.json           what the viewer page needs: titles, viewpoints, the face position, which controls apply.

Units are metres. Scenes reference textures by relative URL (../maps/...), so keep the package layout.
"""
import json
import math
import os
import sys
from xml.sax.saxutils import escape

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shroudlib as L                 # noqa: E402

PKG = L.PKG
HANG = "0.57735 0.57735 0.57735 2.0944"     # cloth frame -> wall: local x (width) -> world y, y (height) -> z, z (length) -> x
UP_HEAD = (-1.0, 0.0, 0.0)                  # on the wall the frontal figure's head points to world -x


def q(s):
    """An XML attribute value in single quotes."""
    return "'" + escape(str(s), {"'": "&apos;", '"': "&quot;"}) + "'"


def mfstring(items):
    return " ".join('"%s"' % str(x).replace("\\", "\\\\").replace('"', '\\"') for x in items)


def nums(a, fmt="%.4g"):
    out = []
    for x in np.ravel(a):
        s = fmt % x
        if "." in s and "e" not in s:
            s = s.rstrip("0").rstrip(".")
        out.append("0" if s in ("-0", "") else s)
    return " ".join(out)


def look(eye, target, up=(0.0, 1.0, 0.0)):
    """Viewpoint orientation (axis and angle) for a camera at eye looking at target, with up as screen-up."""
    from scipy.spatial.transform import Rotation
    e, t, u = (np.asarray(x, dtype=float) for x in (eye, target, up))
    f = (t - e) / np.linalg.norm(t - e)
    r = np.cross(f, u)
    r /= np.linalg.norm(r)
    rv = Rotation.from_matrix(np.column_stack([r, np.cross(r, f), -f])).as_rotvec()
    a = float(np.linalg.norm(rv))
    if a < 1e-9:
        return "0 0 1 0"
    return "%.5f %.5f %.5f %.5f" % (rv[0] / a, rv[1] / a, rv[2] / a, a)


def viewpoints(rows, sink, face=None):
    """rows: (DEF, chip label, description, eye, target, up, fieldOfView). Records each in sink for scenes.json."""
    out = []
    for d, label, text, e, t, up, fov in rows:
        out.append("  <Viewpoint DEF=%s description=%s position=%s orientation=%s centerOfRotation=%s fieldOfView='%.4f'/>" % (
            q(d), q(text), q(nums(e, "%.4f")), q(look(e, t, up)), q(nums(t, "%.4f")), fov))
        rec = {"def": d, "label": label, "description": text}
        if face is not None:
            rec["distance_to_face_m"] = round(float(np.linalg.norm(np.subtract(e, face))), 3)
        sink.append(rec)
    return "\n".join(out)


def doc(title, desc, body, components, profile="Interchange"):
    comps = "\n".join("  <component name=%s level='%d'/>" % (q(n), l) for n, l in components)
    return """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE X3D PUBLIC "ISO//Web3D//DTD X3D 4.0//EN" "https://www.web3d.org/specifications/x3d-4.0.dtd">
<X3D profile=%s version='4.0' xmlns:xsd='http://www.w3.org/2001/XMLSchema-instance' xsd:noNamespaceSchemaLocation='https://www.web3d.org/specifications/x3d-4.0.xsd'>
 <head>
%s
  <meta name='title' content=%s/>
  <meta name='description' content=%s/>
  <meta name='created' content='2026-10-16'/>
  <meta name='creator' content='Shroud of Turin knowledge base, x3d.poc'/>
  <meta name='generator' content='tools/make_x3d.py'/>
  <meta name='reference' content='data/constants.json'/>
  <meta name='license' content='Data and scenes: CC BY 4.0. The body image is synthetic (tools/synthetic_body.py).'/>
  <meta name='warning' content='The body image in this scene is a synthetic forward model, not a photograph or a reconstruction of the man of the Shroud.'/>
 </head>
 <Scene>
%s
 </Scene>
</X3D>
""" % (q(profile), comps, q(title), q(desc), body)


def metadata(C):
    """Registry constants flagged x3d, as a MetadataSet on WorldInfo: name = id with _ for ., reference = id, tag, citations, unit, label."""
    rows = []
    for cid, c in C.items():
        if not c.get("x3d"):
            continue
        ref = "id: %s; tag: %s; cite: %s; unit: %s; %s" % (cid, c["tag"], ", ".join(c["citations"]) or "none", c["unit"] or "-", c["label"])
        name = cid.replace(".", "_")                             # dots would clash with ClassicVRML ROUTE syntax
        v = c["value"]
        vals = v if isinstance(v, list) else [v]
        if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in vals):
            rows.append("     <MetadataDouble containerField='value' name=%s reference=%s value=%s/>" % (q(name), q(ref), q(nums(vals, "%.6g"))))
        else:
            rows.append("     <MetadataString containerField='value' name=%s reference=%s value=%s/>" % (q(name), q(ref), q(mfstring(vals))))
    return """    <MetadataSet containerField='metadata' name='shroud' reference='data/constants.json'>
     <MetadataString containerField='value' name='package' value='"Shroud of Turin knowledge base 1.0.0"'/>
     <MetadataString containerField='value' name='image_source' value='"synthetic forward model (tools/synthetic_body.py), aesthetic stand-in"'/>
%s
    </MetadataSet>""" % "\n".join(rows)


def world_info(C, title, info):
    return "  <WorldInfo title=%s info=%s>\n%s\n  </WorldInfo>" % (q(title), q(mfstring(info)), metadata(C))


def tex(url, field=None, DEF=None, repeat=True, aniso=8):
    a = "<ImageTexture"
    if DEF:
        a += " DEF=%s" % q(DEF)
    if field:
        a += " containerField=%s" % q(field)
    a += " url=%s" % q(mfstring([url]))
    if not repeat:
        a += " repeatS='false' repeatT='false'"
    mode = "REPEAT" if repeat else "CLAMP_TO_EDGE"
    return a + ("><TextureProperties generateMipMaps='true' minificationFilter='AVG_PIXEL_AVG_MIPMAP' magnificationFilter='AVG_PIXEL' "
                "anisotropicDegree='%d' boundaryModeS='%s' boundaryModeT='%s'/></ImageTexture>" % (aniso, mode, mode))


def read_png16(path):
    from PIL import Image
    return np.asarray(Image.open(path)).astype(np.float64)[::-1] / 65535.0    # rows now run with v upward


def read_exr(path):
    import OpenEXR
    with OpenEXR.File(path) as f:
        return np.asarray(f.channels()["Y"].pixels, dtype=np.float64)[::-1]


def sample(a, W, Lc, ua, ub, va, vb, rows, cols, blur=True):
    """Bilinear samples of a cell-centred [v, u] map at a rows x cols vertex grid spanning u in [ua, ub], v in [va, vb]."""
    from scipy import ndimage
    nv, nu = a.shape
    if blur:
        sv = max(0.0, (vb - va) / max(rows - 1, 1) / (Lc / nv) / 2.5)
        su = max(0.0, (ub - ua) / max(cols - 1, 1) / (W / nu) / 2.5)
        if sv > 0.5 or su > 0.5:
            a = ndimage.gaussian_filter(a, (sv, su))
    v = np.linspace(va, vb, rows) * nv / Lc - 0.5
    u = np.linspace(ua, ub, cols) * nu / W - 0.5
    V, U = np.meshgrid(v, u, indexing="ij")
    return ndimage.map_coordinates(a, [V, U], order=1, mode="nearest")


def lights(key=2.2, fill=0.55, key_dir="0.42 -0.5 -0.76", fill_dir="-0.55 0.35 -0.76"):
    return ("  <DirectionalLight DEF='Key' direction='%s' intensity='%g' color='1 0.94 0.86'/>\n"
            "  <DirectionalLight DEF='Fill' direction='%s' intensity='%g' color='0.86 0.9 1'/>" % (key_dir, key, fill_dir, fill))


def env(bg="0.035 0.03 0.027", limit=120):
    return ("  <NavigationInfo type='\"EXAMINE\" \"ANY\"' headlight='false' visibilityLimit='%g'/>\n"
            "  <Background skyColor='%s'/>" % (limit, bg))


def text(s, pos, size=0.05, color="0.91 0.81 0.54", justify='"MIDDLE" "MIDDLE"', family='"SERIF"', style="PLAIN", rot=None):
    return ("<Transform translation=%s%s><Shape><Appearance><Material diffuseColor='0 0 0' emissiveColor=%s/></Appearance>"
            "<Text string=%s><FontStyle family=%s style=%s size='%g' justify=%s/></Text></Shape></Transform>" % (
                q(nums(pos, "%.4f")), (" rotation=%s" % q(rot)) if rot else "", q(color), q(mfstring([s])), q(family), q(style), size, q(justify)))


def scale_bar(x0, y0, z0=0.003, length=1.0, color="0.91 0.81 0.54"):
    """A horizontal metre bar on the wall with decimetre ticks and a label."""
    m = "<Appearance><Material diffuseColor='0 0 0' emissiveColor=%s/></Appearance>" % q(color)
    parts = ["  <Transform DEF='ScaleBar' translation=%s>" % q(nums([x0, y0, z0], "%.4f")),
             "   <Transform translation='%g 0 0'><Shape>%s<Box size='%g 0.004 0.002'/></Shape></Transform>" % (length / 2, m, length)]
    for i in range(11):
        hgt = 0.03 if i in (0, 10) else (0.02 if i == 5 else 0.012)
        parts.append("   <Transform translation='%g %g 0'><Shape>%s<Box size='0.003 %g 0.002'/></Shape></Transform>" % (i * length / 10, hgt / 2, m, hgt))
    parts.append("   " + text("1 m", [length / 2, -0.045, 0], 0.045, color))
    parts.append("  </Transform>")
    return "\n".join(parts)


# ---------------------------------------------------------------- the cloth
def cloth_scene(C, P, W, Lc, face_v, rep, sink):
    lods = P["lod_textures"]["levels"]
    ds = [x["distance_m"] for x in lods]
    ranges = [math.sqrt(a * b) for a, b in zip(ds[:-1], ds[1:])]
    face_local = [W / 2, 0, face_v]
    fx = face_v - Lc / 2                                        # the face sits at world (fx, 0, 0)
    face = (fx, 0.0, 0.0)
    # one quad; IndexedFaceSet because its texCoord takes a MultiTextureCoordinate (ElevationGrid's takes one set only)
    grid = ("<IndexedFaceSet DEF='Cloth' coordIndex='0 2 3 1 -1' solid='false'>"
            "<Coordinate point=%s/>"
            "<MultiTextureCoordinate containerField='texCoord'>"
            "<TextureCoordinate mapping='body' point='0 0 1 0 0 1 1 1'/>"
            "<TextureCoordinate mapping='weave' point='0 0 %.4f 0 0 %.4f %.4f %.4f'/>"
            "</MultiTextureCoordinate></IndexedFaceSet>") % (q(nums([0, 0, 0, W, 0, 0, 0, 0, Lc, W, 0, Lc])), rep[0], rep[1], rep[0], rep[1])
    shapes = []
    for i, lv in enumerate(lods):
        first = i == 0
        wn = tex("../maps/weave/weave_normal.png", "normalTexture", "WeaveNormal", aniso=16) if first else "<ImageTexture USE='WeaveNormal' containerField='normalTexture'/>"
        wo = tex("../maps/weave/weave_occlusion.png", "occlusionTexture", "WeaveAO", aniso=16) if first else "<ImageTexture USE='WeaveAO' containerField='occlusionTexture'/>"
        shapes.append("""      <Shape DEF='Seen_%s'>
       <Appearance>
        <PhysicalMaterial baseColor='1 1 1' metallic='0' roughness='0.92' baseTextureMapping='body' normalTextureMapping='weave' normalScale='0.8' occlusionTextureMapping='weave' occlusionStrength='0.55'>
         %s
         %s
         %s
        </PhysicalMaterial>
       </Appearance>
       %s
      </Shape>""" % (("%04.1fm" % lv["distance_m"]).replace(".", "_"), tex("../" + lv["file"], "baseTexture", repeat=False), wn, wo,
                     grid if first else "<IndexedFaceSet USE='Cloth'/>"))
    # about 1 m of cloth around the face at each distance, so the three face views compare like with like
    fov = lambda d, span=1.0: 2 * math.atan(span / 2 / d)          # noqa: E731
    vp = viewpoints([
        ("V_whole", "Whole cloth", "The whole cloth at 5.5 m, hung as it is shown in Turin", (0, 0, 5.5), (0, 0, 0), (0, 1, 0), 0.8),
        ("V_frontal", "Frontal image", "The frontal image at 3 m", (fx + 0.78, 0, 3.0), (fx + 0.78, 0, 0), UP_HEAD, fov(3.0, 2.2)),
        ("V_face_6", "Face at 6 m", "The face from 6 m: the image is clear", (fx, 0, 6.0), face, UP_HEAD, fov(6.0)),
        ("V_face_18", "Face at 1.8 m", "The face from 1.8 m: the measured threshold", (fx, 0, 1.8), face, UP_HEAD, fov(1.8)),
        ("V_face_10", "Face at 1 m", "The face from 1 m: the image has dissolved into the cloth", (fx, 0, 1.0), face, UP_HEAD, fov(1.0)),
        ("V_weave", "Weave at 0.3 m", "The weave from 0.3 m, a 4 cm field: 38.3 warp and 25.4 weft threads per cm", (fx, 0.03, 0.3), (fx, 0.03, 0), UP_HEAD, fov(0.3, 0.04)),
    ], sink, face)
    body = "\n".join([
        world_info(C, "Shroud of Turin: the cloth at true scale", [
            "4.37 x 1.11 m (pre-2002 state), linen colour from JJE 1984, the image as JJE albedo, the weave at Vial's thread counts.",
            "The LOD swaps the image texture by viewing distance: each level is the image an eye resolves at that distance (data/perception.json).",
            "Body image: a synthetic forward model (aesthetic stand-in), not a photograph. See README.md."]),
        env(), vp, lights(4.6, 1.15),                             # bright enough that bare linen renders near its albedo in X_ITE
        "  <ProximitySensor DEF='Near' size='400 400 400'/>",
        "  <Transform DEF='Backing' translation='0 0 -0.012'><Shape><Appearance><PhysicalMaterial baseColor='0.045 0.05 0.07' metallic='0' roughness='0.95'/></Appearance><Box size='4.75 1.45 0.02'/></Shape></Transform>",
        scale_bar(-Lc / 2, -W / 2 - 0.1),
        "  " + text("FRONTAL", [fx + 0.8, W / 2 + 0.08, 0.003], 0.05, "0.72 0.59 0.29", family='"SANS"', style="BOLD"),
        "  " + text("DORSAL", [-(fx + 0.8), W / 2 + 0.08, 0.003], 0.05, "0.72 0.59 0.29", family='"SANS"', style="BOLD"),
        "  <Transform DEF='Hang' rotation=%s>" % q(HANG),
        "   <Transform DEF='ClothOrigin' translation=%s>" % q(nums([-W / 2, 0, -Lc / 2])),
        "    <LOD DEF='Dissolve' center=%s range=%s>" % (q(nums(face_local)), q(nums(ranges, "%.3f"))),
        "\n".join(shapes),
        "    </LOD>", "   </Transform>", "  </Transform>"])
    return doc("Shroud of Turin: cloth at true scale", "The cloth with the JJE 1984 colour model, Vial's weave and the 1.8 m dissolve.", body,
               [("Navigation", 2), ("EnvironmentalSensor", 1), ("Texturing", 2), ("Shape", 2), ("Text", 1)]), face


# ---------------------------------------------------------------- the laboratory
VERT = r"""data:x-shader/x-vertex,#version 300 es
precision highp float;
uniform mat4 x3d_ProjectionMatrix;
uniform mat4 x3d_ModelViewMatrix;
uniform mat3 x3d_NormalMatrix;
uniform sampler2D hTex;
uniform float relief;
uniform float rangeM;
in vec4 x3d_Vertex;
in vec3 x3d_Normal;
in vec4 x3d_TexCoord0;
out vec2 uv;
out vec3 vPos;
out vec3 vN;
out vec3 vT;
out vec3 vB;
void main ()
{
  uv = x3d_TexCoord0 .st;
  vec4 p = x3d_Vertex;
  if (relief > 0.0)
    p .y += rangeM * relief * textureLod (hTex, uv, 1.0) .r;
  vec4 vp = x3d_ModelViewMatrix * p;
  vPos = vp .xyz;
  vN = normalize (x3d_NormalMatrix * x3d_Normal);
  vT = normalize (mat3 (x3d_ModelViewMatrix) * vec3 (1.0, 0.0, 0.0));
  vB = normalize (mat3 (x3d_ModelViewMatrix) * vec3 (0.0, 0.0, 1.0));
  gl_Position = x3d_ProjectionMatrix * vp;
}
"""

FRAG = r"""data:x-shader/x-fragment,#version 300 es
precision highp float;
uniform sampler2D hTex;
uniform sampler2D weaveTex;
uniform vec3  linen;
uniform vec3  image1;
uniform float lambdaNm;
uniform float gain;
uniform float dissolve;
uniform float weave;
uniform float negative;
uniform float relief;
uniform float exposure;
uniform float sPeak;
uniform float sMax;
uniform float aLum;
uniform float texelM;
uniform float clothW;
uniform float clothL;
uniform float warpRepeat;
uniform float weftRepeat;
uniform float rangeM;
uniform float jjeA;
uniform float jjeB;
uniform float jjeC;
uniform float jjeLp;
in vec2 uv;
in vec3 vPos;
in vec3 vN;
in vec3 vT;
in vec3 vB;
out vec4 x3d_FragColor;

// Mannos and Sakrison (1974) contrast sensitivity; f in cycles per degree.
float csf (float f)
{
  return 2.6 * (0.0192 + 0.114 * f) * exp (-pow (0.114 * f, 1.1));
}

// The image as an eye at distance d resolves it (data/perception.json): each mip band of h is kept with weight
// v^3 / (1 + v^3), where v is the band's local contrast (Peli 1990) times the calibrated sensitivity at the band's
// angular frequency.
float seenH (float d)
{
  float prev = textureLod (hTex, uv, 0.0) .r;
  float acc  = 0.0;
  for (int k = 0; k < 9; ++ k)
  {
    float next = textureLod (hTex, uv, float (k + 1)) .r;
    float band = prev - next;
    if (dissolve > 0.5)
    {
      float f  = 0.53 / (texelM * exp2 (float (k)));
      float c  = abs (aLum * band) / max (1.0 - aLum * next, 0.05);
      float v  = c * sPeak * csf (f * d * 0.01745329) / sMax;
      float v3 = v * v * v;
      acc += band * v3 / (1.0 + v3);
    }
    else
      acc += band;
    prev = next;
  }
  return clamp (prev + acc, 0.0, 1.0);
}

vec3 toSRGB (vec3 c)
{
  c = clamp (c, 0.0, 1.0);
  return mix (c * 12.92, 1.055 * pow (c, vec3 (1.0 / 2.4)) - 0.055, step (vec3 (0.0031308), c));
}

void main ()
{
  float h = seenH (length (vPos));
  vec3 alb;
  if (lambdaNm > 0.0)
  {
    // JJE 1984: r = (a + b l) [1 + c (l - l') h], valid 300 to 700 nm
    float l  = clamp (lambdaNm, 300.0, 700.0);
    float r0 = jjeA + jjeB * l;
    alb = vec3 (r0 + gain * r0 * jjeC * (l - jjeLp) * h);
  }
  else
    alb = linen + gain * h * (image1 - linen);
  vec3 n = normalize (vN);
  vec3 T = normalize (vT);
  vec3 B = normalize (vB);
  if (relief > 0.0)
  {
    float es = 1.0 / 512.0;
    float et = 1.0 / 2048.0;
    float hs = textureLod (hTex, uv + vec2 (es, 0.0), 1.0) .r - textureLod (hTex, uv - vec2 (es, 0.0), 1.0) .r;
    float ht = textureLod (hTex, uv + vec2 (0.0, et), 1.0) .r - textureLod (hTex, uv - vec2 (0.0, et), 1.0) .r;
    n = normalize (n - rangeM * relief * (hs / (2.0 * es * clothW)) * T - rangeM * relief * (ht / (2.0 * et * clothL)) * B);
  }
  if (weave > 0.5)
  {
    vec3 tn = texture (weaveTex, uv * vec2 (warpRepeat, weftRepeat)) .xyz * 2.0 - 1.0;
    n = normalize (tn .x * T + tn .y * B + tn .z * n);
  }
  vec3  Lk   = normalize (vec3 (-0.45, 0.55, 0.70));
  vec3  Lf   = normalize (vec3 (0.6, -0.2, 0.75));
  float key  = max (dot (n, Lk), 0.0);
  float fill = max (dot (n, Lf), 0.0);
  vec3  col  = alb * exposure * (0.16 + 1.05 * key * vec3 (1.0, 0.95, 0.88) + 0.30 * fill * vec3 (0.86, 0.9, 1.0));
  if (negative > 0.5)
    col = max (vec3 (0.0), vec3 (0.62) - col) * 1.55;
  x3d_FragColor = vec4 (toSRGB (col), 1.0);
}
"""


def lab_scene(C, P, S, W, Lc, face_v, rep, sink):
    rows, cols = 513, 129
    flat = q(" ".join(["0"] * (rows * cols)))
    rgb = S["rgb"]["D65_daylight"]
    fields = [
        ("SFFloat", "lambdaNm", "0"), ("SFFloat", "gain", "1"), ("SFFloat", "dissolve", "1"), ("SFFloat", "weave", "1"),
        ("SFFloat", "negative", "0"), ("SFFloat", "relief", "0"), ("SFFloat", "exposure", "1"),
        ("SFVec3f", "linen", nums(rgb[0], "%.6f")), ("SFVec3f", "image1", nums(rgb[-1], "%.6f")),
        ("SFFloat", "sPeak", "%.4f" % (P["peak_sensitivity"]["value"] * P["calibration"]["factor"])),
        ("SFFloat", "sMax", "%.6f" % P["csf"]["peak_value"]), ("SFFloat", "aLum", "%.6f" % P["luminance"]["a"]),
        ("SFFloat", "texelM", "%.6f" % (W / 512)), ("SFFloat", "clothW", "%g" % W), ("SFFloat", "clothL", "%g" % Lc),
        ("SFFloat", "warpRepeat", "%.4f" % rep[0]), ("SFFloat", "weftRepeat", "%.4f" % rep[1]),
        ("SFFloat", "rangeM", "%g" % C["distance.frontal_range_m"]["value"]),
        ("SFFloat", "jjeA", "%g" % C["jje.a"]["value"]), ("SFFloat", "jjeB", "%g" % C["jje.b"]["value"]),
        ("SFFloat", "jjeC", "%g" % C["jje.c"]["value"]), ("SFFloat", "jjeLp", "%g" % C["jje.lambda_prime_nm"]["value"]),
    ]
    flds = "\n".join("       <field accessType='inputOutput' type=%s name=%s value=%s/>" % (q(t), q(n), q(v)) for t, n, v in fields)
    fx = face_v - Lc / 2
    face = (fx, 0.0, 0.0)
    fov = lambda d, span=1.0: 2 * math.atan(span / 2 / d)          # noqa: E731
    vp = viewpoints([
        ("L_face_6", "Face at 6 m", "The face from 6 m", (fx, 0, 6.0), face, UP_HEAD, fov(6.0)),
        ("L_face_18", "Face at 1.8 m", "The face from 1.8 m: the measured threshold", (fx, 0, 1.8), face, UP_HEAD, fov(1.8)),
        ("L_face_10", "Face at 1 m", "The face from 1 m", (fx, 0, 1.0), face, UP_HEAD, fov(1.0)),
        ("L_weave", "Weave at 0.3 m", "The weave from 0.3 m, a 4 cm field", (fx, 0.03, 0.3), (fx, 0.03, 0), UP_HEAD, fov(0.3, 0.04)),
        ("L_whole", "Whole cloth", "The whole cloth at 5.5 m", (0, 0, 5.5), (0, 0, 0), (0, 1, 0), 0.8),
        ("L_raking", "Raking light", "The frontal half from low on the right; switch relief on", (fx + 2.6, -1.3, 1.5), (fx + 0.8, 0, 0), (0, 0, 1), 0.75),
    ], sink, face)
    body = "\n".join([
        world_info(C, "Shroud of Turin: spectral and perception laboratory", [
            "Albedo = lerp(LUT row h=0, LUT row h=1, h) under a chosen illuminant (data/spectral), or the JJE reflectance at one wavelength.",
            "Per fragment, the image is filtered by the dissolve model (data/perception.json): it fades below about 1.8 m.",
            "The weave normal map repeats at Vial's counts: 38.3 warp and 25.4 weft threads per cm.",
            "gain multiplies the image contrast for display only (1 = physical). Body image: a synthetic forward model."]),
        env("0.03 0.028 0.026"), vp,
        "  <ProximitySensor DEF='Near' size='400 400 400'/>",
        "  <Transform DEF='Backing' translation='0 0 -0.012'><Shape><Appearance><PhysicalMaterial baseColor='0.045 0.05 0.07' metallic='0' roughness='0.95'/></Appearance><Box size='4.75 1.45 0.02'/></Shape></Transform>",
        lights(1.6, 0.4),
        "  <Transform rotation=%s>" % q(HANG),
        "   <Transform translation=%s>" % q(nums([-W / 2, 0, -Lc / 2])),
        "    <Shape DEF='LabCloth'>",
        "     <Appearance>",
        "      <PhysicalMaterial baseColor='1 1 1' metallic='0' roughness='0.92'>%s</PhysicalMaterial>" % tex("../maps/synthetic/albedo_d65_srgb.png", "baseTexture", repeat=False),
        "      <ComposedShader DEF='Lab' language='GLSL'>",
        "       <field accessType='inputOutput' type='SFNode' name='hTex'>%s</field>" % tex("../maps/synthetic/h_8bit_dithered_half.png", repeat=False, aniso=4),
        "       <field accessType='inputOutput' type='SFNode' name='weaveTex'>%s</field>" % tex("../maps/weave/weave_normal.png", aniso=16),
        flds,
        "       <ShaderPart type='VERTEX'><![CDATA[%s]]></ShaderPart>" % VERT,
        "       <ShaderPart type='FRAGMENT'><![CDATA[%s]]></ShaderPart>" % FRAG,
        "      </ComposedShader>",
        "     </Appearance>",
        "     <ElevationGrid DEF='LabGrid' xDimension='%d' zDimension='%d' xSpacing='%.6f' zSpacing='%.6f' solid='false' height=%s/>" % (cols, rows, W / (cols - 1), Lc / (rows - 1), flat),
        "    </Shape>", "   </Transform>", "  </Transform>"])
    return doc("Shroud of Turin: spectral and perception laboratory",
               "JJE 1984 colour under seven illuminants or at one wavelength, with the 1.8 m dissolve computed per fragment.", body,
               [("Geometry3D", 3), ("Navigation", 2), ("EnvironmentalSensor", 1), ("Texturing", 2), ("Shape", 2), ("Shaders", 1)]), face


# ---------------------------------------------------------------- the relief
def relief_scene(C, h, W, Lc, face_v, sink, exag=4.0, rng=0.037, face_exag=1.0):
    rows, cols = 513, 129
    heights = rng * exag * sample(h, W, Lc, 0, W, 0, Lc, rows, cols)
    g = ("<ElevationGrid DEF='Relief' xDimension='%d' zDimension='%d' xSpacing='%.6f' zSpacing='%.6f' creaseAngle='1.2' solid='false' height=%s/>"
         % (cols, rows, W / (cols - 1), Lc / (rows - 1), q(nums(heights, "%.4f"))))
    u0, u1 = W / 2 - 0.15, W / 2 + 0.15                       # the face at 1.5 mm, true width
    v0, v1 = face_v - 0.17, face_v + 0.21
    fr, fc = int(round((v1 - v0) / 0.0015)) + 1, int(round((u1 - u0) / 0.0015)) + 1
    fh = rng * face_exag * sample(h, W, Lc, u0, u1, v0, v1, fr, fc)      # true scale: the 3.7 cm the range allows
    fg = ("<ElevationGrid DEF='FaceRelief' xDimension='%d' zDimension='%d' xSpacing='%.6f' zSpacing='%.6f' creaseAngle='1.2' solid='false' height=%s/>"
          % (fc, fr, (u1 - u0) / (fc - 1), (v1 - v0) / (fr - 1), q(nums(fh, "%.4f"))))
    fx = face_v - Lc / 2
    plaque_top = -W / 2 - 0.16                                   # the face plaque hangs below the cloth, head up
    pc = (fx, plaque_top - (v1 - v0) / 2, 0.04)
    vp = viewpoints([
        ("R_whole", "Whole relief", "The whole cloth as relief, lit from the upper left", (0.3, -2.3, 4.6), (0, -0.25, 0.04), (0, 1, 0), 0.8),
        ("R_frontal", "Frontal relief", "The frontal figure as relief, raking view from the feet", (fx + 2.7, -0.75, 1.25), (fx + 0.8, 0, 0.05), (0, 0, 1), 0.75),
        ("R_face", "Face relief", "The face as relief at 1.5 mm, true width and true 3.7 cm range", (fx + 0.07, pc[1] - 0.12, 1.0), (fx, pc[1] - 0.05, 0.02), (0, 1, 0), 0.5),
        ("R_face_side", "Face, raking", "The face relief from the right, under a grazing light", (fx + 0.35, pc[1] + 0.03, 0.55), (fx, pc[1] - 0.02, 0.02), (0, 1, 0), 0.5),
    ], sink)
    plaster = "<PhysicalMaterial baseColor='0.82 0.8 0.76' metallic='0' roughness='0.75'/>"
    body = "\n".join([
        world_info(C, "Shroud of Turin: the image field as relief", [
            "Whole cloth: height = 0.037 m x h x %g (distance.relief_exaggeration_default, aesthetic). The face below it is at true scale (x1)." % exag,
            "JJE 1984 found image intensity correlates with cloth-body distance (linear fit, r2 = 0.60). The relief is that reading made visible.",
            "Body image: a synthetic forward model (aesthetic stand-in)."]),
        env("0.03 0.03 0.035"), vp, lights(2.6, 0.4),
        "  <ProximitySensor DEF='Near' size='400 400 400'/>",
        scale_bar(-Lc / 2, W / 2 + 0.1),
        "  <Transform rotation=%s>" % q(HANG),
        "   <Transform translation=%s>" % q(nums([-W / 2, 0, -Lc / 2])),
        "    <Shape><Appearance>%s</Appearance>%s</Shape>" % (plaster, g),
        "   </Transform>", "  </Transform>",
        "  <Group DEF='FaceStage'>",                               # a grazing light that reaches only the plaque (not global)
        "   <DirectionalLight DEF='Raking' direction='-0.88 -0.36 -0.3' intensity='1.8' color='1 0.95 0.88'/>",
        "   <Transform DEF='FacePlaque' translation=%s rotation='1 0 0 1.5708'>" % q(nums([fx - 0.15, plaque_top, 0.0], "%.4f")),
        "    <Shape><Appearance><PhysicalMaterial baseColor='0.86 0.84 0.8' metallic='0' roughness='0.68'/></Appearance>%s</Shape>" % fg,
        "   </Transform>",
        "  </Group>",
        "  " + text("The face at true scale: 1.5 mm grid, 3.7 cm range", [fx, plaque_top - (v1 - v0) - 0.05, 0.003], 0.028, "0.72 0.59 0.29", family='"SANS"'),
    ])
    return doc("Shroud of Turin: image field as relief", "h displayed as height, as the VP-8 Image Analyzer first showed in 1976.", body,
               [("Geometry3D", 3), ("EnvironmentalSensor", 1), ("Text", 1), ("Shape", 2)])


# ---------------------------------------------------------------- the formation hypothesis
SEPIA = np.array([[0.93, 0.89, 0.80], [0.80, 0.62, 0.38], [0.45, 0.25, 0.10]])


def sepia(hv):
    t = np.clip(hv, 0, 1)[..., None]
    return np.where(t < 0.5, SEPIA[0] + (SEPIA[1] - SEPIA[0]) * (t / 0.5), SEPIA[1] + (SEPIA[2] - SEPIA[1]) * ((t - 0.5) / 0.5))


def formation_scene(C, W, Lc, fold, head_gap, sink):
    top = read_exr(os.path.join(PKG, "maps", "synthetic", "top_m_half.exr"))
    cloth = read_exr(os.path.join(PKG, "maps", "synthetic", "cloth_m_half.exr"))
    h = read_png16(os.path.join(PKG, "maps", "synthetic", "h_16bit.png"))
    ua, ub = W / 2 - 0.36, W / 2 + 0.36
    va, vb = fold + head_gap - 0.04, fold + head_gap + 1.86
    step = 0.0065
    cols, rows = int(round((ub - ua) / step)) + 1, int(round((vb - va) / step)) + 1
    import synthetic_body as SB
    # the body as a height field has vertical walls where its sides turn under; a steep skirt (slope 1.2, display
    # only) hides them, and stays below the slope-0.30 drape everywhere
    skirt = SB.tent_drape(np.where(top > 0, top, 0.0), W / top.shape[1], slope=1.2, smooth=0.002, step_px=4)
    tb = sample(skirt, W, Lc, ua, ub, va, vb, rows, cols, blur=False)
    cl = np.maximum(sample(cloth, W, Lc, ua, ub, va, vb, rows, cols, blur=False), tb + 0.0006)
    # the image the cloth would carry, at 2 mm, on a sepia ramp (dark = strong image), for the drape and the flat copy
    tr, tc = int(round((vb - va) / 0.002)), int(round((ub - ua) / 0.002))
    img = sepia(sample(h, W, Lc, ua, ub, va, vb, tr, tc))
    os.makedirs(os.path.join(PKG, "x3d", "textures"), exist_ok=True)
    L.write_png(os.path.join(PKG, "x3d", "textures", "formation_h_sepia.png"), L.to_u8(img[::-1]),
                {"Description": "h of the synthetic frontal image on a sepia ramp (display only, not a colour measurement)",
                 "Software": "tools/make_x3d.py"})
    dx, dz = (ub - ua) / (cols - 1), (vb - va) / (rows - 1)
    body_grid = ("<ElevationGrid DEF='Body' xDimension='%d' zDimension='%d' xSpacing='%.6f' zSpacing='%.6f' creaseAngle='1.4' solid='false' height=%s/>"
                 % (cols, rows, dx, dz, q(nums(tb, "%.4f"))))
    cloth_grid = ("<ElevationGrid DEF='Drape' xDimension='%d' zDimension='%d' xSpacing='%.6f' zSpacing='%.6f' creaseAngle='1.4' solid='false' height=%s/>"
                  % (cols, rows, dx, dz, q(nums(cl, "%.4f"))))
    wx, lz = ub - ua, vb - va
    off = [-wx / 2, 0, -lz / 2]                                   # the figure centred on the origin, head toward -z
    face_z = 0.04 + 0.12 - lz / 2
    vp = viewpoints([
        ("F_three_quarter", "Over the body", "The cloth resting on the body, three-quarter view", (1.45, 0.95, -1.35), (0.05, 0.08, -0.25), (0, 1, 0), 0.8),
        ("F_face", "Over the face", "Over the face: where the cloth touches, the image is darkest", (0.12, 0.6, face_z + 0.45), (0, 0.12, face_z - 0.03), (0, 1, 0), 0.5),
        ("F_top", "From above", "From above: the drape's colour is the image it would form", (0.33, 3.3, 0.0), (0.33, 0, 0.0), (0, 0, -1), 0.72),
        ("F_flat", "Drape and flat", "The drape beside the same cloth laid flat", (0.85, 1.9, 1.95), (0.33, 0.05, 0.1), (0, 1, 0), 0.85),
    ], sink)
    flat = ("<Shape><Appearance><PhysicalMaterial baseColor='1 1 1' metallic='0' roughness='0.95'>%s</PhysicalMaterial></Appearance>"
            "<ElevationGrid xDimension='2' zDimension='2' xSpacing='%.4f' zSpacing='%.4f' height='0 0 0 0' solid='false'/></Shape>"
            % ("<ImageTexture USE='SepiaH' containerField='baseTexture'/>", wx, lz))
    body = "\n".join([
        world_info(C, "Shroud of Turin: the image-formation hypothesis", [
            "A mannequin (aesthetic) lies on a slab; a cloth rests on its high points and falls no steeper than slope 0.30 (inferred).",
            "The cloth carries h = 1 - gap / 0.037 m (JJE 1984 linear fit), softened to the 5 mm image resolution, on a sepia ramp.",
            "Beside it, the same cloth laid flat. This is the distance hypothesis made visible, not a reconstruction or a mechanism."]),
        env("0.04 0.04 0.045"), vp, lights(2.0, 0.6, "0.35 -0.8 0.45", "-0.6 -0.3 -0.7"),
        "  <Transform DEF='Bench' translation=%s>" % q(nums(off, "%.4f")),
        "   <Shape><Appearance><PhysicalMaterial baseColor='0.84 0.82 0.78' metallic='0' roughness='0.6'/></Appearance>%s</Shape>" % body_grid,
        "   <Transform translation='0 0.0015 0'><Shape><Appearance><PhysicalMaterial baseColor='1 1 1' metallic='0' roughness='0.95' transparency='0.25'>%s</PhysicalMaterial></Appearance>%s</Shape></Transform>"
        % (tex("textures/formation_h_sepia.png", "baseTexture", "SepiaH", repeat=False), cloth_grid),
        "   <Transform DEF='Slab' translation=%s><Shape><Appearance><PhysicalMaterial baseColor='0.2 0.19 0.18' metallic='0' roughness='0.85'/></Appearance><Box size=%s/></Shape></Transform>"
        % (q(nums([wx / 2, -0.031, lz / 2], "%.4f")), q(nums([wx + 0.12, 0.06, lz + 0.12], "%.4f"))),
        "   <Transform DEF='FlatCloth' translation=%s>%s</Transform>" % (q(nums([wx + 0.28, 0.001, 0], "%.4f")), flat),
        "  </Transform>",
        "  " + text("draped", [0, 0.002, lz / 2 + 0.14], 0.07, "0.72 0.59 0.29", family='"SANS"', rot="1 0 0 -1.5708"),
        "  " + text("laid flat", [wx + 0.28, 0.002, lz / 2 + 0.14], 0.07, "0.72 0.59 0.29", family='"SANS"', rot="1 0 0 -1.5708"),
    ])
    return doc("Shroud of Turin: image-formation hypothesis", "Mannequin, draped cloth coloured by h, and the same cloth laid flat.", body,
               [("Geometry3D", 3), ("Text", 1), ("Shape", 2), ("Texturing", 2)])


# ---------------------------------------------------------------- the timeline
LANES = [("legend", "Edessa and the images not made by hands", "0.83 0.62 0.32"),
         ("byzantine", "Pantocrator and the Eastern icon", "0.86 0.70 0.30"),
         ("veronica", "Veronica and the Holy Face", "0.78 0.45 0.38"),
         ("shroud", "The Shroud and its copies", "0.93 0.87 0.74"),
         ("salvator", "Salvator Mundi", "0.58 0.66 0.86"),
         ("photography", "Photography and devotion", "0.62 0.78 0.76"),
         ("science", "Measurement and dispute", "0.55 0.84 0.62")]


def year_x(y):
    """Years to metres, stretched where the graph is dense (the Renaissance copies and paintings)."""
    for y0, x0, per in SCALE[::-1]:
        if y >= y0:
            return x0 + (y - y0) / per
    return (y - 200) / 100.0


SCALE = [(200, 0.0, 100.0), (1200, 10.0, 40.0), (1400, 15.0, 25.0), (1750, 29.0, 40.0), (1900, 32.75, 10.0)]   # (from year, x, years per metre)


def timeline_scene(nodes, sink):
    gap = 2.0
    lane_y = {k: gap * 3 - gap * i for i, (k, _, _) in enumerate(LANES)}
    out = ["  <Transform DEF='Rails'>"]
    x0, x_end = year_x(200) - 0.6, year_x(2026) + 0.6
    for k, title, col in LANES:
        y = lane_y[k]
        dim = nums([float(x) * 0.35 for x in col.split()], "%.3f")
        out.append("   <Transform translation=%s><Shape><Appearance><Material diffuseColor='0 0 0' emissiveColor=%s/></Appearance><Box size='%g 0.02 0.02'/></Shape></Transform>"
                   % (q(nums([(x0 + x_end) / 2, y, -0.05], "%.3f")), q(dim), x_end - x0))
        out.append("   " + text(title, [x0 - 0.3, y, 0], 0.32, col, '"END" "MIDDLE"', '"SERIF"'))
        for xl in (8.0, 20.0, 32.0):                            # the lane's name again along the way, for close views
            out.append("   " + text(title, [xl, y - 0.34, 0], 0.13, dim, '"BEGIN" "MIDDLE"', '"SANS"', "ITALIC"))
    for y in [200, 400, 600, 800, 1000, 1200, 1300, 1400, 1450, 1500, 1550, 1600, 1650, 1700, 1750, 1800, 1850, 1900, 1950, 2000, 2026]:
        x = year_x(y)
        out.append("   <Transform translation=%s><Shape><Appearance><Material diffuseColor='0 0 0' emissiveColor='0.16 0.15 0.17'/></Appearance><Box size='0.015 %g 0.01'/></Shape></Transform>"
                   % (q(nums([x, 0, -0.1], "%.3f")), gap * 7))
        out.append("   " + text(str(y), [x, -gap * 3.5 - 0.5, 0], 0.32, "0.6 0.57 0.52", family='"SANS"'))
    bounds = [y0 for y0, _, _ in SCALE] + [2026]
    for (y0, _, per), y1 in zip(SCALE, bounds[1:]):
        label = {100.0: "1 m per century", 10.0: "1 m per decade"}.get(per, "1 m per %d years" % per)
        out.append("   " + text(label, [(year_x(y0) + year_x(y1)) / 2, -gap * 3.5 - 1.1, 0], 0.22, "0.42 0.4 0.37", family='"SANS"', style="ITALIC"))
    out.append("  </Transform>")
    tagcol = {"measured": "0.45 0.85 0.55", "historical": "0.95 0.9 0.8", "contested": "0.95 0.55 0.35", "tradition": "0.85 0.75 1",
              "inferred": "0.95 0.8 0.35", "unsupported": "0.6 0.6 0.6", "hypothesis": "0.8 0.6 1"}
    lane_col = dict((a, c) for a, _, c in LANES)
    dated = sorted([n for n in nodes.values() if n.get("start") is not None and n.get("lane")], key=lambda n: n["start"])
    ends = {}
    for n in dated:
        x = year_x((n["start"] + (n.get("end") or n["start"])) / 2.0)
        label = n["name"] if len(n["name"]) <= 34 else n["name"][:32].rstrip() + "…"
        when = n.get("date") or str(n["start"])
        width = 0.14 + max(len(label) * 0.13, len(when) * 0.1) * 0.56 + 0.2
        lv = 0
        while lv < 5 and ends.get((n["lane"], lv), -99) > x:     # the lowest row in this lane where the label fits
            lv += 1
        ends[(n["lane"], lv)] = x + width
        yy = lane_y[n["lane"]] + 0.3 * lv
        col = lane_col[n["lane"]]
        rim = tagcol.get(n["tag"], "0.9 0.9 0.9")
        if lv:                                                    # a stem back to the rail
            out.append("  <Transform translation=%s><Shape><Appearance><Material diffuseColor='0 0 0' emissiveColor=%s/></Appearance><Box size='0.012 %g 0.006'/></Shape></Transform>"
                       % (q(nums([x, lane_y[n["lane"]] + 0.15 * lv, -0.02], "%.3f")), q(nums([float(c) * 0.45 for c in col.split()], "%.3f")), 0.3 * lv))
        out.append("  <Transform translation=%s><Shape><Appearance><Material diffuseColor='0 0 0' emissiveColor=%s/></Appearance><Sphere radius='0.06'/></Shape>%s%s</Transform>"
                   % (q(nums([x, yy, 0], "%.3f")), q(rim),
                      text(label, [0.1, 0.035, 0], 0.13, col, '"BEGIN" "MIDDLE"', '"SANS"'),
                      text(when, [0.1, -0.1, 0], 0.1, "0.55 0.52 0.48", '"BEGIN" "MIDDLE"', '"SANS"', "ITALIC")))
    mid = (x0 - 7 + x_end) / 2
    vp = viewpoints([
        ("T_all", "Whole timeline", "Every dated node, 200 to 2026", (mid, -0.4, 32), (mid, -0.4, 0), (0, 1, 0), 0.9),
        ("T_early", "200 to 1250", "Legend and icon: Edessa, the Pantocrator, the Mandylion", (5.6, -0.4, 13), (5.6, -0.4, 0), (0, 1, 0), 0.9),
        ("T_middle", "1350 to 1550", "Lirey, Chambery, Veronica, the first Salvator Mundi", (18.2, 0.2, 9.5), (18.2, 0.2, 0), (0, 1, 0), 0.9),
        ("T_late", "1550 to 1900", "Turin, the painted copies, the chapel, the first photograph", (27.5, 0.2, 9.5), (27.5, 0.2, 0), (0, 1, 0), 0.9),
        ("T_modern", "1880 to 2026", "Photography and science", (39.0, -0.4, 13), (39.0, -0.4, 0), (0, 1, 0), 0.9),
    ], sink)
    body = "\n".join(["  <WorldInfo title='Shroud knowledge graph: timeline' info='\"Dated nodes of graph/shroud.jsonld, one lane per lineage. Dot colour = epistemic tag.\"'/>",
                      "  <NavigationInfo type='\"EXAMINE\" \"ANY\"' headlight='false' visibilityLimit='300'/>",
                      "  <Background skyColor='0.03 0.028 0.036'/>", vp] + out)
    return doc("Shroud knowledge graph: timeline", "Relics, artworks, photographs and events on one timeline, with the lanes of the lineage diagram.", body,
               [("Text", 1)])


# ---------------------------------------------------------------- main
def main():
    C = L.load_constants(PKG)
    P = json.load(open(os.path.join(PKG, "data", "perception.json"), encoding="utf-8"))
    S = json.load(open(os.path.join(PKG, "data", "spectral", "shroud_spectral_lut.json"), encoding="utf-8"))
    D = json.load(open(os.path.join(PKG, "data", "dimensions.json"), encoding="utf-8"))
    WV = json.load(open(os.path.join(PKG, "data", "weave.json"), encoding="utf-8"))
    HM = json.load(open(os.path.join(PKG, "data", "height_model.json"), encoding="utf-8"))
    W, Lc = D["states"]["pre-2002"]["width_m"], D["states"]["pre-2002"]["length_m"]
    lay = HM["synthetic_forward_model"]["layout"]
    fold = lay["fold_v"] * Lc
    face_v = fold + lay["head_gap"] + 0.12                      # the synthetic face, metres along the cloth from v = 0
    rep = WV["tile"]["repeats_on_cloth_pre2002"]
    h = read_png16(os.path.join(PKG, "maps", "synthetic", "h_16bit.png"))
    import make_graph
    _, nodes, _ = make_graph.build(PKG)
    X = os.path.join(PKG, "x3d")
    os.makedirs(X, exist_ok=True)
    manifest = []

    def add(fid, fn, title, kicker, blurb, xml, vps, face=None, controls=None, look_=None):
        with open(os.path.join(X, fn), "w", encoding="utf-8") as f:
            f.write(xml)
        manifest.append({"id": fid, "file": "x3d/" + fn, "title": title, "kicker": kicker, "blurb": blurb, "viewpoints": vps,
                         "face_world_m": list(face) if face else None, "controls": controls, "look": look_ or {}})
        print("%-24s %7.0f KB  %d viewpoints" % (fn, len(xml.encode()) / 1024, len(vps)))

    vps = []
    xml, face = cloth_scene(C, P, W, Lc, face_v, rep, vps)
    add("cloth", "shroud_cloth.x3d", "The cloth", "4.37 by 1.11 m, as Enrie and STURP saw it",
        "Linen coloured by the JJE 1984 model, the weave at Vial's thread counts, and an image that fades as you come closer than about 1.8 m.",
        xml, vps, face, "distance", {"toneMapping": "KHR_PBR_NEUTRAL", "exposure": 1.0})
    vps = []
    xml, face = lab_scene(C, P, S, W, Lc, face_v, rep, vps)
    add("lab", "shroud_lab.x3d", "Spectral lab", "One equation, seven lights",
        "The image under daylight, tungsten, candle and museum LEDs, or at a single wavelength, with the dissolve computed for every pixel.",
        xml, vps, face, "lab", {"toneMapping": "NONE", "exposure": 1.0})
    vps = []
    add("relief", "shroud_relief.x3d", "Relief", "Intensity read as distance",
        "The image intensity plotted as height, as the VP-8 Image Analyzer first showed it in 1976. Height is exaggerated four times.",
        relief_scene(C, h, W, Lc, face_v, vps, exag=C["distance.relief_exaggeration_default"]["value"], rng=C["distance.frontal_range_m"]["value"]),
        vps, None, None, {"toneMapping": "KHR_PBR_NEUTRAL", "exposure": 1.0})
    vps = []
    add("formation", "shroud_formation.x3d", "Formation", "A hypothesis made visible",
        "A cloth resting on a body carries an image whose darkness follows the gap between them. This is what that rule predicts, not how it happened.",
        formation_scene(C, W, Lc, fold, lay["head_gap"], vps), vps, None, None, {"toneMapping": "KHR_PBR_NEUTRAL", "exposure": 1.0})
    vps = []
    add("timeline", "shroud_timeline.x3d", "Timeline", "Eighteen centuries of one face",
        "Relics, artworks, photographs and measurements from the knowledge graph, in the lanes of the lineage diagram.",
        timeline_scene(nodes, vps), vps, None, None, {"toneMapping": "NONE", "exposure": 1.0})
    L.write_json(os.path.join(X, "scenes.json"), {"title": "Shroud of Turin scenes", "generator": "tools/make_x3d.py", "scenes": manifest})


if __name__ == "__main__":
    main()
