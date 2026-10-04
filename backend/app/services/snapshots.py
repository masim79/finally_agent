"""Background task recording a portfolio_snapshots row every 30 seconds.

CONTRACTS.md §7 starts this during lifespan startup and cancels it on
shutdown. A single bad tick (a transient DB error, a locked file, whatever)
must never kill the loop — it is logged and the loop keeps running on the
next interval. Only cancellation is allowed to stop it.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from app.db import repositories as repo
from app.market.cache import PriceCache
from app.services.portfolio import compute_total_value

logger = logging.getLogger(__name__)

SNAPSHOT_INTERVAL_SECONDS = 30.0


async def run_snapshot_loop(cache: PriceCache, interval: float = SNAPSHOT_INTERVAL_SECONDS) -> None:
    """Record a snapshot every `interval` seconds until cancelled.

    Sleeps first so startup doesn't immediately duplicate a trade-triggered
    snapshot. Runs until the enclosing task is cancelled.
    """
    while True:
        await asyncio.sleep(interval)
        try:
            total_value = compute_total_value(cache)
            repo.record_snapshot(round(total_value, 2))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Portfolio snapshot tick failed; will retry next interval.")


def start_snapshot_task(cache: PriceCache, interval: float = SNAPSHOT_INTERVAL_SECONDS) -> asyncio.Task:
    """Launch the snapshot loop as a background asyncio task."""
    return asyncio.create_task(run_snapshot_loop(cache, interval=interval))


async def stop_snapshot_task(task: asyncio.Task) -> None:
    """Cancel the snapshot task and wait for it to finish cleanly."""
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
