#!/usr/bin/env python3
"""Validate the package's X3D scenes.

Two layers, both optional so the script runs anywhere lxml does:

  1. XML Schema. The X3D 4.0 XSD from the Web3D Consortium
     (https://www.web3d.org/specifications/x3d-4.0.xsd). Pass --xsd PATH, or let
     the script use the copy bundled with x3d_mcp when x3d_mcp is found.
  2. x3d_mcp's semantic and profile checks: DEF/USE, ROUTE typing, containerField,
     tuple counts, and whether the declared profile plus component statements
     cover every node. Found through --x3d-mcp PATH (its src folder) or the
     X3D_MCP environment variable.

Usage
  python3 tools/validate_x3d.py                          # every x3d/*.x3d
  python3 tools/validate_x3d.py --x3d-mcp ../x3d_mcp/src x3d/shroud_cloth.x3d
  python3 tools/validate_x3d.py --xsd x3d-4.0.xsd

Exit status is 1 when any file fails a check that ran, 2 when no check could run.
"""
import argparse
import glob
import os
import sys

from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load_mcp(path):
    """Import x3d_mcp's validation package from its src folder, or return None."""
    for cand in [path, os.environ.get("X3D_MCP")]:
        if cand and os.path.isdir(os.path.join(cand, "validation")):
            sys.path.insert(0, cand)
            try:
                from validation import validate, semantic, profile
                return validate, semantic, profile
            except Exception as e:                      # missing dependency, wrong folder
                print("x3d_mcp found at %s but could not be imported: %s" % (cand, e))
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="*")
    ap.add_argument("--xsd", help="path to x3d-4.0.xsd")
    ap.add_argument("--x3d-mcp", help="path to the src folder of x3d_mcp")
    ap.add_argument("-v", "--verbose", action="store_true", help="also list x3d_mcp's info notes (DEFs kept for the viewer page, etc.)")
    a = ap.parse_args()
    files = a.files or sorted(glob.glob(os.path.join(ROOT, "x3d", "*.x3d")))
    mcp = load_mcp(a.x3d_mcp)
    schema = None
    if a.xsd:
        schema = etree.XMLSchema(etree.parse(a.xsd))
    elif not mcp:
        print("No schema: pass --xsd x3d-4.0.xsd or --x3d-mcp PATH. Checking well-formedness only.")

    ran, failed = False, 0
    for f in files:
        text = open(f, encoding="utf-8").read()
        name = os.path.relpath(f, ROOT)
        problems = []
        try:
            root = etree.fromstring(text.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            print("FAIL %s: not well-formed: %s" % (name, e))
            failed += 1
            continue
        if root.get("version") != "4.0":
            problems.append("declares version %r, expected 4.0" % root.get("version"))
        if schema is not None:
            ran = True
            if not schema.validate(root):
                problems += ["XSD line %d: %s" % (e.line, e.message) for e in schema.error_log]
        elif mcp:
            ran = True
            r = mcp[0].validate_xml(text)
            if r.get("schema_version") != "4.0":
                problems.append("validated against X3D %s, not 4.0" % r.get("schema_version"))
            problems += ["XSD " + e for e in r["errors"]]
        if mcp:
            diags = mcp[1].semantic_diagnostics(text)
            problems += ["%s %s: %s" % (d.level, d.check, d.message) for d in diags if d.level == "error"]
            notes = ["%s %s: %s" % (d.level, d.check, d.message) for d in diags
                     if d.level == "warning" or (a.verbose and d.level != "error")]
            rep = mcp[2].check_profile(root)
            if rep.missing:
                problems.append("profile %s lacks components: %s" % (rep.profile, " ".join(mcp[2].component_statements(rep))))
        else:
            notes = []
        status = "FAIL" if problems else "ok  "
        failed += bool(problems)
        print("%s %-34s %6.1f KB  %s" % (status, name, len(text.encode("utf-8")) / 1024, root.get("profile")))
        for p in problems:
            print("     " + p)
        for n in notes:
            print("     note " + n)
    if not ran:
        print("Only well-formedness and the version attribute were checked.")
        sys.exit(2 if not failed else 1)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
