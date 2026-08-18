"""Agrupación acústica local y ligera de hablantes para una sesión.

No intenta identificar personas ni inferir género/edad. Produce etiquetas efímeras
speaker-a/speaker-b/... comparando firmas espectrales normalizadas dentro de la
misma sesión. El objetivo es continuidad visual/TTS, no biometría.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(slots=True)
class _Cluster:
    speaker_id: str
    centroid: np.ndarray
    final_count: int = 0


class SpeakerClusterer:
    """Clustering online por similitud coseno de una firma acústica barata."""

    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        similarity_threshold: float = 0.88,
        max_speakers: int = 8,
    ) -> None:
        if sample_rate <= 0:
            raise ValueError("sample_rate debe ser positivo")
        if not 0.0 < similarity_threshold < 1.0:
            raise ValueError("similarity_threshold fuera de rango")
        if not 1 <= max_speakers <= 26:
            raise ValueError("max_speakers fuera de rango")
        self.sample_rate = sample_rate
        self.similarity_threshold = similarity_threshold
        self.max_speakers = max_speakers
        self._clusters: list[_Cluster] = []

    @property
    def speaker_ids(self) -> tuple[str, ...]:
        return tuple(cluster.speaker_id for cluster in self._clusters)

    @property
    def dominant_id(self) -> str | None:
        if not self._clusters:
            return None
        return max(
            self._clusters,
            key=lambda cluster: (cluster.final_count, -self._clusters.index(cluster)),
        ).speaker_id

    def _embedding(self, samples: Sequence[float]) -> np.ndarray:
        audio = np.asarray(samples, dtype=np.float32)
        if audio.size < 64:
            padded = np.zeros(64, dtype=np.float32)
            padded[: audio.size] = audio
            audio = padded
        if audio.size > self.sample_rate * 4:
            audio = audio[-self.sample_rate * 4 :]

        audio = audio - float(np.mean(audio))
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if peak > 1e-7:
            audio = audio / peak

        window = np.hanning(audio.size).astype(np.float32)
        spectrum = np.abs(np.fft.rfft(audio * window)).astype(np.float64) ** 2
        frequencies = np.fft.rfftfreq(audio.size, d=1.0 / self.sample_rate)
        total_power = float(np.sum(spectrum)) + 1e-12

        edges = np.geomspace(80.0, min(4000.0, self.sample_rate / 2 - 1), 11)
        bands: list[float] = []
        for low, high in zip(edges[:-1], edges[1:]):
            mask = (frequencies >= low) & (frequencies < high)
            band_power = float(np.sum(spectrum[mask])) / total_power if np.any(mask) else 0.0
            bands.append(np.log1p(band_power * 1000.0))

        weighted_frequency = float(np.sum(frequencies * spectrum) / total_power)
        spectral_centroid = weighted_frequency / max(1.0, self.sample_rate / 2)
        sign_changes = np.count_nonzero(np.diff(np.signbit(audio)))
        zcr = float(sign_changes) / max(1, audio.size - 1)
        nonzero = spectrum[spectrum > 1e-12]
        if nonzero.size:
            flatness = float(np.exp(np.mean(np.log(nonzero))) / (np.mean(nonzero) + 1e-12))
        else:
            flatness = 0.0

        vector = np.asarray([*bands, spectral_centroid, zcr, flatness], dtype=np.float64)
        norm = float(np.linalg.norm(vector))
        if norm <= 1e-12:
            vector[0] = 1.0
            norm = 1.0
        return vector / norm

    @staticmethod
    def _similarity(left: np.ndarray, right: np.ndarray) -> float:
        return float(np.clip(np.dot(left, right), -1.0, 1.0))

    def _new_cluster(self, embedding: np.ndarray, *, final: bool) -> _Cluster:
        index = len(self._clusters)
        speaker_id = f"speaker-{chr(ord('a') + index)}"
        cluster = _Cluster(
            speaker_id=speaker_id,
            centroid=embedding.copy(),
            final_count=1 if final else 0,
        )
        self._clusters.append(cluster)
        return cluster

    def assign(self, samples: Sequence[float], *, update: bool) -> str:
        """Asigna una etiqueta efímera; `update=True` confirma una frase final."""

        embedding = self._embedding(samples)
        if not self._clusters:
            return self._new_cluster(embedding, final=update).speaker_id

        similarities = [
            self._similarity(embedding, cluster.centroid) for cluster in self._clusters
        ]
        best_index = int(np.argmax(similarities))
        best_similarity = similarities[best_index]

        if (
            best_similarity < self.similarity_threshold
            and len(self._clusters) < self.max_speakers
        ):
            return self._new_cluster(embedding, final=update).speaker_id

        cluster = self._clusters[best_index]
        if update:
            blended = cluster.centroid * 0.82 + embedding * 0.18
            norm = float(np.linalg.norm(blended))
            if norm > 1e-12:
                cluster.centroid = blended / norm
            cluster.final_count += 1
        return cluster.speaker_id
