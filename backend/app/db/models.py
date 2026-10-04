"""Frozen row dataclasses for FinAlly's SQLite tables.

Every row type carries a `to_dict()` for JSON serialization and a `from_row()`
classmethod that builds the dataclass from a `sqlite3.Row` (requires
`row_factory = sqlite3.Row`, which `app.db.connection.get_connection()` sets).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


def utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string with millisecond precision ('...Z')."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class WatchlistRow:
    id: str
    user_id: str
    ticker: str
    added_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "ticker": self.ticker,
            "added_at": self.added_at,
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> WatchlistRow:
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            ticker=row["ticker"],
            added_at=row["added_at"],
        )


@dataclass(frozen=True, slots=True)
class PositionRow:
    id: str
    user_id: str
    ticker: str
    quantity: float
    avg_cost: float
    updated_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "ticker": self.ticker,
            "quantity": self.quantity,
            "avg_cost": self.avg_cost,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> PositionRow:
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            ticker=row["ticker"],
            quantity=row["quantity"],
            avg_cost=row["avg_cost"],
            updated_at=row["updated_at"],
        )


@dataclass(frozen=True, slots=True)
class TradeRow:
    id: str
    user_id: str
    ticker: str
    side: str
    quantity: float
    price: float
    executed_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "ticker": self.ticker,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "executed_at": self.executed_at,
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> TradeRow:
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            ticker=row["ticker"],
            side=row["side"],
            quantity=row["quantity"],
            price=row["price"],
            executed_at=row["executed_at"],
        )


@dataclass(frozen=True, slots=True)
class SnapshotRow:
    id: str
    user_id: str
    total_value: float
    recorded_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "total_value": self.total_value,
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> SnapshotRow:
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            total_value=row["total_value"],
            recorded_at=row["recorded_at"],
        )


@dataclass(frozen=True, slots=True)
class ChatRow:
    id: str
    user_id: str
    role: str
    content: str
    actions: dict | None
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "role": self.role,
            "content": self.content,
            "actions": self.actions,
            "created_at": self.created_at,
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> ChatRow:
        raw_actions = row["actions"]
        actions = json.loads(raw_actions) if raw_actions is not None else None
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            role=row["role"],
            content=row["content"],
            actions=actions,
            created_at=row["created_at"],
        )
