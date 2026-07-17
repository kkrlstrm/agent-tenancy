# Copyright 2026 Kai Karlstrom
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
capability — the router that turns a tenant binding into a *tenant-scoped* handle.

This is where two of the load-bearing ideas meet:

  • Deterministic coordination, probabilistic content. The caller (often an LLM) names
    an *intent* — "read doc X", "get the token" — and never constructs an id, a path, a
    namespace, or a URL. The capability computes those from the tenant's binding in
    plain code. Symbolic wiring is moved out of the model, where it hallucinates, into
    typed code, where it can't. (Band/Bolna/Lua all keep the model off the control path.)

  • Structural isolation, not policy isolation. `for_tenant(t)` captures tenant t's
    binding and returns a handle whose methods take ONLY content arguments (a key, a
    value) — there is no tenant/namespace/path parameter through which a caller could
    address another tenant. Cross-tenant access isn't forbidden by a check you can
    forget; it's unreachable by construction. (This is SurrealDB enforcing record-level
    security in the planner, and Natural's server-side hard capability exclusions:
    "we architecturally cannot" beats "we promise not to.")

A Capability is a reusable definition, configured once. `for_tenant` mints an ephemeral,
isolated scoped handle per tenant — the definition/execution split, again.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .registry import Tenant


class Capability(ABC):
    """
    A provider configured once (base dir, client, etc.). Scope it to a tenant with
    `for_tenant()`; the returned handle can reach that tenant's resources and no other.

    Subclasses declare `binding_name` (which tenant binding they read) and implement
    `_scope(slug, target)` to return the tenant-scoped handle.
    """
    binding_name: str

    def for_tenant(self, tenant: Tenant):
        # Resolve THIS tenant's target. Raises if the binding is missing/unusable —
        # you cannot get a handle to a tenant whose binding didn't resolve.
        target = tenant.value(self.binding_name)
        return self._scope(tenant.slug, target)

    @abstractmethod
    def _scope(self, tenant_slug: str, target: str):
        """Return a handle bound to `target`, exposing only content-level methods."""
        raise NotImplementedError
