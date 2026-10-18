import unittest
from unittest import mock

from shelf import export


class SnapshotTest(unittest.TestCase):
    def test_snapshot_text_for_two_skus(self):
        self.assertEqual(export.snapshot_text({"B-2": 0, "A-10": 7}), "SHELF/2\nA-10;7\nB-2;0\n")

    def test_each_row_is_built_once(self):
        with mock.patch.object(export, "_row", wraps=export._row) as row:
            export.snapshot_text({"A-10": 7, "B-2": 0})
        self.assertEqual(row.call_count, 2)


if __name__ == "__main__":
    unittest.main()
