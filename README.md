# agent-tenancy

> **Compile-time tenant binding for multi-tenant agents.**
> A generated, provenance-stamped registry + structurally-scoped capabilities — so an
> agent never constructs an id, and never can touch the wrong tenant.

If you run one agent across many tenants — clients, workspaces, orgs — you have a wiring
problem: *which* repo, *which* database, *which* channel is this tenant's? The common
answer is to stuff the ids into the prompt ("you are working on Acme, project 4172,
channel C08…") and let the model plug them into tool calls at runtime. That does two bad
things: it leaks tenant context across a long session, and it asks the LLM to do
**symbolic id/url reasoning** — exactly the thing it hallucinates.

`agent-tenancy` moves that binding out of the prompt and into generated, typed code:

- **A registry** maps each tenant → its binding targets, **generated** from your sources
  of truth (not hand-maintained), with every binding stamped with where it came from and
  whether it still verifies.
- **Capabilities** turn a tenant's binding into a **scoped handle** whose methods take
  only content (`get("welcome")`), never a tenant or a path. The id/url is computed in
  plain code; the model just names an intent.
- **Isolation is structural.** A handle scoped to Acme has no argument through which to
  address Globex. Cross-tenant access isn't blocked by a check you could forget — it's
  unreachable by construction.

```console
$ tenancy show acme -r tenants.generated.json
tenant: acme
  ✓ docs_store     'acme'
    └ verified · resolver markdown-frontmatter · source examples/tenants/acme/tenant.md verified 2026-07-17
  ✓ api_token_env  'ACME_API_TOKEN'
    └ verified · resolver env-var · source env:ACME_API_TOKEN verified 2026-07-17
```

---

## Why this shape

Three commitments, each borrowed from how funded AI-infra runtimes are actually built
(see [Design lineage](#design-lineage)):

**1. Deterministic wiring, not model-constructed wiring.** The caller (often an LLM)
names an intent — "read this doc", "get the token". It never assembles a project id, a
`%2F`-encoded path, or a connection string. Those are computed from the tenant binding in
typed code, where they can't be hallucinated.

**2. Structural isolation, not policy isolation.** `for_tenant(t)` captures tenant `t`'s
binding and hands back a handle that can reach `t`'s resources and no other — because its
methods expose no tenant/namespace/path parameter, and keys are sanitized so you can't
traverse out. "We architecturally cannot" beats "we promise not to."

**3. Definition / execution split.** A `Tenant` is a frozen config record — zero-cost at
rest, and its bindings map is read-only so the definition can't drift under you. Any
per-run state lives in the ephemeral scoped handle, minted fresh per call. The reusable
definition and the throwaway execution are different objects.

## Install

```bash
pip install agent-tenancy        # once published
# or from source:
git clone https://github.com/kkrlstrm/agent-tenancy
cd agent-tenancy && pip install -e .
```

Pure standard library — **zero runtime dependencies**. Python 3.9+.

## Quickstart

**1. Generate a registry** from a directory of tenant folders (each with a `tenant.md`):

```bash
tenancy generate examples/tenants -o tenants.generated.json --verify
```
```text
wrote tenants.generated.json — 2 tenant(s)
  acme:   ✓ docs_store, ✓ api_token_env
  globex: ✓ docs_store, ✓ api_token_env
```

**2. Reach a tenant's resources through a scoped capability** ([`examples/demo.py`](examples/demo.py)):

```python
from agent_tenancy import tenant, load_registry
from agent_tenancy.providers import LocalStore

reg   = load_registry("tenants.generated.json")
store = LocalStore(root="./data")          # one provider, configured once

acme = store.for_tenant(tenant("acme", reg))   # a handle scoped to Acme
acme.put("welcome", "hello from acme")
acme.get("welcome")                             # -> 'hello from acme'

globex = store.for_tenant(tenant("globex", reg))
globex.get("welcome")                           # -> None  (Acme's data is unreachable)
globex.keys()                                   # -> []    (can't even see Acme's keys)
```

The caller never names a namespace. There is no argument on `get`/`put`/`keys` through
which `globex` could read `acme` — that's the guarantee, and it's a passing test, not a
promise.

## How it works

Three layers, each swappable:

| Layer | What it is | Ships |
|---|---|---|
| **Registry** (`Tenant`, `Binding`) | Immutable tenant definition; each binding carries `value / resolver / source / status / verified_at` | core |
| **Resolvers** (`Resolver`) | The generator's plug-points — one per source of truth. Resolve a binding + optionally verify it live | ABC + 2 reference resolvers |
| **Capabilities** (`Capability`) | Turn a binding into a tenant-scoped handle; the router that keeps the model off the wiring | ABC + 2 reference providers |

The two reference resolvers (`MarkdownFrontmatterResolver`, `EnvVarResolver`) and two
reference providers (`LocalStore`, `EnvKV`) exist to make the pattern runnable end-to-end
on synthetic tenants. **In your own system you write the resolvers that hit your sources
and the providers that wrap your services**, and register them the same way — see
[Bring your own](#bring-your-own).

## The isolation guarantee, precisely

Splitting tenants across a registry is easy; the interesting part is that the *capability*
can't be talked into crossing the line. Two things enforce it:

- **No selector argument.** A scoped handle's methods take content only (`key`, `value`).
  The target namespace is captured at `for_tenant()` time from the tenant's binding — it
  is not a parameter, so there is no way to pass another tenant's.
- **Sanitized keys.** Keys are validated (`^[A-Za-z0-9._-]+$`, no `..`), so you can't
  smuggle a traversal (`../globex/...`) through the content argument either.

A tenant whose binding didn't resolve can't even be scoped — `for_tenant()` raises rather
than hand you a half-bound handle. (`tests/test_capability.py` asserts all of this.)

## Provenance — why a binding is what it is

A registry that stores only values can't tell you *why* a tenant is misconfigured. Every
binding here is a `Binding`, not a bare string:

```python
b = tenant("acme", reg).binding("docs_store")
b.value        # 'acme'
b.resolver     # 'markdown-frontmatter'   ← which resolver produced it
b.source       # 'examples/tenants/acme/tenant.md'
b.status       # 'verified'               ← resolved | verified | missing | unverifiable
b.verified_at  # '2026-07-17'
```

Status is a **graded state, not a boolean** — `--verify` upgrades `resolved → verified`
by checking each binding live (the file still exists, the env var is actually set), and
demotes to `missing` when it's gone. `tenancy verify` reports every non-usable binding
across the registry.

## Secrets stay out of the registry

A binding's *value* is an identifier or an env-var **name** — never the secret itself.
`EnvKV` reads the actual value from the environment at call time, so the generated
`tenants.generated.json` is safe to commit. The registry says *where* the secret is, not
what it is.

## Bring your own

The public package is the **mechanism**; your wiring is config + plugins. A private repo
uses it like this:

```python
from agent_tenancy.generate import build_registry, TenantSource
from agent_tenancy import Resolver, Capability

class GitLabRepoResolver(Resolver):        # your source of truth
    name = "gitlab"
    def resolve(self, src): ...            # -> {"repo": Binding(...)}
    def verify(self, binding): ...         # -> hit glab, mark verified/missing

class GitLabFiles(Capability):             # your service, tenant-scoped
    binding_name = "repo"
    def _scope(self, slug, project_id): ...# -> a handle that reads only that repo

reg = build_registry(my_sources, [GitLabRepoResolver(), ...], verify=True)
```

Nothing about your tenants, services, or credentials lives in this package — only the
schema, the generator, and the scoping discipline.

## Design lineage

The shape here isn't invented; it's the convergent practice of several funded AI-infra
runtimes, applied to tenancy:

- **Deterministic wiring, model off the control path** — Band routes on `@mention` (no
  LLM), Bolna evaluates edges deterministically and falls back to a model only on a miss.
- **Structural isolation over policy** — SurrealDB enforces record-level security in the
  query planner (not the app); Natural uses server-side hard capability exclusions.
- **Definition / execution split** — Band models an agent as a config record and a run as
  a throwaway, state-isolated instance.
- **Per-attribute provenance** — OpsMill tags every attribute with its source and owner so
  a misconfiguration is explainable, not mysterious.

## Not in scope

- **It's not an agent framework or an orchestrator.** It's the tenant-binding layer you
  put *under* one.
- **It doesn't manage secrets.** It records where a secret lives (an env-var name); your
  secret manager owns the value.
- **Reference resolvers/providers are illustrative.** The markdown/env resolvers and the
  local-store/env-kv providers demonstrate the pattern on synthetic tenants; production
  use means writing your own.

## Testing

Zero dependencies, fully offline:

```bash
pip install -e ".[dev]"
pytest -q
```

## License

Apache 2.0 — see [LICENSE](LICENSE).
