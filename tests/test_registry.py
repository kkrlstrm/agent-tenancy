# Copyright 2026 Kai Karlstrom
# SPDX-License-Identifier: Apache-2.0
"""The tenant definition is immutable, and every binding carries its provenance."""
from __future__ import annotations

import dataclasses

import pytest

from agent_tenancy import Binding, BindingError, TenantError, tenant
from agent_tenancy.registry import STATUS_MISSING, Tenant


def _registry():
    return {
        "acme": Tenant.from_dict("acme", {"bindings": {
            "docs_store": {"value": "acme", "resolver": "markdown-frontmatter",
                           "source": "acme/tenant.md", "status": "verified",
                           "verified_at": "2026-07-17"},
            "api_token_env": {"value": "ACME_API_TOKEN", "resolver": "env-var",
                              "source": "env:ACME_API_TOKEN", "status": "resolved"},
            "missing_one": {"value": None, "resolver": "env-var",
                            "source": "env:ACME_NOPE", "status": STATUS_MISSING},
        }}),
    }


def test_value_resolves_usable_binding():
    t = tenant("acme", _registry())
    assert t.value("docs_store") == "acme"
    assert t.value("api_token_env") == "ACME_API_TOKEN"


def test_provenance_is_carried():
    b = tenant("acme", _registry()).binding("docs_store")
    assert isinstance(b, Binding)
    assert b.resolver == "markdown-frontmatter"
    assert b.source == "acme/tenant.md"
    assert b.status == "verified"
    assert b.verified_at == "2026-07-17"


def test_missing_binding_raises_not_returns_none():
    t = tenant("acme", _registry())
    with pytest.raises(BindingError):
        t.value("missing_one")          # status=missing → unusable → raises
    with pytest.raises(BindingError):
        t.value("does_not_exist")       # absent → raises
    assert t.has("docs_store") is True
    assert t.has("missing_one") is False


def test_unknown_tenant_raises():
    with pytest.raises(TenantError):
        tenant("nope", _registry())


def test_tenant_slug_is_tolerant():
    reg = {"club-hub": Tenant.from_dict("club-hub", {"bindings": {}})}
    assert tenant("Club Hub", reg).slug == "club-hub"
    assert tenant("clubhub", reg).slug == "club-hub"


def test_tenant_definition_is_frozen():
    t = tenant("acme", _registry())
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.slug = "evil"                 # frozen dataclass


def test_bindings_mapping_is_read_only():
    t = tenant("acme", _registry())
    with pytest.raises(TypeError):
        t.bindings["injected"] = Binding("injected", "x", "r", "s")   # MappingProxyType
