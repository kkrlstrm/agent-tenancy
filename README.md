# agent-tenancy

> **Keep tenant routing out of the model.**
> Resolve the tenant *before* the agent runs, then hand it capabilities that expose
> content-level operations only — no tenant id, repo, namespace, or connection string for
> the model to choose or hallucinate.

`agent-tenancy` is a tenant-binding and capability-scoping layer for multi-tenant agent
runtimes. It generates a verified registry of each tenant's resource bindings — which
repo, which database, which channel, which credential — then turns those bindings into
**tenant-scoped capabilities** minted before an agent enters the loop.

The model never constructs a tenant id, a repository path, a namespace, an account URL,
or a connection string. It sees content-level operations like `get("welcome")`;
deterministic code owns the resource routing.

```python
acme = docs.for_tenant(tenant("acme", registry))
acme.get("welcome")
# No tenant, repository, namespace, or path selector is exposed on the handle.
```

**Deterministic tenant routing. Probabilistic content generation.**

---

## The move, in one contrast

```
Generic agent tenancy
  prompt ──▶ model picks tenant id / repo / namespace / creds ──▶ generic tools ──▶ shared infra
             └─ symbolic id reasoning by a probabilistic model: hallucination + leakage risk

agent-tenancy
  tenant resolved deterministically ──▶ scoped capabilities minted ──▶ model sees content-only ops
             └─ the model is never a participant in tenant routing
```

This removes two recurring risks in multi-tenant agent systems:

- **Misdirection** — the model can't substitute or hallucinate another tenant's
  identifier through a scoped interface, because the interface has no identifier argument.
- **Context leakage** — tenant wiring doesn't have to be repeated through prompts and tool
  calls, so it can't drift or bleed across a long session.

## The problem

Most multi-tenant systems assume *deterministic application code* constructs resource
identifiers. Agent systems often do the opposite: they hand a **probabilistic model** the
tenant ids, repo names, database namespaces, channel ids, and credential references as
prompt text and tool arguments, and ask it to plug them into calls at runtime. That is
exactly the symbolic id/url reasoning LLMs are worst at — and every id in the prompt is
another thing that can be hallucinated or leak between tenants.

## The architectural move

1. **Resolve the tenant first** — from your sources of truth, into a generated registry of
   provenance-stamped bindings, optionally verified against the real systems.
2. **Mint a scoped capability** — `for_tenant(t)` captures tenant `t`'s binding and returns
   a handle whose methods take only content (`get("welcome")`), with no tenant/namespace
   selector.
3. **Let the model operate on content only** — routing is already decided, in code, before
   the model runs.

## The guarantee (stated precisely)

After scoping, **the model cannot redirect a correctly-implemented scoped capability to
another tenant** — there is no tenant, namespace, repo, or path argument on the handle to
manipulate, and keys are sanitized so a value argument can't smuggle a traversal.

This is a guarantee about the **capability interface**, not a whole-process sandbox. A
provider you write could still expose an unsafe method, share a misconfigured client, or
ignore its scope; the process can reach the filesystem or credentials if those are exposed
separately. What this package makes unrepresentable is *tenant selection through the tool
surface the agent sees*. That's the boundary — a narrow, real, and load-bearing one.

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
globex.get("welcome")                           # -> None  (can't reach Acme's data)
globex.keys()                                   # -> []    (can't even see Acme's keys)
```

The caller never names a namespace. There is no argument on `get`/`put`/`keys` through
which `globex` could read `acme` — and the test suite asserts that by inspecting the
method signatures, not just by exercising a runtime check.

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

## Provenance — why a binding is what it is

The registry is a **generated artifact with an audit trail**, not a hand-kept config. A
registry that stores only values can't tell you why a tenant is misconfigured; every
binding here is a `Binding`, not a bare string:

```python
b = tenant("acme", reg).binding("docs_store")
b.value        # 'acme'
b.resolver     # 'markdown-frontmatter'   ← which resolver produced it
b.source       # 'examples/tenants/acme/tenant.md'
b.status       # 'verified'               ← resolved | verified | missing | unverifiable
b.verified_at  # '2026-07-17'
```

Status is a **graded state, not a boolean** — `--verify` upgrades `resolved → verified` by
checking each binding live (the file still exists, the env var is actually set), and
demotes to `missing` when it's gone. `tenancy verify` reports every non-usable binding
across the registry. The generator discovers, resolves, verifies, and preserves
provenance — a tenant wiring pipeline, not an injection helper.

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

## Where this fits — an agent control-plane primitive

An agent should generate and interpret **content**. It should not be the thing that
decides which tenant it represents, which credential to use, which repository to access,
which namespace to query, which policy boundary applies, or where an action executes.
Those are **control-plane** decisions.

`agent-tenancy` takes one of them — tenant and resource binding — out of the model's hands
and makes it deterministic, inspectable, and testable. It's a reference architecture for
putting a deterministic tenant boundary around a probabilistic system, and it composes
with whatever owns the other control-plane responsibilities.

## Related architectural patterns

The design leans on four established ideas rather than inventing new ones:

- **Capability-based security** — a scoped handle is an unforgeable capability: holding it
  grants access to exactly one tenant's resources, and there's no ambient way to name
  another. Authority travels with the handle, not with an argument.
- **Deterministic control planes** — keep the probabilistic component off the routing
  path; let it decide content, let code decide addressing.
- **Immutable definitions** — the tenant record is frozen and its bindings are read-only,
  so the definition can't drift under a running system; per-run state lives in the
  ephemeral scoped handle.
- **Configuration provenance** — every binding records its source and verification status,
  so a misconfiguration is explainable instead of mysterious.

## Not in scope

- **It's not an agent framework or orchestrator.** It's the tenant-binding layer you put
  *under* one.
- **It's not a generic multi-tenancy platform.** No auth, authorization policy, row-level
  security, credential lifecycle, workload isolation, provisioning, or billing — it does
  one thing: bind the tenant and scope the capability.
- **It doesn't manage secrets.** It records where a secret lives (an env-var name); your
  secret manager owns the value.
- **Reference resolvers/providers are illustrative.** They demonstrate the pattern on
  synthetic tenants; production use means writing your own.

## Testing

Zero dependencies, fully offline:

```bash
pip install -e ".[dev]"
pytest -q
```

## License

GNU AGPL-3.0-or-later — see [LICENSE](LICENSE).
