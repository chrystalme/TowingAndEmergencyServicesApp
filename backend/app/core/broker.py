"""Pub/sub broker: Redis when configured, in-process otherwise.

This exists for fan-out. The live-tracking WebSocket needs an event published
by whichever API instance received a driver's position update to reach clients
connected to a *different* instance. A Python-local registry cannot do that:
with two instances behind a load balancer, a client watching on instance A
never sees an event published on B, and the bug looks like "tracking randomly
doesn't work" rather than anything obviously wrong.

Two implementations behind one interface:

* ``RedisBroker``   — real fan-out across processes and machines.
* ``InProcessBroker`` — correct within a single process. Used by the tests and
  by a local run with no Redis, so neither needs the extra service.

``get_broker()`` picks based on ``REDIS_URL``. The choice is logged at startup
so a deployment that silently fell back is visible rather than mysterious.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import AsyncIterator, Optional, Protocol

import redis.asyncio as aioredis

from .settings import settings

logger = logging.getLogger(__name__)


class Broker(Protocol):
    """The surface anything publishing or watching events depends on."""

    async def publish(self, channel: str, payload: dict) -> None: ...

    def subscribe(self, channel: str) -> AsyncIterator[dict]: ...

    async def ping(self) -> bool: ...

    async def close(self) -> None: ...


class InProcessBroker:
    """Single-process fan-out via per-subscriber queues.

    Deliberately not a fallback that pretends to be Redis: it is correct for
    one process and wrong for two, which is exactly why REDIS_URL matters in
    any environment that can scale beyond a single instance.
    """

    name = "in-process"

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)

    async def publish(self, channel: str, payload: dict) -> None:
        # Snapshot the set: a slow consumer unsubscribing mid-publish must not
        # mutate what we are iterating.
        for queue in list(self._subscribers.get(channel, ())):
            queue.put_nowait(payload)

    async def subscribe(self, channel: str) -> AsyncIterator[dict]:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[channel].add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers[channel].discard(queue)
            if not self._subscribers[channel]:
                self._subscribers.pop(channel, None)

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        self._subscribers.clear()

    @property
    def subscriber_count(self) -> int:
        return sum(len(q) for q in self._subscribers.values())


class RedisBroker:
    """Cross-instance fan-out over Redis pub/sub."""

    name = "redis"

    def __init__(self, url: str) -> None:
        self._url = url
        self._client = aioredis.from_url(url, decode_responses=True)

    async def publish(self, channel: str, payload: dict) -> None:
        await self._client.publish(channel, json.dumps(payload))

    async def subscribe(self, channel: str) -> AsyncIterator[dict]:
        pubsub = self._client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue  # subscribe/unsubscribe acks
                try:
                    yield json.loads(message["data"])
                except (TypeError, ValueError):
                    # Never let one malformed publisher kill a subscriber.
                    logger.warning("broker: dropping unparseable message on %s", channel)
        finally:
            try:
                await pubsub.unsubscribe(channel)
            finally:
                await pubsub.aclose()

    async def ping(self) -> bool:
        return bool(await self._client.ping())

    async def close(self) -> None:
        await self._client.aclose()


_broker: Optional[Broker] = None


def get_broker() -> Broker:
    """The process-wide broker, built on first use."""
    global _broker
    if _broker is None:
        url = settings.REDIS_URL.strip()
        if url:
            _broker = RedisBroker(url)
            logger.info("broker: using Redis fan-out")
        else:
            _broker = InProcessBroker()
            if settings.is_deployed:
                # Not fatal — refusing to serve because pub/sub is unconfigured
                # would be a worse outage than degraded tracking — but this must
                # be loud, because the symptom otherwise is intermittent.
                logger.warning(
                    "broker: REDIS_URL is not set in a deployed environment. "
                    "Falling back to in-process fan-out, which does NOT work "
                    "across multiple instances."
                )
            else:
                logger.info("broker: using in-process fan-out (no REDIS_URL)")
    return _broker


async def reset_broker() -> None:
    """Drop the cached broker. For tests and shutdown."""
    global _broker
    if _broker is not None:
        await _broker.close()
    _broker = None
