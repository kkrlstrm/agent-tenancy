# Copyright 2026 Kai Karlstrom
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
generate — build the registry as a deterministic artifact from sources + resolvers.

The registry is *generated, not hand-maintained*: point it at your tenant sources and a
set of resolvers, and it resolves every binding, stamps provenance, optionally verifies
each live, and emits warnings for anything missing/unusable. Re-run it whenever a tenant
or a source changes. Nothing here reaches the network unless a resolver's verify() does.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .registry import STATUS_VERIFIED, Binding, Tenant
from .resolvers import Resolver, TenantSource


@dataclass
class Registry:
    tenants: dict[str, Tenant]
    warnings: list[str] = field(default_factory=list)
    generated_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "_generated_by": "agent-tenancy",
            "_note": "Generated artifact — do not hand-edit; re-run the generator.",
            "generated_at": self.generated_at,
            "tenants": {slug: t.to_dict() for slug, t in self.tenants.items()},
        }

    def write(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2) + "\n")
        return p


def discover_dirs(root: str | Path, marker: str = "tenant.md") -> list[TenantSource]:
    """Reference discovery: each immediate subdir of `root` holding `marker` is a tenant."""
    root = Path(root)
    out: list[TenantSource] = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        if (d / marker).exists():
            out.append(TenantSource(slug=d.name, locator=str(d)))
    return out


def build_registry(sources: list[TenantSource], resolvers: list[Resolver], *,
                   verify: bool = False, today: str | None = None) -> Registry:
    """
    Resolve every binding for every tenant, merging across resolvers (later resolvers
    win a name conflict). With verify=True, each binding is checked live by the resolver
    that produced it and its status/verified_at updated. Collects a warning per binding
    that ended up missing or unusable.
    """
    today = today or date.today().isoformat()
    by_name = {r.name: r for r in resolvers}
    tenants: dict[str, Tenant] = {}
    warnings: list[str] = []

    for src in sources:
        merged: dict[str, Binding] = {}
        for r in resolvers:
            for name, binding in r.resolve(src).items():
                merged[name] = binding

        if verify:
            for name, b in list(merged.items()):
                resolver = by_name.get(b.resolver)
                vb = resolver.verify(b) if resolver else b
                if vb.status == STATUS_VERIFIED and vb.verified_at is None:
                    vb = Binding(name=vb.name, value=vb.value, resolver=vb.resolver,
                                 source=vb.source, status=vb.status, verified_at=today)
                merged[name] = vb

        for name, b in merged.items():
            if not b.usable:
                warnings.append(f"{src.slug}: binding {name!r} is {b.status} "
                                f"(resolver {b.resolver}, source {b.source})")

        tenants[src.slug] = Tenant.from_dict(src.slug, {
            "bindings": {n: b.to_dict() for n, b in merged.items()}
        })

    return Registry(tenants=tenants, warnings=warnings, generated_at=today)
