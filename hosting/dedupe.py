#!/usr/bin/env python3
"""dedupe.py OUT/v: replace byte-identical files (>= 64 KB) with relative symlinks to the copy in the NEWEST release,
so keeping every release costs little. The server never resolves symlinks, so URLs are unchanged."""
import os, sys, hashlib
v = sys.argv[1]; rels = sorted((d for d in os.listdir(v)), key=int, reverse=True)
seen = {}; saved = 0; n = 0
for r in rels:
    for d, _, fs in os.walk(os.path.join(v, r)):
        for f in fs:
            p = os.path.join(d, f)
            if os.path.islink(p) or os.path.getsize(p) < 65536: continue
            h = hashlib.sha256(open(p, 'rb').read()).hexdigest()
            if h in seen:
                saved += os.path.getsize(p); os.remove(p); os.symlink(os.path.relpath(seen[h], d), p); n += 1
            else: seen[h] = p
print('dedupe: %d files -> symlinks, %.0f MB saved' % (n, saved / 1e6))
