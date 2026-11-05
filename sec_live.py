"""Fresh SEC filing lists for the covered companies, cached on the server.

Only the server talks to EDGAR, at most once per company per cache window, so
visitor traffic never reaches the SEC. When live access is not configured or
fails, callers fall back to the committed snapshot and say so.
"""
from __future__ import annotations

from threading import Lock
import time

import requests

import sec_edgar

TTL_SECONDS=1800
FAILURE_BACKOFF_SECONDS=300


def requests_fetch(user_agent):
    session=requests.Session();session.headers.update({'User-Agent':user_agent,'Accept-Encoding':'gzip, deflate'})
    def fetch(cik):
        response=session.get(f'https://data.sec.gov/submissions/CIK{cik:010d}.json',timeout=10)
        response.raise_for_status();return response.json()
    return fetch


class LiveFilings:
    def __init__(self,fetch,ttl=TTL_SECONDS,backoff=FAILURE_BACKOFF_SECONDS,clock=time.monotonic,wall=time.time):
        self.fetch=fetch;self.ttl=ttl;self.backoff=backoff;self.clock=clock;self.wall=wall
        self.cache={};self.failed_at={};self.lock=Lock()

    def filings(self,cik):
        """(rows, fetched_at_epoch) or None when no live data is available for this company."""
        now=self.clock()
        with self.lock:
            cached=self.cache.get(cik)
            if cached and now-cached[0]<self.ttl:return cached[1],cached[2]
            if now-self.failed_at.get(cik,-1e18)<self.backoff:return (cached[1],cached[2]) if cached else None
            try:rows=sec_edgar.recent_filings(self.fetch(cik))
            except Exception:
                self.failed_at[cik]=now
                return (cached[1],cached[2]) if cached else None
            self.cache[cik]=(now,rows,self.wall())
            return rows,self.cache[cik][2]


def merge_filings(live,snapshot,limit=20):
    """Live rows first, then snapshot rows not already present (e.g. a predecessor registrant's)."""
    seen={row['accession'] for row in live}
    rows=live+[row for row in snapshot if row['accession'] not in seen]
    return sorted(rows,key=lambda row:row['filed'],reverse=True)[:limit]
