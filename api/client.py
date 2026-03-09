from __future__ import annotations

import sys
import time
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.config import (
    API_BASE,
    FULL_SELECT,
    OA_ID_PREFIX,
    REQUEST_TIMEOUT,
    STUB_SELECT,
    MAX_RETRIES,
    RATE_LIMIT_WAIT,
)
from core.style import styled, Colour


def _build_session(email=None):
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist={500, 502, 503, 504},
        allowed_methods={"GET"},
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    ua = "litgraph/1.0 (https://github.com/your-repo/litgraph)"
    if email:
        ua += f"; mailto:{email}"
    session.headers["User-Agent"] = ua
    return session


class OpenAlexClient:
    def __init__(self, email=None):
        self._session = _build_session(email)

    def fetch_paper(self, work_id: str):
        if work_id.startswith("W") and work_id[1:].isdigit():
            url = f"{API_BASE}/works/{work_id}"
        elif work_id.lower().startswith("doi:"):
            url = f"{API_BASE}/works/doi:{work_id[4:]}"
        elif work_id.startswith("https://"):
            url = f"{API_BASE}/works/{work_id}"
        else:
            url = f"{API_BASE}/works/{work_id}"
        return self._get(url, params={"select": FULL_SELECT})

    def fetch_papers_by_ids(self, work_ids: list[str]):
        if not work_ids:
            return []
        full_ids = [
            f"{OA_ID_PREFIX}{wid}" if not wid.startswith("http") else wid
            for wid in work_ids[:50]
        ]
        filter_str = "openalex_id:" + "|".join(full_ids)
        result = self._get(
            f"{API_BASE}/works",
            params={"filter": filter_str, "select": STUB_SELECT, "per_page": 50},
        )
        return (result or {}).get("results", [])

    def search(self, query: str, limit: int = 10):
        res = self._get(
            f"{API_BASE}/works",
            params={"search": query, "select": STUB_SELECT, "per_page": limit},
        )
        return (res or {}).get('results', [])

    def _get(
        self,
        url: str,
        params: Optional[dict] = None,
        *,
        _attempt: int = 0,
    ):
        try:
            resp = self._session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            print(styled(f" Network error: {exc}", Colour.RED), file=sys.stderr)
            return None

        if resp.status_code == 200:
            return resp.json()

        if resp.status_code == 429:
            if _attempt >= MAX_RETRIES:
                print(styled(' gave up after retries', Colour.RED), file=sys.stderr)
                return None
            wait = RATE_LIMIT_WAIT * (2 ** _attempt)
            print(styled(f" Rate limited — waiting {wait}s (attempt {_attempt + 1})", Colour.YELLOW))
            time.sleep(wait)
            return self._get(url, params, _attempt=_attempt + 1)

        if resp.status_code == 404:
            print(styled(f' not found: {url}', Colour.RED), file=sys.stderr)
        else:
            print(styled(f' HTTP {resp.status_code}: {url}', Colour.RED), file=sys.stderr)

        return None
