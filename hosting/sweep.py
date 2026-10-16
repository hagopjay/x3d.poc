#!/usr/bin/env python3
"""Leak sweep for the public site. Usage: sweep.py SITE_DIR [--json out.json]. Exit 1 on any finding."""
import re, sys, os, json
RULES = [
 ("gcp-project", r"key-tokenizer|demo-418|iam\.gserviceaccount|\b2022900\d{5}\b"),
 ("secret", r"AIza[0-9A-Za-z_\-]{20,}|ya29\.[0-9A-Za-z_\-]{20,}|sk-[A-Za-z0-9]{20,}|BEGIN (?:RSA |EC )?PRIVATE KEY|hf_[A-Za-z0-9]{20,}"),
 ("private-link", r"claude\.ai/(?:code/)?artifact/[A-Za-z0-9\-]+"),
 ("vendor-name", r"\b(?:Anthropic|Claude|OpenAI|ChatGPT|GPT-?\d[\w.\-]*|Gemini|Vertex AI|Kimi|Nemotron|DeepSeek|Opus|Sonnet|Fable)\b"),
 ("cost-figure", r"(?<=[\s>(~])\$\s?\d[\d,.]*(?![\w'=)])"),
 ("title-office", r"\bPresident\b"),
 ("local-url", r"https?://(?:localhost|127\.0\.0\.1)|C:\\\\Users|/home/user|/mnt/project-files"),
 ("email", r"[\w.+-]+@(?:gmail|vt|outlook|yahoo)\.[a-z.]+"),
]
TEXT = {".html", ".js", ".css", ".json", ".x3d", ".md", ".txt", ".svg", ".xml"}
IMG = (b"caBX", b"c2pa", b"jumb", b"com.anthropic")
def main():
    root = sys.argv[1]; out = sys.argv[sys.argv.index("--json")+1] if "--json" in sys.argv else None
    hits = []
    for d, ds, fs in os.walk(root):
        if os.sep + "vendor" in d + os.sep: continue
        for f in fs:
            if os.path.splitext(f)[1].lower() not in TEXT or ".b64" in f or f.startswith("_admin"): continue
            p = os.path.join(d, f)
            try: s = open(p, encoding="utf-8", errors="ignore").read()
            except OSError: continue
            for name, rx in RULES:
                if name == "cost-figure" and f.endswith(".js"): continue
                for m in re.finditer(rx, s, re.I if name == "vendor-name" and False else 0):
                    a = max(0, m.start()-50); hits.append({"rule": name, "file": os.path.relpath(p, root), "match": m.group(0)[:60], "ctx": s[a:m.end()+50].replace("\n", " ")})
    LONG = re.compile(rb"com\.anthropic|anthropic\.claude|urn:c2pa|c2pa:manifest|xmlns:c2pa|contentauth|content credentials", re.I)   # unambiguous: any file
    SHORT = re.compile(rb"c2pa|caBX")       # exact case, raster/SVG only: in base64 text these 4-letter strings occur by chance
    for d, ds, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f)
            if os.path.islink(p) or f.startswith("_admin"): continue
            b = open(p, "rb").read(); m = LONG.search(b)
            img = b[:8] == b"\x89PNG\r\n\x1a\n" or b[:2] == b"\xff\xd8" or b"<svg" in b[:4096].lower()
            if not m and img: m = SHORT.search(b) or (re.search(b"jumb", b) if b[:8] == b"\x89PNG\r\n\x1a\n" or b[:2] == b"\xff\xd8" else None)
            if m: hits.append({"rule": "image-metadata", "file": os.path.relpath(p, root), "match": m.group(0).decode("latin1"), "ctx": "provenance marker in file bytes"})
    by = {}
    for h in hits: by[h["rule"]] = by.get(h["rule"], 0) + 1
    print("SWEEP", "FAIL" if hits else "PASS", json.dumps(by))
    for h in hits[:200]: print(f'  {h["rule"]:13} {h["file"]}: …{h["ctx"]}…')
    if out: json.dump(hits, open(out, "w"), indent=1)
    sys.exit(1 if hits else 0)
main()
