"""Async DDP receiver with bounded, latest-frame-only action dispatch.

No Home Assistant imports: the scheduler can be exercised independently.
All methods run on the same event loop; no threads or unbounded queues.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import struct
from collections import deque
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import Any

_LOGGER = logging.getLogger(__name__)
RGB = tuple[int, int, int]


def parse_ddp(packet: bytes) -> RGB | None:
    """Accept one RGB888 pixel at offset 0, destination 1, DDP version 1."""
    if len(packet) < 10:
        return None
    flags, _, kind, destination, offset, size = struct.unpack("!BBBBIH", packet[:10])
    if (
        flags & 0xC0 != 0x40
        or flags & 0x0E
        or kind != 0x0B
        or destination != 1
        or offset != 0
        or size != 3
    ):
        return None
    start = 14 if flags & 0x10 else 10
    if len(packet) != start + 3:
        return None
    return packet[start], packet[start + 1], packet[start + 2]


def light_command(rgb: RGB) -> tuple[str, dict[str, Any]]:
    """Separate hue from intensity so dim colors are not sent at full power."""
    peak = max(rgb)
    if peak == 0:
        return "turn_off", {}
    return "turn_on", {
        "rgb_color": [round(channel * 255 / peak) for channel in rgb],
        "brightness": peak,
    }


def changed(previous: RGB | None, rgb: RGB, threshold: int) -> bool:
    """Always preserve on/off changes, even with a noise threshold."""
    return (
        previous is None
        or (max(previous) == 0) != (max(rgb) == 0)
        or max(abs(a - b) for a, b in zip(previous, rgb)) >= threshold
    )


@dataclass(frozen=True)
class Settings:
    """One DDP port maps to one Home Assistant light."""

    port: int
    source_ip: str = ""
    max_fps: int = 20
    max_inflight: int = 4
    threshold: int = 1
    stale_after: float = 5.0


class _Protocol(asyncio.DatagramProtocol):
    def __init__(self, engine: BridgeEngine) -> None:
        self.engine = engine

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.engine.receive(data, addr[0])

    def error_received(self, exc: Exception) -> None:
        _LOGGER.debug("DDP socket error: %s", type(exc).__name__)


class BridgeEngine:
    """Replace old frames, rate-limit starts, and cap active action calls."""

    def __init__(
        self,
        settings: Settings,
        send: Callable[[RGB], Awaitable[None]],
        *,
        ready: Callable[[], bool] = lambda: True,
        create_task: Callable[[Coroutine[Any, Any, Any], str], asyncio.Task] | None = None,
        enabled: bool = True,
    ) -> None:
        if not (
            1 <= settings.max_fps <= 60
            and 1 <= settings.max_inflight <= 8
            and 1 <= settings.threshold <= 255
            and 0 <= settings.port <= 65535
        ):
            raise ValueError("Invalid bridge settings")
        self.settings, self._send, self._ready = settings, send, ready
        self._create_task = create_task or (lambda coro, name: asyncio.create_task(coro, name=name))
        self.enabled = enabled
        self.running = False
        self.transport: asyncio.DatagramTransport | None = None
        self._worker: asyncio.Task | None = None
        self._pending: set[asyncio.Task] = set()
        self._wake = asyncio.Event()
        self._latest: RGB | None = None
        self._last_sent: RGB | None = None
        self._received_at: float | None = None
        self._next_dispatch = 0.0
        self._retry_at = 0.0
        self._failures = 0
        self._starts: deque[float] = deque(maxlen=240)
        self.received = self.rejected = self.filtered = 0
        self.sent = self.completed = self.errors = 0
        self.latency_ms: float | None = None
        self.last_error: str | None = None

    async def start(self, bind_ip: str = "0.0.0.0") -> None:
        """Bind exactly once; port 0 is reserved for isolated tests."""
        if self.running:
            return
        loop = asyncio.get_running_loop()
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: _Protocol(self),
            local_addr=(bind_ip, self.settings.port),
            family=socket.AF_INET,
        )
        self.running = True
        self._worker = self._create_task(self._run(), "LedFx DDP scheduler")

    def receive(self, packet: bytes, source_ip: str) -> None:
        """Called by the UDP protocol; memory use is constant per device."""
        if not self.running:
            return
        if self.settings.source_ip and source_ip != self.settings.source_ip:
            self.filtered += 1
            return
        rgb = parse_ddp(packet)
        if rgb is None:
            self.rejected += 1
            return
        self.received += 1
        self._latest = rgb
        self._received_at = asyncio.get_running_loop().time()
        _LOGGER.debug("UDP %s received RGB %s", self.settings.port, rgb)
        self._wake.set()

    def set_enabled(self, enabled: bool) -> None:
        """Resume only on a new frame; already started actions may finish."""
        self.enabled = enabled
        self._latest = self._last_sent = None
        self._wake.set()

    @property
    def receiving(self) -> bool:
        return (
            self.running
            and self._received_at is not None
            and asyncio.get_running_loop().time() - self._received_at <= self.settings.stale_after
        )

    @property
    def status(self) -> str:
        if not self.running or not self.enabled:
            return "disabled"
        if not self._ready():
            return "target_unavailable"
        if asyncio.get_running_loop().time() < self._retry_at:
            return "backoff"
        return "streaming" if self.receiving else "waiting"

    def snapshot(self) -> dict[str, Any]:
        """Diagnostics sampled at 1 Hz, independently of music frames."""
        now = asyncio.get_running_loop().time()
        return {
            "status": self.status,
            "enabled": self.enabled,
            "receiving": self.receiving,
            "send_rate": round(sum(now - t <= 2 for t in self._starts) / 2, 1),
            "latency_ms": None if self.latency_ms is None else round(self.latency_ms, 1),
            "received": self.received,
            "rejected": self.rejected,
            "filtered": self.filtered,
            "sent": self.sent,
            "completed": self.completed,
            "errors": self.errors,
            "inflight": len(self._pending),
            "last_error": self.last_error,
        }

    async def _dispatch(self, rgb: RGB) -> None:
        started = asyncio.get_running_loop().time()
        try:
            await self._send(rgb)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.errors += 1
            self._failures += 1
            delay = min(60, 2 ** min(self._failures, 6))
            self._retry_at = max(self._retry_at, asyncio.get_running_loop().time() + delay)
            self._last_sent = None
            if self.last_error is None:
                _LOGGER.warning(
                    "UDP %s light action failed (%s); backing off",
                    self.settings.port,
                    type(exc).__name__,
                )
            self.last_error = type(exc).__name__
        else:
            self.completed += 1
            self.latency_ms = (asyncio.get_running_loop().time() - started) * 1000
            if asyncio.get_running_loop().time() >= self._retry_at:
                if self.last_error is not None:
                    _LOGGER.info("UDP %s light actions recovered", self.settings.port)
                self._failures = 0
                self.last_error = None
            _LOGGER.debug(
                "UDP %s applied RGB %s (%.1f ms)", self.settings.port, rgb, self.latency_ms
            )

    def _done(self, task: asyncio.Task) -> None:
        self._pending.discard(task)
        self._wake.set()

    async def _run(self) -> None:
        while self.running:
            self._wake.clear()
            now = asyncio.get_running_loop().time()
            rgb = self._latest
            if not self.receiving:
                self._last_sent = None
            if (
                self.enabled
                and self._ready()
                and self.receiving
                and rgb is not None
                and now >= max(self._next_dispatch, self._retry_at)
                and len(self._pending) < self.settings.max_inflight
                and changed(self._last_sent, rgb, self.settings.threshold)
            ):
                self._last_sent = rgb
                self._next_dispatch = now + 1 / self.settings.max_fps
                self._starts.append(now)
                self.sent += 1
                task = self._create_task(self._dispatch(rgb), "LedFx light action")
                self._pending.add(task)
                task.add_done_callback(self._done)
                continue
            deadline = max(self._next_dispatch, self._retry_at)
            delay = min(0.25, deadline - now) if deadline > now else 0.25
            try:
                await asyncio.wait_for(self._wake.wait(), delay)
            except TimeoutError:
                pass

    async def stop(self) -> None:
        """Release UDP and cancel every task owned by this engine."""
        self.running = False
        self._wake.set()
        if self.transport is not None:
            self.transport.close()
            self.transport = None
        tasks = [*self._pending]
        if self._worker is not None:
            tasks.append(self._worker)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._pending.clear()
        self._worker = None
        await asyncio.sleep(0)  # Let the datagram transport close its socket.
