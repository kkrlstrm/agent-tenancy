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
