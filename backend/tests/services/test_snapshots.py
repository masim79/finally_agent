"""Unit tests for the 30s portfolio snapshot background task."""

from __future__ import annotations

import asyncio

from app.db import repositories as repo
from app.services import snapshots as svc


async def _run_briefly(cache, interval: float, duration: float) -> None:
    task = svc.start_snapshot_task(cache, interval=interval)
    await asyncio.sleep(duration)
    await svc.stop_snapshot_task(task)
    assert task.cancelled() or task.done()


async def test_snapshot_loop_records_periodically(price_cache):
    await _run_briefly(price_cache, interval=0.01, duration=0.05)
    assert len(repo.list_snapshots()) >= 2


async def test_snapshot_loop_survives_a_failing_tick(price_cache, monkeypatch):
    calls = {"n": 0}
    original_record_snapshot = repo.record_snapshot

    def flaky_record_snapshot(total_value, user_id="default"):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated transient failure")
        return original_record_snapshot(total_value, user_id=user_id)

    monkeypatch.setattr("app.services.snapshots.repo.record_snapshot", flaky_record_snapshot)
    await _run_briefly(price_cache, interval=0.01, duration=0.05)

    # The loop kept ticking past the first (failing) call.
    assert calls["n"] >= 2
    assert len(repo.list_snapshots()) >= 1


async def test_stop_snapshot_task_cancels_cleanly(price_cache):
    task = svc.start_snapshot_task(price_cache, interval=5.0)
    await svc.stop_snapshot_task(task)
    # Still sleeping when stopped, so cancellation (not natural completion) is
    # what ended it, and stop_snapshot_task already awaited it without raising.
    assert task.cancelled()
