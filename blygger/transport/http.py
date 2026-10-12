"""HTTP transport over urllib with fetch hygiene (spec 12.2-12.3, 14)."""
import urllib.request
import urllib.error
import urllib.parse
from .base import Transport, Response

_MAX_REDIRECTS = 5
_MAX_BYTES = 5 * 1024 * 1024
_TIMEOUT = 30


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # we follow manually to track final_url


class HttpTransport(Transport):
    def __init__(self, generator="blygger-ref/0.1", max_redirects=_MAX_REDIRECTS,
                 max_bytes=_MAX_BYTES, timeout=_TIMEOUT):
        self.user_agent = generator
        self.max_redirects = max_redirects
        self.max_bytes = max_bytes
        self.timeout = timeout
        self._opener = urllib.request.build_opener(_NoRedirect())

    def get(self, url: str, *, etag=None, last_modified=None) -> Response:
        current = url
        for _ in range(self.max_redirects + 1):
            req = urllib.request.Request(current, method="GET")
            req.add_header("User-Agent", self.user_agent)
            if etag:
                req.add_header("If-None-Match", etag)
            if last_modified:
                req.add_header("If-Modified-Since", last_modified)
            try:
                resp = self._opener.open(req, timeout=self.timeout)
            except urllib.error.HTTPError as e:
                if e.code in (301, 302, 303, 307, 308):
                    loc = e.headers.get("Location")
                    if not loc:
                        return Response(status=e.code, body=b"", final_url=current)
                    current = urllib.parse.urljoin(current, loc)
                    continue
                if e.code == 304:
                    return Response(status=304, body=b"", final_url=current,
                                    headers=dict(e.headers))
                return Response(status=e.code, body=b"", final_url=current,
                                headers=dict(e.headers))
            except (urllib.error.URLError, OSError):
                return Response(status=0, body=b"", final_url=current)
            with resp:
                body = resp.read(self.max_bytes + 1)
                if len(body) > self.max_bytes:
                    body = body[:self.max_bytes]
                return Response(status=resp.status, body=body,
                                final_url=resp.geturl(), headers=dict(resp.headers))
        return Response(status=0, body=b"", final_url=current)
