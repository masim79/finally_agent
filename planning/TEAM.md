# FinAlly Agent Team

Six specialist agents build the remainder of the platform. Market data (`backend/app/market/`)
is already complete — see `MARKET_DATA_SUMMARY.md`.

Agent definitions live in `.claude/agents/`. The orchestrator (main session) spawns them,
sequences the phases, and arbitrates contract changes.

## Roster

| Agent | Owns | Model |
|---|---|---|
| `database-engineer` | `backend/app/db/` — schema, lazy init, seed, repositories | Sonnet 5 |
| `backend-api-engineer` | `backend/app/main.py`, `backend/app/api/`, `backend/app/services/` | Sonnet 5 |
| `llm-engineer` | `backend/app/llm/` — LiteLLM/OpenRouter/Cerebras, structured output, mock mode | Opus 5 |
| `frontend-engineer` | `frontend/` — Next.js static export, SSE, charts, Tailwind dark theme | Opus 5 |
| `devops-engineer` | `Dockerfile`, `docker-compose.yml`, `scripts/`, `.env.example`, `.dockerignore` | Sonnet 5 |
| `integration-tester` | `test/` — Playwright E2E + `docker-compose.test.yml` | Sonnet 5 |

## File Ownership Is Exclusive

An agent writes **only** inside the paths it owns. Needing a change outside your paths is a
message to the owner, not an edit. This is the single rule that keeps six agents from
colliding, and it is not negotiable.

`backend/app/market/` is **frozen**. It is complete, tested (73 tests), and reviewed. Read it,
import from it, do not modify it. If you believe it has a bug, report it to the orchestrator
with a failing test.

## Shared Contracts

`CONTRACTS.md` is the contract of record: REST shapes, SSE event shape, the repository API, the
LLM service API. Every agent codes against it rather than against another agent's
implementation, which is what makes parallel work possible.

Changing a contract requires the orchestrator's agreement and an edit to `CONTRACTS.md` first,
announced to every consumer. Never silently diverge — a frontend built against a shape the
backend abandoned is the most expensive failure mode available to this team.

## Build Phases

```
Phase 1  database-engineer                           (schema + repositories)
Phase 2  backend-api-engineer  ‖  llm-engineer  ‖  frontend-engineer  ‖  devops-engineer
Phase 3  integration-tester                          (E2E against the real container)
Phase 4  fix loop: tester reports → owners fix → tester re-runs
```

Phase 2 agents start against `CONTRACTS.md` immediately; the frontend does not wait for a live
backend, and the tester writes specs before the app is up.

## Status Board

Append to your own section of `STATUS.md` when you finish a unit of work, become blocked, or
change something another agent consumes. Read the other sections before you start. Never edit
another agent's section.

## Definition of Done (every agent)

1. Code complete against `CONTRACTS.md`.
2. Unit tests written and passing — `uv run --extra dev pytest` (backend) or `npm test` (frontend).
3. Lint clean — `uv run --extra dev ruff check app/ tests/` or `npm run lint`.
4. `STATUS.md` updated.

"It should work" is not done. Run the tests and paste the result.
