"""HTTP GET with retries for transient errors (connection problems, 429, 5xx)"""

import logging
import time

import httpx

ATTEMPTS = 4

_logger = logging.getLogger(__name__)


def _is_transient(error: httpx.HTTPError) -> bool:
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        return status == 429 or status >= 500
    return isinstance(error, httpx.TransportError)


def get(client: httpx.Client, url: str) -> httpx.Response:
    """the successful response; raises httpx.HTTPError when all attempts failed or the error is permanent"""
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return client.get(url).raise_for_status()
        except httpx.HTTPError as error:
            if attempt == ATTEMPTS or not _is_transient(error):
                raise
            _logger.debug("Attempt %i for %s failed: %s", attempt, url, error)
            time.sleep(2**attempt)
    raise AssertionError("unreachable")
