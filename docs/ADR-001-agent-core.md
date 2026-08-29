# ADR-001 — Core agent should not depend on OpenClaw

**Status:** Accepted for V0.1

## Decision
Implement a small native Ollama tool-calling core and make OpenClaw an optional orchestration layer.

## Why
- The analytics engine must remain usable if an orchestration project changes APIs.
- Native Ollama tool calling is sufficient for the first deterministic tool loop.
- OpenClaw remains valuable later for skills, MCP/plugin tool projection, scheduling and multi-agent workflows.

## Risk
We temporarily duplicate a small amount of orchestration logic.

## Revisit
Phase 2 after OpenClaw integration benchmark and sandbox evaluation.
