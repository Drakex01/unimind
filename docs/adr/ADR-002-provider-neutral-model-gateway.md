# ADR-002: Capability-Aware Provider-Neutral Model Gateway

## Status
Accepted

## Context
UniMind connects to multiple foundation model providers (Google Gemini API, OpenAI API, Ollama, self-hosted models). Different models vary drastically in capabilities (vision, audio, streaming, function calling, structured outputs, context window, pricing, data privacy guarantees). Hardcoding provider SDK calls across the codebase prevents seamless failover, tenant policy enforcement, and auditability.

## Decision
All model invocations must pass through an abstract `ModelProvider` contract and a centralized `ModelGateway`:
- Every adapter explicitly declares its `ModelCapabilities` (token limits, supported modalities, tool-calling support, structured output support).
- Requests define `TaskRequirements` rather than hardcoding a vendor model name.
- The Gateway checks tenant policy constraints (e.g. data residency, approved provider allowlists) before routing.
- The Gateway provides rate-limiting, exponential backoff retries with jitter, circuit breaking, token/cost accounting, and audit logging.

## Consequences
- Codebase remains vendor-neutral.
- Sensitive data is never routed to unapproved providers.
- Local mock providers can be safely used in automated test suites without incurring costs or network flakiness.
