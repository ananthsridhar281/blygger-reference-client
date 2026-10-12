import unittest
from blygger.read.poll import PollState

class TestPoll(unittest.TestCase):
    def test_success_resets_interval(self):
        p = PollState(base_interval=60, max_interval=3600)
        p.on_failure(); p.on_failure()
        p.on_success(etag='"abc"')
        self.assertEqual(p.next_interval(), 60)
        self.assertEqual(p.etag, '"abc"')

    def test_failure_backs_off_exponentially(self):
        p = PollState(base_interval=60, max_interval=3600)
        p.on_failure()
        self.assertEqual(p.next_interval(), 120)
        p.on_failure()
        self.assertEqual(p.next_interval(), 240)

    def test_interval_capped_at_max(self):
        p = PollState(base_interval=60, max_interval=100)
        for _ in range(10):
            p.on_failure()
        self.assertEqual(p.next_interval(), 100)

    def test_retry_after_honored(self):
        p = PollState(base_interval=60, max_interval=3600)
        p.on_retry_after(900)
        self.assertEqual(p.next_interval(), 900)
