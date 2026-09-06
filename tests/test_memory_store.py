"""Unit tests for memory_store.py using hand-constructed embedding vectors.

No Ollama or network access required.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import memory_store


class TestMemoryStore(unittest.TestCase):
    def setUp(self):
        self.conn = memory_store.connect(":memory:")

    def test_search_ranks_closest_vector_first(self):
        memory_store.add_chunk(self.conn, "a.md", "unrelated chunk", [0.0, 1.0, 0.0])
        memory_store.add_chunk(self.conn, "b.md", "near match", [1.0, 0.0, 0.0])
        memory_store.add_chunk(self.conn, "c.md", "exact match", [1.0, 0.0, 0.0001])

        results = memory_store.search(self.conn, [1.0, 0.0, 0.0], k=3)

        self.assertEqual(results[0]["source"], "b.md")
        self.assertEqual(results[1]["source"], "c.md")
        self.assertEqual(results[2]["source"], "a.md")

    def test_search_respects_top_k(self):
        for i in range(5):
            memory_store.add_chunk(self.conn, f"file{i}.md", f"chunk {i}", [1.0, float(i)])

        results = memory_store.search(self.conn, [1.0, 0.0], k=2)

        self.assertEqual(len(results), 2)

    def test_search_on_empty_store_returns_empty_list(self):
        results = memory_store.search(self.conn, [1.0, 0.0], k=3)
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
