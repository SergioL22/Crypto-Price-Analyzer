"""Session-aware stock research, isolated from legacy crypto persistence."""
from datetime import timedelta
from threading import Lock
from time import monotonic
import math
import pandas as pd
import exchange_calendars as calendars
import analysis
from stock_provider import TwelveData, StockDataError
from stock_cache import HistoryCache
from stock_validation import validate_bars


def session_window(days, now):
    if type(days) is not int or not 1 <= days <= 3660:
        raise ValueError('History days must be an integer from 1 to 3660')
    current = pd.Timestamp(now)
    if current.tzinfo is None:
        raise ValueError('Current time must have a timezone')
    end = current.tz_convert('America/New_York').date()
    start = end - timedelta(days=days - 1)
    # These US venues share the regular-session holiday schedule. No extended hours.
    calendar = calendars.get_calendar('XNYS', start=str(start - timedelta(days=10)), end=str(end + timedelta(days=10)))
    schedule = calendar.schedule.loc[str(start):str(end)]
    # A closed session is eligible, but the provider may not have published its bar yet.
    eligible = schedule[schedule['close'] <= current]
    return str(start), str(end), [d.date().isoformat() for d in eligible.index]


class StockService:
    def __init__(self, *, provider=None, clock=None, history_ttl=300, history_capacity=16, error_cooldown=60,history_request_limit=6,history_budget_window=60):
        self.provider = provider or TwelveData()
        self.clock = clock or monotonic
        self.history_cache=HistoryCache(clock=self.clock,ttl=history_ttl,capacity=history_capacity,cooldown=error_cooldown,request_limit=history_request_limit,budget_window=history_budget_window)
        self._lock = Lock()
        self._assets = []
        self._loaded = float('-inf')
        self._retry = float('-inf')
        self._fetched = None

    def catalog(self, now):
        with self._lock:
            current = self.clock()
            stale = current - self._loaded >= 86400
            if stale and current >= self._retry:
                try:
                    assets = self.provider.catalog()
                except StockDataError:
                    self._retry = current + 60
                    if not self._assets:
                        raise
                else:
                    self._assets, self._loaded = assets, current
                    self._fetched = now.isoformat()
                    stale = False
            if not self._assets:
                raise StockDataError('stock_unavailable', 'Stock catalog is temporarily unavailable. Retry after one minute.')
            return dict(assets=[a.public() for a in self._assets], stale=stale, fetched_at_utc=self._fetched,
                        coverage='Supported US USD listings with explicit MICs. Catalog inclusion does not guarantee account access. Delisted coverage and permanent security identity are not available.')

    def research(self, asset_id, days, now, *, use_cache=False,refresh=False):
        start, end, sessions = session_window(days, now)
        self.catalog(now)
        with self._lock:
            asset = next((a for a in self._assets if a.id == asset_id), None)
        if asset is None:
            raise StockDataError('stock_not_found', 'Select a supported listing from the stock catalog.')
        expected = set(sessions)
        # Drop an intraday/current bar; reject bars on an actual non-trading date.
        all_sessions = set(calendars.get_calendar('XNYS').sessions_in_range(start, end).strftime('%Y-%m-%d'))
        def fetch():
            bars=validate_bars(self.provider.history(asset,start,end),start,end)
            if any(b['date'] not in all_sessions for b in bars):
                raise StockDataError('stock_invalid','Provider returned a bar on a non-trading date.')
            return [b for b in bars if b['date'] in expected]
        if use_cache:
            key=(asset.id,start,end,sessions[-1] if sessions else None,'splits')
            bars,source=self.history_cache.load(key,fetch,now,refresh=refresh)
        else:
            bars=fetch();source=dict(cache_hit=False,fetched_at_utc=now.isoformat(),age_seconds=0)
        observed = {b['date'] for b in bars}
        missing = [day for day in sessions if day not in observed]
        complete = not missing and bool(bars)
        indicators = None
        points = []
        prices = pd.Series([b['close'] for b in bars], dtype=float)
        ma7, ma25 = prices.rolling(7).mean(), prices.rolling(25).mean()
        mid, upper, lower = analysis.compute_bollinger_bands(prices)
        def finite(value):
            return float(value) if math.isfinite(value) else None
        previous = None
        positions = {day: index for index, day in enumerate(sessions)}
        for i, bar in enumerate(bars):
            position = positions[bar['date']]
            points.append(dict(date=bar['date'], price=bar['close'], ma_7=finite(ma7.iloc[i]), ma_25=finite(ma25.iloc[i]),
                bollinger_lower=finite(lower.iloc[i]), bollinger_middle=finite(mid.iloc[i]), bollinger_upper=finite(upper.iloc[i]),
                break_before=previous is not None and position != previous + 1))
            previous = position
        if complete and len(bars) >= 35:
            macd, signal, hist = analysis.compute_macd(prices)
            indicators = dict(rsi_14=finite(analysis.compute_rsi(prices)), ma_7=finite(ma7.iloc[-1]), ma_25=finite(ma25.iloc[-1]),
                macd=finite(macd.iloc[-1]), macd_signal=finite(signal.iloc[-1]), macd_histogram=finite(hist.iloc[-1]),
                bollinger_lower=finite(lower.iloc[-1]), bollinger_middle=finite(mid.iloc[-1]), bollinger_upper=finite(upper.iloc[-1]))
        else:
            # Never imply indicators calculated across missing sessions are comparable.
            for point in points:
                for key in ('ma_7', 'ma_25', 'bollinger_lower', 'bollinger_middle', 'bollinger_upper'):
                    point[key] = None
        return dict(asset=asset.public(), generated_at_utc=now.isoformat(), adjustment='splits',
            window=dict(start=start, end=end, expected_sessions=len(sessions), observations=len(bars),
                        missing_sessions=missing, complete=complete, latest_closed_session=sessions[-1] if sessions else None),
            history=points, bars=bars, indicators=indicators,history_source=source,
            limitations=['Regular completed US sessions only; the latest bar may be delayed by the provider.',
                         'Prices are requested split-adjusted; dividends are excluded. This is not total return.',
                         'No point-in-time corporate-action archive or guaranteed delisted coverage.',
                         'Indicators require at least 35 observations and no missing sessions. No stock AI forecast or measured prediction accuracy yet.'])
