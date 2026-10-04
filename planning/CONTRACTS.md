# FinAlly Interface Contracts

The contract of record between agents. Code against this document, not against another agent's
implementation. Changes require orchestrator agreement and an edit here **first**.

Conventions: all money is `float` USD. All timestamps in REST payloads are ISO-8601 UTC strings
(`2026-10-01T14:32:11.482Z`). SSE timestamps are Unix seconds (`float`) — this is the existing
market-data format and is not changing. `user_id` is always `"default"` and never appears in any
REST payload.

---

## 1. Module Layout & Ownership

```
backend/app/
├── main.py              FastAPI app, lifespan, static mount      [backend-api]
├── config.py            env var loading (.env via python-dotenv)  [backend-api]
├── market/              FROZEN — complete, do not modify          [nobody]
├── db/                                                           [database]
│   ├── schema.sql       DDL for all 6 tables
│   ├── connection.py    get_connection(), init_db()
│   ├── seed.py          default user + 10 watchlist tickers
│   └── repositories.py  all data access (see §4)
├── services/                                                     [backend-api]
│   ├── portfolio.py     trade execution, valuation, P&L
│   └── snapshots.py     30s portfolio snapshot background task
├── api/                                                          [backend-api]
│   ├── portfolio.py     /api/portfolio*
│   ├── watchlist.py     /api/watchlist*
│   ├── chat.py          /api/chat*
│   └── health.py        /api/health
└── llm/                                                          [llm]
    ├── client.py        LiteLLM → OpenRouter → Cerebras call
    ├── schemas.py       Pydantic structured-output models
    ├── prompts.py       system prompt + context builder
    ├── mock.py          LLM_MOCK=true deterministic responses
    └── service.py       public entry point (see §5)
```

`frontend/` internal structure is the frontend engineer's call.

---

## 2. SSE Price Stream (already implemented — read only)

`GET /api/stream/prices` → `text/event-stream`

One event carries **every** tracked ticker as a JSON object keyed by symbol. Events are emitted
only when the price cache version changes, at ~500ms cadence. A `retry: 1000` directive is sent
first so `EventSource` reconnects after 1s.

```
retry: 1000

data: {"AAPL":{"ticker":"AAPL","price":190.52,"previous_price":190.48,"timestamp":1759325531.482,"change":0.04,"change_percent":0.021,"direction":"up"},"GOOGL":{...}}
```

```ts
type Direction = "up" | "down" | "flat";

interface PriceUpdate {
  ticker: string;
  price: number;
  previous_price: number;
  timestamp: number;        // Unix SECONDS (float), not ms
  change: number;
  change_percent: number;   // already a percentage, e.g. 0.021 means 0.021%
  direction: Direction;
}

type PriceStreamEvent = Record<string, PriceUpdate>;
```

`change_percent` is tick-over-tick, not daily. The watchlist's "daily change %" must be computed
on the frontend against the first price observed for that ticker since page load.

---

## 3. REST API

Error responses are uniform. Any 4xx/5xx returns:

```json
{ "detail": { "code": "INSUFFICIENT_CASH", "message": "Need $1925.00, have $100.00" } }
```

Codes: `INSUFFICIENT_CASH`, `INSUFFICIENT_SHARES`, `UNKNOWN_TICKER`, `INVALID_QUANTITY`,
`DUPLICATE_TICKER`, `TICKER_NOT_IN_WATCHLIST`, `LLM_ERROR`, `INTERNAL_ERROR`.

### GET /api/portfolio → 200

```json
{
  "cash_balance": 8075.00,
  "positions": [
    {
      "ticker": "AAPL",
      "quantity": 10.0,
      "avg_cost": 190.00,
      "current_price": 192.50,
      "market_value": 1925.00,
      "unrealized_pnl": 25.00,
      "unrealized_pnl_percent": 1.3158,
      "weight": 0.1924
    }
  ],
  "positions_value": 1925.00,
  "total_value": 10000.00,
  "total_unrealized_pnl": 25.00,
  "total_unrealized_pnl_percent": 0.25
}
```

`weight` is `market_value / total_value`, in `[0,1]` — the heatmap sizes rectangles by it.
`total_value` is `cash_balance + positions_value`. A position whose ticker has no cached price
uses `avg_cost` as `current_price` so P&L reads 0 rather than crashing. Empty portfolio returns
`positions: []`, never null.

### POST /api/portfolio/trade → 200

Request: `{ "ticker": "AAPL", "quantity": 10, "side": "buy" }`
`quantity` > 0, fractional allowed. `side` is `"buy"` or `"sell"`. `ticker` is upper-cased
server-side; it need **not** be on the watchlist.

```json
{
  "trade": {
    "id": "uuid", "ticker": "AAPL", "side": "buy",
    "quantity": 10.0, "price": 192.50, "executed_at": "2026-10-01T14:32:11.482Z"
  },
  "cash_balance": 8075.00,
  "position": {
    "ticker": "AAPL", "quantity": 10.0, "avg_cost": 192.50,
    "current_price": 192.50, "market_value": 1925.00,
    "unrealized_pnl": 0.0, "unrealized_pnl_percent": 0.0, "weight": 0.1924
  }
}
```

`position` is `null` when a sell closes the position entirely. Fill price is the current cached
price; `UNKNOWN_TICKER` (400) if the cache has no price for it.

Rules: buy requires `cash >= quantity * price`. Sell requires `held >= quantity`. Buy updates
`avg_cost` to the weighted average; **sell never changes `avg_cost`**. A position reaching
quantity 0 is deleted. Every trade writes a `portfolio_snapshots` row immediately.

### GET /api/portfolio/history?limit=500 → 200

```json
{ "snapshots": [ { "total_value": 10000.00, "recorded_at": "2026-10-01T14:30:00.000Z" } ] }
```

Oldest first, so the P&L chart plots left-to-right without reversing. `limit` defaults to 500,
max 5000, and returns the most recent N (still oldest-first).

### GET /api/watchlist → 200

```json
{
  "tickers": [
    {
      "ticker": "AAPL", "added_at": "2026-10-01T14:00:00.000Z",
      "price": 192.50, "previous_price": 192.48,
      "change": 0.02, "change_percent": 0.0104, "direction": "up"
    }
  ]
}
```

Ordered by `added_at` ascending. Price fields are `null` when the cache has not yet seen a tick.

### POST /api/watchlist → 201

Request: `{ "ticker": "pypl" }` — upper-cased server-side. Returns one entry in the same shape
as above. `DUPLICATE_TICKER` (409) if already present. Adding also calls
`market_source.add_ticker()` so the simulator starts generating it.

### DELETE /api/watchlist/{ticker} → 204

No body. `TICKER_NOT_IN_WATCHLIST` (404) if absent. Also calls
`market_source.remove_ticker()`. Removing a ticker does **not** touch an open position in it.

### POST /api/chat → 200

Request: `{ "message": "buy me 10 apple shares" }`

```json
{
  "id": "uuid",
  "message": "Bought 10 AAPL at $192.50. That's 19% of your portfolio — worth watching.",
  "actions": {
    "trades": [
      { "ticker": "AAPL", "side": "buy", "quantity": 10,
        "status": "executed", "price": 192.50, "error": null }
    ],
    "watchlist_changes": [
      { "ticker": "PYPL", "action": "add", "status": "executed", "error": null }
    ]
  },
  "created_at": "2026-10-01T14:32:11.482Z"
}
```

`status` is `"executed"` or `"failed"`; `error` holds the human-readable reason when failed.
`actions.trades` and `actions.watchlist_changes` are always arrays, never null. A failed trade
is **not** an HTTP error — the response is 200 and the failure is reported inline so the
assistant's text can explain it.

### GET /api/chat/history?limit=50 → 200

> Addition to PLAN.md §8, which lists only `POST /api/chat`. Without it the conversation vanishes
> on reload even though `chat_messages` persists it. Approved as part of the contract.

```json
{
  "messages": [
    { "id": "uuid", "role": "user", "content": "buy me 10 apple shares",
      "actions": null, "created_at": "2026-10-01T14:32:10.000Z" },
    { "id": "uuid", "role": "assistant", "content": "Bought 10 AAPL at $192.50.",
      "actions": { "trades": [...], "watchlist_changes": [] },
      "created_at": "2026-10-01T14:32:11.482Z" }
  ]
}
```

Oldest first. `actions` is null for user messages.

### GET /api/health → 200

```json
{ "status": "ok", "market_source": "simulator", "tracked_tickers": 10, "db": "ok" }
```

`market_source` is `"simulator"` or `"massive"`. Must not require the DB to be warm — it is the
Docker healthcheck.

---

## 4. Repository API — `app.db.repositories`

Owned by `database-engineer`, consumed by `backend-api-engineer` and (via services only)
`llm-engineer`. Synchronous `sqlite3` is correct here: SQLite writes serialize anyway and FastAPI
runs sync handlers in a threadpool. Connections are per-call, `check_same_thread=False`,
`PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`, `row_factory = sqlite3.Row`.

```python
# Lifecycle
def init_db(db_path: str | None = None) -> None
    """Create tables if absent and seed defaults if empty. Idempotent.
    Path resolution: argument > FINALLY_DB_PATH env var > 'db/finally.db'."""

# Profile
def get_cash_balance(user_id: str = "default") -> float
def set_cash_balance(amount: float, user_id: str = "default") -> None

# Watchlist
def list_watchlist(user_id: str = "default") -> list[WatchlistRow]   # by added_at ASC
def add_watchlist_ticker(ticker: str, user_id: str = "default") -> WatchlistRow
    """Raises DuplicateTickerError if (user_id, ticker) exists."""
def remove_watchlist_ticker(ticker: str, user_id: str = "default") -> None
    """Raises TickerNotFoundError if absent."""

# Positions
def list_positions(user_id: str = "default") -> list[PositionRow]
def get_position(ticker: str, user_id: str = "default") -> PositionRow | None
def upsert_position(ticker: str, quantity: float, avg_cost: float,
                    user_id: str = "default") -> PositionRow
def delete_position(ticker: str, user_id: str = "default") -> None

# Trades
def record_trade(ticker: str, side: str, quantity: float, price: float,
                 user_id: str = "default") -> TradeRow
def list_trades(limit: int = 100, user_id: str = "default") -> list[TradeRow]   # newest first

# Snapshots
def record_snapshot(total_value: float, user_id: str = "default") -> None
def list_snapshots(limit: int = 500, user_id: str = "default") -> list[SnapshotRow]  # oldest first

# Chat
def record_chat_message(role: str, content: str, actions: dict | None = None,
                        user_id: str = "default") -> ChatRow
    """`actions` is JSON-encoded on write."""
def list_chat_messages(limit: int = 50, user_id: str = "default") -> list[ChatRow]
    """Oldest first. `actions` is JSON-decoded back to dict | None."""

# Atomic trade application — the ONE write path for trades
def apply_trade(ticker: str, side: str, quantity: float, price: float,
                user_id: str = "default") -> tuple[TradeRow, PositionRow | None, float]
    """Single transaction: validate funds/shares, update cash, upsert-or-delete the
    position, insert the trade row. Returns (trade, position_or_None, new_cash_balance).
    Raises InsufficientCashError / InsufficientSharesError / InvalidQuantityError.
    Nothing else may write cash, positions, or trades."""
```

Rows are frozen dataclasses in `app/db/models.py` with `to_dict()`. Exceptions subclass
`app.db.errors.RepositoryError` and map to the §3 error codes.

`apply_trade` existing in the DB layer is deliberate: atomicity across three tables belongs where
the transaction is, and it means a trade can never half-apply whether it came from the trade bar
or the LLM.

---

## 5. LLM Service API — `app.llm.service`

Owned by `llm-engineer`, consumed by `backend-api-engineer` from `api/chat.py`.

```python
@dataclass(frozen=True)
class ChatResult:
    message: str
    trades: list[ProposedTrade]              # ticker, side, quantity
    watchlist_changes: list[ProposedChange]  # ticker, action: "add" | "remove"

async def generate_chat_response(
    user_message: str,
    portfolio: dict,          # exactly the GET /api/portfolio payload
    watchlist: list[dict],    # exactly GET /api/watchlist's "tickers"
    history: list[dict],      # [{"role","content"}], oldest first, caller-trimmed
) -> ChatResult:
    """Call the LLM and return its parsed intent. Executes NOTHING.
    Honours LLM_MOCK=true. Never raises for a malformed model response —
    degrades to ChatResult(message=<explanatory text>, trades=[], watchlist_changes=[]).
    Raises LLMError only when the provider is unreachable or unauthenticated."""
```

The division of labour that matters: the LLM layer **decides**, the backend **executes**. The
backend loops over `result.trades`, calls the same `portfolio_service.execute_trade` the trade bar
uses, catches per-trade failures, and assembles the `actions` block in §3. This keeps trade
validation in exactly one place and keeps the LLM layer independently testable with no database.

Model: `openrouter/openai/gpt-oss-120b`, `extra_body={"provider": {"order": ["cerebras"]}}`,
`reasoning_effort="low"`, structured output via `response_format=<pydantic model>`. Use the
`cerebras` skill. `OPENROUTER_API_KEY` comes from the environment.

### Mock mode (`LLM_MOCK=true`)

Deterministic, keyword-driven, no network — the E2E suite depends on these exact behaviours:

| User message contains | Mock returns |
|---|---|
| `buy` + a ticker + a number | that buy in `trades`, message naming ticker and quantity |
| `sell` + a ticker + a number | that sell in `trades` |
| `add` + a ticker | `watchlist_changes: [{add}]` |
| `remove` + a ticker | `watchlist_changes: [{remove}]` |
| anything else | a fixed analysis string citing `total_value`, no actions |

---

## 6. Static Serving

Next.js `output: 'export'` emits `frontend/out/`. Docker copies it to `/app/static/`. FastAPI
mounts it **after** all `/api/*` routes:

```python
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
```

`html=True` serves `index.html` for `/`. `frontend/next.config.ts` sets `output: 'export'`,
`images: { unoptimized: true }`, and `trailingSlash: true`. Frontend calls same-origin relative
paths (`/api/...`) only — no base URL, no CORS, no env-var API host.

`main.py` must tolerate a missing `static_dir` (local backend-only development) by skipping the
mount with a warning rather than crashing.

---

## 7. Environment & Startup

```bash
OPENROUTER_API_KEY=      # required for live chat
MASSIVE_API_KEY=         # empty → simulator
LLM_MOCK=false           # true → deterministic mock, no network
FINALLY_DB_PATH=db/finally.db
```

There is currently **no `.env` in the repo** (it is gitignored). `devops-engineer` commits
`.env.example`; the user supplies the real key. Everything except live chat must work with no
keys at all.

Lifespan startup order, owned by `backend-api-engineer`:

1. `init_db()`
2. `cache = PriceCache()`
3. `source = create_market_data_source(cache)`
4. `await source.start([t.ticker for t in list_watchlist()])`
5. start the 30s snapshot task
6. include routers, then `create_stream_router(cache)`, then mount static

Shutdown: cancel the snapshot task, `await source.stop()`.

`PriceCache` and the source are held on `app.state` and reached through FastAPI dependencies —
no module-level globals.
