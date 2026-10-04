"""Chat message persistence: actions JSON round-tripping and ordering."""

from __future__ import annotations

from app.db import repositories as repo


def test_record_chat_message_with_none_actions_round_trips(initialized_db):
    row = repo.record_chat_message("user", "buy me 10 apple shares")

    assert row.actions is None
    fetched = repo.list_chat_messages()
    assert fetched[0].actions is None
    assert fetched[0].content == "buy me 10 apple shares"
    assert fetched[0].role == "user"


def test_record_chat_message_with_actions_dict_round_trips(initialized_db):
    actions = {
        "trades": [
            {"ticker": "AAPL", "side": "buy", "quantity": 10, "status": "executed",
             "price": 192.5, "error": None}
        ],
        "watchlist_changes": [],
    }

    repo.record_chat_message("assistant", "Bought 10 AAPL.", actions=actions)

    fetched = repo.list_chat_messages()
    assert fetched[0].actions == actions  # exact structural round-trip, nested lists/dicts intact


def test_list_chat_messages_oldest_first(initialized_db):
    first = repo.record_chat_message("user", "hello")
    second = repo.record_chat_message("assistant", "hi there")
    third = repo.record_chat_message("user", "buy AAPL")

    messages = repo.list_chat_messages()

    assert [m.id for m in messages] == [first.id, second.id, third.id]


def test_list_chat_messages_respects_limit(initialized_db):
    for i in range(5):
        repo.record_chat_message("user", f"message {i}")

    messages = repo.list_chat_messages(limit=2)

    assert len(messages) == 2
    assert messages[0].content == "message 3"
    assert messages[1].content == "message 4"


def test_list_chat_messages_scoped_per_user(initialized_db):
    repo.record_chat_message("user", "hi", user_id="alice")

    assert repo.list_chat_messages() == []
    assert len(repo.list_chat_messages(user_id="alice")) == 1
