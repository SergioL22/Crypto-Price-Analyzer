"""Twelve Data transport and validation. No network activity on import."""
from datetime import date
import math
import os
import requests
from assets import Asset, US_EQUITY_MICS


class StockDataError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class TwelveData:
    def __init__(self, *, get=None, key=None):
        self.get = get or requests.get
        self.key = key

    def request(self, endpoint, params):
        key = self.key if self.key is not None else os.environ.get('TWELVE_DATA_API_KEY', '')
        if not isinstance(key, str) or not key.strip():
            raise StockDataError('stock_setup_required', 'Set TWELVE_DATA_API_KEY on the server and restart it to enable stocks and ETFs.')
        try:
            response = self.get('https://api.twelvedata.com/' + endpoint, params=params,
                                headers={'Authorization': 'apikey ' + key.strip()},
                                timeout=(10, 45) if endpoint in ('stocks', 'etf') else 15,
                                allow_redirects=False)
            if response.status_code == 429:
                raise StockDataError('stock_quota', 'Stock provider quota reached. Try again later; no automatic retry was made.')
            if response.status_code in (401, 403):
                raise StockDataError('stock_access', 'Stock provider rejected access. Check the server key and account entitlements.')
            if not 200 <= response.status_code < 300:
                raise StockDataError('stock_unavailable', 'Stock provider is unavailable. Try again later.')
            payload = response.json()
        except (requests.RequestException, ValueError):
            raise StockDataError('stock_unavailable', 'Stock provider did not return usable data.') from None
        if not isinstance(payload, dict):
            raise StockDataError('stock_invalid', 'Stock provider returned an invalid response.')
        if payload.get('status') == 'error':
            code = str(payload.get('code'))
            kind = 'stock_quota' if code == '429' else 'stock_access' if code in ('401', '403') else 'stock_unavailable'
            raise StockDataError(kind, 'Stock data is unavailable for this request. Check account access or try again later.')
        return payload

    def catalog(self):
        result = {}
        for kind, endpoint in (('stock', 'stocks'), ('etf', 'etf')):
            payload = self.request(endpoint, {'country': 'United States'})
            rows = payload.get('data')
            if not isinstance(rows, list):
                raise StockDataError('stock_invalid', 'Stock catalog is unavailable.')
            for row in rows:
                if not isinstance(row, dict):
                    continue
                # Do not guess an exchange from a ticker or an ambiguous name.
                mic = row.get('mic_code')
                if mic not in US_EQUITY_MICS or row.get('currency') != 'USD':
                    continue
                if row.get('country', 'United States') != 'United States':
                    continue
                try:
                    asset = Asset(kind, 'twelvedata', row['symbol'], row['name'], mic, 'USD', 'America/New_York')
                except (ValueError, TypeError, KeyError):
                    continue
                if asset.id in result and result[asset.id] != asset:
                    raise StockDataError('stock_invalid', 'Stock catalog contains conflicting identities.')
                result[asset.id] = asset
        if not result:
            raise StockDataError('stock_invalid', 'No supported US listings were returned by the provider.')
        return sorted(result.values(), key=lambda a: (a.symbol, a.exchange, a.asset_class))

    def history(self, asset, start, end):
        payload = self.request('time_series', dict(symbol=asset.symbol, mic_code=asset.exchange,
            interval='1day', start_date=start, end_date=end, outputsize=5000, order='ASC', adjust='splits'))
        meta, rows = payload.get('meta'), payload.get('values')
        if not isinstance(meta, dict) or not isinstance(rows, list):
            raise StockDataError('stock_invalid', 'Stock history is missing metadata or daily bars.')
        expected = dict(symbol=asset.symbol, mic_code=asset.exchange, currency=asset.currency,
                        interval='1day', exchange_timezone=asset.timezone)
        if any(meta.get(key) != value for key, value in expected.items()):
            raise StockDataError('stock_identity_mismatch', 'Returned stock identity does not match the requested listing.')
        output, seen = [], set()
        try:
            for row in rows:
                day = row['datetime']
                if date.fromisoformat(day).isoformat() != day or day in seen:
                    raise ValueError('Invalid or duplicate date')
                seen.add(day)
                values = {}
                for field in ('open', 'high', 'low', 'close', 'volume'):
                    raw = row[field]
                    if isinstance(raw, bool):
                        raise ValueError('Boolean price')
                    value = float(raw)
                    if not math.isfinite(value) or value < 0 or (field != 'volume' and value == 0):
                        raise ValueError('Invalid price')
                    values[field] = value
                if not values['low'] <= min(values['open'], values['close']) <= max(values['open'], values['close']) <= values['high']:
                    raise ValueError('Inconsistent OHLC')
                if start <= day <= end:
                    output.append(dict(date=day, **values))
        except (ValueError, TypeError, KeyError, OverflowError):
            raise StockDataError('stock_invalid', 'Stock history contains invalid daily bars.') from None
        return sorted(output, key=lambda r: r['date'])
