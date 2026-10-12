"""Polling policy: conditional requests + backoff (spec 12.3). Pure, no I/O."""


class PollState:
    def __init__(self, base_interval=60, max_interval=3600):
        self.base_interval = base_interval
        self.max_interval = max_interval
        self.failures = 0
        self.etag = None
        self.last_modified = None
        self._retry_after = None

    def on_success(self, etag=None, last_modified=None):
        self.failures = 0
        self._retry_after = None
        if etag is not None:
            self.etag = etag
        if last_modified is not None:
            self.last_modified = last_modified

    def on_failure(self):
        self.failures += 1               # never discards etag/state

    def on_retry_after(self, seconds):
        self._retry_after = seconds

    def next_interval(self):
        if self._retry_after is not None:
            return min(self._retry_after, self.max_interval) if self._retry_after > self.max_interval \
                else self._retry_after
        interval = self.base_interval * (2 ** self.failures)
        return min(interval, self.max_interval)
