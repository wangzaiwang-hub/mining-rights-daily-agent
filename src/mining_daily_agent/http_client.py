"""HTTP helpers with cache, timeouts, and URL validation."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import httpx

from mining_daily_agent.cache import read_cached, write_cached

USER_AGENT = "mining-rights-daily-agent/0.1 (+https://example.local/interview)"


class FetchError(RuntimeError):
    """Raised when an external fetch fails in a user-actionable way."""


def is_http_url(value: str) -> bool:
    """Return true when the value is an HTTP(S) URL."""

    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


async def fetch_bytes(url: str, *, ttl_seconds: int = 1800) -> bytes:
    """Fetch bytes from HTTP(S) or local file path with caching for HTTP URLs."""

    if is_http_url(url):
        cached = read_cached("http", url, ttl_seconds)
        if cached is not None:
            return cached
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=httpx.Timeout(20.0, connect=10.0),
                headers={"User-Agent": USER_AGENT},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                payload = response.content
                write_cached("http", url, payload)
                return payload
        except httpx.TimeoutException as exc:
            raise FetchError(
                f"Timed out fetching {url}. Try a narrower query or retry later."
            ) from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise FetchError(
                f"HTTP {status} fetching {url}. Check access, robots, or rate limits."
            ) from exc
        except httpx.HTTPError as exc:
            raise FetchError(f"Could not fetch {url}: {type(exc).__name__}") from exc

    path = Path(url)
    if not path.exists():
        raise FetchError(f"Local file does not exist: {path}")
    return path.read_bytes()


async def fetch_text(url: str, *, ttl_seconds: int = 1800) -> str:
    """Fetch text from HTTP(S) or local file path."""

    payload = await fetch_bytes(url, ttl_seconds=ttl_seconds)
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")
