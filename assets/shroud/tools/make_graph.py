#!/usr/bin/env python3
"""Build the knowledge graph: graph/curated.json + data/constants.json + data/corrections.json + the bibliography
-> graph/shroud.jsonld (JSON-LD 1.1), graph/vocab.jsonld, graph/nodes.csv, graph/edges.csv, graph/INDEX.md.

    python3 tools/make_graph.py            # build and check (every edge must land on a node)
    python3 tools/make_graph.py --rdflib   # also parse the JSON-LD with rdflib and run the example queries

Ids are 'kind/slug'; in RDF they become urn:shroud:kind/slug, with properties in urn:shroud:vocab: and
schema:name / schema:description for labels.
"""
import argparse
import csv
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)

CLASSES = {
    "Relic": "A physical object venerated or studied as a relic (the Shroud, the Sudarium, the Mandylion).",
    "Artwork": "A painting, mosaic, icon, coin, engraving, medal or building.",
    "Photograph": "A photographic record of a relic.",
    "Person": "A person, legendary or historical, or an author.",
    "Organization": "A family, team, laboratory, religious community or standards body.",
    "Place": "A city, monastery, museum or laboratory site.",
    "Event": "A dated event.",
    "Concept": "An iconographic type, legend, method or idea.",
    "Claim": "A statement with an epistemic tag: measured, inferred, contested, tradition, unsupported or retracted.",
    "Study": "A publication or report from the bibliography.",
    "Quantity": "A constant from data/constants.json, with value, unit, tag and citations.",
    "Correction": "An entry of data/corrections.json: a contradiction resolved, a citation fixed, a claim retracted.",
    "Document": "A project document that a constant was taken from (build plan, v3 corrections, PRD, web page).",
    "Dataset": "A file of this package.",
}
PROPS = {
    "locatedAt": "where it is or was kept", "heldBy": "who holds or held it", "derivesFrom": "iconographic or legendary descent",
    "branchOf": "a branch of the lineage diagram", "about": "what a claim, concept or dataset concerns",
    "describedIn": "the standard scholarly treatment", "proposedBy": "who proposed a claim or method",
    "supportedBy": "a study supporting the claim", "disputedBy": "a study or person disputing the claim",
    "answeredBy": "a reply to the dispute", "examinedBy": "a study that examined the claim", "madeBy": "artist or maker",
    "instanceOf": "the type a work belongs to", "depicts": "what a work shows", "commissionedBy": "patron",
    "approvedBy": "who approved it", "houses": "a building housing a relic", "exhibitedAt": "where it was exhibited",
    "foundAt": "where it was found", "takenBy": "photographer", "photographs": "the subject of a photograph",
    "basedOn": "a source image", "happenedAt": "where an event happened", "involves": "who or what took part",
    "recordedAs": "the registry constant that records it", "recordedBy": "who recorded it", "usesData": "data a dataset uses",
    "author": "an author of a study", "cites": "a study a constant or correction cites", "supersedes": "an older value it replaces",
    "affects": "a constant a correction changed", "source": "the project document it was taken from",
}
LITERALS = ["tag", "lane", "date", "start", "end", "value", "unit", "group", "prdStatus", "note", "kind", "was", "now",
            "decidedBy", "year", "container", "volume", "issue", "page", "doi", "url", "verified", "path", "family", "initials"]


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build(pkg):
    cur = load(os.path.join(pkg, "graph", "curated.json"))
    cons = load(os.path.join(pkg, "data", "constants.json"))
    corr = load(os.path.join(pkg, "data", "corrections.json"))
    refs = load(os.path.join(pkg, "data", "bibliography", "references.json"))
    nodes, edges = {}, []

    def add(n):
        if n["id"] in nodes:
            raise SystemExit("duplicate node " + n["id"])
        nodes[n["id"]] = n

    def link(s, p, o, **kw):
        e = {"s": s, "p": p, "o": o}
        e.update({k: v for k, v in kw.items() if v})
        edges.append(e)

    for n in cur["nodes"]:
        add(dict(n))
    for e in cur["edges"]:
        link(e["s"], e["p"], e["o"], tag=e.get("tag"), note=e.get("note"))

    # documents
    for k, v in cons["sources"].items():
        add({"id": "doc/" + k, "type": "Document", "name": v if isinstance(v, str) else v.get("title", k), "tag": "convention"})

    # bibliography: studies and their authors
    alias = {}
    for n in nodes.values():
        if n.get("bib_alias"):
            alias[tuple(n["bib_alias"])] = n["id"]
    special = {"STURP": "org/sturp"}
    for r in refs:
        year = (r.get("issued") or {}).get("date-parts", [[None]])[0][0]
        fams = [a["family"] for a in r.get("author", []) if a["family"] != "et al."]
        etal = len(fams) > 2 or any(a["family"] == "et al." for a in r.get("author", []))
        who = (fams[0] + " et al.") if etal and fams else " and ".join(fams)
        label = r.get("title") or ("%s %s" % (who, year or "")).strip()
        n = {"id": "ref/" + r["id"], "type": "Study", "name": label, "tag": "standard" if r["type"] == "standard" else "historical",
             "year": year, "container": r.get("container-title"), "volume": r.get("volume"), "issue": r.get("issue"),
             "page": r.get("page"), "doi": r.get("DOI"), "url": r.get("URL"), "verified": r.get("x-verified"), "note": r.get("note")}
        add({k: v for k, v in n.items() if v is not None})
        for a in r.get("author", []):
            fam, ini = a["family"], a.get("given", "")
            if fam == "et al.":
                continue
            pid = alias.get((fam, ini)) or special.get(fam)
            if fam == "CIE":
                pid = "org/cie"
                if pid not in nodes:
                    add({"id": pid, "type": "Organization", "name": "CIE (International Commission on Illumination)", "tag": "standard"})
            if not pid:
                pid = "person/" + slug(fam) + ("-" + slug(ini) if ini else "")
                if pid not in nodes:
                    add({"id": pid, "type": "Person", "name": (fam + (", " + ini if ini else "")), "tag": "historical",
                         "family": fam, "initials": ini or None, "note": "Bibliography author; initials as given in the sources."})
            link("ref/" + r["id"], "author", pid)

    # constants
    for c in cons["constants"]:
        v = c["value"]
        n = {"id": "constant/" + c["id"], "type": "Quantity", "name": c["label"], "tag": c["tag"], "group": c["group"],
             "value": v if isinstance(v, (int, float, str)) else json.dumps(v, ensure_ascii=False), "unit": c["unit"],
             "prdStatus": c.get("prd_status"), "note": c.get("note") or None}
        add({k: x for k, x in n.items() if x is not None})
        for r in c["citations"]:
            link(n["id"], "cites", "ref/" + r)
        for s in c["sources"]:
            link(n["id"], "source", "doc/" + s)
        for old in c.get("supersedes", []):
            link(n["id"], "supersedes", "constant/" + old)
    # corrections
    for x in corr["corrections"]:
        cid = "correction/" + x["id"]
        add({"id": cid, "type": "Correction", "name": x["topic"], "kind": x["kind"], "was": x["was"], "now": x["now"],
             "decidedBy": x["decided_by"], "tag": "retracted" if x["kind"] == "retraction" else "convention"})
        for k in x["constants"]:
            link(cid, "affects", "constant/" + k)
        for r in x["cite"]:
            link(cid, "cites", "ref/" + r)

    missing = [e for e in edges if e["s"] not in nodes or e["o"] not in nodes]
    if missing:
        for e in missing[:20]:
            print("dangling edge", e, file=sys.stderr)
        raise SystemExit("make_graph: %d dangling edges" % len(missing))
    bad = [e for e in edges if e["p"] not in PROPS]
    if bad:
        raise SystemExit("make_graph: unknown predicates %s" % sorted({e["p"] for e in bad}))
    badt = [n for n in nodes.values() if n["type"] not in CLASSES]
    if badt:
        raise SystemExit("make_graph: unknown types %s" % sorted({n["type"] for n in badt}))
    return cur, nodes, edges


CONTEXT = {
    "@vocab": "urn:shroud:vocab:",
    "kb": "urn:shroud:",
    "schema": "https://schema.org/",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "name": "schema:name",
    "description": "schema:description",
    "url": {"@id": "schema:url", "@type": "xsd:anyURI"},
    "start": {"@id": "startYear", "@type": "xsd:integer"},
    "end": {"@id": "endYear", "@type": "xsd:integer"},
    "year": {"@type": "xsd:integer"},
}
for p in PROPS:
    CONTEXT[p] = {"@type": "@id"}


def to_jsonld(cur, nodes, edges):
    out = defaultdict(lambda: defaultdict(list))
    for e in edges:
        out[e["s"]][e["p"]].append({"@id": "kb:" + e["o"]})
    graph = []
    for nid, n in nodes.items():
        d = {"@id": "kb:" + nid, "@type": n["type"], "name": n["name"]}
        if n.get("description"):
            d["description"] = n["description"]
        for k in LITERALS:
            if n.get(k) is not None:
                d[k] = n[k]
        if n.get("sources"):
            d["fromDocument"] = n["sources"]
        for p, vals in out.get(nid, {}).items():
            d[p] = vals if len(vals) > 1 else vals[0]
        graph.append(d)
    return {"@context": CONTEXT, "@graph": graph}


def vocab():
    g = []
    for c, d in CLASSES.items():
        g.append({"@id": "urn:shroud:vocab:" + c, "@type": "rdfs:Class", "rdfs:label": c, "rdfs:comment": d})
    for p, d in PROPS.items():
        g.append({"@id": "urn:shroud:vocab:" + p, "@type": "rdf:Property", "rdfs:label": p, "rdfs:comment": d})
    return {"@context": {"rdfs": "http://www.w3.org/2000/01/rdf-schema#", "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#"}, "@graph": g}


QUERIES = [
    ("Contested claims and who proposed them", """
PREFIX v: <urn:shroud:vocab:>
PREFIX schema: <https://schema.org/>
SELECT ?claim ?by WHERE {
  ?c a v:Claim ; v:tag "contested" ; schema:name ?claim .
  OPTIONAL { ?c v:proposedBy ?p . ?p schema:name ?by }
} ORDER BY ?claim"""),
    ("Measured constants cited to Jackson, Jumper and Ercoline 1984", """
PREFIX v: <urn:shroud:vocab:>
PREFIX schema: <https://schema.org/>
SELECT ?label ?value ?unit WHERE {
  ?q a v:Quantity ; v:tag "measured" ; v:cites <urn:shroud:ref/jje1984> ; schema:name ?label ; v:value ?value .
  OPTIONAL { ?q v:unit ?unit }
} ORDER BY ?label"""),
    ("Artworks of the Spas Nerukotvorny type, with makers", """
PREFIX v: <urn:shroud:vocab:>
PREFIX schema: <https://schema.org/>
SELECT ?work ?date ?maker WHERE {
  ?a v:instanceOf <urn:shroud:concept/spas-nerukotvorny> ; schema:name ?work ; v:date ?date .
  OPTIONAL { ?a v:madeBy ?m . ?m schema:name ?maker }
} ORDER BY ?date"""),
    ("Retracted values and what replaced them", """
PREFIX v: <urn:shroud:vocab:>
PREFIX schema: <https://schema.org/>
SELECT ?old ?new WHERE {
  ?o a v:Quantity ; v:tag ?t ; schema:name ?old .
  FILTER(?t IN ("retracted", "superseded"))
  OPTIONAL { ?n v:supersedes ?o ; schema:name ?new }
} ORDER BY ?old"""),
]


def write_index(pkg, cur, nodes, edges, results):
    by_type = defaultdict(list)
    for n in nodes.values():
        by_type[n["type"]].append(n)
    outgoing = defaultdict(list)
    for e in edges:
        outgoing[e["s"]].append(e)
    name = lambda i: nodes[i]["name"]
    L = ["# Shroud knowledge graph: index", "",
         "Generated by `tools/make_graph.py` from `graph/curated.json`, `data/constants.json`, `data/corrections.json` "
         "and the bibliography. Edit those, not this file.", "",
         "| Type | Nodes | What it holds |", "|---|---|---|"]
    for t in CLASSES:
        L.append("| %s | %d | %s |" % (t, len(by_type[t]), CLASSES[t]))
    L += ["", "%d nodes and %d edges in all. Files: `shroud.jsonld` (JSON-LD 1.1), `vocab.jsonld`, `nodes.csv`, `edges.csv`."
          % (len(nodes), len(edges)), "",
          "## The lineage in one paragraph", "",
          "One legend (Abgar, the Image of Edessa, images not made by hands) is the trunk. Three branches grow from it: the "
          "Byzantine line (the Pantocrator and the Spas Nerukotvorny icons), the Shroud line (the Shroud's own history and the "
          "painted contact-relic copies pressed against it), and the Salvator Mundi line, which descends from the Pantocrator "
          "without needing any single relic. The West's Veronica legend runs in parallel. Which way influence ran between the "
          "Shroud and the icon tradition is contested; both readings are recorded as claims.", "",
          "## Claims by epistemic tag", ""]
    claims = sorted(by_type["Claim"], key=lambda n: (n["tag"], n["name"]))
    for tag in ["measured", "inferred", "historical", "hypothesis", "tradition", "contested", "unsupported"]:
        cs = [c for c in claims if c["tag"] == tag]
        if not cs:
            continue
        L += ["### " + tag.capitalize(), ""]
        for c in cs:
            rel = []
            for e in outgoing[c["id"]]:
                if e["p"] in ("proposedBy", "supportedBy", "disputedBy", "answeredBy", "examinedBy"):
                    rel.append("%s %s" % ({"proposedBy": "by", "supportedBy": "supported by", "disputedBy": "disputed by",
                                            "answeredBy": "answered by", "examinedBy": "examined by"}[e["p"]], name(e["o"])))
            L.append("- **%s**%s%s" % (c["name"], (". " + c["description"]) if c.get("description") else "",
                                       (" (" + "; ".join(rel) + ")") if rel else ""))
        L.append("")
    L += ["## Retracted and superseded values", "",
          "Kept as records so old files can be traced. See `data/corrections.json`.", ""]
    for n in sorted(by_type["Quantity"], key=lambda n: n["id"]):
        if n["tag"] in ("retracted", "superseded"):
            rep = [e["s"] for e in edges if e["p"] == "supersedes" and e["o"] == n["id"]]
            L.append("- `%s` %s: %s%s" % (n["id"].split("/", 1)[1], n["tag"], n["name"],
                                          (" (replaced by `%s`)" % rep[0].split("/", 1)[1]) if rep else ""))
    L += ["", "## Timeline of dated nodes", "", "| Start | Lane | Node | Tag |", "|---|---|---|---|"]
    dated = sorted([n for n in nodes.values() if n.get("start") is not None], key=lambda n: (n["start"], n["name"]))
    for n in dated:
        L.append("| %s | %s | %s (%s) | %s |" % (n.get("date") or n["start"], n.get("lane", ""), n["name"], n["type"], n["tag"]))
    L += ["", "## Artworks", "", "| Work | Date | Maker | Where | Type |", "|---|---|---|---|---|"]
    for n in sorted(by_type["Artwork"], key=lambda n: (n.get("start") or 9999, n["name"])):
        g = lambda p: ", ".join(name(e["o"]) for e in outgoing[n["id"]] if e["p"] == p)
        L.append("| %s | %s | %s | %s | %s |" % (n["name"], n.get("date") or "", g("madeBy"), g("locatedAt"), g("instanceOf")))
    L += ["", "## Example queries (SPARQL, run by `make_graph.py --rdflib`)", ""]
    for title, q, rows in results:
        L += ["### " + title, "", "```sparql" + q + "\n```", ""]
        if rows is None:
            L += ["(not run)", ""]
            continue
        L += ["%d rows; first ones:" % len(rows), ""]
        for r in rows[:8]:
            L.append("- " + " | ".join("" if x is None else str(x) for x in r))
        L.append("")
    L += ["## Lanes", ""] + ["- `%s`: %s" % (k, v) for k, v in cur["lanes"].items()] + [""]
    with open(os.path.join(pkg, "graph", "INDEX.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkg", default=PKG)
    ap.add_argument("--rdflib", action="store_true")
    a = ap.parse_args()
    cur, nodes, edges = build(a.pkg)
    G = os.path.join(a.pkg, "graph")
    doc = to_jsonld(cur, nodes, edges)
    for fn, obj in (("shroud.jsonld", doc), ("vocab.jsonld", vocab())):
        with open(os.path.join(G, fn), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
            f.write("\n")
    with open(os.path.join(G, "nodes.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "type", "name", "tag", "lane", "date", "start", "end", "description"])
        for n in nodes.values():
            w.writerow([n["id"], n["type"], n["name"], n.get("tag", ""), n.get("lane", ""), n.get("date", ""),
                        n.get("start", ""), n.get("end", ""), n.get("description", "")])
    with open(os.path.join(G, "edges.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source", "predicate", "target", "note"])
        for e in edges:
            w.writerow([e["s"], e["p"], e["o"], e.get("note", "")])
    results = [(t, q, None) for t, q in QUERIES]
    if a.rdflib:
        import rdflib
        g = rdflib.Graph()
        g.parse(os.path.join(G, "shroud.jsonld"), format="json-ld")
        print("rdflib: %d triples" % len(g))
        results = []
        for t, q in QUERIES:
            rows = [tuple(None if x is None else str(x) for x in r) for r in g.query(q)]
            print("query '%s': %d rows" % (t, len(rows)))
            if not rows:
                raise SystemExit("make_graph: example query returned nothing: " + t)
            results.append((t, q, rows))
    write_index(a.pkg, cur, nodes, edges, results)
    cnt = Counter(n["type"] for n in nodes.values())
    print("graph: %d nodes, %d edges;" % (len(nodes), len(edges)), dict(cnt))


if __name__ == "__main__":
    main()
