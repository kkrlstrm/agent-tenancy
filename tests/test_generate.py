# Copyright 2026 Kai Karlstrom
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The registry is generated from sources + resolvers, with provenance and verify."""
from __future__ import annotations

from pathlib import Path

from agent_tenancy.generate import build_registry, discover_dirs
from agent_tenancy.resolvers import EnvVarResolver, MarkdownFrontmatterResolver

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "tenants"


def _resolvers():
    return [
        MarkdownFrontmatterResolver(fields={"docs_store": "docs_store"}),
        EnvVarResolver(bindings={"api_token_env": "API_TOKEN"}),
    ]


def test_discover_finds_example_tenants():
    slugs = {s.slug for s in discover_dirs(EXAMPLES)}
    assert slugs == {"acme", "globex"}


def test_build_resolves_bindings_with_provenance():
    reg = build_registry(discover_dirs(EXAMPLES), _resolvers(), today="2026-07-17")
    acme = reg.tenants["acme"]
    assert acme.value("docs_store") == "acme"                 # from frontmatter
    assert acme.value("api_token_env") == "ACME_API_TOKEN"    # from env-var convention
    assert acme.binding("docs_store").resolver == "markdown-frontmatter"
    assert acme.binding("api_token_env").source == "env:ACME_API_TOKEN"


def test_verify_upgrades_status_and_stamps_date():
    # The env var is set → env-var resolver verifies to 'verified'; the tenant.md exists
    # → frontmatter resolver verifies too.
    reg = build_registry(discover_dirs(EXAMPLES), _resolvers(),
                         verify=True, today="2026-07-17")
    acme = reg.tenants["acme"]
    docs = acme.binding("docs_store")
    assert docs.status == "verified"
    assert docs.verified_at == "2026-07-17"


def test_missing_env_var_is_flagged_missing_with_warning(monkeypatch):
    monkeypatch.delenv("ACME_API_TOKEN", raising=False)
    monkeypatch.delenv("GLOBEX_API_TOKEN", raising=False)
    reg = build_registry(discover_dirs(EXAMPLES), _resolvers(), verify=True)
    # value (the var name) still resolves, but live-verify marks it missing...
    assert reg.tenants["acme"].binding("api_token_env").status == "missing"
    # ...and a warning is emitted for the unusable binding.
    assert any("api_token_env" in w and "acme" in w for w in reg.warnings)


def test_registry_roundtrips_through_json(tmp_path):
    reg = build_registry(discover_dirs(EXAMPLES), _resolvers(), today="2026-07-17")
    out = reg.write(tmp_path / "r.json")
    from agent_tenancy import load_registry
    loaded = load_registry(out)
    assert loaded["globex"].value("docs_store") == "globex"
