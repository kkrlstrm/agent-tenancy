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
