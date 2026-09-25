"""Process-local catalog cache; refreshes are serialized and failures back off."""
from threading import Lock
from time import monotonic
from datetime import datetime, timezone
import re
import api


class CoinCatalog:
    def __init__(self, fetcher=None, clock=monotonic, ttl=3600, retry_delay=60):
        self.fetcher = fetcher or (lambda: api._get('coins/list', {'include_platform': 'false'}))
        self.clock, self.ttl, self.retry_delay = clock, ttl, retry_delay
        self.lock = Lock()
        self.cached = None
        self.expires = self.retry_at = 0

    def get(self):
        with self.lock:
            now = self.clock()
            if self.cached is not None and now < self.expires:
                return {**self.cached, 'stale': False}
            if now >= self.retry_at:
                try:
                    raw = self.fetcher()
                    if not isinstance(raw, list) or not raw:
                        raise ValueError('Invalid catalog')
                    coins = {}
                    for row in raw:
                        if not isinstance(row, dict) or not all(isinstance(row.get(k), str) and row[k].strip() for k in ('id','name','symbol')):
                            raise ValueError('Invalid catalog row')
                        # The existing analysis API accepts lowercase slug IDs only.
                        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', row['id']) or len(row['id']) > 100:
                            continue
                        coins[row['id']] = {k: row[k] for k in ('id','name','symbol')}
                    if not coins: raise ValueError('No supported IDs')
                    self.cached = {'coins': sorted(coins.values(), key=lambda c: (c['name'].casefold(),c['id'])),
                                   'fetched_at_utc': datetime.now(timezone.utc).isoformat()}
                    self.expires = self.clock() + self.ttl
                    self.retry_at = 0
                    return {**self.cached, 'stale': False}
                except (api.UpstreamError, ValueError, TypeError):
                    self.retry_at = self.clock() + self.retry_delay
            if self.cached is not None:
                return {**self.cached, 'stale': True}
            raise api.UpstreamError('Coin catalog unavailable; retry later.')
