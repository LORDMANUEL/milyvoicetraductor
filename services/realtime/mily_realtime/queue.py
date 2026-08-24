"""Bounded FIFO buffering for realtime frames with explicit backpressure."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class BackpressurePolicy(StrEnum):
    REJECT_NEW = "rejectNew"
    DROP_OLDEST = "dropOldest"


@dataclass(frozen=True, slots=True)
class QueueOfferResult:
    accepted: bool
    rejected_new: bool
    dropped_sequence_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class QueueSnapshot:
    depth: int
    buffered_duration_ns: int
    max_chunks: int
    max_buffered_duration_ns: int
    policy: BackpressurePolicy
    dropped_oldest: int
    rejected_new: int


class BoundedRealtimeQueue:
    """FIFO queue bounded by both item count and media duration."""

    def __init__(
        self,
        *,
        max_chunks: int,
        max_buffered_duration_ns: int,
        policy: BackpressurePolicy = BackpressurePolicy.REJECT_NEW,
    ) -> None:
        if (
            not isinstance(max_chunks, int)
            or isinstance(max_chunks, bool)
            or max_chunks <= 0
        ):
            raise ValueError("max_chunks debe ser un entero positivo")
        if (
            not isinstance(max_buffered_duration_ns, int)
            or isinstance(max_buffered_duration_ns, bool)
            or max_buffered_duration_ns <= 0
        ):
            raise ValueError("max_buffered_duration_ns debe ser un entero positivo")
        if not isinstance(policy, BackpressurePolicy):
            try:
                policy = BackpressurePolicy(policy)
            except (TypeError, ValueError) as exc:
                raise ValueError("política de backpressure inválida") from exc

        self.max_chunks = max_chunks
        self.max_buffered_duration_ns = max_buffered_duration_ns
        self.policy = policy
        self._items: deque[Any] = deque()
        self._buffered_duration_ns = 0
        self._dropped_oldest = 0
        self._rejected_new = 0

    def __len__(self) -> int:
        return len(self._items)

    @staticmethod
    def _frame_duration(frame: object) -> int:
        duration = getattr(frame, "duration_ns", None)
        if (
            not isinstance(duration, int)
            or isinstance(duration, bool)
            or duration <= 0
        ):
            raise ValueError("frame.duration_ns debe ser un entero positivo")
        return duration

    @staticmethod
    def _sequence_id(frame: object) -> int:
        sequence_id = getattr(frame, "sequence_id", -1)
        return sequence_id if isinstance(sequence_id, int) else -1

    def snapshot(self) -> QueueSnapshot:
        return QueueSnapshot(
            depth=len(self._items),
            buffered_duration_ns=self._buffered_duration_ns,
            max_chunks=self.max_chunks,
            max_buffered_duration_ns=self.max_buffered_duration_ns,
            policy=self.policy,
            dropped_oldest=self._dropped_oldest,
            rejected_new=self._rejected_new,
        )

    def _would_overflow(self, duration_ns: int) -> bool:
        return (
            len(self._items) >= self.max_chunks
            or self._buffered_duration_ns + duration_ns
            > self.max_buffered_duration_ns
        )

    def offer(self, frame: object) -> QueueOfferResult:
        duration_ns = self._frame_duration(frame)
        if duration_ns > self.max_buffered_duration_ns:
            self._rejected_new += 1
            return QueueOfferResult(False, True, ())

        if self.policy is BackpressurePolicy.REJECT_NEW and self._would_overflow(
            duration_ns
        ):
            self._rejected_new += 1
            return QueueOfferResult(False, True, ())

        dropped: list[int] = []
        if self.policy is BackpressurePolicy.DROP_OLDEST:
            while self._items and self._would_overflow(duration_ns):
                removed = self._items.popleft()
                removed_duration = self._frame_duration(removed)
                self._buffered_duration_ns -= removed_duration
                dropped.append(self._sequence_id(removed))
                self._dropped_oldest += 1

        # The single-frame-too-large case was rejected above, so an empty queue
        # must be able to fit the new frame after the minimum required evictions.
        if self._would_overflow(duration_ns):
            self._rejected_new += 1
            return QueueOfferResult(False, True, tuple(dropped))

        self._items.append(frame)
        self._buffered_duration_ns += duration_ns
        return QueueOfferResult(True, False, tuple(dropped))

    def pop(self):
        if not self._items:
            return None
        frame = self._items.popleft()
        self._buffered_duration_ns -= self._frame_duration(frame)
        return frame
