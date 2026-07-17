# Copyright 2026 Kai Karlstrom
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
capability — turn a tenant binding into a *tenant-scoped* handle.

Two ideas meet here:

  • Deterministic routing, probabilistic content. The caller (often an LLM) names an
    intent — "get this doc", "read the token" — and never constructs an id, a path, a
    namespace, or a URL. The capability computes those from the tenant's binding in plain
    code, moving symbolic wiring out of the model (where it hallucinates) into typed code
    (where it can't).

  • Scoping at the interface, not a policy check. `for_tenant(t)` captures tenant t's
    binding and returns a handle whose methods take ONLY content arguments (a key, a
    value) — no tenant/namespace/path parameter through which a caller could address
    another tenant. Within a correctly-implemented capability, the model can't redirect it
    to a different tenant, because the interface exposes nothing to redirect. This is a
    capability-security guarantee about the tool surface the agent sees — not a
    whole-process sandbox.

A Capability is a reusable definition, configured once. `for_tenant` mints an ephemeral,
isolated scoped handle per tenant — the definition/execution split.
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
