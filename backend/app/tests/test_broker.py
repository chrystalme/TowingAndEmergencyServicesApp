"""Tests for the pub/sub broker.

These exercise the in-process implementation, which is what the test suite and
a local run without Redis use. The Redis implementation is covered by the live
stack (`GET /api/broker-ping` reports which backend is active) rather than by
mocking redis-py here — a mock would only assert that we call the library the
way we think we do.
"""

import asyncio

import pytest

from app.core.broker import InProcessBroker, get_broker, reset_broker
from app.core.settings import settings


async def _collect(broker, channel, count, timeout=2.0):
    """Subscribe and gather `count` messages, failing rather than hanging."""
    received = []
    agen = broker.subscribe(channel)

    async def pump():
        async for message in agen:
            received.append(message)
            if len(received) >= count:
                return

    task = asyncio.create_task(pump())
    await asyncio.sleep(0)  # let the subscription register before publishing
    return received, task, agen


@pytest.mark.asyncio
async def test_subscriber_receives_published_messages():
    broker = InProcessBroker()
    received, task, agen = await _collect(broker, "request:1", 2)

    await broker.publish("request:1", {"lat": 6.5, "lng": 3.3})
    await broker.publish("request:1", {"lat": 6.6, "lng": 3.4})

    await asyncio.wait_for(task, timeout=2.0)
    await agen.aclose()

    assert received == [{"lat": 6.5, "lng": 3.3}, {"lat": 6.6, "lng": 3.4}]


@pytest.mark.asyncio
async def test_channels_are_isolated():
    """A watcher on one request must not see another request's driver."""
    broker = InProcessBroker()
    received, task, agen = await _collect(broker, "request:1", 1)

    await broker.publish("request:2", {"lat": 0.0, "lng": 0.0})  # different channel
    await broker.publish("request:1", {"lat": 6.5, "lng": 3.3})

    await asyncio.wait_for(task, timeout=2.0)
    await agen.aclose()

    assert received == [{"lat": 6.5, "lng": 3.3}]


@pytest.mark.asyncio
async def test_every_subscriber_gets_a_copy():
    """Fan-out, not a work queue: two watchers both see the same update."""
    broker = InProcessBroker()
    first, task_a, agen_a = await _collect(broker, "request:7", 1)
    second, task_b, agen_b = await _collect(broker, "request:7", 1)

    await broker.publish("request:7", {"lat": 1.0, "lng": 2.0})

    await asyncio.wait_for(asyncio.gather(task_a, task_b), timeout=2.0)
    await agen_a.aclose()
    await agen_b.aclose()

    assert first == second == [{"lat": 1.0, "lng": 2.0}]


@pytest.mark.asyncio
async def test_publishing_with_no_subscribers_is_a_noop():
    broker = InProcessBroker()
    await broker.publish("nobody-listening", {"x": 1})  # must not raise


@pytest.mark.asyncio
async def test_unsubscribing_cleans_up():
    """A closed subscription must not leak its queue."""
    broker = InProcessBroker()
    _, task, agen = await _collect(broker, "request:9", 1)
    await broker.publish("request:9", {"done": True})
    await asyncio.wait_for(task, timeout=2.0)
    await agen.aclose()

    assert broker.subscriber_count == 0


@pytest.mark.asyncio
async def test_falls_back_to_in_process_without_redis_url():
    """No REDIS_URL means in-process fan-out rather than a hard failure."""
    await reset_broker()
    original = settings.REDIS_URL
    settings.REDIS_URL = ""
    try:
        broker = get_broker()
        assert isinstance(broker, InProcessBroker)
        assert broker.name == "in-process"
        assert await broker.ping() is True
    finally:
        settings.REDIS_URL = original
        await reset_broker()
