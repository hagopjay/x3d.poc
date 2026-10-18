# x3d.poc: PolyXandria demos

A master index and eight live X3D demo pages (Gobbler, Pantheon, Khufu, Powers of ten, Drillfield, Two renderers,
Materials, Spec questions) on one shared engine. Plain X3D 4.0 and the 4.1 draft GaussianSplats node, rendered by X_ITE.

- `assets/`  scenes, textures and splat data (about 110 MB; the largest file is 10 MB).
- `assets/shroud/`  the Shroud of Turin as data: constants with sources and epistemic tags, a knowledge graph,
  five X3D 4.0 scenes with their own viewer page (served at `shroud/`), and Blender scripts. Its README says how to load it.
- `src/`     the page generator and shared engine (`common.js`, `common.css`).
- `tools/`   `assemble.sh` builds the site; `smoke.js` loads each page headless; `shoot.js` and `poster2.js` take screenshots.
- `.github/workflows/pages.yml`  builds, smoke-tests, and deploys to GitHub Pages on a push to `site/pages-actions`; pull requests into that branch are built and smoke-tested but never deployed.

Local build and run:

    bash tools/assemble.sh site && cd site && python3 -m http.server 8080

X_ITE 16.4.3 is fetched from npm at build time (pinned), not vendored.
