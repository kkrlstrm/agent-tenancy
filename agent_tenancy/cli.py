# Copyright 2026 Kai Karlstrom
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
agent-tenancy CLI.

    tenancy generate <root> -o registry.json [--verify]   discover dirs → registry
    tenancy show <slug> -r registry.json                  print a tenant's bindings + provenance
    tenancy verify -r registry.json                       re-verify and report status

`generate` wires the two reference resolvers (markdown-frontmatter + env-var) over a
directory of tenant folders — that's the shipped example. In your own system you call
`build_registry(sources, resolvers)` from code with the resolvers that hit your sources.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .generate import build_registry, discover_dirs
from .registry import USABLE, all_tenants, load_registry, tenant
from .resolvers import EnvVarResolver, MarkdownFrontmatterResolver

# The example resolver wiring: a docs_store from tenant.md frontmatter, an api token from
# a per-tenant env-var convention. Swap these for your own in code.
EXAMPLE_RESOLVERS = [
    MarkdownFrontmatterResolver(fields={"docs_store": "docs_store"}),
    EnvVarResolver(bindings={"api_token_env": "API_TOKEN"}),
]


def _status_glyph(status: str) -> str:
    return {"verified": "✓", "resolved": "·", "missing": "✗", "unverifiable": "?"}.get(status, "·")


def cmd_generate(args) -> int:
    sources = discover_dirs(args.root)
    if not sources:
        print(f"no tenant dirs found under {args.root} (looking for tenant.md)", file=sys.stderr)
        return 2
    reg = build_registry(sources, EXAMPLE_RESOLVERS, verify=args.verify)
    out = reg.write(args.out)
    print(f"wrote {out} — {len(reg.tenants)} tenant(s)")
    for slug, t in reg.tenants.items():
        bits = [f"{_status_glyph(b.status)} {n}" for n, b in t.bindings.items()]
        print(f"  {slug}: {', '.join(bits)}")
    if reg.warnings:
        print(f"\n{len(reg.warnings)} warning(s):", file=sys.stderr)
        for w in reg.warnings:
            print(f"  - {w}", file=sys.stderr)
    return 0


def cmd_show(args) -> int:
    t = tenant(args.slug, args.registry)
    print(f"tenant: {t.slug}")
    if not t.bindings:
        print("  (no bindings)")
        return 0
    width = max(len(n) for n in t.bindings)
    for name, b in t.bindings.items():
        va = f" verified {b.verified_at}" if b.verified_at else ""
        print(f"  {_status_glyph(b.status)} {name:<{width}}  {b.value!r}")
        print(f"    └ {b.status} · resolver {b.resolver} · source {b.source}{va}")
    return 0


def cmd_verify(args) -> int:
    reg = load_registry(args.registry)
    bad = 0
    for t in all_tenants(reg):
        for name, b in t.bindings.items():
            if b.status not in USABLE:
                bad += 1
                print(f"  {_status_glyph(b.status)} {t.slug}.{name}: {b.status} "
                      f"(resolver {b.resolver}, source {b.source})")
    total = sum(len(t.bindings) for t in all_tenants(reg))
    print(f"\n{total - bad}/{total} bindings usable across {len(reg)} tenant(s)")
    return 1 if bad else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tenancy",
        description="Keep tenant routing out of the model: a generated, provenance-stamped "
                    "tenant registry + structurally-scoped capabilities for agent runtimes.")
    p.add_argument("--version", action="version", version=f"agent-tenancy {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="discover tenant dirs and build the registry")
    g.add_argument("root", help="dir whose subfolders (each with tenant.md) are tenants")
    g.add_argument("-o", "--out", default="tenants.generated.json", help="output registry path")
    g.add_argument("--verify", action="store_true", help="check each binding live")
    g.set_defaults(func=cmd_generate)

    s = sub.add_parser("show", help="print a tenant's bindings + provenance")
    s.add_argument("slug")
    s.add_argument("-r", "--registry", required=True)
    s.set_defaults(func=cmd_show)

    v = sub.add_parser("verify", help="report any non-usable bindings in a registry")
    v.add_argument("-r", "--registry", required=True)
    v.set_defaults(func=cmd_verify)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
