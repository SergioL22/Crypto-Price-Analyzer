"""Bounded interactive-history cache. Never used implicitly by dataset capture."""
from collections import OrderedDict,deque
from copy import deepcopy
from math import ceil,isfinite
from threading import Lock
from time import monotonic
from stock_provider import StockDataError


class HistoryCache:
    def __init__(self,*,clock=monotonic,ttl=300,capacity=16,cooldown=60,request_limit=6,budget_window=60):
        if type(capacity) is not int or capacity<1 or not isfinite(ttl) or not isfinite(cooldown) or ttl<=0 or cooldown<=0:raise ValueError('Positive finite cache bounds required')
        if type(request_limit) is not int or request_limit<1 or isinstance(budget_window,bool) or not isfinite(budget_window) or budget_window<=0:raise ValueError('Positive finite request budget required')
        self.request_limit=request_limit;self.budget_window=budget_window;self._attempts=deque()
        self.clock=clock;self.ttl=ttl;self.capacity=capacity;self.cooldown=cooldown
        self._items=OrderedDict();self._lock=Lock();self._retry=0;self._error=None

    def load(self,key,fetch,now,*,refresh=False):
        # Serializing cache misses avoids duplicate provider calls for concurrent clicks.
        with self._lock:
            current=self.clock();entry=self._items.get(key)
            if not refresh and entry and current-entry['stored']<self.ttl:
                self._items.move_to_end(key)
                return deepcopy(entry['bars']),dict(cache_hit=True,fetched_at_utc=entry['fetched'],age_seconds=max(0,int(current-entry['stored'])))
            if current<self._retry:
                raise StockDataError(self._error,'Provider requests are paused after an error. Retry manually after the cooldown.',retry_after_seconds=ceil(self._retry-current))
            while self._attempts and current-self._attempts[0]>=self.budget_window:self._attempts.popleft()
            if len(self._attempts)>=self.request_limit:
                wait=max(1,ceil(self.budget_window-(current-self._attempts[0])))
                raise StockDataError('stock_budget','Interactive history request budget reached. Wait before requesting fresh history.',retry_after_seconds=wait)
            # Failed upstream attempts count too. Cache reads above consume no slot.
            self._attempts.append(current)
            try:bars=fetch()
            except StockDataError as error:
                self._retry=self.clock()+self.cooldown;self._error=error.code
                raise StockDataError(error.code,str(error),retry_after_seconds=ceil(self.cooldown)) from None
            self._retry=0;self._error=None
            self._items[key]=dict(bars=deepcopy(bars),stored=current,fetched=now.isoformat())
            self._items.move_to_end(key)
            while len(self._items)>self.capacity:self._items.popitem(last=False)
            return deepcopy(bars),dict(cache_hit=False,fetched_at_utc=now.isoformat(),age_seconds=0)
