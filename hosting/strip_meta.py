#!/usr/bin/env python3
"""strip_meta.py SITE_DIR: lossless removal of provenance metadata from images, in place (run on the scratch copy, never on the mount).
PNG: drops caBX (C2PA), eXIf, iTXt/tEXt/zTXt chunks. JPEG: drops APP1 (EXIF/XMP), APP11 (C2PA/JUMBF), APP13, COM. Pixels are not re-encoded."""
import os, struct, sys
PNG_DROP = {b"caBX", b"eXIf", b"iTXt", b"tEXt", b"zTXt"}
JPG_DROP = {0xE1, 0xEB, 0xED, 0xFE}
def png(b):
    if b[:8] != b"\x89PNG\r\n\x1a\n": return b
    o, i = [b[:8]], 8
    while i + 8 <= len(b):
        n = struct.unpack(">I", b[i:i+4])[0]; t = b[i+4:i+8]; e = i + 12 + n
        if t not in PNG_DROP: o.append(b[i:e])
        i = e
        if t == b"IEND": break
    return b"".join(o)
def jpg(b):
    if b[:2] != b"\xff\xd8": return b
    o, i = [b[:2]], 2
    while i + 4 <= len(b):
        if b[i] != 0xFF: o.append(b[i:]); break
        m = b[i+1]
        if m == 0xDA: o.append(b[i:]); break              # start of scan: copy the rest verbatim
        if m == 0xFF: o.append(b[i:i+1]); i += 1; continue
        n = struct.unpack(">H", b[i+2:i+4])[0]
        if m not in JPG_DROP: o.append(b[i:i+2+n])
        i += 2 + n
    else: o.append(b[i:])
    return b"".join(o)
n = c = 0
for d, _, fs in os.walk(sys.argv[1]):
    for f in fs:
        p = os.path.join(d, f); e = f.lower().rsplit(".", 1)[-1]
        if os.path.islink(p) or e not in ("png", "jpg", "jpeg"): continue
        b = open(p, "rb").read(); r = png(b) if e == "png" else jpg(b); n += 1
        if r != b: open(p, "wb").write(r); c += 1
print(f"strip_meta: {c} of {n} images stripped")
