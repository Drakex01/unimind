# UniMind Security Threat Model & Mitigations

Mapped against OWASP Top 10 for Large Language Models (LLM) and enterprise multi-tenancy requirements.

| Threat Category | Attack Vector | UniMind Architectural Mitigation |
| :--- | :--- | :--- |
| **LLM01: Prompt Injection** | Untrusted content inside uploaded documents attempts to instruct model to ignore rules or leak secrets. | Retrieved document snippets are demarcated as untrusted evidence blocks, never injected into the system instruction block. System prompts strictly mandate ignoring instructions inside evidence. |
| **LLM02: Insecure Output Handling** | Model generates malicious script tags or markdown links. | Client UI sanitizes model text before rendering. Code execution is strictly sandboxed. |
| **LLM06: Sensitive Information Disclosure** | Cross-tenant data leakage via shared vector stores or database tables. | Hard tenant boundaries: All vector searches, file paths, and database queries require `org_id` and `workspace_id`. Cross-tenant retrieval is mathematically impossible. |
| **LLM07: Insecure Plugin Design** | Third-party plugins execute arbitrary code in the main API process. | Plugins are declarative YAML packages validated with strict Pydantic schemas. Dynamic code loading is prohibited in core API. |
| **LLM08: Excessive Agency** | Agent workflows enter unbounded autonomous execution loops. | Workflows are bounded with deterministic step counts (max 4–8), per-step timeouts, and mandatory audit records. |
| **Path Traversal / Arbitrary File Overwrite** | Malicious upload with filename `../../etc/passwd`. | `LocalStorageService` resolves paths, rejects filenames with directory separators, and verifies `path.startswith(base_dir)`. |
| **Unauthenticated / Broken Object Authorization** | Client supplies another tenant's `org_id` or `workspace_id` in headers. | `TenantContext` verifies that the authenticated user possesses an active `OrganizationMembership` in the target organization before granting access. |
