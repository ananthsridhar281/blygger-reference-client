import unittest
from blygger.core import ids

class TestIds(unittest.TestCase):
    def test_new_id_is_26_lowercase_crockford_chars(self):
        i = ids.new_id()
        self.assertEqual(len(i), 26)
        self.assertTrue(all(c in ids.ALPHABET for c in i))
        for bad in "ilou":
            self.assertNotIn(bad, ids.ALPHABET)

    def test_new_ids_are_unique(self):
        self.assertEqual(len({ids.new_id() for _ in range(1000)}), 1000)

    def test_is_valid_id(self):
        self.assertTrue(ids.is_valid_id(ids.new_id()))
        self.assertFalse(ids.is_valid_id("too-short"))
        self.assertFalse(ids.is_valid_id("A" * 26))          # uppercase
        self.assertFalse(ids.is_valid_id("i" * 26))          # excluded letter
        self.assertFalse(ids.is_valid_id("7c9wk2mhq0v3xj8tn5rzfd41b"))  # 25 chars

if __name__ == "__main__":
    unittest.main()
