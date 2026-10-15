#!/usr/bin/env bash
# build.sh VERSION OUTDIR  -- assemble, inject, sweep. Earlier releases are fetched from the bucket-less image history:
# pass PREV=/path/to/previous/site to carry every earlier v/N forward untouched.
set -euo pipefail
V="${1:?version number}"; OUT="${2:?outdir}"; HERE="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$OUT"; mkdir -p "$OUT/v"
TMP="$(mktemp -d)"; bash "$HERE/tools/assemble.sh" "$TMP/s" >/dev/null
rm -f "$TMP/s/Dockerfile"
python3 "$HERE/hosting/inject.py" "$TMP/s"
cp "$HERE/hosting/beacon.js" "$TMP/s/_b.js.src"; mv "$TMP/s/_b.js.src" "$TMP/s/_b.js"
python3 "$HERE/hosting/sweep.py" "$TMP/s"                       # blocking: nonzero exit stops the build
mv "$TMP/s" "$OUT/v/$V"
if [ -n "${PREV:-}" ] && [ -d "$PREV/v" ]; then for d in "$PREV"/v/*; do n="$(basename "$d")"; [ "$n" = "$V" ] && { echo "refusing to overwrite v/$n"; exit 2; }; cp -a "$d" "$OUT/v/$n"; done; fi
# root = newest release, as symlinks into v/$V (no second copy of 120 MB)
for f in "$OUT/v/$V"/*; do ln -s "v/$V/$(basename "$f")" "$OUT/$(basename "$f")"; done
cp "$HERE/hosting/admin.html" "$OUT/_admin.html"
echo "release v$V built: $(du -shL "$OUT" | cut -f1)"
