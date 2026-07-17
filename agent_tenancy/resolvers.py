# Copyright 2026 Kai Karlstrom
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
resolvers — how a binding gets discovered from a source of truth.

A Resolver knows how to pull one or more bindings for a tenant out of some source (a
markdown frontmatter block, an env-var naming convention, a SaaS API, a CMDB row, …)
and stamp each with provenance. Resolvers are the plug-points of the generator: the
framework ships two trivial reference resolvers; you write the ones that hit your real
sources and register them the same way.

`resolve()` produces bindings; `verify()` optionally upgrades a binding's status from
`resolved` to `verified` (or flags it) by checking it live — the standard split between
"what is known" and "what has been confirmed."
"""
from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from .registry import (STATUS_MISSING, STATUS_RESOLVED, STATUS_UNVERIFIABLE,
                       STATUS_VERIFIED, Binding)


@dataclass
class TenantSource:
    """A tenant to resolve: its slug plus an opaque locator each resolver interprets."""
    slug: str
    locator: str  # e.g. a directory path, an org id, a CMDB key


class Resolver(ABC):
    """Resolve + optionally verify bindings for one tenant source."""
    name: str = "resolver"

    @abstractmethod
    def resolve(self, src: TenantSource) -> dict[str, Binding]:
        """Return {binding_name: Binding} for this tenant. Missing → status=missing."""

    def verify(self, binding: Binding) -> Binding:
        """Default: no live check possible → mark unverifiable. Override to check."""
        if binding.value is None:
            return binding
        return _restatus(binding, STATUS_UNVERIFIABLE)


def _restatus(b: Binding, status: str, *, verified_at: str | None = None) -> Binding:
    return Binding(name=b.name, value=b.value, resolver=b.resolver, source=b.source,
                   status=status, verified_at=verified_at if verified_at is not None else b.verified_at)


# --------------------------------------------------------------------------- toy #1
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


class MarkdownFrontmatterResolver(Resolver):
    """
    Reads `<locator>/<filename>` and lifts named frontmatter keys into bindings. This is
    the reference resolver for "the source of truth is a doc the humans already keep."
    `fields` maps binding_name -> frontmatter key.
    """
    name = "markdown-frontmatter"

    def __init__(self, fields: dict[str, str], filename: str = "tenant.md"):
        self.fields = fields
        self.filename = filename

    def resolve(self, src: TenantSource) -> dict[str, Binding]:
        path = Path(src.locator) / self.filename
        source_ref = str(path)
        fm = self._frontmatter(path)
        out: dict[str, Binding] = {}
        for binding_name, fm_key in self.fields.items():
            val = fm.get(fm_key)
            status = STATUS_RESOLVED if val else STATUS_MISSING
            out[binding_name] = Binding(name=binding_name, value=val, resolver=self.name,
                                        source=source_ref, status=status)
        return out

    def verify(self, binding: Binding) -> Binding:
        """The doc it came from still exists → verified; else unverifiable."""
        if binding.value is None:
            return binding
        ok = Path(binding.source).exists()
        return _restatus(binding, STATUS_VERIFIED if ok else STATUS_UNVERIFIABLE)

    @staticmethod
    def _frontmatter(path: Path) -> dict[str, str]:
        if not path.exists():
            return {}
        m = _FRONTMATTER_RE.match(path.read_text())
        if not m:
            return {}
        out: dict[str, str] = {}
        for line in m.group(1).splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip("'\"")
        return out


# --------------------------------------------------------------------------- toy #2
class EnvVarResolver(Resolver):
    """
    Emits bindings whose *value* is the NAME of an environment variable, derived from a
    per-tenant convention (default `<SLUG>_<SUFFIX>`). The registry stores the var name,
    never the secret — the capability reads the secret from the environment at call
    time. This is how you keep credentials out of a committed registry.

    `bindings` maps binding_name -> env-var suffix, e.g. {"api_token_env": "API_TOKEN"}.
    """
    name = "env-var"

    def __init__(self, bindings: dict[str, str]):
        self.bindings = bindings

    def resolve(self, src: TenantSource) -> dict[str, Binding]:
        upper = re.sub(r"[^A-Z0-9]", "_", src.slug.upper())
        out: dict[str, Binding] = {}
        for binding_name, suffix in self.bindings.items():
            var = f"{upper}_{suffix}"
            out[binding_name] = Binding(name=binding_name, value=var, resolver=self.name,
                                        source=f"env:{var}", status=STATUS_RESOLVED)
        return out

    def verify(self, binding: Binding) -> Binding:
        """The named env var is actually set → verified; else missing (not just unverifiable)."""
        if binding.value is None:
            return binding
        present = bool(os.environ.get(binding.value))
        return _restatus(binding, STATUS_VERIFIED if present else STATUS_MISSING)
