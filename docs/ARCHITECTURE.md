# Architecture 1.0 RC1

```text
                    Browser UI / CLI
                           |
                        FastAPI
                           |
                    Conversation Store
                           |
                      Ollama Agent
                 Fast / Main / Deep model
                           |
                  High-Level Tool Surface
       +---------+---------+---------+---------+
       |         |         |         |         |
      Data    Analytics  Business    BI       NPL
       |         |         |         |         |
       +---------+----+----+---------+---------+
                    |    |
                 SQL/DB  Local RAG
                    |    |
                 Memory / Mentor
                    |
          Workspace Sandbox + Audit
```

## Design principles

### 1. LLM ≠ calculation engine
The language model decides what to inspect, which tool family to call and how to explain the result. Numeric/statistical calculations are performed by tested Python/SQL functions.

### 2. Small high-level tool surface
The implementation contains many internal methods, but the model sees a limited number of high-level tool families such as `analytics_engine`, `business_engine`, `bi_engine`, and `npl_engine`. This reduces tool-selection entropy.

### 3. Local-first privacy
- Workspace sandbox for file tools
- Web disabled by default
- Ollama loopback by default
- Remote Ollama and cloud model tags blocked by default
- Exact-argument approval queue for agent-requested writes/external calls
- Optional API token
- Database secrets only from environment variables
- Read-only DB account strongly recommended

### 4. Human-approved learning
The model can propose a candidate memory/business rule but cannot approve it through its agent tool surface. Promotion is a human action.

### 5. OpenClaw optional
OpenClaw is useful as an orchestration/scheduling/skill layer, but deterministic analytics and the FastAPI service remain independent.

### 6. No arbitrary shell/Python tool in the LLM surface
A local model being “local” does not make arbitrary execution safe. The LLM receives narrow functions instead of unrestricted terminal access.

## Data flow

```text
User question
   |
   +--> inspect/profile data if unfamiliar
   |
   +--> select analysis family
   |
   +--> deterministic tool executes
         (or queues a write/external call for human approval)
   |
   +--> bounded result returned to LLM
   |
   +--> LLM explains in selected personality/mentor level
   |
   +--> audit + local conversation history
```

## RAG flow

```text
workspace/knowledge document
      -> extract text
      -> chunk
      -> SQLite FTS5
      -> optional local Ollama embeddings
      -> retrieved path/chunk
      -> LLM source-grounded explanation
```

## Remote access
Remote use is deliberately not bundled as public hosting. Keep the app on loopback unless using a private authenticated network/VPN + firewall + company approval. See `REMOTE_ACCESS.md`.
