#!/usr/bin/env bash
# Build the static site into $1 (default: site/). Used by the Actions workflow and runnable locally.
set -euo pipefail
OUT="${1:-site}"; HERE="$(cd "$(dirname "$0")/.." && pwd)"
XITE_VERSION="16.4.3"
rm -rf "$OUT"; mkdir -p "$OUT/vendor/x_ite"
cp -r "$HERE/assets/." "$OUT/"
TMP="$(mktemp -d)"; ( cd "$TMP" && npm pack "x_ite@$XITE_VERSION" --silent >/dev/null && tar -xzf "x_ite-$XITE_VERSION.tgz" )
cp "$TMP/package/dist/x_ite.min.js" "$TMP/package/dist/x_ite.css" "$OUT/vendor/x_ite/"
cp -r "$TMP/package/dist/assets" "$OUT/vendor/x_ite/assets"
cp "$TMP/package/LICENSE.md" "$OUT/vendor/x_ite/" 2>/dev/null || true
# the browser only needs the minified components; drop the unminified copies and source maps
find "$OUT/vendor/x_ite/assets" \( -name '*.map' -o \( -name '*.js' ! -name '*.min.js' -path '*/components/*' \) \) -delete
python3 "$HERE/src/build.py" "$OUT"
cp "$HERE/Dockerfile" "$OUT/Dockerfile" 2>/dev/null || true
echo "site ready: $(find "$OUT" -type f | wc -l) files, $(du -sh "$OUT" | cut -f1)"
