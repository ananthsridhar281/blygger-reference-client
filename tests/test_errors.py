import unittest
from blygger.core.errors import PublishError, Discrepancy

class TestErrors(unittest.TestCase):
    def test_publish_error_is_exception(self):
        with self.assertRaises(PublishError):
            raise PublishError("bad")

    def test_discrepancy_is_a_record(self):
        d = Discrepancy(type="stealth_edit", origin="https://x/", id="7" * 26, detail="hash")
        self.assertEqual(d.type, "stealth_edit")
        self.assertEqual(d.id, "7" * 26)
