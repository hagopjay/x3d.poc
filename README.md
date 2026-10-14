# x3d.poc: PolyXandria demos

A master index and eight live X3D demo pages (Gobbler, Pantheon, Khufu, Powers of ten, Drillfield, Two renderers,
Materials, Spec questions) on one shared engine. Plain X3D 4.0 and the 4.1 draft GaussianSplats node, rendered by X_ITE.

- `assets/`  scenes, textures and splat data (about 110 MB; the largest file is 10 MB).
- `src/`     the page generator and shared engine (`common.js`, `common.css`).
- `tools/`   `assemble.sh` builds the site; `smoke.js` loads each page headless; `shoot.js` and `poster2.js` take screenshots.
- `.github/workflows/pages.yml`  builds, smoke-tests, and deploys to GitHub Pages on a push to `main`.

Local build and run:

    bash tools/assemble.sh site && cd site && python3 -m http.server 8080

X_ITE 16.4.3 is fetched from npm at build time (pinned), not vendored.

## Before turning Pages on
GitHub Pages sites are reachable by anyone with the URL, even when the repository is private
(private Pages needs GitHub Enterprise Cloud). Pages is enabled in Settings > Pages > Source: GitHub Actions.
