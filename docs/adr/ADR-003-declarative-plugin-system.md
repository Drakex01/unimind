# ADR-003: Declarative Plugin Manifests and Sandboxed Tools

## Status
Accepted

## Context
UniMind supports cross-domain extensibility (Cybersecurity, Education, Finance, Engineering, Healthcare-info) without altering core application routing. Loading arbitrary Python code dynamically from third-party plugins directly inside the main application process exposes the platform to remote code execution, denial of service, and cross-tenant data leakage.

## Decision
- Plugins are declared via strictly validated YAML manifests (`plugin.yaml`) adhering to a standardized schema version.
- Manifests define identity, version, domain instructions, capability tags, retrieval requirements, allowed tools, permissions, and safety policies.
- Manifest validation is enforced before installation and execution.
- Any executable tools defined by plugins must run via a sandboxed execution boundary with least-privilege permissions, never directly inside the core API runtime.

## Consequences
- Plugins can be securely created, versioned, rolled back, and audited.
- The core orchestration engine interacts only with validated configuration, eliminating plugin-level code injection risks in the main API.
