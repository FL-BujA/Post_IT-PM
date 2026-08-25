#!/usr/bin/env python3
"""Validate build cards before an agent is asked to run one.

Every failure this catches cost at least one wasted session on this project:

  - a card citing a contract section that does not exist (C3.0)
  - a card citing a section that exists but describes something else
    (P-12 cited C3.4 EngagementService for evidence work; evidence is C3.2)
  - a card naming more source files than R10 allows
  - a card whose Done-when bullets name a type that is in neither the
    signature sheet nor the card itself, so the agent must go looking

Usage:
    python tools/cardcheck.py                 check every card
    python tools/cardcheck.py cards/P-12.md   check one
    python tools/cardcheck.py --strict        warnings become failures

Add to the gate:
    python tools/cardcheck.py
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

CARDS = "cards"
CONTRACTS = "contracts"
SIGSHEET = "core.sig.txt"

SECTION_RE = re.compile(r"^##\s+(C\d+\.\d+)\s*(.*)$", re.M)
CITATION_RE = re.compile(r"\bC\d+\.\d+\b")
CAMEL_RE = re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z0-9]+)+)\b")
ROLE_RE = re.compile(r"^\s+(SOURCE|TESTS|REGISTER)\s+(\S+)", re.M)

# Types the checker should not flag: language and stdlib names that will
# never be in a project signature sheet.
IGNORE_TYPES = {
    "TestCase", "PathLike", "DataFrame", "TypeError", "ValueError",
    "AttributeError", "KeyError", "RuntimeError", "NotImplementedError",
    "FileNotFoundError", "BaseModel", "IntEnum", "StrEnum",
}


def load_sections(root: pathlib.Path) -> dict[str, str]:
    """Map C-number -> heading text, across every contract file."""
    out: dict[str, str] = {}
    d = root / CONTRACTS
    if not d.is_dir():
        return out
    for f in sorted(d.glob("*.md")):
        for num, title in SECTION_RE.findall(f.read_text(encoding="utf-8")):
            out.setdefault(num, f"{title.strip()}  [{f.name}]")
    return out


def load_sigsheet(root: pathlib.Path) -> str:
    p = root / SIGSHEET
    return p.read_text(encoding="utf-8") if p.exists() else ""


def section_of(text: str, name: str) -> str:
    """Return the named section of a card ('Done when', 'Goal', ...)."""
    m = re.search(rf"^{re.escape(name)}:(.*?)(?=^\w[\w .]*:|\Z)",
                  text, re.M | re.S)
    return m.group(1) if m else ""


def check_card(path: pathlib.Path, sections: dict[str, str],
               sigsheet: str, root: pathlib.Path) -> tuple[list[str], list[str]]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    warns: list[str] = []

    # ---- 1. contract citations resolve -------------------------------
    for cite in sorted(set(CITATION_RE.findall(text))):
        if cite not in sections:
            errors.append(f"cites {cite}, which is not a heading in contracts/")

    # ---- 2. R10 source budget ---------------------------------------
    roles = ROLE_RE.findall(text)
    src = [p for r, p in roles if r == "SOURCE"]
    if not roles:
        warns.append("no SOURCE/TESTS/REGISTER labels under Files allowed")
    elif len(src) > 2:
        errors.append(f"{len(src)} SOURCE files, R10 allows 2: {', '.join(src)}")

    # ---- 3. named files exist, or the card says it creates them ------
    goal = section_of(text, "Goal").lower()
    creating = any(w in goal for w in
                   ("create", "creates", "new ", "adds", "backfill", "seed"))
    for role, rel in roles:
        if role == "TESTS":
            continue
        if not (root / rel.rstrip(".,;·")).exists() and not creating:
            warns.append(f"{role} {rel} does not exist and the Goal does not "
                         f"say this card creates it")

    # ---- 4. types in Done-when are resolvable ------------------------
    done = section_of(text, "Done when")
    for t in sorted(set(CAMEL_RE.findall(done))):
        if t in IGNORE_TYPES:
            continue
        if t in sigsheet:
            continue
        if re.search(rf"\b{t}\b", goal, re.I):
            continue          # the card says it creates this type
        warns.append(f"Done-when names {t}, which is not in {SIGSHEET} and is "
                     f"not mentioned in the Goal — the agent will go looking")

    # ---- 5. required fields present ---------------------------------
    for field in ("Goal", "Contract", "Files allowed", "Done when",
                  "Forbidden", "Commit"):
        if not re.search(rf"^{re.escape(field)}", text, re.M):
            warns.append(f"missing '{field}:' section")

    return errors, warns


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cards", nargs="*", help="specific cards (default: all)")
    ap.add_argument("--root", default=".")
    ap.add_argument("--strict", action="store_true",
                    help="treat warnings as failures")
    args = ap.parse_args()

    root = pathlib.Path(args.root).resolve()
    sections = load_sections(root)
    if not sections:
        print(f"no contract sections found under {root/CONTRACTS}",
              file=sys.stderr)
        return 1
    sigsheet = load_sigsheet(root)
    if not sigsheet:
        print(f"warning: {SIGSHEET} missing — type checks skipped",
              file=sys.stderr)

    paths = ([pathlib.Path(c) for c in args.cards] if args.cards
             else sorted((root / CARDS).glob("[PA]-*.md")))
    if not paths:
        print("no cards found", file=sys.stderr)
        return 1

    n_err = n_warn = 0
    for p in paths:
        errors, warns = check_card(p, sections, sigsheet, root)
        if errors or warns:
            print(f"\n{p.name}")
            for e in errors:
                print(f"  ERROR  {e}")
            for w in warns:
                print(f"  warn   {w}")
        n_err += len(errors)
        n_warn += len(warns)

    print(f"\n{len(paths)} cards checked · {n_err} errors · {n_warn} warnings")
    if n_err or (args.strict and n_warn):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
