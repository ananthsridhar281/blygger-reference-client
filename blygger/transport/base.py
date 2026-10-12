"""Transport interface. Policy (polling/backoff) lives above this, in read/poll.py."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes
    final_url: str
    headers: dict = field(default_factory=dict)


class Transport(ABC):
    @abstractmethod
    def get(self, url: str, *, etag=None, last_modified=None) -> Response:
        ...
