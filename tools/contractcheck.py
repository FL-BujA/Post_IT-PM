#!/usr/bin/env python3
"""Assert that classes declared in the contracts expose the attributes the
contracts say they expose.

Three divergences on this project were invisible until an agent looped
looking for something the contract promised:

  - DataKit declared eleven repository slots in C2.1 and exposed none
  - ServiceKit declared six services in C3.1 and exposed eight different ones
  - three repositories declared typed row returns and returned tuples

Each passed its card's tests, because those tests asserted behaviour and
never shape. This check asserts shape.

It reads the ```python blocks under each contract heading, extracts class
names and their annotated attributes, imports the real class, and reports
anything the contract names that the class does not have.

Usage:
    python tools/contractcheck.py
    python tools/contractcheck.py --list      show what was parsed
"""

from __future__ import annotations

import argparse
import ast
import importlib
import pathlib
import re
import sys

CONTRACTS = "contracts"

# Where to find each contract class. A class not listed here is skipped with
# a note — add it when its module lands.
MODULE_OF = {
    "DataKit": "data.db",
    "ServiceKit": "services.compose",
    "FlowService": "services.flow",
    "EvidenceService": "services.evidence",
    "EngagementService": "services.engagement",
    "ReportService": "services.report",
    "BackupService": "services.backup",
    "HandoverService": "services.handover",
}

BLOCK_RE = re.compile(r"```python\n(.*?)```", re.S)


def declared(root: pathlib.Path) -> dict[str, tuple[set[str], set[str]]]:
    """class name -> (annotated attributes, method names) from the contracts."""
    out: dict[str, tuple[set[str], set[str]]] = {}
    for f in sorted((root / CONTRACTS).glob("*.md")):
        for block in BLOCK_RE.findall(f.read_text(encoding="utf-8")):
            try:
                tree = ast.parse(block)
            except SyntaxError:
                continue          # prose pseudo-code, not a real block
            for node in tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue
                attrs: set[str] = set()
                meths: set[str] = set()
                for m in node.body:
                    if isinstance(m, ast.AnnAssign) and isinstance(m.target, ast.Name):
                        attrs.add(m.target.id)
                    elif isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not m.name.startswith("_"):
                            meths.add(m.name)
                a, b = out.get(node.name, (set(), set()))
                out[node.name] = (a | attrs, b | meths)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    root = pathlib.Path(args.root).resolve()
    sys.path.insert(0, str(root))

    spec = declared(root)
    if not spec:
        print("no python blocks found in contracts/", file=sys.stderr)
        return 1

    if args.list:
        for name, (attrs, meths) in sorted(spec.items()):
            print(f"{name}: {len(attrs)} attributes, {len(meths)} methods")
            for a in sorted(attrs):
                print(f"    {a}")
        return 0

    failures = 0
    skipped = 0
    for name, (attrs, meths) in sorted(spec.items()):
        mod_name = MODULE_OF.get(name)
        if not mod_name:
            continue
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            print(f"skip  {name}: {mod_name} not importable yet")
            skipped += 1
            continue
        cls = getattr(mod, name, None)
        if cls is None:
            print(f"FAIL  {name}: not found in {mod_name}")
            failures += 1
            continue

        missing_m = sorted(m for m in meths if not hasattr(cls, m))
        # attributes are usually instance-level; accept a property, a
        # class attribute, or an annotation
        ann = set(getattr(cls, "__annotations__", {}))
        missing_a = sorted(a for a in attrs
                           if not hasattr(cls, a) and a not in ann)

        if missing_m or missing_a:
            print(f"FAIL  {name} ({mod_name})")
            for a in missing_a:
                print(f"          contract declares attribute '{a}' — missing")
            for m in missing_m:
                print(f"          contract declares method '{m}' — missing")
            failures += 1
        else:
            print(f"ok    {name}: {len(attrs)} attributes, {len(meths)} methods")

    print(f"\n{len(spec)} contract classes · {failures} failing · {skipped} not built yet")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
