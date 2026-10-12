import unittest
from datetime import datetime, timezone
from blygger.core import timefmt

class TestTimefmt(unittest.TestCase):
    def setUp(self):
        self.dt = datetime(2026, 7, 18, 9, 30, 0, tzinfo=timezone.utc)

    def test_to_iso(self):
        self.assertEqual(timefmt.to_iso(self.dt), "2026-07-18T09:30:00Z")

    def test_parse_iso_roundtrip(self):
        self.assertEqual(timefmt.parse_iso("2026-07-18T09:30:00Z"), self.dt)

    def test_to_rfc822_is_gmt(self):
        self.assertEqual(timefmt.to_rfc822(self.dt), "Sat, 18 Jul 2026 09:30:00 GMT")
