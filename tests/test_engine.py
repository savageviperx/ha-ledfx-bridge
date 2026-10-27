"""Exercise timing, real UDP, overload, filtering and lifecycle behavior."""

import asyncio
import socket
import struct

import pytest

from custom_components.ledfx_bridge.engine import (
    BridgeEngine,
    Settings,
    changed,
    light_command,
    parse_ddp,
)


def packet(rgb, flags=0x41):
    return (
        struct.pack("!BBBBIH", flags, 1, 0x0B, 1, 0, 3)
        + (b"\0" * 4 if flags & 0x10 else b"")
        + bytes(rgb)
    )


@pytest.mark.parametrize("flags", [0x40, 0x41, 0x51])
def test_ddp(flags):
    assert parse_ddp(packet((12, 34, 56), flags)) == (12, 34, 56)


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"\0" * 9,
        packet((1, 2, 3))[:-1],
        packet((1, 2, 3)) + b"x",
        packet((1, 2, 3), 0x81),
        packet((1, 2, 3), 0x43),
        struct.pack("!BBBBIH", 0x41, 0, 0x0B, 1, 3, 3) + b"rgb",
    ],
)
def test_ddp_rejects_invalid(raw):
    assert parse_ddp(raw) is None


def test_color_and_threshold():
    assert light_command((80, 40, 0)) == ("turn_on", {"rgb_color": [255, 128, 0], "brightness": 80})
    assert light_command((0, 0, 0)) == ("turn_off", {})
    assert changed((1, 0, 0), (0, 0, 0), 255)
    assert not changed((40, 0, 0), (41, 0, 0), 2)


@pytest.mark.asyncio
async def test_twenty_starts_per_second_with_160ms_actions():
    starts, pending, peak = [], 0, 0

    async def send(rgb):
        nonlocal pending, peak
        starts.append(asyncio.get_running_loop().time())
        pending += 1
        peak = max(peak, pending)
        try:
            await asyncio.sleep(0.160)
        finally:
            pending -= 1

    engines = [BridgeEngine(Settings(port=0), send) for _ in range(2)]
    try:
        for engine in engines:
            await engine.start("127.0.0.1")
        started = asyncio.get_running_loop().time()
        n = 0
        while asyncio.get_running_loop().time() - started < 1.2:
            for engine in engines:
                engine.receive(packet((n % 255 + 1, 50, 0)), "127.0.0.1")
                assert len(engine._pending) <= 4
            n += 1
            await asyncio.sleep(0.008)
        for engine in engines:
            assert 21 <= engine.sent <= 25
            gaps = [b - a for a, b in zip(engine._starts, list(engine._starts)[1:])]
            assert min(gaps) >= 0.049
        assert peak <= 8
    finally:
        for engine in engines:
            await engine.stop()
    assert pending == 0


@pytest.mark.asyncio
async def test_overload_sends_latest_frame_only_and_stop_releases_port():
    gate = asyncio.Event()
    colors = []

    async def send(rgb):
        colors.append(rgb)
        await gate.wait()

    engine = BridgeEngine(Settings(port=0, max_inflight=1, max_fps=60), send)
    await engine.start("127.0.0.1")
    port = engine.transport.get_extra_info("sockname")[1]
    try:
        engine.receive(packet((1, 0, 0)), "127.0.0.1")
        await asyncio.sleep(0.025)
        for n in range(2, 200):
            engine.receive(packet((n, 0, 0)), "127.0.0.1")
        await asyncio.sleep(0.03)
        assert colors == [(1, 0, 0)]
        gate.set()
        await asyncio.sleep(0.04)
        assert colors == [(1, 0, 0), (199, 0, 0)]
    finally:
        await engine.stop()
    engine.receive(packet((250, 0, 0)), "127.0.0.1")
    await asyncio.sleep(0.02)
    assert len(colors) == 2
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", port))


@pytest.mark.asyncio
async def test_real_udp_filter_pause_deduplication_and_stale():
    colors = []

    async def send(rgb):
        colors.append(rgb)

    engine = BridgeEngine(Settings(port=0, source_ip="127.0.0.1", stale_after=0.08), send)
    await engine.start("127.0.0.1")
    try:
        port = engine.transport.get_extra_info("sockname")[1]
        engine.receive(packet((200, 0, 0)), "192.0.2.10")
        assert engine.filtered == 1
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(packet((40, 50, 60)), ("127.0.0.1", port))
            await asyncio.sleep(0.02)
            sock.sendto(packet((40, 50, 60)), ("127.0.0.1", port))
        await asyncio.sleep(0.06)
        assert colors == [(40, 50, 60)]
        engine.set_enabled(False)
        engine.receive(packet((60, 0, 0)), "127.0.0.1")
        await asyncio.sleep(0.03)
        assert len(colors) == 1
        engine.set_enabled(True)
        await asyncio.sleep(0.03)
        assert len(colors) == 1  # Do not replay a color from before resume.
        engine.receive(packet((70, 0, 0)), "127.0.0.1")
        await asyncio.sleep(0.03)
        assert colors[-1] == (70, 0, 0)
        await asyncio.sleep(0.09)
        assert not engine.receiving
        assert engine.status == "waiting"
    finally:
        await engine.stop()


@pytest.mark.asyncio
async def test_action_failure_backs_off_without_queue_growth():
    async def send(rgb):
        raise RuntimeError("test failure")

    engine = BridgeEngine(Settings(port=0), send)
    await engine.start("127.0.0.1")
    try:
        engine.receive(packet((200, 0, 0)), "127.0.0.1")
        await asyncio.sleep(0.04)
        for n in range(200):
            engine.receive(packet((n, 0, 0)), "127.0.0.1")
        await asyncio.sleep(0.1)
        assert engine.sent == engine.errors == 1
        assert engine.status == "backoff"
        assert not engine._pending
    finally:
        await engine.stop()
