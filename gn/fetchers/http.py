"""Wspólny klient HTTP: identyfikowalny User-Agent, timeout, jedna próba ponowienia."""
from __future__ import annotations

import time

import requests

USER_AGENT = "grodzisk-news-bot/0.1 (+https://github.com/maciejkfrankowski/grodzisk-news)"
TIMEOUT = 25


def get(url: str) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            response = requests.get(
                url,
                timeout=TIMEOUT,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "pl"},
            )
            response.raise_for_status()
            return response
        except requests.RequestException as error:  # noqa: PERF203
            last_error = error
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"{url}: {last_error}")
