"""Shared UTC calendar-day window selection for fresh daily analysis."""
from numbers import Integral
import pandas as pd


def select_daily_window(history, days, *, now=None):
    """Select exactly N UTC calendar dates ending today; never fill missing rows."""
    if (not isinstance(days, Integral) or isinstance(days, bool)) or not 1 <= days <= 365:
        raise ValueError('History window must be 1 to 365 days.')
    days = int(days)
    if not isinstance(history, pd.DataFrame) or 'price' not in history:
        raise ValueError('Historical prices are missing.')
    frame = history.copy(deep=True)
    if 'date' not in frame and not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError('Historical data needs dates or a DatetimeIndex.')
    try:
        dates = pd.to_datetime(frame['date'] if 'date' in frame else frame.index, utc=True, errors='raise')
        frame.index = pd.DatetimeIndex(dates).normalize()
    except (ValueError, TypeError, OverflowError):
        raise ValueError('Historical dates are invalid.') from None
    if frame.index.hasnans or frame.index.has_duplicates:
        raise ValueError('Historical dates must be unique and nonempty.')
    current = pd.Timestamp.now(tz='UTC') if now is None else pd.Timestamp(now)
    current = current.tz_localize('UTC') if current.tzinfo is None else current.tz_convert('UTC')
    end = current.normalize()
    start = end - pd.Timedelta(days=days - 1)
    frame = frame.loc[(frame.index >= start) & (frame.index <= end)].sort_index()
    if frame.empty:
        leading, trailing, internal = days, 0, 0
    else:
        leading = int((frame.index[0] - start).days)
        trailing = int((end - frame.index[-1]).days)
        internal = int((frame.index[-1] - frame.index[0]).days) + 1 - len(frame)
    coverage = {
        'requested_days': days, 'expected_start': start.date().isoformat(),
        'expected_end': end.date().isoformat(), 'observations': len(frame),
        'start': None if frame.empty else frame.index[0].date().isoformat(),
        'end': None if frame.empty else frame.index[-1].date().isoformat(),
        'missing_days': days - len(frame), 'internal_missing_days': internal,
        'leading_missing_days': leading, 'trailing_missing_days': trailing,
        'complete': len(frame) == days,
        'latest_observation_age_days': None if frame.empty else trailing,
        'definition': 'N UTC calendar dates ending today, including the possibly incomplete current day.',
    }
    return frame, coverage
