from __future__ import annotations

import random
import tempfile
import unittest
from pathlib import Path

from cookiekit.selectors import load_rotate_index, save_rotate_index, select_source


class SelectorTests(unittest.TestCase):
    def test_rotate_is_deterministic(self) -> None:
        sources = ["a", "b", "c"]
        selected, idx = select_source(sources, mode="rotate", rotate_index=0)
        self.assertEqual(selected, "a")
        self.assertEqual(idx, 1)

        selected, idx = select_source(sources, mode="rotate", rotate_index=idx)
        self.assertEqual(selected, "b")
        self.assertEqual(idx, 2)

        selected, idx = select_source(sources, mode="rotate", rotate_index=idx)
        self.assertEqual(selected, "c")
        self.assertEqual(idx, 3)

        selected, idx = select_source(sources, mode="rotate", rotate_index=idx)
        self.assertEqual(selected, "a")
        self.assertEqual(idx, 4)

    def test_random_can_be_seeded(self) -> None:
        sources = ["a", "b", "c"]
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        selected1, _ = select_source(sources, mode="random", rng=rng1)
        selected2, _ = select_source(sources, mode="random", rng=rng2)
        self.assertEqual(selected1, selected2)

    def test_rotate_state_file_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "rotate.json"
            self.assertEqual(load_rotate_index(state_file), 0)
            save_rotate_index(state_file, 7)
            self.assertEqual(load_rotate_index(state_file), 7)

            state_file.write_text("{broken", encoding="utf-8")
            self.assertEqual(load_rotate_index(state_file), 0)


if __name__ == "__main__":
    unittest.main()
