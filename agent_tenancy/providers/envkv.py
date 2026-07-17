# Copyright 2026 Kai Karlstrom
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
envkv — a toy secret accessor (the safe analogue of "get this tenant's DB connection
string"). The tenant's binding holds the NAME of an environment variable; this reads the
value at call time. The secret is never in the registry, and the handle only exposes the
one variable this tenant is bound to.
"""
from __future__ import annotations

import os

from ..capability import Capability


class EnvKV(Capability):
    """Scopes to the tenant's bound env-var name (from the `api_token_env` binding)."""
    binding_name = "api_token_env"

    def __init__(self, env: dict[str, str] | None = None):
        # Optional override map for tests; defaults to the real process environment.
        self._env = env if env is not None else os.environ

    def _scope(self, tenant_slug: str, target: str) -> "_EnvHandle":
        return _EnvHandle(self._env, target)


class _EnvHandle:
    """Bound to exactly one env-var name; no argument selects a different variable."""
    def __init__(self, env, var_name: str):
        self._env = env
        self._var = var_name

    @property
    def var_name(self) -> str:
        return self._var

    def value(self) -> str | None:
        """Resolve the secret from the environment at call time. None if unset."""
        return self._env.get(self._var)

    def require(self) -> str:
        v = self.value()
        if not v:
            raise KeyError(f"env var {self._var!r} is not set")
        return v
