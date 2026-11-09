# UniMind Engineering Principles & Agent Operating Model

## Non-Negotiable Engineering Principles
1. **Inspect before modifying**: Always inspect existing code and git status before proposing or writing modifications.
2. **Preserve user work**: Never overwrite or delete existing working files without explaining the impact.
3. **Verified increments**: Build in small, verified steps. Do not attempt monolithic code dumps.
4. **Tenant isolation**: Every database query, vector search, file access, and tool invocation must be strictly scoped to the authenticated tenant and workspace.
5. **Provider neutrality**: All foundation models are integrated behind the `ModelGateway` interface. Never call vendor SDKs directly from route handlers or domain services.
6. **Declarative plugins**: Domain-specific logic resides in versioned plugin packages (`plugin.yaml`), not hardcoded in the core router.
7. **Zero-trust inputs**: Every upload, document snippet, query, and model output is treated as untrusted. Sanitize inputs and validate outputs.
8. **No host code execution**: Never execute user-supplied or model-generated code directly on the host process.
9. **Never leak secrets**: No API keys, credentials, or stack traces exposed to clients or checked into source control.
10. **Test with every increment**: A feature without automated tests is incomplete.
11. **Keep `STATUS.md` updated**: Record completed features, known gaps, blocked items, and next milestones after each work unit.
