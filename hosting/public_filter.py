#!/usr/bin/env python3
"""public_filter.py DIR: neutralise vendor/model names in exhibit copies (never edits the originals). Prints counts per rule."""
import os, re, sys
RULES = [
 (r"Gemini 3\.1 Pro and 3\.8 Flash on Vertex(?: AI)?", "large language models"),
 (r"Gemini 3\.8 Flash on Vertex(?: AI)?(?: \([^)]*\))?", "a large language model"),
 (r"Gemini 3\.8 Flash via Vertex", "a large language model"),
 (r"live Gemini call", "live model call"),
 (r"Gemini 3\.1 Pro|Gemini 3\.8 Flash", "a large language model"),
 (r"Vertex AI|(?<=on )Vertex\b|(?<=via )Vertex\b", "a cloud model service"),
 (r"Gemini", "the model"),
 (r'<meta name="creator" content="OpenAI Codex" />\s*', ""),
 (r"OpenAI Codex", "an AI coding assistant"),
]
counts = {}
for d, _, fs in os.walk(sys.argv[1]):
    if any(os.sep + x + os.sep in d + os.sep for x in ("vendor", "lib", "x_ite", "scene")): continue
    for f in fs:
        if os.path.splitext(f)[1].lower() not in (".html", ".x3d", ".json", ".md", ".txt", ".js") or ".b64" in f: continue
        p = os.path.join(d, f); s = o = open(p, encoding="utf-8", errors="ignore").read()
        for rx, rep in RULES:
            s, n = re.subn(rx, rep, s)
            if n: counts[rx] = counts.get(rx, 0) + n
        if s != o: open(p, "w", encoding="utf-8").write(s)
print("filter:", sum(counts.values()), "replacements", counts)
