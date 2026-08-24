"""Sample-derived realtime timeline with explicit sequence anomaly handling."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class TimelineError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class RealtimeFrame:
    source: str
    epoch: int
    sequence_id: int
    captured_monotonic_ns: int
    media_start_ns: int
    duration_ns: int
    sample_rate: int
    channels: int
    sample_count: int
    sample_format: str
    discontinuity: bool
    gap_before: int
    jitter_ns: int
    payload: Any = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class TimelineSnapshot:
    epoch: int
    expected_sequence_id: int
    media_cursor_ns: int
    accepted_chunks: int
    gap_events: int
    missing_chunks: int
    out_of_order_events: int
    timestamp_regressions: int
    max_jitter_ns: int


class RealtimeTimeline:
    """Map ordered audio chunks onto a deterministic media clock.

    Arrival/capture time is used only to measure jitter and reject monotonic clock
    regressions. Media position advances exclusively from the amount of audio in
    accepted chunks, so processing stalls cannot accumulate playback drift.
    """

    def __init__(self) -> None:
        self._epoch = 0
        self._expected_sequence_id = 0
        self._media_cursor_ns = 0
        self._accepted_chunks = 0
        self._accepted_in_epoch = 0
        self._gap_events = 0
        self._missing_chunks = 0
        self._out_of_order_events = 0
        self._timestamp_regressions = 0
        self._max_jitter_ns = 0
        self._last_capture_ns: int | None = None
        self._last_duration_ns: int | None = None

    def snapshot(self) -> TimelineSnapshot:
        return TimelineSnapshot(
            epoch=self._epoch,
            expected_sequence_id=self._expected_sequence_id,
            media_cursor_ns=self._media_cursor_ns,
            accepted_chunks=self._accepted_chunks,
            gap_events=self._gap_events,
            missing_chunks=self._missing_chunks,
            out_of_order_events=self._out_of_order_events,
            timestamp_regressions=self._timestamp_regressions,
            max_jitter_ns=self._max_jitter_ns,
        )

    @staticmethod
    def _positive_int(value: object) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value > 0

    @staticmethod
    def _non_negative_int(value: object) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0

    def _validate_chunk(self, chunk: object) -> tuple[int, int, int, int, int, str, bool, str, Any]:
        sequence_id = getattr(chunk, "sequence_id", None)
        captured_ns = getattr(chunk, "captured_monotonic_ns", None)
        sample_count = getattr(chunk, "sample_count", None)
        sample_rate = getattr(chunk, "sample_rate", None)
        channels = getattr(chunk, "channels", None)
        sample_format = getattr(chunk, "sample_format", None)
        discontinuity = getattr(chunk, "discontinuity", None)
        source = getattr(chunk, "source", None)
        payload = getattr(chunk, "samples", None)

        valid = (
            self._non_negative_int(sequence_id)
            and self._non_negative_int(captured_ns)
            and self._positive_int(sample_count)
            and self._positive_int(sample_rate)
            and self._positive_int(channels)
            and sample_format == "float32"
            and isinstance(discontinuity, bool)
            and source is not None
            and sample_count % channels == 0
        )
        if not valid:
            raise TimelineError("INVALID_CHUNK", "Metadatos de audio inválidos para Realtime")

        return (
            sequence_id,
            captured_ns,
            sample_count,
            sample_rate,
            channels,
            sample_format,
            discontinuity,
            str(source),
            payload,
        )

    @staticmethod
    def _duration_ns(sample_count: int, sample_rate: int, channels: int) -> int:
        frames = sample_count // channels
        return (frames * 1_000_000_000 + sample_rate // 2) // sample_rate

    def accept(self, chunk: object) -> RealtimeFrame:
        (
            sequence_id,
            captured_ns,
            sample_count,
            sample_rate,
            channels,
            sample_format,
            explicit_discontinuity,
            source,
            payload,
        ) = self._validate_chunk(chunk)

        if explicit_discontinuity and sequence_id != 0:
            raise TimelineError(
                "DISCONTINUITY_SEQUENCE",
                "Una discontinuidad debe reiniciar sequenceId en cero",
            )

        starting_new_epoch = explicit_discontinuity and self._accepted_chunks > 0
        expected_sequence = 0 if starting_new_epoch else self._expected_sequence_id
        accepted_in_epoch = 0 if starting_new_epoch else self._accepted_in_epoch
        previous_capture = None if starting_new_epoch else self._last_capture_ns
        previous_duration = None if starting_new_epoch else self._last_duration_ns
        media_start_ns = 0 if starting_new_epoch else self._media_cursor_ns

        if accepted_in_epoch == 0 and sequence_id != 0:
            raise TimelineError(
                "FIRST_SEQUENCE",
                "El primer chunk de un epoch debe usar sequenceId cero",
            )

        if sequence_id < expected_sequence:
            self._out_of_order_events += 1
            raise TimelineError(
                "SEQUENCE_ORDER",
                "Chunk duplicado o fuera de orden",
            )

        if previous_capture is not None and captured_ns < previous_capture:
            self._timestamp_regressions += 1
            raise TimelineError(
                "TIMESTAMP_REGRESSION",
                "capturedMonotonicNs retrocedió dentro del mismo epoch",
            )

        gap_before = sequence_id - expected_sequence
        duration_ns = self._duration_ns(sample_count, sample_rate, channels)
        jitter_ns = 0
        if gap_before == 0 and previous_capture is not None and previous_duration is not None:
            arrival_delta_ns = captured_ns - previous_capture
            jitter_ns = abs(arrival_delta_ns - previous_duration)

        epoch = self._epoch + 1 if starting_new_epoch else self._epoch
        derived_discontinuity = explicit_discontinuity or gap_before > 0

        frame = RealtimeFrame(
            source=source,
            epoch=epoch,
            sequence_id=sequence_id,
            captured_monotonic_ns=captured_ns,
            media_start_ns=media_start_ns,
            duration_ns=duration_ns,
            sample_rate=sample_rate,
            channels=channels,
            sample_count=sample_count,
            sample_format=sample_format,
            discontinuity=derived_discontinuity,
            gap_before=gap_before,
            jitter_ns=jitter_ns,
            payload=payload,
        )

        # Commit state only after all validation and descriptor construction pass.
        if starting_new_epoch:
            self._epoch = epoch
            self._media_cursor_ns = 0
            self._expected_sequence_id = 0
            self._accepted_in_epoch = 0
            self._last_capture_ns = None
            self._last_duration_ns = None

        if gap_before > 0:
            self._gap_events += 1
            self._missing_chunks += gap_before

        self._media_cursor_ns = media_start_ns + duration_ns
        self._expected_sequence_id = sequence_id + 1
        self._accepted_chunks += 1
        self._accepted_in_epoch += 1
        self._last_capture_ns = captured_ns
        self._last_duration_ns = duration_ns
        self._max_jitter_ns = max(self._max_jitter_ns, jitter_ns)
        return frame
