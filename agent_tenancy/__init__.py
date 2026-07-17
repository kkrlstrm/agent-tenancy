# Copyright 2026 Kai Karlstrom
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
agent-tenancy — compile-time tenant binding for multi-tenant agents.

Turn per-tenant wiring (which repo, which DB, which channel) into a generated registry
of provenance-stamped bindings, and reach each tenant's resources through capabilities
that are structurally scoped — so an agent never constructs an id and never can touch the
wrong tenant.
"""
from . import capability, generate, providers, registry, resolvers  # noqa: F401
from .capability import Capability
from .registry import (Binding, BindingError, Tenant, TenantError, all_tenants,
                       load_registry, tenant)
from .resolvers import Resolver, TenantSource

__version__ = "0.1.0"

__all__ = [
    "Tenant", "Binding", "tenant", "all_tenants", "load_registry",
    "TenantError", "BindingError",
    "Capability", "Resolver", "TenantSource",
    "registry", "resolvers", "generate", "capability", "providers",
    "__version__",
]
