from functools import cache

import httpx

from common.settings import settings
from common.utils import get_headers


@cache
def get_sync_client():
    transport = httpx.HTTPTransport(retries=settings.MAX_HTTP_RETRIES)
    return httpx.Client(headers=get_headers(), transport=transport)
