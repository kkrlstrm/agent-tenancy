# Copyright 2026 Kai Karlstrom
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
registry — the immutable tenant *definition* and its provenance-carrying bindings.

Two design commitments live in this file, both borrowed from how funded AI-infra
companies build multi-tenant runtimes:

  • Definition / execution split. A Tenant is a frozen config record — zero-cost at
    rest, never mutated at runtime. Binding resolution and any per-run state happen in
    the ephemeral scoped handles returned by capabilities (see capability.py), never
    here. The bindings map is wrapped read-only so the definition genuinely cannot drift
    under you. (Band builds agents this way: a definition is a record, a run is a
    throwaway isolated instance.)

  • Per-binding provenance. Every binding is not a bare string but a `Binding` that
    knows which resolver produced it, from what source, its verification status, and
    when it was last verified. A registry that only stores values can't tell you why a
    tenant is misconfigured; this one can. (OpsMill tags every attribute with source +
    owner for exactly this reason.)

Secrets never live in the registry. A binding's *value* is an identifier or an env-var
NAME — the actual secret is resolved at call time by the capability, so the registry
file is safe to commit.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

# Binding status vocabulary — a graded state, not a boolean (see the deliverability
# tool's graded verdicts; a registry has the same "more than two outcomes" need).
STATUS_RESOLVED = "resolved"          # a value was produced, not verified
STATUS_VERIFIED = "verified"          # value produced AND checked live (file exists / env set / API 200)
STATUS_MISSING = "missing"            # resolver ran but could not produce a value
STATUS_UNVERIFIABLE = "unverifiable"  # verify was attempted but couldn't reach a verdict
STATUSES = (STATUS_RESOLVED, STATUS_VERIFIED, STATUS_MISSING, STATUS_UNVERIFIABLE)

USABLE = (STATUS_RESOLVED, STATUS_VERIFIED)


class TenantError(KeyError):
    """Unknown tenant slug."""


class BindingError(KeyError):
    """A binding is absent, missing, or unusable for this tenant."""


@dataclass(frozen=True)
class Binding:
    """One resolved binding + where it came from. Frozen: provenance is a fact."""
    name: str
    value: str | None
    resolver: str
    source: str
    status: str = STATUS_RESOLVED
    verified_at: str | None = None

    @property
    def usable(self) -> bool:
        return self.status in USABLE and self.value is not None

    def to_dict(self) -> dict:
        return {"value": self.value, "resolver": self.resolver, "source": self.source,
                "status": self.status, "verified_at": self.verified_at}

    @classmethod
    def from_dict(cls, name: str, d: dict) -> "Binding":
        return cls(name=name, value=d.get("value"), resolver=d.get("resolver", "unknown"),
                   source=d.get("source", ""), status=d.get("status", STATUS_RESOLVED),
                   verified_at=d.get("verified_at"))


@dataclass(frozen=True)
class Tenant:
    """
    An immutable tenant definition. `bindings` is a read-only mapping name -> Binding;
    attempting to mutate it raises. Resolve a value with `.value(name)` (raises if the
    binding is missing/unusable) and inspect provenance with `.binding(name)`.
    """
    slug: str
    bindings: Mapping[str, Binding] = field(default_factory=lambda: MappingProxyType({}))

    def value(self, name: str) -> str:
        """The resolved value for a binding. Raises BindingError if unusable."""
        b = self.bindings.get(name)
        if b is None:
            raise BindingError(
                f"tenant {self.slug!r} has no binding {name!r}; "
                f"has: {', '.join(sorted(self.bindings)) or '(none)'}"
            )
        if not b.usable:
            raise BindingError(
                f"tenant {self.slug!r} binding {name!r} is {b.status} "
                f"(resolver {b.resolver!r}, source {b.source!r})"
            )
        return b.value  # type: ignore[return-value]

    def binding(self, name: str) -> Binding:
        """Full provenance for a binding (may be missing/unusable)."""
        b = self.bindings.get(name)
        if b is None:
            raise BindingError(f"tenant {self.slug!r} has no binding {name!r}")
        return b

    def has(self, name: str) -> bool:
        b = self.bindings.get(name)
        return b is not None and b.usable

    def to_dict(self) -> dict:
        return {"slug": self.slug,
                "bindings": {n: b.to_dict() for n, b in self.bindings.items()}}

    @classmethod
    def from_dict(cls, slug: str, d: dict) -> "Tenant":
        bindings = {n: Binding.from_dict(n, bd) for n, bd in d.get("bindings", {}).items()}
        return cls(slug=slug, bindings=MappingProxyType(bindings))


def load_registry(path: str | Path) -> dict[str, Tenant]:
    """Load a generated registry JSON into {slug: Tenant}."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"registry not found: {p} — generate it first")
    data = json.loads(p.read_text())
    return {slug: Tenant.from_dict(slug, rec) for slug, rec in data.get("tenants", {}).items()}


def tenant(slug: str, registry: str | Path | dict[str, Tenant]) -> Tenant:
    """
    Resolve a tenant slug (case-insensitive, hyphen/space tolerant) from a registry
    path or an already-loaded {slug: Tenant} mapping.
    """
    reg = registry if isinstance(registry, dict) else load_registry(registry)
    key = slug.strip().lower().replace(" ", "-")
    if key in reg:
        return reg[key]
    squashed = {k.replace("-", ""): k for k in reg}
    if key.replace("-", "") in squashed:
        return reg[squashed[key.replace("-", "")]]
    raise TenantError(f"unknown tenant {slug!r}. Known: {', '.join(sorted(reg)) or '(none)'}")


def all_tenants(registry: str | Path | dict[str, Tenant]) -> list[Tenant]:
    reg = registry if isinstance(registry, dict) else load_registry(registry)
    return [reg[k] for k in sorted(reg)]
