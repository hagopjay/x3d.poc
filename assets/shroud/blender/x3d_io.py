#!/usr/bin/env python3
"""X3D 4.0 in and out of Blender for this package's scenes, keeping their metadata.

Import (the package's five scenes, or any X3D file built from the same nodes)
  blender -b -P blender/x3d_io.py -- import x3d/shroud_relief.x3d --save relief.blend
  blender -b -P blender/x3d_io.py -- import x3d/shroud_formation.x3d --render formation.png --viewpoint F_flat
  python3 blender/x3d_io.py import x3d/shroud_cloth.x3d --render cloth.png        # with the bpy module

Export (meshes, cameras and suns of the open scene)
  blender -b scene.blend -P blender/x3d_io.py -- export out.x3d
  blender -b -P blender/build_shroud.py -- --export-x3d out.x3d                   # the cloth built from the data

Why an importer of its own: Blender's X3D add-on (and the X3D 4.0 fork of it) builds ElevationGrid faces in the wrong
vertex order whenever xDimension differs from zDimension, and every height field in this package is non-square
(a 3 x 5 test grid comes back with all eight faces wrong). This importer follows ISO/IEC 19775-1 13.3.4 instead.

Handled: Transform, Group, Switch, LOD (every level imported, the last one visible), Shape, Appearance, Material,
PhysicalMaterial, UnlitMaterial, ImageTexture (baseTexture, normalTexture, emissiveTexture, occlusionTexture,
texture), ElevationGrid, IndexedFaceSet (TextureCoordinate or MultiTextureCoordinate, one UV map per mapping),
Box, Sphere, Text with FontStyle, Viewpoint, DirectionalLight, Background, WorldInfo with Metadata nodes, DEF/USE.
PhysicalMaterial colours are taken as linear (as glTF does); classic Material and Background colours as display (sRGB)
values, which is how X_ITE shows them.
Skipped, with a note on the collection: sensors, interpolators, routes, scripts, ComposedShader (GLSL does not run
in Blender; its Appearance's material is used instead).
The writer emits X3D 4.0, Interchange profile plus Shape level 2: IndexedFaceSet, PhysicalMaterial (base colour
texture when the material has one), Viewpoint, DirectionalLight, Background, and a WorldInfo with MetadataSet
provenance when given. X3D is Y up and Blender Z up; both directions convert (x, y, z)_x3d = (x, z, -y)_blender.
"""
import json
import math
import os
import sys
import xml.etree.ElementTree as ET

import bpy
from mathutils import Matrix, Quaternion, Vector

TO_BLENDER = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))   # X3D Y-up -> Blender Z-up
TO_X3D = TO_BLENDER.inverted()


# ---------------------------------------------------------------- field parsing
def floats(s, default=()):
    if s is None:
        return list(default)
    return [float(x) for x in s.replace(",", " ").split()]


def ints(s):
    return [int(x) for x in (s or "").replace(",", " ").split()]


def mfstring(s):
    """X3D MFString: "a" "b c" -> ['a', 'b c'] (XML encoding)."""
    out, cur, inside, esc = [], [], False, False
    for ch in s or "":
        if esc:
            cur.append(ch)
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == '"':
            if inside:
                out.append("".join(cur))
                cur = []
            inside = not inside
        elif inside:
            cur.append(ch)
    return out if out or not (s or "").strip() else [s.strip()]


def srgb_to_linear(c):
    """Background and classic Material colours are display values; Blender's colour inputs are linear."""
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]


def boolean(s, default):
    return default if s is None else s.strip().lower() == "true"


def rotation_matrix(r):
    x, y, z, a = (floats(r) + [0, 0, 1, 0])[:4] if r else (0, 0, 1, 0)
    axis = Vector((x, y, z))
    if axis.length < 1e-12:
        return Matrix.Identity(4)
    return Matrix.Rotation(a, 4, axis.normalized())


def transform_matrix(el):
    """X3D Transform: T * C * R * SR * S * -SR * -C."""
    t = Matrix.Translation(floats(el.get("translation"), (0, 0, 0)))
    c = Matrix.Translation(floats(el.get("center"), (0, 0, 0)))
    r = rotation_matrix(el.get("rotation"))
    sr = rotation_matrix(el.get("scaleOrientation"))
    sx, sy, sz = floats(el.get("scale"), (1, 1, 1))
    s = Matrix.Diagonal((sx, sy, sz, 1.0))
    return t @ c @ r @ sr @ s @ sr.inverted() @ c.inverted()


# ---------------------------------------------------------------- import
class Importer:
    def __init__(self, path, collection, scene):
        self.path = os.path.abspath(path)
        self.dir = os.path.dirname(self.path)
        self.col = collection
        self.scene = scene
        self.root = ET.parse(path).getroot()
        self.defs = {el.get("DEF"): el for el in self.root.iter() if el.get("DEF")}
        self.cache = {}                              # DEF of geometry / material / image -> datablock
        self.skipped = {}
        self.cameras = {}
        self.count = 0

    def resolve(self, el):
        use = el.get("USE")
        return (self.defs.get(use, el), use) if use else (el, None)

    def note_skip(self, tag):
        self.skipped[tag] = self.skipped.get(tag, 0) + 1

    def run(self):
        scene_el = self.root.find("Scene")
        if scene_el is None:
            raise ValueError("no Scene element in " + self.path)
        self.walk(scene_el, Matrix.Identity(4), self.col)
        self.col["x3d_source"] = os.path.basename(self.path)
        if self.skipped:
            self.col["x3d_skipped_nodes"] = json.dumps(self.skipped)
        return self.col

    # -- grouping
    def walk(self, el, m, col):
        for child in el:
            self.node(child, m, col, top=el.tag == "Scene")

    def node(self, el, m, col, top=False):
        el, _ = self.resolve(el)
        tag = el.tag
        if tag == "Transform":
            self.walk(el, m @ transform_matrix(el), col)
        elif tag in ("Group", "StaticGroup", "Collision", "Anchor", "Billboard"):
            self.walk(el, m, col)
        elif tag == "Switch":
            kids = [c for c in el if not c.tag.startswith("Metadata")]
            which = int(el.get("whichChoice", "-1"))
            if 0 <= which < len(kids):
                self.node(kids[which], m, col)
        elif tag == "LOD":
            kids = [c for c in el if not c.tag.startswith("Metadata")]
            sub = bpy.data.collections.new((el.get("DEF") or "LOD") + " levels")
            col.children.link(sub)
            sub["x3d_lod_range"] = floats(el.get("range"))
            for i, k in enumerate(kids):
                before = set(sub.all_objects)
                self.node(k, m, sub)
                for ob in set(sub.all_objects) - before:
                    ob["x3d_lod_level"] = i
                    ob.hide_render = ob.hide_viewport = i != len(kids) - 1
        elif tag == "Shape":
            self.shape(el, m, col)
        elif tag == "Viewpoint":
            self.viewpoint(el, m, col)
        elif tag == "DirectionalLight":
            ob = self.light(el, m, col)
            if not top and not boolean(el.get("global"), False):
                ob["x3d_scoped"] = "lit only its own group in X3D; Blender lights are global"
        elif tag == "Background":
            self.background(el)
        elif tag == "WorldInfo":
            self.world_info(el)
        elif tag in ("NavigationInfo", "head", "component", "meta", "ROUTE"):
            pass
        elif tag.startswith("Metadata"):
            pass
        else:
            self.note_skip(tag)

    # -- leaves
    def shape(self, el, m, col):
        app = el.find("Appearance")
        geom = next((c for c in el if c.tag not in ("Appearance",) and not c.tag.startswith("Metadata")), None)
        if geom is None:
            return
        geom_el, use = self.resolve(geom)
        key = ("mesh", geom_el.get("DEF")) if geom_el.get("DEF") else None
        if geom_el.tag == "Text":
            ob = self.text(geom_el, col)
        else:
            me = self.cache.get(key) if key else None
            if me is None:
                me = self.geometry(geom_el)
                if me is None:
                    self.note_skip(geom_el.tag)
                    return
                if key:
                    self.cache[key] = me
            ob = bpy.data.objects.new(el.get("DEF") or geom_el.get("DEF") or geom_el.tag, me)
            col.objects.link(ob)
        ob.matrix_world = TO_BLENDER @ m
        if app is not None:
            mat = self.material(self.resolve(app)[0], geom_el)
            if mat is not None:
                if ob.type == "MESH" and ob.data.users > 1 and ob.data.materials:
                    ob.material_slots[0].link = "OBJECT"
                    ob.material_slots[0].material = mat
                else:
                    ob.data.materials.clear()
                    ob.data.materials.append(mat)
        self.count += 1

    def geometry(self, g):
        if g.tag == "ElevationGrid":
            return self.elevation_grid(g)
        if g.tag == "IndexedFaceSet":
            return self.indexed_face_set(g)
        if g.tag == "Box":
            return self.box(g)
        if g.tag == "Sphere":
            return self.sphere(g)
        return None

    def elevation_grid(self, g):
        """ISO/IEC 19775-1 13.3.4: vertex (i, j) at (i * xSpacing, height[i + j * xDimension], j * zSpacing);
        default texture coordinates (i / (xDimension - 1), j / (zDimension - 1))."""
        import numpy as np
        nx, nz = int(g.get("xDimension", "0")), int(g.get("zDimension", "0"))
        dx, dz = float(g.get("xSpacing", "1")), float(g.get("zSpacing", "1"))
        h = np.array(floats(g.get("height")), dtype=np.float64)
        if nx < 2 or nz < 2 or h.size != nx * nz:
            raise ValueError("ElevationGrid %s: %d heights for %d x %d" % (g.get("DEF"), h.size, nx, nz))
        X, Z = np.meshgrid(np.arange(nx) * dx, np.arange(nz) * dz)          # rows along z, columns along x
        co = np.stack([X.ravel(), h, Z.ravel()], axis=1)
        j, i = np.meshgrid(np.arange(nz - 1), np.arange(nx - 1), indexing="ij")
        v0 = (j * nx + i).ravel()
        quads = np.stack([v0, v0 + nx, v0 + nx + 1, v0 + 1], axis=1)        # +Y facing when ccw is TRUE
        if not boolean(g.get("ccw"), True):
            quads = quads[:, ::-1]
        tc = g.find("TextureCoordinate")
        if tc is not None:
            uv = np.array(floats(tc.get("point")), dtype=np.float64).reshape(-1, 2)
        else:
            uv = np.stack([(X / (dx * (nx - 1))).ravel(), (Z / (dz * (nz - 1))).ravel()], axis=1)
        me = self.mesh_from(g.get("DEF") or "ElevationGrid", co, quads, {"UVMap": (uv, quads)})
        self.shading(me, g)
        return me

    def indexed_face_set(self, g):
        import numpy as np
        coord = g.find("Coordinate")
        if coord is None:
            return None
        co = np.array(floats(coord.get("point")), dtype=np.float64).reshape(-1, 3)
        faces, face = [], []
        for k in ints(g.get("coordIndex")) + [-1]:
            if k < 0:
                if len(face) >= 3:
                    faces.append(face)
                face = []
            else:
                face.append(k)
        tci = ints(g.get("texCoordIndex"))
        uv_faces = []
        if tci:
            cur = []
            for k in tci + [-1]:
                if k < 0:
                    if len(cur) >= 3:
                        uv_faces.append(cur)
                    cur = []
                else:
                    cur.append(k)
        else:
            uv_faces = faces
        sets = {}
        mt = g.find("MultiTextureCoordinate")
        tcs = list(mt.findall("TextureCoordinate")) if mt is not None else [x for x in [g.find("TextureCoordinate")] if x is not None]
        for n, t in enumerate(tcs):
            name = t.get("mapping") or ("UVMap" if n == 0 else "UVMap.%03d" % n)
            sets[name] = (np.array(floats(t.get("point")), dtype=np.float64).reshape(-1, 2), uv_faces)
        if not boolean(g.get("ccw"), True):
            faces = [f[::-1] for f in faces]
            sets = {k: (v[0], [f[::-1] for f in v[1]]) for k, v in sets.items()}
        me = self.mesh_from(g.get("DEF") or "IndexedFaceSet", co, faces, sets)
        self.shading(me, g)
        return me

    def mesh_from(self, name, co, faces, uv_sets):
        import numpy as np
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(p) for p in co], [], [list(map(int, f)) for f in faces])
        for uvname, (pts, uv_faces) in uv_sets.items():
            layer = me.uv_layers.new(name=uvname)
            loop_uv = np.array([pts[k] for f in uv_faces for k in f], dtype=np.float32)
            if len(loop_uv) == len(me.loops):
                layer.data.foreach_set("uv", loop_uv.ravel())
        me.update()
        return me

    def shading(self, me, g):
        crease = float(g.get("creaseAngle", "0"))
        smooth = crease > 0.01
        me.polygons.foreach_set("use_smooth", [smooth] * len(me.polygons))
        me["x3d_creaseAngle"] = crease
        me["x3d_solid"] = boolean(g.get("solid"), True)

    def box(self, g):
        sx, sy, sz = [v / 2 for v in floats(g.get("size"), (2, 2, 2))]
        co = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz), (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]
        faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (3, 0, 4, 7)]
        me = bpy.data.meshes.new("Box")
        me.from_pydata(co, [], faces)
        return me

    def sphere(self, g):
        import bmesh
        r = float(g.get("radius", "1"))
        me = bpy.data.meshes.new("Sphere")
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=r)
        bm.to_mesh(me)
        bm.free()
        me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
        return me

    def text(self, g, col):
        fs = g.find("FontStyle")
        size = float(fs.get("size", "1")) if fs is not None else 1.0
        just = mfstring(fs.get("justify")) if fs is not None and fs.get("justify") else ["BEGIN"]
        cu = bpy.data.curves.new("Text", "FONT")
        cu.body = "\n".join(mfstring(g.get("string")))
        cu.size = size
        cu.align_x = {"BEGIN": "LEFT", "FIRST": "LEFT", "MIDDLE": "CENTER", "END": "RIGHT"}.get(just[0], "LEFT")
        minor = just[1] if len(just) > 1 else "FIRST"
        cu.align_y = {"FIRST": "TOP_BASELINE", "BEGIN": "TOP", "MIDDLE": "CENTER", "END": "BOTTOM"}.get(minor, "TOP_BASELINE")
        ob = bpy.data.objects.new("Text", cu)
        col.objects.link(ob)
        return ob

    def image(self, t, colorspace):
        t, _ = self.resolve(t)
        key = ("image", t.get("DEF") or t.get("url"), colorspace)
        if key in self.cache:
            return self.cache[key]
        img = None
        for u in mfstring(t.get("url")):
            p = u if os.path.isabs(u) else os.path.normpath(os.path.join(self.dir, u))
            if os.path.isfile(p):
                img = bpy.data.images.load(p, check_existing=True)
                img.colorspace_settings.name = colorspace
                break
        self.cache[key] = img
        return img

    def material(self, app, geom_el):
        mats = [c for c in app if c.tag in ("Material", "PhysicalMaterial", "UnlitMaterial", "TwoSidedMaterial")]
        if app.find("ComposedShader") is not None:
            self.note_skip("ComposedShader")
        if not mats:
            return None
        mel, _ = self.resolve(mats[0])
        key = ("material", mel.get("DEF") or ET.tostring(mel))
        if key in self.cache:
            return self.cache[key]
        name = mel.get("DEF") or app.get("DEF") or mel.tag
        mat = bpy.data.materials.new(name)
        if bpy.app.version < (5, 0, 0):
            mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        out = nt.nodes.get("Material Output")
        rgb = lambda s, d: (*floats(s, d)[:3], 1.0)
        textures = {c.get("containerField", "texture"): c for c in mel if c.tag == "ImageTexture"}
        textures.update({c.get("containerField", "texture"): c for c in app if c.tag == "ImageTexture"})
        if mel.tag == "PhysicalMaterial":
            bsdf.inputs["Base Color"].default_value = rgb(mel.get("baseColor"), (1, 1, 1))
            bsdf.inputs["Metallic"].default_value = float(mel.get("metallic", "1"))
            bsdf.inputs["Roughness"].default_value = float(mel.get("roughness", "1"))
            emis = floats(mel.get("emissiveColor"), (0, 0, 0))
        elif mel.tag == "UnlitMaterial":
            emis = floats(mel.get("emissiveColor"), (1, 1, 1))
            bsdf.inputs["Base Color"].default_value = (0, 0, 0, 1)
        else:                                        # classic Material: display colours, decoded to linear
            bsdf.inputs["Base Color"].default_value = (*srgb_to_linear(floats(mel.get("diffuseColor"), (0.8, 0.8, 0.8))[:3]), 1.0)
            bsdf.inputs["Roughness"].default_value = 1.0 - min(1.0, float(mel.get("shininess", "0.2")))
            bsdf.inputs["Metallic"].default_value = 0.0
            emis = srgb_to_linear(floats(mel.get("emissiveColor"), (0, 0, 0))[:3])
        if any(e > 0 for e in emis):
            bsdf.inputs["Emission Color"].default_value = (*emis[:3], 1.0)
            bsdf.inputs["Emission Strength"].default_value = 1.0
        transparency = float(mel.get("transparency", "0"))
        if transparency > 0:
            bsdf.inputs["Alpha"].default_value = 1.0 - transparency
        y = 300
        for field, (sock, cs) in {"baseTexture": ("Base Color", "sRGB"), "texture": ("Base Color", "sRGB"),
                                  "emissiveTexture": ("Emission Color", "sRGB")}.items():
            if field in textures:
                img = self.image(textures[field], cs)
                if img:
                    tn = self.tex_node(nt, img, textures[field], mel.get(field + "Mapping"), (-400, y))
                    if sock == "Base Color" and tuple(bsdf.inputs["Base Color"].default_value)[:3] != (1.0, 1.0, 1.0):
                        mul = nt.nodes.new("ShaderNodeMix")
                        mul.data_type, mul.blend_type, mul.location = "RGBA", "MULTIPLY", (-150, y)
                        ids = {s.identifier: s for s in mul.inputs}
                        ids["Factor_Float"].default_value = 1.0
                        ids["A_Color"].default_value = bsdf.inputs["Base Color"].default_value
                        nt.links.new(tn.outputs["Color"], ids["B_Color"])
                        nt.links.new(next(o for o in mul.outputs if o.identifier == "Result_Color"), bsdf.inputs[sock])
                    else:
                        nt.links.new(tn.outputs["Color"], bsdf.inputs[sock])
                    y -= 280
        if "normalTexture" in textures:
            img = self.image(textures["normalTexture"], "Non-Color")
            if img:
                tn = self.tex_node(nt, img, textures["normalTexture"], mel.get("normalTextureMapping"), (-400, y))
                nm = nt.nodes.new("ShaderNodeNormalMap")
                nm.location = (-150, y)
                if mel.get("normalTextureMapping"):
                    nm.uv_map = mel.get("normalTextureMapping")
                nm.inputs["Strength"].default_value = float(mel.get("normalScale", "1"))
                nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
                nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
        mat["x3d_material"] = mel.tag
        if mel.get("occlusionStrength") and "occlusionTexture" in textures:
            mat["x3d_occlusion"] = "occlusionTexture kept as a reference; Blender computes occlusion itself"
        self.cache[key] = mat
        return mat

    def tex_node(self, nt, img, t_el, mapping, loc):
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image, tn.location = img, loc
        t_el, _ = self.resolve(t_el)
        repeat = boolean(t_el.get("repeatS"), True) and boolean(t_el.get("repeatT"), True)
        tn.extension = "REPEAT" if repeat else "EXTEND"
        if mapping:
            uvn = nt.nodes.new("ShaderNodeUVMap")
            uvn.uv_map, uvn.location = mapping, (loc[0] - 220, loc[1])
            nt.links.new(uvn.outputs["UV"], tn.inputs["Vector"])
        return tn

    def viewpoint(self, el, m, col):
        name = el.get("DEF") or "Viewpoint"
        cam = bpy.data.cameras.new(name)
        fov = float(el.get("fieldOfView", str(math.pi / 4)))
        landscape = self.scene.render.resolution_x >= self.scene.render.resolution_y
        cam.sensor_fit = "VERTICAL" if landscape else "HORIZONTAL"   # X3D: the smaller dimension
        cam.angle = fov
        cam.clip_start, cam.clip_end = 0.005, 500.0
        ob = bpy.data.objects.new(name, cam)
        col.objects.link(ob)
        local = Matrix.Translation(floats(el.get("position"), (0, 0, 10))) @ rotation_matrix(el.get("orientation"))
        ob.matrix_world = TO_BLENDER @ m @ local
        ob["x3d_description"] = el.get("description", "")
        self.cameras[name] = ob
        if self.scene.camera is None:
            self.scene.camera = ob

    def light(self, el, m, col):
        name = el.get("DEF") or "DirectionalLight"
        lt = bpy.data.lights.new(name, "SUN")
        lt.energy = float(el.get("intensity", "1"))                # X_ITE and Cycles agree: albedo x E / pi
        lt.color = floats(el.get("color"), (1, 1, 1))[:3]
        ob = bpy.data.objects.new(name, lt)
        col.objects.link(ob)
        d = (TO_BLENDER @ m).to_3x3() @ Vector(floats(el.get("direction"), (0, 0, -1)))
        ob.rotation_mode = "QUATERNION"
        ob.rotation_quaternion = d.normalized().to_track_quat("-Z", "Y")
        return ob

    def background(self, el):
        sky = srgb_to_linear(floats(el.get("skyColor"), (0, 0, 0))[:3])
        w = self.scene.world or bpy.data.worlds.new("World")
        if bpy.app.version < (5, 0, 0):
            w.use_nodes = True
        bg = w.node_tree.nodes.get("Background")
        if bg:
            bg.inputs["Color"].default_value = (*sky, 1.0)
        self.scene.world = w

    def world_info(self, el):
        meta = {"title": el.get("title"), "info": mfstring(el.get("info"))}
        for ms in el:
            if ms.tag.startswith("Metadata"):
                meta[ms.get("name") or ms.tag] = metadata_to_py(ms)
        self.scene["x3d_world_info"] = json.dumps(meta, ensure_ascii=False)
        txt = bpy.data.texts.new("X3D WorldInfo " + os.path.basename(self.path))
        txt.write(json.dumps(meta, ensure_ascii=False, indent=1))


def metadata_to_py(el):
    if el.tag == "MetadataSet":
        out = {"reference": el.get("reference")}
        for c in el:
            if c.tag.startswith("Metadata"):
                out[c.get("name") or c.tag] = metadata_to_py(c)
        return out
    if el.tag in ("MetadataDouble", "MetadataFloat"):
        v = floats(el.get("value"))
    elif el.tag == "MetadataInteger":
        v = ints(el.get("value"))
    elif el.tag == "MetadataBoolean":
        v = [x.lower() == "true" for x in (el.get("value") or "").split()]
    else:
        v = mfstring(el.get("value"))
    return {"value": v[0] if len(v) == 1 else v, "reference": el.get("reference")}


def import_x3d(path, scene=None, name=None):
    """Import an X3D file into a new collection of the scene; returns (collection, {viewpoint DEF: camera})."""
    scene = scene or bpy.context.scene
    col = bpy.data.collections.new(name or os.path.splitext(os.path.basename(path))[0])
    scene.collection.children.link(col)
    imp = Importer(path, col, scene)
    imp.run()
    print("imported %s: %d shapes, %d viewpoints; skipped %s" % (os.path.basename(path), imp.count, len(imp.cameras), imp.skipped or "nothing"))
    return col, imp.cameras


# ---------------------------------------------------------------- export
def q(s):
    return "'" + str(s).replace("&", "&amp;").replace("'", "&apos;").replace("<", "&lt;") + "'"


def def_name(s):
    """A DEF that X3D's naming conventions accept (no dots or spaces, which break ClassicVRML ROUTEs)."""
    import re
    s = re.sub(r"[^A-Za-z0-9_]", "_", s)
    return s if s and not s[0].isdigit() else "_" + s


def nums(vals, fmt="%.6g"):
    return " ".join(fmt % v for v in vals)


def provenance_xml(prov, indent="   "):
    """prov: {constant id: {value, unit, tag, citations}} -> MetadataSet lines, one MetadataDouble or String each."""
    lines = [indent + "<MetadataSet containerField='metadata' name='shroud_provenance' reference='data/constants.json'>"]
    for cid, c in prov.items():
        ref = "id: %s; tag: %s; cite: %s; unit: %s" % (cid, c.get("tag"), ",".join(c.get("citations") or []), c.get("unit"))
        name = cid.replace(".", "_")
        if isinstance(c.get("value"), (int, float)):
            lines.append(indent + " <MetadataDouble name=%s reference=%s value='%s'/>" % (q(name), q(ref), c["value"]))
        else:
            lines.append(indent + " <MetadataString name=%s reference=%s value=%s/>" % (q(name), q(ref), q('"%s"' % c.get("value"))))
    lines.append(indent + "</MetadataSet>")
    return lines


def base_texture(mat):
    """The image feeding Base Color, through any Mix, Color Ramp-free chain; None for a plain colour."""
    if not mat or not mat.node_tree:
        return None
    bsdf = next((n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    if not bsdf or not bsdf.inputs["Base Color"].is_linked:
        return None
    stack = [bsdf.inputs["Base Color"].links[0].from_node]
    while stack:
        n = stack.pop()
        if n.bl_idname == "ShaderNodeTexImage" and n.image:
            return n.image
        stack += [l.from_node for i in n.inputs for l in i.links]
    return None


def export_x3d(path, objects=None, scene=None, title="Blender scene", provenance=None, info=()):
    """Write meshes (evaluated, world space), cameras and suns as X3D 4.0. Returns the path."""
    import numpy as np
    scene = scene or bpy.context.scene
    objects = objects if objects is not None else [o for o in scene.objects if o.visible_get() or o.type == "CAMERA"]
    out_dir = os.path.dirname(os.path.abspath(path))
    dg = bpy.context.evaluated_depsgraph_get()
    body = []
    for ob in objects:
        if ob.type == "CAMERA":
            mw = TO_X3D @ ob.matrix_world
            loc, rot, _ = mw.decompose()
            axis, angle = rot.to_axis_angle()
            cam = ob.data
            aspect = scene.render.resolution_x / max(1, scene.render.resolution_y)
            fov = cam.angle_y if aspect >= 1 else cam.angle_x       # the smaller dimension, as X3D defines it
            body.append("  <Viewpoint DEF=%s description=%s position='%s' orientation='%s %.6g' fieldOfView='%.6g'/>"
                        % (q(def_name(ob.name)), q(ob.name), nums(loc), nums(axis), angle, fov))
        elif ob.type == "LIGHT" and ob.data.type == "SUN":
            d = (TO_X3D @ ob.matrix_world).to_3x3() @ Vector((0, 0, -1))
            body.append("  <DirectionalLight DEF=%s direction='%s' intensity='%.6g' color='%s'/>"
                        % (q(def_name(ob.name)), nums(d.normalized()), ob.data.energy, nums(ob.data.color)))
        elif ob.type == "MESH":
            ev = ob.evaluated_get(dg)
            me = ev.to_mesh()
            mw = TO_X3D @ ob.matrix_world
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3) @ np.array(mw.to_3x3()).T + np.array(mw.translation)
            uv = me.uv_layers.active
            for slot in range(max(1, len(me.materials))):
                polys = [p for p in me.polygons if p.material_index == slot]
                if not polys:
                    continue
                mat = me.materials[slot] if me.materials else None
                ci = " ".join(" ".join(str(v) for v in p.vertices) + " -1" for p in polys)
                tex_xml, uv_xml = "", ""
                img = base_texture(mat)
                if uv is not None:
                    loops = [i for p in polys for i in p.loop_indices]
                    pts = np.array([tuple(uv.data[i].uv) for i in loops])
                    uv_xml = "<TextureCoordinate point='%s'/>" % nums(pts.ravel(), "%.6g")
                    k, tci = 0, []
                    for p in polys:
                        tci.append(" ".join(str(k + n) for n in range(p.loop_total)) + " -1")
                        k += p.loop_total
                    tci = " texCoordIndex='%s'" % " ".join(tci)
                else:
                    tci = ""
                if img is not None and uv is not None:
                    rel = os.path.relpath(bpy.path.abspath(img.filepath), out_dir).replace(os.sep, "/")
                    tex_xml = "<ImageTexture containerField='baseTexture' url='\"%s\"'/>" % rel
                bsdf = next((n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None) if mat and mat.node_tree else None
                base = list(bsdf.inputs["Base Color"].default_value)[:3] if bsdf and not img else [1, 1, 1]
                rough = bsdf.inputs["Roughness"].default_value if bsdf else 0.9
                metal = bsdf.inputs["Metallic"].default_value if bsdf else 0.0
                smooth = any(p.use_smooth for p in polys)
                body.append("  <Shape DEF=%s><Appearance><PhysicalMaterial baseColor='%s' metallic='%.4g' roughness='%.4g'>%s</PhysicalMaterial></Appearance>"
                            % (q(def_name(ob.name + ("_%d" % slot if slot else ""))), nums(base, "%.4g"), metal, rough, tex_xml))
                body.append("   <IndexedFaceSet solid='false' creaseAngle='%s' coordIndex='%s'%s><Coordinate point='%s'/>%s</IndexedFaceSet></Shape>"
                            % ("1.57" if smooth else "0", ci, tci, nums(co.ravel(), "%.6g"), uv_xml))
            ev.to_mesh_clear()
    if scene.world and scene.world.node_tree and scene.world.node_tree.nodes.get("Background"):
        c = scene.world.node_tree.nodes["Background"].inputs["Color"].default_value
        body.insert(0, "  <Background skyColor='%s'/>" % nums(list(c)[:3], "%.4g"))
    wi = ["  <WorldInfo title=%s info=%s>" % (q(title), q(" ".join('"%s"' % s.replace('"', "'") for s in info)))]
    wi += provenance_xml(provenance) if provenance else []
    wi.append("  </WorldInfo>")
    doc = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<!DOCTYPE X3D PUBLIC 'ISO//Web3D//DTD X3D 4.0//EN' 'https://www.web3d.org/specifications/x3d-4.0.dtd'>",
           "<X3D profile='Interchange' version='4.0' xmlns:xsd='http://www.w3.org/2001/XMLSchema-instance' "
           "xsd:noNamespaceSchemaLocation='https://www.web3d.org/specifications/x3d-4.0.xsd'>",
           " <head>", "  <component name='Shape' level='2'/>",
           "  <meta name='title' content=%s/>" % q(title),
           "  <meta name='generator' content='blender/x3d_io.py (Blender %s)'/>" % bpy.app.version_string,
           " </head>", " <Scene>"] + wi + body + [" </Scene>", "</X3D>", ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(doc))
    print("wrote", path)
    return path


def export_cloth(scene, path, data):
    """The cloth from build_shroud.py as X3D: the procedural linen cannot travel, so the cloth goes out with the
    D65 albedo map as its base texture (the dissolve and the weave are in x3d/shroud_cloth.x3d)."""
    cloth = scene.objects["Shroud"]
    keep = cloth.data.materials[0]
    proxy = bpy.data.materials.new("Shroud linen (D65 albedo)")
    if bpy.app.version < (5, 0, 0):
        proxy.use_nodes = True
    nt = proxy.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.92
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = bpy.data.images.load(data.path("maps/synthetic/albedo_d65_srgb.png"), check_existing=True)
    nt.links.new(tn.outputs["Color"], bsdf.inputs["Base Color"])
    cloth.data.materials[0] = proxy
    try:
        cams = [o for o in scene.objects if o.type == "CAMERA" and o.name != "Cam_walk"]
        suns = [o for o in scene.objects if o.type == "LIGHT"]
        export_x3d(path, [cloth] + cams + suns, scene, "Shroud of Turin: the cloth from Blender",
                   data.provenance(), ["Exported by blender/x3d_io.py from blender/build_shroud.py.",
                                       "Body image: synthetic stand-in (maps/synthetic), D65 albedo as the base texture."])
    finally:
        cloth.data.materials[0] = keep


# ---------------------------------------------------------------- command line
def main():
    import argparse
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else (argv[1:] if argv and argv[0].endswith(".py") else [])
    ap = argparse.ArgumentParser(prog="x3d_io.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    im = sub.add_parser("import")
    im.add_argument("x3d")
    im.add_argument("--save")
    im.add_argument("--render")
    im.add_argument("--viewpoint")
    im.add_argument("--samples", type=int, default=16)
    im.add_argument("--size", default="960x540")
    ex = sub.add_parser("export")
    ex.add_argument("x3d")
    a = ap.parse_args(argv)
    if a.cmd == "import":
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        w, h = (int(x) for x in a.size.lower().split("x"))
        scene.render.resolution_x, scene.render.resolution_y = w, h
        col, cams = import_x3d(a.x3d, scene)
        if a.viewpoint:
            if a.viewpoint not in cams:
                raise SystemExit("no Viewpoint %r; the file has %s" % (a.viewpoint, ", ".join(cams)))
            scene.camera = cams[a.viewpoint]
        if a.render:
            scene.render.engine = "CYCLES"
            scene.cycles.samples = a.samples
            scene.cycles.use_denoising = True
            scene.view_settings.view_transform = "Standard"
            scene.render.filepath = os.path.abspath(a.render)
            bpy.ops.render.render(write_still=True)
        if a.save:
            bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.save))
    else:
        export_x3d(os.path.abspath(a.x3d))


if __name__ == "__main__":
    main()
