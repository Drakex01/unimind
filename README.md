# UniMind

> **An Adaptive Multimodal Foundation-Model Platform for Cross-Domain Intelligence, Knowledge Retrieval and Autonomous Task Execution**

UniMind is an enterprise-grade, multi-tenant AI orchestration platform designed to power cross-domain intelligence through modular versioned plugins, capability-aware model routing, citation-grounded RAG, and bounded task workflows.

---

## Architecture Overview

UniMind follows a **modular core with independently scalable execution services**:
- **Apps**:
  - `apps/api`: FastAPI core application handling authentication, tenant RBAC, domain routing, and session management.
  - `apps/web`: React + TypeScript frontend providing chat, workspace, domain plugin, and knowledge base management.
  - `apps/worker-ingestion`: Background job worker for asynchronous document extraction, chunking, and vector indexing.
  - `apps/worker-agent`: Background worker for durable stateful multi-step agent workflows.
  - `apps/sandbox-service`: Isolated execution environment for approved computational tools.
- **Packages**:
  - `packages/domain-contracts`: Protocol specifications and data types for domain behavior.
  - `packages/provider-contracts`: Abstract contracts for foundation model providers and capability declarations.
  - `packages/plugin-sdk`: Manifest schema, validation, and registry tooling for domain plugins.
  - `packages/observability`: Structured logging, OpenTelemetry tracing, and metric instrumentation.
  - `packages/shared-schemas`: Pydantic models for shared request/response payloads.
- **Plugins**:
  - Declarative domain packages (Education, Cybersecurity, Finance, Engineering, Healthcare-info) containing instructions, safety rules, and tool bindings.

---

## Getting Started (Local Development)

### Prerequisites
- Python 3.11+ (Python 3.12 recommended)
- Node.js 18+ and npm
- Git

### Setup
1. Clone the repository and navigate to the project directory:
   ```bash
   cd unimind
   ```
2. Copy environment configuration:
   ```bash
   cp .env.example .env
   ```
3. Initialize the Python virtual environment and install dependencies:
   ```bash
   py -3.12 -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   ```
4. Run tests:
   ```bash
   .\.venv\Scripts\pytest
   ```

---

## Documentation & Progress
- [STATUS.md](STATUS.md): Current implementation progress, completed features, and active sprint items.
- [AGENTS.md](AGENTS.md): Engineering principles, code conventions, and safety guidelines.
- [Architecture Decision Records](docs/adr/): Architectural rationale for foundational design choices.
