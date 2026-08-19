"""Backpressure y coalescencia para traducción en tiempo real."""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict, deque
from typing import Callable, Literal

from .pipeline import TranslationRequest

SerialTranslationAction = Literal["run", "defer", "drop"]


def serial_translation_action(
    request: TranslationRequest, *, audio_pending: bool
) -> SerialTranslationAction:
    if not audio_pending:
        return "run"
    return "defer" if request.final else "drop"


class CoalescingTranslationQueue:
    """Conserva finales y mantiene como máximo un parcial por utterance."""

    def __init__(
        self,
        maxsize: int = 8,
        *,
        partial_ttl_seconds: float = 0.75,
        clock: Callable[[], float] = time.monotonic,
    ):
        if maxsize <= 0:
            raise ValueError("maxsize debe ser positivo")
        if partial_ttl_seconds <= 0:
            raise ValueError("partial_ttl_seconds debe ser positivo")
        self.maxsize = int(maxsize)
        self.partial_ttl_seconds = float(partial_ttl_seconds)
        self._clock = clock
        self._finals: deque[TranslationRequest] = deque()
        self._partials: OrderedDict[str, TranslationRequest] = OrderedDict()
        self._condition = asyncio.Condition()
        self._unfinished_tasks = 0
        self._finished = asyncio.Event()
        self._finished.set()
        self._closed = False

    @staticmethod
    def _key(request: TranslationRequest) -> str:
        return request.utterance_id or f"{request.start:.3f}:{request.language}"

    def _mark_removed(self, count: int = 1) -> None:
        self._unfinished_tasks = max(0, self._unfinished_tasks - count)
        if self._unfinished_tasks == 0:
            self._finished.set()

    def _purge_stale_locked(self) -> None:
        now = self._clock()
        stale = [
            key
            for key, item in self._partials.items()
            if item.created_at > 0
            and now - item.created_at > self.partial_ttl_seconds
        ]
        for key in stale:
            self._partials.pop(key, None)
            self._mark_removed()

    def qsize(self) -> int:
        return len(self._finals) + len(self._partials)

    def empty(self) -> bool:
        return self.qsize() == 0

    def full(self) -> bool:
        return self.qsize() >= self.maxsize

    def oldest_age_seconds(self) -> float:
        items = list(self._finals) + list(self._partials.values())
        created = [item.created_at for item in items if item.created_at > 0]
        return max(0.0, self._clock() - min(created)) if created else 0.0

    async def put(self, request: TranslationRequest) -> bool:
        if not isinstance(request, TranslationRequest):
            raise TypeError("La cola solo acepta TranslationRequest")
        async with self._condition:
            if self._closed:
                return False
            self._purge_stale_locked()
            key = self._key(request)
            if request.final:
                if self._partials.pop(key, None) is not None:
                    self._mark_removed()
                while self.full() and self._partials:
                    self._partials.popitem(last=False)
                    self._mark_removed()
                while self.full() and not self._closed:
                    await self._condition.wait()
                    self._purge_stale_locked()
                if self._closed:
                    return False
                self._finals.append(request)
                self._unfinished_tasks += 1
                self._finished.clear()
                self._condition.notify_all()
                return True
            if key in self._partials:
                self._partials[key] = request
                self._partials.move_to_end(key)
                self._condition.notify_all()
                return True
            if self.full():
                if self._partials:
                    self._partials.popitem(last=False)
                    self._mark_removed()
                else:
                    return False
            self._partials[key] = request
            self._unfinished_tasks += 1
            self._finished.clear()
            self._condition.notify_all()
            return True

    async def get(self) -> TranslationRequest | None:
        async with self._condition:
            while True:
                self._purge_stale_locked()
                if self._finals:
                    item = self._finals.popleft()
                    self._condition.notify_all()
                    return item
                if self._partials:
                    _key, item = self._partials.popitem(last=False)
                    self._condition.notify_all()
                    return item
                if self._closed:
                    return None
                await self._condition.wait()

    def task_done(self) -> None:
        if self._unfinished_tasks <= 0:
            raise ValueError("task_done() llamado demasiadas veces")
        self._mark_removed()

    async def join(self) -> None:
        await self._finished.wait()

    async def close(self) -> None:
        async with self._condition:
            self._closed = True
            self._condition.notify_all()


async def enqueue_translation(
    queue: asyncio.Queue[TranslationRequest] | CoalescingTranslationQueue,
    request: TranslationRequest,
) -> bool:
    if isinstance(queue, CoalescingTranslationQueue):
        return await queue.put(request)
    if request.final:
        await queue.put(request)
        return True
    try:
        queue.put_nowait(request)
        return True
    except asyncio.QueueFull:
        return False
