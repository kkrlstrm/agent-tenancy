# Copyright 2026 Kai Karlstrom
# SPDX-License-Identifier: Apache-2.0
"""
Structural isolation: a capability scoped to one tenant cannot reach another — not by a
check you could forget, but because there is no argument through which to address it.
"""
from __future__ import annotations

import inspect

import pytest

from agent_tenancy import tenant
from agent_tenancy.generate import build_registry
from agent_tenancy.providers import EnvKV, LocalStore
from agent_tenancy.registry import Tenant


def _reg():
    return {
        "acme": Tenant.from_dict("acme", {"bindings": {
            "docs_store": {"value": "acme", "resolver": "r", "source": "s", "status": "resolved"},
            "api_token_env": {"value": "ACME_API_TOKEN", "resolver": "r", "source": "s", "status": "resolved"},
        }}),
        "globex": Tenant.from_dict("globex", {"bindings": {
            "docs_store": {"value": "globex", "resolver": "r", "source": "s", "status": "resolved"},
            "api_token_env": {"value": "GLOBEX_API_TOKEN", "resolver": "r", "source": "s", "status": "resolved"},
        }}),
    }


def test_scoped_handle_is_isolated_to_its_tenant(tmp_path):
    reg = _reg()
    store = LocalStore(root=tmp_path)
    acme = store.for_tenant(tenant("acme", reg))
    globex = store.for_tenant(tenant("globex", reg))

    acme.put("welcome", "from acme")
    globex.put("welcome", "from globex")

    assert acme.get("welcome") == "from acme"
    assert globex.get("welcome") == "from globex"     # same key, different tenant, no collision
    assert acme.keys() == ["welcome"]
    assert globex.keys() == ["welcome"]               # neither sees the other's namespace


def test_no_method_exposes_a_tenant_or_namespace_selector(tmp_path):
    # The structural guarantee: handle methods take only content args (key/value),
    # never a tenant/namespace/path through which another tenant could be addressed.
    handle = LocalStore(root=tmp_path).for_tenant(tenant("acme", _reg()))
    for meth in ("get", "put", "keys"):
        params = set(inspect.signature(getattr(handle, meth)).parameters)
        assert not (params & {"tenant", "namespace", "slug", "path", "base"}), meth


def test_key_traversal_cannot_escape_the_namespace(tmp_path):
    handle = LocalStore(root=tmp_path).for_tenant(tenant("acme", _reg()))
    for evil in ("../globex/welcome", "../../etc/passwd", "a/b", "..", ""):
        with pytest.raises(ValueError):
            handle.get(evil)


def test_two_handles_share_no_mutable_state(tmp_path):
    # Definition/execution split: each for_tenant() mints an independent handle.
    store = LocalStore(root=tmp_path)
    a1 = store.for_tenant(tenant("acme", _reg()))
    a2 = store.for_tenant(tenant("acme", _reg()))
    assert a1 is not a2
    a1.put("k", "v")
    assert a2.get("k") == "v"                          # same namespace on disk...
    assert a1._base == a2._base and a1 is not a2       # ...but distinct handle objects


def test_cannot_scope_a_tenant_whose_binding_is_unusable(tmp_path):
    bad = {"broken": Tenant.from_dict("broken", {"bindings": {
        "docs_store": {"value": None, "resolver": "r", "source": "s", "status": "missing"},
    }})}
    from agent_tenancy import BindingError
    with pytest.raises(BindingError):
        LocalStore(root=tmp_path).for_tenant(tenant("broken", bad))


def test_envkv_resolves_var_name_to_secret_at_call_time():
    # The registry holds the env-var NAME; the secret is read at call time, never stored.
    fake_env = {"ACME_API_TOKEN": "s3cret-acme", "GLOBEX_API_TOKEN": "s3cret-globex"}
    kv = EnvKV(env=fake_env)
    acme = kv.for_tenant(tenant("acme", _reg()))
    globex = kv.for_tenant(tenant("globex", _reg()))

    assert acme.var_name == "ACME_API_TOKEN"
    assert acme.value() == "s3cret-acme"
    assert globex.value() == "s3cret-globex"          # each bound to only its own var
    # nothing in the registry record is the secret itself
    assert tenant("acme", _reg()).value("api_token_env") == "ACME_API_TOKEN"
