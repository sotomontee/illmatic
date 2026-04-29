"""Shared HTTP utilities with curl fallback for restricted environments."""

import asyncio
import shutil
import json
from urllib.parse import urlencode

try:
    import httpx
except ImportError:
    httpx = None


def _clean(text: str) -> str:
    """Normalize line endings."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


async def _curl(url: str, params: dict, accept: str = "text/csv", timeout: int = 45) -> str:
    """Fetch via curl subprocess."""
    full_url = url
    if params:
        full_url = f"{url}?{urlencode(params)}"

    proc = await asyncio.create_subprocess_exec(
        "curl", "-s", "-L", "--max-time", str(timeout),
        "-H", f"Accept: {accept}",
        full_url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"curl failed (rc={proc.returncode}) for {url}: {stderr.decode()}")
    return _clean(stdout.decode())


async def fetch_csv(url: str, params: dict = None, timeout: int = 45) -> str:
    """Fetch a URL expecting CSV/text response. Tries httpx, falls back to curl."""
    params = params or {}

    if httpx is not None:
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as c:
                r = await c.get(url, params=params, headers={"Accept": "text/csv"})
                r.raise_for_status()
                return _clean(r.text)
        except Exception:
            pass

    return await _curl(url, params, accept="text/csv", timeout=timeout)


async def fetch_json(url: str, params: dict = None, timeout: int = 45) -> dict:
    """Fetch a URL expecting JSON response. Tries httpx, falls back to curl."""
    params = params or {}

    if httpx is not None:
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as c:
                r = await c.get(url, params=params)
                r.raise_for_status()
                return r.json()
        except Exception:
            pass

    text = await _curl(url, params, accept="application/json", timeout=timeout)
    return json.loads(text)
