"""Filesystem transport: serve an emitted output directory as an origin (spec 7)."""
import hashlib
from pathlib import Path
from .base import Transport, Response


class FsTransport(Transport):
    def __init__(self, origin: str, root: Path):
        if not origin.endswith("/"):
            origin += "/"
        self.origin = origin
        self.root = Path(root)

    def _path_for(self, url: str):
        if not url.startswith(self.origin):
            return None
        rel = url[len(self.origin):]
        return self.root / rel if rel else self.root

    def get(self, url: str, *, etag=None, last_modified=None) -> Response:
        path = self._path_for(url)
        if path is None or not path.is_file():
            return Response(status=404, body=b"", final_url=url)
        body = path.read_bytes()
        tag = '"' + hashlib.sha256(body).hexdigest()[:16] + '"'
        if etag is not None and etag == tag:
            return Response(status=304, body=b"", final_url=url, headers={"ETag": tag})
        return Response(status=200, body=body, final_url=url, headers={"ETag": tag})
