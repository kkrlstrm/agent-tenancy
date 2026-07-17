# Copyright 2026 Kai Karlstrom
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Reference capability providers — safe, generic analogues you swap for your own."""
from .envkv import EnvKV
from .localstore import LocalStore

__all__ = ["LocalStore", "EnvKV"]
