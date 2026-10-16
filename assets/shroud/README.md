# The Shroud of Turin as X3D and Blender data

Everything this project knows about the Shroud of Turin, moved out of its Unity documents into plain data that X3D
browsers, Blender and any script can read: a registry of 163 constants with their sources and epistemic tags, 32
corrections and retractions, a knowledge graph of 532 nodes, the maps that the physics produces (image field,
colour under seven lights, weave, visibility with distance), five X3D 4.0 scenes with a viewer page, and Blender
scripts that build the cloth from the same numbers.

> **The body image in this package is synthetic.** It is a mannequin draped and projected by the published
> distance rule (`tools/synthetic_body.py`), not a photograph and not a reconstruction of the man of the Shroud.
> The colours, the cloth, the weave and the viewing distance are measured; the figure is a stand-in until a
> licensed, registered photograph (the Enrie 1931 plates, for example) and hand-drawn masks replace
> `maps/synthetic/h_16bit.png`. Every scene and every render repeats this.

## Start here

| To | Do |
|---|---|
| See it | Serve this folder over HTTP (`python3 -m http.server 8000` in it) and open `index.html` at the address the server prints. Browsers refuse local files, so double-clicking does not work. X_ITE 16.4.3 comes from the site's copy or from jsDelivr. |
| Open a scene in another X3D browser | `x3d/*.x3d` are plain X3D 4.0 XML (Interchange profile plus the components each declares), tested in X_ITE 16.4.3. Other X3D 4.0 browsers should read them; the lab scene's GLSL shader is written for X_ITE, and a browser without it falls back to the scene's PhysicalMaterial. Textures are referenced relative to `x3d/`, so keep the folder layout. |
| Build it in Blender | `blender -b -P blender/build_shroud.py -- --render renders/blender` (or open the script in Blender's Text Editor and press Run Script). Tested with Blender 5.2. |
| Bring a scene into Blender | `blender -b -P blender/x3d_io.py -- import x3d/shroud_formation.x3d --save formation.blend` |
| Read the knowledge | `graph/INDEX.md` (readable), `graph/shroud.jsonld` (JSON-LD 1.1), `graph/nodes.csv` and `graph/edges.csv` (spreadsheets, Gephi), `data/constants.json` |
| Check a number | `data/constants.json`: every constant has an id, value, unit, tag, citations and the documents it came from. `data/corrections.json` says which documents disagreed and what won. |

## What is in the package

```
index.html                  the viewer: five scenes, distance readout, spectral lab, constants and corrections browsers
README.md                   this file
MANIFEST.json               every file with its size and SHA-256
data/
  constants.json            163 constants: id, value, unit, tag, citations, sources, notes; tags and precedence explained inside
  corrections.json          32 entries: contradictions resolved, citations fixed, claims retracted, values replaced
  bibliography/             references.json and references.bib (50 studies)
  dimensions.json           cloth size before and after the 2002 restoration, axes, UV and map conventions
  spectral/                 the JJE 1984 model, illuminants, and the LUT (JSON, CSV, 16-bit PNG, EXR): 256 h steps x 7 lights
  weave.json                3/1 herringbone, thread counts, band repeat, the tile the weave maps use
  height_model.json         h as cloth-body distance: linear (r2 0.60) and exponential readings, and the synthetic layout
  perception.json           the dissolve model: why the image is not seen inside about 1.8 m
  visibility_vs_distance.csv  detection probability against viewing distance, 0.25 to 12 m
  derive_report.json        the checks tools/derive.py ran against the published values (all pass)
graph/
  INDEX.md                  the graph in prose: node types, the lineage, claims grouped by epistemic tag
  shroud.jsonld, vocab.jsonld   532 nodes and 885 typed edges, schema.org terms plus a small vocabulary of our own
  nodes.csv, edges.csv      the same as tables
  curated.json              the hand-written part (relics, artworks, people, places, events, claims) the graph is built from
maps/
  synthetic/                h (16-bit), albedo and tint (sRGB), masks, height fields (EXR), and lod/: the image as perceived
                            at 0.5, 1.0, 1.4, 1.8, 2.5, 4 and 8 m, as D65 colour and as h
  weave/                    one 80 x 52 thread tile: height, slope-space normal map, occlusion, warp-on-top mask
x3d/
  shroud_cloth.x3d          the cloth on a wall; the image dissolves as you approach (LOD by distance)
  shroud_lab.x3d            one GLSL shader: the JJE colour under any light or at one wavelength, the dissolve per pixel, the weave
  shroud_relief.x3d         h as height, the 1976 VP-8 reading, with the face at true scale
  shroud_formation.x3d      a cloth resting on a body, coloured by the gap: the distance hypothesis made visible
  shroud_timeline.x3d       the graph's 59 dated nodes in the lanes of the lineage diagram, 200 to 2026
  scenes.json               what the viewer page reads: titles, viewpoints, controls
  textures/                 the one texture a scene makes for itself
blender/
  build_shroud.py           the cloth from the data: LUT material, dissolve, procedural herringbone, relief, cameras, renders
  x3d_io.py                 X3D in (all five scenes) and out (X3D 4.0 with provenance metadata)
renders/blender/            the test frames build_shroud.py rendered, and renders.json saying how
tools/
  derive.py                 data -> maps, with checks (needs numpy, scipy, Pillow, OpenEXR, colour-science)
  make_graph.py             curated.json + data -> graph/
  make_x3d.py               data + maps -> x3d/ (needs numpy, scipy, Pillow, OpenEXR)
  validate_x3d.py           X3D 4.0 schema, semantic and profile checks (lxml; x3d_mcp optional)
  shroudlib.py, synthetic_body.py   shared code and the synthetic forward model
```

## Measured, inferred, imagined

Every constant carries one tag. The ones that matter most:

| Tag | Count | Meaning |
|---|---|---|
| measured | 52 | Read off the cloth by an instrument and published (STURP 1978, Vial 1989, the 1988 radiocarbon labs, JJE 1984) |
| fitted | 11 | A parameter of a model fitted to measurements (the JJE reflectance coefficients, the 0.60 correlation) |
| derived | 19 | Computed from measured or fitted values by a stated formula (the LUT, the luminance of the image) |
| inferred | 3 | A reasoned reading of measurements that the measurements alone do not settle (h as cloth-body distance) |
| hypothesis, contested | 12 | Proposed and disputed (radiation hypotheses, the icon correspondences) |
| historical, tradition | 13 | From documents and traditions, dated and attributed |
| assumption, convention, standard | 21 | Choices this package makes (axes, units) and standards it uses (CIE illuminants, the sRGB transfer) |
| aesthetic | 4 | Display choices with no claim to truth (the relief exaggeration, the sepia ramp, the candle and LED lights) |
| superseded, retracted | 28 | Kept as entries, struck through in the viewer, so the history of the project stays readable |

When the project's documents disagreed, the build plan won, then the v3 corrections, then the Unity PRD v2.0, then
the Shader of the Shroud v3 page, then the proof of concept (lessons only). `data/corrections.json` lists each case.
Values that change what you see:

| Quantity | Value | Tag | Source |
|---|---|---|---|
| Cloth, before the 2002 restoration (the default) | 4.37 x 1.11 m | measured | the build plan; the state Enrie 1931 and STURP 1978 recorded (no primary citation in the project's sources) |
| Cloth, after the 2002 restoration | 4.415 x 1.137 m | measured | the 2002 restoration report |
| Thickness | 345 um | measured | JJE 1984 |
| Weave | 3/1 herringbone, 38.3 warp and 25.4 weft per cm, bands about 40 warps wide running lengthwise | measured | Vial 1989 |
| Reflectance | r(lambda, h) = (a + b lambda)[1 + c (lambda - lambda') h], a = -0.21, b = 1.02e-3 /nm, c = 7.78e-4 /nm, lambda' = 790 nm | fitted | JJE 1984 |
| Bare linen under D65 | linear sRGB (0.445, 0.344, 0.240), luminance 0.36 | derived | from the fit |
| Image intensity against cloth-body distance | range about 3.7 cm, linear fit r2 = 0.60 | measured | JJE 1984 |
| Closest distance at which the image is seen | about 1.8 m | measured | JJE 1984 |
| Dorsal image range | none measured; the package does not invent one | | |
| Laser fluence that colours linen like the image | 6 to 13 MW/cm2 (the PRD's GW figure was wrong) | measured | Di Lazzaro 2012 |

## What the scenes make visible

- **The dissolve.** The image is faint (a luminance contrast of about 18 % at its darkest) and coarse, and JJE 1984
  found it cannot be seen closer than about 1.8 m. `data/perception.json` explains that with the eye's contrast
  sensitivity (Mannos and Sakrison 1974) applied to band-pass contrast (Peli 1990): before any calibration it predicts
  2.75 m; one factor of 1.31 brings it to the measured 1.8 m. The cloth scene switches between seven precomputed
  textures by distance; the lab scene computes it per pixel; Blender interpolates the same seven fields by the
  camera's distance. Walk toward the face and it goes.
- **The colour.** The image is not a darker linen but a bluer loss: at the strongest point reflectance falls to 0.73
  at 440 nm and 0.91 at 680 nm. The lab shows it under daylight, tungsten, candle, oil lamp, halogen, the 1978 flash
  and museum LEDs, or at one wavelength from 380 to 700 nm.
- **The weave.** One 80 x 52 thread tile at the true pitch, 3/1 herringbone; the normal map is written in slope space
  so its mipmaps fade to flat cloth at a distance instead of striping. Blender draws the same twill procedurally
  from the thread counts.
- **The relief.** h read as height, as the VP-8 Image Analyzer first showed in 1976: the whole cloth at four times
  (an aesthetic choice) and the face at true scale (3.7 cm).
- **The formation hypothesis.** A cloth resting on a body, coloured by h = 1 - gap / 3.7 cm, beside the same cloth
  laid flat. It shows what the rule predicts, not a mechanism.
- **The lineage.** Relics, icons, paintings and photographs from the Image of Edessa to the 2008 gigapixel capture, in
  the lanes of the lineage diagram, with the claims and their tags in the graph.

The viewer's "Image contrast" chip multiplies the image's contrast around the bare linen by 3 for display (the
default) or shows it as measured (x1). The X3D files and the data are always physical.

## Blender

`blender/build_shroud.py` reads `data/` and `maps/` and builds two scenes:

- **Shroud**: the cloth hanging at eye height, dorsal image left, frontal right, heads meeting in the middle, on a
  dark wall. Its material, "Shroud linen (JJE 1984)", looks up the LUT row of the chosen light by h, takes h as
  perceived at the camera's distance (log-linear between the seven fields in `maps/synthetic/lod/`), and bumps the
  surface with a node group, "Herringbone 3/1 (Vial 1989)", that computes the twill from the thread counts
  (`--weave maps` uses the baked weave maps instead). Value nodes in the material named Illuminant, Display contrast,
  Dissolve and Weave are the controls. Cameras: the whole cloth from 6 m, the face from 6, 1.8, 1.0 and 0.5 m with the
  same field, 3 cm of linen from 6 cm, and Cam_walk, an animation from 8 m to 0.5 m (`--animation` renders it).
- **Shroud relief**: the same grid displaced by h (a Displace modifier, 3.7 cm x 4 by default) under a grazing light.

Options: `--illuminant`, `--contrast`, `--weave`, `--relief-exaggeration`, `--samples`, `--size`, `--format`,
`--save scene.blend`, `--export-x3d cloth.x3d`. `renders/blender/` holds the test frames rendered with
`--samples 64 --size 960x540 --format jpeg` (Cycles, CPU) and `renders.json`, which records how.

`blender/x3d_io.py` imports the five scenes (geometry, materials with their textures and UV sets, text, viewpoints as
cameras, lights, background, and the WorldInfo metadata as a text block and a scene property) and exports meshes,
cameras and suns as X3D 4.0 with a MetadataSet of the constants used. Exports pass `tools/validate_x3d.py`.

### Notes for the X3D Blender I/O add-on

Three things found while testing the X3D 4.0 fork of Blender's X3D add-on (x3d-blender-io 2.6.1) against these files:

1. **ElevationGrid import scrambles non-square grids.** `importMesh_ElevationGrid` lists vertices x-major
   (`for x … for z`) but indexes faces z-major (`z * x_dim + x`). The two agree only when xDimension equals zDimension;
   a 3 x 5 test grid comes back with all eight faces wrong, and every height field here is non-square. Building the
   vertex list z-major (`for z … for x`) fixes it. `x3d_io.py` imports ElevationGrid itself for this reason.
2. **A textured base colour is exported darker.** When Base Color is linked to an image, the exporter writes the
   socket's unlinked default (0.8) as `baseColor`, and X3D multiplies the texture by it. glTF exporters write 1 there.
3. **Lights made in Blender are capped at intensity 1** by design (documented in `extract.py`). A sun of 3.4 W/m2
   leaves as 1.0, so a scene lit for Cycles comes out darker in a browser. `x3d_io.py` writes the sun's strength as
   the intensity: Cycles and X_ITE both shade Lambert surfaces as albedo x E / pi, so the two then agree.

## Rebuilding and checking

```
python3 tools/derive.py                      # maps and data/derive_report.json (about a minute)
python3 tools/derive.py --h measured_h.png   # the same from a measured h map (16-bit, 1024 x 4096, rows from t = 1)
python3 tools/make_graph.py                  # graph/
python3 tools/make_x3d.py                    # x3d/
python3 tools/validate_x3d.py --xsd x3d-4.0.xsd          # or --x3d-mcp path/to/x3d_mcp/src for semantic checks too
```

What was checked before this package was published:

- `tools/derive.py`: ten checks against published values (the linen and image colours, luminance, density,
  reflectance ratios at 440, 550 and 680 nm, linearity of the LUT); all pass.
- All five scenes validate against the X3D 4.0 schema, and pass x3d_mcp's semantic checks (DEF/USE, routes,
  containerField, tuple counts) and its profile check (every node covered by the profile and component statements).
- The viewer page loads each scene in headless Chromium with X_ITE 16.4.3; the distance readout reads 100 % at 6 m,
  50 % at 1.8 m and 6 % at 0.3 m, and the image fades on screen accordingly.
- Blender 5.2 builds both scenes and renders the frames in `renders/blender/`; `x3d_io.py` imports all five scenes
  and its export validates.

## What stays in Unity form

This package carries the science and the data; the Unity documents keep the runtime design, and nothing was deleted.
Left where it is, for the return to URP and HDRP:

- Unity PRD v2.0 (`unity/`): the URP render features (photographic negative, VP-8 terrain grid, X-ray hypothesis view,
  holographic sub-modes, UV fluorescence), evidence layers as decals, the triptych, mode transitions and the experience
  orchestrator; `ImageFormation.compute` with its four dose-against-distance models and energy bookkeeping; the
  biophoton VFX Graph, body dissolve, VAT and XPBD cloth, the resurrection event director, the additive audio synth
  (430.9 Hz and 1412.8 Hz) and the narrative schema. The HDRP fork document was never uploaded.
- The v3 collateral (`unity/v3-collateral/`): its numbers are in `data/` (the LUT here is the same bake), its
  directions (Mitsuba 3 inverse rendering, the image-formation laboratory, the endmember-abundance model) are not built.
- Shader of the Shroud v3 and its Unity 6.3 port (`shader-of-the-shroud/`): the palette cycling, CRT stage, halftone,
  fractal veil, fringe, rainbow and anaglyph modes are display effects and stay there. Its spectral palette, height
  model and weave counts are in `data/`.

## Licence and sources

Data, maps, scenes and renders: CC BY 4.0. Code in `tools/` and `blender/`: MIT. The synthetic figure is generated
by `tools/synthetic_body.py`; no photograph of the Shroud is included. Sources are in
`data/bibliography/references.bib`; each constant names the ones it rests on.
