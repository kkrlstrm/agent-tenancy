# Copyright 2026 Kai Karlstrom
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
End-to-end demo: generate a registry from the example tenants, then use a capability
that is structurally scoped to one tenant.

    python examples/demo.py
"""
import tempfile
from pathlib import Path

from agent_tenancy import tenant
from agent_tenancy.generate import build_registry, discover_dirs
from agent_tenancy.providers import LocalStore
from agent_tenancy.resolvers import EnvVarResolver, MarkdownFrontmatterResolver

HERE = Path(__file__).resolve().parent


def main() -> None:
    # 1. Generate the registry from the example tenant dirs (definition, generated).
    sources = discover_dirs(HERE / "tenants")
    resolvers = [
        MarkdownFrontmatterResolver(fields={"docs_store": "docs_store"}),
        EnvVarResolver(bindings={"api_token_env": "API_TOKEN"}),
    ]
    reg = build_registry(sources, resolvers, verify=True)
    print(f"generated registry: {sorted(reg.tenants)}")
    for slug, t in reg.tenants.items():
        b = t.binding("docs_store")
        print(f"  {slug}.docs_store = {b.value!r}  ({b.status}, via {b.resolver})")

    # 2. Resolve a tenant and reach its resources through a scoped capability.
    with tempfile.TemporaryDirectory() as tmp:
        store = LocalStore(root=tmp)  # one provider, configured once

        acme = store.for_tenant(tenant("acme", reg.tenants))    # execution: scoped handle
        acme.put("welcome", "hello from acme")
        print(f"\nacme.get('welcome') -> {acme.get('welcome')!r}")

        globex = store.for_tenant(tenant("globex", reg.tenants))
        # The caller never names a namespace — there is no argument to reach acme's data.
        print(f"globex.get('welcome') -> {globex.get('welcome')!r}   (isolated: None)")
        print(f"globex.keys() -> {globex.keys()}   (cannot see acme's keys)")


if __name__ == "__main__":
    main()
