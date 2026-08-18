"""Pruebas de backpressure para colas realtime."""

from __future__ import annotations

import asyncio
import unittest

from mily_ai.pipeline import TranslationRequest
from mily_ai.queueing import enqueue_translation


def request(kind: str, text: str) -> TranslationRequest:
    return TranslationRequest(
        type=kind,
        start=0.0,
        end=1.0,
        original=text,
        language="en",
    )


class RealtimeQueueingTests(unittest.IsolatedAsyncioTestCase):
    async def test_partial_can_be_dropped_when_queue_is_full(self):
        queue: asyncio.Queue[TranslationRequest] = asyncio.Queue(maxsize=1)
        await queue.put(request("translation.final", "important final"))

        accepted = await enqueue_translation(
            queue, request("translation.partial", "obsolete partial")
        )

        self.assertFalse(accepted)
        self.assertEqual(queue.qsize(), 1)
        self.assertEqual((await queue.get()).original, "important final")

    async def test_final_waits_for_capacity_and_is_never_dropped(self):
        queue: asyncio.Queue[TranslationRequest] = asyncio.Queue(maxsize=1)
        await queue.put(request("translation.partial", "old partial"))

        producer = asyncio.create_task(
            enqueue_translation(queue, request("translation.final", "must survive"))
        )
        await asyncio.sleep(0)
        self.assertFalse(producer.done())

        old = await queue.get()
        queue.task_done()
        self.assertEqual(old.original, "old partial")

        self.assertTrue(await producer)
        final = await queue.get()
        queue.task_done()
        self.assertTrue(final.final)
        self.assertEqual(final.original, "must survive")


if __name__ == "__main__":
    unittest.main()
