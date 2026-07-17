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
localstore — a toy per-tenant document store (the safe analogue of a "read a file from
this tenant's repo" capability). Reads the tenant's `docs_store` binding as a namespace
under a shared root; the handle can only ever touch that namespace.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..capability import Capability

_SAFE_KEY = re.compile(r"^[A-Za-z0-9._-]+$")


class LocalStore(Capability):
    """Configured once with a root dir; `for_tenant` scopes to `<root>/<docs_store>/`."""
    binding_name = "docs_store"

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _scope(self, tenant_slug: str, target: str) -> "_StoreHandle":
        # `target` is the tenant's namespace, from its binding — not caller-supplied.
        return _StoreHandle(self.root / _safe_segment(target))


class _StoreHandle:
    """
    Bound to exactly one directory. Every method takes only a key/value — there is no
    argument that selects a different tenant or namespace, and keys are sanitized so a
    caller cannot traverse out with '../'. That's the structural isolation guarantee.
    """
    def __init__(self, base: Path):
        self._base = base

    def _path(self, key: str) -> Path:
        if not _SAFE_KEY.match(key or "") or ".." in key:
            raise ValueError(f"invalid key {key!r}: must match {_SAFE_KEY.pattern} and contain no '..'")
        return self._base / f"{key}.txt"

    def put(self, key: str, value: str) -> None:
        self._base.mkdir(parents=True, exist_ok=True)
        self._path(key).write_text(value, encoding="utf-8")

    def get(self, key: str) -> str | None:
        p = self._path(key)
        return p.read_text(encoding="utf-8") if p.exists() else None

    def keys(self) -> list[str]:
        if not self._base.exists():
            return []
        return sorted(p.stem for p in self._base.glob("*.txt"))


def _safe_segment(seg: str) -> str:
    seg = (seg or "").strip().strip("/")
    if not _SAFE_KEY.match(seg):
        raise ValueError(f"unsafe namespace segment {seg!r}")
    return seg
