# Security & data handling

`agent-tenancy` is a local library. It has no runtime dependencies and does not phone
home.

- **Secrets are never stored in the registry.** A binding's value is an identifier or an
  environment-variable *name*. Capabilities like `EnvKV` read the actual secret from the
  environment at call time, so a generated `tenants.generated.json` is safe to commit.
- **Network:** the core does nothing over the network. A resolver's `verify()` *may* make
  a call (e.g. to confirm an id lives) — that is entirely up to the resolvers you supply;
  the two reference resolvers only touch the local filesystem and the process environment.
- **Isolation is structural, not advisory.** A capability scoped to a tenant exposes no
  argument through which another tenant can be addressed, and keys are sanitized against
  path traversal. This is enforced in code and covered by tests, but it protects only the
  resources reached *through* a capability — a resolver or provider you write is
  responsible for scoping its own backend correctly.

## Reporting a vulnerability

Open a private security advisory on the GitHub repository, or email the maintainer.
Please don't file public issues for security reports.
