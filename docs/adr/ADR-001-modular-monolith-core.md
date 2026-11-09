# ADR-001: Modular Core Architecture with Independent Async Execution

## Status
Accepted

## Context
UniMind requires high architectural velocity during the initial foundation sprint while strictly enforcing multi-tenancy, cross-domain plugin isolation, and future horizontal scalability. Prematurely splitting the system into dozens of independent microservices creates distributed transaction complexity, network overhead, and testing friction before contracts stabilize.

## Decision
We adopt a **modular core with independently scalable execution services**:
- Core API: FastAPI running an asynchronous Python service handling HTTP/WebSocket, authentication, authorization, domain routing, and session management.
- Execution Workers: Independent background worker processes for long-running ingestion, embedding generation, and multi-step agent workflows.
- Modular Boundaries: Clear internal Python packages (`domain-contracts`, `provider-contracts`, `plugin-sdk`, `observability`, `shared-schemas`) with strict dependency direction.
- Storage: Relational database (PostgreSQL in staging/production, SQLite supported for isolated automated unit tests), Qdrant for vector retrieval, Redis for queuing and ephemeral state.

## Consequences
- Fast local iteration with straightforward test fixtures.
- Strict boundaries prevent coupling across modules.
- Services can be separated into distinct container deployments without rewriting business logic.
