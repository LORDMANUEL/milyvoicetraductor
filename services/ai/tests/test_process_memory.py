import unittest

from mily_ai.process_memory import (
    ProcessTreeMemorySnapshot,
    aggregate_process_tree,
    descendant_pids,
)


class ProcessMemoryTests(unittest.TestCase):
    def test_nested_sidecars_are_counted_but_unrelated_processes_are_not(self):
        parents = {11: 1, 12: 11, 13: 99, 14: 12}
        self.assertEqual(descendant_pids(1, parents), {1, 11, 12, 14})
        snapshot = aggregate_process_tree(
            1,
            parents,
            {
                1: (100.0, 120.0),
                11: (200.0, 220.0),
                12: (300.0, 350.0),
                13: (900.0, 950.0),
                14: (50.0, 55.0),
            },
        )
        self.assertEqual(snapshot.process_count, 4)
        self.assertEqual(snapshot.current_mb, 650.0)
        self.assertEqual(snapshot.peak_mb, 745.0)

    def test_missing_or_exited_child_is_ignored_safely(self):
        snapshot = aggregate_process_tree(
            1,
            {2: 1, 3: 2},
            {1: (80.0, 90.0), 2: (20.0, 25.0)},
        )
        self.assertEqual(
            snapshot,
            ProcessTreeMemorySnapshot(
                current_mb=100.0,
                peak_mb=115.0,
                process_count=2,
            ),
        )


if __name__ == "__main__":
    unittest.main()
