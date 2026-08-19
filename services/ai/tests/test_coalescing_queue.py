import unittest

from mily_ai.pipeline import TranslationRequest
from mily_ai.queueing import CoalescingTranslationQueue


def request(
    utterance_id: str,
    text: str,
    *,
    final: bool = False,
    created_at: float = 0.0,
) -> TranslationRequest:
    return TranslationRequest(
        type="translation.final" if final else "translation.partial",
        start=0.0,
        end=1.0,
        original=text,
        language="en",
        utterance_id=utterance_id,
        created_at=created_at,
    )


class CoalescingTranslationQueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_partial_replaces_old_partial_for_same_utterance(self):
        queue = CoalescingTranslationQueue(maxsize=8, clock=lambda: 1.0)
        self.assertTrue(await queue.put(request("u1", "hello", created_at=0.90)))
        self.assertTrue(
            await queue.put(request("u1", "hello world", created_at=0.95))
        )
        self.assertEqual(queue.qsize(), 1)
        item = await queue.get()
        self.assertIsNotNone(item)
        self.assertEqual(item.original, "hello world")

    async def test_final_removes_partial_and_has_priority(self):
        queue = CoalescingTranslationQueue(maxsize=8, clock=lambda: 1.0)
        await queue.put(request("u1", "partial one", created_at=0.85))
        await queue.put(request("u2", "partial two", created_at=0.90))
        await queue.put(
            request("u1", "final one", final=True, created_at=0.95)
        )
        self.assertEqual(queue.qsize(), 2)
        first = await queue.get()
        self.assertIsNotNone(first)
        self.assertTrue(first.final)
        self.assertEqual(first.original, "final one")

    async def test_stale_partial_is_evicted_before_enqueue(self):
        now = [2.0]
        queue = CoalescingTranslationQueue(
            maxsize=8,
            partial_ttl_seconds=0.5,
            clock=lambda: now[0],
        )
        await queue.put(request("old", "obsolete", created_at=1.0))
        await queue.put(request("new", "fresh", created_at=1.9))
        self.assertEqual(queue.qsize(), 1)
        item = await queue.get()
        self.assertIsNotNone(item)
        self.assertEqual(item.original, "fresh")

    async def test_full_queue_never_drops_final(self):
        queue = CoalescingTranslationQueue(maxsize=1, clock=lambda: 1.0)
        await queue.put(request("u1", "partial", created_at=0.9))
        self.assertTrue(
            await queue.put(
                request("u2", "important", final=True, created_at=1.0)
            )
        )
        item = await queue.get()
        self.assertIsNotNone(item)
        self.assertEqual(item.original, "important")

    async def test_rescue_drop_partials_preserves_every_final(self):
        queue = CoalescingTranslationQueue(maxsize=8, clock=lambda: 1.0)
        await queue.put(request("u1", "partial one", created_at=0.80))
        await queue.put(
            request("u2", "final one", final=True, created_at=0.85)
        )
        await queue.put(request("u3", "partial three", created_at=0.90))
        removed = await queue.drop_partials()
        self.assertEqual(removed, 2)
        self.assertEqual(queue.qsize(), 1)
        remaining = await queue.get()
        self.assertIsNotNone(remaining)
        self.assertTrue(remaining.final)
        self.assertEqual(remaining.original, "final one")
        queue.task_done()
        await queue.join()


if __name__ == "__main__":
    unittest.main()
